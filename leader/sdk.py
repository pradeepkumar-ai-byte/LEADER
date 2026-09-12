"""
Leader – SDK

The single entry point for embedding Leader inside any application.
Three lines to add multi-backend AI routing to your app:

    from leader.sdk import Leader
    leader = Leader()
    result = await leader.run("summarize my emails")

Or synchronously:

    result = leader.run_sync("summarize my emails")
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from . import config as cfg_module
from .chain_diagnostics import ChainMonitor
from .executor import Executor
from .logger import TaskLogger
from .models import (
    ChainAction,
    ChainSession,
    ChainStep,
    RouteDecision,
    Task,
    TaskCategory,
    TaskResult,
)
from .registry import Registry
from .router import Router


class Leader:
    """
    Leader SDK — embed multi-backend AI routing in any application.

    Usage:
        leader = Leader()
        result = await leader.run("your task here")

        # Or with options:
        result = await leader.run(
            "optimize this SQL query",
            category="coding",
            parallel=True,
        )

        # Multi-agent chain execution with loop isolation & drift diagnostics:
        session = await leader.run_chain(
            root_prompt="Analyze churn data and build report",
            steps=["Extract DB metrics", "Plot chart", "Write executive summary"],
        )

        # Synchronous usage:
        result = leader.run_sync("your task here")
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        auto_load_config: bool = True,
        chain_monitor: ChainMonitor | None = None,
    ):
        self.registry = Registry()
        self.warnings: list[str] = []

        if auto_load_config:
            path = Path(config_path) if config_path else cfg_module.CONFIG_PATH
            self.warnings = cfg_module.load(self.registry, path)

        self.logger = TaskLogger()
        self.router = Router(self.registry, self.logger)
        self.executor = Executor(self.registry)
        self.chain_monitor = chain_monitor or ChainMonitor()

    # ── core API ─────────────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str,
        category: str | TaskCategory | None = None,
        parallel: bool = False,
        timeout: int | None = None,
    ) -> TaskResult:
        """
        Route and execute a task. Returns a TaskResult.

        Args:
            prompt:   The task description.
            category: Optional task category (e.g. "coding", "research").
                      Auto-classified if not provided.
            parallel: If True, race all backends and return the fastest result.
            timeout:  Override default timeout (seconds).
        """
        if isinstance(category, str):
            category = TaskCategory(category)

        task = Task(prompt=prompt, category=category)
        decision = self.router.decide(task)

        if timeout:
            self.executor.timeout = timeout

        self.logger.log_dispatch(task, decision)
        result = await self.executor.run(task, decision, parallel=parallel)
        self.logger.log_result(result)

        return result

    def run_sync(
        self,
        prompt: str,
        category: str | TaskCategory | None = None,
        parallel: bool = False,
        timeout: int | None = None,
    ) -> TaskResult:
        """Synchronous wrapper around run(). Safe to call from non-async code."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop — use a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.run(prompt, category=category, parallel=parallel, timeout=timeout),
                )
                return future.result()
        else:
            return asyncio.run(
                self.run(prompt, category=category, parallel=parallel, timeout=timeout)
            )

    # ── multi-agent chain execution ──────────────────────────────────────────

    async def run_chain(
        self,
        root_prompt: str,
        steps: list[ChainStep] | list[str],
        chain_id: str | None = None,
        stop_on_error: bool = True,
        timeout: int | None = None,
    ) -> ChainSession:
        """
        Execute an end-to-end multi-agent delegation chain with active loop isolation
        and real-time semantic drift diagnostics.

        Args:
            root_prompt:   The user's original alignment prompt initiating the workflow.
            steps:         List of ChainStep objects or prompt strings representing hops.
            chain_id:      Optional explicit session ID (auto-generated if omitted).
            stop_on_error: If True, halts execution if any step fails or trips safety breaks.
            timeout:       Per-step execution timeout in seconds.

        Returns:
            ChainSession containing step verdicts, results, max drift, and final status.
        """
        import uuid

        session_id = chain_id or uuid.uuid4().hex
        session = ChainSession(
            chain_id=session_id,
            root_prompt=root_prompt,
            status="completed",
        )

        parent_prompt: str | None = None
        max_drift: float = 0.0

        for i, step_item in enumerate(steps):
            if isinstance(step_item, str):
                step = ChainStep(
                    prompt=step_item,
                    step_index=i,
                    chain_id=session_id,
                    source_backend="user" if i == 0 else "agent_chain",
                )
            else:
                step = step_item
                step.chain_id = session_id
                step.step_index = i

            # 1. Pre-execution Chain Diagnostic Inspection (Loops + Drift)
            verdict = self.chain_monitor.inspect_step(
                step=step,
                root_prompt=root_prompt,
                parent_prompt=parent_prompt,
            )
            session.step_verdicts.append(verdict)
            if verdict.drift_result.drift_score > max_drift:
                max_drift = verdict.drift_result.drift_score

            # 2. Handle Administrative Termination Actions
            if verdict.action in (ChainAction.TERMINATE_LOOP, ChainAction.TERMINATE_DRIFT):
                session.status = verdict.action.value
                failed_res = TaskResult(
                    task_id=step.step_id,
                    backend_id="safety_chain_monitor",
                    output="",
                    success=False,
                    latency_ms=verdict.latency_ms,
                    error=verdict.summary,
                )
                session.results.append(failed_res)
                self.logger.log_chain_step(step, verdict, output_payload="")
                break

            # 3. Route & Execute Step
            task = Task(prompt=step.prompt, task_id=step.step_id)
            decision = self.router.decide(task)
            step.target_backend = decision.primary

            if timeout:
                self.executor.timeout = timeout

            self.logger.log_dispatch(task, decision)
            raw_result = await self.executor.run(task, decision)

            # 4. Post-Execution Safety Validation (Circuit Breaker)
            validated_result = self.router.validate_response(raw_result)
            session.results.append(validated_result)

            self.logger.log_result(validated_result)
            self.logger.log_chain_step(step, verdict, output_payload=validated_result.output)

            parent_prompt = step.prompt

            if not validated_result.success and stop_on_error:
                session.status = "step_failed"
                break

        session.total_steps = len(session.results)
        session.max_drift = max_drift
        self.logger.log_chain_session(session)

        # Clear active in-memory chain tracking upon termination/completion
        self.chain_monitor.loop_detector.clear_chain(session_id)

        return session

    def run_chain_sync(
        self,
        root_prompt: str,
        steps: list[ChainStep] | list[str],
        chain_id: str | None = None,
        stop_on_error: bool = True,
        timeout: int | None = None,
    ) -> ChainSession:
        """Synchronous wrapper for multi-agent chain execution."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.run_chain(
                        root_prompt=root_prompt,
                        steps=steps,
                        chain_id=chain_id,
                        stop_on_error=stop_on_error,
                        timeout=timeout,
                    ),
                )
                return future.result()
        else:
            return asyncio.run(
                self.run_chain(
                    root_prompt=root_prompt,
                    steps=steps,
                    chain_id=chain_id,
                    stop_on_error=stop_on_error,
                    timeout=timeout,
                )
            )

    # ── routing only (no execution) ──────────────────────────────────────────

    def route(self, prompt: str, category: str | TaskCategory | None = None) -> RouteDecision:
        """
        Classify and route a task WITHOUT executing it.
        Useful for inspection, logging, or custom execution.
        """
        if isinstance(category, str):
            category = TaskCategory(category)
        task = Task(prompt=prompt, category=category)
        return self.router.decide(task)

    # ── feedback ─────────────────────────────────────────────────────────────

    def feedback(self, task_id: str, rating: int, comment: str = "") -> None:
        """Submit user feedback on a task result (1-5 rating)."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        self.logger.log_feedback(task_id, rating, comment)

    # ── introspection ────────────────────────────────────────────────────────

    def backends(self) -> dict:
        """Return info about all known backends and their connection status."""
        result = {"connected": [], "available": [], "total": 0}
        for spec in self.registry.all():
            entry = {
                "id": spec.id,
                "name": spec.display_name,
                "description": spec.description,
                "strengths": [s.value for s in spec.strengths],
                "connected": spec.connected,
            }
            if spec.connected:
                result["connected"].append(entry)
            else:
                result["available"].append(entry)
        result["total"] = len(result["connected"]) + len(result["available"])
        return result

    def stats(self) -> dict:
        """Return routing performance statistics."""
        return {
            "win_rates": self.logger.win_rates(),
            "avg_latency": self.logger.avg_latency(),
        }

    @property
    def connected_count(self) -> int:
        return len(self.registry.connected())

    @property
    def is_ready(self) -> bool:
        """True if at least one backend is connected and available."""
        return self.connected_count > 0
