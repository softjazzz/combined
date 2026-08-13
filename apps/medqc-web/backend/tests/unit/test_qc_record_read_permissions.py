from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.security import get_current_user
from app.routers import emr_render, qc_sichuan


class _LatestResultWorkspace:
    def get_latest_luxian_0609_record_result(self, **_kwargs):
        return {
            "state": "ready",
            "record_ref": "safe-record-ref",
            "items": [],
        }


def _client_for_role(monkeypatch, role: str) -> tuple[TestClient, list[str]]:
    app = FastAPI()
    app.include_router(emr_render.router)
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": f"u-{role}",
        "email": f"{role}@example.test",
        "roles": [role],
        "role": role,
    }
    document_loads: list[str] = []

    def load_summaries(**_kwargs):
        document_loads.append("summary")
        return {"documents": [], "documents_tree": [], "empty_reason": ""}

    monkeypatch.setattr(
        emr_render,
        "_load_document_summaries_from_bundle",
        load_summaries,
    )
    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda: _LatestResultWorkspace(),
    )
    return TestClient(app), document_loads


@pytest.mark.parametrize("role", ["doctor", "reviewer"])
def test_ordinary_logged_in_user_cannot_read_arbitrary_record_documents_or_results(
    monkeypatch,
    role: str,
):
    client, document_loads = _client_for_role(monkeypatch, role)

    documents = client.get(
        "/api/v1/emr/V1/documents",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "view": "summary",
        },
    )
    latest_result = client.get(
        "/api/v1/qc/sichuan/workspace/records/V1/latest-result",
        params={"institute_id": "H1", "patient_id": "P1"},
    )

    assert documents.status_code == 403
    assert latest_result.status_code == 403
    assert document_loads == []


@pytest.mark.parametrize("role", ["admin", "qc_manager", "sync_admin", "super_admin"])
def test_authorized_quality_role_can_read_record_documents_and_latest_result(
    monkeypatch,
    role: str,
):
    client, document_loads = _client_for_role(monkeypatch, role)

    documents = client.get(
        "/api/v1/emr/V1/documents",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "view": "summary",
        },
    )
    latest_result = client.get(
        "/api/v1/qc/sichuan/workspace/records/V1/latest-result",
        params={"institute_id": "H1", "patient_id": "P1"},
    )

    assert documents.status_code == 200
    assert latest_result.status_code == 200
    assert document_loads == ["summary"]
