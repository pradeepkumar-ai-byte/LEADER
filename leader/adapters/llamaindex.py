"""Leader – LLamaIndex adapter"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter

class LlamaIndexAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("base_url") and self.config.get("api_key"))
    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url", "").rstrip("/")
        url = f"{base_url}/api/query"
        t0 = time.monotonic()
        try:
            headers = {"Authorization": f"Bearer {self.config['api_key']}", "Content-Type": "application/json"}
            payload = {"query": task.prompt, "similarity_top_k": self.config.get("top_k", 3)}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(task_id=task.task_id, backend_id="llamaindex", output=data.get("response", ""), success=True, latency_ms=latency)
                    else:
                        return TaskResult(task_id=task.task_id, backend_id="llamaindex", output="", success=False, latency_ms=latency, error=f"HTTP {resp.status}")
        except Exception as exc:
            return TaskResult(task_id=task.task_id, backend_id="llamaindex", output="", success=False, latency_ms=(time.monotonic() - t0) * 1000, error=str(exc))
