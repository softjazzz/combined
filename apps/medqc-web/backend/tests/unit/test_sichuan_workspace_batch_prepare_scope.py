"""workspace 批量任务范围守卫：门诊/未知范围必须在取数与建任务前失败。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan
from app.services import sichuan_workspace_batch_prepare as prepare_module

SCOPE_DETAIL = prepare_module._UNSUPPORTED_WORKSPACE_SCOPE_DETAIL
FINAL_SCOPE_RULE_SET_KEY = "sc_content_v1"


class _WorkspaceStub:
    def __init__(self) -> None:
        self.collect_calls: List[Dict[str, Any]] = []
        self.created_job: Optional[Dict[str, Any]] = None

    def collect_records(self, **kwargs: Any) -> List[Dict[str, Any]]:
        self.collect_calls.append(dict(kwargs))
        return [
            {
                "institute_id": "HOSP-001",
                "patient_id": "PAT-001",
                "record_id": "VISIT-001",
                "visit_id": "VISIT-001",
                "scope": "running",
                "admission_datetime": "2026-06-01 08:00:00",
                "discharge_datetime": "",
            }
        ]

    def create_batch_job(self, **kwargs: Any) -> Dict[str, Any]:
        self.created_job = dict(kwargs)
        return {"id": "job-1", **kwargs}


class _ServiceStub:
    def assert_sc_rule_source_ready(
        self, *, context: str, block_batch: bool = False
    ) -> Dict[str, Any]:
        return {"sc_source": "pg_governance"}


def _prepare(payload: Any, workspace: _WorkspaceStub):
    return qc_sichuan.prepare_workspace_batch_job(
        payload=payload,
        qc_service=_ServiceStub(),  # type: ignore[arg-type]
        workspace=workspace,  # type: ignore[arg-type]
    )


def test_explicit_outpatient_without_rule_set_rejected_before_collect_and_create():
    workspace = _WorkspaceStub()

    with pytest.raises(HTTPException) as error:
        _prepare(
            qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_ids=["SC-001"],
                scope="outpatient",
            ),
            workspace,
        )

    assert error.value.status_code == 422
    assert error.value.detail == SCOPE_DETAIL
    assert len(workspace.collect_calls) == 0  # 取数 0 次
    assert workspace.created_job is None


def test_explicit_outpatient_not_masked_by_final_rule_set_scope():
    """规则集默认范围是 final，也不得把显式 outpatient 掩盖成可执行范围。"""

    workspace = _WorkspaceStub()

    with pytest.raises(HTTPException) as error:
        _prepare(
            qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=FINAL_SCOPE_RULE_SET_KEY,
                rule_ids=["SC-001"],
                scope="outpatient",
            ),
            workspace,
        )

    assert error.value.status_code == 422
    assert error.value.detail == SCOPE_DETAIL
    assert len(workspace.collect_calls) == 0  # 取数 0 次
    assert workspace.created_job is None


@pytest.mark.parametrize(
    "scope",
    ["", "   ", "emergency", "outpatient_emergency", "inpatient", "unknown"],
)
def test_unknown_scope_values_rejected_before_collect_and_create(scope: str):
    workspace = _WorkspaceStub()

    with pytest.raises(HTTPException) as error:
        _prepare(
            qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_ids=["SC-001"],
                scope=scope,
            ),
            workspace,
        )

    assert error.value.status_code == 422
    assert error.value.detail == SCOPE_DETAIL
    assert len(workspace.collect_calls) == 0  # 取数 0 次
    assert workspace.created_job is None


@pytest.mark.parametrize("scope", ["all", "running", "final"])
def test_supported_scopes_keep_existing_semantics(scope: str):
    workspace = _WorkspaceStub()

    prepared = _prepare(
        qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_ids=["SC-001"],
            scope=scope,
        ),
        workspace,
    )

    assert len(workspace.collect_calls) == 1
    assert workspace.collect_calls[0]["scope"] == scope
    assert prepared.create_kwargs["scope"] == scope
    assert prepared.create_kwargs["filters"]["query_scope"] == scope


def test_valid_request_scope_still_yields_to_rule_set_scope():
    """受支持的范围保持既有语义：规则集默认范围仍可覆盖请求范围。"""

    workspace = _WorkspaceStub()

    prepared = _prepare(
        qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=FINAL_SCOPE_RULE_SET_KEY,
            rule_ids=["SC-001"],
            scope="running",
        ),
        workspace,
    )

    assert prepared.create_kwargs["scope"] == "final"
    assert workspace.collect_calls[0]["scope"] == "final"


@pytest.mark.asyncio
async def test_route_rejects_outpatient_scope_before_workspace_init(monkeypatch):
    queued: List[Any] = []
    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda: pytest.fail("超出范围的门诊请求不得初始化 workspace"),
    )
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    with pytest.raises(HTTPException) as error:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_ids=["SC-001"],
                scope="outpatient",
            ),
            current_user={"id": "tester", "roles": ["qc_manager"]},
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
        )

    assert error.value.status_code == 422
    assert error.value.detail == SCOPE_DETAIL
    assert queued == []
