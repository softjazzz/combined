from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.routers import qc_sichuan


SHARED_JOB_ID = "shared-job"
SHARED_POOL_ID = "shared-pool"
SHARED_JOB_OWNER = "admin-001"


def _workspace_job(
    *,
    job_id: str = SHARED_JOB_ID,
    created_by: str = SHARED_JOB_OWNER,
    pool_id: str = SHARED_POOL_ID,
    source: str = "manual_problem_sample_pool",
    workspace: bool = True,
    rule_set_key: str = "luxian_0609_qc_v1",
) -> dict[str, Any]:
    return {
        "id": job_id,
        "draft_id": "customer-rule-library" if workspace else "private-custom-draft",
        "rule_code": "CUSTOMER-RULE-LIBRARY",
        "rule_name": "客户样本质控",
        "status": "completed",
        "created_by": created_by,
        "filters": {
            "sample_pool_id": pool_id,
            "source": source,
            "rule_set_key": rule_set_key,
            "execution_scope_hash": "a" * 64,
        },
        "summary": {},
        "items": [],
        "failed_records": [],
        "rule_results": [],
        "children": [],
        "child_jobs": [],
    }


class _WorkspaceStub:
    def __init__(self, jobs_by_owner: dict[str, dict[str, Any]] | None = None):
        self.jobs_by_owner = jobs_by_owner or {}
        self.get_calls: list[tuple[str, str | None]] = []
        self.cancel_calls: list[tuple[str, str | None]] = []

    def get_batch_job(self, *, job_id: str, created_by: str | None = None):
        self.get_calls.append((job_id, created_by))
        if created_by is None:
            for candidate in self.jobs_by_owner.values():
                if candidate and candidate.get("id") == job_id:
                    return deepcopy(candidate)
            return None
        job = self.jobs_by_owner.get(created_by)
        if not job or job.get("id") != job_id:
            return None
        return deepcopy(job)

    def cancel_batch_job(self, *, job_id: str, created_by: str | None = None):
        self.cancel_calls.append((job_id, created_by))
        return None

    def _load_batch_job_canonical_items(self, *, job: dict[str, Any], allow_partial: bool = False):
        return list(job.get("items") or [])


class _SharedPoolStub:
    def __init__(self, resolved: tuple[str, str] | None):
        self.resolved = resolved
        self.calls: list[str] = []

    def resolve_unique_pool_id_for_latest_job(self, *, job_id: str):
        self.calls.append(job_id)
        return self.resolved


@pytest.fixture(autouse=True)
def _auth_override(client):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    yield
    client.app.dependency_overrides.clear()


def _set_user(client, *, role: str, user_id: str = "admin-reader-001") -> None:
    client.app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "email": f"{role}@test.local",
        "roles": [role],
    }


def _install_services(monkeypatch, *, workspace: _WorkspaceStub, pool: _SharedPoolStub) -> None:
    from app.services import saved_result_access

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_shared_sample_pool_service", lambda: pool, raising=False)
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: None)


@pytest.mark.unit
@pytest.mark.api
def test_owner_can_read_ordinary_workspace_job_without_shared_pool_fallback(client, monkeypatch):
    owner_id = "admin-reader-001"
    job = _workspace_job(created_by=owner_id)
    workspace = _WorkspaceStub({owner_id: job})
    pool = _SharedPoolStub((SHARED_POOL_ID, SHARED_JOB_OWNER))
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role="admin", user_id=owner_id)

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 200
    assert "read_only" not in response.json()["data"]
    assert pool.calls == []
    assert workspace.get_calls == [(SHARED_JOB_ID, owner_id)]


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.parametrize("role", ["admin", "qc_manager"])
@pytest.mark.parametrize(
    "source",
    ["manual_problem_sample_pool", "manual_sample_formal_fast_screen_full"],
)
def test_authorized_role_can_read_shared_pool_latest_job_created_by_another_admin(
    client,
    monkeypatch,
    role,
    source,
):
    workspace = _WorkspaceStub(
        {
            SHARED_JOB_OWNER: _workspace_job(
                source=source,
                rule_set_key=(
                    ""
                    if source == "manual_sample_formal_fast_screen_full"
                    else "luxian_0609_qc_v1"
                ),
            )
        }
    )
    pool = _SharedPoolStub((SHARED_POOL_ID, SHARED_JOB_OWNER))
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role=role)

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 200
    response_data = response.json()["data"]
    assert response_data["id"] == SHARED_JOB_ID
    assert response_data["read_only"] is True
    assert "created_by" not in response_data
    assert "filters" not in response_data
    assert workspace.get_calls == [
        (SHARED_JOB_ID, "admin-reader-001"),
        (SHARED_JOB_ID, SHARED_JOB_OWNER),
    ]


