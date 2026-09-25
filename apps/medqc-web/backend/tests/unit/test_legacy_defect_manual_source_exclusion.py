"""旧缺陷入口不得读取或改写任务病历人工缺陷。"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import supabase_client
from app.core.security import get_current_user
from app.routers import defects
from app.services import defect_export_service


LEGACY_ROWS = [
    {"id": "old-null", "source_key": None, "severity": "warning", "category": "other", "status": "pending"},
    {"id": "old-other", "source_key": "legacy_import", "severity": "error", "category": "other", "status": "pending"},
    {"id": "manual", "source_key": "task_assigned_qc", "severity": "critical", "category": "manual", "status": "pending"},
]


class MemoryQuery:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.filters = []
        self.payload = None
        self.operation = "select"
        self.single_row = False
        self.offset = 0
        self.max_rows = None

    def select(self, _columns, count=None):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def neq_or_null(self, column, value):
        self.filters.append(("neq_or_null", column, value))
        self.db.exclusions += 1
        return self

    def gte(self, _column, _value):
        return self

    def lte(self, _column, _value):
        return self

    def or_(self, _value):
        return self

    def order(self, _column, desc=False):
        return self

    def range(self, start, end):
        self.offset = start
        self.max_rows = end - start + 1
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def single(self):
        self.single_row = True
        return self

    def run(self):
        if self.operation == "insert":
            assert self.table == "qc_defect_history"
            self.db.history.append(self.payload)
            return type("Response", (), {"data": [self.payload]})()

        assert self.table == "qc_defects"
        rows = [row for row in self.db.rows if all(
            row.get(column) == value if op == "eq" else row.get(column) != value
            for op, column, value in self.filters
        )]
        count = len(rows)
        if self.operation == "update":
            for row in rows:
                row.update(self.payload)
                self.db.updates.append(row["id"])
            return type("Response", (), {"data": rows})()

        rows = rows[self.offset:self.offset + self.max_rows if self.max_rows is not None else None]
        data = rows[0] if self.single_row and rows else (None if self.single_row else rows)
        return type("Response", (), {"data": data, "count": count})()


class MemoryDatabase:
    def __init__(self):
        self.rows = [row.copy() for row in LEGACY_ROWS]
        self.history = []
        self.updates = []
        self.exclusions = 0

    def table(self, name):
        return MemoryQuery(self, name)


def _client(monkeypatch, database):
    async def execute(query):
        return query.run()

    monkeypatch.setattr(defects, "get_supabase", lambda: database)
    monkeypatch.setattr(defects, "async_execute", execute)
    monkeypatch.setattr(supabase_client, "get_supabase", lambda: database)
    monkeypatch.setattr(supabase_client, "async_execute", execute)
    app = FastAPI()
    app.include_router(defects.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1", "user_id": "admin-1", "roles": ["admin"],
    }
    return TestClient(app)


def test_legacy_list_stats_and_export_keep_null_and_other_sources(monkeypatch):
    database = MemoryDatabase()
    client = _client(monkeypatch, database)

    listing = client.get("/api/v1/qc/defects")
    assert listing.status_code == 200, listing.text
    assert {row["id"] for row in listing.json()["data"]["items"]} == {"old-null", "old-other"}
    assert listing.json()["data"]["total"] == 2

    stats = client.get("/api/v1/qc/defects/stats")
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["total"] == 2
    assert stats.json()["data"]["by_severity"] == {"warning": 1, "error": 1}

    exported = asyncio.run(defect_export_service.DefectExportService()._fetch_defects({}, 100))
    assert {row["id"] for row in exported} == {"old-null", "old-other"}
    assert database.exclusions >= 3


@pytest.mark.parametrize(
    ("suffix", "payload"),
    [
        ("urge", {"message": "催办"}),
        ("cancel-urge", {"reason": "撤回"}),
        ("mark-remediated", {"remediation_note": "已整改"}),
        ("approve", {"comment": "通过"}),
        ("reject", {"reason": "退回"}),
    ],
)
def test_legacy_single_record_actions_cannot_touch_manual_source(monkeypatch, suffix, payload):
    database = MemoryDatabase()
    client = _client(monkeypatch, database)

    response = client.post(f"/api/v1/qc/defects/manual/{suffix}", json=payload)

    assert response.status_code in {404, 409}, response.text
    assert database.rows[2] == LEGACY_ROWS[2]
    assert database.updates == []
    assert database.history == []


def test_legacy_batch_action_skips_manual_source_but_updates_old_row(monkeypatch):
    database = MemoryDatabase()
    client = _client(monkeypatch, database)

    response = client.post(
        "/api/v1/qc/defects/batch-action",
        json={"defect_ids": ["old-null", "manual"], "action": "approve"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["success_count"] == 1
    assert data["fail_count"] == 1
    assert database.rows[0]["status"] == "approved"
    assert database.rows[2] == LEGACY_ROWS[2]
    assert database.updates == ["old-null"]
    assert [row["defect_id"] for row in database.history] == ["old-null"]


def test_legacy_single_record_action_still_updates_old_row(monkeypatch):
    database = MemoryDatabase()
    client = _client(monkeypatch, database)

    response = client.post("/api/v1/qc/defects/old-other/urge", json={"message": "请整改"})

    assert response.status_code == 200, response.text
    assert database.rows[1]["status"] == "urged"
    assert database.updates == ["old-other"]
    assert [row["defect_id"] for row in database.history] == ["old-other"]
