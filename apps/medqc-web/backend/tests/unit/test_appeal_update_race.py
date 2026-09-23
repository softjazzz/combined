"""申诉更新边界：归属、终态竞争与敏感输入不得被绕过或回显。"""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.security import get_current_user
from app.core.supabase_client import _Query
from app.routers import appeals


class _Response:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, client):
        self.client = client
        self.method = "select"
        self.filters = []

    def select(self, columns):
        self.client.selected_columns = columns
        return self

    def update(self, payload):
        self.method = "update"
        self.client.update_payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.method == "update":
            self.client.update_filters = list(self.filters)
            if isinstance(self.client.update_result, Exception):
                raise self.client.update_result
            return _Response(self.client.update_result)
        self.client.select_filters = list(self.filters)
        if isinstance(self.client.select_result, Exception):
            raise self.client.select_result
        return _Response(self.client.select_result)


class _FakeSupabase:
    def __init__(self, select_result, update_result=None):
        self.select_result = select_result
        self.update_result = update_result if update_result is not None else []
        self.tables = []
        self.selected_columns = None
        self.select_filters = []
        self.update_filters = []
        self.update_payload = None

    def table(self, name):
        self.tables.append(name)
        return _FakeQuery(self)


def _client_for(user):
    app = FastAPI()
    app.include_router(appeals.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _user(user_id="doctor-1"):
    return {"id": user_id, "roles": ["doctor"]}


def _pending(appellant_id="doctor-1"):
    return [{"id": "appeal-1", "appellant_id": appellant_id, "status": "pending"}]


def test_real_query_builds_qualified_compare_and_swap_update():
    captured = {}

    class _Result:
        def __iter__(self):
            return iter(())

    class _Session:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = params
            return _Result()

        def commit(self):
            captured["committed"] = True

    query = (
        _Query(None, "qc.qc_appeals")
        .update({"evidence": [{"kind": "record"}]})
        .eq("id", "appeal-1")
        .eq("appellant_id", "doctor-1")
        .eq("status", "pending")
    )

    query._exec_update(_Session())

    assert 'UPDATE "qc"."qc_appeals"' in captured["sql"]
    assert '"id" = :p0' in captured["sql"]
    assert '"appellant_id" = :p1' in captured["sql"]
    assert '"status" = :p2' in captured["sql"]
    assert json.loads(captured["params"]["set_evidence"]) == [{"kind": "record"}]
    assert captured["committed"] is True


def test_update_uses_qualified_table_and_all_compare_and_swap_filters(monkeypatch):
    db = _FakeSupabase(
        _pending(),
        [{"id": "appeal-1", "appellant_id": "doctor-1", "status": "pending", "reason": "足够长的新申诉理由说明"}],
    )
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client_for(_user()).put(
        "/api/v1/appeals/appeal-1",
        json={"reason": "足够长的新申诉理由说明", "evidence": [{"kind": "record"}]},
    )

    assert response.status_code == 200, response.text
    assert db.tables == ["qc.qc_appeals", "qc.qc_appeals"]
    assert db.selected_columns == "id,appellant_id,status"
    assert db.select_filters == [("id", "appeal-1")]
    assert db.update_filters == [
        ("id", "appeal-1"),
        ("appellant_id", "doctor-1"),
        ("status", "pending"),
    ]
    assert db.update_payload["evidence"] == [{"kind": "record"}]


@pytest.mark.parametrize(
    ("select_result", "expected"),
    [
        ([], 404),
        (_pending("doctor-2"), 403),
        ([{"id": "appeal-1", "appellant_id": "doctor-1", "status": "approved"}], 409),
    ],
)
def test_update_rejects_missing_foreign_or_terminal_appeal(monkeypatch, select_result, expected):
    db = _FakeSupabase(select_result)
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client_for(_user()).put(
        "/api/v1/appeals/appeal-1", json={"reason": "足够长的新申诉理由说明"}
    )

    assert response.status_code == expected
    assert db.update_payload is None


def test_update_returns_conflict_when_status_changes_after_read(monkeypatch):
    db = _FakeSupabase(_pending(), update_result=[])
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client_for(_user()).put(
        "/api/v1/appeals/appeal-1", json={"reason": "足够长的新申诉理由说明"}
    )

    assert response.status_code == 409
    assert "成功" not in response.text
    assert db.update_filters[-1] == ("status", "pending")


def test_update_requires_identity_and_nonempty_changes(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "get_supabase", lambda: calls.append(True))

    missing_identity = _client_for(_user("")).put(
        "/api/v1/appeals/appeal-1", json={"reason": "足够长的新申诉理由说明"}
    )
    assert missing_identity.status_code == 401
    assert calls == []

    db = _FakeSupabase(_pending())
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)
    empty = _client_for(_user()).put("/api/v1/appeals/appeal-1", json={})
    assert empty.status_code == 400
    assert db.update_payload is None


def test_update_database_failure_is_sanitized(monkeypatch, caplog):
    db = _FakeSupabase(RuntimeError("private SQL patient-name"))
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = _client_for(_user()).put(
            "/api/v1/appeals/appeal-1", json={"reason": "足够长的新申诉理由说明"}
        )

    assert response.status_code == 503
    assert "private SQL" not in response.text
    assert "private SQL" not in caplog.text


def test_update_client_initialization_failure_is_sanitized(monkeypatch, caplog):
    def fail():
        raise RuntimeError("private connection detail")

    monkeypatch.setattr(appeals, "get_supabase", fail)
    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = _client_for(_user()).put(
            "/api/v1/appeals/appeal-1", json={"reason": "足够长的新申诉理由说明"}
        )

    assert response.status_code == 503
    assert "private connection" not in response.text
    assert "private connection" not in caplog.text


def test_update_validation_does_not_echo_private_input(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "get_supabase", lambda: calls.append(True))

    response = _client_for(_user()).put(
        "/api/v1/appeals/appeal-1",
        json={"reason": {"patient_name": "private-name"}},
    )

    assert response.status_code == 422
    assert "private-name" not in response.text
    assert calls == []


def test_update_openapi_keeps_request_body_contract():
    app = FastAPI()
    app.include_router(appeals.router)

    schema = app.openapi()["paths"]["/api/v1/appeals/{appeal_id}"]["put"]["requestBody"]["content"]["application/json"]["schema"]

    assert set(schema["properties"]) == {"reason", "evidence", "priority", "notes"}
    assert schema.get("required", []) == []
