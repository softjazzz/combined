"""新任务指定病例范围必须使用完整三坐标，旧请求保持原合同。"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import StatementError

from app.core.security import get_current_user
from app.core.supabase_client import _Query
from app.routers import tasks


class InsertQuery:
    def __init__(self, database):
        self.database = database
        self.payload = None

    def insert(self, payload):
        self.payload = dict(payload)
        return self

    def execute(self):
        self.database.calls += 1
        if self.database.fail:
            raise self.database.fail
        self.database.inserted.append(self.payload)
        if self.database.empty_result:
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[dict(self.payload)])


class Database:
    def __init__(self, *, fail=None, empty_result=False):
        self.fail = fail
        self.empty_result = empty_result
        self.calls = 0
        self.inserted = []

    def table(self, name):
        assert name == "qc_tasks"
        return InsertQuery(self)


def client_for(monkeypatch, database):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "creator-1",
        "display_name": "质控员",
        "roles": ["admin"],
    }
    monkeypatch.setattr(tasks, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "async_execute", execute)
    return TestClient(app)


def reference(institute="H-1", patient="P-1", visit="V-1"):
    return {"institute_id": institute, "patient_id": patient, "visit_id": visit}


def test_new_explicit_case_refs_are_stripped_and_persisted_in_order(monkeypatch):
    database = Database()
    client = client_for(monkeypatch, database)
    refs = [reference(" H-1 ", " P-1 ", " V-1 "), reference("H-2", "P-2", "V-2")]

    response = client.post(
        "/api/v1/tasks",
        json={"task_name": "指定病例", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": refs},
    )

    assert response.status_code == 200, response.text
    expected = [reference(), reference("H-2", "P-2", "V-2")]
    assert database.inserted[0]["record_refs"] == expected
    assert database.inserted[0]["record_ids"] == []
    assert response.json()["data"]["record_refs"] == expected
    assert database.calls == 1


def test_postgres_adapter_serializes_record_refs_as_json_without_rewriting_identity():
    refs = [reference(), reference("H-2", "P-2", "V-1")]
    serialized = _Query._serialize_params({"record_refs": refs})

    assert json.loads(serialized["record_refs"]) == refs


@pytest.mark.parametrize(
    "payload",
    [
        {"task_name": "混合范围", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference()], "record_ids": ["V-1"]},
        {"task_name": "缺场景", "record_refs": [reference()]},
        {"task_name": "重复范围", "scene": "running", "rule_set_key": "luxian_0609_qc_v1", "record_refs": [reference(), reference(" H-1 ", "P-1", "V-1")]},
        {"task_name": "缺机构", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [{"patient_id": "P-1", "visit_id": "V-1"}]},
        {"task_name": "空患者", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference(patient=" \t ")]},
        {"task_name": "多余字段", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [{**reference(), "record_id": "V-1"}]},
        {"task_name": "顶层错拼", "scene": "final", "rule_set_key": "sc_content_v1", "record_ref": [reference()]},
        {"task_name": "非法格式", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": ["H-1/P-1/V-1"]},
        {"task_name": "过长坐标", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference(institute="H" * 101)]},
    ],
)
def test_invalid_new_case_scope_is_422_before_database_access(monkeypatch, payload):
    database = Database()
    response = client_for(monkeypatch, database).post("/api/v1/tasks", json=payload)

    assert response.status_code == 422
    assert database.calls == 0
    assert database.inserted == []


@pytest.mark.parametrize(
    "payload",
    [
        {"task_name": "旧请求", "record_ids": ["legacy-1"]},
        {"task_name": "空新范围", "scene": "running", "rule_set_key": "luxian_0609_qc_v1", "record_refs": []},
        {"task_name": "默认范围"},
    ],
)
def test_legacy_or_empty_scope_does_not_write_new_column(monkeypatch, payload):
    database = Database()
    response = client_for(monkeypatch, database).post("/api/v1/tasks", json=payload)

    assert response.status_code == 200, response.text
    assert "record_refs" not in database.inserted[0]


def test_database_unavailable_is_not_fake_success(monkeypatch):
    response = client_for(monkeypatch, None).post(
        "/api/v1/tasks", json={"task_name": "指定病例", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference()]}
    )
    assert response.status_code == 503


def test_insert_failure_does_not_leak_database_details(monkeypatch):
    database = Database(fail=RuntimeError("private database connection detail"))
    response = client_for(monkeypatch, database).post(
        "/api/v1/tasks", json={"task_name": "指定病例", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference()]}
    )
    assert response.status_code == 500
    assert "private database" not in response.text


def test_insert_failure_does_not_log_case_coordinates(monkeypatch, caplog):
    ref = reference("H-PRIVATE", "P-PRIVATE", "V-PRIVATE")
    error = StatementError("insert failed", "INSERT INTO qc_tasks", {"record_refs": [ref]}, ValueError("db"))
    database = Database(fail=error)

    with caplog.at_level("ERROR", logger="app.routers.tasks"):
        response = client_for(monkeypatch, database).post(
            "/api/v1/tasks",
            json={"task_name": "指定病例", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [ref]},
        )

    assert response.status_code == 500
    assert "StatementError" in caplog.text
    assert all(secret not in caplog.text for secret in ref.values())


def test_empty_insert_result_is_not_reported_as_success(monkeypatch):
    database = Database(empty_result=True)
    response = client_for(monkeypatch, database).post(
        "/api/v1/tasks",
        json={"task_name": "指定病例", "scene": "final", "rule_set_key": "sc_content_v1", "record_refs": [reference()]},
    )

    assert response.status_code == 500
    assert database.calls == 1


def test_null_new_scope_is_invalid_not_an_empty_legacy_scope(monkeypatch):
    database = Database()
    response = client_for(monkeypatch, database).post(
        "/api/v1/tasks", json={"task_name": "空范围", "record_refs": None}
    )

    assert response.status_code == 422
    assert database.calls == 0
