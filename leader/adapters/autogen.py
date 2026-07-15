"""Leader – Microsoft Autogen adapter"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter

class AutogenAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("base_url"))
    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url", "").rstrip("/")
        url = f"{base_url}/chat"
        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}
            if self.config.get("api_key"):
                headers["Authorization"] = f"Bearer {self.config['api_key']}"
            payload = {"message": task.prompt, "agents": self.config.get("agents", ["assistant", "user_proxy"])}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(task_id=task.task_id, backend_id="autogen", output=data.get("response", ""), success=True, latency_ms=latency)
                    else:
                        return TaskResult(task_id=task.task_id, backend_id="autogen", output="", success=False, latency_ms=latency, error=f"HTTP {resp.status}")
        except Exception as exc:
            return TaskResult(task_id=task.task_id, backend_id="autogen", output="", success=False, latency_ms=(time.monotonic() - t0) * 1000, error=str(exc))
