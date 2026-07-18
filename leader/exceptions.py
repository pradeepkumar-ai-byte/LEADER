"""
Leader – exception hierarchy

Defines structured exceptions for the Leader routing engine.
All Leader-specific exceptions inherit from LeaderError.
"""

from __future__ import annotations


class LeaderError(Exception):
    """Base exception for all Leader errors."""

    pass


class ConfigurationError(LeaderError):
    """Raised when Leader configuration is invalid or missing."""

    pass


class BackendNotFoundError(LeaderError):
    """Raised when a requested backend ID does not exist in the registry."""

    def __init__(self, backend_id: str):
        self.backend_id = backend_id
        super().__init__(f"Backend '{backend_id}' not found in registry.")


class BackendUnavailableError(LeaderError):
    """Raised when a backend exists but is not connected or misconfigured."""

    def __init__(self, backend_id: str, reason: str = ""):
        self.backend_id = backend_id
        self.reason = reason
        msg = f"Backend '{backend_id}' is unavailable"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class NoBackendsConnectedError(LeaderError):
    """Raised when no backends are connected and a task cannot be routed."""

    def __init__(self):
        super().__init__(
            "No backends connected. Run `leader init` to create a config, "
            "then add at least one backend."
        )


class AdapterLoadError(LeaderError):
    """Raised when an adapter class cannot be dynamically loaded."""

    def __init__(self, adapter_class: str, reason: str = ""):
        self.adapter_class = adapter_class
        msg = f"Failed to load adapter '{adapter_class}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class TaskExecutionError(LeaderError):
    """Raised when all backends in the fallback chain fail to execute a task."""

    def __init__(self, task_id: str, errors: list[str] | None = None):
        self.task_id = task_id
        self.errors = errors or []
        msg = f"All backends failed for task '{task_id}'"
        if self.errors:
            msg += f". Errors: {'; '.join(self.errors)}"
        super().__init__(msg)


class ClassificationError(LeaderError):
    """Raised when the router cannot classify a task."""

    pass


class SnapshotError(LeaderError):
    """Raised when snapshot creation or restoration fails."""

    pass
