from app.core.runtime_metrics import RuntimeRequestMetrics


def test_runtime_metrics_recording():
    metrics = RuntimeRequestMetrics()
    metrics.mark_request_started()
    metrics.mark_request_finished(status_code=200, duration_ms=12.4)
    metrics.mark_request_started()
    metrics.mark_request_finished(status_code=503, duration_ms=7.6)

    snapshot = metrics.snapshot()
    assert snapshot["total_requests"] == 2
    assert snapshot["in_flight_requests"] == 0
    assert snapshot["error_requests"] == 1
    assert snapshot["status_counts"]["2xx"] == 1
    assert snapshot["status_counts"]["5xx"] == 1
    assert snapshot["avg_latency_ms"] > 0
    assert snapshot["p95_latency_ms"] > 0
    assert snapshot["requests_per_second"] >= 0
    assert snapshot["requests_per_second_1m"] >= 0
    assert snapshot["error_rate"] == 0.5
