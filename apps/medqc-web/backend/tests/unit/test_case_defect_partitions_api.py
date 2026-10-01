from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import qc_sichuan


def _client(monkeypatch, roles=("qc_manager",)):
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1", "roles": list(roles)}
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: object())
    return app, TestClient(app)


def _payload():
    return {
        "schema_version": "case-defect-partitions-v1",
        "institute_id": "H-1",
        "patient_id": "P-1",
        "visit_id": "V-1",
        "state": "ready",
        "job_id": "job-1",
        "confirmed": {
            "status": "ready",
            "source": "luxian_0609_canonical_projection",
            "rule_ids": ["LX0609-001"],
            "reason_code": None,
        },
        "veto": {
            "status": "no_standard",
            "source": "scoring_deductions",
            "rule_ids": [],
            "standard_name": None,
            "reason_code": None,
        },
        "core": {
            "status": "not_integrated",
            "source": "core_system_classification",
            "reason_code": "core_system_classification_missing",
        },
    }


def test_route_requires_same_privileged_roles_as_saved_result(monkeypatch):
    app, client = _client(monkeypatch, roles=("doctor",))
    try:
        response = client.get(
            "/api/v1/qc/sichuan/workspace/records/V-1/defect-partitions",
            params={"institute_id": "H-1", "patient_id": "P-1", "scene": "running"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_route_returns_owner_sources_and_no_standard_state(monkeypatch):
    app, client = _client(monkeypatch)
    monkeypatch.setattr(qc_sichuan, "build_case_defect_partitions", lambda **_kwargs: _payload())
    try:
        response = client.get(
            "/api/v1/qc/sichuan/workspace/records/V-1/defect-partitions",
            params={"institute_id": "H-1", "patient_id": "P-1", "scene": "running"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["confirmed"]["source"] == "luxian_0609_canonical_projection"
        assert data["veto"]["status"] == "no_standard"
        assert data["core"]["status"] == "not_integrated"
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_route_maps_not_found_and_masks_owner_errors(monkeypatch):
    app, client = _client(monkeypatch)
    try:
        not_found = _payload()
        not_found["state"] = "not_found"
        monkeypatch.setattr(
            qc_sichuan, "build_case_defect_partitions", lambda **_kwargs: not_found
        )
        response = client.get(
            "/api/v1/qc/sichuan/workspace/records/V-1/defect-partitions",
            params={"institute_id": "H-1", "patient_id": "P-1"},
        )
        assert response.status_code == 404

        def fail(**_kwargs):
            raise RuntimeError("postgresql://secret/patient-text")

        monkeypatch.setattr(qc_sichuan, "build_case_defect_partitions", fail)
        response = client.get(
            "/api/v1/qc/sichuan/workspace/records/V-1/defect-partitions",
            params={"institute_id": "H-1", "patient_id": "P-1"},
        )
        assert response.status_code == 503
        assert "secret" not in response.text
        assert "patient-text" not in response.text
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_route_treats_whitespace_identity_as_422(monkeypatch):
    app, client = _client(monkeypatch)
    try:
        response = client.get(
            "/api/v1/qc/sichuan/workspace/records/%20/defect-partitions",
            params={"institute_id": "H-1", "patient_id": "P-1"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        client.close()
