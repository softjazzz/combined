from __future__ import annotations

import pytest


def _assert_success_shell(body: dict) -> dict:
    assert body["success"] is True
    assert isinstance(body.get("trace_id"), str) and body["trace_id"]
    assert "data" in body
    return body["data"]


def _login(client, email: str, password: str) -> tuple[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    _assert_success_shell(payload)
    assert set(["access_token", "refresh_token", "token_type", "expires_in"]).issubset(payload.keys())
    return payload["access_token"], payload["refresh_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.unit
@pytest.mark.api
def test_me_marks_builtin_account_for_demo_presentation(client):
    access_token, _ = _login(client, "admin@medqc.com", "admin888")

    response = client.get("/api/v1/auth/me", headers=_headers(access_token))

    assert response.status_code == 200, response.text
    payload = _assert_success_shell(response.json())
    assert payload["email"] == "admin@medqc.com"
    assert payload["is_demo_account"] is True


@pytest.mark.unit
@pytest.mark.api
def test_refresh_contract_accepts_json_and_returns_stable_shape(client):
    _, refresh_token = _login(client, "admin@medqc.com", "admin888")
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200, refresh_resp.text

    body = refresh_resp.json()
    _assert_success_shell(body)
    assert isinstance(body.get("access_token"), str) and body["access_token"]
    assert body.get("refresh_token") == refresh_token
    assert body.get("token_type") == "bearer"
    assert isinstance(body.get("expires_in"), int) and body["expires_in"] > 0


@pytest.mark.unit
@pytest.mark.api
def test_sync_pg_config_contract_read_write(client, monkeypatch):
    access_token, _ = _login(client, "sync_admin@medqc.com", "sync888")
    monkeypatch.setenv("SYNC_PG_HOST_ALLOWLIST", "10.8.8.8")

    base_cfg = {
        "remote_host": "127.0.0.1",
        "remote_port": "5432",
        "remote_database": "dhc-app",
        "remote_username": "tester",
        "remote_password": "secret-pass",
        "remote_password_ref": "env:REMOTE_DB_PASSWORD",
        "default_institute_id": "MEDQC-TEST-HOSPITAL",
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr("app.services.etl_sync.load_db_config", lambda: dict(base_cfg))
    monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})

    def _fake_save_db_config(cfg: dict, runtime_password=None):
        captured["cfg"] = dict(cfg)
        captured["runtime_password"] = runtime_password
        return dict(cfg)

    monkeypatch.setattr("app.services.etl_sync.save_db_config", _fake_save_db_config)

    read_resp = client.get("/api/v1/sync/config/pg", headers=_headers(access_token))
    assert read_resp.status_code == 200, read_resp.text
    read_body = _assert_success_shell(read_resp.json())
    assert set(
        [
            "remote_host",
            "remote_port",
            "remote_database",
            "remote_username",
            "remote_password_set",
            "remote_password_display",
            "remote_password_ref",
        ]
    ).issubset(read_body.keys())
    assert "remote_password" not in read_body
    assert read_body["remote_password_set"] is True

    write_resp = client.put(
        "/api/v1/sync/config/pg",
        headers=_headers(access_token),
        json={
            "remote_host": "10.8.8.8",
            "remote_port": 5544,
            "remote_password_ref": "env:REMOTE_DB_PASSWORD",
            "remote_password": "",
        },
    )
    assert write_resp.status_code == 200, write_resp.text
    write_body = _assert_success_shell(write_resp.json())
    assert isinstance(write_body.get("connection"), dict)
    assert write_body["connection"].get("connected") is True
    assert write_body["config"]["remote_host"] == "10.8.8.8"
    assert write_body["config"]["remote_port"] == "5544"
    assert write_body["config"]["remote_password_set"] is True
    assert captured.get("runtime_password") is None


@pytest.mark.unit
@pytest.mark.api
def test_sync_trigger_forbidden_shape_for_non_admin(client):
    doctor_token, _ = _login(client, "doctor@medqc.com", "doctor123")
    resp = client.post("/api/v1/sync/trigger", headers=_headers(doctor_token), json={"source": "mongo", "tier": "all"})
    assert resp.status_code == 403, resp.text
    payload = resp.json()
    assert payload.get("success") is False
    assert payload.get("code") == "HTTP_403"
    assert isinstance(payload.get("trace_id"), str) and payload["trace_id"]
    detail = payload.get("detail") or payload.get("error") or payload.get("message")
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("detail")
    assert isinstance(detail, str) and detail


@pytest.mark.unit
@pytest.mark.api
def test_sichuan_rules_contract_returns_success_shell(client):
    access_token, _ = _login(client, "admin@medqc.com", "admin888")
    resp = client.get("/api/v1/qc/sichuan/rules", headers=_headers(access_token))
    assert resp.status_code == 200, resp.text
    payload = _assert_success_shell(resp.json())
    assert isinstance(payload.get("total_rules"), int)
    assert "source" in payload


@pytest.mark.unit
@pytest.mark.api
def test_sichuan_history_contract_returns_success_shell(client):
    access_token, _ = _login(client, "admin@medqc.com", "admin888")
    resp = client.get("/api/v1/qc/sichuan/results/history?page=1&page_size=10", headers=_headers(access_token))
    assert resp.status_code == 200, resp.text
    payload = _assert_success_shell(resp.json())
    assert set(["records", "total", "page", "page_size"]).issubset(payload.keys())


@pytest.mark.unit
@pytest.mark.api
def test_legacy_system_read_contract_returns_success_shell(client, monkeypatch):
    access_token, _ = _login(client, "sync_admin@medqc.com", "sync888")

    monkeypatch.setattr("app.services.etl_sync.test_local_connection", lambda: {"connected": True, "tables": 12})
    monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})

    resp = client.get("/api/system/db/status", headers=_headers(access_token))
    assert resp.status_code == 200, resp.text
    payload = _assert_success_shell(resp.json())
    assert isinstance(payload.get("local"), dict)
    assert isinstance(payload.get("remote"), dict)
