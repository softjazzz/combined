"""现有任务读取入口的失败任务权限边界，不启动应用 lifespan。"""
from copy import deepcopy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security import get_current_user
from app.routers import qc_sichuan
from app.services.custom_qc_workspace_service import project_customer_safe_batch_job


@pytest.mark.parametrize("user_id, expected", [(None, 401), ("other", 404), ("owner", 200)])
def test_failed_task_access(monkeypatch, user_id, expected):
    saved = {"id": "synthetic-failed", "draft_id": "customer-rule-library",
             "rule_code": "CUSTOMER-RULE-LIBRARY", "status": "failed", "created_by": "owner",
             "items": [{"status": "data_gap", "is_compliant": None, "rule_id": "SYNTHETIC-RULE"}],
             "failed_records": [{"reason_code": "model_transport_error", "error_phase": "evaluate_document"}]}
    original = deepcopy(saved)
    class Workspace:
        def get_batch_job(self, *, job_id, created_by):
            return deepcopy(saved) if created_by == "owner" and job_id == saved["id"] else None
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: Workspace())
    monkeypatch.setattr(qc_sichuan, "_resolve_shared_sample_pool_latest_job", lambda **kwargs: None)
    monkeypatch.setattr(qc_sichuan, "_workspace_batch_response_item",
                        lambda job: project_customer_safe_batch_job(job, hmac_key="synthetic", _validate_luxian=False))
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    if user_id:
        app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "roles": ["qc_manager"]}
    with TestClient(app) as client:
        response = client.get("/api/v1/qc/sichuan/workspace/batch-jobs/synthetic-failed")
    assert response.status_code == expected
    if expected == 200:
        data = response.json()["data"]
        assert data["status"] == "failed"
        assert len(data["items"]) == 1
        assert data["failed_records"][0]["reason_code"] == "model_transport_error"
    assert saved == original
