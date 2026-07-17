"""Leader – AWS Bedrock adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class BedrockAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("region") and self.config.get("model_id"))

    async def run(self, task: Task) -> TaskResult:
        # Note: Bedrock uses AWS SDK, this is a REST wrapper simulation
        region = self.config.get("region", "us-east-1")
        model_id = self.config.get("model_id", "anthropic.claude-v2")
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"prompt": task.prompt, "max_tokens_to_sample": 1000}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="bedrock",
                            output=data.get("completion", ""),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="bedrock",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="bedrock",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
