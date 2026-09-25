"""病历详情只读取身份明确的病历与其文书。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request

from app.routers import records


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.filter_key = None
        self.filter_value = None

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filter_key = key
        self.filter_value = value
        return self

    def order(self, *_args):
        return self

    def limit(self, *_args):
        return self


class Client:
    def __init__(self, rows=None, documents=None, failure=None):
        self.rows = rows or {}
        self.documents = documents or []
        self.failure = failure
        self.calls = []

    def table(self, name):
        self.calls.append(name)
        return Query(self, name)


def setup(monkeypatch, client):
    monkeypatch.setattr(records, "get_supabase", lambda: client)
    monkeypatch.setattr(
        records,
        "get_settings",
        lambda: SimpleNamespace(RECORDS_TABLE="medical_records", DOCUMENTS_TABLE="medical_documents"),
    )
    monkeypatch.setattr(records, "_load_bundle_payload_for_record", Mock(side_effect=AssertionError("bundle called")))
    monkeypatch.setattr(records, "_load_review_items_from_latest_batch", Mock(side_effect=AssertionError("review called")))

    async def execute(query):
        if client.failure == query.table_name:
            raise RuntimeError("private database error")
        if query.table_name == "medical_records":
            data = client.rows.get(query.filter_key, [])
        elif query.table_name == "medical_documents":
            data = client.documents
        else:
            raise AssertionError(f"unexpected table: {query.table_name}")
        return SimpleNamespace(data=data)

    monkeypatch.setattr(records, "async_execute", execute)


async def detail(record_id="external-1"):
    request = Request({"type": "http", "headers": []})
    return await records.get_record_qc_detail.__wrapped__(
        request, record_id, {"id": "test"}, "legacy_medical_records"
    )


@pytest.mark.asyncio
async def test_document_lookup_uses_primary_key_and_never_reads_single_key_qc(monkeypatch):
    client = Client(
        rows={"id": [{"id": "external-1", "record_id": "clinical-1", "defect_count": 7}]},
        documents=[{"id": "doc-1", "record_id": "external-1", "document_type": "入院记录", "content": "正文"}],
    )
    setup(monkeypatch, client)
    queries = []
    original_execute = records.async_execute

    async def track(query):
        queries.append((query.table_name, query.filter_key, query.filter_value))
        return await original_execute(query)

    monkeypatch.setattr(records, "async_execute", track)

    result = await detail()

    assert result["data"]["exists"] is True
    assert result["data"]["qc_data_status"] == "unavailable_identity_contract"
    assert "defect_count" not in result["data"]["record"]
    assert result["data"]["documents"]["raw_documents"][0]["id"] == "doc-1"
    assert queries == [
        ("medical_records", "id", "external-1"),
        ("medical_documents", "record_id", "external-1"),
    ]
    assert client.calls == ["medical_records", "medical_documents"]


@pytest.mark.asyncio
async def test_ambiguous_identity_returns_409_without_document_or_qc_read(monkeypatch):
    client = Client(
        rows={
            "id": [
                {"id": "external-1", "record_id": "clinical-1"},
                {"id": "external-1", "record_id": "clinical-1"},
            ],
        }
    )
    setup(monkeypatch, client)

    with pytest.raises(HTTPException) as exc:
        await detail()

    assert exc.value.status_code == 409
    assert client.calls == ["medical_records"]


@pytest.mark.asyncio
async def test_clinical_record_number_is_not_primary_key(monkeypatch):
    client = Client(
        rows={
            "id": [],
            "record_id": [
                {"id": "primary-1", "record_id": "external-1"},
                {"id": "primary-2", "record_id": "external-1"},
            ],
        }
    )
    setup(monkeypatch, client)

    with pytest.raises(HTTPException) as exc:
        await detail()

    assert exc.value.status_code == 404
    assert client.calls == ["medical_records"]


@pytest.mark.asyncio
async def test_missing_record_returns_404(monkeypatch):
    client = Client()
    setup(monkeypatch, client)

    with pytest.raises(HTTPException) as exc:
        await detail()

    assert exc.value.status_code == 404
    assert client.calls == ["medical_records"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["medical_records", "medical_documents"])
async def test_query_failure_returns_sanitized_503(monkeypatch, failure):
    client = Client(rows={"id": [{"id": "external-1"}], "record_id": []}, failure=failure)
    setup(monkeypatch, client)

    with pytest.raises(HTTPException) as exc:
        await detail()

    assert exc.value.status_code == 503
    assert "private database error" not in exc.value.detail


@pytest.mark.asyncio
async def test_missing_database_returns_503_without_memory_fallback(monkeypatch):
    setup(monkeypatch, None)

    with pytest.raises(HTTPException) as exc:
        await detail()

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_existing_record_with_no_documents_is_success_not_no_record(monkeypatch):
    client = Client(
        rows={
            "id": [
                {
                    "id": "external-1",
                    "record_id": "clinical-1",
                    "status": "passed",
                    "defect_count": 3,
                }
            ],
            "record_id": [],
        }
    )
    setup(monkeypatch, client)

    result = await detail()

    assert result["data"]["exists"] is True
    assert result["data"]["documents"]["raw_documents"] == []
    assert result["data"]["defects"] == []
    assert result["data"]["qc_data_status"] == "unavailable_identity_contract"
    assert "status" not in result["data"]["record"]
    assert "defect_count" not in result["data"]["record"]
