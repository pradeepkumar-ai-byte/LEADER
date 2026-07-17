"""
Leader – Generic REST adapter for any backend
"""

from __future__ import annotations

import time

import aiohttp

from ..models import Task, TaskResult
from .base import BaseAdapter


class GenericRestAdapter(BaseAdapter):
    """
    Generic adapter for any REST-accessible backend.
    Configure via YAML:
      base_url: http://localhost:9000
      endpoint: /api/run
      prompt_field: query
      output_field: result
      auth_header: Authorization
      auth_value: Bearer my-token
    """

    def is_available(self) -> bool:
        return bool(self.config.get("base_url"))

    async def run(self, task: Task) -> TaskResult:
        base_url = self.config.get("base_url", "").rstrip("/")
        endpoint = self.config.get("endpoint", "/api/run")
        prompt_field = self.config.get("prompt_field", "prompt")
        output_field = self.config.get("output_field", "output")

        url = f"{base_url}{endpoint}"

        t0 = time.monotonic()
        try:
            headers = {"Content-Type": "application/json"}

            # Add auth if configured
            if self.config.get("auth_header") and self.config.get("auth_value"):
                headers[self.config["auth_header"]] = self.config["auth_value"]

            # Build payload
            payload = {prompt_field: task.prompt}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    latency = (time.monotonic() - t0) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        # Navigate nested dict if output_field contains dots
                        output = data
                        for field in output_field.split("."):
                            if isinstance(output, dict):
                                output = output.get(field, "")
                            else:
                                output = ""
                                break

                        return TaskResult(
                            task_id=task.task_id,
                            backend_id=self.id,
                            output=str(output),
                            success=True,
                            latency_ms=latency,
                        )
                    else:
                        error_text = await resp.text()
                        return TaskResult(
                            task_id=task.task_id,
                            backend_id=self.id,
                            output="",
                            success=False,
                            latency_ms=latency,
                            error=f"HTTP {resp.status}: {error_text}",
                        )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id=self.id,
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
