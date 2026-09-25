"""公开注册与 Bearer 令牌类型的最小权限边界，不启动完整应用或数据库。"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/nonexistent"

import pytest  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import security  # noqa: E402
from app.core.access_control import enforce_default_auth, is_public_path  # noqa: E402
from app.routers import auth  # noqa: E402


def _registration_payload(*, role: str | None = "doctor") -> dict:
    return {
        "email": "new-user@example.com",
        "password": "SamplePassword123!",
        "display_name": "测试用户",
        "department": "测试科室",
        "role": role,
    }


@pytest.fixture()
def registration_client(monkeypatch):
    create_calls: list[dict] = []
    hash_calls: list[str] = []

    def fake_create_user(**kwargs):
        create_calls.append(kwargs)
        return {
            "id": "new-user-1",
            "email": kwargs["email"],
            "username": kwargs.get("username"),
            "display_name": kwargs["display_name"],
            "department": kwargs["department"],
            "roles": [kwargs["role"]],
            "avatar": "",
            "phone": kwargs.get("phone"),
            "bio": kwargs.get("bio"),
            "created_at": "2026-09-25T00:00:00Z",
            "last_login": None,
        }

    def fake_hash(password: str) -> str:
        hash_calls.append(password)
        return "hashed-for-test"

    monkeypatch.setattr(auth, "create_user", fake_create_user)
    monkeypatch.setattr(auth, "get_password_hash", fake_hash)
    app = FastAPI()
    app.include_router(auth.router)
    with TestClient(app) as client:
        yield client, create_calls, hash_calls


@pytest.mark.parametrize("role", ["admin", "qc_manager", "qc_staff", "Admin", "", "doctor "])
def test_public_registration_rejects_role_grant_before_side_effect(registration_client, role):
    client, create_calls, hash_calls = registration_client
    assert is_public_path("/api/v1/auth/register")

    response = client.post("/api/v1/auth/register", json=_registration_payload(role=role))

    assert response.status_code == 403
    assert create_calls == []
    assert hash_calls == []


@pytest.mark.parametrize("role", ["doctor", None])
def test_public_registration_only_creates_doctor(registration_client, role):
    client, create_calls, hash_calls = registration_client
    payload = _registration_payload(role=role)
    if role is None:
        payload.pop("role")

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 200
    assert response.json()["data"]["roles"] == ["doctor"]
    assert len(create_calls) == 1
    assert create_calls[0]["role"] == "doctor"
    assert len(hash_calls) == 1


@pytest.mark.parametrize(
    ("token_type", "expected_status"),
    [(None, 200), ("access", 200), ("refresh", 401), ("password_reset", 401), ("unknown", 401)],
)
def test_protected_route_accepts_only_access_token(monkeypatch, token_type, expected_status):
    resolved: list[str] = []

    def resolve_user(subject: str):
        resolved.append(subject)
        return {"id": "user-1", "roles": ["doctor"]}

    monkeypatch.setattr(security, "resolve_user_by_subject", resolve_user)
    app = FastAPI(dependencies=[Depends(enforce_default_auth)])

    @app.get("/private")
    def private_route():
        return {"ok": True}

    claims = {"sub": "new-user@example.com"}
    if token_type is not None:
        claims["type"] = token_type
    token = security.create_access_token(claims)
    with TestClient(app) as client:
        response = client.get("/private", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == expected_status
    assert resolved == (["new-user@example.com"] if expected_status == 200 else [])
