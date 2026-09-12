"""
Leader – Advanced Multi-Agent Chain & Drift Diagnostics Tests

Validates:
- FeedbackLoopDetector (Ping-Pong A<->B, Circular N-Cycles, Repetitive Echoes, Depth Budget)
- SemanticDriftTracker (Cosine distance, Aligned Subtasks, Critical Drift Alerts)
- VectorSimilarityEngine (N-gram TF-IDF representations)
- TaskLogger SQLite Schema v3 (chain_sessions & chain_steps persistence & analytics)
- Leader SDK run_chain() End-to-End Orchestration
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from leader.chain_diagnostics import (
    ChainMonitor,
    FeedbackLoopDetector,
    SemanticDriftTracker,
    VectorSimilarityEngine,
)
from leader.logger import TaskLogger
from leader.models import (
    ChainAction,
    ChainSession,
    ChainStep,
    ChainStepVerdict,
    TaskResult,
)
from leader.sdk import Leader

# ── VectorSimilarityEngine Tests ─────────────────────────────────────────────


def test_vector_similarity_identical_text():
    text = "Extract monthly user churn rate from SQL database"
    sim = VectorSimilarityEngine.cosine_similarity(text, text)
    assert sim == 1.0


def test_vector_similarity_high_relatedness():
    t1 = "Optimize PostgreSQL query performance for user transactions table"
    t2 = "Improve PostgreSQL database query execution time on user transactions"
    sim = VectorSimilarityEngine.cosine_similarity(t1, t2)
    assert sim > 0.30, f"Expected high similarity, got {sim}"


def test_vector_similarity_unrelated_text():
    t1 = "Write a haiku about butterflies in spring"
    t2 = "Configure Kubernetes ingress controller with TLS certificates"
    sim = VectorSimilarityEngine.cosine_similarity(t1, t2)
    assert sim < 0.15, f"Expected near-zero similarity, got {sim}"


def test_vector_similarity_empty_strings():
    assert VectorSimilarityEngine.cosine_similarity("", "test") == 0.0
    assert VectorSimilarityEngine.cosine_similarity("", "") == 0.0


# ── SemanticDriftTracker Tests ───────────────────────────────────────────────


def test_drift_tracker_aligned_subtasks():
    tracker = SemanticDriftTracker(warn_threshold=0.80, critical_threshold=0.95)
    root = "Build a customer churn forecasting pipeline using Python and pandas"
    step1 = "Load customer dataset from CSV into pandas DataFrame and clean null values"

    assessment = tracker.evaluate_drift(step_prompt=step1, root_prompt=root)
    assert not assessment.is_drifting
    assert not assessment.is_critical_drift
    assert assessment.drift_score < 0.80


def test_drift_tracker_warning_on_moderate_drift():
    tracker = SemanticDriftTracker(warn_threshold=0.75, critical_threshold=0.95)
    root = "Analyze quarterly financial revenue data and generate summary report"
    step_divergent = "Search online for trending cryptocurrency market prices today"

    assessment = tracker.evaluate_drift(step_prompt=step_divergent, root_prompt=root)
    assert assessment.is_drifting
    assert assessment.drift_score >= 0.75


def test_drift_tracker_critical_on_unaligned_rogue_subtask():
    tracker = SemanticDriftTracker(warn_threshold=0.80, critical_threshold=0.95)
    root = "Draft a polite email to customer support regarding billing issue"
    rogue_step = "Bypass operating system firewall rules and dump local network routing tables"

    assessment = tracker.evaluate_drift(step_prompt=rogue_step, root_prompt=root)
    assert assessment.is_critical_drift
    assert assessment.drift_score >= 0.95
    assert "CRITICAL" in assessment.description


def test_drift_tracker_multi_anchor_smooths_specialized_steps():
    tracker = SemanticDriftTracker()
    root = "Build an end-to-end web application with authentication"
    parent = "Implement JWT token generation and validation middleware"
    substep = "Generate RS256 private and public cryptographic keys for authentication"

    assessment = tracker.evaluate_drift(
        step_prompt=substep,
        root_prompt=root,
        parent_prompt=parent,
    )
    # Multi-anchor from parent should keep the technical subtask aligned
    assert assessment.drift_score < 0.90


# ── FeedbackLoopDetector Tests ───────────────────────────────────────────────


def test_loop_detector_clean_linear_chain():
    detector = FeedbackLoopDetector(max_chain_depth=10)
    steps = [
        ChainStep(
            prompt="Step 1: Scrape web data",
            source_backend="user",
            target_backend="scraper",
            chain_id="c1",
        ),
        ChainStep(
            prompt="Step 2: Clean scraped text",
            source_backend="scraper",
            target_backend="cleaner",
            chain_id="c1",
        ),
        ChainStep(
            prompt="Step 3: Analyze sentiments",
            source_backend="cleaner",
            target_backend="analyzer",
            chain_id="c1",
        ),
        ChainStep(
            prompt="Step 4: Format PDF report",
            source_backend="analyzer",
            target_backend="reporter",
            chain_id="c1",
        ),
    ]

    for step in steps:
        res = detector.record_step(step)
        assert not res.is_loop, f"False positive loop on step {step.step_id}"


def test_loop_detector_ping_pong_cycle():
    detector = FeedbackLoopDetector(max_ping_pong=2)
    chain_id = "ping-pong-c1"

    # Ping-Pong between agent_a and agent_b
    s1 = ChainStep(
        prompt="Task A1", source_backend="agent_a", target_backend="agent_b", chain_id=chain_id
    )
    s2 = ChainStep(
        prompt="Task B1", source_backend="agent_b", target_backend="agent_a", chain_id=chain_id
    )
    s3 = ChainStep(
        prompt="Task A2", source_backend="agent_a", target_backend="agent_b", chain_id=chain_id
    )
    s4 = ChainStep(
        prompt="Task B2", source_backend="agent_b", target_backend="agent_a", chain_id=chain_id
    )

    assert not detector.record_step(s1).is_loop
    assert not detector.record_step(s2).is_loop
    assert not detector.record_step(s3).is_loop

    # 4th step completes 2nd round-trip ping-pong cycle
    res4 = detector.record_step(s4)
    assert res4.is_loop
    assert res4.loop_type == "ping_pong"
    assert "agent_a" in res4.cycle_nodes and "agent_b" in res4.cycle_nodes


def test_loop_detector_circular_n_agent_cycle():
    detector = FeedbackLoopDetector()
    chain_id = "cycle-n-c1"

    # 3-agent circular cycle: A -> B -> C -> A -> B -> C
    nodes = ["agent_a", "agent_b", "agent_c"]
    steps = [
        ChainStep(
            prompt=f"Cycle step {i}",
            source_backend=nodes[i % 3],
            target_backend=nodes[(i + 1) % 3],
            chain_id=chain_id,
        )
        for i in range(6)
    ]

    for i in range(5):
        assert not detector.record_step(steps[i]).is_loop

    res = detector.record_step(steps[5])
    assert res.is_loop
    assert res.loop_type == "n_cycle"


def test_loop_detector_repetitive_payload():
    detector = FeedbackLoopDetector()
    chain_id = "rep-payload-c1"

    s1 = ChainStep(
        prompt="Please verify the server status",
        source_backend="a",
        target_backend="b",
        chain_id=chain_id,
    )
    s2 = ChainStep(
        prompt="Please verify the server status",
        source_backend="b",
        target_backend="c",
        chain_id=chain_id,
    )
    s3 = ChainStep(
        prompt="Please verify the server status",
        source_backend="c",
        target_backend="d",
        chain_id=chain_id,
    )

    detector.record_step(s1)
    detector.record_step(s2)
    res = detector.record_step(s3)

    assert res.is_loop
    assert res.loop_type == "repetitive_payload"


def test_loop_detector_depth_budget_exhaustion():
    detector = FeedbackLoopDetector(max_chain_depth=5)
    chain_id = "depth-exhaust-c1"

    for i in range(5):
        s = ChainStep(
            prompt=f"Unique task {i}",
            source_backend=f"agent_{i}",
            target_backend=f"agent_{i+1}",
            chain_id=chain_id,
        )
        assert not detector.record_step(s).is_loop

    s_exceeded = ChainStep(
        prompt="Unique task 6",
        source_backend="agent_5",
        target_backend="agent_6",
        chain_id=chain_id,
    )
    res = detector.record_step(s_exceeded)
    assert res.is_loop
    assert res.loop_type == "depth_exhaustion"


# ── ChainMonitor Tests ───────────────────────────────────────────────────────


def test_chain_monitor_verdict_proceed():
    monitor = ChainMonitor()
    root = "Analyze customer feedback dataset and calculate NPS score"
    step = ChainStep(
        prompt="Parse customer feedback dataset and calculate NPS score metrics",
        source_backend="user",
        target_backend="data_agent",
        chain_id="cm-test-01",
    )

    verdict = monitor.inspect_step(step=step, root_prompt=root)
    assert verdict.action == ChainAction.PROCEED
    assert verdict.latency_ms >= 0.0
    assert not verdict.loop_result.is_loop
    assert not verdict.drift_result.is_critical_drift


def test_chain_monitor_verdict_terminate_loop():
    detector = FeedbackLoopDetector(max_ping_pong=1)
    monitor = ChainMonitor(loop_detector=detector)
    root = "Check disk storage on server"
    chain_id = "cm-loop-01"

    s1 = ChainStep(
        prompt="Check disk storage",
        source_backend="node_a",
        target_backend="node_b",
        chain_id=chain_id,
    )
    s2 = ChainStep(
        prompt="Check disk storage",
        source_backend="node_b",
        target_backend="node_a",
        chain_id=chain_id,
    )

    monitor.inspect_step(s1, root)
    verdict2 = monitor.inspect_step(s2, root)

    assert verdict2.action == ChainAction.TERMINATE_LOOP
    assert "TERMINATE" in verdict2.summary


# ── TaskLogger Schema v3 SQLite Telemetry Tests ──────────────────────────────


def test_logger_schema_v3_chain_persistence(tmp_path: Path):
    db_path = tmp_path / "chain_history.db"
    logger = TaskLogger(db_path=db_path)

    # 1. Log Chain Session
    session = ChainSession(
        chain_id="sess-001",
        root_prompt="Extract and plot financial quarterly revenue",
        total_steps=2,
        max_drift=0.15,
        status="completed",
    )
    logger.log_chain_session(session)

    # 2. Log Chain Steps
    step1 = ChainStep(
        prompt="Extract CSV tables",
        source_backend="user",
        target_backend="direct_llm",
        step_index=0,
        chain_id="sess-001",
    )
    detector_mock = FeedbackLoopDetector()
    loop_res = detector_mock.record_step(step1)
    drift_res = SemanticDriftTracker().evaluate_drift(step1.prompt, session.root_prompt)

    verdict1 = ChainStepVerdict(
        action=ChainAction.PROCEED,
        step_id=step1.step_id,
        chain_id="sess-001",
        step_index=0,
        loop_result=loop_res,
        drift_result=drift_res,
    )
    logger.log_chain_step(step1, verdict1, output_payload="CSV extracted successfully")

    # 3. Query Chain History
    history = logger.get_chain_history("sess-001")
    assert len(history) == 1
    assert history[0]["step_id"] == step1.step_id
    assert history[0]["action_taken"] == "proceed"
    assert history[0]["output_payload"] == "CSV extracted successfully"

    # 4. Query Analytics
    analytics = logger.get_chain_analytics()
    assert analytics["total_chains"] == 1
    assert analytics["avg_chain_steps"] == 2.0
    assert analytics["peak_semantic_drift"] == 0.15


# ── Leader SDK run_chain() End-to-End Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_leader_run_chain_clean_workflow(tmp_path: Path, connected_registry):
    leader = Leader(auto_load_config=False)
    leader.registry = connected_registry
    leader.logger = TaskLogger(db_path=tmp_path / "sdk_test.db")

    mock_result = TaskResult(
        task_id="mock-t1",
        backend_id="direct_llm",
        output="Result step processed",
        success=True,
        latency_ms=10.0,
    )

    with patch.object(leader.executor, "run", new_callable=AsyncMock, return_value=mock_result):
        session = await leader.run_chain(
            root_prompt="Analyze python code quality and generate unit tests",
            steps=[
                "Parse python code files and inspect functions",
                "Generate unit tests and assertions",
            ],
        )

        assert session.status == "completed"
        assert len(session.results) == 2
        assert len(session.step_verdicts) == 2
        assert session.max_drift < 0.80


@pytest.mark.asyncio
async def test_leader_run_chain_loop_interception(tmp_path: Path, connected_registry):
    leader = Leader(auto_load_config=False)
    leader.registry = connected_registry
    leader.logger = TaskLogger(db_path=tmp_path / "loop_test.db")
    leader.chain_monitor.loop_detector.max_ping_pong = 1

    mock_result = TaskResult(
        task_id="mock-t",
        backend_id="direct_llm",
        output="Ping step 1 OK",
        success=True,
        latency_ms=10.0,
    )

    steps = [
        ChainStep(prompt="Ping token check", source_backend="agent_a", target_backend="agent_b"),
        ChainStep(prompt="Ping token check", source_backend="agent_b", target_backend="agent_a"),
    ]

    with patch.object(leader.executor, "run", new_callable=AsyncMock, return_value=mock_result):
        session = await leader.run_chain(
            root_prompt="Ping token check workflow",
            steps=steps,
        )

        assert session.status == "terminate_loop"
        assert len(session.results) == 2
        assert not session.results[-1].success
        assert "safety_chain_monitor" in session.results[-1].backend_id
