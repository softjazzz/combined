"""独立 ASGI 路由测试，不启动主应用、不连接数据库或模型。"""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI

from app.core.security import get_current_user
from app.routers import qc_diagnostics
from app.services.qc_diagnostics.history_delivery import HistoryDelivery


@pytest.mark.asyncio
async def test_admin_owned_result_prepare_confirm_download(monkeypatch):
    app = FastAPI()
    app.include_router(qc_diagnostics.router)
    user = {"id": "synthetic-admin", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: user
    workspace = Mock()
    workspace.get_batch_job.return_value = {"status": "completed"}
    workspace.get_latest_luxian_0609_record_result.return_value = {
        "state": "ready", "job_id": "job", "record_ref": "ref",
        "items": [{"rule_id": "LX0609-032", "status": "not_applicable", "reason_code": "trigger_absent_complete"}],
    }
    monkeypatch.setattr(qc_diagnostics, "_workspace", lambda: workspace)
    monkeypatch.setattr(qc_diagnostics, "_delivery", HistoryDelivery())
    payload = {"job_id": "job", "record_ref": "ref", "institute_id": "i", "patient_id": "p", "visit_id": "v"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        base = "/api/v1/qc/diagnostics/history"
        user["roles"] = ["doctor"]
        assert (await client.post(f"{base}/prepare", json=payload)).status_code == 403
        workspace.get_batch_job.assert_not_called()
        user["roles"] = ["admin"]
        assert (await client.post(f"{base}/prepare", json={**payload, "medical_text": "forbidden"})).status_code == 422
        prepared = await client.post(f"{base}/prepare", json=payload)
        assert prepared.status_code == 200
        assert prepared.headers["cache-control"] == "no-store"
        token = prepared.json()["token"]
        path = f"{base}/{token}/download"
        assert (await client.post(path, json={"confirmed": False})).status_code == 409
        assert (await client.post(path, json={"confirmed": "true"})).status_code == 422
        user["id"] = "other-admin"
        assert (await client.post(path, json={"confirmed": True})).status_code == 409
        user["id"] = "synthetic-admin"
        downloaded = await client.post(path, json={"confirmed": True})
        assert downloaded.status_code == 200 and downloaded.content.startswith(b"PK")
        assert downloaded.headers["cache-control"] == "no-store"
        assert (await client.delete(f"{base}/{token}")).status_code == 204
        assert (await client.post(path, json={"confirmed": True})).status_code == 409
