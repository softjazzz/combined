"""扫码登录匿名入口的默认拒绝边界。"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/nonexistent"

import pytest  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.access_control import enforce_default_auth  # noqa: E402


_SESSION_ID = "123e4567-e89b-42d3-a456-426614174000"


@pytest.fixture()
def boundary_client():
    app = FastAPI(dependencies=[Depends(enforce_default_auth)])

    @app.api_route(
        "/{path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def boundary_probe(path: str):
        return {"path": path}

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/qr/sessions",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/status",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/cancel",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/exchange",
    ],
)
def test_qr_anonymous_endpoints_allow_post_only(boundary_client, path):
    response = boundary_client.post(path)

    assert response.status_code == 200


@pytest.mark.parametrize("method", ["get", "head", "put", "patch", "delete"])
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/qr/sessions",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/status",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/cancel",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/exchange",
    ],
)
def test_qr_anonymous_paths_reject_non_post_methods(boundary_client, method, path):
    response = getattr(boundary_client, method)(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/confirmation",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/confirm",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/reject",
    ],
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_qr_phone_confirmation_paths_remain_protected(boundary_client, method, path):
    response = getattr(boundary_client, method)(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/auth/qr/sessions/{'-' * 36}/status",
        "/api/v1/auth/qr/sessions/123e4567e89b42d3a456426614174000/status",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/status/",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/status/extra",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/status-confirm",
        f"/api/v1/auth/qr/sessions/{_SESSION_ID}/confirmation/status",
    ],
)
def test_qr_path_disguises_do_not_become_public(boundary_client, path):
    response = boundary_client.post(path, follow_redirects=False)

    assert response.status_code == 401


def test_existing_login_and_health_public_boundaries_remain_available(boundary_client):
    assert boundary_client.post("/api/v1/auth/login").status_code == 200
    assert boundary_client.get("/api/v1/health").status_code == 200
