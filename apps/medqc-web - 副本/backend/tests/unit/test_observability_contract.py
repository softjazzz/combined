from __future__ import annotations

import logging
import pytest

from app.core.access_control import enforce_default_auth
from app.main import create_app


def _assert_success_shell(body: dict) -> dict:
    assert body.get("success") is True
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert "data" in body
    return body["data"]


def _patch_metrics_dependencies(monkeypatch):
    monkeypatch.setattr(
        "app.routers.system.runtime_request_metrics.snapshot",
        lambda: {
            "uptime_seconds": 120,
            "total_requests": 100,
            "in_flight_requests": 2,
            "error_requests": 4,
            "error_rate": 0.04,
            "avg_latency_ms": 35.5,
            "p95_latency_ms": 120.0,
            "requests_per_second": 0.8,
            "requests_per_second_1m": 1.2,
            "status_counts": {"2xx": 96, "4xx": 3, "5xx": 1},
        },
    )
    monkeypatch.setattr(
        "app.routers.system.get_sync_health_stats",
        lambda window_minutes=60: {
            "window_minutes": window_minutes,
            "window_total_runs": 10,
            "window_failed_runs": 1,
            "window_failure_rate": 0.1,
            "last_run_lag_seconds": 20,
            "last_success_lag_seconds": 60,
        },
    )
    monkeypatch.setattr(
        "app.routers.system.SichuanQCService.stats",
        lambda self: {"total_calls": 50, "success_rate": 0.98, "avg_api_time": 0.8, "total_tokens": 4096},
    )


@pytest.fixture(autouse=True)
def _bypass_default_auth_guard(client):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    yield
    client.app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.api
def test_metrics_endpoint_exposes_runtime_qc_sync_contract(client, monkeypatch):
    _patch_metrics_dependencies(monkeypatch)

    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200, resp.text
    data = _assert_success_shell(resp.json())

    assert set(["system", "dependencies", "runtime", "qc", "sync", "timestamp"]).issubset(data.keys())
    assert set(["total_requests", "p95_latency_ms", "requests_per_second_1m"]).issubset(data["runtime"].keys())
    assert set(["total_calls", "success_rate", "avg_api_time"]).issubset(data["qc"].keys())
    assert set(["window_total_runs", "window_failure_rate", "last_success_lag_seconds"]).issubset(
        data["sync"].keys()
    )


@pytest.mark.unit
@pytest.mark.api
def test_prometheus_metrics_contains_core_series(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.system.runtime_request_metrics.snapshot",
        lambda: {
            "uptime_seconds": 60,
            "total_requests": 20,
            "in_flight_requests": 1,
            "error_requests": 1,
            "error_rate": 0.05,
            "avg_latency_ms": 40.0,
            "p95_latency_ms": 200.0,
            "requests_per_second": 0.3,
            "requests_per_second_1m": 0.5,
            "status_counts": {"2xx": 18, "4xx": 1, "5xx": 1},
        },
    )
    monkeypatch.setattr(
        "app.routers.system.get_sync_health_stats",
        lambda window_minutes=60: {
            "window_minutes": window_minutes,
            "window_total_runs": 5,
            "window_failed_runs": 1,
            "window_failure_rate": 0.2,
            "last_run_lag_seconds": 30,
            "last_success_lag_seconds": 90,
        },
    )
    monkeypatch.setattr(
        "app.routers.system.SichuanQCService.stats",
        lambda self: {"total_calls": 8, "success_rate": 0.9, "avg_api_time": 1.1, "total_tokens": 1024},
    )

    resp = client.get("/api/v1/metrics/prometheus")
    assert resp.status_code == 200, resp.text
    text = resp.text

    required_series = [
        "medqc_runtime_requests_total",
        "medqc_runtime_request_latency_p95_ms",
        "medqc_runtime_requests_per_second_1m",
        "medqc_qc_total_calls",
        "medqc_sync_failure_rate",
        "medqc_sync_last_success_lag_seconds",
        'medqc_runtime_status_bucket_total{env="',
    ]
    for metric_name in required_series:
        assert metric_name in text


