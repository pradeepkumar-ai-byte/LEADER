"""
Leader – ZeroClaw adapter
"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter


class ZeroClawAdapter(BaseAdapter):
    """Adapter for ZeroClaw agent backend."""

    def is_available(self) -> bool:
        return bool(self.config.get("base_url") or self.config.get("binary"))

    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url")
        if not base_url:
            # Could implement local binary execution here
            return TaskResult(
                task_id=task.task_id,
                backend_id="zeroclaw",
                output="",
                success=False,
                latency_ms=0,
                error="ZeroClaw binary execution not yet implemented",
            )

        base_url = base_url.rstrip("/")
        endpoint = "/run"
        url = f"{base_url}{endpoint}"

        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}
            if self.config.get("api_key"):
                headers["Authorization"] = f"Bearer {self.config['api_key']}"

            payload = {"prompt": task.prompt}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload,
                                      timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        output = data.get("result", data.get("output", ""))
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="zeroclaw",
                            output=output,
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        error_text = await resp.text()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="zeroclaw",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}: {error_text}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="zeroclaw",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
