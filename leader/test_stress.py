"""
Leader – Tests for High-Concurrency Load Stress Test Engine

Verifies:
  • Concurrent benign routing throughput and zero-drop rate
  • Concurrent adversarial attack detection under heavy parallel load
  • Multi-agent chain session isolation across concurrent coroutines
  • Circuit breaker state machine and SQLite WAL thread safety
  • Automated stress test report generation
"""

from __future__ import annotations

import pytest

from evals.stress_test import StressTestEngine, generate_stress_report


@pytest.mark.asyncio
async def test_stress_test_benign_concurrency(tmp_path):
    db_path = tmp_path / "stress_benign.db"
    engine = StressTestEngine(
        concurrency=10,
        total_requests_per_scenario=30,
        db_path=db_path,
    )
    try:
        metrics = await engine.run_benign_routing_stress()
        assert metrics.total_requests == 30
        assert metrics.successful_requests == 30
        assert metrics.failed_requests == 0
        assert metrics.p50_latency_ms >= 0.0
        assert metrics.throughput_rps > 0.0
    finally:
        engine.cleanup()


@pytest.mark.asyncio
async def test_stress_test_adversarial_concurrency(tmp_path):
    db_path = tmp_path / "stress_adv.db"
    engine = StressTestEngine(
        concurrency=10,
        total_requests_per_scenario=30,
        db_path=db_path,
    )
    try:
        metrics = await engine.run_adversarial_attack_stress()
        assert metrics.total_requests == 30
        assert metrics.successful_requests == 30
        assert metrics.safety_efficacy_pct == 100.0
    finally:
        engine.cleanup()


@pytest.mark.asyncio
async def test_stress_test_multiagent_chain_concurrency(tmp_path):
    db_path = tmp_path / "stress_chain.db"
    engine = StressTestEngine(
        concurrency=10,
        total_requests_per_scenario=20,
        db_path=db_path,
    )
    try:
        metrics = await engine.run_multiagent_chain_stress()
        assert metrics.successful_requests == 10
        assert metrics.failed_requests == 0
    finally:
        engine.cleanup()


@pytest.mark.asyncio
async def test_stress_test_circuit_breaker_concurrency(tmp_path):
    db_path = tmp_path / "stress_cb.db"
    engine = StressTestEngine(
        concurrency=10,
        total_requests_per_scenario=20,
        db_path=db_path,
    )
    try:
        metrics = await engine.run_circuit_breaker_stress()
        assert metrics.total_requests == 20
        assert metrics.safety_efficacy_pct == 100.0
    finally:
        engine.cleanup()


@pytest.mark.asyncio
async def test_stress_test_sqlite_wal_concurrency(tmp_path):
    db_path = tmp_path / "stress_wal.db"
    engine = StressTestEngine(
        concurrency=10,
        total_requests_per_scenario=30,
        db_path=db_path,
    )
    try:
        metrics = await engine.run_sqlite_wal_stress()
        assert metrics.total_requests == 30
        assert metrics.successful_requests == 30
        assert metrics.failed_requests == 0
    finally:
        engine.cleanup()


@pytest.mark.asyncio
async def test_stress_report_generation(tmp_path):
    db_path = tmp_path / "stress_full.db"
    engine = StressTestEngine(
        concurrency=5,
        total_requests_per_scenario=10,
        db_path=db_path,
    )
    try:
        results = await engine.run_all()
        assert len(results) == 5
        report = generate_stress_report(
            results=results,
            concurrency=5,
            total_ops=sum(r.total_requests for r in results),
        )
        assert "# LEADER Enterprise Concurrency & Load Stress Test Report" in report
        assert "Zero-Drop Rate" in report
        assert "High-Concurrency Benign Routing" in report
    finally:
        engine.cleanup()
