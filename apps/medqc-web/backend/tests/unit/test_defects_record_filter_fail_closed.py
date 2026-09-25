"""缺陷列表、导出和统计不得把裸 record_id 当作病例归属。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import defects
from app.services import defect_export_service


def _client():
    app = FastAPI()
    app.include_router(defects.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1",
        "roles": ["admin"],
    }
    return TestClient(app)


@pytest.mark.parametrize("route", ["", "/export", "/stats"])
@pytest.mark.parametrize("record_id", ["visit-1", "workflow::visit-1", "", "  "])
def test_record_filter_is_rejected_before_database_read(monkeypatch, route, record_id):
    calls = []
    monkeypatch.setattr(defects, "get_supabase", lambda: calls.append("database"))
    monkeypatch.setattr(
        defect_export_service,
        "DefectExportService",
        lambda: calls.append("export service"),
    )

    response = _client().get(f"/api/v1/qc/defects{route}", params={"record_id": record_id})

    assert response.status_code == 422
    assert response.json()["detail"] == "record_identity_unverifiable"
    assert calls == []


def test_global_defect_list_keeps_filters_and_pagination(monkeypatch):
    class Query:
        def __init__(self):
            self.calls = []

        def select(self, columns, count=None):
            self.calls.append(("select", columns, count))
            return self

        def eq(self, column, value):
            self.calls.append(("eq", column, value))
            return self

        def gte(self, column, value):
            self.calls.append(("gte", column, value))
            return self

        def lte(self, column, value):
            self.calls.append(("lte", column, value))
            return self

        def or_(self, value):
            self.calls.append(("or", value))
            return self

        def exclude_task_manual_source(self):
            self.calls.append(("exclude_task_manual_source",))
            return self

        def order(self, column, desc=False):
            self.calls.append(("order", column, desc))
            return self

        def range(self, start, end):
            self.calls.append(("range", start, end))
            return self

    class Database:
        def __init__(self):
            self.query = Query()
            self.tables = []

        def table(self, name):
            self.tables.append(name)
            return self.query

    database = Database()

    async def execute(query):
        assert query is database.query
        return type("Response", (), {"data": [{"id": "defect-2"}], "count": 5})()

    monkeypatch.setattr(defects, "get_supabase", lambda: database)
    monkeypatch.setattr(defects, "async_execute", execute)

    response = _client().get(
        "/api/v1/qc/defects",
        params={
            "department": "内科",
            "severity": "high",
            "category": "documentation",
            "status": "pending",
            "start_date": "2026-09-01",
            "end_date": "2026-09-23",
            "keyword": "病程",
            "page": 2,
            "page_size": 2,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "items": [{"id": "defect-2"}],
        "total": 5,
        "page": 2,
        "page_size": 2,
        "total_pages": 3,
    }
    assert database.tables == ["qc_defects"]
    assert database.query.calls == [
        ("select", "*", "exact"),
        ("exclude_task_manual_source",),
        ("eq", "department", "内科"),
        ("eq", "severity", "high"),
        ("eq", "category", "documentation"),
        ("eq", "status", "pending"),
        ("gte", "created_at", "2026-09-01"),
        ("lte", "created_at", "2026-09-23"),
        ("or", "rule_name.ilike.%病程%,description.ilike.%病程%"),
        ("order", "created_at", True),
        ("range", 2, 3),
    ]


def test_global_defect_stats_keeps_filters(monkeypatch):
    class Query:
        def __init__(self):
            self.calls = []

        def select(self, columns):
            self.calls.append(("select", columns))
            return self

        def eq(self, column, value):
            self.calls.append(("eq", column, value))
            return self

        def gte(self, column, value):
            self.calls.append(("gte", column, value))
            return self

        def lte(self, column, value):
            self.calls.append(("lte", column, value))
            return self

        def exclude_task_manual_source(self):
            self.calls.append(("exclude_task_manual_source",))
            return self

    query = Query()

    class Database:
        def table(self, name):
            assert name == "qc_defects"
            return query

    async def execute(received):
        assert received is query
        return type(
            "Response",
            (),
            {"data": [{"severity": "high", "category": "documentation", "status": "pending"}]},
        )()

    monkeypatch.setattr(defects, "get_supabase", Database)
    monkeypatch.setattr(defects, "async_execute", execute)

    response = _client().get(
        "/api/v1/qc/defects/stats",
        params={"department": "内科", "start_date": "2026-09-01", "end_date": "2026-09-23"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "total": 1,
        "by_severity": {"high": 1},
        "by_category": {"documentation": 1},
        "by_status": {"pending": 1},
    }
    assert query.calls == [
        ("select", "severity,category,status"),
        ("exclude_task_manual_source",),
        ("eq", "department", "内科"),
        ("gte", "created_at", "2026-09-01"),
        ("lte", "created_at", "2026-09-23"),
    ]


def test_global_defect_export_keeps_filters(monkeypatch, tmp_path):
    exported_file = tmp_path / "defects.csv"
    exported_file.write_bytes(b"id\ndefect-1\n")
    calls = []

    class ExportService:
        async def export(self, *, format, max_rows, filters):
            calls.append((format, max_rows, filters))
            return {
                "file_path": str(exported_file),
                "file_name": "defects.csv",
                "media_type": "text/csv",
                "total_rows": 1,
            }

    monkeypatch.setattr(defect_export_service, "DefectExportService", ExportService)
    monkeypatch.setattr(defects, "audit_event", lambda *_args, **_kwargs: None)

    response = _client().get(
        "/api/v1/qc/defects/export",
        params={"format": "csv", "max_rows": 3, "department": "内科"},
    )

    assert response.status_code == 200, response.text
    assert response.content == b"id\ndefect-1\n"
    assert calls == [("csv", 3, {"department": "内科"})]
