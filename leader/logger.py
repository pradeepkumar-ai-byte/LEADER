"""
Leader – task logger

Persists every task dispatch and its result to a local SQLite database.
This is the memory the evolutionary router learns from over time.

Schema versioning: uses SQLite PRAGMA user_version to track migrations.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .models import (
    ChainSession,
    ChainStep,
    ChainStepVerdict,
    RouteDecision,
    Task,
    TaskResult,
)

DEFAULT_DB = Path.home() / ".leader" / "history.db"

# Current schema version — bump this when adding migrations
SCHEMA_VERSION = 3


class TaskLogger:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = DEFAULT_DB
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(db_path))
        self._migrate()

    # ── schema migrations ────────────────────────────────────────────────────

    def _get_version(self) -> int:
        cur = self.conn.execute("PRAGMA user_version")
        return cur.fetchone()[0]

    def _set_version(self, version: int) -> None:
        self.conn.execute(f"PRAGMA user_version = {version}")
        self.conn.commit()

    def _migrate(self):
        """Run all pending migrations in order."""
        current = self._get_version()

        if current < 1:
            self._migration_v1()

        if current < 2:
            self._migration_v2()

        if current < 3:
            self._migration_v3()

        # Future migrations go here:
        # if current < 4:
        #     self._migration_v4()

        if current < SCHEMA_VERSION:
            self._set_version(SCHEMA_VERSION)

    def _migration_v1(self):
        """Initial schema: dispatches, results, feedback tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS dispatches (
                task_id     TEXT PRIMARY KEY,
                category    TEXT,
                prompt_len  INTEGER,
                backend_id  TEXT,
                rationale   TEXT,
                timestamp   REAL
            );
            CREATE TABLE IF NOT EXISTS results (
                task_id      TEXT PRIMARY KEY,
                backend_id   TEXT,
                success      INTEGER,
                latency_ms   REAL,
                cost_usd     REAL,
                error        TEXT,
                timestamp    REAL,
                FOREIGN KEY (task_id) REFERENCES dispatches(task_id)
            );
            CREATE TABLE IF NOT EXISTS feedback (
                task_id   TEXT,
                rating    INTEGER,   -- 1-5, given by user
                comment   TEXT,
                timestamp REAL
            );
        """)
        self.conn.commit()

    def _migration_v2(self):
        """Add safety-alignment compliance columns to results table."""
        try:
            self.conn.execute(
                "ALTER TABLE results ADD COLUMN alignment_failure_triggered INTEGER DEFAULT 0"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists (idempotent)

        try:
            self.conn.execute(
                "ALTER TABLE results ADD COLUMN security_exception_payload TEXT DEFAULT NULL"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists (idempotent)

    def _migration_v3(self):
        """Add multi-agent chain session and granular step diagnostic tables.

        Provides complete forensic auditability across inter-agent workflows,
        recording loop detections, semantic drift distances, and administrative break actions.
        """
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS chain_sessions (
                chain_id        TEXT PRIMARY KEY,
                root_prompt     TEXT,
                total_steps     INTEGER DEFAULT 0,
                max_drift       REAL DEFAULT 0.0,
                status          TEXT DEFAULT 'completed',
                timestamp       REAL
            );
            CREATE TABLE IF NOT EXISTS chain_steps (
                step_id             TEXT PRIMARY KEY,
                chain_id            TEXT,
                parent_step_id      TEXT,
                step_index          INTEGER,
                source_backend      TEXT,
                target_backend      TEXT,
                input_payload       TEXT,
                output_payload      TEXT,
                drift_score         REAL,
                semantic_similarity REAL,
                loop_detected       INTEGER DEFAULT 0,
                loop_pattern        TEXT,
                action_taken        TEXT,
                timestamp           REAL,
                FOREIGN KEY (chain_id) REFERENCES chain_sessions(chain_id)
            );
        """)
        self.conn.commit()

    # ── logging ──────────────────────────────────────────────────────────────

    def log_dispatch(self, task: Task, decision: RouteDecision):
        self.conn.execute(
            "INSERT OR REPLACE INTO dispatches VALUES (?,?,?,?,?,?)",
            (
                task.task_id,
                task.category.value if task.category else None,
                len(task.prompt),
                decision.primary,
                decision.rationale,
                time.time(),
            ),
        )
        self.conn.commit()

    def log_result(
        self,
        result: TaskResult,
        alignment_failure: bool = False,
        security_payload: str | None = None,
    ):
        """Persist a task result with optional safety-alignment metadata.

        Args:
            result:             The TaskResult from the executor.
            alignment_failure:  True if the firewall's post-execution validator
                                detected that this backend executed an unsafe prompt.
            security_payload:   Raw prompt or rule-match summary that triggered
                                the alignment failure (for audit trail).
        """
        self.conn.execute(
            "INSERT OR REPLACE INTO results "
            "(task_id, backend_id, success, latency_ms, cost_usd, error, "
            "timestamp, alignment_failure_triggered, security_exception_payload) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                result.task_id,
                result.backend_id,
                int(result.success),
                result.latency_ms,
                result.cost_estimate,
                result.error,
                time.time(),
                int(alignment_failure),
                security_payload,
            ),
        )
        self.conn.commit()

    def log_feedback(self, task_id: str, rating: int, comment: str = ""):
        self.conn.execute(
            "INSERT INTO feedback VALUES (?,?,?,?)",
            (task_id, rating, comment, time.time()),
        )
        self.conn.commit()

    def win_rates(self) -> dict[str, dict[str, float]]:
        """
        Return win_rates[backend_id][category] = success_rate (0-1).
        This is what the router uses to evolve its dispatch strategy.
        """
        cur = self.conn.execute("""
            SELECT d.backend_id, d.category, AVG(r.success) as rate
            FROM dispatches d
            JOIN results r ON d.task_id = r.task_id
            GROUP BY d.backend_id, d.category
        """)
        rates: dict[str, dict[str, float]] = {}
        for backend_id, category, rate in cur.fetchall():
            rates.setdefault(backend_id, {})[category or "general"] = rate
        return rates

    def avg_latency(self) -> dict[str, float]:
        cur = self.conn.execute(
            "SELECT backend_id, AVG(latency_ms) FROM results GROUP BY backend_id"
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    def feedback_scores(self) -> dict[str, float]:
        """
        Return feedback_scores[backend_id] = average_rating (1-5 scale, normalised to 0-1).
        Joins feedback with dispatches to map ratings back to the backend that handled the task.
        """
        cur = self.conn.execute("""
            SELECT d.backend_id, AVG(f.rating) as avg_rating
            FROM feedback f
            JOIN dispatches d ON f.task_id = d.task_id
            GROUP BY d.backend_id
        """)
        # Normalise 1-5 rating to 0-1 range
        return {row[0]: (row[1] - 1) / 4.0 for row in cur.fetchall()}

    # ── multi-agent chain telemetry ──────────────────────────────────────────

    def log_chain_session(self, session: ChainSession) -> None:
        """Persist or update high-level multi-agent workflow session metadata."""
        self.conn.execute(
            "INSERT OR REPLACE INTO chain_sessions VALUES (?,?,?,?,?,?)",
            (
                session.chain_id,
                session.root_prompt,
                session.total_steps,
                session.max_drift,
                session.status,
                time.time(),
            ),
        )
        self.conn.commit()

    def log_chain_step(
        self,
        step: ChainStep,
        verdict: ChainStepVerdict,
        output_payload: str = "",
    ) -> None:
        """Persist granular step-level telemetry for a multi-agent delegation hop."""
        self.conn.execute(
            "INSERT OR REPLACE INTO chain_steps VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                step.step_id,
                step.chain_id,
                step.parent_step_id,
                step.step_index,
                step.source_backend,
                step.target_backend or "router",
                step.prompt,
                output_payload,
                verdict.drift_result.drift_score,
                verdict.drift_result.similarity,
                int(verdict.loop_result.is_loop),
                verdict.loop_result.loop_type if verdict.loop_result.is_loop else None,
                verdict.action.value,
                time.time(),
            ),
        )
        self.conn.commit()

    def get_chain_history(self, chain_id: str) -> list[dict]:
        """Return full ordered step telemetry history for an audited chain_id."""
        cur = self.conn.execute(
            """
            SELECT step_id, parent_step_id, step_index, source_backend, target_backend,
                   input_payload, output_payload, drift_score, semantic_similarity,
                   loop_detected, loop_pattern, action_taken, timestamp
            FROM chain_steps
            WHERE chain_id = ?
            ORDER BY step_index ASC, timestamp ASC
            """,
            (chain_id,),
        )
        columns = [
            "step_id",
            "parent_step_id",
            "step_index",
            "source_backend",
            "target_backend",
            "input_payload",
            "output_payload",
            "drift_score",
            "semantic_similarity",
            "loop_detected",
            "loop_pattern",
            "action_taken",
            "timestamp",
        ]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def get_chain_analytics(self) -> dict:
        """Return aggregate statistics across all recorded multi-agent chains."""
        cur_sessions = self.conn.execute(
            "SELECT COUNT(*), AVG(total_steps), MAX(max_drift) FROM chain_sessions"
        )
        s_count, s_avg_steps, s_max_drift = cur_sessions.fetchone()

        cur_loops = self.conn.execute("SELECT COUNT(*) FROM chain_steps WHERE loop_detected = 1")
        loop_count = cur_loops.fetchone()[0]

        cur_terminations = self.conn.execute(
            "SELECT status, COUNT(*) FROM chain_sessions GROUP BY status"
        )
        status_counts = {row[0]: row[1] for row in cur_terminations.fetchall()}

        return {
            "total_chains": s_count or 0,
            "avg_chain_steps": round(s_avg_steps or 0.0, 2),
            "peak_semantic_drift": round(s_max_drift or 0.0, 4),
            "loops_isolated": loop_count or 0,
            "chain_statuses": status_counts,
        }
