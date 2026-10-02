"""病历质量分析报表 HTTP 合同；服务全部替换，不访问数据库。"""

from __future__ import annotations

import codecs
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import quality_reports as routes
from app.services import record_quality_report_service as service

BASE = "/api/v1/quality-reports/record-quality"


def _client(roles=("qc_manager",)) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "qc-1", "roles": list(roles)}
    return TestClient(app)


def test_summary_reuses_authorized_scope_and_returns_service_contract(monkeypatch):
    captured = {}

    def build(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(service, "build_report_context", build)
    monkeypatch.setattr(service, "summarize", lambda _ctx: {"scope": {"scene": "running"}, "kpis": {"record_total": 3}})
    response = _client().get(BASE, params={
        "scene": "running", "department": "内科", "doctor": "张医生", "defect_source": "manual",
    })
    assert response.status_code == 200
    assert response.json()["data"]["kpis"]["record_total"] == 3
    assert captured["department"] == "内科"
    assert captured["doctor"] == "张医生"
    assert captured["defect_source"] == "manual"


def test_records_passes_filters_and_page_to_same_context(monkeypatch):
    context = object()
    captured = {}
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: context)

    def records(ctx, **kwargs):
        assert ctx is context
        captured.update(kwargs)
        return {"total": 1, "page": 2, "page_size": 10, "items": [{"patient_id": "p-1"}]}

    monkeypatch.setattr(service, "records_page", records)
    response = _client().get(f"{BASE}/records", params={
        "scene": "running", "rule_id": "LX0609-001", "document": "病程记录",
        "grade": "甲", "has_defect": "true", "page": 2, "page_size": 10,
    })
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["patient_id"] == "p-1"
    assert captured["rule_id"] == "LX0609-001"
    assert captured["has_defect"] is True
    assert (captured["page"], captured["page_size"]) == (2, 10)


@pytest.mark.parametrize("scene", ["running", "final"])
def test_remediation_scope_identity_pagination_and_export(monkeypatch, scene):
    context = object()
    analysis = {"rows": [], "labels": [], "assumptions": [], "contract_status": "confirmed"}
    calls = []
    monkeypatch.setattr(service, "build_report_context", lambda **kwargs: calls.append(kwargs) or context)
    def build(ctx, *, actor_id):
        assert ctx is context and actor_id == "qc-1"
        return analysis
    monkeypatch.setattr(routes.remediation_report_service, "build_analysis", build)
    monkeypatch.setattr(routes.remediation_report_service, "page", lambda data, **kwargs: {"contract_status": data["contract_status"], **kwargs})
    response = _client().get(f"{BASE}/remediations", params={"scene": scene, "label": "clinical_appeal", "page": 2, "defect_source": "manual"})
    assert response.status_code == 200 and response.json()["data"]["label"] == "clinical_appeal"
    assert calls[-1]["scene"] == scene and calls[-1]["defect_source"] == "manual"
    labels = []
    monkeypatch.setattr(routes.remediation_report_service, "export_csv", lambda data, *, label: labels.append(label) or codecs.BOM_UTF8 + b"synthetic\n")
    response = _client().get(f"{BASE}/remediations/export", params={"scene": scene, "label": "clinical_appeal"})
    assert response.status_code == 200 and response.content.startswith(codecs.BOM_UTF8)
    assert labels == ["clinical_appeal"] and response.headers["cache-control"] == "no-store"


def test_remediation_owner_failure_is_503_not_empty_data(monkeypatch):
    monkeypatch.setattr(service, "build_report_context", lambda **kwargs: object())
    def fail(*args, **kwargs):
        raise RuntimeError("private source SQL")
    monkeypatch.setattr(routes.remediation_report_service, "build_analysis", fail)
    for path in ("remediations", "remediations/export"):
        response = _client().get(f"{BASE}/{path}", params={"scene": "running"})
        assert response.status_code == 503 and "private source SQL" not in response.text


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",)])
def test_remediation_http_roles_cannot_override_persistent_owner(monkeypatch, roles):
    called = []
    monkeypatch.setattr(service, "build_report_context", lambda **kwargs: called.append(kwargs))
    assert _client(roles).get(f"{BASE}/remediations", params={"scene": "running"}).status_code == 403
    assert called == []


def test_export_is_attachment_with_bom_and_audit(monkeypatch):
    events = []
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: object())
    monkeypatch.setattr(service, "export_csv", lambda _ctx, **_kwargs: codecs.BOM_UTF8 + "科室,数量\r\n内科,1\r\n".encode())
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: events.append(kwargs))
    response = _client().get(f"{BASE}/export", params={"scene": "running", "sheet": "departments"})
    assert response.status_code == 200
    assert response.content.startswith(codecs.BOM_UTF8)
    assert response.headers["content-disposition"] == 'attachment; filename="record_quality_running_departments.csv"'
    assert response.headers["cache-control"] == "no-store"
    assert events[0]["action"] == "quality_reports.record_quality.export"
    assert events[0]["details"]["sheet"] == "departments"


