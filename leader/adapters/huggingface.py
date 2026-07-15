"""Leader – Hugging Face Agents adapter"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter

class HuggingFaceAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))
    async def run(self, task: Task) -> TaskResult:
        url = "https://api-inference.huggingface.co/v1/agents"
        t0 = time.monotonic()
        try:
            headers = {"Authorization": f"Bearer {self.config['api_key']}", "Content-Type": "application/json"}
            payload = {"task": task.prompt, "model": self.config.get("model", "gpt2"), "temperature": self.config.get("temperature", 0.7)}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(task_id=task.task_id, backend_id="huggingface", output=str(data.get("generated_text", "")), success=True, latency_ms=latency)
                    else:
                        return TaskResult(task_id=task.task_id, backend_id="huggingface", output="", success=False, latency_ms=latency, error=f"HTTP {resp.status}")
        except Exception as exc:
            return TaskResult(task_id=task.task_id, backend_id="huggingface", output="", success=False, latency_ms=(time.monotonic() - t0) * 1000, error=str(exc))
