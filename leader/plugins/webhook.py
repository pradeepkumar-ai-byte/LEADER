"""
Leader – Webhook Plugin

A generic plugin that lets ANY platform embed Leader via webhooks.
Works with any tool that can send HTTP POST requests (n8n, Make, Zapier,
custom apps, Slack bots, Discord bots, Telegram bots, etc.)

Usage:
    from aiohttp import web
    from leader.plugins import WebhookPlugin

    app = web.Application()
    plugin = WebhookPlugin()
    await plugin.install(app)

    # Now your app has:
    #   POST /webhook/leader          — run a task
    #   POST /webhook/leader/callback — run a task with callback URL

    web.run_app(app, port=8585)

Webhook payload format:
    {
        "prompt": "summarize this document",
        "category": "research",        // optional
        "parallel": false,             // optional
        "callback_url": "https://..."  // optional — Leader POSTs result here
    }
"""

from __future__ import annotations

from typing import Any

import aiohttp
from aiohttp import web

from ..sdk import Leader
from .base import BasePlugin


class WebhookPlugin(BasePlugin):
    """
    Generic webhook plugin — lets any external platform call Leader
    via a simple HTTP POST. Optionally sends results back to a
    callback URL (fire-and-forget pattern for async workflows).
    """

    def __init__(
        self,
        leader: Leader | None = None,
        config: dict | None = None,
        prefix: str = "/webhook/leader",
    ):
        super().__init__(leader=leader, config=config)
        self.prefix = prefix.rstrip("/")

    @property
    def name(self) -> str:
        return "Leader Webhook"

    async def install(self, host: Any) -> None:
        """
        Install webhook routes on an aiohttp application.

        Args:
            host: An aiohttp web.Application.
        """
        if not isinstance(host, web.Application):
            raise TypeError(
                f"WebhookPlugin expects an aiohttp web.Application, got {type(host).__name__}"
            )

        host["leader"] = self.leader

        host.router.add_post(self.prefix, self._handle_webhook)
        host.router.add_post(f"{self.prefix}/callback", self._handle_webhook_callback)
        host.router.add_get(f"{self.prefix}/health", self._handle_health)

        self._installed = True

    async def on_task(self, prompt: str, context: dict | None = None) -> dict:
        """Route a task through Leader."""
        context = context or {}
        result = await self.route_task(
            prompt=prompt,
            category=context.get("category"),
            parallel=context.get("parallel", False),
        )
        return self.result_to_dict(result)

    # ── HTTP handlers ────────────────────────────────────────────────────────

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """
        POST /webhook/leader — synchronous webhook.
        Waits for the result and returns it in the response.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        prompt = body.get("prompt") or body.get("text") or body.get("message")
        if not prompt:
            return web.json_response(
                {"error": "Provide 'prompt', 'text', or 'message'"}, status=400
            )

        result_dict = await self.on_task(prompt, context=body)
        return web.json_response(result_dict)

    async def _handle_webhook_callback(self, request: web.Request) -> web.Response:
        """
        POST /webhook/leader/callback — async webhook with callback.
        Immediately returns 202 Accepted, then POSTs the result to the
        callback_url when done. Useful for n8n, Make, Zapier, etc.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        prompt = body.get("prompt") or body.get("text") or body.get("message")
        callback_url = body.get("callback_url")

        if not prompt:
            return web.json_response(
                {"error": "Provide 'prompt', 'text', or 'message'"}, status=400
            )
        if not callback_url:
            return web.json_response(
                {"error": "'callback_url' is required for async mode"}, status=400
            )

        # Fire-and-forget: start the task in the background
        import asyncio

        asyncio.create_task(self._run_and_callback(prompt, body, callback_url))

        return web.json_response(
            {
                "status": "accepted",
                "message": "Task started, result will be POSTed to callback_url",
            },
            status=202,
        )

    async def _run_and_callback(self, prompt: str, context: dict, callback_url: str):
        """Execute the task and POST the result to the callback URL."""
        try:
            result_dict = await self.on_task(prompt, context=context)
            async with aiohttp.ClientSession() as session:
                await session.post(
                    callback_url,
                    json=result_dict,
                    timeout=aiohttp.ClientTimeout(total=30),
                )
        except Exception:
            # Best effort — don't crash the server if callback fails
            pass

    async def _handle_health(self, request: web.Request) -> web.Response:
        """GET /webhook/leader/health"""
        return web.json_response(
            {
                "plugin": "Leader Webhook",
                "status": "healthy",
                "connected_backends": self.leader.connected_count,
                "ready": self.leader.is_ready,
            }
        )
