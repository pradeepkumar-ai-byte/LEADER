"""
Leader – DirectLLM adapter

This is Leader's ONLY built-in working backend.
It requires no external agent software — just an API key for any LLM provider.
It's the fallback that makes Leader useful even when the user has connected
zero agent backends.

Supported providers (user picks one in config):
  anthropic  — Claude (claude-sonnet-4-6 default)
  openai     — GPT  (gpt-4o default)
  openrouter — any model via openrouter.ai

Config keys:
  provider  : "anthropic" | "openai" | "openrouter"
  api_key   : your key
  model     : optional override, e.g. "claude-opus-4-6"
"""

from __future__ import annotations

import time

import aiohttp

from ..types import Task, TaskResult
from .base import BaseAdapter

PROVIDERS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "default_model": "claude-sonnet-4-6",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "anthropic/claude-sonnet-4-6",
    },
}


class DirectLLMAdapter(BaseAdapter):

    def is_available(self) -> bool:
        return bool(self.config.get("api_key") and self.config.get("provider") in PROVIDERS)

    async def run(self, task: Task) -> TaskResult:
        provider = self.config["provider"]
        api_key = self.config["api_key"]
        pconf = PROVIDERS[provider]
        model = self.config.get("model", pconf["default_model"])
        url = pconf["url"]

        t0 = time.monotonic()
        try:
            if provider == "anthropic":
                return await self._call_anthropic(task, url, api_key, model, t0)
            else:
                return await self._call_openai_compat(task, url, api_key, model, t0, provider)
        except Exception as exc:
            return TaskResult(
                task_id=task.task_id,
                backend_id="direct_llm",
                output="",
                success=False,
                latency_ms=(time.monotonic() - t0) * 1000,
                error=str(exc),
            )

    async def _call_anthropic(self, task, url, api_key, model, t0):
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": task.prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                latency = (time.monotonic() - t0) * 1000
                data = await resp.json()
                if resp.status == 200:
                    output = data["content"][0]["text"]
                    input_tokens = data.get("usage", {}).get("input_tokens", 0)
                    output_tokens = data.get("usage", {}).get("output_tokens", 0)
                    # rough cost estimate (claude-sonnet-4-6 pricing)
                    cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id="direct_llm",
                        output=output,
                        success=True,
                        latency_ms=latency,
                        cost_estimate=cost,
                    )
                else:
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id="direct_llm",
                        output="",
                        success=False,
                        latency_ms=latency,
                        error=f"HTTP {resp.status}: {data}",
                    )

    async def _call_openai_compat(self, task, url, api_key, model, t0, provider):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/leader-agent/leader"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": task.prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                latency = (time.monotonic() - t0) * 1000
                data = await resp.json()
                if resp.status == 200:
                    output = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    cost = (
                        usage.get("prompt_tokens", 0) * 2.5 + usage.get("completion_tokens", 0) * 10
                    ) / 1_000_000
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id="direct_llm",
                        output=output,
                        success=True,
                        latency_ms=latency,
                        cost_estimate=cost,
                    )
                else:
                    return TaskResult(
                        task_id=task.task_id,
                        backend_id="direct_llm",
                        output="",
                        success=False,
                        latency_ms=latency,
                        error=f"HTTP {resp.status}: {data}",
                    )
