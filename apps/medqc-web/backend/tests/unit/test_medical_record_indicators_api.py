from __future__ import annotations

import codecs

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import quality_reports as routes
from app.services import medical_record_indicator_service as service

BASE = "/api/v1/quality-reports/medical-record-indicators"


def _client(roles=("qc_manager",), department=None) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1", "roles": list(roles), "department": department,
    }
    return TestClient(app)


def test_summary_uses_authorized_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(service, "build_report_context", lambda **kwargs: captured.update(kwargs) or object())
    monkeypatch.setattr(service, "summarize", lambda _ctx: {"scope": {}, "summary": {"indicator_total": 27}, "indicators": []})
    response = _client().get(BASE, params={
        "department": "内科", "doctor": "甲医生",
        "discharged_from": "2026-09-01", "discharged_to": "2026-09-30",
    })
    assert response.status_code == 200
    assert captured["department"] == "内科" and captured["doctor"] == "甲医生"
    assert response.json()["data"]["scope"]["discharged_from"] == "2026-09-01"


def test_breakdown_cases_and_export_contract(monkeypatch):
    context = object()
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: context)
    monkeypatch.setattr(service, "breakdown", lambda ctx, **kwargs: {"dimension": kwargs["dimension"], "items": []})
    monkeypatch.setattr(service, "cases_page", lambda ctx, **kwargs: {"total": 0, "items": []})
    monkeypatch.setattr(service, "export_csv", lambda ctx, **kwargs: codecs.BOM_UTF8 + b"x,y\r\n")
    assert _client().get(f"{BASE}/breakdown", params={"indicator_code": "MER-TL-01", "dimension": "doctor"}).status_code == 200
    assert _client().get(f"{BASE}/cases", params={"indicator_code": "MER-TL-01", "state": "unknown"}).status_code == 200
    exported = _client().get(f"{BASE}/export", params={"kind": "indicators"})
    assert exported.status_code == 200 and exported.content.startswith(codecs.BOM_UTF8)
    assert exported.headers["content-disposition"] == 'attachment; filename="medical_record_indicators_indicators.csv"'


def test_non_manager_is_forbidden_before_read(monkeypatch):
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: (_ for _ in ()).throw(AssertionError()))
    for path in (BASE, f"{BASE}/breakdown?indicator_code=MER-TL-01", f"{BASE}/cases?indicator_code=MER-TL-01", f"{BASE}/export"):
        assert _client(("doctor",)).get(path).status_code == 403


def test_invalid_range_is_422_and_internal_error_is_redacted(monkeypatch):
    def fail(**_kwargs):
        raise service.MedicalRecordIndicatorInvalid("日期范围无效")

    monkeypatch.setattr(service, "build_report_context", fail)
    response = _client().get(BASE)
    assert response.status_code == 422
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("patient P001")))
    response = _client().get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "病案管理指标报表暂不可用，请稍后重试"
    assert "P001" not in response.text
