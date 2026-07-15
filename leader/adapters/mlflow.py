"""Leader – MLflow adapter"""
from __future__ import annotations
import time
import aiohttp
from ..models import Task, TaskResult
from .base import BaseAdapter

class MLflowAdapter(BaseAdapter):
    def is_available(self) -> bool:
        return bool(self.config.get("tracking_uri") and self.config.get("model_uri"))
    async def run(self, task: Task) -> TaskResult:
        tracking_uri = self.config.get("tracking_uri", "").rstrip("/")
        url = f"{tracking_uri}/api/2.0/mlflow/models/predict"
        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}
            model_uri = self.config.get("model_uri")
            payload = {"model_uri": model_uri, "dataframe_split": {"data": [[task.prompt]]}}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        return TaskResult(task_id=task.task_id, backend_id="mlflow", output=str(data.get("predictions", "")), success=True, latency_ms=latency)
                    else:
                        return TaskResult(task_id=task.task_id, backend_id="mlflow", output="", success=False, latency_ms=latency, error=f"HTTP {resp.status}")
        except Exception as exc:
            return TaskResult(task_id=task.task_id, backend_id="mlflow", output="", success=False, latency_ms=(time.monotonic() - t0) * 1000, error=str(exc))
