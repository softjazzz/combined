from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDocumentDefinition
from app.services import document_definition_service as service
from app.services.document_definition_excel_service import ParsedDocumentDefinition


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCDocumentDefinition.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _entry(code="DOC-01", name="入院记录"):
    return ParsedDocumentDefinition(code, name, "住院", "模板正文")


def test_import_and_list_have_stable_total_and_pagination(sessions):
    created = service.import_document_definitions(
        actor="admin-1", definitions=(_entry("B", "乙"), _entry("A", "甲")),
    )
    assert created["imported_count"] == 2
    listed = service.list_document_definitions(page=1, page_size=1)
    assert listed["total"] == 2
    assert len(listed["items"]) == 1
    assert listed["items"][0]["import_batch_id"] == created["import_batch_id"]


def test_existing_code_rejects_entire_batch_without_overwrite(sessions):
    service.import_document_definitions(actor="admin-1", definitions=(_entry(),))
    with pytest.raises(service.DocumentDefinitionConflict) as caught:
        service.import_document_definitions(
            actor="admin-2", definitions=(_entry(), _entry("DOC-02", "出院记录")),
        )
    assert caught.value.codes == ["DOC-01"]
    listed = service.list_document_definitions(page=1, page_size=100)
    assert listed["total"] == 1
    assert listed["items"][0]["name"] == "入院记录"


def test_invalid_page_and_actor_fail_before_storage(sessions):
    with pytest.raises(service.DocumentDefinitionInvalid):
        service.list_document_definitions(page=0, page_size=20)
    with pytest.raises(service.DocumentDefinitionInvalid):
        service.import_document_definitions(actor=" ", definitions=(_entry(),))


def test_constraint_failure_mid_batch_rolls_back_every_row(sessions):
    invalid = ParsedDocumentDefinition("DOC-02", "   ", "住院", "模板正文")
    with pytest.raises(service.DocumentDefinitionUnavailable):
        service.import_document_definitions(
            actor="admin-1", definitions=(_entry("DOC-01"), invalid),
        )
    assert service.list_document_definitions(page=1, page_size=100)["total"] == 0


def test_name_search_is_case_insensitive_literal_and_keeps_filtered_total(sessions):
    service.import_document_definitions(actor="admin-1", definitions=(
        _entry("A", "Admission Note"),
        _entry("B", "入院记录"),
        _entry("C", "百分比%模板"),
        _entry("D", "下划线_模板"),
        _entry("E", r"路径\模板"),
        _entry("F", "普通文书"),
    ))
    assert [item["code"] for item in service.list_document_definitions(
        page=1, page_size=20, q="adMISSION",
    )["items"]] == ["A"]
    assert service.list_document_definitions(page=1, page_size=20, q=" 入院 ")["total"] == 1
    assert service.list_document_definitions(page=1, page_size=20, q="无匹配")["items"] == []
    assert service.list_document_definitions(page=1, page_size=20, q="%")["items"][0]["code"] == "C"
    assert service.list_document_definitions(page=1, page_size=20, q="_")["items"][0]["code"] == "D"
    assert service.list_document_definitions(page=1, page_size=20, q="\\")["items"][0]["code"] == "E"
    page = service.list_document_definitions(page=2, page_size=1, q="模板")
    assert page["total"] == 3 and len(page["items"]) == 1
    assert service.list_document_definitions(page=1, page_size=20, q="   ")["total"] == 6


@pytest.mark.parametrize("q", [123, "x" * 201])
def test_name_search_rejects_invalid_query_before_storage(sessions, q):
    with pytest.raises(service.DocumentDefinitionInvalid):
        service.list_document_definitions(page=1, page_size=20, q=q)
