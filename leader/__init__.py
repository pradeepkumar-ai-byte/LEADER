"""
Leader – A credential-aware router that evolves which specialist to dispatch each task to.

Sits above OpenClaw, Hermes, ZeroClaw, or any REST-accessible agent backend.
Routes every task to whichever backend is best suited based on capability registry
and your actual task history (learning over time).

Quick start (3 lines):

    from leader import Leader
    leader = Leader()
    result = await leader.run("your task here")
"""

__version__ = "0.2.0"
__author__ = "Krish"

from .exceptions import (
    AdapterLoadError,
    BackendNotFoundError,
    BackendUnavailableError,
    ClassificationError,
    ConfigurationError,
    LeaderError,
    NoBackendsConnectedError,
    SnapshotError,
    TaskExecutionError,
)
from .executor import Executor
from .logger import TaskLogger
from .models import RouteDecision, Task, TaskCategory, TaskResult
from .registry import BackendSpec, Registry
from .router import Router
from .sdk import Leader

__all__ = [
    # SDK entry point
    "Leader",
    # Core types
    "Task",
    "TaskCategory",
    "TaskResult",
    "RouteDecision",
    # Infrastructure
    "Registry",
    "BackendSpec",
    "Router",
    "Executor",
    "TaskLogger",
    # Exceptions
    "LeaderError",
    "ConfigurationError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "NoBackendsConnectedError",
    "AdapterLoadError",
    "TaskExecutionError",
    "ClassificationError",
    "SnapshotError",
]
