from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import defect_rectifications as api
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def client(monkeypatch):
    service = Mock()
    monkeypatch.setattr(api, "service", service)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "roles": ["admin"]}
    return TestClient(app), service


def test_actor_from_login_and_bounded_pagination(client):
    http, service = client
    service.list.return_value = {"items": [], "total": 0}
    assert http.get("/api/v1/defect-rectifications").status_code == 200
    service.list.assert_called_once_with("u1", state=None, page=1, page_size=20, source=None)
    assert http.get("/api/v1/defect-rectifications?page_size=101").status_code == 422


def test_comparison_requires_exact_submit_event_and_login(client):
    http, service = client
    service.comparison.return_value = {"available": False, "documents": []}
    assert http.get("/api/v1/defect-rectifications/t1/comparison").status_code == 422
    assert http.get("/api/v1/defect-rectifications/t1/comparison?event_id=submit1").status_code == 200
    service.comparison.assert_called_once_with("u1", "t1", "submit1")
    service.comparison.side_effect = RectificationError("无权访问", 403)
    assert http.get("/api/v1/defect-rectifications/t1/comparison?event_id=submit1").status_code == 403


@pytest.mark.parametrize("body", [
    {"version": True, "action": "submit", "comment": "这是足够长的整改说明内容"},
    {"version": 1, "action": "approve", "comment": "短"},
    {"version": 1, "action": "approve", "comment": "这是足够长的整改说明内容", "actor_id": "admin"},
    {"version": 1, "action": "withdraw_urge", "comment": "这是足够长的撤回催办说明"},
    {"version": 1, "action": "urge", "comment": "这是足够长的催办说明内容", "urge_event_id": "event1"},
])
def test_invalid_actions_rejected_before_service(client, body):
    http, service = client
    assert http.post("/api/v1/defect-rectifications/t1/actions", json=body).status_code == 422
    service.transition.assert_not_called()


def test_withdraw_action_keeps_original_event_reference(client):
    http, service = client
    service.transition.return_value = {"status": "pending"}
    body = {"version": 2, "action": "withdraw_urge", "comment": "已通知医生因此撤回本次催办", "urge_event_id": "event1"}
    assert http.post("/api/v1/defect-rectifications/t1/actions", json=body).status_code == 200
    service.transition.assert_called_once_with("u1", "t1", **body)


@pytest.mark.parametrize("code", [403, 404, 409])
def test_expected_error_semantics(client, code):
    http, service = client
    service.detail.side_effect = RectificationError("固定业务错误", code)
    assert http.get("/api/v1/defect-rectifications/t1").status_code == code


def test_unavailable_redacts_database_detail(client):
    http, service = client
    service.detail.side_effect = RuntimeError("postgresql://secret-password")
    response = http.get("/api/v1/defect-rectifications/t1")
    assert response.status_code == 503 and "secret-password" not in response.text


def test_candidates_not_swallowed_by_id_route(client):
    http, service = client
    service.candidates.return_value = {"targets": [], "doctors": []}
    response = http.get("/api/v1/defect-rectifications/candidates", params={
        "institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "expected_job_id": "J1",
    })
    assert response.status_code == 200
    service.detail.assert_not_called()


def test_create_contract_forbids_client_status_and_empty_identity(client):
    http, service = client
    body = {"institute_id": " ", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "canonical_defect", "target_id": "R1", "root_job_id": "J1",
            "envelope_id": "E1", "assignee_id": "D1", "requirement": "需要完善相应记录并提交整改",
            "status": "approved"}
    assert http.post("/api/v1/defect-rectifications", json=body).status_code == 422
    service.create.assert_not_called()
