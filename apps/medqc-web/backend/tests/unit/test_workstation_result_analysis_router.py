from __future__ import annotations


def _authenticate(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-analysis"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-analysis", "roles": ["admin"]},
    )


def test_result_analysis_router_forwards_running_scope_and_visible_status_only(client, monkeypatch):
    _authenticate(monkeypatch)
    captured: dict[str, object] = {}

    def get_analysis(**kwargs):
        captured.update(kwargs)
        return {
            "scope": {"care_phase": "inpatient"},
            "kpis": {},
            "status_distribution": [],
            "rule_distribution": [],
            "physician_distribution": [],
            "selected_rule": None,
            "record_page": {"items": []},
        }

    monkeypatch.setattr(
        "app.routers.workstation.default_luxian_0609_result_analysis_service.get_analysis",
        get_analysis,
    )
    response = client.get(
        "/api/v1/workstation/qc-result-analysis/luxian-0609?"
        "care_phase=inpatient&department=ICU&doctor=%E5%BC%A0%E5%8C%BB%E7%94%9F&"
        "rule_id=LX0609-017&result_status=data_gap&page=2&page_size=10",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["scope"]["care_phase"] == "inpatient"
    assert captured["care_phase"] == "inpatient"
    assert captured["department"] == "ICU"
    assert captured["doctor"] == "张医生"
    assert captured["rule_id"] == "LX0609-017"
    assert captured["result_status"] == "data_gap"
    assert captured["page"] == 2
    assert captured["page_size"] == 10


def test_result_analysis_router_rejects_technical_error_filter_and_requires_authentication(client, monkeypatch):
    _authenticate(monkeypatch)

    unsupported_status = client.get(
        "/api/v1/workstation/qc-result-analysis/luxian-0609?"
        "care_phase=inpatient&result_status=technical_error",
        headers={"Authorization": "Bearer test-token"},
    )
    unauthenticated = client.get(
        "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged",
    )

    assert unsupported_status.status_code == 422
    assert unauthenticated.status_code == 401
