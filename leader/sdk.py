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
from typing import Optional

from .models import Task, TaskCategory, TaskResult, RouteDecision
from .registry import Registry
from .logger import TaskLogger
from .router import Router
from .executor import Executor
from . import config as cfg_module


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

        # Synchronous usage:
        result = leader.run_sync("your task here")
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        auto_load_config: bool = True,
    ):
        self.registry = Registry()
        self.warnings: list[str] = []

        if auto_load_config:
            path = Path(config_path) if config_path else cfg_module.CONFIG_PATH
            self.warnings = cfg_module.load(self.registry, path)

        self.logger = TaskLogger()
        self.router = Router(self.registry, self.logger)
        self.executor = Executor(self.registry)

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
