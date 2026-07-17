"""Leader – Stability AI adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class StabilityAIAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))

    async def run(self, task: Task) -> TaskResult:
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
        t0 = time.monotonic()
        try:
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "text_prompts": [{"text": task.prompt, "weight": 1.0}],
                "cfg_scale": self.config.get("cfg_scale", 7.0),
                "steps": self.config.get("steps", 30),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("artifacts", [])
                        image_base64 = results[0].get("base64", "") if results else ""
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="stabilityai",
                            output=f"Image generated (base64: {image_base64[:50]}...)",
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="stabilityai",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="stabilityai",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
