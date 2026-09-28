"""真实扫码路由到持久服务的合成闭环，不访问真实数据库。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limit_store_for_testing
from app.routers import auth
from tests.unit.test_qr_login_service import qr_context  # noqa: F401


def test_http_create_confirm_exchange_and_replay(qr_context, monkeypatch):  # noqa: F811
    service, _, _ = qr_context
    monkeypatch.setattr(auth, "default_qr_login_service", service)
    reset_rate_limit_store_for_testing()
    app = FastAPI()
    app.include_router(auth.router)
    with TestClient(app) as client:
        created_response = client.post("/api/v1/auth/qr/sessions")
        assert created_response.status_code == 200
        created = created_response.json()["data"]
        base = f"/api/v1/auth/qr/sessions/{created['session_id']}"
        secret = {"browser_secret": created["browser_secret"]}
        assert client.get(f"{base}/confirmation").status_code in {401, 403}
        assert client.post(f"{base}/exchange", json=secret).status_code == 409
        app.dependency_overrides[auth.get_current_user] = lambda: {"id": "user-1"}
        confirmation = client.get(f"{base}/confirmation")
        assert confirmation.status_code == 200
        assert "verification_code" not in confirmation.json()["data"]
        approved = client.post(
            f"{base}/confirm", json={"verification_code": created["verification_code"]},
        )
        assert approved.status_code == 200
        assert approved.json()["data"]["status"] == "approved"
        app.dependency_overrides.clear()
        polled = client.post(f"{base}/status", json=secret)
        assert polled.json()["data"]["status"] == "approved"
        assert "access_token" not in polled.json()["data"]
        exchanged = client.post(f"{base}/exchange", json=secret)
        assert exchanged.status_code == 200
        assert exchanged.json()["data"]["access_token"] == "access-user-1"
        assert client.post(f"{base}/exchange", json=secret).status_code == 409
        assert client.post(f"{base}/cancel", json=secret).status_code == 409
