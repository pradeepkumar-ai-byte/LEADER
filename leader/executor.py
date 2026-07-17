"""
Leader – executor

Runs tasks with:
- health check before routing
- parallel multi-backend execution (when parallel=True)
- per-task timeout
- automatic fallback chain on failure
- smart retries with exponential backoff (transient errors only)
"""

from __future__ import annotations

import asyncio
import importlib
import time

from .adapters.base import BaseAdapter
from .models import RouteDecision, Task, TaskCategory, TaskResult
from .registry import Registry

DEFAULT_TIMEOUT = 120  # seconds
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds

# ── Exception classification ─────────────────────────────────────────────────
# Only these exception families are considered transient (worth retrying).
# Everything else (TypeError, ValueError, KeyError, AttributeError, …) is a
# programming bug or a permanent configuration error and must fail immediately.
_RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    ConnectionError,  # includes ConnectionRefused, ConnectionReset
    OSError,  # covers socket.error, BrokenPipeError, etc.
    TimeoutError,  # stdlib TimeoutError (parent of asyncio.TimeoutError)
)

# ── Side-effect guard ─────────────────────────────────────────────────────────
# Tasks in these categories trigger real-world actions (send a Slack message,
# fire a Zapier webhook, schedule a cron job).  Retrying them risks duplicate
# delivery, so the executor always fails fast on the first error.
_NO_RETRY_CATEGORIES = frozenset(
    {
        TaskCategory.MESSAGING,
        TaskCategory.AUTOMATION,
    }
)


def _is_retryable(exc: BaseException, task: Task) -> bool:
    """Return True only when the error is transient AND the task is safe to retry."""
    if task.category in _NO_RETRY_CATEGORIES:
        return False
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def _load_adapter(backend_id: str, registry: Registry) -> BaseAdapter | None:
    spec = registry.get(backend_id)
    if spec is None:
        return None
    module_path, class_name = spec.adapter_class.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls(config={**spec.config, "id": backend_id})
    except Exception:
        return None


class Executor:
    def __init__(
        self, registry: Registry, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES
    ):
        self.registry = registry
        self.timeout = timeout
        self.max_retries = max_retries

    async def _run_one(self, backend_id: str, task: Task) -> TaskResult:
        adapter = _load_adapter(backend_id, self.registry)
        if adapter is None or not adapter.is_available():
            return TaskResult(
                task_id=task.task_id,
                backend_id=backend_id,
                output="",
                success=False,
                latency_ms=0,
                error=f"Backend '{backend_id}' not available or misconfigured.",
            )

        last_err: str = ""
        for attempt in range(self.max_retries):
            t0 = time.monotonic()
            try:
                return await asyncio.wait_for(adapter.run(task), timeout=self.timeout)
            except Exception as exc:
                latency = (time.monotonic() - t0) * 1000
                last_err = (
                    f"Timed out after {self.timeout}s"
                    if isinstance(exc, asyncio.TimeoutError)
                    else str(exc)
                )

                # ── Fail fast on non-retryable errors ────────────────────
                if not _is_retryable(exc, task):
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id=backend_id,
                        output="",
                        success=False,
                        latency_ms=latency,
                        error=last_err,
                    )

                # ── Last attempt exhausted ───────────────────────────────
                if attempt == self.max_retries - 1:
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id=backend_id,
                        output="",
                        success=False,
                        latency_ms=latency,
                        error=f"All {self.max_retries} attempts failed. Last error: {last_err}",
                    )

                # ── Exponential back-off before next retry ───────────────
                sleep_time = BACKOFF_BASE * (1.5**attempt)
                print(
                    f"  [leader] {backend_id}: attempt {attempt + 1}/{self.max_retries} "
                    f"failed ({last_err}). Retrying in {sleep_time:.1f}s…"
                )
                await asyncio.sleep(sleep_time)

        # Unreachable in practice, but satisfies type-checkers.
        return TaskResult(  # pragma: no cover
            task_id=task.task_id,
            backend_id=backend_id,
            output="",
            success=False,
            latency_ms=0,
            error=last_err,
        )

    async def run(self, task: Task, decision: RouteDecision, parallel: bool = False) -> TaskResult:
        """
        parallel=False (default): try primary, then fallbacks in order.
        parallel=True:            run primary + all fallbacks simultaneously,
                                  return the first successful result.
        """
        if decision.primary == "none":
            return TaskResult(
                task_id=task.task_id,
                backend_id="none",
                output="",
                success=False,
                latency_ms=0,
                error="No backends connected. Run `leader init` to get started.",
            )

        chain = [decision.primary] + decision.fallback_chain

        if parallel and len(chain) > 1:
            return await self._run_parallel(task, chain)
        return await self._run_sequential(task, chain)

    async def _run_sequential(self, task: Task, chain: list[str]) -> TaskResult:
        last_result = None
        for backend_id in chain:
            result = await self._run_one(backend_id, task)
            last_result = result
            if result.success:
                return result
            print(f"  [leader] {backend_id} failed ({result.error}) — trying fallback…")
        return last_result or TaskResult(
            task_id=task.task_id,
            backend_id="none",
            output="",
            success=False,
            latency_ms=0,
            error="All backends failed.",
        )

    async def _run_parallel(self, task: Task, chain: list[str]) -> TaskResult:
        """Fire all backends at once. Return first success; cancel the rest."""
        tasks_map: dict[asyncio.Task, str] = {}
        loop_tasks = []
        for backend_id in chain:
            t = asyncio.create_task(self._run_one(backend_id, task))
            tasks_map[t] = backend_id
            loop_tasks.append(t)

        best: TaskResult | None = None
        pending = set(loop_tasks)

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for done_task in done:
                result = done_task.result()
                if result.success and best is None:
                    best = result
                    # cancel the rest
                    for p in pending:
                        p.cancel()
                    pending = set()
                    break

        if best:
            return best

        # all failed — collect last results
        results = [t.result() for t in loop_tasks if not t.cancelled()]
        return (
            results[-1]
            if results
            else TaskResult(
                task_id=task.task_id,
                backend_id="none",
                output="",
                success=False,
                latency_ms=0,
                error="All backends failed.",
            )
        )
