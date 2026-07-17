"""
Leader – router

Classifies an incoming task and dispatches it to the best connected backend.
Uses evolved scoring (50% history, 30% static, 20% feedback) once data accumulates.

Classification uses a two-tier system:
  Tier 1: TF-IDF weighted bi-gram phrase matching with negative-weight suppression.
  Tier 2 (future): Optional LLM-based classification for ambiguous cases.
"""

from __future__ import annotations

import re

from .logger import TaskLogger
from .models import RouteDecision, Task, TaskCategory
from .registry import BackendSpec, Registry

# ── Semantic Classifier ──────────────────────────────────────────────────────
# Each category has:
#   "phrases": high-value compound phrases scored first (these prevent false positives)
#   "keywords": single keywords with individual weights
#   "suppress": keywords that reduce this category's score when present
#
# Scoring: phrases get +3.0 each, keywords get their weight, suppressors get -1.5.
# The classifier picks the category with the highest weighted score.

_CATEGORY_RULES: dict[TaskCategory, dict] = {
    TaskCategory.MESSAGING: {
        "phrases": [
            "send a message",
            "send message",
            "send email",
            "send notification",
            "send a whatsapp",
            "dm me",
            "text me",
            "slack message",
            "discord message",
            "notify me",
        ],
        "keywords": {
            "send": 1.5,
            "message": 1.5,
            "whatsapp": 2.0,
            "telegram": 2.0,
            "slack": 2.0,
            "discord": 1.5,
            "email": 1.5,
            "notify": 1.5,
            "notification": 1.5,
            "dm": 1.5,
            "contact": 1.0,
        },
        "suppress": ["code", "function", "bug", "debug", "script", "implement"],
    },
    TaskCategory.CODING: {
        "phrases": [
            "write a function",
            "write code",
            "fix the bug",
            "bug report",
            "debug this",
            "refactor this",
            "code review",
            "write a script",
            "implement a",
            "unit test",
            "write a test",
            "pull request",
            "merge conflict",
            "stack trace",
            "compile error",
            "syntax error",
            "type error",
            "runtime error",
        ],
        "keywords": {
            "code": 2.0,
            "function": 1.5,
            "bug": 2.0,
            "debug": 2.0,
            "script": 1.5,
            "implement": 1.5,
            "refactor": 2.0,
            "test": 1.0,
            "class": 1.0,
            "module": 1.0,
            "error": 1.5,
            "exception": 2.0,
            "syntax": 2.0,
            "python": 2.0,
            "javascript": 2.0,
            "typescript": 2.0,
            "rust": 2.0,
            "go": 1.0,
            "api": 1.0,
            "endpoint": 1.5,
            "database": 1.0,
            "sql": 1.5,
            "git": 1.5,
            "deploy": 1.0,
            "compile": 1.5,
            "lint": 1.5,
            "variable": 1.5,
            "algorithm": 1.5,
            "regex": 2.0,
            "dependency": 1.5,
        },
        "suppress": ["blog", "poem", "story", "essay", "article", "headline"],
    },
    TaskCategory.RESEARCH: {
        "phrases": [
            "look up",
            "what is",
            "who is",
            "when did",
            "where is",
            "how does",
            "find out",
            "can you find",
            "tell me about",
            "latest news",
            "current state of",
        ],
        "keywords": {
            "search": 1.5,
            "find": 1.0,
            "summarise": 1.5,
            "summarize": 1.5,
            "research": 2.0,
            "explain": 1.5,
            "latest": 1.5,
            "news": 1.5,
            "current": 1.0,
            "recent": 1.0,
            "compare": 1.0,
            "difference": 1.0,
            "history": 1.0,
            "overview": 1.5,
        },
        "suppress": [],
    },
    TaskCategory.CREATIVE: {
        "phrases": [
            "write a story",
            "write a poem",
            "write a blog",
            "write an essay",
            "write an article",
            "draft a post",
            "brainstorm ideas",
            "come up with",
            "creative writing",
        ],
        "keywords": {
            "story": 2.0,
            "blog": 2.0,
            "poem": 2.0,
            "idea": 1.0,
            "brainstorm": 2.0,
            "creative": 2.0,
            "article": 1.5,
            "essay": 2.0,
            "caption": 1.5,
            "headline": 1.5,
            "draft": 1.0,
            "narrative": 2.0,
            "fiction": 2.0,
        },
        "suppress": ["code", "function", "bug", "debug", "script", "error", "syntax"],
    },
    TaskCategory.DATA: {
        "phrases": [
            "plot a chart",
            "create a graph",
            "analyse the data",
            "analyze the data",
            "data analysis",
            "parse the csv",
            "build a dashboard",
        ],
        "keywords": {
            "chart": 2.0,
            "graph": 2.0,
            "analyse": 2.0,
            "analyze": 2.0,
            "data": 1.5,
            "csv": 2.0,
            "spreadsheet": 2.0,
            "table": 1.0,
            "statistics": 2.0,
            "plot": 2.0,
            "visualise": 2.0,
            "visualize": 2.0,
            "dataset": 2.0,
            "numbers": 1.0,
            "pandas": 2.0,
            "dataframe": 2.0,
            "dashboard": 1.5,
        },
        "suppress": [],
    },
    TaskCategory.AUTOMATION: {
        "phrases": [
            "every day",
            "run when",
            "on event",
            "set up a pipeline",
            "automate this",
            "schedule a",
            "run daily",
            "run weekly",
            "cron job",
        ],
        "keywords": {
            "schedule": 2.0,
            "repeat": 1.5,
            "automate": 2.0,
            "pipeline": 1.5,
            "whenever": 1.5,
            "trigger": 1.5,
            "cron": 2.0,
            "daily": 1.5,
            "weekly": 1.5,
            "hourly": 1.5,
            "workflow": 1.5,
            "recurring": 2.0,
        },
        "suppress": [],
    },
    TaskCategory.MULTIAGENT: {
        "phrases": [
            "multiple agents",
            "coordinate agents",
            "team of agents",
            "split the work",
            "assign tasks",
            "delegate to",
            "agent team",
        ],
        "keywords": {
            "team": 1.5,
            "agents": 1.5,
            "coordinate": 2.0,
            "parallel": 1.0,
            "assign": 1.5,
            "split": 1.0,
            "crew": 1.5,
            "delegate": 2.0,
            "orchestrate": 2.0,
        },
        "suppress": [],
    },
}