@pytest.mark.unit
@pytest.mark.api
def test_shared_luxian_0916_job_preserves_independent_result_contract(client, monkeypatch):
    job = _workspace_job(rule_set_key="luxian_0916_qc_v1")
    job["items"] = [
        {
            "institute_id": "I-1",
            "patient_id": "P-1",
            "visit_id": "V-1",
            "rule_id": "LX0916-001",
            "status": "data_quality_gap",
            "reason_code": "semantic_fact_unavailable",
            "findings": "缺少权威语义事实。",
            "evidence": [],
            "suggestion": "补齐资料后复核。",
            "document_anchors": [],
            "diagnostics": {"family": "admission"},
        }
    ]
    workspace = _WorkspaceStub({SHARED_JOB_OWNER: job})
    pool = _SharedPoolStub((SHARED_POOL_ID, SHARED_JOB_OWNER))
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role="admin")

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 200
    response_data = response.json()["data"]
    assert response_data["read_only"] is True
    assert "created_by" not in response_data
    assert "filters" not in response_data
    assert response_data["items"][0]["status"] == "data_quality_gap"
    assert response_data["items"][0]["reason_code"] == "semantic_fact_unavailable"
    assert response_data["items"][0]["diagnostics"] == {"family": "admission"}


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.parametrize(
    ("resolved", "candidate"),
    [
        (None, _workspace_job(source="ordinary_workspace")),
        (None, _workspace_job()),
        (None, _workspace_job()),
        ((SHARED_POOL_ID, SHARED_JOB_OWNER), _workspace_job(pool_id="different-pool")),
        ((SHARED_POOL_ID, SHARED_JOB_OWNER), _workspace_job(source="ordinary_workspace")),
        ((SHARED_POOL_ID, SHARED_JOB_OWNER), _workspace_job(workspace=False)),
    ],
    ids=[
        "ordinary-cross-owner-job",
        "old-sample-job-not-latest",
        "duplicate-pool-pointer-resolver-failed-closed",
        "wrong-pool",
        "wrong-source",
        "wrong-workspace-type",
    ],
)
def test_cross_owner_job_fails_closed_without_exact_shared_latest_contract(
    client,
    monkeypatch,
    resolved,
    candidate,
):
    workspace = _WorkspaceStub({SHARED_JOB_OWNER: candidate})
    pool = _SharedPoolStub(resolved)
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role="admin")

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 404


@pytest.mark.unit
@pytest.mark.api
def test_doctor_cannot_trigger_shared_pool_fallback(client, monkeypatch):
    workspace = _WorkspaceStub({SHARED_JOB_OWNER: _workspace_job()})
    pool = _SharedPoolStub((SHARED_POOL_ID, SHARED_JOB_OWNER))
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role="doctor", user_id="doctor-001")

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 404
    assert pool.calls == []
    assert workspace.get_calls == [(SHARED_JOB_ID, "doctor-001")]


@pytest.mark.unit
@pytest.mark.api
def test_shared_pool_fallback_does_not_open_cancel_or_export(client, monkeypatch):
    workspace = _WorkspaceStub({SHARED_JOB_OWNER: _workspace_job()})
    pool = _SharedPoolStub((SHARED_POOL_ID, SHARED_JOB_OWNER))
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role="admin")

    cancel_response = client.post(
        f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}/cancel"
    )
    export_response = client.get(
        f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}/export?format=html"
    )

    assert cancel_response.status_code == 404
    assert export_response.status_code == 404
    assert pool.calls == []


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.parametrize("role", ["super_admin", "sync_admin"])
def test_super_admin_reads_cross_owner_job_directly_without_shared_pool_fallback(
    client,
    monkeypatch,
    role,
):
    job = _workspace_job(created_by=SHARED_JOB_OWNER, source="ordinary_workspace")
    workspace = _WorkspaceStub({SHARED_JOB_OWNER: job})
    pool = _SharedPoolStub(None)
    _install_services(monkeypatch, workspace=workspace, pool=pool)
    _set_user(client, role=role, user_id=f"{role}-001")

    response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{SHARED_JOB_ID}")

    assert response.status_code == 200
    assert "read_only" not in response.json()["data"]
    assert pool.calls == []
    assert workspace.get_calls == [(SHARED_JOB_ID, None)]
