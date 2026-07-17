"""
Leader – REST API Server

A lightweight HTTP server that exposes Leader's routing engine over REST.
Allows any tool, platform, or language to embed Leader via HTTP calls.

Usage:
    leader serve                  # start on default port 8585
    leader serve --port 9000      # custom port
    leader serve --host 0.0.0.0   # bind to all interfaces

Endpoints:
    POST /api/run          — Route and execute a task
    GET  /api/backends     — List all backends and status
    GET  /api/stats        — Routing performance stats
    POST /api/feedback     — Submit user feedback
    GET  /api/health       — Health check
    POST /api/route        — Route only (no execution)
"""

from __future__ import annotations

import json
import time

from aiohttp import web

from .sdk import Leader

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8585


def _json_response(data: dict, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, default=str),
        content_type="application/json",
        status=status,
    )


def create_app(config_path: str | None = None) -> web.Application:
    """Create and return the Leader API application."""
    app = web.Application()
    app["leader"] = Leader(config_path=config_path)

    # ── CORS middleware ──────────────────────────────────────────────────
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            try:
                response = await handler(request)
            except web.HTTPException as ex:
                response = _json_response({"error": ex.reason}, status=ex.status)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    app.middlewares.append(cors_middleware)

    # ── routes ───────────────────────────────────────────────────────────
    app.router.add_post("/api/run", handle_run)
    app.router.add_post("/api/route", handle_route)
    app.router.add_get("/api/backends", handle_backends)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_post("/api/feedback", handle_feedback)
    app.router.add_get("/api/health", handle_health)

    # Root — welcome page
    app.router.add_get("/", handle_root)

    return app


# ── handlers ─────────────────────────────────────────────────────────────────


async def handle_root(request: web.Request) -> web.Response:
    leader: Leader = request.app["leader"]
    return _json_response(
        {
            "name": "Leader API",
            "version": "0.1.0",
            "description": "Credential-aware multi-backend AI agent router",
            "connected_backends": leader.connected_count,
            "ready": leader.is_ready,
            "endpoints": {
                "POST /api/run": "Route and execute a task",
                "POST /api/route": "Route only (no execution)",
                "GET /api/backends": "List all backends and status",
                "GET /api/stats": "Routing performance stats",
                "POST /api/feedback": "Submit user feedback",
                "GET /api/health": "Health check",
            },
        }
    )


async def handle_run(request: web.Request) -> web.Response:
    """
    POST /api/run
    Body: { "prompt": "...", "category": "coding" (optional), "parallel": false (optional) }
    """
    leader: Leader = request.app["leader"]

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    prompt = body.get("prompt")
    if not prompt:
        return _json_response({"error": "'prompt' is required"}, status=400)

    category = body.get("category")
    parallel = body.get("parallel", False)
    timeout = body.get("timeout")

    result = await leader.run(
        prompt=prompt,
        category=category,
        parallel=parallel,
        timeout=timeout,
    )

    return _json_response(
        {
            "task_id": result.task_id,
            "backend_id": result.backend_id,
            "output": result.output,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "cost_estimate": result.cost_estimate,
            "error": result.error or None,
        }
    )


async def handle_route(request: web.Request) -> web.Response:
    """
    POST /api/route
    Route only — returns which backend would be selected, without executing.
    Body: { "prompt": "...", "category": "coding" (optional) }
    """
    leader: Leader = request.app["leader"]

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    prompt = body.get("prompt")
    if not prompt:
        return _json_response({"error": "'prompt' is required"}, status=400)

    decision = leader.route(prompt=prompt, category=body.get("category"))

    return _json_response(
        {
            "primary": decision.primary,
            "fallback_chain": decision.fallback_chain,
            "rationale": decision.rationale,
            "recommendation": decision.recommendation,
        }
    )


async def handle_backends(request: web.Request) -> web.Response:
    """GET /api/backends — list all backends and their connection status."""
    leader: Leader = request.app["leader"]
    return _json_response(leader.backends())


async def handle_stats(request: web.Request) -> web.Response:
    """GET /api/stats — routing performance statistics."""
    leader: Leader = request.app["leader"]
    return _json_response(leader.stats())


async def handle_feedback(request: web.Request) -> web.Response:
    """
    POST /api/feedback
    Body: { "task_id": "...", "rating": 1-5, "comment": "" (optional) }
    """
    leader: Leader = request.app["leader"]

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    task_id = body.get("task_id")
    rating = body.get("rating")

    if not task_id or rating is None:
        return _json_response({"error": "'task_id' and 'rating' are required"}, status=400)

    try:
        leader.feedback(task_id, int(rating), body.get("comment", ""))
    except ValueError as e:
        return _json_response({"error": str(e)}, status=400)

    return _json_response({"status": "ok", "task_id": task_id, "rating": rating})


async def handle_health(request: web.Request) -> web.Response:
    """GET /api/health — health check."""
    leader: Leader = request.app["leader"]
    return _json_response(
        {
            "status": "healthy",
            "ready": leader.is_ready,
            "connected_backends": leader.connected_count,
            "timestamp": time.time(),
        }
    )


# ── entry point ──────────────────────────────────────────────────────────────


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, config_path: str | None = None):
    """Start the Leader API server."""
    app = create_app(config_path=config_path)

    print(f"\n  ⚡ Leader API server starting on http://{host}:{port}")
    print("  📡 Endpoints:")
    print(f"     POST http://{host}:{port}/api/run")
    print(f"     POST http://{host}:{port}/api/route")
    print(f"     GET  http://{host}:{port}/api/backends")
    print(f"     GET  http://{host}:{port}/api/stats")
    print(f"     POST http://{host}:{port}/api/feedback")
    print(f"     GET  http://{host}:{port}/api/health")
    print()

    web.run_app(app, host=host, port=port, print=None)
