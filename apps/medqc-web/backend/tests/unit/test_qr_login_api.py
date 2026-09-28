"""扫码登录路由合同。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limit_store_for_testing
from app.routers import auth


class FakeQrService:
    def create(self):
        return {
            "session_id": "123e4567-e89b-42d3-a456-426614174000",
            "browser_secret": "s" * 43,
            "verification_code": "123456",
            "expires_at": "2026-09-28T08:02:00.000Z",
            "poll_interval_ms": 1500,
        }

    def status(self, session_id, browser_secret):
        assert browser_secret == "s" * 43
        return {"session_id": session_id, "status": "pending", "expires_at": "2026-09-28T08:02:00.000Z"}

    def confirmation(self, session_id):
        return {
            "session_id": session_id,
            "status": "pending",
            "expires_at": "2026-09-28T08:02:00.000Z",
            "remaining_attempts": 5,
        }

    def confirm(self, session_id, code, user_id):
        assert (code, user_id) == ("123456", "user-1")
        return {"session_id": session_id, "status": "approved", "expires_at": "2026-09-28T08:02:00.000Z"}

    def reject(self, session_id, user_id):
        return {"session_id": session_id, "status": "rejected", "expires_at": "2026-09-28T08:02:00.000Z"}

    def cancel(self, session_id, browser_secret):
        return {"session_id": session_id, "status": "cancelled", "expires_at": "2026-09-28T08:02:00.000Z"}

    def exchange(self, session_id, browser_secret):
        return {"access_token": "access", "refresh_token": "refresh", "token_type": "bearer", "expires_in": 60}


def test_actual_qr_routes_keep_code_on_desktop_only(monkeypatch):
    reset_rate_limit_store_for_testing()
    monkeypatch.setattr(auth, "default_qr_login_service", FakeQrService())
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[auth.get_current_user] = lambda: {"id": "user-1"}
    session_id = "123e4567-e89b-42d3-a456-426614174000"
    with TestClient(app) as client:
        created = client.post("/api/v1/auth/qr/sessions").json()
        assert created["verification_code"] == "123456"
        status = client.post(
            f"/api/v1/auth/qr/sessions/{session_id}/status",
            json={"browser_secret": "s" * 43},
        ).json()
        assert status["status"] == "pending"
        confirmation = client.get(
            f"/api/v1/auth/qr/sessions/{session_id}/confirmation"
        ).json()
        assert "verification_code" not in confirmation
        approved = client.post(
            f"/api/v1/auth/qr/sessions/{session_id}/confirm",
            json={"verification_code": "123456"},
        ).json()
        assert approved["status"] == "approved"
        exchanged = client.post(
            f"/api/v1/auth/qr/sessions/{session_id}/exchange",
            json={"browser_secret": "s" * 43},
        ).json()
        assert exchanged["access_token"] == "access"


def test_qr_request_bodies_reject_unknown_fields(monkeypatch):
    monkeypatch.setattr(auth, "default_qr_login_service", FakeQrService())
    app = FastAPI()
    app.include_router(auth.router)
    session_id = "123e4567-e89b-42d3-a456-426614174000"
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/auth/qr/sessions/{session_id}/status",
            json={"browser_secret": "s" * 43, "verification_code": "123456"},
        )
    assert response.status_code == 422
