"""申诉审核 HTTP 边界：权限、状态错误和数据库故障不伪报成功。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.security import get_current_user
from app.routers import appeals


def client_for(user):
    app = FastAPI()
    app.include_router(appeals.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def reviewer(role="qc_manager", user_id="reviewer-1"):
    return {
        "id": user_id,
        "name": "审核员",
        "email": "reviewer@example.invalid",
        "roles": [role],
    }


@pytest.mark.parametrize("role", ["doctor", "qc_staff"])
def test_user_without_review_permission_cannot_touch_service(monkeypatch, role):
    calls = []
    monkeypatch.setattr(appeals, "review_appeal_atomically", lambda *args, **kwargs: calls.append(args), raising=False)
    monkeypatch.setattr(appeals, "get_supabase", lambda: None)

    response = client_for(reviewer(role)).post(
        "/api/v1/appeals/appeal-1/review", json={"action": "approve"}
    )

    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_authorized_review_returns_persisted_result(monkeypatch, role):
    calls = []

    def save(appeal_id, **kwargs):
        calls.append((appeal_id, kwargs))
        return {"id": appeal_id, "status": "approved", "reviewer_id": kwargs["reviewer_id"]}

    monkeypatch.setattr(appeals, "review_appeal_atomically", save, raising=False)
    monkeypatch.setattr(appeals, "get_supabase", lambda: None)

    response = client_for(reviewer(role)).post(
        "/api/v1/appeals/appeal-1/review",
        json={"action": "approve", "comment": "确认申诉"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "approved"
    assert len(calls) == 1
    assert calls[0][0] == "appeal-1"
    assert calls[0][1]["reviewer_id"] == "reviewer-1"
    assert calls[0][1]["action"].value == "approve"


def test_review_without_user_id_is_rejected_before_save(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "review_appeal_atomically", lambda *args, **kwargs: calls.append(args), raising=False)
    monkeypatch.setattr(appeals, "get_supabase", lambda: None)

    response = client_for(reviewer(user_id="")).post(
        "/api/v1/appeals/appeal-1/review", json={"action": "approve"}
    )

    assert response.status_code == 401
    assert calls == []


def test_review_audit_role_is_the_authorized_role(monkeypatch):
    saved = []

    def save(appeal_id, **kwargs):
        saved.append(kwargs)
        return {"id": appeal_id, "status": "reviewing"}

    monkeypatch.setattr(appeals, "review_appeal_atomically", save)
    user = reviewer()
    user["roles"] = ["doctor", "qc_manager"]
    user["role"] = "doctor"

    response = client_for(user).post(
        "/api/v1/appeals/appeal-1/review", json={"action": "request_info"}
    )

    assert response.status_code == 200
    assert saved[0]["reviewer_role"] == "qc_manager"


def test_review_not_found_and_conflict_have_distinct_statuses(monkeypatch):
    from app.services.appeal_review_service import AppealReviewConflict, AppealReviewNotFound

    monkeypatch.setattr(appeals, "get_supabase", lambda: None)
    client = client_for(reviewer())
    for error, expected in ((AppealReviewNotFound("missing"), 404), (AppealReviewConflict("closed"), 409)):
        def fail(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(appeals, "review_appeal_atomically", fail, raising=False)
        response = client.post("/api/v1/appeals/appeal-1/review", json={"action": "approve"})
        assert response.status_code == expected


def test_database_error_is_sanitized(monkeypatch, caplog):
    def fail(*_args, **_kwargs):
        raise RuntimeError("private SQL parameters and patient data")

    monkeypatch.setattr(appeals, "review_appeal_atomically", fail, raising=False)
    monkeypatch.setattr(appeals, "get_supabase", lambda: None)

    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = client_for(reviewer()).post(
            "/api/v1/appeals/appeal-1/review", json={"action": "approve"}
        )

    assert response.status_code == 503
    assert "private SQL" not in response.text
    assert "private SQL" not in caplog.text


def test_review_permission_precedes_body_validation(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "review_appeal_atomically", lambda *args, **kwargs: calls.append(args))
    private_input = {"action": "approve", "comment": {"patient_name": "private-name"}}

    denied = client_for(reviewer("doctor")).post(
        "/api/v1/appeals/appeal-1/review", json=private_input
    )
    invalid = client_for(reviewer()).post(
        "/api/v1/appeals/appeal-1/review", json=private_input
    )

    assert denied.status_code == 403
    assert invalid.status_code == 422
    assert "private-name" not in denied.text
    assert "private-name" not in invalid.text
    assert calls == []


def test_withdraw_maps_ownership_conflict_and_database_failure(monkeypatch, caplog):
    from app.services.appeal_review_service import AppealReviewConflict, AppealWithdrawForbidden

    client = client_for(reviewer("doctor"))
    for error, expected in (
        (AppealWithdrawForbidden("private-name"), 403),
        (AppealReviewConflict("closed"), 409),
        (RuntimeError("private SQL parameters"), 503),
    ):
        def fail(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(appeals, "withdraw_appeal_atomically", fail)
        with caplog.at_level("ERROR", logger="app.routers.appeals"):
            response = client.post("/api/v1/appeals/appeal-1/withdraw", json={})
        assert response.status_code == expected
        assert "private" not in response.text
    assert "private SQL" not in caplog.text


def test_withdraw_validation_does_not_echo_private_input(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "withdraw_appeal_atomically", lambda *args, **kwargs: calls.append(args))

    response = client_for(reviewer("doctor")).post(
        "/api/v1/appeals/appeal-1/withdraw",
        json={"reason": {"patient_name": "private-name"}},
    )

    assert response.status_code == 422
    assert "private-name" not in response.text
    assert calls == []


def test_review_and_withdraw_openapi_keep_request_body_contract():
    from app.schemas.appeals import ReviewAction

    app = FastAPI()
    app.include_router(appeals.router)
    paths = app.openapi()["paths"]
    review_schema = paths["/api/v1/appeals/{appeal_id}/review"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    withdraw_schema = paths["/api/v1/appeals/{appeal_id}/withdraw"]["post"]["requestBody"]["content"]["application/json"]["schema"]

    assert review_schema["required"] == ["action"]
    assert review_schema["properties"]["action"]["enum"] == [action.value for action in ReviewAction]
    assert "$ref" not in review_schema["properties"]["action"]
    assert "reason" in withdraw_schema["properties"]
