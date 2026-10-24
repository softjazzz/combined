"""只启动最小路由应用，验证启动版本冻结，不触发业务数据库初始化。"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.access_control import enforce_default_auth
from app.routers import runtime_build as endpoint
from app.services.qc_diagnostics import runtime_build as declaration


def _app():
    @asynccontextmanager
    async def lifespan(app):
        endpoint.initialize_runtime_build(app)
        yield

    app = FastAPI(lifespan=lifespan, dependencies=[Depends(enforce_default_auth)])
    app.include_router(endpoint.router)
    return app


def _write(path, *, version="20260909-180000", commit="a"):
    path.write_text(json.dumps({
        "schema_version": 1, "inventory_schema_version": 1,
        "build_id": f"medqc-web-customer-{version}", "git_commit": commit * 40,
    }), encoding="utf-8")


def test_runtime_build_is_public_safe_json_and_frozen_until_new_start(tmp_path, monkeypatch, caplog):
    path = tmp_path / "runtime_build.json"
    monkeypatch.setattr(declaration, "_BUILD_PATH", path)
    _write(path)
    calls = []
    original = endpoint.load_runtime_build

    def counted_load():
        calls.append(1)
        return original()

    monkeypatch.setattr(endpoint, "load_runtime_build", counted_load)
    caplog.set_level("INFO", logger=endpoint.__name__)
    old_app = _app()
    with TestClient(old_app) as old_client:
        response = old_client.get("/api/v1/runtime-build")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"].startswith("application/json")
        first = response.json()
        assert set(first) == {"available", "build_id", "git_commit", "started_at", "pid", "p0_acceptance"}
        assert first["p0_acceptance"]["loaded_equals_disk"] is True
        assert first["p0_acceptance"]["recovery_supported"] is True
        assert first["available"] is True
        assert first["git_commit"] == "a" * 40
        assert first["pid"] == os.getpid()
        assert datetime.fromisoformat(first["started_at"]).utcoffset() == timezone.utc.utcoffset(None)
        _write(path, version="20260909-190000", commit="b")
        endpoint.initialize_runtime_build(old_app)
        assert old_client.get("/api/v1/runtime-build").json() == first
        assert len(calls) == 1
        with TestClient(_app()) as new_client:
            new = new_client.get("/api/v1/runtime-build").json()
            assert new["build_id"] == "medqc-web-customer-20260909-190000"
            assert new["git_commit"] == "b" * 40
            assert old_client.get("/api/v1/runtime-build").json() == first
        assert len(calls) == 2
    assert "medqc-web-customer-20260909-180000" in caplog.text
    assert str(path) not in caplog.text


@pytest.mark.parametrize("contents", [None, "invalid-json"])
def test_unavailable_build_stays_unavailable_after_file_replacement(tmp_path, monkeypatch, contents):
    path = tmp_path / "runtime_build.json"
    monkeypatch.setattr(declaration, "_BUILD_PATH", path)
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    with TestClient(_app()) as client:
        response = client.get("/api/v1/runtime-build")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        first = response.json()
        assert first["available"] is False
        assert first["build_id"] is None and first["git_commit"] is None
        assert first["reason"] == "build_version_unavailable"
        assert set(first) == {"available", "build_id", "git_commit", "started_at", "pid", "reason"}
        _write(path)
        assert client.get("/api/v1/runtime-build").json() == first
