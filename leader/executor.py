"""
Leader – executor

Runs tasks with:
- health check before routing
- parallel multi-backend execution (when parallel=True)
- per-task timeout
- automatic fallback chain on failure
"""
from __future__ import annotations
import asyncio
import importlib
import time
from .models import Task, TaskResult, RouteDecision
from .registry import Registry
from .adapters.base import BaseAdapter

DEFAULT_TIMEOUT = 120  # seconds


def _load_adapter(backend_id: str, registry: Registry) -> BaseAdapter | None:
    spec = registry.get(backend_id)
    if spec is None:
        return None
    module_path, class_name = spec.adapter_class.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls(config={**spec.config, "id": backend_id})
    except Exception as e:
        return None


class Executor:
    def __init__(self, registry: Registry, timeout: int = DEFAULT_TIMEOUT):
        self.registry = registry
        self.timeout  = timeout

    async def _run_one(self, backend_id: str, task: Task) -> TaskResult:
        adapter = _load_adapter(backend_id, self.registry)
        if adapter is None or not adapter.is_available():
            return TaskResult(
                task_id=task.task_id, backend_id=backend_id,
                output="", success=False, latency_ms=0,
                error=f"Backend '{backend_id}' not available or misconfigured.",
            )
        
        max_retries = 3
        backoff_factor = 1.0  # start with 1 second sleep
        
        for attempt in range(max_retries):
            t0 = time.monotonic()
            try:
                # Execute the adapter call with a timeout
                return await asyncio.wait_for(adapter.run(task), timeout=self.timeout)
            except (asyncio.TimeoutError, Exception) as exc:
                latency = (time.monotonic() - t0) * 1000
                is_timeout = isinstance(exc, asyncio.TimeoutError)
                err_msg = f"Timed out after {self.timeout}s" if is_timeout else str(exc)
                
                # If we've exhausted our retries, return the failed TaskResult
                if attempt == max_retries - 1:
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id=backend_id,
                        output="",
                        success=False,
                        latency_ms=latency,
                        error=f"All {max_retries} attempts failed. Last error: {err_msg}",
                    )
                
                # Log the warning and sleep before next retry (exponential backoff)
                sleep_time = backoff_factor * (1.5 ** attempt)
                print(f"  [leader] Warning: {backend_id} failed on attempt {attempt + 1}/{max_retries} ({err_msg}). Retrying in {sleep_time:.1f}s...")
                await asyncio.sleep(sleep_time)


    async def run(self, task: Task, decision: RouteDecision,
                  parallel: bool = False) -> TaskResult:
        """
        parallel=False (default): try primary, then fallbacks in order.
        parallel=True:            run primary + all fallbacks simultaneously,
                                  return the first successful result.
        """
        if decision.primary == "none":
            return TaskResult(
                task_id=task.task_id, backend_id="none",
                output="", success=False, latency_ms=0,
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
            task_id=task.task_id, backend_id="none",
            output="", success=False, latency_ms=0,
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
        return results[-1] if results else TaskResult(
            task_id=task.task_id, backend_id="none",
            output="", success=False, latency_ms=0, error="All backends failed."
        )
