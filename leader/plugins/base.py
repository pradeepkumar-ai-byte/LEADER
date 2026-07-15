"""
Leader – Base Plugin Interface

All Leader plugins must inherit from BasePlugin and implement the
required methods. A plugin bridges a host application (OpenClaw, VS Code,
a custom web app, etc.) to Leader's routing engine.

Lifecycle:
    1. Plugin is instantiated with Leader SDK
    2. Plugin is installed into the host application via install()
    3. Host app receives a task → calls plugin.on_task()
    4. Plugin routes through Leader and returns the result
    5. Host app displays the result in its own UI
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from ..sdk import Leader
from ..models import TaskResult


class BasePlugin(ABC):
    """
    Abstract base class for all Leader plugins.

    A plugin is a bridge between a host application and Leader's routing engine.
    The host application receives tasks from users; the plugin routes those tasks
    through Leader to the best backend, then returns results to the host.

    Subclasses must implement:
        - install()    — integrate with the host application
        - on_task()    — handle incoming tasks from the host
    """

    def __init__(self, leader: Leader | None = None, config: dict | None = None):
        self.leader = leader or Leader()
        self.config = config or {}
        self._installed = False

    @property
    def name(self) -> str:
        """Human-readable plugin name."""
        return self.__class__.__name__

    @property
    def is_installed(self) -> bool:
        return self._installed

    # ── required methods ─────────────────────────────────────────────────────

    @abstractmethod
    async def install(self, host: Any) -> None:
        """
        Install this plugin into the host application.

        This is where you register routes, hooks, event listeners,
        skills, or whatever the host platform supports.

        Args:
            host: The host application instance (e.g., an aiohttp app,
                  an OpenClaw skill registry, etc.)
        """
        pass

    @abstractmethod
    async def on_task(self, prompt: str, context: dict | None = None) -> dict:
        """
        Handle an incoming task from the host application.

        This method is called when the host app receives a task that
        should be routed through Leader.

        Args:
            prompt:  The task description.
            context: Optional metadata from the host (user info, session, etc.)

        Returns:
            A dict with at least: output, success, backend_id
        """
        pass

    # ── convenience methods ──────────────────────────────────────────────────

    async def route_task(
        self,
        prompt: str,
        category: str | None = None,
        parallel: bool = False,
    ) -> TaskResult:
        """
        Route a task through Leader. Convenience wrapper around the SDK.
        """
        return await self.leader.run(
            prompt=prompt,
            category=category,
            parallel=parallel,
        )

    def result_to_dict(self, result: TaskResult) -> dict:
        """Convert a TaskResult to a dict suitable for returning to the host."""
        return {
            "task_id": result.task_id,
            "backend_id": result.backend_id,
            "output": result.output,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "cost_estimate": result.cost_estimate,
            "error": result.error or None,
            "routed_by": "leader",
        }

    async def uninstall(self) -> None:
        """Optional: clean up when the plugin is removed from the host."""
        self._installed = False
