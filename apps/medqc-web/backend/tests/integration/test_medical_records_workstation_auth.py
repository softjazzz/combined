"""病历池全院视图只保留登录认证，不保留角色门禁。"""

import asyncio
from threading import Event

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

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


def test_workstation_route_rejects_unsupported_hospital_status(monkeypatch):
    client = _client_for_workstation_auth(
        monkeypatch,
        user={"id": "reader-1", "roles": ["read_only_observer"]},
    )

    # unknown 是独立 CDM 支持的状态。这里测试合同外的值。
    response = client.get("/api/medical-records/workstation?hospital_status=unsupported")

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


def test_slow_workstation_query_does_not_block_other_requests(monkeypatch):
    from app.database import clinical_connection
    from app.services.doctor_case_scope import get_doctor_case_scope

    entered, release, finished = Event(), Event(), Event()
    selection = {"id": "independent_cdm", "binding": "synthetic-workstation-cdm"}
    scope = object()

    def slow_query(**kwargs):
        assert clinical_connection.current_selection() == selection
        assert kwargs["case_scope"] is scope
        entered.set()
        release.wait(timeout=2)
        finished.set()
        return {"records": [], "total": 0}

    app = FastAPI()
    app.include_router(medical_records.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic", "roles": ["doctor"]}
    monkeypatch.setattr(medical_records_query, "get_doctor_case_scope", lambda _: scope)
    monkeypatch.setattr(medical_records_query, "get_workstation_data", slow_query)

    @app.get("/synthetic-ping")
    async def ping():
        return {"slow_request_finished": finished.is_set()}

    async def invoke():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://synthetic") as client:
            with clinical_connection.selected(selection):
                slow_request = asyncio.create_task(client.get("/api/medical-records/workstation"))
                try:
                    assert await asyncio.to_thread(entered.wait, 2)
                    response = await client.get("/synthetic-ping")
                    assert response.json() == {"slow_request_finished": False}
                finally:
                    release.set()
                    assert (await slow_request).status_code == 200

    asyncio.run(invoke())
