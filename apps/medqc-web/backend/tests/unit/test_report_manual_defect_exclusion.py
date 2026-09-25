"""正式报表分类统计不包含尚未审核的任务人工缺陷。"""

from types import SimpleNamespace

import pytest

from app.routers import reports


class _DefectQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def neq_or_null(self, column, value):
        self.calls.append(("neq_or_null", column, value))
        self.rows = [row for row in self.rows if row.get(column) is None or row[column] != value]
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        self.rows = self.rows[:value]
        return self


class _Database:
    def __init__(self, rows):
        self.query = _DefectQuery(rows)

    def table(self, name):
        assert name == "qc_defects"
        return self.query


@pytest.mark.asyncio
async def test_top_categories_excludes_task_manual_defects_before_scan_limit(monkeypatch):
    database = _Database(
        [
            {"category": "人工", "source_key": "task_assigned_qc"},
            {"category": "病案", "source_key": None},
            {"category": "时效", "source_key": "legacy_import"},
            {"category": "病案", "source_key": "verified_qc"},
            {"category": "人工", "source_key": "task_assigned_qc"},
        ]
    )

    async def execute(query):
        return SimpleNamespace(data=query.rows)

    monkeypatch.setattr(reports, "async_execute", execute)
    monkeypatch.setattr(reports, "REPORT_SCAN_LIMIT", 3)

    result = await reports._fetch_top_categories(database)

    assert result == [
        {"category": "病案", "issue_count": 2},
        {"category": "时效", "issue_count": 1},
    ]
    assert database.query.calls == [
        ("select", "category"),
        ("neq_or_null", "source_key", "task_assigned_qc"),
        ("limit", 3),
    ]


@pytest.mark.asyncio
async def test_top_categories_query_failure_keeps_empty_result(monkeypatch):
    async def fail(_query):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(reports, "async_execute", fail)

    assert await reports._fetch_top_categories(_Database([])) == []
