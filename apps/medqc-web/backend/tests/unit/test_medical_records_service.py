"""medical_records 域服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table

from app.services.medical_records.detail_service import get_documents
from app.services.medical_records.errors import (
    MedicalRecordsNotFoundError,
    MedicalRecordsValidationError,
)
from app.services.medical_records.export_service import get_table_data
from app.services.medical_records.maintenance_service import save_ai_frontpage_draft
from app.services.medical_records.query_service import list_medical_records


class FakeRepo:
    def __init__(self):
        self.calls = []

    def list_patients(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "total": 1,
            "items": [{"id": "v1"}],
            "page": kwargs.get("page", 1),
            "page_size": kwargs.get("page_size", 20),
        }


class FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSessionDocuments:
    def __init__(self, responses):
        self.responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeQuery:
    def __init__(self, record=None):
        self.record = record

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self.record


class FakeSessionDraft:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = None
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self, *_args, **_kwargs):
        return FakeQuery(self.existing)

    def add(self, record):
        self.added = record

    def commit(self):
        self.committed = True


class FakeSessionTable:
    def __init__(self, count_total, rows):
        self.count_total = count_total
        self.rows = rows
        self.step = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        self.step += 1
        if self.step == 1:
            return SimpleNamespace(scalar=lambda: self.count_total)
        return SimpleNamespace(fetchall=lambda: self.rows)


def test_list_medical_records_delegates_to_repository(monkeypatch):
    repo = FakeRepo()
    monkeypatch.setattr("app.services.medical_records.query_service.get_repository", lambda: repo)

    result = list_medical_records(dept="心内科", keyword="张三", page=2, page_size=10)

    assert result["items"][0]["id"] == "v1"
    assert repo.calls[0]["dept"] == "心内科"
    assert repo.calls[0]["keyword"] == "张三"
    assert repo.calls[0]["page"] == 2
    assert repo.calls[0]["page_size"] == 10


def test_get_documents_concat_mode_handles_missing_table():
    responses = [
        FakeRowsResult([{"record_content": "入院内容"}]),
        RuntimeError("missing table"),
    ]
    for _ in range(10):
        responses.append(FakeRowsResult([]))

    session_factory = lambda: FakeSessionDocuments(responses)
    result = get_documents("VISIT-1", mode="concat", session_factory=session_factory)

    assert result["mode"] == "concat"
    assert result["document_count"] == 1
    assert "入院记录" in result["text"]
    assert "入院内容" in result["text"]


def test_save_ai_frontpage_draft_validation_error():
    with pytest.raises(MedicalRecordsValidationError):
        save_ai_frontpage_draft({"visit_id": "V-1", "draft_json": {"a": 1}})


def test_save_ai_frontpage_draft_create():
    fake_session = FakeSessionDraft(existing=None)
    result = save_ai_frontpage_draft(
        {
            "patient_id": "P-1",
            "visit_id": "V-1",
            "draft_json": {"name": "张三"},
            "institute_id": "I-1",
        },
        session_factory=lambda: fake_session,
        ensure_table=lambda: None,
    )

    assert result == {"action": "created", "visit_id": "V-1"}
    assert fake_session.committed is True
    assert fake_session.added is not None
    assert fake_session.added.visit_id == "V-1"


def test_get_table_data_unknown_table():
    metadata = MetaData()
    Table("known_table", metadata, Column("id", Integer), Column("name", String))

    with pytest.raises(MedicalRecordsNotFoundError):
        get_table_data("missing_table", metadata=metadata, session_factory=lambda: FakeSessionTable(0, []))

