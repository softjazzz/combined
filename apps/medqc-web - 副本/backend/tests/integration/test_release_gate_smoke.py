import uuid

from fastapi.testclient import TestClient

from app.main import create_app


def _extract_auth_payload(payload: dict) -> dict:
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _login(client: TestClient, email: str, password: str) -> dict:
    unique_email = f"release-gate-{uuid.uuid4().hex[:12]}@example.com"
    target_email = email or unique_email
    target_password = password

    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": target_email,
            "password": target_password,
            "display_name": "Release Gate User",
            "role": "doctor",
            "department": "质控科",
        },
    )
    if register_resp.status_code not in (200, 400):
        raise AssertionError(register_resp.text)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": target_password},
    )
    assert login_resp.status_code == 200, login_resp.text
    return _extract_auth_payload(login_resp.json())


def test_release_gate_auth_smoke():
    app = create_app()
    client = TestClient(app)
    login_payload = _login(client, email="", password="StrongPass123!")
    assert isinstance(login_payload.get("access_token"), str) and login_payload["access_token"]
    assert isinstance(login_payload.get("refresh_token"), str) and login_payload["refresh_token"]
    headers = {"Authorization": f"Bearer {login_payload['access_token']}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200, me_resp.text

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh_resp.status_code == 200, refresh_resp.text
    refresh_payload = _extract_auth_payload(refresh_resp.json())
    assert isinstance(refresh_payload.get("access_token"), str) and refresh_payload["access_token"]


def test_release_gate_authz_reject_smoke():
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/medical-records/list")
    assert resp.status_code in (401, 403), resp.text


def test_release_gate_sync_trigger_permission_smoke():
    app = create_app()
    client = TestClient(app)
    payload = _login(client, email="", password="StrongPass123!")
    headers = {"Authorization": f"Bearer {payload['access_token']}"}

    resp = client.post("/api/v1/sync/trigger", headers=headers, json={"source": "mongo", "tier": "all"})
    assert resp.status_code == 403, resp.text


def test_release_gate_records_query_smoke():
    app = create_app()
    client = TestClient(app)

    admin_login = client.post("/api/v1/auth/login", json={"email": "admin@medqc.com", "password": "admin888"})
    assert admin_login.status_code == 200, admin_login.text
    payload = _extract_auth_payload(admin_login.json())
    headers = {"Authorization": f"Bearer {payload['access_token']}"}

    resp = client.get("/api/v1/records?page=1&page_size=5", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert isinstance((body.get("data") or {}).get("items"), list)


def test_release_gate_system_probe_smoke():
    app = create_app()
    client = TestClient(app)

    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200, health_resp.text

    ready_resp = client.get("/api/v1/ready")
    assert ready_resp.status_code in (200, 503), ready_resp.text
    ready_payload = ready_resp.json()
    assert ready_payload.get("success") is True
    assert "ready" in ready_payload.get("data", {})
