"""Leader – Microsoft Autogen native adapter"""

from __future__ import annotations

import asyncio
import importlib.util
import time

from ..models import Task, TaskResult
from .base import BaseAdapter


class AutogenAdapter(BaseAdapter):
    def is_available(self) -> bool:
        # Require the autogen package to be installed locally
        return importlib.util.find_spec("autogen") is not None

    async def run(self, task: Task) -> TaskResult:
        t0 = time.monotonic()
        try:
            autogen = importlib.import_module("autogen")

            api_key = self.config.get("api_key")
            llm_config = {
                "config_list": [{"model": self.config.get("model", "gpt-4"), "api_key": api_key}]
            }

            def _run_autogen():
                assistant = autogen.AssistantAgent(
                    name="assistant",
                    llm_config=llm_config,
                    system_message="You are a helpful AI assistant.",
                )
                user_proxy = autogen.UserProxyAgent(
                    name="user_proxy",
                    human_input_mode="NEVER",
                    max_consecutive_auto_reply=1,
                    is_termination_msg=lambda x: x.get("content", "")
                    .rstrip()
                    .endswith("TERMINATE"),
                    code_execution_config=False,
                )
                chat_res = user_proxy.initiate_chat(
                    assistant,
                    message=task.prompt,
                    summary_method="reflection_with_llm",
                )
                return chat_res.summary

            output = await asyncio.to_thread(_run_autogen)
            latency = (time.monotonic() - t0) * 1000

            return TaskResult(
                task_id=task.task_id,
                backend_id="autogen",
                output=str(output),
                success=True,
                latency_ms=latency,
            )
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="autogen",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )
