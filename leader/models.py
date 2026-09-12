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


# ── Multi-Agent Chain & Drift Diagnostics Types ──────────────────────────────


class ChainAction(str, Enum):
    """Action recommendation for an active multi-agent step."""

    PROCEED = "proceed"
    WARN = "warn"
    TERMINATE_LOOP = "terminate_loop"
    TERMINATE_DRIFT = "terminate_drift"


@dataclass
class LoopDetectionResult:
    """Feedback loop detection analysis for an inter-agent step."""

    is_loop: bool = False
    loop_type: str = (
        "none"  # "none", "ping_pong", "n_cycle", "depth_exhaustion", "repetitive_payload"
    )
    cycle_nodes: list[str] = field(default_factory=list)
    repetition_count: int = 0
    description: str = ""


@dataclass
class DriftAssessment:
    """Semantic drift measurement comparing step to root alignment prompt."""

    drift_score: float = 0.0  # 0.0 (identical) to 1.0 (completely orthogonal/drifted)
    similarity: float = 1.0  # 0.0 to 1.0 cosine similarity
    is_drifting: bool = False  # True if drift exceeds warning threshold
    is_critical_drift: bool = False  # True if drift exceeds critical threshold
    root_alignment_ratio: float = 1.0
    description: str = ""


@dataclass
class ChainStep:
    """A single execution hop in a multi-agent chain."""

    prompt: str
    source_backend: str = "user"
    target_backend: str | None = None
    step_index: int = 0
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_step_id: str | None = None
    chain_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ChainStepVerdict:
    """Safety and integrity verdict for a multi-agent chain step."""

    action: ChainAction
    step_id: str
    chain_id: str
    step_index: int
    loop_result: LoopDetectionResult
    drift_result: DriftAssessment
    summary: str = ""
    latency_ms: float = 0.0


@dataclass
class ChainSession:
    """Summary of an end-to-end multi-agent execution session."""

    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    root_prompt: str = ""
    total_steps: int = 0
    max_drift: float = 0.0
    status: str = "completed"  # "completed", "terminated_loop", "terminated_drift"
    step_verdicts: list[ChainStepVerdict] = field(default_factory=list)
    results: list[TaskResult] = field(default_factory=list)
