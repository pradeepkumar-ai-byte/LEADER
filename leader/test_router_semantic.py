"""
Leader – Semantic Router Tests

Tests the TF-IDF weighted bi-gram classifier and the evolved scoring with feedback.
"""

import pytest

from leader.logger import TaskLogger
from leader.models import RouteDecision, Task, TaskCategory
from leader.registry import Registry
from leader.router import Router, classify

# ── classify() edge cases ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "prompt, expected",
    [
        # The critical bug: "Write me a bug report" MUST be CODING, not CREATIVE
        ("Write me a bug report", TaskCategory.CODING),
        ("write a function to sort a list", TaskCategory.CODING),
        ("write a blog post about space travel", TaskCategory.CREATIVE),
        ("write a poem about rain", TaskCategory.CREATIVE),
        ("write a story about dragons", TaskCategory.CREATIVE),
        # Coding prompts
        ("debug this python error", TaskCategory.CODING),
        ("refactor the user module", TaskCategory.CODING),
        ("fix the syntax error in main.py", TaskCategory.CODING),
        ("implement a binary search algorithm", TaskCategory.CODING),
        ("write a unit test for the login function", TaskCategory.CODING),
        # Messaging prompts
        ("send a whatsapp message to mom", TaskCategory.MESSAGING),
        ("send an email to the team", TaskCategory.MESSAGING),
        ("notify me on slack when the build fails", TaskCategory.MESSAGING),
        # Research prompts
        ("what is quantum computing", TaskCategory.RESEARCH),
        ("summarize the latest AI news", TaskCategory.RESEARCH),
        ("explain how transformers work", TaskCategory.RESEARCH),
        # Data prompts
        ("analyse this csv file and plot a chart", TaskCategory.DATA),
        ("create a graph of monthly revenue", TaskCategory.DATA),
        ("visualize the dataset", TaskCategory.DATA),
        # Automation prompts
        ("every day at 9am remind me to drink water", TaskCategory.AUTOMATION),
        ("schedule a daily backup at midnight", TaskCategory.AUTOMATION),
        ("automate this workflow", TaskCategory.AUTOMATION),
        # Multi-agent prompts
        ("coordinate three agents to build a report", TaskCategory.MULTIAGENT),
        ("split the work between multiple agents", TaskCategory.MULTIAGENT),
        # General / ambiguous
        ("hello", TaskCategory.GENERAL),
        ("thanks", TaskCategory.GENERAL),
    ],
)
def test_classify_semantic(prompt, expected):
    """Verify the semantic classifier handles all edge cases correctly."""
    result = classify(prompt)
    assert result == expected, f"classify({prompt!r}) = {result.value}, expected {expected.value}"


def test_classify_phrase_beats_single_keyword():
    """Compound phrases must outweigh single-word matches."""
    # "bug report" phrase should dominate over "write" keyword
    result = classify("Write me a bug report for the login page")
    assert result == TaskCategory.CODING


def test_classify_suppression():
    """Suppression keywords should prevent false positives."""
    # "write" alone would score CREATIVE, but "code" suppresses it
    result = classify("write code to parse JSON")
    assert result == TaskCategory.CODING


# ── Router._evolved_score() with feedback ─────────────────────────────────────


def test_evolved_score_uses_feedback(tmp_path):
    """Human feedback scores should influence routing decisions."""
    db_path = tmp_path / "test.db"
    logger = TaskLogger(db_path=db_path)
    registry = Registry()

    # Simulate: backend A has good win rate but terrible feedback
    task_a = Task(prompt="test", category=TaskCategory.CODING, task_id="t1")
    decision_a = RouteDecision(primary="direct_llm", fallback_chain=[], rationale="t")
    logger.log_dispatch(task_a, decision_a)
    from leader.models import TaskResult

    logger.log_result(
        TaskResult(
            task_id="t1",
            backend_id="direct_llm",
            output="ok",
            success=True,
            latency_ms=100,
        )
    )
    # User gives terrible feedback
    logger.log_feedback("t1", rating=1)

    router = Router(registry, logger)

    spec = registry.get("direct_llm")
    score = router._evolved_score(spec, TaskCategory.CODING)

    # Score should be lower than pure static (2.0) because feedback is bad
    assert score < 2.0, f"Feedback should lower score, got {score}"


def test_feedback_scores_normalisation(tmp_path):
    """feedback_scores() should normalise 1-5 ratings to 0-1 range."""
    db_path = tmp_path / "test.db"
    logger = TaskLogger(db_path=db_path)

    task = Task(prompt="test", category=TaskCategory.CODING, task_id="t1")
    decision = RouteDecision(primary="direct_llm", fallback_chain=[], rationale="t")
    logger.log_dispatch(task, decision)
    logger.log_feedback("t1", rating=5)  # Perfect rating

    scores = logger.feedback_scores()
    assert "direct_llm" in scores
    assert scores["direct_llm"] == 1.0  # (5-1)/4 = 1.0

    logger.log_feedback("t1", rating=1)  # Terrible rating
    scores = logger.feedback_scores()
    # Average of 5 and 1 = 3, normalised = (3-1)/4 = 0.5
    assert abs(scores["direct_llm"] - 0.5) < 0.01
