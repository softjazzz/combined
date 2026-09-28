from __future__ import annotations

import hashlib
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import qc_sample_pools
from app.services.test_record_import_service import (
    ImportValidationError,
    ParsedTestRecord,
    TestRecordImportValidationError,
)


def _client(roles=("admin",)) -> TestClient:
    app = FastAPI()
    app.include_router(qc_sample_pools.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "import-user-1",
        "roles": list(roles),
    }
    return TestClient(app)


def _parsed(case_key: str, row: int) -> ParsedTestRecord:
    return ParsedTestRecord(
        case_key=case_key,
        case_row=row,
        document_rows=(row,),
        payload={"case_title": f"{case_key}合成病历", "documents": [{"content": "合成正文"}]},
    )


def test_download_template_is_xlsx_no_store_and_rejects_sync_admin():
    response = _client().get("/api/v1/qc/sample-pools/test-records/import-template")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"PK")

    forbidden = _client(("sync_admin",)).get(
        "/api/v1/qc/sample-pools/test-records/import-template"
    )
    assert forbidden.status_code == 403


def test_import_rejects_non_xlsx_with_structured_location():
    response = _client().post(
        "/api/v1/qc/sample-pools/test-records/import",
        files={"file": ("cases.csv", b"not,xlsx", "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["errors"] == [
        {"sheet": "文件", "row": 0, "field": "文件", "message": "仅支持 .xlsx 文件"}
    ]


def test_import_validation_returns_all_locations_without_calling_creator(monkeypatch):
    creator = SimpleNamespace(create_customer_test_record=lambda **_kwargs: None)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: creator)
    monkeypatch.setattr(qc_sample_pools, "_current_version_rule_ids", lambda: {"LX0609-001"})

    def fail_parse(*_args, **_kwargs):
        raise TestRecordImportValidationError(
            [
                ImportValidationError("病历", 2, "年龄", "必须是 1–120 的整数"),
                ImportValidationError("文书", 4, "文书类型", "不属于模板支持的文书类型"),
            ]
        )

    monkeypatch.setattr(qc_sample_pools, "parse_test_record_import", fail_parse)
    response = _client().post(
        "/api/v1/qc/sample-pools/test-records/import",
        files={"file": ("cases.xlsx", b"synthetic", "application/octet-stream")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_test_record_import"
    assert detail["errors"] == [
        {"sheet": "病历", "row": 2, "field": "年龄", "message": "必须是 1–120 的整数"},
        {"sheet": "文书", "row": 4, "field": "文书类型", "message": "不属于模板支持的文书类型"},
    ]


def test_import_reports_created_and_unknown_without_exposing_exception(monkeypatch):
    monkeypatch.setattr(qc_sample_pools, "_current_version_rule_ids", lambda: {"LX0609-001"})
    monkeypatch.setattr(
        qc_sample_pools,
        "parse_test_record_import",
        lambda *_args, **_kwargs: [_parsed("CASE-A", 2), _parsed("CASE-B", 3)],
    )
    calls = []

    def create_customer_test_record(*, payload, created_by):
        calls.append((payload, created_by))
        if len(calls) == 2:
            raise RuntimeError("PRIVATE_DATABASE_EXCEPTION")
        return {
            "item": {"id": "ct-created", "matched_institute_id": "CUSTOMER_TEST"},
            "patient_id": "CUSTOMER_PATIENT_1",
            "visit_id": "CUSTOMER_TEST_1",
            "bundle_status": "pending",
            "bundle_error": "bundle refresh failed",
        }

    monkeypatch.setattr(
        qc_sample_pools,
        "_service",
        lambda: SimpleNamespace(create_customer_test_record=create_customer_test_record),
    )
    audit = []
    monkeypatch.setattr(qc_sample_pools, "audit_event", lambda *_args, **kwargs: audit.append(kwargs))

    response = _client().post(
        "/api/v1/qc/sample-pools/test-records/import",
        files={"file": ("cases.xlsx", b"synthetic", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["total"], data["created"], data["unknown"]) == (2, 1, 1)
    assert data["results"][0] == {
        "case_key": "CASE-A",
        "case_row": 2,
        "document_rows": [2],
        "status": "created",
        "message": "病历已创建，资料视图仍在准备，请稍后刷新",
        "item_id": "ct-created",
        "institute_id": "CUSTOMER_TEST",
        "patient_id": "CUSTOMER_PATIENT_1",
        "visit_id": "CUSTOMER_TEST_1",
        "bundle_status": "pending",
    }
    assert data["results"][1]["status"] == "unknown"
    assert "请勿盲目重试" in data["results"][1]["message"]
    assert "PRIVATE_DATABASE_EXCEPTION" not in str(response.json())
    assert calls[0][1] == "import-user-1"
    assert audit[0]["outcome"] == "partial"


def test_import_rejects_actor_without_stable_id_before_reading_rules(monkeypatch):
    app = FastAPI()
    app.include_router(qc_sample_pools.router)
    app.dependency_overrides[get_current_user] = lambda: {"roles": ["admin"]}
    rules = []
    monkeypatch.setattr(qc_sample_pools, "_current_version_rule_ids", lambda: rules.append(True))

    response = TestClient(app).post(
        "/api/v1/qc/sample-pools/test-records/import",
        files={"file": ("cases.xlsx", b"synthetic", "application/octet-stream")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "当前用户缺少稳定标识，无法导入测试病历"
    assert rules == []


def test_created_receipt_without_complete_identity_is_reported_unknown(monkeypatch):
    monkeypatch.setattr(qc_sample_pools, "_current_version_rule_ids", lambda: {"LX0609-001"})
    monkeypatch.setattr(
        qc_sample_pools,
        "parse_test_record_import",
        lambda *_args, **_kwargs: [_parsed("CASE-A", 2)],
    )
    monkeypatch.setattr(
        qc_sample_pools,
        "_service",
        lambda: SimpleNamespace(
            create_customer_test_record=lambda **_kwargs: {
                "item": {"id": "ct-created", "matched_institute_id": "CUSTOMER_TEST"},
                "patient_id": "",
                "visit_id": "CUSTOMER_TEST_1",
                "bundle_status": "ready",
            }
        ),
    )
    monkeypatch.setattr(qc_sample_pools, "audit_event", lambda *_args, **_kwargs: None)

    response = _client().post(
        "/api/v1/qc/sample-pools/test-records/import",
        files={"file": ("cases.xlsx", b"synthetic", "application/octet-stream")},
    )

    data = response.json()["data"]
    assert (data["created"], data["unknown"]) == (0, 1)
    assert data["results"][0]["status"] == "unknown"
    assert "回执不完整" in data["results"][0]["message"]


def test_same_file_for_same_user_is_rejected_while_request_is_active():
    content = b"same-request"
    key = f"import-user-1:{hashlib.sha256(content).hexdigest()}"
    qc_sample_pools._ACTIVE_TEST_RECORD_IMPORTS.add(key)
    try:
        response = _client().post(
            "/api/v1/qc/sample-pools/test-records/import",
            files={"file": ("cases.xlsx", content, "application/octet-stream")},
        )
    finally:
        qc_sample_pools._ACTIVE_TEST_RECORD_IMPORTS.discard(key)
    assert response.status_code == 409
    assert response.json()["detail"] == "相同文件正在导入，请等待当前请求完成"
