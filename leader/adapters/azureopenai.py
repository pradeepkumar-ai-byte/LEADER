"""Leader – Azure OpenAI adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class AzureOpenAIAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("endpoint") and self.config.get("api_key"))

    async def run(self, task: Task) -> TaskResult:
        endpoint = self.config.get("endpoint", "").rstrip("/")
        deployment_id = self.config.get("deployment_id", "gpt-35-turbo")
        url = (
            f"{endpoint}/openai/deployments/{deployment_id}/chat/completions?api-version=2023-05-15"
        )
        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json", "api-key": self.config["api_key"]}
            payload = {"messages": [{"role": "user", "content": task.prompt}], "temperature": 0.7}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        msg = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="azureopenai",
                            output=msg,
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="azureopenai",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="azureopenai",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
