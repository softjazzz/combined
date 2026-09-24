from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import emr_render, qc_sichuan


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-qc",
        "roles": ["qc_manager"],
        "role": "qc_manager",
    }
    return TestClient(app)


def _params(view: str, source_view: str) -> dict[str, str]:
    return {
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "V1",
        "view": view,
        "source_view": source_view,
    }


@pytest.mark.parametrize(
    ("view", "source_view", "loader_name"),
    [
        ("full", "saved", "_load_documents_from_bundle"),
        ("summary", "saved", "_load_document_summaries_from_bundle"),
        ("full", "current", "load_current_documents"),
    ],
)
def test_documents_load_and_response_are_inside_read_guard(monkeypatch, view, source_view, loader_name):
    events: list[str] = []
    active = False

    @asynccontextmanager
    async def guarded():
        nonlocal active
        events.append("acquire")
        active = True
        try:
            yield
        finally:
            active = False
            events.append("release")

    def loader(**_kwargs):
        assert active
        events.append("load")
        return {"documents": [{"id": "D1"}], "documents_tree": []}

    monkeypatch.setattr(qc_sichuan, "_cdm_bundle_read_guard", guarded)
    monkeypatch.setattr(emr_render, loader_name, loader)
    response = _client().get("/api/v1/emr/V1/documents", params=_params(view, source_view))

    assert response.status_code == 200
    assert response.json()["data"]["documents"] == [{"id": "D1"}]
    assert events == ["acquire", "load", "release"]


@pytest.mark.parametrize(
    ("view", "source_view", "loader_name"),
    [
        ("full", "saved", "_load_documents_from_bundle"),
        ("summary", "saved", "_load_document_summaries_from_bundle"),
        ("full", "current", "load_current_documents"),
    ],
)
def test_documents_lock_failure_returns_503_without_loading(monkeypatch, view, source_view, loader_name):
    @asynccontextmanager
    async def unavailable():
        raise HTTPException(status_code=503, detail="质控数据同步中，请稍后重试")
        yield

    def reject_load(**_kwargs):
        raise AssertionError("锁失败后不得读取病历")

    monkeypatch.setattr(qc_sichuan, "_cdm_bundle_read_guard", unavailable)
    monkeypatch.setattr(emr_render, loader_name, reject_load)
    response = _client().get("/api/v1/emr/V1/documents", params=_params(view, source_view))

    assert response.status_code == 503
    assert "质控数据同步中" in response.json()["detail"]


def test_documents_loader_failure_releases_read_guard(monkeypatch):
    events: list[str] = []

    @asynccontextmanager
    async def guarded():
        events.append("acquire")
        try:
            yield
        finally:
            events.append("release")

    def failing_loader(**_kwargs):
        events.append("load")
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(qc_sichuan, "_cdm_bundle_read_guard", guarded)
    monkeypatch.setattr(emr_render, "load_current_documents", failing_loader)
    response = _client().get("/api/v1/emr/V1/documents", params=_params("full", "current"))

    assert response.status_code == 503
    assert events == ["acquire", "load", "release"]


@pytest.mark.parametrize(
    ("execution_domain", "loader_name"),
    [
        ("", "_load_documents_from_bundle"),
        ("course", "_load_document_from_bundle"),
    ],
)
def test_render_bundle_read_is_guarded(monkeypatch, execution_domain, loader_name):
    events: list[str] = []
    active = False

    @asynccontextmanager
    async def guarded():
        nonlocal active
        events.append("acquire")
        active = True
        try:
            yield
        finally:
            active = False
            events.append("release")

    def loader(**_kwargs):
        assert active
        events.append("load")
        selected = {"id": "D1", "doc_type": "daily_course_record", "content": "受控测试正文"}
        return selected if execution_domain else {"documents": [selected], "documents_tree": []}

    monkeypatch.setattr(qc_sichuan, "_cdm_bundle_read_guard", guarded)
    monkeypatch.setattr(emr_render, loader_name, loader)
    monkeypatch.setattr(emr_render, "build_render_view", lambda _selected: {"content": "受控测试正文"})
    response = _client().get(
        "/api/v1/emr/V1/render",
        params={**_params("full", "saved"), "execution_domain": execution_domain},
    )

    assert response.status_code == 200
    assert events == ["acquire", "load", "release"]


@pytest.mark.parametrize(
    ("execution_domain", "loader_name"),
    [
        ("", "_load_documents_from_bundle"),
        ("course", "_load_document_from_bundle"),
    ],
)
def test_render_lock_failure_does_not_read_bundle(monkeypatch, execution_domain, loader_name):
    @asynccontextmanager
    async def unavailable():
        raise HTTPException(status_code=503, detail="质控数据同步中，请稍后重试")
        yield

    def reject_load(**_kwargs):
        raise AssertionError("锁失败后不得读取 Bundle")

    monkeypatch.setattr(qc_sichuan, "_cdm_bundle_read_guard", unavailable)
    monkeypatch.setattr(emr_render, loader_name, reject_load)
    response = _client().get(
        "/api/v1/emr/V1/render",
        params={**_params("full", "saved"), "execution_domain": execution_domain},
    )

    assert response.status_code == 503
    assert "质控数据同步中" in response.json()["detail"]
