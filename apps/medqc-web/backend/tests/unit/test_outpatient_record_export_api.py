from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import records
from app.services import outpatient_record_list_service as service


def _client(role: str = "admin", *, department: str = "心内科") -> TestClient:
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": f"user-{role}", "email": f"{role}@example.com",
        "roles": [role], "department": department,
    }
    return TestClient(app)


def test_list_and_export_forward_identical_authorized_filters(monkeypatch):
    seen = []
    audits = []

    async def query_records(**kwargs):
        seen.append(("list", kwargs["filters"]))
        return service.OutpatientRecordPage(items=[], total=0)

    async def export_records(**kwargs):
        seen.append(("export", kwargs["filters"]))
        return service.OutpatientRecordExport(content=b"\xef\xbb\xbfcsv", row_count=0)

    monkeypatch.setattr(records, "get_supabase", lambda: object())
    monkeypatch.setattr(service, "query_records", query_records)
    monkeypatch.setattr(service, "export_records", export_records)
    monkeypatch.setattr(records, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    query = (
        "keyword=abc&department=%E5%BF%83%E5%86%85%E7%A7%91&status=passed"
        "&start_date=2026-09-01&end_date=2026-09-28&scoring_standard=v36"
        "&sort_field=score&sort_order=asc"
    )
    client = _client("admin")

    list_response = client.get(f"/api/v1/records/outpatient-emergency?{query}")
    export_response = client.get(f"/api/v1/records/outpatient-emergency/export?{query}")

    assert list_response.status_code == 200
    assert export_response.status_code == 200
    assert seen[0][1] == seen[1][1]
    assert export_response.content == b"\xef\xbb\xbfcsv"
    assert export_response.headers["cache-control"] == "no-store"
    assert export_response.headers["content-disposition"].endswith(
        "outpatient-emergency-records.csv"
    )
    assert audits[0]["details"] == {
        "keyword_applied": True,
        "department_applied": True,
        "status_applied": True,
        "start_date": "2026-09-01",
        "end_date": "2026-09-28",
        "scoring_standard_applied": True,
        "sort_field": "score",
        "sort_order": "asc",
        "total_rows": 0,
        "limit": 10_000,
    }


def test_doctor_list_is_forced_to_own_department_but_export_requires_export_permission(monkeypatch):
    seen = []

    async def query_records(**kwargs):
        seen.append(kwargs["filters"].department)
        return service.OutpatientRecordPage(items=[], total=0)

    monkeypatch.setattr(records, "get_supabase", lambda: object())
    monkeypatch.setattr(service, "query_records", query_records)
    monkeypatch.setattr(
        service, "export_records",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("无导出权限时不应调用")),
    )
    client = _client("doctor", department="急诊科")

    list_response = client.get("/api/v1/records/outpatient-emergency")
    export_response = client.get("/api/v1/records/outpatient-emergency/export")

    assert list_response.status_code == 200
    assert seen == ["急诊科"]
    assert export_response.status_code == 403


def test_invalid_filters_and_export_too_large_have_explicit_errors(monkeypatch):
    async def too_large(**_kwargs):
        raise service.OutpatientRecordExportTooLarge(10_001)

    monkeypatch.setattr(records, "get_supabase", lambda: object())
    monkeypatch.setattr(service, "export_records", too_large)
    client = _client("qc_manager")

    invalid = client.get(
        "/api/v1/records/outpatient-emergency/export?sort_field=created_at"
    )
    too_many = client.get("/api/v1/records/outpatient-emergency/export")

    assert invalid.status_code == 422
    assert too_many.status_code == 413
    assert too_many.json()["detail"] == {
        "code": "outpatient_export_too_large",
        "message": "匹配病历共 10001 条，超过导出上限 10000 条",
        "matched_count": 10_001,
        "limit": 10_000,
    }


def test_export_source_failure_is_redacted_and_not_audited(monkeypatch):
    audits = []

    async def fail(**_kwargs):
        raise service.OutpatientRecordSourceUnavailable("private source detail")

    monkeypatch.setattr(records, "get_supabase", lambda: object())
    monkeypatch.setattr(service, "export_records", fail)
    monkeypatch.setattr(records, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))

    response = _client("admin").get("/api/v1/records/outpatient-emergency/export")

    assert response.status_code == 503
    assert response.json()["detail"] == "门急诊病历导出暂不可用，请稍后重试"
    assert "private source detail" not in response.text
    assert audits == []
