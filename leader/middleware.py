"""
Leader – Middleware

Drop-in middleware and route helpers for embedding Leader into an existing
aiohttp web application. Instead of running Leader as a separate server,
mount it directly inside your app.

Usage:
    from aiohttp import web
    from leader.middleware import mount_leader

    app = web.Application()

    # Mount Leader's API under /leader/
    mount_leader(app, prefix="/leader")

    # Now your existing app has these routes:
    #   POST /leader/api/run
    #   GET  /leader/api/backends
    #   GET  /leader/api/health
    #   etc.

    web.run_app(app)
"""
from __future__ import annotations
from aiohttp import web
from .sdk import Leader
from . import server as leader_server


def mount_leader(
    app: web.Application,
    prefix: str = "/leader",
    config_path: str | None = None,
) -> Leader:
    """
    Mount Leader's API routes onto an existing aiohttp application.

    Args:
        app:         Your aiohttp application instance.
        prefix:      URL prefix for Leader's routes (default: "/leader").
        config_path: Optional path to Leader config file.

    Returns:
        The Leader SDK instance (for programmatic access alongside the API).

    Example:
        app = web.Application()
        leader = mount_leader(app, prefix="/ai")
        # Now POST /ai/api/run routes through Leader
    """
    leader = Leader(config_path=config_path)
    app["leader"] = leader

    prefix = prefix.rstrip("/")

    app.router.add_post(f"{prefix}/api/run", leader_server.handle_run)
    app.router.add_post(f"{prefix}/api/route", leader_server.handle_route)
    app.router.add_get(f"{prefix}/api/backends", leader_server.handle_backends)
    app.router.add_get(f"{prefix}/api/stats", leader_server.handle_stats)
    app.router.add_post(f"{prefix}/api/feedback", leader_server.handle_feedback)
    app.router.add_get(f"{prefix}/api/health", leader_server.handle_health)

    return leader


def leader_middleware(config_path: str | None = None):
    """
    Create an aiohttp middleware that injects a Leader instance into every request.

    Usage:
        from leader.middleware import leader_middleware

        app = web.Application(middlewares=[leader_middleware()])

        # In your handlers:
        async def my_handler(request):
            leader = request.app["leader"]
            result = await leader.run("do something")
    """
    leader = Leader(config_path=config_path)

    @web.middleware
    async def middleware(request: web.Request, handler):
        if "leader" not in request.app:
            request.app["leader"] = leader
        return await handler(request)

    return middleware
