from __future__ import annotations


def _authenticate(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-analytics"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-analytics", "roles": ["admin"]},
    )


def test_luxian_analytics_router_forwards_scope_and_returns_canonical_payload(client, monkeypatch):
    _authenticate(monkeypatch)
    captured: dict[str, object] = {}
    payload = {
        "scope": {"time_basis": "qc_completed_at"},
        "kpis": {"distinct_record_total": 2},
        "status_distribution": [],
        "department_distribution": [],
        "rule_distribution": [],
        "completion_time_series": None,
        "data_health": {"canonical_invalid_or_missing_total": 0},
    }

    def _get_analytics(**kwargs):
        captured.update(kwargs)
        return payload

    monkeypatch.setattr(
        "app.routers.workstation.default_workstation_aggregation_service.get_luxian_0609_analytics",
        _get_analytics,
    )
    response = client.get(
        "/api/v1/workstation/analytics/luxian-0609?"
        "completed_from=2026-08-01T00:00:00&completed_to=2026-08-02T23:59:59&"
        "department=ICU&job_id=00000000-0000-0000-0000-000000000001",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["scope"]["time_basis"] == "qc_completed_at"
    assert captured["department"] == "ICU"
    assert str(captured["job_id"]) == "00000000-0000-0000-0000-000000000001"
    assert captured["completed_from"].isoformat().startswith("2026-08-01T00:00:00")


def test_luxian_analytics_router_rejects_invalid_scope_parameters(client, monkeypatch):
    _authenticate(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    invalid_time = client.get(
        "/api/v1/workstation/analytics/luxian-0609?completed_from=not-a-time",
        headers=headers,
    )
    invalid_job = client.get(
        "/api/v1/workstation/analytics/luxian-0609?job_id=not-a-uuid",
        headers=headers,
    )

    assert invalid_time.status_code == 422
    assert invalid_job.status_code == 422


def test_luxian_analytics_router_requires_authentication(client):
    response = client.get("/api/v1/workstation/analytics/luxian-0609")

    assert response.status_code == 401


def test_luxian_analytics_router_rejects_reverse_time_range(client, monkeypatch):
    _authenticate(monkeypatch)
    response = client.get(
        "/api/v1/workstation/analytics/luxian-0609?"
        "completed_from=2026-08-02T00:00:00&completed_to=2026-08-01T00:00:00",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
