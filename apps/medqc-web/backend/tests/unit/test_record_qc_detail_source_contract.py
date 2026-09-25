"""旧病历详情必须由显式来源和 medical_records 主键定位。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import records


class Query:
    def __init__(self, table_name):
        self.table_name = table_name
        self.key = None
        self.value = None

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.key = key
        self.value = value
        return self

    def order(self, *_args):
        return self

    def limit(self, *_args):
        return self


class Database:
    def __init__(self, records_by_id=None, documents=None, fail_table=None):
        self.records_by_id = records_by_id or {}
        self.documents = documents or []
        self.fail_table = fail_table
        self.queries = []

    def table(self, name):
        return Query(name)


def _client(monkeypatch, database):
    monkeypatch.setattr(records, "get_supabase", lambda: database)
    monkeypatch.setattr(
        records,
        "get_settings",
        lambda: SimpleNamespace(RECORDS_TABLE="medical_records", DOCUMENTS_TABLE="medical_documents"),
    )

    async def execute(query):
        database.queries.append((query.table_name, query.key, query.value))
        if query.table_name == database.fail_table:
            raise RuntimeError("private database exception")
        if query.table_name == "medical_records":
            assert query.key == "id"
            data = database.records_by_id.get(query.value, [])
        elif query.table_name == "medical_documents":
            assert query.key == "record_id"
            data = [row for row in database.documents if row["record_id"] == query.value]
        else:
            raise AssertionError(f"unexpected table: {query.table_name}")
        return SimpleNamespace(data=data)

    monkeypatch.setattr(records, "async_execute", execute)
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "roles": ["admin"]}
    return TestClient(app)


@pytest.mark.parametrize("source", [None, "", "cdm", "modern_qc_result"])
def test_missing_or_other_source_rejected_before_database_read(monkeypatch, source):
    calls = []
    monkeypatch.setattr(records, "get_supabase", lambda: calls.append("database"))
    client = TestClient(FastAPI())
    client.app.include_router(records.router)
    client.app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "roles": ["admin"]}

    params = {} if source is None else {"source": source}
    response = client.get("/api/v1/records/legacy-1/qc-detail", params=params)

    assert response.status_code == 422
    assert calls == []


def test_primary_key_reads_only_its_own_documents(monkeypatch):
    database = Database(
        records_by_id={
            "legacy-1": [{
                "id": "legacy-1",
                "record_id": "shared-visit",
                "patient_name": "A",
                "status": "failed",
                "qc_status": "failed",
                "score": 56,
                "overall_score": 56,
                "scoring_standard": "old-rule-set",
                "defect_count": 8,
            }],
            "legacy-2": [{"id": "legacy-2", "record_id": "shared-visit", "patient_name": "B"}],
        },
        documents=[
            {"id": "doc-a", "record_id": "legacy-1", "document_type": "admission_record", "content": "A"},
            {"id": "doc-b", "record_id": "legacy-2", "document_type": "admission_record", "content": "B"},
        ],
    )
    client = _client(monkeypatch, database)

    response = client.get("/api/v1/records/legacy-1/qc-detail", params={"source": "legacy_medical_records"})
    other_response = client.get("/api/v1/records/legacy-2/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code == 200, response.text
    assert other_response.status_code == 200, other_response.text
    payload = response.json()["data"]
    other_payload = other_response.json()["data"]
    assert payload["record"]["id"] == "legacy-1"
    assert payload["record"]["source"] == "legacy_medical_records"
    assert payload["record"]["patient_name"] == "A"
    assert payload["qc_data_status"] == "unavailable_identity_contract"
    assert not ({"status", "qc_status", "score", "overall_score", "scoring_standard", "defect_count"} & payload["record"].keys())
    assert other_payload["record"]["id"] == "legacy-2"
    assert [doc["id"] for doc in payload["documents"]["raw_documents"]] == ["doc-a"]
    assert [doc["id"] for doc in other_payload["documents"]["raw_documents"]] == ["doc-b"]
    assert database.queries == [
        ("medical_records", "id", "legacy-1"),
        ("medical_documents", "record_id", "legacy-1"),
        ("medical_records", "id", "legacy-2"),
        ("medical_documents", "record_id", "legacy-2"),
    ]


def test_matching_clinical_record_number_is_not_a_legacy_primary_key(monkeypatch):
    database = Database(
        records_by_id={"legacy-1": [{"id": "legacy-1", "record_id": "shared-visit"}]},
        documents=[{"id": "doc-a", "record_id": "legacy-1", "content": "A"}],
    )
    client = _client(monkeypatch, database)

    response = client.get("/api/v1/records/shared-visit/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code == 404
    assert database.queries == [("medical_records", "id", "shared-visit")]


def test_duplicate_primary_key_rows_fail_without_document_read(monkeypatch):
    row = {"id": "legacy-1", "record_id": "shared-visit"}
    database = Database(records_by_id={"legacy-1": [row, row]})
    client = _client(monkeypatch, database)

    response = client.get("/api/v1/records/legacy-1/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code == 409
    assert database.queries == [("medical_records", "id", "legacy-1")]


@pytest.mark.parametrize("failure", ["medical_records", "medical_documents"])
def test_database_failure_is_sanitized(monkeypatch, failure):
    database = Database(
        records_by_id={"legacy-1": [{"id": "legacy-1"}]},
        fail_table=failure,
    )
    client = _client(monkeypatch, database)

    response = client.get("/api/v1/records/legacy-1/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code == 503
    assert "private database exception" not in response.text


def test_malformed_record_identity_fails_closed(monkeypatch):
    database = Database(records_by_id={"legacy-1": [{"id": "other-primary-key"}]})
    client = _client(monkeypatch, database)

    response = client.get("/api/v1/records/legacy-1/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code in (409, 503)
    assert "other-primary-key" not in response.text
    assert database.queries == [("medical_records", "id", "legacy-1")]


def test_misconfigured_legacy_source_table_fails_before_query(monkeypatch):
    database = Database(records_by_id={"legacy-1": [{"id": "legacy-1"}]})
    client = _client(monkeypatch, database)
    monkeypatch.setattr(
        records,
        "get_settings",
        lambda: SimpleNamespace(RECORDS_TABLE="other_records", DOCUMENTS_TABLE="medical_documents"),
    )

    response = client.get("/api/v1/records/legacy-1/qc-detail", params={"source": "legacy_medical_records"})

    assert response.status_code == 503
    assert database.queries == []
