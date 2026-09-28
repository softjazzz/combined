from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import records


@dataclass
class _Result:
    data: list[dict[str, Any]]
    count: int


class _Query:
    def __init__(self, database: "_Database"):
        self.database = database
        self.start = 0
        self.end = len(database.rows) - 1

    def select(self, *_args, **_kwargs):
        return self

    def order(self, _column, *, desc=False):
        assert desc is False
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self) -> _Result:
        if self.database.failed:
            raise RuntimeError("records source unavailable")
        rows = sorted(self.database.rows, key=lambda row: str(row.get("id") or ""))
        return _Result(
            data=[dict(row) for row in rows[self.start:self.end + 1]],
            count=len(rows),
        )


class _Database:
    def __init__(self, rows: list[dict[str, Any]], *, failed: bool = False):
        self.rows = rows
        self.failed = failed

    def table(self, _table_name: str) -> _Query:
        return _Query(self)


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database | None,
) -> TestClient:
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1",
        "email": "admin@example.com",
        "roles": ["admin"],
    }

    async def _execute(query: _Query) -> _Result:
        return query.execute()

    monkeypatch.setattr(records, "get_supabase", lambda: database)
    monkeypatch.setattr(records, "async_execute", _execute)
    return TestClient(app)


@pytest.mark.parametrize("database", [None, _Database([], failed=True)])
def test_source_unavailable_returns_503_without_memory_demo_records(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database | None,
):
    assert any(
        str(row.get("record_type") or "") in {"outpatient", "emergency"}
        for row in records.medical_records_db.values()
    ), "反证需要内存库中确实存在门急诊演示数据"
    client = _make_client(monkeypatch, database)

    response = client.get("/api/v1/records/outpatient-emergency")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"] == "门急诊病历数据源暂不可用，请稍后重试"
    assert payload.get("success") is not True
    assert "record-" not in response.text


def test_empty_source_returns_real_empty_success(monkeypatch: pytest.MonkeyPatch):
    client = _make_client(monkeypatch, _Database([]))

    response = client.get("/api/v1/records/outpatient-emergency")

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }


def test_source_recovers_after_transient_failure(monkeypatch: pytest.MonkeyPatch):
    database = _Database(
        [
            {
                "id": "outpatient-1",
                "patient_name": "测试患者",
                "record_type": "outpatient",
                "visit_date": "2026-09-22",
            }
        ],
        failed=True,
    )
    client = _make_client(monkeypatch, database)

    failed_response = client.get("/api/v1/records/outpatient-emergency")
    database.failed = False
    recovered_response = client.get("/api/v1/records/outpatient-emergency")

    assert failed_response.status_code == 503
    assert recovered_response.status_code == 200, recovered_response.text
    assert recovered_response.json()["data"]["total"] == 1
    assert recovered_response.json()["data"]["items"][0]["id"] == "outpatient-1"
