"""
Leader – type definitions
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskCategory(str, Enum):
    """Task classification for routing decisions."""

    MESSAGING = "messaging"
    CODING = "coding"
    RESEARCH = "research"
    CREATIVE = "creative"
    DATA = "data"
    AUTOMATION = "automation"
    MULTIAGENT = "multiagent"
    GENERAL = "general"


@dataclass
class Task:
    """A single task to be routed and executed."""

    prompt: str
    category: TaskCategory | None = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    backend_id: str
    output: str
    success: bool
    latency_ms: float
    error: str = ""
    cost_estimate: float = 0.0


@dataclass
class RouteDecision:
    """Router's decision on where to send a task."""

    primary: str
    fallback_chain: list[str] = field(default_factory=list)
    rationale: str = ""
    recommendation: str | None = None
    task_id: str = ""
    category: TaskCategory | None = None
    confidence: float = 0.5
