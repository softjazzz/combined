from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.routers import emr_render, qc_sichuan
from app.services import task_document_access


@pytest.fixture
def scoped_documents(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True),
        Column("status", String, nullable=False),
    )
    records = Table(
        "qc_task_records", metadata,
        Column("id", String, primary_key=True),
        Column("task_id", String, nullable=False),
        Column("record_id", String, nullable=False),
        Column("assignee_id", String),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(task_document_access, "SessionLocal", factory)
    with factory.begin() as session:
        session.execute(tasks.insert(), [
            {"id": "task-1", "status": "in_progress"},
            {"id": "task-2", "status": "cancelled"},
        ])
        session.execute(records.insert(), [
            {"id": "record-1", "task_id": "task-1", "record_id": "record-1", "assignee_id": "qc-1",
             "institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
            {"id": "record-2", "task_id": "task-1", "record_id": "record-2", "assignee_id": "qc-2",
             "institute_id": "H2", "patient_id": "P2", "visit_id": "V1"},
            {"id": "legacy", "task_id": "task-1", "record_id": "V1", "assignee_id": "qc-1",
             "institute_id": None, "patient_id": None, "visit_id": None},
            {"id": "record-3", "task_id": "task-2", "record_id": "record-3", "assignee_id": "qc-1",
             "institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
        ])

    actor = {"id": "qc-1", "roles": ["qc_staff"]}
    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: actor
    document = {"id": "DOC-1", "doc_type": "course", "document_id": "DOC-1", "content": "saved text"}
    list_loader = Mock(return_value={"documents": [document], "documents_tree": [], "empty_reason": ""})
    render_loader = Mock(return_value=document)
    monkeypatch.setattr(emr_render, "_load_documents_from_bundle", list_loader)
    monkeypatch.setattr(emr_render, "_load_document_from_bundle", render_loader)
    # CDM 共享读锁由 test_emr_documents_qc_data_lock 覆盖；此处只验证任务授权。
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: None)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, actor=actor, factory=factory, records=records,
                              list_loader=list_loader, render_loader=render_loader)
    engine.dispose()


def request_params(**overrides):
    return {
        "task_id": "task-1", "task_record_id": "record-1",
        "institute_id": "H1", "patient_id": "P1", "visit_id": "V1", **overrides,
    }


def test_assigned_qc_staff_reads_only_saved_documents_and_render(scoped_documents):
    docs = scoped_documents.client.get("/api/v1/emr/V1/documents", params=request_params())
    render = scoped_documents.client.get(
        "/api/v1/emr/V1/render",
        params=request_params(execution_domain="course", doc_type="course", doc_id="DOC-1"),
    )
    assert docs.status_code == 200
    assert render.status_code == 200
    assert render.json()["data"]["content"] == "saved text"
    scoped_documents.list_loader.assert_called_once()
    scoped_documents.render_loader.assert_called_once()


@pytest.mark.parametrize("params", [
    {"task_id": "task-other"},
    {"task_record_id": "record-2", "institute_id": "H2", "patient_id": "P2"},
    {"task_record_id": "record-2"},
    {"task_record_id": "legacy"},
    {"task_id": "task-2", "task_record_id": "record-3"},
    {"institute_id": "H2"},
    {"patient_id": "P2"},
    {"visit_id": "V2"},
    {"task_id": ""},
    {"source_view": "current"},
])
@pytest.mark.parametrize("path", ["documents", "render"])
def test_unassigned_or_unverified_case_cannot_read_documents(scoped_documents, params, path):
    response = scoped_documents.client.get(f"/api/v1/emr/V1/{path}", params=request_params(**params))
    assert response.status_code == 403
    scoped_documents.list_loader.assert_not_called()
    scoped_documents.render_loader.assert_not_called()


def test_assignment_revocation_takes_effect_before_document_load(scoped_documents):
    with scoped_documents.factory.begin() as session:
        session.execute(scoped_documents.records.update().where(
            scoped_documents.records.c.id == "record-1"
        ).values(assignee_id="qc-2"))
    response = scoped_documents.client.get("/api/v1/emr/V1/documents", params=request_params())
    assert response.status_code == 403
    scoped_documents.list_loader.assert_not_called()


def test_privileged_legacy_read_is_unchanged_and_doctor_still_forbidden(scoped_documents):
    scoped_documents.actor["roles"] = ["admin"]
    assert scoped_documents.client.get("/api/v1/emr/V1/documents", params={
        "institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
    }).status_code == 200
    scoped_documents.actor["roles"] = ["doctor"]
    assert scoped_documents.client.get("/api/v1/emr/V1/documents", params=request_params()).status_code == 403
    assert scoped_documents.list_loader.call_count == 1


def test_authorization_database_failure_is_503_not_empty_documents(scoped_documents, monkeypatch):
    monkeypatch.setattr(task_document_access, "SessionLocal", None)
    response = scoped_documents.client.get("/api/v1/emr/V1/documents", params=request_params())
    assert response.status_code == 503
    scoped_documents.list_loader.assert_not_called()
