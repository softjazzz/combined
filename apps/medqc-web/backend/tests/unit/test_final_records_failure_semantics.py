"""终末列表的 CDM 数据源不可用时必须脱敏失败。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import records


def _client():
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1",
        "roles": ["admin"],
    }
    return TestClient(app)


@pytest.mark.parametrize("qc_status", [None, "unverified", "pending", "passed", "failed"])
def test_final_list_rejects_missing_database_without_memory_rows(monkeypatch, qc_status):
    monkeypatch.setattr(records, "SessionLocal", None)
    monkeypatch.setitem(
        records.medical_records_db,
        "private-fake-row",
        {
            "record_id": "private-fake-row",
            "patient_name": "private patient",
            "discharge_date": "2026-09-23",
        },
    )

    response = _client().get("/api/v1/records/final", params={"status": qc_status} if qc_status else {})

    assert response.status_code == 503
    assert "private" not in response.text
    assert "items" not in response.text


@pytest.mark.parametrize("failure_point", ["factory", "enter", "query", "http"])
@pytest.mark.parametrize("qc_status", [None, "unverified", "pending", "passed", "failed"])
def test_final_list_rejects_session_and_cdm_query_failures(monkeypatch, failure_point, qc_status):
    class BrokenSession:
        def __enter__(self):
            if failure_point == "enter":
                raise RuntimeError("private connection details")
            return self

        def __exit__(self, *_args):
            return False

        def query(self, *_args):
            if failure_point == "http":
                raise HTTPException(status_code=500, detail="private CDM SQL and patient details")
            raise RuntimeError("private CDM SQL and patient details")

    def session_factory():
        if failure_point == "factory":
            raise RuntimeError("private connection details")
        return BrokenSession()

    monkeypatch.setattr(records, "SessionLocal", session_factory)

    response = _client().get("/api/v1/records/final", params={"status": qc_status} if qc_status else {})

    assert response.status_code == 503
    assert "private" not in response.text
    assert "items" not in response.text


@pytest.mark.parametrize("qc_status", [None, "unverified", "pending", "passed", "failed"])
def test_final_list_rejects_cdm_count_failure_even_if_followup_query_works(monkeypatch, qc_status):
    class FallbackQuery:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def count(self):
            return 1

        def all(self):
            row = SimpleNamespace(
                visit_id="private-visit",
                visit_type="inpatient",
                name="private patient",
                discharge_dept_name="内科",
                admission_dept_name="",
                update_time="2026-09-23",
            )
            return [(row, "2026-09-23", "2026-09-23")]

    class Session:
        query_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def query(self, *_args):
            self.query_count += 1
            if self.query_count == 1:
                raise RuntimeError("private CDM SQL")
            return FallbackQuery()

        def rollback(self):
            pass

    monkeypatch.setattr(records, "SessionLocal", Session)

    response = _client().get("/api/v1/records/final", params={"status": qc_status} if qc_status else {})

    assert response.status_code == 503
    assert "private" not in response.text
    assert "items" not in response.text
