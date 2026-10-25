from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import record_reviews
from app.services.defect_rectification_service import RectificationError
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


@pytest.fixture
def setup(monkeypatch):
    app = FastAPI()
    app.include_router(record_reviews.router)
    user = {"id": "persisted-staff", "role": "admin"}
    app.dependency_overrides[get_current_user] = lambda: user
    service = Mock()
    monkeypatch.setattr(record_reviews, "service", service)
    source = dict(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        scene="running",
        root_job_id="J",
        envelope_id="E",
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        rule_set_version="1",
    )
    with TestClient(app) as client:
        yield client, service, source, user


def test_persisted_actor_and_frozen_contract_forwarded(setup):
    client, service, source, _ = setup
    service.current.return_value = {"state": "pending_review"}
    assert (
        client.get("/api/v1/record-reviews/current", params=source).status_code == 200
    )
    service.current.assert_called_once_with("persisted-staff", source=source)
    service.submit.return_value = {"id": "review"}
    payload = dict(
        source=source,
        expected_state="pending_review",
        decision="approved",
        reason="",
        request_id="00000000-0000-4000-8000-000000000001",
    )
    assert client.post("/api/v1/record-reviews", json=payload).status_code == 200
    service.submit.assert_called_once_with("persisted-staff", **payload)
    service.history.return_value = {"can_submit": False}
    assert client.get("/api/v1/record-reviews/review").status_code == 200
    service.history.assert_called_once_with("persisted-staff", "review")


def test_pagination_paused_scene_and_forged_roles_rejected(setup):
    client, service, source, _ = setup
    service.list.return_value = {"items": [], "pending_count": 0}
    assert (
        client.get(
            "/api/v1/record-reviews",
            params={"state": "history", "scene": "final", "page": 2, "page_size": 20},
        ).status_code
        == 200
    )
    service.list.assert_called_once_with(
        "persisted-staff", state="history", scene="final", page=2, page_size=20
    )
    assert (
        client.get("/api/v1/record-reviews", params={"page_size": 101}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/record-reviews/current",
            params={**source, "scene": "outpatient_emergency"},
        ).status_code
        == 422
    )
    payload = dict(
        source=source,
        expected_state="pending_review",
        decision="approved",
        reason="",
        request_id="00000000-0000-4000-8000-000000000001",
        actor_id="other",
    )
    assert client.post("/api/v1/record-reviews", json=payload).status_code == 422
    service.submit.assert_not_called()


def test_unknown_database_errors_are_not_success_or_zero(setup):
    client, service, _, user = setup
    service.list.side_effect = RuntimeError("synthetic-private-error")
    response = client.get("/api/v1/record-reviews")
    assert response.status_code == 503
    assert "synthetic-private-error" not in response.text
    assert "暂不可用" in response.text
    service.history.side_effect = RectificationError("无权访问", 403)
    assert client.get("/api/v1/record-reviews/old").status_code == 403
    user.clear()
    assert client.get("/api/v1/record-reviews").status_code == 403
