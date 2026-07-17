"""Leader – LangChain adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class LangChainAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("base_url") or self.config.get("api_key"))

    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url", "").rstrip("/")
        url = f"{base_url}/run" if base_url else "https://api.langchain.com/v1/chains/run"
        t0 = time.monotonic()
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.config.get("api_key", ""),
            }
            payload = {
                "input": task.prompt,
                "agent": self.config.get("agent_type", "conversational"),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="langchain",
                            output=data.get("output", ""),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="langchain",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="langchain",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
