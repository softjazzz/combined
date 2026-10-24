"""病案首页统计分析 HTTP 合同；服务全部替换，不访问数据库。"""

from __future__ import annotations

import codecs

import pytest
from app.core.security import get_current_user
from app.routers import quality_reports as routes
from app.services import frontpage_quality_report_service as service
from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE = "/api/v1/quality-reports/frontpage-quality"


def _client(roles=("qc_manager",), department=None) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    user = {"id": "qc-1", "roles": list(roles)}
    if department:
        user["department"] = department
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _context():
    return service.ReportContext(scope={"department": None}, rows=[])


def test_summary_passes_authorized_scope(monkeypatch):
    captured = {}

    def build(**kwargs):
        captured.update(kwargs)
        return _context()

    monkeypatch.setattr(service, "build_report_context", build)
    response = _client().get(
        BASE,
        params={
            "department": "内科",
            "doctor": "甲医生",
            "analyzed_from": "2026-09-01T00:00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["kpis"]["case_total"] == 0
    assert captured["department"] == "内科" and captured["doctor"] == "甲医生"
    assert captured["analyzed_from"].year == 2026


def test_records_forward_drilldown_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: _context())

    def page(_ctx, **kwargs):
        captured.update(kwargs)
        return {"page": 1, "page_size": 20, "total": 0, "items": []}

    monkeypatch.setattr(service, "records_page", page)
    response = _client().get(
        f"{BASE}/records",
        params={
            "department": "内科",
            "source": "coding",
            "rule_code": "CR-1",
            "problem_only": "true",
        },
    )
    assert response.status_code == 200
    assert captured == {
        "page": 1,
        "page_size": 20,
        "department": "内科",
        "source": "coding",
        "rule_code": "CR-1",
        "problem_only": True,
    }


def test_export_is_csv_and_audited(monkeypatch):
    events = []
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: _context())
    monkeypatch.setattr(
        routes, "audit_event", lambda *_args, **kwargs: events.append(kwargs)
    )
    response = _client().get(f"{BASE}/export", params={"sheet": "departments"})
    assert response.status_code == 200
    assert response.content.startswith(codecs.BOM_UTF8)
    assert response.headers["cache-control"] == "no-store"
    assert events and events[0]["action"] == "quality_reports.frontpage_quality.export"


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",), ()])
def test_non_manager_roles_are_forbidden_before_read(monkeypatch, roles):
    def forbidden(**_kwargs):
        raise AssertionError("不应读取报表")

    monkeypatch.setattr(service, "build_report_context", forbidden)
    for path, extra in (
        (BASE, {}),
        (f"{BASE}/records", {}),
        (f"{BASE}/export", {"sheet": "records"}),
    ):
        assert _client(roles).get(path, params=extra).status_code == 403


def test_schema_unavailable_is_distinct_from_generic_failure(monkeypatch):
    def missing(**_kwargs):
        raise service.FrontpageQualityReportSchemaUnavailable("未部署")

    monkeypatch.setattr(service, "build_report_context", missing)
    response = _client().get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "schema_unavailable"

    def broken(**_kwargs):
        raise RuntimeError("patient P001 SQL secret")

    events = []
    monkeypatch.setattr(service, "build_report_context", broken)
    monkeypatch.setattr(
        routes, "audit_event", lambda *_args, **_kwargs: events.append(1)
    )
    response = _client().get(f"{BASE}/export", params={"sheet": "records"})
    assert response.status_code == 503
    assert "P001" not in response.text
    assert events == []


def test_invalid_params_and_range_limit_are_422(monkeypatch):
    assert (
        _client().get(f"{BASE}/records", params={"source": "settlement"}).status_code
        == 422
    )
    assert (
        _client().get(f"{BASE}/export", params={"sheet": "doctors"}).status_code == 422
    )

    def too_large(**_kwargs):
        raise service.FrontpageQualityReportTooLarge("太大")

    monkeypatch.setattr(service, "build_report_context", too_large)
    response = _client().get(BASE)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "range_too_large"
