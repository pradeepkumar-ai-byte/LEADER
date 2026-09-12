"""
Tests for Leader telemetry, Prometheus metrics collector, OpenTelemetry spans, and JSON logging.
"""

import json
import logging

import pytest

from leader.server import create_app
from leader.telemetry import (
    JsonLogFormatter,
    MetricsRegistry,
    PrometheusMetricType,
    trace_span,
)


def test_metrics_registry_counter():
    reg = MetricsRegistry()
    reg.register_metric("test_counter", PrometheusMetricType.COUNTER, "Test counter metric")
    reg.increment_counter("test_counter", {"category": "coding"}, value=1.0)
    reg.increment_counter("test_counter", {"category": "coding"}, value=2.5)
    reg.increment_counter("test_counter", {"category": "research"}, value=1.0)

    text = reg.generate_prometheus_text()
    assert "# HELP test_counter Test counter metric" in text
    assert "# TYPE test_counter counter" in text
    assert 'test_counter{category="coding"} 3.5' in text
    assert 'test_counter{category="research"} 1.0' in text


def test_metrics_registry_gauge():
    reg = MetricsRegistry()
    reg.register_metric("test_gauge", PrometheusMetricType.GAUGE, "Test gauge metric")
    reg.set_gauge("test_gauge", 42.0, {"backend_id": "direct_llm"})

    text = reg.generate_prometheus_text()
    assert "# HELP test_gauge Test gauge metric" in text
    assert "# TYPE test_gauge gauge" in text
    assert 'test_gauge{backend_id="direct_llm"} 42.0' in text

    reg.set_gauge("test_gauge", 10.0, {"backend_id": "direct_llm"})
    text2 = reg.generate_prometheus_text()
    assert 'test_gauge{backend_id="direct_llm"} 10.0' in text2


def test_metrics_registry_histogram():
    reg = MetricsRegistry()
    reg.register_metric("test_hist", PrometheusMetricType.HISTOGRAM, "Test histogram metric")
    reg.observe_histogram("test_hist", 0.003, {"stage": "pre"})
    reg.observe_histogram("test_hist", 0.05, {"stage": "pre"})
    reg.observe_histogram("test_hist", 1.5, {"stage": "pre"})

    text = reg.generate_prometheus_text()
    assert "# HELP test_hist Test histogram metric" in text
    assert "# TYPE test_hist histogram" in text
    assert 'test_hist_bucket{le="0.005",stage="pre"} 1' in text
    assert 'test_hist_bucket{le="0.05",stage="pre"} 2' in text
    assert 'test_hist_bucket{le="+Inf",stage="pre"} 3' in text
    assert 'test_hist_count{stage="pre"} 3' in text
    assert 'test_hist_sum{stage="pre"} 1.553' in text


def test_trace_span_success():
    with trace_span("unit_test_span", {"test_attr": "val"}) as span:
        span["custom_data"] = 123
        assert span["status"] == "OK"
        assert span["name"] == "unit_test_span"

    assert span["status"] == "OK"
    assert span["duration_ms"] >= 0.0


def test_trace_span_error():
    with pytest.raises(RuntimeError):
        with trace_span("failing_span") as span:
            raise RuntimeError("Span failure simulation")

    assert span["status"] == "ERROR"
    assert "Span failure simulation" in span["error"]


def test_json_log_formatter():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="leader.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test logging structured message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "leader.test"
    assert parsed["message"] == "Test logging structured message"
    assert "timestamp" in parsed


@pytest.mark.asyncio
async def test_server_metrics_endpoint():
    from aiohttp.test_utils import TestClient, TestServer

    app = create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        # Scrape /metrics endpoint
        resp = await client.get("/metrics")
        assert resp.status == 200
        assert "text/plain" in resp.headers["Content-Type"]
        body = await resp.text()

        assert "leader_routing_requests_total" in body
        assert "leader_circuit_breaker_violations_total" in body
        assert "leader_dead_letters_total" in body
    finally:
        await client.close()
