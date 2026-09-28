"""批量任务纯校验失败时不得提前初始化 workspace 数据库服务。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan


@pytest.mark.asyncio
async def test_unknown_rule_set_rejected_before_workspace_access(monkeypatch):
    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda: pytest.fail("invalid rule set must not initialize workspace"),
    )
    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(rule_set_key="unknown_v1"),
            current_user={"id": "user-1", "roles": ["qc_manager"]},
            qc_service=object(),
        )
    assert exc.value.status_code == 422
