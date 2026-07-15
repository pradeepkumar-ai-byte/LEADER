"""
Leader – OpenClaw native adapter
"""
from __future__ import annotations
import time
import asyncio
import shutil
from ..models import Task, TaskResult
from .base import BaseAdapter

class OpenClawAdapter(BaseAdapter):
    """Adapter for OpenClaw native backend."""

    def is_available(self) -> bool:
        # Check if openclaw binary exists in PATH
        return shutil.which("openclaw") is not None

    async def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        try:
            # Execute OpenClaw natively via subprocess
            proc = await asyncio.create_subprocess_exec(
                "openclaw", "run", "--prompt", task.prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise

            latency = (time.monotonic() - t0) * 1000
            
            if proc.returncode == 0:
                output = stdout.decode("utf-8").strip()
                return TaskResult(
                    task_id=task.task_id,
                    backend_id="openclaw",
                    output=output,
                    success=True,
                    latency_ms=latency,
                )
            else:
                error_text = stderr.decode("utf-8").strip()
                return TaskResult(
                    task_id=task.task_id,
                    backend_id="openclaw",
                    output="",
                    success=False,
                    latency_ms=latency,
                    error=f"Exit code {proc.returncode}: {error_text}",
                )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="openclaw",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
