from unittest.mock import Mock

import pytest
from app.core.security import get_current_user
from app.routers import core_system_reports as api
from app.services.defect_rectification_service import RectificationError
from app.services.record_quality_report_service import RecordQualityReportInvalid
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    service = Mock()
    monkeypatch.setattr(api, "service", service)
    monkeypatch.setattr(api, "audit_event", service.audit)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic-user"}
    return TestClient(app), service, app


def test_private_export_rows_stripped_and_query_validated(client):
    http, service, _ = client
    service.report.return_value = {"systems": [], "_export_rows": [{"private": True}]}
    result = http.get(
        "/api/v1/core-system-reports", params={"scene": "final", "page": 2}
    )
    assert result.status_code == 200 and "private" not in result.text
    assert service.report.call_args.args == ("synthetic-user",)
    assert service.report.call_args.kwargs["page"] == 2
    assert (
        http.get("/api/v1/core-system-reports", params={"scene": "invalid"}).status_code
        == 422
    )
    assert (
        http.get("/api/v1/core-system-reports", params={"page_size": 101}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "error,status",
    [
        (RectificationError("无权", 403), 403),
        (RecordQualityReportInvalid("无效"), 422),
        (RuntimeError("private SQL"), 503),
    ],
)
def test_expected_error_and_source_failure_no_fake_zero(client, error, status):
    http, service, _ = client
    service.report.side_effect = error
    result = http.get("/api/v1/core-system-reports")
    assert (
        result.status_code == status
        and "private SQL" not in result.text
        and "systems" not in result.text
    )


def test_missing_actor_denied(client):
    http, service, app = client
    app.dependency_overrides[get_current_user] = lambda: {
        "id": None,
        "roles": ["admin"],
    }
    assert http.get("/api/v1/core-system-reports").status_code == 403
    service.report.assert_not_called()


def test_csv_same_filters_formula_guard_and_audit_without_patient_details(client):
    http, service, _ = client
    service.report.return_value = {
        "as_of": "2026-10-01T00:00:00Z",
        "total": 1,
        "_export_rows": [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "patient_name": "=synthetic()",
                "department": "内科",
                "doctor": "合成",
                "completed_at": None,
                "root_job_id": "J1",
                "envelope_id": "E1",
                "rule_set_key": "synthetic",
                "rule_set_version": "v1",
                "coverage": "unknown",
                "points": [],
            }
        ],
    }
    result = http.get(
        "/api/v1/core-system-reports/export",
        params={"institute_id": "H1", "system_id": "unknown", "problems_only": False},
    )
    assert (
        result.status_code == 200
        and "'=synthetic()" in result.text
        and "H1,P1,V1" in result.text
    )
    assert result.headers["cache-control"] == "no-store"
    assert service.report.call_args.kwargs["system_id"] == "unknown"
    details = service.audit.call_args.kwargs["details"]
    assert details["row_count"] == 1 and "patient_id" not in details
