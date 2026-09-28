"""申诉读取边界：审核池可见，普通申诉人只见本人。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.security import get_current_user
from app.routers import appeals


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.filters = []
        self.bounds = None
        self.order_by = None

    def select(self, columns, count=None):
        self.db.selects.append((self.table, columns, count))
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.filters.append((f"in:{column}", tuple(values)))
        return self

    def gte(self, column, value):
        self.filters.append((f">={column}", value))
        return self

    def lte(self, column, value):
        self.filters.append((f"<={column}", value))
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def execute(self):
        self.db.queries.append(self)
        if self.db.error:
            raise self.db.error
        rows = [dict(row) for row in self.db.rows[self.table]]
        for column, value in self.filters:
            if column.startswith("in:"):
                rows = [row for row in rows if row[column[3:]] in value]
            elif column.startswith(">="):
                rows = [row for row in rows if row[column[2:]] >= value]
            elif column.startswith("<="):
                rows = [row for row in rows if row[column[2:]] <= value]
            else:
                rows = [row for row in rows if row[column] == value]
        count = len(rows)
        if self.order_by:
            column, desc = self.order_by
            rows.sort(key=lambda row: row[column], reverse=desc)
        if self.bounds:
            start, end = self.bounds
            rows = rows[start : end + 1]
        return _Result(rows, count)


class _DB:
    def __init__(self, appeals_rows=(), reviews_rows=(), statistics_rows=(), error=None):
        self.rows = {
            "qc.qc_appeals": appeals_rows,
            "qc.qc_appeal_reviews": reviews_rows,
            "qc.qc_appeals_statistics": statistics_rows,
        }
        self.error = error
        self.tables = []
        self.selects = []
        self.queries = []

    def table(self, name):
        self.tables.append(name)
        return _Query(self, name)


def _client(user):
    app = FastAPI()
    app.include_router(appeals.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _user(user_id="doctor-1", role="doctor"):
    return {"id": user_id, "roles": [role]}


_APPEALS = [
    {"id": "a1", "appellant_id": "doctor-1", "created_at": "2026-09-20", "status": "pending"},
    {"id": "a2", "appellant_id": "doctor-2", "created_at": "2026-09-21", "status": "pending"},
    {"id": "a3", "appellant_id": "doctor-1", "created_at": "2026-09-22", "status": "approved"},
]


def test_appellant_list_filters_before_count_and_pagination(monkeypatch):
    db = _DB(appeals_rows=_APPEALS)
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client(_user()).get("/api/v1/appeals?page=2&page_size=1")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 2
    assert [row["id"] for row in response.json()["data"]["items"]] == ["a1"]
    assert db.queries[0].filters == [("appellant_id", "doctor-1")]
    assert db.queries[0].bounds == (1, 1)
    assert db.tables == ["qc.qc_appeals"]


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_reviewer_list_sees_shared_pool(monkeypatch, role):
    db = _DB(appeals_rows=_APPEALS)
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client(_user("reviewer-1", role)).get("/api/v1/appeals")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 3
    assert db.queries[0].filters == []


def test_reviewable_alias_filters_both_open_statuses_before_pagination(monkeypatch):
    rows = [
        *_APPEALS,
        {"id": "a4", "appellant_id": "doctor-2", "created_at": "2026-09-23", "status": "reviewing"},
    ]
    db = _DB(appeals_rows=rows)
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    denied = _client(_user()).get("/api/v1/appeals?status=reviewable")
    assert denied.status_code == 403

    response = _client(_user("reviewer-1", "qc_manager")).get(
        "/api/v1/appeals?status=reviewable&page=1&page_size=2"
    )
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 3
    assert [row["id"] for row in response.json()["data"]["items"]] == ["a4", "a2"]
    assert db.queries[-1].filters == [("in:status", ("pending", "reviewing"))]
    assert db.queries[-1].bounds == (0, 1)


@pytest.mark.parametrize("count", [None, -1, True, False, 1.0, "1"])
def test_list_rejects_missing_or_invalid_exact_count(monkeypatch, caplog, count):
    db = _DB(appeals_rows=_APPEALS)
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)
    original_execute = _Query.execute

    def execute_with_invalid_count(query):
        result = original_execute(query)
        result.count = count
        return result

    monkeypatch.setattr(_Query, "execute", execute_with_invalid_count)

    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = _client(_user("reviewer-1", "qc_manager")).get(
            "/api/v1/appeals?status=reviewable&page=1&page_size=1"
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "申诉列表服务暂不可用"
    assert "appeal_list_failed" in caplog.text
    assert str(count) not in response.text


def test_detail_scope_checks_owner_before_reviews(monkeypatch):
    db = _DB(appeals_rows=_APPEALS, reviews_rows=[{"appeal_id": "a2", "comment": "private review", "created_at": "2026-09-22"}])
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client(_user()).get("/api/v1/appeals/a2")

    assert response.status_code == 404
    assert "private review" not in response.text
    assert db.tables == ["qc.qc_appeals"]
    assert db.queries[0].filters == [("id", "a2"), ("appellant_id", "doctor-1")]


def test_owner_and_reviewer_detail_include_reviews(monkeypatch):
    db = _DB(appeals_rows=_APPEALS, reviews_rows=[{"appeal_id": "a1", "comment": "review", "created_at": "2026-09-22"}])
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    for user in (_user(), _user("reviewer-1", "qc_manager")):
        response = _client(user).get("/api/v1/appeals/a1")
        assert response.status_code == 200
        assert response.json()["data"]["reviews"][0]["comment"] == "review"
    assert "qc.qc_appeal_reviews" in db.tables


@pytest.mark.parametrize("path", ["", "/a1", "/statistics/summary"])
def test_read_requires_user_id_before_database(monkeypatch, path):
    calls = []
    monkeypatch.setattr(appeals, "get_supabase", lambda: calls.append(True))

    response = _client(_user("")).get(f"/api/v1/appeals{path}")

    assert response.status_code == 401
    assert calls == []


def test_statistics_reviewer_only_and_qualified_view(monkeypatch):
    db = _DB(statistics_rows=[{"status": "pending", "appeal_type": "other", "priority": "normal", "count": 2}])
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    denied = _client(_user()).get("/api/v1/appeals/statistics/summary")
    assert denied.status_code == 403
    assert db.tables == []

    allowed = _client(_user("reviewer-1", "qc_manager")).get("/api/v1/appeals/statistics/summary")
    assert allowed.status_code == 200
    assert allowed.json()["data"]["total"] == 2
    assert db.tables == ["qc.qc_appeals_statistics"]


@pytest.mark.parametrize("path", ["", "/a1", "/statistics/summary"])
def test_database_error_is_sanitized(monkeypatch, caplog, path):
    db = _DB(error=RuntimeError("private SQL patient-name"))
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = _client(_user("reviewer-1", "qc_manager")).get(f"/api/v1/appeals{path}")

    assert response.status_code == 503
    assert "private SQL" not in response.text
    assert "private SQL" not in caplog.text
