"""
Leader – base adapter interface for all backends
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import Task, TaskResult


class BaseAdapter(ABC):
    """
    Abstract base adapter that all backends must implement.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.id = self.config.get("id", "unknown")

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this backend is properly configured and available.
        Return False if required credentials/config are missing.
        """
        pass

    @abstractmethod
    async def run(self, task: Task) -> TaskResult:
        """
        Execute a task on this backend.
        Return a TaskResult with success/error info.
        """
        pass

    def health_check(self) -> bool:
        """
        Optional: quick health check to see if backend is responding.
        Default implementation returns is_available() result.
        """
        return self.is_available()
