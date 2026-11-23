"""普通东华病例无持久 Bundle 时，目录和正文仍可只读查看。"""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.database import clinical_connection
from app.routers import emr_render as router


IDENTITY = dict(institute_id="H-SYN", patient_id="P-SYN", visit_id="V-SYN")
DOCUMENT = dict(id="D-SYN", document_id="D-SYN", doc_id="D-SYN",
                doc_key="admission_record::D-SYN", doc_type="admission_record",
                doc_name="合成入院记录", execution_domain="admission",
                content="仅用于离线验证的合成正文", has_content=True)


@pytest.fixture
def browse(monkeypatch):
    calls = []
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    monkeypatch.setattr(router.case_material, "current", lambda: None)

    def current(*, include_exam_evidence_coordinates=False, **identity):
        assert identity == IDENTITY
        calls.append(identity)
        return dict(documents=[deepcopy(DOCUMENT)], documents_tree=[], empty_reason="")

    monkeypatch.setattr(router, "load_current_documents", current)
    # 模拟服务器已有临床文书，但尚未生成任何持久 Bundle。
    monkeypatch.setattr(router, "load_bundle_document_summaries", lambda **_: dict(documents=[]))
    monkeypatch.setattr(router, "load_bundle_documents", lambda **_: dict(documents=[]))
    monkeypatch.setattr(router, "load_bundle_document", lambda **_: None)
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_current_user] = lambda: dict(id="test", roles=["qc_manager"])
    return TestClient(app), calls


@pytest.mark.parametrize("view", ["summary", "full"])
def test_no_saved_bundle_still_has_documents(browse, view):
    client, calls = browse
    response = client.get("/api/v1/emr/V-SYN/documents", params={**IDENTITY, "view": view})
    assert response.status_code == 200
    docs = response.json()["data"]["documents"]
    assert len(docs) == 1
    assert docs[0]["document_id"] == "D-SYN"
    assert bool(calls)
    if view == "summary":
        assert "content" not in docs[0]
    else:
        assert docs[0]["content"] == DOCUMENT["content"]


@pytest.mark.parametrize("domain", ["", "admission"])
def test_render_uses_same_current_document(browse, domain):
    client, calls = browse
    response = client.get("/api/v1/emr/V-SYN/render", params={**IDENTITY,
        "execution_domain": domain, "doc_type": "admission_record", "doc_id": "D-SYN"})
    assert response.status_code == 200
    assert response.json()["data"]["content"] == DOCUMENT["content"]
    assert calls


def test_read_failure_does_not_return_empty_or_saved_material(browse, monkeypatch):
    client, _ = browse
    def fail(**_):
        raise RuntimeError("synthetic-source-failure")
    monkeypatch.setattr(router, "load_current_documents", fail)
    for endpoint in ("documents", "render"):
        response = client.get(f"/api/v1/emr/V-SYN/{endpoint}", params={**IDENTITY,
            "view": "summary", "execution_domain": "admission", "doc_id": "D-SYN"})
        assert response.status_code == 503
        assert "synthetic-source-failure" not in response.text


def test_missing_identity_is_not_reported_as_no_documents(browse):
    client, calls = browse
    response = client.get("/api/v1/emr/V-SYN/documents", params={"view": "summary"})
    assert response.status_code == 422
    assert not calls


@pytest.mark.parametrize("domain", ["", "admission"])
def test_missing_requested_document_never_borrows_another(browse, domain):
    client, _ = browse
    response = client.get("/api/v1/emr/V-SYN/render", params={**IDENTITY,
        "execution_domain": domain, "doc_type": "admission_record", "doc_id": "MISSING"})
    assert response.status_code == 200
    assert response.json()["data"]["content"] == ""
    assert response.json()["data"]["empty_reason"] == "document_not_found"


def test_frozen_history_stays_frozen(browse, monkeypatch):
    client, calls = browse
    frozen = dict(identity=IDENTITY, documents=dict(documents=[{**DOCUMENT, "content": "历史合成正文"}]))
    monkeypatch.setattr(router.case_material, "current", lambda: frozen)
    # 身份保护仍必须被调用，测试不依赖快照其他持久化字段。
    checked = []
    monkeypatch.setattr(router.case_material, "identity_check", lambda value, identity: checked.append(identity))
    response = client.get("/api/v1/emr/V-SYN/documents", params={**IDENTITY, "view": "full"})
    assert response.status_code == 200
    assert response.json()["data"]["documents"][0]["content"] == "历史合成正文"
    assert checked == [tuple(IDENTITY.values())]
    assert not calls


def test_legacy_material_route_unchanged(browse, monkeypatch):
    client, calls = browse
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    response = client.get("/api/v1/emr/V-SYN/documents", params={**IDENTITY, "view": "summary"})
    assert response.status_code == 200
    assert response.json()["data"]["documents"] == []
    assert not calls


def test_open_current_clinical_surgery_requires_directory_version(browse, monkeypatch):
    client, _ = browse
    from app.database import clinical_connection
    from app.services.bundles import clinical_surgery_browse

    body = " " + ("合成手术经过。" * 100)[:492] + "\n"
    row = dict(document_id="SYN-5608526||1", document_title="合成手术记录",
               record_time=None, submit_time=None, surgery_process=body, cache_document_id=None,
               source_epoch="synthetic", source_key_hash="synthetic-key", target_key_hash="synthetic-key",
               generation=861733, mapping_hash="synthetic-mapping", activation=3,
               surgery_process_sha256="synthetic-body-hash")
    monkeypatch.setattr(clinical_connection, "source_binding", lambda: "synthetic-cdm")

    def read(identity, document_id=None):
        assert identity == tuple(IDENTITY.values())
        return ([row] if not document_id or document_id == row["document_id"] else []), "available"

    monkeypatch.setattr(clinical_surgery_browse, "_read", read)
    directory = client.get("/api/v1/emr/V-SYN/documents", params={
        **IDENTITY, "source_view": "current", "include_clinical_surgery": True,
    })
    assert directory.status_code == 200
    base, summary = directory.json()["data"]["documents"]
    assert base["content"] == DOCUMENT["content"]
    assert "content" not in summary and summary["length"] == 494
    params = {**IDENTITY, "source_view": "current", "doc_type": "surgery_record",
              "doc_id": summary["document_id"], "clinical_surgery_version": summary["version_id"]}
    response = client.get("/api/v1/emr/V-SYN/render", params=params)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"] == body and data["metadata"]["generation"] == 861733
    assert data["metadata"]["clinical_surgery_version"] == summary["version_id"]
    row["generation"] = 861734
    stale = client.get("/api/v1/emr/V-SYN/render", params=params)
    assert stale.status_code == 409 and "请刷新病历目录" in stale.text
    assert body not in stale.text
    wrong_visit = client.get("/api/v1/emr/wrong/render", params=params)
    assert wrong_visit.status_code == 422
