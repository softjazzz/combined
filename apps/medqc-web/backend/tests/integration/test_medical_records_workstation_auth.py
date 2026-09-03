"""病历池全院视图只保留登录认证，不保留角色门禁。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import medical_records, medical_records_query


def _client_for_workstation_auth(monkeypatch, user=None) -> TestClient:
    app = FastAPI()
    app.include_router(medical_records.router)
    monkeypatch.setattr(
        medical_records_query,
        "get_workstation_data",
        lambda **_kwargs: {"records": [], "departments": [], "total": 0},
    )
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_workstation_route_requires_login(monkeypatch):
    client = _client_for_workstation_auth(monkeypatch)

    response = client.get("/api/medical-records/workstation")

    assert response.status_code == 401


def test_workstation_route_allows_any_authenticated_role(monkeypatch):
    client = _client_for_workstation_auth(
        monkeypatch,
        user={"id": "reader-1", "roles": ["read_only_observer"]},
    )

    response = client.get("/api/medical-records/workstation")

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_workstation_route_rejects_unknown_hospital_status(monkeypatch):
    client = _client_for_workstation_auth(
        monkeypatch,
        user={"id": "reader-1", "roles": ["read_only_observer"]},
    )

    response = client.get("/api/medical-records/workstation?hospital_status=unknown")

    assert response.status_code == 422


def test_workstation_route_rejects_unknown_inpatient_sort(monkeypatch):
    client = _client_for_workstation_auth(
        monkeypatch,
        user={"id": "reader-1", "roles": ["read_only_observer"]},
    )

    response = client.get("/api/medical-records/workstation?inpatient_sort=priority")

    assert response.status_code == 422


def test_workstation_route_forwards_attending_physician_filter(monkeypatch):
    captured = {}
    app = FastAPI()
    app.include_router(medical_records.router)
    monkeypatch.setattr(
        medical_records_query,
        "get_workstation_data",
        lambda **kwargs: captured.update(kwargs) or {"records": [], "doctors": [], "total": 0},
    )
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "reader-1",
        "roles": ["read_only_observer"],
    }
    client = TestClient(app)

    response = client.get("/api/medical-records/workstation?doctor=%E5%BC%A0%E5%8C%BB%E5%B8%88")

    assert response.status_code == 200
    assert captured["doctor"] == "张医师"
