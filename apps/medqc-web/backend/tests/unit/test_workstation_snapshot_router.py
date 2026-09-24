import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers.workstation import router
from app.services.workstation.worklist_service import WorklistIdentityAmbiguousError


@pytest.fixture
def authenticated_client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-snapshot", "roles": ["admin"]}
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("workflow", "service_method"),
    [
        ("frontpage-qc", "get_frontpage_snapshot"),
        ("coding-qc", "get_coding_snapshot"),
        ("settlement-qc", "get_settlement_snapshot"),
    ],
)
def test_snapshot_ambiguous_identity_is_redacted_conflict(
    authenticated_client, monkeypatch, workflow, service_method
):
    def raise_ambiguous(_visit_id, *, recipient_id):
        assert recipient_id == "u-snapshot"
        raise WorklistIdentityAmbiguousError("hospital-1/patient-1 conflicts with hospital-2/patient-2")

    monkeypatch.setattr(
        f"app.routers.workstation.default_workstation_aggregation_service.{service_method}",
        raise_ambiguous,
    )

    response = authenticated_client.get(
        f"/api/v1/workstation/{workflow}/visit-1/snapshot",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "case_identity_ambiguous"
    assert "hospital-1" not in response.text
    assert "patient-1" not in response.text


@pytest.mark.parametrize(
    ("workflow", "service_method"),
    [
        ("frontpage-qc", "get_frontpage_snapshot"),
        ("coding-qc", "get_coding_snapshot"),
        ("settlement-qc", "get_settlement_snapshot"),
    ],
)
def test_snapshot_single_case_and_ordinary_validation_unchanged(
    authenticated_client, monkeypatch, workflow, service_method
):
    calls = []

    def get_single_case(visit_id, *, recipient_id):
        calls.append((visit_id, recipient_id))
        return {"visit_id": visit_id, "patient_id": "patient-1"}

    monkeypatch.setattr(
        f"app.routers.workstation.default_workstation_aggregation_service.{service_method}",
        get_single_case,
    )
    url = f"/api/v1/workstation/{workflow}/visit-1/snapshot"
    headers = {"Authorization": "Bearer test-token"}

    success = authenticated_client.get(url, headers=headers)
    assert success.status_code == 200
    assert success.json()["data"] == {"visit_id": "visit-1", "patient_id": "patient-1"}
    assert calls == [("visit-1", "u-snapshot")]

    def raise_validation(_visit_id, *, recipient_id):
        raise ValueError("invalid snapshot filter")

    monkeypatch.setattr(
        f"app.routers.workstation.default_workstation_aggregation_service.{service_method}",
        raise_validation,
    )
    invalid = authenticated_client.get(url, headers=headers)
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "invalid snapshot filter"
