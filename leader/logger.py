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

from .models import RouteDecision, Task, TaskResult

DEFAULT_DB = Path.home() / ".leader" / "history.db"

# Current schema version — bump this when adding migrations
SCHEMA_VERSION = 1


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

        # Future migrations go here:
        # if current < 2:
        #     self._migration_v2()

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

    # ── Example future migration ─────────────────────────────────────────────
    # def _migration_v2(self):
    #     """Add model_used column to results."""
    #     try:
    #         self.conn.execute("ALTER TABLE results ADD COLUMN model_used TEXT DEFAULT ''")
    #         self.conn.commit()
    #     except sqlite3.OperationalError:
    #         pass  # Column already exists (idempotent)

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

    def log_result(self, result: TaskResult):
        self.conn.execute(
            "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)",
            (
                result.task_id,
                result.backend_id,
                int(result.success),
                result.latency_ms,
                result.cost_estimate,
                result.error,
                time.time(),
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