@pytest.mark.unit
@pytest.mark.api
def test_trace_id_header_passthrough_x_trace_id(client, monkeypatch):
    _patch_metrics_dependencies(monkeypatch)
    trace_id = "trace-client-123"

    resp = client.get("/api/v1/metrics", headers={"X-Trace-ID": trace_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["trace_id"] == trace_id
    assert resp.headers.get("X-Trace-ID") == trace_id


@pytest.mark.unit
@pytest.mark.api
def test_trace_id_header_fallback_x_request_id(client, monkeypatch):
    _patch_metrics_dependencies(monkeypatch)
    trace_id = "req-client-456"

    resp = client.get("/api/v1/metrics", headers={"X-Request-ID": trace_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["trace_id"] == trace_id
    assert resp.headers.get("X-Trace-ID") == trace_id


@pytest.mark.unit
@pytest.mark.api
def test_trace_id_header_extracts_traceparent(client, monkeypatch):
    _patch_metrics_dependencies(monkeypatch)
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    expected_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    resp = client.get("/api/v1/metrics", headers={"traceparent": traceparent})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["trace_id"] == expected_trace_id
    assert resp.headers.get("X-Trace-ID") == expected_trace_id


@pytest.mark.unit
@pytest.mark.api
def test_trace_id_header_generates_when_missing(client, monkeypatch):
    _patch_metrics_dependencies(monkeypatch)

    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    trace_id = body.get("trace_id")

    assert isinstance(trace_id, str) and trace_id
    assert resp.headers.get("X-Trace-ID") == trace_id


@pytest.mark.unit
@pytest.mark.api
def test_traceparent_request_log_and_response_keep_same_trace_id(client, monkeypatch, caplog):
    _patch_metrics_dependencies(monkeypatch)
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-1111111111111111-01"
    expected_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/api/v1/metrics", headers={"traceparent": traceparent})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["trace_id"] == expected_trace_id
    assert resp.headers.get("X-Trace-ID") == expected_trace_id

    completed_records = [r for r in caplog.records if r.name == "app.access" and "Request completed" in r.message]
    assert completed_records, "missing request completed log"
    completed = completed_records[-1]
    assert getattr(completed, "trace_id", None) == expected_trace_id
    assert getattr(completed, "method", None) == "GET"
    assert getattr(completed, "path", None) == "/api/v1/metrics"
    assert isinstance(getattr(completed, "status_code", None), int)
    assert getattr(completed, "duration_ms", None)


@pytest.mark.unit
def test_otel_enabled_with_unreachable_exporter_does_not_block_startup(monkeypatch):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "medqc-test")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1/v1/traces")
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")

    app = create_app()
    assert app is not None
    assert hasattr(app.state, "otel_enabled")


@pytest.mark.unit
@pytest.mark.api
def test_exception_response_still_contains_trace_id(client, monkeypatch):
    def _raise_metrics_error():
        raise RuntimeError("boom")

    monkeypatch.setattr("app.routers.system.runtime_request_metrics.snapshot", _raise_metrics_error)
    monkeypatch.setattr(
        "app.routers.system.get_sync_health_stats",
        lambda window_minutes=60: {
            "window_minutes": window_minutes,
            "window_total_runs": 0,
            "window_failed_runs": 0,
            "window_failure_rate": 0.0,
            "last_run_lag_seconds": None,
            "last_success_lag_seconds": None,
        },
    )
    monkeypatch.setattr(
        "app.routers.system.SichuanQCService.stats",
        lambda self: {"total_calls": 0, "success_rate": 0.0, "avg_api_time": 0.0, "total_tokens": 0},
    )

    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 500, resp.text
    body = resp.json()
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert resp.headers.get("X-Trace-ID") == body["trace_id"]
