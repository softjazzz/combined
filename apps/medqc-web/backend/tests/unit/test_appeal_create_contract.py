"""创建申诉必须与审核读取同表，成功响应不得掩盖已提交写入。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import appeals


QC_RESULT_ID = "11111111-1111-4111-8111-111111111111"
RECORD_ID = "22222222-2222-4222-8222-222222222222"


class _Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.payload = None

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.db.error:
            raise self.db.error
        if self.payload is not None:
            self.db.inserted = self.payload
            return type("Result", (), {"data": [{"id": "appeal-1", **self.payload}]})()
        return type("Result", (), {"data": [{"id": "source-1"}]})()


class _DB:
    def __init__(self, error=None):
        self.error = error
        self.tables = []
        self.inserted = None

    def table(self, name):
        self.tables.append(name)
        return _Query(self, name)


def _client(user):
    app = FastAPI()
    app.include_router(appeals.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _payload():
    return {
        "qc_result_id": QC_RESULT_ID,
        "record_id": RECORD_ID,
        "appeal_type": "defect",
        "reason": "临床证据需要重新核对",
    }


def test_create_uses_canonical_tables_and_returns_committed_result(monkeypatch):
    db = _DB()
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    response = _client({"id": "doctor-1", "roles": ["doctor"]}).post(
        "/api/v1/appeals", json=_payload()
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["id"] == "appeal-1"
    assert db.tables == ["qc.qc_results", "cdm.medical_records", "qc.qc_appeals"]
    assert db.inserted["appellant_id"] == "doctor-1"


def test_create_requires_user_id_before_source_queries(monkeypatch):
    calls = []
    monkeypatch.setattr(appeals, "get_supabase", lambda: calls.append(True))

    response = _client({"roles": ["doctor"]}).post("/api/v1/appeals", json=_payload())

    assert response.status_code == 401
    assert calls == []


def test_create_database_error_does_not_expose_sql_or_patient_data(monkeypatch, caplog):
    db = _DB(error=RuntimeError("private patient SQL parameters"))
    monkeypatch.setattr(appeals, "get_supabase", lambda: db)

    with caplog.at_level("ERROR", logger="app.routers.appeals"):
        response = _client({"id": "doctor-1", "roles": ["doctor"]}).post(
            "/api/v1/appeals", json=_payload()
        )

    assert response.status_code == 503
    assert "private" not in response.text
    assert "private" not in caplog.text