def test_export_passes_structured_columns_without_splitting_grade_names(monkeypatch):
    captured = {}
    monkeypatch.setattr(service, "build_report_context", lambda **_: object())
    def export(_ctx, **kwargs):
        captured.update(kwargs)
        return b"synthetic\n"
    monkeypatch.setattr(service, "export_csv", export)
    columns = ["defect_total", "grade_rate:优秀,合格"]
    response = _client().get(f"{BASE}/export", params={
        "scene": "final", "sheet": "departments", "columns": json.dumps(columns),
    })
    assert response.status_code == 200
    assert captured["columns"] == columns
    for invalid in ('{}', '[1]', 'invalid'):
        assert _client().get(f"{BASE}/export", params={
            "scene": "running", "sheet": "departments", "columns": invalid,
        }).status_code == 422


def test_filtered_department_summary_export_uses_real_csv_service(monkeypatch):
    context = service.ReportContext(
        scene="running",
        scope={"scene": "running", "defect_source": "all"},
        record_total=1, unavailable_total=0, rows=[], standard=None,
        score_status="no_standard", review_status="available", manual_status="available",
        rule_meta={}, department_record_totals={"内科": 1}, doctor_record_totals={"张医生": 1},
    )
    captured = {}

    def build(**kwargs):
        captured.update(kwargs)
        return context

    monkeypatch.setattr(service, "build_report_context", build)
    for sheet, expected in (("departments", "内科"), ("doctors", "张医生")):
        response = _client().get(f"{BASE}/export", params={
            "scene": "running", "department": "内科", "doctor": "张医生", "sheet": sheet,
        })
        assert response.status_code == 200
        assert response.content.startswith(codecs.BOM_UTF8)
        assert expected in response.content.decode("utf-8-sig")
    assert captured["department"] == "内科" and captured["doctor"] == "张医生"


def test_summary_export_rejects_case_drilldown_filters(monkeypatch):
    context = service.ReportContext(
        scene="running", scope={"scene": "running", "defect_source": "all"},
        record_total=0, unavailable_total=0, rows=[], standard=None,
        score_status="no_standard", review_status="available", manual_status="available",
        rule_meta={}, department_record_totals={}, doctor_record_totals={},
    )
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: context)
    response = _client().get(f"{BASE}/export", params={
        "scene": "running", "sheet": "departments", "rule_id": "LX0609-001",
    })
    assert response.status_code == 422


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",), ()])
def test_non_manager_roles_are_forbidden_before_read(monkeypatch, roles):
    def forbidden(**_kwargs):
        raise AssertionError("不应读取报表")

    monkeypatch.setattr(service, "build_report_context", forbidden)
    for path, extra in ((BASE, {}), (f"{BASE}/records", {}), (f"{BASE}/export", {"sheet": "records"})):
        assert _client(roles).get(path, params={"scene": "running", **extra}).status_code == 403


@pytest.mark.parametrize("path, extra", [
    (BASE, {}), (f"{BASE}/records", {}), (f"{BASE}/export", {"sheet": "records"}),
])
def test_final_scene_is_served_with_unverified_archive_scope(monkeypatch, path, extra):
    captured = {}
    context = service.ReportContext(
        scene="final", scope={"scene": "final", "defect_source": "all", **service.SCENE_SCOPES["final"]},
        record_total=0, unavailable_total=0, rows=[], standard=None,
        score_status="no_standard", review_status="available", manual_status="available",
        rule_meta={}, department_record_totals={}, doctor_record_totals={},
    )

    def build(**kwargs):
        captured.update(kwargs)
        return context

    monkeypatch.setattr(service, "build_report_context", build)
    response = _client().get(path, params={"scene": "final", **extra})
    assert response.status_code == 200
    assert captured["scene"] == "final"
    if path == BASE:
        assert response.json()["data"]["scope"]["archive_status"] == "unverified"


def test_read_failure_is_redacted_and_export_not_audited(monkeypatch):
    events = []
    monkeypatch.setattr(service, "build_report_context", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("patient P001 SQL secret")))
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **_kwargs: events.append(1))
    response = _client().get(f"{BASE}/export", params={"scene": "running", "sheet": "records"})
    assert response.status_code == 503
    assert response.json()["detail"] == "病历质量报表暂不可用，请稍后重试"
    assert "P001" not in response.text and "secret" not in response.text
    assert events == []


@pytest.mark.parametrize("params", [
    {"scene": "outpatient"},
    {"scene": "running", "defect_source": "unknown"},
    {"scene": "running", "page": 0},
])
def test_bad_query_is_422(params):
    path = f"{BASE}/records" if "page" in params else BASE
    assert _client().get(path, params=params).status_code == 422
