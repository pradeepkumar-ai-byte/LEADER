"""
Leader – OpenClaw Plugin

Embeds Leader inside an OpenClaw instance. When installed, Leader becomes
a "skill" inside OpenClaw's skill system. Any task routed to OpenClaw can
be intercepted by Leader and re-routed to a better backend if one exists.

Installation (inside an OpenClaw deployment):

    from leader.plugins import OpenClawPlugin

    plugin = OpenClawPlugin()
    await plugin.install(openclaw_app)

    # Now OpenClaw has a "/leader/run" endpoint and a "leader" skill.
    # Tasks can be routed through Leader from within OpenClaw's UI.

The plugin also exposes a simple HTTP endpoint so OpenClaw's
skill system can call Leader via its standard REST skill interface.
"""
from __future__ import annotations
from typing import Any
from aiohttp import web

from .base import BasePlugin
from ..sdk import Leader


class OpenClawPlugin(BasePlugin):
    """
    Plugin that embeds Leader inside an OpenClaw instance.

    OpenClaw users can:
    - Use Leader as a skill from OpenClaw's dashboard
    - Tasks are routed to the best backend automatically
    - Results appear inside OpenClaw's UI — user never leaves

    This plugin registers:
    - A "/leader/run" POST endpoint (skill-compatible)
    - A "/leader/health" GET endpoint
    - A "/leader/backends" GET endpoint
    """

    @property
    def name(self) -> str:
        return "Leader for OpenClaw"

    async def install(self, host: Any) -> None:
        """
        Install Leader as a skill inside an OpenClaw aiohttp application.

        Args:
            host: The OpenClaw aiohttp web.Application instance.
        """
        if not isinstance(host, web.Application):
            raise TypeError(
                f"OpenClawPlugin expects an aiohttp web.Application, got {type(host).__name__}"
            )

        host["leader"] = self.leader

        # Register Leader routes inside OpenClaw's app
        host.router.add_post("/leader/run", self._handle_run)
        host.router.add_get("/leader/health", self._handle_health)
        host.router.add_get("/leader/backends", self._handle_backends)

        # Register as an OpenClaw skill if the skill registry exists
        if "skill_registry" in host:
            host["skill_registry"]["leader"] = {
                "name": "Leader Router",
                "description": "Routes tasks to the best AI backend automatically",
                "endpoint": "/leader/run",
                "method": "POST",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The task to execute"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "messaging", "coding", "research", "creative",
                                "data", "automation", "multiagent", "general",
                            ],
                            "description": "Optional task category",
                        },
                    },
                    "required": ["prompt"],
                },
            }

        self._installed = True

    async def on_task(self, prompt: str, context: dict | None = None) -> dict:
        """Handle a task from OpenClaw's skill system."""
        context = context or {}
        category = context.get("category")
        parallel = context.get("parallel", False)

        result = await self.route_task(prompt, category=category, parallel=parallel)
        return self.result_to_dict(result)

    # ── HTTP handlers ────────────────────────────────────────────────────────

    async def _handle_run(self, request: web.Request) -> web.Response:
        """POST /leader/run — OpenClaw-compatible skill endpoint."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        prompt = body.get("prompt") or body.get("query") or body.get("input")
        if not prompt:
            return web.json_response(
                {"error": "Provide 'prompt', 'query', or 'input'"}, status=400
            )

        result_dict = await self.on_task(prompt, context=body)

        # Format response in OpenClaw's expected format
        return web.json_response({
            "result": result_dict["output"],
            "output": result_dict["output"],
            "success": result_dict["success"],
            "metadata": {
                "routed_by": "leader",
                "backend_used": result_dict["backend_id"],
                "latency_ms": result_dict["latency_ms"],
                "task_id": result_dict["task_id"],
            },
        })

    async def _handle_health(self, request: web.Request) -> web.Response:
        """GET /leader/health"""
        return web.json_response({
            "plugin": "Leader for OpenClaw",
            "status": "healthy",
            "connected_backends": self.leader.connected_count,
            "ready": self.leader.is_ready,
        })

    async def _handle_backends(self, request: web.Request) -> web.Response:
        """GET /leader/backends"""
        return web.json_response(self.leader.backends())
