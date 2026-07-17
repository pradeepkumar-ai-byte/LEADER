"""Leader – Google Vertex AI adapter"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class VertexAIAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("project_id") and self.config.get("access_token"))

    async def run(self, task: Task) -> TaskResult:
        project_id = self.config.get("project_id")
        region = self.config.get("region", "us-central1")
        model = self.config.get("model", "text-bison")
        url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/publishers/google/models/{model}:predict"
        t0 = time.monotonic()
        try:
            headers = {
                "Authorization": f"Bearer {self.config['access_token']}",
                "Content-Type": "application/json",
            }
            payload = {"instances": [{"prompt": task.prompt}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        predictions = data.get("predictions", [{}])
                        output = predictions[0].get("content", "") if predictions else ""
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="vertexai",
                            output=output,
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id="vertexai",
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="vertexai",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
