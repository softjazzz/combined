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


def test_workstation_drilldown_forwards_analytics_scope_to_service(client, monkeypatch):
    _authenticate(monkeypatch)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.routers.medical_records_query.get_workstation_data",
        lambda **kwargs: captured.update(kwargs) or {"records": [], "total": 0},
    )

    response = client.get(
        "/api/medical-records/workstation?"
        "analytics_job_id=00000000-0000-0000-0000-000000000001&"
        "analytics_completed_from=2026-08-01T00:00:00&"
        "analytics_completed_to=2026-08-02T00:00:00&"
        "analytics_rule_id=LX0609-010&analytics_result_status=non_compliant&analytics_scope=final",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert captured["analytics_job_id"] == "00000000-0000-0000-0000-000000000001"
    assert captured["analytics_rule_id"] == "LX0609-010"
    assert captured["analytics_result_status"] == "non_compliant"
    assert captured["analytics_scope"] == "final"


def test_workstation_drilldown_rejects_invalid_status(client, monkeypatch):
    _authenticate(monkeypatch)
    response = client.get(
        "/api/medical-records/workstation?analytics_result_status=anything",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
