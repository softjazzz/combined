from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.core.security import get_current_user
from app.routers import qc_diagnostics, qc_sichuan
from app.services.qc_diagnostics import support_store


@pytest.mark.asyncio
async def test_capture_requires_owned_unchanged_result_and_explicit_download(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(qc_diagnostics.router)
    user = {"id": "owner", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: user
    workspace = Mock()
    job_id = str(uuid4())
    workspace.get_batch_job.return_value = {"scope": "final", "status": "completed", "filters": {"diagnostic_capture": True}}
    workspace.get_latest_luxian_0609_record_result.return_value = {
        "state": "ready", "job_id": job_id, "record_ref": "ref",
        "items": [{"rule_id": "LX0609-007"}],
    }
    monkeypatch.setattr(qc_diagnostics, "_workspace", lambda: workspace)
    monkeypatch.setattr(support_store, "_ROOT", tmp_path)
    create = AsyncMock(return_value={"data": {"id": job_id}})
    monkeypatch.setattr(qc_sichuan, "create_workspace_batch_job", create)
    monkeypatch.setattr(qc_sichuan, "get_qc_service", AsyncMock())
    selection = {"job_id": job_id, "record_ref": "ref", "institute_id": "I", "patient_id": "P", "visit_id": "V"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        base = "/api/v1/qc/diagnostics/capture"
        assert (await client.post(base + "/start", json={**selection, "record_ref": "wrong"})).status_code == 409
        create.assert_not_called()
        assert (await client.post(base + "/start", json=selection)).json() == {"job_id": job_id}
        payload = create.call_args.args[1]
        assert payload.diagnostic_capture is True
        assert payload.rule_ids == ["LX0609-007"]
        assert payload.record_refs == [{"institute_id": "I", "patient_id": "P", "visit_id": "V"}]
        support_store._write_status(job_id, {"state": "ready", "capture_completeness": "partial"})
        support_store._path(job_id, ".zip").write_bytes(b"PKtest")
        assert (await client.get(base + "/" + job_id)).json()["state"] == "ready"
        path = base + "/" + job_id + "/download"
        assert (await client.post(path, json={"confirmed": False})).status_code == 409
        assert (await client.post(path, json={"confirmed": True})).content == b"PKtest"
        workspace.get_batch_job.return_value = {"status": "completed", "filters": {}}
        unavailable = await client.get(base + "/" + job_id)
        assert unavailable.status_code == 200
        assert unavailable.json() == {"state": "unavailable", "error_code": "capture_not_recorded"}
        assert unavailable.headers["cache-control"] == "no-store"
        assert (await client.post(path, json={"confirmed": True})).status_code == 404
        workspace.get_batch_job.return_value = None
        assert (await client.get(base + "/" + job_id)).status_code == 404
        assert (await client.post(path, json={"confirmed": True})).status_code == 404
        user["roles"] = ["doctor"]
        assert (await client.get(base + "/" + job_id)).status_code == 403


def test_store_only_activates_explicit_capture_and_reports_interruption(monkeypatch, tmp_path):
    monkeypatch.setattr(support_store, "_ROOT", tmp_path)
    workspace = Mock()
    workspace.get_batch_job_for_processing.return_value = {"filters": {}}
    job_id = str(uuid4())
    assert support_store.capture_for_job(workspace, job_id) is None
    assert not list(tmp_path.iterdir())
    support_store._write_status(job_id, {"state": "running"})
    support_store.finalize(job_id)
    assert support_store.status(job_id, "failed")["state"] == "failed"


def test_partial_capture_delivers_failure_evidence_without_saved_result():
    from app.services.qc_diagnostics.job_capture import DiagnosticJobCapture
    delivered = []
    capture = DiagnosticJobCapture(job_id=str(uuid4()), record_identity=("I", "P", "V"),
        consume=lambda data, summary: delivered.append((data, summary)), capture_partial=True)
    capture.finish(deliver=False)
    assert len(delivered) == 1
    assert delivered[0][0]["saved_result"] is None
    assert "execution_interrupted" in delivered[0][1]["missing_reasons"]
    assert capture.summary()["retained_bytes"] == 0