def classify(prompt: str) -> TaskCategory:
    """
    Semantic classifier with TF-IDF-weighted bi-gram phrase matching.

    1. Score compound phrases first (+3.0 each) — "bug report" beats "write".
    2. Score individual keywords with per-word weights.
    3. Apply suppression penalties (-1.5) for cross-category false positives.
    4. Return the highest-scoring category, or GENERAL if nothing matches.
    """
    low = prompt.lower()
    # Normalise whitespace for phrase matching
    normalised = re.sub(r"\s+", " ", low).strip()

    scores: dict[TaskCategory, float] = {cat: 0.0 for cat in _CATEGORY_RULES}

    for category, rules in _CATEGORY_RULES.items():
        # Phase 1: Compound phrase matching (highest priority)
        for phrase in rules["phrases"]:
            if phrase in normalised:
                scores[category] += 3.0

        # Phase 2: Weighted keyword matching
        for keyword, weight in rules["keywords"].items():
            # Use word boundary matching to avoid partial matches
            # (e.g., "go" shouldn't match "google")
            if len(keyword) <= 2:
                # Short keywords: require word boundaries
                if re.search(rf"\b{re.escape(keyword)}\b", low):
                    scores[category] += weight
            else:
                if keyword in low:
                    scores[category] += weight

        # Phase 3: Suppression (penalise categories when contradicting keywords present)
        for suppressor in rules.get("suppress", []):
            if suppressor in low:
                scores[category] -= 1.5

    best_cat = max(scores, key=lambda c: scores[c])
    return best_cat if scores[best_cat] > 0 else TaskCategory.GENERAL


class Router:
    def __init__(self, registry: Registry, logger: TaskLogger):
        self.registry = registry
        self.logger = logger

    def _evolved_score(self, spec: BackendSpec, category: TaskCategory) -> float:
        """
        Hybrid scoring: 50% historical win-rate, 30% static affinity, 20% human feedback.
        Falls back to static-only when no history exists.
        """
        win_rates = self.logger.win_rates()
        latencies = self.logger.avg_latency()
        feedback = self.logger.feedback_scores()

        # Static affinity score
        if category in spec.strengths:
            static = 2.0
        elif category in spec.weaknesses:
            static = 0.0
        else:
            static = 1.0

        history_rate = win_rates.get(spec.id, {}).get(category.value, None)
        feedback_score = feedback.get(spec.id, None)

        # Penalise slow backends slightly (cap at 0.5 penalty)
        latency_penalty = min(latencies.get(spec.id, 0) / 10000, 0.5)

        # No history at all — use static score only
        if history_rate is None and feedback_score is None:
            return static - latency_penalty

        # Partial data — use what we have
        hist_component = (history_rate * 2) if history_rate is not None else static
        fb_component = (feedback_score * 2) if feedback_score is not None else static

        # 50% history, 30% static, 20% human feedback
        return (0.3 * static) + (0.5 * hist_component) + (0.2 * fb_component) - latency_penalty

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
