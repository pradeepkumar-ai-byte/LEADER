"""Leader – Replicate adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class ReplicateAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))

    async def run(self, task: Task) -> TaskResult:
        url = "https://api.replicate.com/v1/predictions"
        t0 = time.monotonic()
        try:
            headers = {
                "Authorization": f"Token {self.config['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "version": self.config.get("model_version", ""),
                "input": {"prompt": task.prompt},
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=600)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status in (200, 201):
                        data = await resp.json()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="replicate",
                            output=str(data.get("output", "")),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="replicate",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="replicate",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
