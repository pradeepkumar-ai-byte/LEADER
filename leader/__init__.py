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

__version__ = "0.1.0"
__author__ = "Krish"

from .executor import Executor
from .logger import TaskLogger
from .models import RouteDecision, Task, TaskCategory, TaskResult
from .registry import BackendSpec, Registry
from .router import Router
from .sdk import Leader

__all__ = [
    "Leader",
    "Task",
    "TaskCategory",
    "TaskResult",
    "RouteDecision",
    "Registry",
    "BackendSpec",
    "Router",
    "Executor",
    "TaskLogger",
]
