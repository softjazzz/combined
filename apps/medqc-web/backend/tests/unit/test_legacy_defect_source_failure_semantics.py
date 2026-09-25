"""旧全院缺陷接口遇到来源探测故障时须失败关闭。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import defects, reports


SENSITIVE_ERROR = "probe failed: SELECT patient_secret FROM qc_defects"


class _Query:
    def __init__(self, table_name):
        self.table_name = table_name

    def __getattr__(self, _name):
        return lambda *args, **kwargs: self


class _Database:
    def table(self, table_name):
        return _Query(table_name)


def _defects_client():
    app = FastAPI()
    app.include_router(defects.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "roles": ["admin"]}
    return TestClient(app)


def _reports_client():
    app = FastAPI()
    app.include_router(reports.router)
    return TestClient(app)


@pytest.mark.parametrize("route", ["", "/stats"])
def test_global_defect_probe_failure_is_redacted_503(monkeypatch, route):
    async def fail_probe(query):
        assert query.table_name == "qc_defects"
        raise RuntimeError(SENSITIVE_ERROR)

    monkeypatch.setattr(defects, "get_supabase", _Database)
    monkeypatch.setattr(defects, "async_execute", fail_probe)

    response = _defects_client().get(f"/api/v1/qc/defects{route}")

    assert response.status_code == 503
    assert SENSITIVE_ERROR not in response.text
    assert "patient_secret" not in response.text


def test_qc_summary_probe_failure_does_not_cache_success(monkeypatch):
    calls = []

    async def execute(query):
        calls.append(query.table_name)
        if query.table_name == "qc_defects":
            raise RuntimeError(SENSITIVE_ERROR)
        return SimpleNamespace(data=[])

    monkeypatch.setattr(reports, "get_supabase", _Database)
    monkeypatch.setattr(reports, "async_execute", execute)
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE", None)
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE_TS", 0.0)

    response = _reports_client().get("/api/v1/reports/qc/summary")

    assert response.status_code == 503
    assert SENSITIVE_ERROR not in response.text
    assert "patient_secret" not in response.text
    assert calls == ["qc_statistics_view", "qc_rules", "qc_defects"]
    assert reports._QC_SUMMARY_CACHE is None
    assert reports._QC_SUMMARY_CACHE_TS == 0.0


def test_qc_summary_empty_defect_set_remains_successful(monkeypatch):
    calls = []

    async def execute(query):
        calls.append(query.table_name)
        return SimpleNamespace(data=[])

    monkeypatch.setattr(reports, "get_supabase", _Database)
    monkeypatch.setattr(reports, "async_execute", execute)
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE", None)
    monkeypatch.setattr(reports, "_QC_SUMMARY_CACHE_TS", 0.0)
    monkeypatch.setattr(
        reports,
        "SichuanQCService",
        lambda: SimpleNamespace(stats=lambda: {"success_rate": 0.0, "avg_api_time": 0.0}),
    )

    response = _reports_client().get("/api/v1/reports/qc/summary")

    assert response.status_code == 200
    assert response.json()["data"]["top_categories"] == []
    assert calls == ["qc_statistics_view", "qc_rules", "qc_defects"]
    assert reports._QC_SUMMARY_CACHE is not None
