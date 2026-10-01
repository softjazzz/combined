from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import manual_quality_reports as api
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def client(monkeypatch):
    service = Mock()
    monkeypatch.setattr(api, "service", service)
    monkeypatch.setattr(api, "audit_event", service.audit)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "synthetic-user",
        "roles": ["admin"],
    }
    return TestClient(app), service, app


PARAMS = {"start_date": "2026-10-01", "end_date": "2026-10-01"}


def test_summary_strips_full_candidate_set_and_validates_filters(client):
    http, service, _ = client
    service.report.return_value = {
        "summary": {"entered": 1},
        "items": [],
        "_export_rows": [{"id": "private"}],
    }
    response = http.get("/api/v1/manual-quality-reports", params=PARAMS)
    assert response.status_code == 200
    assert "private" not in response.text and "_export_rows" not in response.text
    assert service.report.call_args.args == ("synthetic-user",)
    assert (
        http.get(
            "/api/v1/manual-quality-reports", params={**PARAMS, "page_size": 101}
        ).status_code
        == 422
    )
    assert (
        http.get(
            "/api/v1/manual-quality-reports", params={**PARAMS, "scene": "bad"}
        ).status_code
        == 422
    )
    assert http.get("/api/v1/manual-quality-reports").status_code == 422


@pytest.mark.parametrize("status", [403, 422])
def test_expected_errors_preserved(client, status):
    http, service, _ = client
    service.report.side_effect = RectificationError("固定错误", status)
    assert (
        http.get("/api/v1/manual-quality-reports", params=PARAMS).status_code == status
    )


def test_fault_not_zero_and_missing_actor_fail_closed(client):
    http, service, app = client
    service.report.side_effect = RuntimeError("secret SQL or private patient")
    response = http.get("/api/v1/manual-quality-reports", params=PARAMS)
    assert (
        response.status_code == 503
        and "secret" not in response.text
        and "entered" not in response.text
    )
    app.dependency_overrides[get_current_user] = lambda: {"roles": ["admin"]}
    assert http.get("/api/v1/manual-quality-reports", params=PARAMS).status_code == 403


def test_export_filtered_same_authorized_contract_and_formula_guard(client):
    http, service, _ = client
    service.report.return_value = {
        "_export_rows": [{"id": "=synthetic", "rectification_status": "unknown"}]
    }
    response = http.get(
        "/api/v1/manual-quality-reports/export",
        params={
            **PARAMS,
            "institute_id": "H1",
            "department": "内科",
            "creator_id": "u1",
            "task_id": "T1",
        },
    )
    assert (
        response.status_code == 200 and "text/csv" in response.headers["content-type"]
    )
    assert "'=synthetic" in response.text and "已确认统计口径" in response.text
    assert "待确认" not in response.text
    assert service.report.call_args.kwargs["task_id"] == "T1"
    assert service.report.call_args.kwargs["institute_id"] == "H1"
    service.audit.assert_called_once()
    assert service.audit.call_args.kwargs["details"]["row_count"] == 1
    assert "patient_id" not in service.audit.call_args.kwargs["details"]
    assert response.headers["cache-control"] == "no-store"
