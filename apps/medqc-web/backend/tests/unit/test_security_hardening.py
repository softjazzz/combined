from __future__ import annotations

from uuid import uuid4


def _login(client, email: str, password: str) -> tuple[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["access_token"], body["refresh_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_high_risk_endpoints_require_auth(client):
    cases = [
        ("GET", "/api/medical-records/list"),
        ("GET", "/api/v1/drg/config/current"),
        ("GET", "/api/medical-records/settlement/list"),
        ("GET", "/api/system/db/status"),
    ]
    for method, path in cases:
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{path} expected 401, got {resp.status_code}"


def test_system_config_requires_admin_role(client):
    doctor_token, _ = _login(client, "doctor@medqc.com", "doctor123")
    resp = client.get("/api/system/db/status", headers=_auth_headers(doctor_token))
    assert resp.status_code == 403


def test_refresh_accepts_json_body(client):
    _, refresh_token = _login(client, "admin@medqc.com", "admin888")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("access_token")
    assert body.get("refresh_token") == refresh_token


def test_password_reset_token_is_one_time(client):
    email = f"reset-{uuid4().hex[:8]}@medqc.com"
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Reset User",
            "department": "测试科室",
            "password": "old-password-123",
        },
    )
    assert register_resp.status_code == 200, register_resp.text

    forgot_resp = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_resp.status_code == 200, forgot_resp.text
    reset_token = (forgot_resp.json().get("data") or {}).get("reset_token")
    assert reset_token, "non-production should return reset_token for controlled testing"

    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "new-password-123"},
    )
    assert reset_resp.status_code == 200, reset_resp.text

    # same token must not be reusable
    replay_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "another-password-123"},
    )
    assert replay_resp.status_code == 401, replay_resp.text

    # verify new password is effective
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "new-password-123"},
    )
    assert login_resp.status_code == 200, login_resp.text


def test_legacy_system_write_endpoints_retired(client):
    admin_token, _ = _login(client, "admin@medqc.com", "admin888")
    headers = _auth_headers(admin_token)

    put_resp = client.put(
        "/api/system/db/config",
        headers=headers,
        json={
            "remote_host": "127.0.0.1",
            "remote_port": "5432",
            "remote_database": "dhc-app",
            "remote_username": "tester",
        },
    )
    assert put_resp.status_code == 410, put_resp.text

    trigger_resp = client.post("/api/system/sync/trigger", headers=headers)
    assert trigger_resp.status_code == 410, trigger_resp.text
