"""Leader – Make.com (formerly Integromat) adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class MakeAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("webhook_url"))

    async def run(self, task: Task) -> TaskResult:
        webhook_url = self.config.get("webhook_url", "")
        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"input": task.prompt, "task_id": task.task_id}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status in (200, 201, 202):
                        data = await resp.json()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="make",
                            output=str(data.get("output", data)),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="make",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="make",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
