"""
Leader – router

Classifies an incoming task and dispatches it to the best connected backend.
Uses evolved scoring (60% history, 40% static) once task data accumulates.
"""

from __future__ import annotations

from .logger import TaskLogger
from .models import RouteDecision, Task, TaskCategory
from .registry import BackendSpec, Registry

# ── improved keyword classifier ──────────────────────────────────────────────

_HINTS: list[tuple[TaskCategory, list[str]]] = [
    (
        TaskCategory.MESSAGING,
        [
            "send",
            "message",
            "whatsapp",
            "telegram",
            "slack",
            "discord",
            "email",
            "notify",
            "notification",
            "dm",
            "text",
            "contact",
        ],
    ),
    (
        TaskCategory.CODING,
        [
            "code",
            "function",
            "bug",
            "debug",
            "script",
            "implement",
            "refactor",
            "test",
            "class",
            "module",
            "error",
            "exception",
            "syntax",
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
        ],
    ),
    (
        TaskCategory.RESEARCH,
        [
            "search",
            "find",
            "look up",
            "summarise",
            "summarize",
            "research",
            "what is",
            "who is",
            "explain",
            "latest",
            "news",
            "current",
            "recent",
            "when did",
            "where is",
            "how does",
        ],
    ),
    (
        TaskCategory.CREATIVE,
        [
            "write",
            "draft",
            "story",
            "blog",
            "poem",
            "idea",
            "brainstorm",
            "creative",
            "article",
            "post",
            "essay",
            "caption",
            "headline",
        ],
    ),
    (
        TaskCategory.DATA,
        [
            "chart",
            "graph",
            "analyse",
            "analyze",
            "data",
            "csv",
            "spreadsheet",
            "table",
            "statistics",
            "plot",
            "visualise",
            "visualize",
            "dataset",
            "numbers",
        ],
    ),
    (
        TaskCategory.AUTOMATION,
        [
            "every",
            "schedule",
            "repeat",
            "automate",
            "pipeline",
            "whenever",
            "trigger",
            "cron",
            "daily",
            "weekly",
            "hourly",
            "run when",
            "on event",
        ],
    ),
    (
        TaskCategory.MULTIAGENT,
        [
            "team",
            "agents",
            "coordinate",
            "parallel",
            "assign",
            "split",
            "crew",
            "multiple agents",
            "delegate",
        ],
    ),
]


def classify(prompt: str) -> TaskCategory:
    """Keyword scorer with tie-breaking. More keywords per category = more accurate."""
    low = prompt.lower()
    scores: dict[TaskCategory, int] = {cat: 0 for cat, _ in _HINTS}
    for category, keywords in _HINTS:
        for kw in keywords:
            if kw in low:
                scores[category] += 1
    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat if scores[best_cat] > 0 else TaskCategory.GENERAL


class Router:
    def __init__(self, registry: Registry, logger: TaskLogger):
        self.registry = registry
        self.logger = logger

    def _evolved_score(self, spec: BackendSpec, category: TaskCategory) -> float:
        win_rates = self.logger.win_rates()
        latencies = self.logger.avg_latency()

        if category in spec.strengths:
            static = 2.0
        elif category in spec.weaknesses:
            static = 0.0
        else:
            static = 1.0

        history_rate = win_rates.get(spec.id, {}).get(category.value, None)
        # penalise slow backends slightly (cap at 0.5 penalty)
        latency_penalty = min(latencies.get(spec.id, 0) / 10000, 0.5)

        if history_rate is None:
            return static - latency_penalty

        # 60% lived experience, 40% static knowledge
        return (0.4 * static) + (0.6 * history_rate * 2) - latency_penalty

    def decide(self, task: Task) -> RouteDecision:
        if task.category is None:
            task.category = classify(task.prompt)

        connected = self.registry.connected()

        if not connected:
            return RouteDecision(
                primary="none",
                fallback_chain=[],
                rationale="No backends connected.",
                recommendation=(
                    "Run `leader init` to create a config, then add at least one backend.\n"
                    "Fastest start: add a direct_llm backend with just an API key — "
                    "no extra software needed."
                ),
            )

        ranked = sorted(
            connected,
            key=lambda s: self._evolved_score(s, task.category),
            reverse=True,
        )

        primary = ranked[0]
        fallbacks = [s.id for s in ranked[1:]]

        missing = self.registry.missing_specialists(task.category)
        rec = None
        if missing:
            names = ", ".join(m.display_name for m in missing[:3])
            rec = (
                f"For {task.category.value} tasks, connecting {names} "
                f"would likely improve results. Run `leader backends` for details."
            )

        return RouteDecision(
            primary=primary.id,
            fallback_chain=fallbacks,
            rationale=(
                f"Category: {task.category.value}. "
                f"{primary.display_name} scored highest among your connected backends."
            ),
            recommendation=rec,
        )
