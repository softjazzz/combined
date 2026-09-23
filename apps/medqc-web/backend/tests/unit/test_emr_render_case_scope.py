from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import emr_render
from app.services.bundles import emr_view


IDENTITY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-qc",
        "roles": ["qc_manager"],
        "role": "qc_manager",
    }
    with TestClient(app) as test_client:
        yield test_client


def test_render_never_reads_visit_only_qc_results_for_another_patient(client, monkeypatch):
    document = {
        "id": "DOC-1",
        "doc_key": "daily_course_record::DOC-1",
        "doc_type": "daily_course_record",
        "document_id": "DOC-1",
        "content": "P1 的病历正文",
        "execution_domain": "course",
        "group_key": "course",
    }
    load_document = Mock(return_value=document)
    legacy_client = Mock(side_effect=AssertionError("不得查询只按 visit_id 定位的旧质控结果"))
    monkeypatch.setattr(emr_render, "_load_document_from_bundle", load_document)
    monkeypatch.setattr(emr_render, "get_supabase", legacy_client, raising=False)

    response = client.get(
        "/api/v1/emr/V1/render",
        params={**IDENTITY, "execution_domain": "course", "doc_type": "daily_course_record", "doc_id": "DOC-1"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"] == "P1 的病历正文"
    assert data["defect_annotations"] == []
    assert data["annotations_status"] == "unavailable_unscoped_source"
    assert data["total_annotations"] == 0
    load_document.assert_called_once()
    legacy_client.assert_not_called()


@pytest.mark.parametrize("view", ["full", "summary"])
def test_saved_documents_loader_error_is_503(client, monkeypatch, view):
    def fail(**_kwargs):
        raise RuntimeError("private connection detail")

    loader_name = "load_bundle_documents" if view == "full" else "load_bundle_document_summaries"
    monkeypatch.setattr(emr_render, loader_name, fail)

    response = client.get("/api/v1/emr/V1/documents", params={**IDENTITY, "view": view})

    assert response.status_code == 503
    assert "private connection detail" not in response.text


def test_single_saved_document_loader_error_is_503(client, monkeypatch):
    monkeypatch.setattr(
        emr_render,
        "load_bundle_document",
        Mock(side_effect=RuntimeError("private connection detail")),
    )

    response = client.get(
        "/api/v1/emr/V1/render",
        params={**IDENTITY, "execution_domain": "course", "doc_type": "daily_course_record", "doc_id": "DOC-1"},
    )

    assert response.status_code == 503
    assert "private connection detail" not in response.text


def test_saved_bundle_true_empty_set_remains_200(client, monkeypatch):
    monkeypatch.setattr(
        emr_render,
        "load_bundle_documents",
        lambda **_kwargs: emr_render._build_empty_documents_payload("bundle_documents_empty"),
    )

    documents = client.get("/api/v1/emr/V1/documents", params=IDENTITY)
    render = client.get("/api/v1/emr/V1/render", params=IDENTITY)

    assert documents.status_code == 200
    assert documents.json()["data"]["empty_reason"] == "bundle_documents_empty"
    assert render.status_code == 200
    assert render.json()["data"]["annotations_status"] == "no_document"


def test_domain_read_error_is_not_projected_as_an_empty_document_list(client, monkeypatch):
    monkeypatch.setattr(
        emr_view,
        "load_domain_bundle",
        Mock(side_effect=RuntimeError("private database detail")),
    )

    response = client.get("/api/v1/emr/V1/documents", params=IDENTITY)

    assert response.status_code == 503
    assert "private database detail" not in response.text


@pytest.mark.parametrize("route", ["documents", "render"])
def test_incomplete_identity_cannot_read_saved_bundle(client, monkeypatch, route):
    full_loader = Mock(side_effect=AssertionError("不得读取不完整身份"))
    single_loader = Mock(side_effect=AssertionError("不得读取不完整身份"))
    monkeypatch.setattr(emr_render, "load_bundle_documents", full_loader)
    monkeypatch.setattr(emr_render, "load_bundle_document", single_loader)

    response = client.get(f"/api/v1/emr/V1/{route}", params={"patient_id": "P1"})

    assert response.status_code == 422
    full_loader.assert_not_called()
    single_loader.assert_not_called()
