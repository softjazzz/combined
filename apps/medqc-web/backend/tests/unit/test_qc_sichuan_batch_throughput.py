from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date
from typing import Any, Dict, List, Optional
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan
from app.services import sichuan_workspace_batch_worker as batch_worker
import app.services.custom_qc_workspace_service as workspace_module
from app.services.case_identity import CaseRef
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.sichuan_qc_service import SichuanQCService
from app.services.llm_observability import current_llm_observation_context
from app.services.qc_rule_sets import SC_CONTENT_V1_RULE_IDS
from app.services.qc_workspace.failed_rule_retry import build_failed_rule_retry_scope
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.luxian_0609 import runtime_shadow_input_provider
from app.services.sample_validation_rule_sets import LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
)


def _luxian_native_settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXECUTION_ENABLED": True,
        "LUXIAN_0609_NATIVE_MDT_040_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": True,
        "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": True,
        "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED": True,
        "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
        "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED": True,
        "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_RUNTIME_SHADOW_ENABLED": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_set_key",
    [qc_sichuan.LUXIAN_0609_RULE_SET_KEY, "sample_programmatic_v1"],
    ids=["luxian-formal", "sample-programmatic"],
)
async def test_formal_worker_rechecks_activation_before_qc_service_and_canonical(
    monkeypatch: pytest.MonkeyPatch,
    rule_set_key: str,
) -> None:
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-01-01-01"],
        "rule_set_key": rule_set_key,
        "validation_mode": "programmatic",
    }
    qc_service_calls = 0
    complete_calls = 0

    class _MissingActivation:
        def enforce(self) -> None:
            raise ValueError("产品尚未激活")

    async def _qc_service_provider():
        nonlocal qc_service_calls
        qc_service_calls += 1
        return _ServiceStub()

    original_complete = workspace.complete_batch_job

    def _complete_batch_job(**kwargs: Any) -> None:
        nonlocal complete_calls
        complete_calls += 1
        original_complete(**kwargs)

    workspace.complete_batch_job = _complete_batch_job  # type: ignore[method-assign]
    monkeypatch.setattr(
        batch_worker,
        "get_product_activation_service",
        lambda: _MissingActivation(),
        raising=False,
    )

    await batch_worker.run_sichuan_workspace_batch_job(
        "job-throughput-001",
        workspace=workspace,
        qc_service_provider=_qc_service_provider,
    )

    assert workspace.job["status"] == "failed"
    assert "产品尚未激活" in workspace.job["error_message"]
    assert qc_service_calls == 0
    assert complete_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("early_return", ["missing", "parent"])
async def test_worker_does_not_check_activation_for_missing_or_parent_job(
    monkeypatch: pytest.MonkeyPatch,
    early_return: str,
) -> None:
    workspace = _WorkspaceStub()
    if early_return == "parent":
        workspace.job["job_kind"] = "parent"
    activation_calls = 0
    qc_service_calls = 0

    class _ActivationProbe:
        def enforce(self) -> None:
            nonlocal activation_calls
            activation_calls += 1

    if early_return == "missing":
        monkeypatch.setattr(
            workspace,
            "get_batch_job_for_processing",
            lambda **_kwargs: None,
        )
    monkeypatch.setattr(
        batch_worker,
        "get_product_activation_service",
        lambda: _ActivationProbe(),
    )

    async def _qc_service_provider():
        nonlocal qc_service_calls
        qc_service_calls += 1
        return _ServiceStub()

    await batch_worker.run_sichuan_workspace_batch_job(
        "job-throughput-001",
        workspace=workspace,
        qc_service_provider=_qc_service_provider,
    )

    assert activation_calls == 0
    assert qc_service_calls == 0


@pytest.mark.asyncio
async def test_luxian_batch_worker_rejects_customer_aggregation_without_unified_engine(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-01-01-01"],
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "date_field": "admission",
    }
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False),
    )

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "客户结果聚合已开启，但统一Native引擎未启用" in workspace.job["error_message"]
    assert service.evaluate_calls == 0


@pytest.mark.asyncio
async def test_luxian_batch_worker_rejects_gate_only_customer_job_without_unified_engine(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": [],
        "gate_only_customer_rule_ids": ["LX0609-11-01-01"],
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "date_field": "admission",
    }
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False),
    )

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "客户结果聚合已开启，但统一Native引擎未启用" in workspace.job["error_message"]
    assert service.evaluate_calls == 0


@pytest.mark.asyncio
async def test_luxian_batch_create_rejects_customer_aggregation_without_unified_engine(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False),
    )

    with pytest.raises(HTTPException, match="客户结果聚合已开启，但统一Native引擎未启用"):
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                rule_ids=["LX0609-01-01-01"],
                scope="final",
                record_refs=[
                    {
                        "institute_id": "HOSP-001",
                        "patient_id": "PAT-visit-001",
                        "visit_id": "visit-001",
                    }
                ],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )

    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_luxian_batch_create_rejects_exam_lab_compatibility_without_creating_job(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                rule_ids=["LX0609-06-01-02"],
                scope="final",
                record_refs=[
                    {
                        "institute_id": "HOSP-001",
                        "patient_id": "PAT-visit-001",
                        "visit_id": "visit-001",
                    }
                ],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 503
    assert "正式质控禁止兼容执行" in str(exc_info.value.detail)
    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_luxian_batch_create_rejects_legacy_rule_id_as_503_without_creating_job(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                rule_ids=["LXE-23"],
                scope="final",
                record_refs=[
                    {
                        "institute_id": "HOSP-001",
                        "patient_id": "PAT-visit-001",
                        "visit_id": "visit-001",
                    }
                ],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 503
    assert "只接受LX0609客户质控点ID" in str(exc_info.value.detail)
    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_luxian_batch_worker_runtime_family_drift_fails_before_result_or_canonical(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-06-01-02"],
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "date_field": "admission",
    }
    service = _ServiceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=False),
    )

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "正式质控禁止兼容执行" in workspace.job["error_message"]
    assert service.evaluate_calls == 0
    assert workspace.summary is None
    assert workspace.items == []
    assert workspace.progress_updates == []
    assert workspace.failed_records == []


@pytest.mark.asyncio
async def test_luxian_batch_worker_rejects_persisted_legacy_rule_id_before_evaluation(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LXE-23"],
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "date_field": "admission",
    }
    service = _ServiceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "只接受LX0609客户质控点ID" in workspace.job["error_message"]
    assert service.evaluate_calls == 0
    assert workspace.summary is None
    assert workspace.items == []
    assert workspace.progress_updates == []
    assert workspace.failed_records == []


def test_luxian_target_document_type_uses_catalog_document_not_final_scene_fallback():
    assert batch_worker._resolve_luxian_target_document_type(
        {
            "rule_id": "LX0609-01-01-02",
            "applicable_documents": ["admission_record"],
            "applicable_document_labels": ["入院记录"],
        }
    ) == "入院记录"

    assert batch_worker._resolve_luxian_target_document_type(
        {
            "rule_id": "LX0609-06-01-02",
            "applicable_document_labels": ["检查检验报告", "日常病程记录"],
        }
    ) == "检查检验报告、日常病程记录"


class _WorkspaceStub:
    def __init__(self) -> None:
        self.job: Dict[str, Any] = {
            "id": "job-throughput-001",
            "status": "queued",
            "scope": "final",
            "filters": {
                "rule_ids": ["SC-001", "SC-002", "SC-003"],
                "date_field": "discharge",
            },
            "record_ids": ["visit-001", "visit-002"],
        }
        self.summary: Optional[Dict[str, Any]] = None
        self.items: List[Dict[str, Any]] = []
        self.failed_records: List[Dict[str, Any]] = []
        self.created_job: Optional[Dict[str, Any]] = None
        self.progress_updates: List[Dict[str, Any]] = []

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        if job_id != self.job["id"]:
            return None
        return dict(self.job)

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        if job_id == self.job["id"]:
            self.job["status"] = "running"
            return True
        return False

    def collect_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[List[str]] = None,
        record_refs: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        refs = list(record_refs or [])
        ids = list(
            record_ids
            or [ref.visit_id if isinstance(ref, CaseRef) else ref["visit_id"] for ref in refs]
        )
        return [
            {
                "institute_id": (
                    refs[idx].institute_id
                    if idx < len(refs) and isinstance(refs[idx], CaseRef)
                    else str(refs[idx].get("institute_id") or "HOSP-001")
                    if idx < len(refs) and isinstance(refs[idx], dict)
                    else "HOSP-001"
                ),
                "patient_id": (
                    refs[idx].patient_id
                    if idx < len(refs) and isinstance(refs[idx], CaseRef)
                    else str(refs[idx].get("patient_id") or f"PAT-{rid}")
                    if idx < len(refs) and isinstance(refs[idx], dict)
                    else f"PAT-{rid}"
                ),
                "record_id": rid,
                "visit_id": rid,
                "patient_name": f"患者{idx + 1}",
                "department": "骨科",
                "scope": scope,
            }
            for idx, rid in enumerate(ids)
        ]

    def hydrate_records_with_medical_text(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**item, "medical_text": f"病历文本-{item.get('record_id')}"} for item in records]

    def create_batch_job(
        self,
        *,
        draft: Dict[str, Any],
        created_by: str,
        scope: str,
        filters: Dict[str, Any],
        record_ids: List[str],
        total_records: int,
        record_refs: Optional[List[Dict[str, str]]] = None,
        draft_ids: Optional[List[str]] = None,
        execution_mode: Optional[str] = None,
        rule_count: Optional[int] = None,
        run_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.created_job = {
            "id": self.job["id"],
            "draft_id": draft.get("id"),
            "draft_ids": list(draft_ids or []),
            "rule_code": draft.get("rule_code"),
            "rule_name": draft.get("name"),
            "scene": draft.get("scene"),
            "created_by": created_by,
            "scope": scope,
            "filters": filters,
            "record_ids": record_ids,
            "record_refs": list(record_refs or []),
            "total_records": total_records,
            "execution_mode": execution_mode,
            "rule_count": rule_count,
            "run_mode": run_mode,
            "status": "queued",
        }
        return dict(self.created_job)

    def list_batch_jobs(
        self,
        *,
        created_by: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
        **_: Any,
    ) -> SimpleNamespace:
        return SimpleNamespace(items=[], total=0, page=page, page_size=page_size)

    def update_batch_job_progress(
        self,
        *,
        job_id: str,
        step_key: str,
        rule_index: int,
        rule_count: int,
        processed_records: int,
        total_records: int,
        summary_patch: Optional[Dict[str, Any]] = None,
        progress_patch: Optional[Dict[str, Any]] = None,
    ) -> None:
        if job_id != self.job["id"]:
            return
        progress = {
            "step_key": step_key,
            "rule_index": rule_index,
            "rule_count": rule_count,
            "processed_records": processed_records,
            "total_records": total_records,
            **dict(progress_patch or {}),
        }
        self.job["progress"] = progress
        self.progress_updates.append(
            {
                **progress,
                "summary_patch": dict(summary_patch or {}),
                "progress_patch": dict(progress_patch or {}),
            }
        )
        if summary_patch:
            current_summary = dict(self.summary or {})
            current_summary.update(summary_patch)
            self.summary = current_summary

    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> None:
        # 持久化层的真实失败/部分失败分支另由 SQLite 合同测试覆盖。
        self.job["status"] = (
            "failed" if summary.get("execution_status") in {"partial_failed", "failed"}
            else "completed"
        )
        self.summary = dict(summary)
        self.items = list(items)
        self.failed_records = list(failed_records)
        self.job.update(
            {
                "summary": dict(summary),
                "items": list(items),
                "failed_records": list(failed_records),
            }
        )

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        self.job["status"] = "failed"
        self.job["error_message"] = error_message


class _IdempotentWorkspaceStub(_WorkspaceStub):
    def __init__(self) -> None:
        super().__init__()
        self.job = {
            **self.job,
            "id": "job-idempotent-active",
            "status": "running",
            "filters": {},
            "record_ids": ["visit-001", "visit-002"],
        }
        self.list_calls: List[Dict[str, Any]] = []
        self.create_called = False

    def list_batch_jobs(
        self,
        *,
        created_by: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
        **_: Any,
    ) -> SimpleNamespace:
        self.list_calls.append(
            {
                "created_by": created_by,
                "status": status,
                "page": page,
                "page_size": page_size,
            }
        )
        if status == "running":
            return SimpleNamespace(items=[dict(self.job)], total=1, page=page, page_size=page_size)
        return SimpleNamespace(items=[], total=0, page=page, page_size=page_size)

    def create_batch_job(self, **_: Any) -> Dict[str, Any]:
        self.create_called = True
        raise AssertionError("复用 active job 时不应创建新任务")


@pytest.mark.asyncio
async def test_luxian_worker_preserves_first_evaluation_error_before_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NoCompleteWorkspace(_WorkspaceStub):
        def __init__(self) -> None:
            super().__init__()
            self.complete_calls = 0

        def complete_batch_job(self, **kwargs: Any) -> None:
            self.complete_calls += 1
            super().complete_batch_job(**kwargs)

    workspace = _NoCompleteWorkspace()
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-06-01-05"],
        "selected_rule_ids": ["LX0609-06-01-05"],
        "scoped_customer_rule_ids": ["LX0609-06-01-05"],
        "record_rule_map": {"visit-001": ["LX0609-06-01-05"]},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        error = ValueError("invalid customer display facts")
        error.rule_id = "LX0609-06-01-05"  # type: ignore[attr-defined]
        raise error

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0609_rules",
        lambda: [get_luxian_0609_rule("LX0609-06-01-05")],
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert workspace.job["error_message"] == (
        "病历质控未形成可交付结果："
        "客户展示事实不符合交付合同（invalid customer display facts）；"
        "质控点 LX0609-06-01-05"
    )
    assert workspace.complete_calls == 0
    assert workspace.items == []
    failure_updates = [
        item
        for item in workspace.progress_updates
        if item["step_key"] == "failed"
    ]
    assert failure_updates
    diagnostics = failure_updates[-1]["summary_patch"]["failure_diagnostics"]
    assert diagnostics[0]["rule_id"] == "LX0609-06-01-05"
    assert diagnostics[0]["error"].startswith("invalid customer display facts")

class _ServiceStub:
    def __init__(self, status_by_rule: Optional[Dict[str, str]] = None) -> None:
        self.evaluate_calls = 0
        self.evaluate_document_args: List[Dict[str, Any]] = []
        self.evaluate_rule_for_visit_calls = 0
        self.evaluate_rule_for_visit_args: List[Dict[str, Any]] = []
        self.status_by_rule = {str(k).upper(): str(v).lower() for k, v in (status_by_rule or {}).items()}

    def assert_sc_rule_source_ready(self, *, context: str, block_batch: bool = False) -> Dict[str, Any]:
        return {"sc_source": "pg_governance"}

    def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
        return {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "name": f"规则-{rule_id}",
            "defect_level": "一般缺陷",
        }

    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        self.evaluate_calls += 1
        self.evaluate_document_args.append(dict(kwargs))
        evals: List[Dict[str, Any]] = []
        for rid in list(rule_ids or []):
            normalized_rid = str(rid).upper()
            status = self.status_by_rule.get(normalized_rid, "compliant")
            is_compliant = status in {"compliant", "not_applicable"}
            evals.append(
                {
                    "rule_id": rid,
                    "rule_name": f"规则-{rid}",
                    "status": status,
                    "is_compliant": is_compliant,
                    "findings": "" if status == "compliant" else f"命中状态: {status}",
                    "evidence": "",
                    "suggestion": "" if status == "compliant" else "请人工复核",
                    "confidence": 0.9 if status == "compliant" else 0.6,
                    "metadata": {
                        "executor_type": "program",
                        "tokens_used": 0,
                        "api_time": 0.001,
                        "cache_hit": False,
                        "rule_version": "v1",
                        "prompt_version": "default-v1",
                        "model_version": "test-model",
                        "evidence_source": "medical_text",
                        "trace_id": "trace-1",
                        "cache_key": "",
                        "execution_domain": "general",
                        "doc_scope": "primary",
                        "cost_class": "low",
                        "llm_fallback": False,
                    },
                }
            )
        return {
            "evaluation_results": evals,
            "pack_metrics": {
                "total_packs": 2,
                "avg_pack_size": 5.0,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "pack_parse_retry_count": 0,
                "context_tokens_estimate": 700,
            },
        }

    async def evaluate_rule_for_visit(
        self,
        *,
        rule_id: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        source_schema: Optional[str] = None,
        bundle_schema: str = "public",
        force_refresh_bundle: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        self.evaluate_rule_for_visit_calls += 1
        self.evaluate_rule_for_visit_args.append(
            {
                "rule_id": rule_id,
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "source_schema": source_schema,
                "bundle_schema": bundle_schema,
                "force_refresh_bundle": force_refresh_bundle,
            }
        )
        normalized_rid = str(rule_id).upper()
        status = self.status_by_rule.get(normalized_rid, "compliant")
        is_compliant = status in {"compliant", "not_applicable"}
        document_type = "病程记录" if normalized_rid == "SC-002" else "出院记录"
        return {
            "document_id": visit_id,
            "document_type": document_type,
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "rule_name": f"规则-{rule_id}",
                    "status": status,
                    "is_compliant": is_compliant,
                    "findings": "" if status == "compliant" else f"分域命中状态: {status}",
                    "evidence": f"bundle-evidence-{rule_id}",
                    "suggestion": "" if status == "compliant" else "请人工复核",
                    "confidence": 0.82 if status == "compliant" else 0.61,
                    "metadata": {
                        "executor_type": "llm",
                        "tokens_used": 120,
                        "api_time": 0.12,
                        "cache_hit": False,
                        "rule_version": "v1",
                        "prompt_version": "batch_compact_v1",
                        "model_version": "test-model",
                        "evidence_source": "bundle",
                        "trace_id": f"trace-{rule_id}",
                        "cache_key": "",
                        "execution_domain": "terminal",
                        "doc_scope": "primary",
                        "cost_class": "standard",
                        "llm_fallback": False,
                    },
                }
            ],
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": 1.0,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "pack_parse_retry_count": 0,
                "context_tokens_estimate": 240,
            },
        }


class _FormalPostprocessServiceStub(_ServiceStub):
    async def evaluate_document(
        self,
        document_id: str,
        content: str,
        document_type: str = "病程记录",
        rule_ids: Optional[List[str]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        self.evaluate_calls += 1
        rows: List[Dict[str, Any]] = []
        data_gap_rules = {"SC-070", "SC-074", "SC-107", "SC-146"}
        for rule_id in list(rule_ids or []):
            normalized = str(rule_id).upper()
            if normalized == "SC-036":
                rows.append(
                    {
                        "rule_id": rule_id,
                        "rule_name": f"规则-{rule_id}",
                        "status": "non_compliant",
                        "is_compliant": False,
                        "findings": "病程记录了ALT异常及甲肝抗体阳性，并给出处理意见，合规。",
                        "evidence": "检查提示ALT异常、甲肝抗体阳性；病程记录已分析异常并给出处理意见。",
                        "suggestion": "无需整改。",
                        "confidence": 0.72,
                        "metadata": {"executor_type": "llm", "tokens_used": 100, "api_time": 0.1},
                    }
                )
            elif normalized in data_gap_rules:
                rows.append(
                    {
                        "rule_id": rule_id,
                        "rule_name": f"规则-{rule_id}",
                        "status": "uncertain",
                        "is_compliant": False,
                        "findings": "缺医嘱或缺执行清单，无法判定是否落实。",
                        "evidence": "未提供长期医嘱单或执行记录。",
                        "suggestion": "补充长期医嘱单和执行清单后复核。",
                        "confidence": 0.5,
                        "metadata": {"executor_type": "llm", "tokens_used": 100, "api_time": 0.1},
                    }
                )
            else:
                rows.append(
                    {
                        "rule_id": rule_id,
                        "rule_name": f"规则-{rule_id}",
                        "status": "uncertain",
                        "is_compliant": False,
                        "findings": "证据片段不足，需人工复核。",
                        "evidence": "当前病程记录仅见相关描述，尚不能闭合触发证据与缺陷事实。",
                        "suggestion": "请人工复核完整文书。",
                        "confidence": 0.55,
                        "metadata": {"executor_type": "llm", "tokens_used": 100, "api_time": 0.1},
                    }
                )
        return {
            "evaluation_results": rows,
            "token_usage": {"total_tokens": 900, "prompt_tokens": 700, "completion_tokens": 200},
            "api_time": 1.0,
            "pack_metrics": {
                "total_packs": 3,
                "avg_pack_size": 3.0,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "pack_parse_retry_count": 0,
                "context_tokens_estimate": 1200,
            },
        }


def test_workspace_bundle_scene_should_prioritize_each_record_over_query_scope():
    assert batch_worker._resolve_workspace_bundle_scene(query_scope="all", record_scope="final") == "final"
    assert batch_worker._resolve_workspace_bundle_scene(query_scope="all", record_scope="running") == "running"
    assert batch_worker._resolve_workspace_bundle_scene(query_scope="final", record_scope="running") == "running"
    assert batch_worker._resolve_workspace_bundle_scene(query_scope="running", record_scope="final") == "final"
    assert batch_worker._resolve_workspace_bundle_scene(query_scope="all", record_scope="") == ""

    assert batch_worker._workspace_bundle_scene_candidates(
        query_scope="running",
        record_scope="final",
    ) == ["final", "running"]
    assert batch_worker._workspace_bundle_scene_candidates(
        query_scope="final",
        record_scope="",
    ) == ["final", "running"]
    assert batch_worker._workspace_bundle_scene_candidates(
        query_scope="all",
        record_scope="",
    ) == ["running", "final"]


def test_workspace_record_scene_snapshot_should_change_after_discharge():
    running_snapshot = qc_sichuan._build_workspace_record_scene_snapshot(
        [
            {
                "record_id": "visit-001",
                "scope": "running",
                "discharge_datetime": "",
            }
        ],
        query_scope="all",
    )
    final_snapshot = qc_sichuan._build_workspace_record_scene_snapshot(
        [
            {
                "record_id": "visit-001",
                "scope": "final",
                "discharge_datetime": "2026-08-03 09:30:00",
            }
        ],
        query_scope="all",
    )

    assert running_snapshot == [
        {
            "record_id": "visit-001",
            "record_scene": "running",
            "resolved_scene": "running",
            "discharge_snapshot": "",
        }
    ]
    assert final_snapshot == [
        {
            "record_id": "visit-001",
            "record_scene": "final",
            "resolved_scene": "final",
            "discharge_snapshot": "2026-08-03 09:30:00",
        }
    ]
    assert running_snapshot != final_snapshot
    assert hashlib.sha256(
        json.dumps(running_snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest() != hashlib.sha256(
        json.dumps(final_snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


@pytest.mark.asyncio
async def test_workspace_batch_should_call_evaluate_once_per_record(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert service.evaluate_calls == 2
    assert service.evaluate_rule_for_visit_calls == 0
    assert workspace.job["status"] == "completed"
    assert workspace.summary is not None
    assert int(workspace.summary.get("total_records") or 0) == 2
    assert int(workspace.summary.get("rule_count") or 0) == 3
    assert int(workspace.summary.get("processed_rule_count") or 0) == 3
    assert int(((workspace.summary.get("pack_metrics") or {}).get("total_packs")) or 0) >= 1
    progress_steps = [item["step_key"] for item in workspace.progress_updates]
    assert "prepare" in progress_steps
    assert "run" in progress_steps
    assert progress_steps.index("prepare") < progress_steps.index("run")
    assert progress_steps[-1] == "aggregate"


@pytest.mark.asyncio
async def test_workspace_batch_does_not_count_legacy_executor_key_as_native(monkeypatch):
    """只有正式 unified native 结果才进入 native 观测桶。"""

    workspace = _WorkspaceStub()
    service = _ServiceStub()
    original_evaluate_document = service.evaluate_document

    async def _evaluate_document_with_legacy_executor_key(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        result = await original_evaluate_document(*args, **kwargs)
        for item in list(result.get("evaluation_results") or []):
            metadata = item.setdefault("metadata", {})
            metadata["executor_key"] = "legacy_adapter"
        return result

    service.evaluate_document = _evaluate_document_with_legacy_executor_key  # type: ignore[method-assign]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "completed"
    breakdown = dict((workspace.summary or {}).get("executor_breakdown") or {})
    assert breakdown == {"program": 6, "llm": 0, "native": 0}


@pytest.mark.parametrize(
    ("system_limit", "configured_limit", "expected_peak"),
    [(None, None, 8), (None, 1, 1), (None, 2, 2), (3, 8, 3)],
)
@pytest.mark.asyncio
async def test_workspace_parallel_batch_default_and_explicit_record_limits(
    monkeypatch,
    system_limit: Optional[int],
    configured_limit: Optional[int],
    expected_peak: int,
):
    workspace = _WorkspaceStub()
    workspace.job["run_mode"] = "parallel"
    workspace.job["record_ids"] = [f"visit-{index:03d}" for index in range(1, 9)]
    if configured_limit is None:
        workspace.job["filters"].pop("max_parallel_records", None)
    else:
        workspace.job["filters"]["max_parallel_records"] = configured_limit

    service = _ServiceStub()
    if system_limit is not None:
        service.client = SimpleNamespace(max_parallel_records=system_limit)
    concurrency = {"active": 0, "peak": 0}
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _fake_evaluate_running_final_bundle(
        *, rule_ids: List[str], **_: Any
    ) -> Dict[str, Any]:
        concurrency["active"] += 1
        concurrency["peak"] = max(concurrency["peak"], concurrency["active"])
        try:
            await asyncio.sleep(0.03)
            return {
                "evaluation_results": [
                    {
                        "rule_id": rule_id,
                        "rule_name": f"规则-{rule_id}",
                        "status": "compliant",
                        "is_compliant": True,
                        "findings": "",
                        "evidence": "",
                        "suggestion": "",
                        "confidence": 0.9,
                        "metadata": {"executor_type": "program", "tokens_used": 0},
                    }
                    for rule_id in rule_ids
                ],
                "token_usage": {"total_tokens": 0},
                "api_time": 0.03,
                "pack_metrics": {"total_packs": 1, "avg_pack_size": len(rule_ids)},
            }
        finally:
            concurrency["active"] -= 1

    monkeypatch.setattr(
        batch_worker,
        "evaluate_running_final_bundle",
        _fake_evaluate_running_final_bundle,
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert service.evaluate_calls == 0
    assert concurrency["peak"] == expected_peak
    runtime_updates = [
        item
        for item in workspace.progress_updates
        if "active_record_count" in item["progress_patch"]
    ]
    assert runtime_updates
    assert max(item["progress_patch"]["active_record_count"] for item in runtime_updates) == expected_peak
    assert {
        item["progress_patch"]["max_parallel_records"] for item in runtime_updates
    } == {expected_peak}
    assert all(
        item["processed_records"]
        + item["progress_patch"]["active_record_count"]
        + item["progress_patch"]["queued_record_count"]
        == 8
        for item in runtime_updates
    )
    assert workspace.job["status"] == "completed"


@pytest.mark.asyncio
async def test_workspace_parallel_batch_cancel_during_execution_does_not_complete_or_write_canonical(
    monkeypatch,
):
    class _CancelDuringExecutionWorkspace(_WorkspaceStub):
        def __init__(self) -> None:
            super().__init__()
            self.complete_calls = 0
            self.canonical_writes = 0

        def complete_batch_job(self, **kwargs: Any) -> None:
            self.complete_calls += 1
            self.canonical_writes += 1
            super().complete_batch_job(**kwargs)

    workspace = _CancelDuringExecutionWorkspace()
    workspace.job["run_mode"] = "parallel"
    workspace.job["record_ids"] = [f"visit-{index:03d}" for index in range(1, 5)]
    service = _ServiceStub()
    evaluation_started = asyncio.Event()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _fake_evaluate_running_final_bundle(
        *, rule_ids: List[str], **_: Any
    ) -> Dict[str, Any]:
        if not evaluation_started.is_set():
            evaluation_started.set()
            workspace.job["status"] = "canceled"
        await asyncio.sleep(0)
        return {
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "rule_name": f"规则-{rule_id}",
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {"executor_type": "program", "tokens_used": 0},
                }
                for rule_id in rule_ids
            ],
            "token_usage": {"total_tokens": 0},
            "api_time": 0.0,
            "pack_metrics": {"total_packs": 1, "avg_pack_size": len(rule_ids)},
        }

    monkeypatch.setattr(
        batch_worker,
        "evaluate_running_final_bundle",
        _fake_evaluate_running_final_bundle,
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert evaluation_started.is_set()
    assert workspace.job["status"] == "canceled"
    assert workspace.complete_calls == 0
    assert workspace.canonical_writes == 0


@pytest.mark.asyncio
async def test_workspace_batch_should_keep_uncertain_items_in_detail(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub(
        status_by_rule={
            "SC-001": "uncertain",
            "SC-002": "non_compliant",
            "SC-003": "compliant",
        }
    )

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert int(workspace.summary.get("issue_records") or 0) == 2
    assert int(workspace.summary.get("uncertain_records") or 0) == 2
    status_breakdown = dict(workspace.summary.get("status_breakdown") or {})
    assert int(status_breakdown.get("non_compliant") or 0) == 2
    assert int(status_breakdown.get("uncertain") or 0) == 2
    assert len(workspace.items) == 4
    assert {str(item.get("status") or "") for item in workspace.items} == {
        "non_compliant",
        "uncertain",
    }
    performance_profile = dict(workspace.summary.get("performance_profile") or {})
    assert performance_profile.get("schema_version") == "luxian_0609_job_perf_v1"
    assert int(performance_profile.get("result_count") or 0) == 4
    assert int(performance_profile.get("program_call_count") or 0) == 4
    assert int(performance_profile.get("llm_call_count") or 0) == 0
    assert performance_profile.get("llm_call_count_basis") == "record_execution_attribution"
    assert int(performance_profile.get("actual_llm_pack_call_count") or 0) >= 1
    assert float(performance_profile.get("sum_rule_duration_seconds") or 0) > 0
    profiled_rules = {str(item.get("rule_id") or "") for item in list(performance_profile.get("rules") or [])}
    assert {"SC-001", "SC-002"}.issubset(profiled_rules)
    assert all(isinstance(item.get("performance_profile"), dict) for item in workspace.items)
    assert all(
        str((item.get("performance_profile") or {}).get("final_status") or "")
        in {"non_compliant", "uncertain"}
        for item in workspace.items
    )
    assert service.evaluate_rule_for_visit_calls == 0


def test_batch_performance_profile_includes_deduplicated_luxian_input_profile():
    input_profile = {
        "mode": "full_text_compat",
        "basis": "programmatic_evidence_payload",
        "visit_id": "visit-001",
        "evidence_payload_available": True,
        "primary_text_char_count": 120,
        "medical_text_char_count": 300,
        "document_count": 3,
        "source_table_count": 2,
        "source_table_counts": {
            "admission_record": 1,
            "first_course_record": 1,
            "daily_course_record": 1,
        },
        "source_table_text_lengths": {
            "admission_record": 80,
            "first_course_record": 90,
            "daily_course_record": 130,
        },
        "available_family_contexts": ["basic_timeliness", "course_quality"],
        "family_profiles": {
            "basic_timeliness": {
                "document_count": 2,
                "text_char_count": 170,
                "ready_for_trimmed_context": True,
                "present_source_tables": ["admission_record", "first_course_record"],
                "missing_source_tables": ["rescue_record"],
            },
            "transfusion": {
                "document_count": 0,
                "text_char_count": 0,
                "ready_for_trimmed_context": False,
                "present_source_tables": [],
                "missing_source_tables": ["blood_application", "bloodtrans_record"],
            },
        },
    }
    items = [
        {
            "rule_id": "LX0609-01-01-01",
            "record_id": "visit-001",
            "visit_id": "visit-001",
            "status": "non_compliant",
            "metadata": {
                "executor_type": "program",
                "api_time": 0.01,
                "luxian_0609_input_profile": input_profile,
            },
        },
        {
            "rule_id": "LX0609-01-02-01",
            "record_id": "visit-001",
            "visit_id": "visit-001",
            "status": "non_compliant",
            "metadata": {
                "executor_type": "program",
                "api_time": 0.02,
                "luxian_0609_input_profile": input_profile,
            },
        },
    ]

    profile = batch_worker._build_batch_performance_profile(
        job_id="job-input-profile",
        items=items,
        total_records=1,
        customer_rule_count=2,
        execution_rule_count=2,
        wall_clock_time=0.1,
        first_result_latency=0.01,
    )

    input_summary = dict(profile.get("input_profile") or {})
    assert input_summary.get("schema_version") == "luxian_0609_input_perf_summary_v1"
    assert int(input_summary.get("record_count") or 0) == 1
    assert int(input_summary.get("document_count") or 0) == 3
    assert int(input_summary.get("primary_text_char_count") or 0) == 120
    assert int((input_summary.get("source_table_counts") or {}).get("first_course_record") or 0) == 1
    assert input_summary.get("available_family_contexts") == ["basic_timeliness", "course_quality"]
    family_profiles = dict(input_summary.get("family_profiles") or {})
    assert int((family_profiles.get("basic_timeliness") or {}).get("ready_record_count") or 0) == 1
    assert int((family_profiles.get("transfusion") or {}).get("ready_record_count") or 0) == 0
    assert all(isinstance((item.get("input_profile") or {}), dict) for item in profile.get("results") or [])


def test_document_evaluation_result_propagates_luxian_input_profile():
    service = SichuanQCService.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="unit-model")
    input_profile = {
        "visit_id": "visit-001",
        "document_count": 2,
        "source_table_counts": {"admission_record": 1, "first_course_record": 1},
    }

    result = service._build_document_evaluation_result(
        document_id="visit-001",
        document_type="终末病历",
        rules=[{"rule_id": "LX0609-01-01-01", "rule_code": "LX0609-01-01-01"}],
        orchestrated={
            "results": [
                {
                    "rule_id": "LX0609-01-01-01",
                    "rule_name": "入院记录时限",
                    "status": "non_compliant",
                    "is_compliant": False,
                }
            ],
            "total_tokens": 120,
            "total_prompt_tokens": 90,
            "total_completion_tokens": 30,
            "luxian_0609_input_profile": input_profile,
        },
    )

    assert result["luxian_0609_input_profile"] == input_profile
    assert result["token_usage"] == {
        "total_tokens": 120,
        "prompt_tokens": 90,
        "completion_tokens": 30,
    }


def test_parent_performance_profile_aggregates_child_profiles():
    child_jobs = [
        {
            "id": "child-basic",
            "status": "completed",
            "filters": {"luxian_rule_family": "basic_timeliness"},
            "summary": {
                "status_breakdown": {"non_compliant": 1},
                "performance_profile": {
                    "schema_version": "luxian_0609_job_perf_v1",
                    "total_records": 1,
                    "customer_rule_count": 3,
                    "execution_rule_count": 4,
                    "result_count": 3,
                    "wall_clock_time_seconds": 10.0,
                    "sum_rule_duration_seconds": 8.0,
                    "llm_call_count": 2,
                    "program_call_count": 1,
                    "actual_llm_pack_call_count": 1,
                    "tokens_total": 1000,
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                    "input_profile": {
                        "record_count": 1,
                        "document_count": 2,
                        "primary_text_char_count": 200,
                        "medical_text_char_count": 500,
                        "source_table_counts": {"admission_record": 1},
                        "source_table_text_lengths": {"admission_record": 200},
                        "available_family_contexts": ["basic_timeliness"],
                        "family_profiles": {
                            "basic_timeliness": {
                                "ready_record_count": 1,
                                "document_count": 2,
                                "text_char_count": 500,
                                "present_source_table_count": 1,
                                "missing_source_table_count": 0,
                            }
                        },
                    },
                },
            },
        },
        {
            "id": "child-surgery",
            "status": "completed",
            "filters": {"luxian_rule_family": "surgery_anesthesia"},
            "summary": {
                "status_breakdown": {"not_applicable": 2},
                "performance_profile": {
                    "schema_version": "luxian_0609_job_perf_v1",
                    "total_records": 1,
                    "customer_rule_count": 2,
                    "execution_rule_count": 5,
                    "result_count": 2,
                    "wall_clock_time_seconds": 7.0,
                    "sum_rule_duration_seconds": 4.0,
                    "llm_call_count": 1,
                    "program_call_count": 2,
                    "actual_llm_pack_call_count": 1,
                    "tokens_total": 500,
                    "prompt_tokens": 400,
                    "completion_tokens": 100,
                    "input_profile": {
                        "record_count": 1,
                        "document_count": 3,
                        "primary_text_char_count": 300,
                        "medical_text_char_count": 600,
                        "source_table_counts": {"operation_record": 1},
                        "source_table_text_lengths": {"operation_record": 300},
                        "available_family_contexts": ["surgery_anesthesia"],
                        "family_profiles": {
                            "surgery_anesthesia": {
                                "ready_record_count": 1,
                                "document_count": 3,
                                "text_char_count": 600,
                                "present_source_table_count": 1,
                                "missing_source_table_count": 1,
                            }
                        },
                    },
                },
            },
        },
    ]

    profile = CustomQCWorkspaceService._aggregate_child_performance_profiles(child_jobs)

    assert profile["schema_version"] == "luxian_0609_parent_job_perf_v1"
    assert profile["profiled_child_job_count"] == 2
    assert profile["customer_rule_count"] == 5
    assert profile["execution_rule_count"] == 9
    assert profile["result_count"] == 5
    assert profile["tokens_total"] == 1500
    assert profile["prompt_tokens"] == 1200
    assert profile["completion_tokens"] == 300
    assert profile["status_breakdown"] == {"non_compliant": 1, "not_applicable": 2}
    input_profile = dict(profile.get("input_profile") or {})
    assert input_profile["schema_version"] == "luxian_0609_parent_input_perf_summary_v1"
    assert input_profile["available_family_contexts"] == ["basic_timeliness", "surgery_anesthesia"]
    assert input_profile["source_table_counts"] == {"admission_record": 1, "operation_record": 1}


@pytest.mark.asyncio
async def test_workspace_batch_summary_status_breakdown_uses_result_level_counts(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub(
        status_by_rule={
            "SC-001": "non_compliant",
            "SC-002": "not_applicable",
            "SC-003": "compliant",
        }
    )

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    result_status_breakdown = dict(workspace.summary.get("status_breakdown") or {})
    assert int(result_status_breakdown.get("non_compliant") or 0) == 2
    assert int(result_status_breakdown.get("not_applicable") or 0) == 2

    record_status_breakdown = dict(workspace.summary.get("record_status_breakdown") or {})
    assert int(record_status_breakdown.get("non_compliant") or 0) == 2
    assert int(record_status_breakdown.get("not_applicable") or 0) == 0

    aggregation_status = {
        str(item.get("key") or ""): int(item.get("count") or 0)
        for item in ((workspace.summary.get("result_aggregation") or {}).get("status_breakdown") or [])
    }
    assert aggregation_status.get("not_applicable") == 2


def test_result_aggregation_should_hide_internal_evidence_phrases():
    aggregation = batch_worker._build_result_aggregation(
        [
            {
                "rule_id": "LX0609-02-01-03",
                "rule_name": "查房记录：病情稳定患者3天内无查房病程记录",
                "status": "not_applicable",
                "evidence": (
                    "适用性：未发现与本质控点直接相关的触发事实\n"
                    "判定依据：未发现与本质控点直接相关的适用事件\n"
                    "映射执行规则：SC-051、CL-231\n"
                    "证据模板：通用质控"
                ),
            }
        ]
    )

    clusters = aggregation.get("clusters") or []
    assert len(clusters) == 1
    serialized = json.dumps(clusters, ensure_ascii=False)
    assert "未发现与本质控点直接相关的触发事实" in serialized
    assert "判定依据" not in serialized
    assert "映射执行规则" not in serialized
    assert "证据模板" not in serialized


@pytest.mark.asyncio
async def test_workspace_batch_formal_full_should_persist_postprocess_fields(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = ["2207717"]
    workspace.job["filters"] = {
        "rule_ids": [
            "SC-036",
            "SC-020",
            "SC-118",
            "SC-123",
            "SC-125",
            "SC-070",
            "SC-074",
            "SC-107",
            "SC-146",
        ],
        "rule_set_key": "sc_content_full_v1",
        "validation_mode": "formal_fast_screen_full",
        "execution_strategy": "fast_screen",
        "bucket_strategy": "fixed_packs",
        "quality_profile": "throughput_v1",
        "date_field": "discharge",
    }
    service = _FormalPostprocessServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _fake_adjudicate(rows: List[Dict[str, Any]], **_: Any) -> List[Dict[str, Any]]:
        next_rows: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            first_pass_display = str(item.get("display_status") or "")
            item["first_pass_status"] = str(item.get("status") or "")
            item["first_pass_display_status"] = first_pass_display
            if first_pass_display == "qc_review_candidate":
                item.update(
                    {
                        "display_status": "rejected_by_system",
                        "display_bucket": "系统驳回",
                        "postprocess_label": "rejected_by_system",
                        "postprocess_reason": "测试二审裁决：证据不足，系统驳回。",
                        "adjudicated_display_status": "rejected_by_system",
                        "adjudicator_reason": "证据不足，不能作为正式缺陷。",
                        "adjudicator_supporting_quote": "",
                        "adjudicator_confidence": 0.7,
                        "rule_requirement_match": "not_matched",
                        "can_show_as_defect": False,
                        "can_show_to_doctor": False,
                        "internal_only": True,
                    }
                )
            next_rows.append(item)
        return next_rows

    monkeypatch.setattr(batch_worker, "adjudicate_postprocessed_qc_results", _fake_adjudicate)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert len(workspace.items) == 9
    postprocess_summary = dict(workspace.summary.get("postprocess_summary") or {})
    assert postprocess_summary["confirmed_defect_count"] == 0
    assert postprocess_summary["qc_review_candidate_count"] == 0
    assert postprocess_summary["needs_review_count"] == 0
    assert postprocess_summary["data_quality_gap_count"] == 5
    assert postprocess_summary["rejected_by_system_count"] == 4
    assert postprocess_summary["technical_error_internal_count"] == 0
    assert workspace.summary["confirmed_defect_count"] == 0
    assert workspace.summary["qc_review_candidate_count"] == 0
    assert workspace.summary["needs_review_count"] == 0
    assert workspace.summary["data_quality_gap_count"] == 5
    assert workspace.summary["rejected_by_system_count"] == 4
    sc036 = next(item for item in workspace.items if item["rule_id"] == "SC-036")
    assert sc036["status"] == "non_compliant"
    assert sc036["display_status"] == "rejected_by_system"
    assert sc036["can_show_as_defect"] is False
    assert sc036["postprocess_mode"] == "formal_final_online"
    assert int(workspace.summary.get("issue_records") or 0) == 0
    assert int(workspace.summary.get("uncertain_records") or 0) == 0


@pytest.mark.asyncio
async def test_workspace_batch_final_should_prefer_bundle_path(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub(
        status_by_rule={
            "SC-001": "non_compliant",
            "SC-002": "uncertain",
            "SC-003": "compliant",
        }
    )

    def _hydrate_with_bundle_keys(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        hydrated: List[Dict[str, Any]] = []
        for item in records:
            hydrated.append(
                {
                    **item,
                    "institute_id": "HOSP-001",
                    "patient_id": f"PAT-{item.get('visit_id')}",
                    "medical_text": f"fallback-text-{item.get('visit_id')}",
                }
            )
        return hydrated

    workspace.hydrate_records_with_medical_text = _hydrate_with_bundle_keys  # type: ignore[assignment]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _fake_evaluate_running_final_bundle(
        *,
        qc_service,
        scene: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        rule_ids: List[str],
        schema: str = "public",
        **_: Any,
    ) -> Dict[str, Any]:
        evaluation_results: List[Dict[str, Any]] = []
        total_tokens = 0
        total_api_time = 0.0
        for rule_id in rule_ids:
            rule_result = await qc_service.evaluate_rule_for_visit(
                rule_id=rule_id,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                bundle_schema=schema,
            )
            evaluation_results.extend(list(rule_result.get("evaluation_results") or []))
            total_tokens += int(((rule_result.get("token_usage") or {}).get("total_tokens")) or 0)
            total_api_time += float(rule_result.get("api_time") or 0.0)
        return {
            "evaluation_results": evaluation_results,
            "token_usage": {"total_tokens": total_tokens},
            "api_time": total_api_time,
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": max(1, len(rule_ids)),
                "fallback_packs": 0,
                "pack_parse_retry_count": 0,
                "single_rule_retries": 0,
                "context_tokens_estimate": 240,
            },
        }

    monkeypatch.setattr(batch_worker, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert service.evaluate_calls == 0
    assert service.evaluate_rule_for_visit_calls == 6
    assert {str(call.get("bundle_schema") or "") for call in service.evaluate_rule_for_visit_args} == {"public"}
    assert int(workspace.summary.get("issue_records") or 0) == 2
    assert int(workspace.summary.get("uncertain_records") or 0) == 2


@pytest.mark.asyncio
async def test_workspace_batch_all_should_use_final_bundle_when_record_scope_is_final(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["scope"] = "all"
    service = _ServiceStub(
        status_by_rule={
            "SC-001": "non_compliant",
            "SC-002": "uncertain",
            "SC-003": "compliant",
        }
    )

    def _collect_records_with_final_scope(
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[List[str]] = None,
        record_refs: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        ids = list(record_ids or [])
        return [
            {
                "record_id": rid,
                "visit_id": rid,
                "patient_name": f"患者{idx + 1}",
                "department": "骨科",
                "scope": "final",
            }
            for idx, rid in enumerate(ids)
        ]

    def _hydrate_with_bundle_keys(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **item,
                "institute_id": "HOSP-001",
                "patient_id": f"PAT-{item.get('visit_id')}",
                "medical_text": f"fallback-text-{item.get('visit_id')}",
            }
            for item in records
        ]

    workspace.collect_records = _collect_records_with_final_scope  # type: ignore[assignment]
    workspace.hydrate_records_with_medical_text = _hydrate_with_bundle_keys  # type: ignore[assignment]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _fake_evaluate_running_final_bundle(
        *,
        qc_service,
        scene: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        rule_ids: List[str],
        schema: str = "public",
        **_: Any,
    ) -> Dict[str, Any]:
        assert scene == "final"
        evaluation_results: List[Dict[str, Any]] = []
        total_tokens = 0
        total_api_time = 0.0
        for rule_id in rule_ids:
            rule_result = await qc_service.evaluate_rule_for_visit(
                rule_id=rule_id,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                bundle_schema=schema,
            )
            evaluation_results.extend(list(rule_result.get("evaluation_results") or []))
            total_tokens += int(((rule_result.get("token_usage") or {}).get("total_tokens")) or 0)
            total_api_time += float(rule_result.get("api_time") or 0.0)
        return {
            "evaluation_results": evaluation_results,
            "token_usage": {"total_tokens": total_tokens},
            "api_time": total_api_time,
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": max(1, len(rule_ids)),
                "fallback_packs": 0,
                "pack_parse_retry_count": 0,
                "single_rule_retries": 0,
                "context_tokens_estimate": 240,
            },
        }

    monkeypatch.setattr(batch_worker, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert service.evaluate_calls == 0
    assert service.evaluate_rule_for_visit_calls == 6


@pytest.mark.asyncio
async def test_sample_pool_single_rule_records_should_prefer_rule_level_visit_eval(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["scope"] = "all"
    workspace.job["filters"] = {
        "rule_ids": ["SC-039", "SC-069"],
        "source": "manual_problem_sample_pool_second_batch_regression",
        "validation_mode": "sc",
        "record_rule_map": {
            "visit-001": ["SC-039"],
            "visit-002": ["SC-069"],
        },
        "execution_strategy": "standard",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "max_refine_candidates": 0,
        "date_field": "admission",
    }
    workspace.job["record_ids"] = ["visit-001", "visit-002"]
    service = _ServiceStub(status_by_rule={"SC-039": "non_compliant", "SC-069": "non_compliant"})

    def _collect_records_with_final_scope(
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[List[str]] = None,
        record_refs: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        ids = list(record_ids or [])
        return [
            {
                "record_id": rid,
                "visit_id": rid,
                "patient_name": f"患者{idx + 1}",
                "department": "内科",
                "scope": "final",
            }
            for idx, rid in enumerate(ids)
        ]

    def _hydrate_with_bundle_keys(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **item,
                "institute_id": "HOSP-001",
                "patient_id": f"PAT-{item.get('visit_id')}",
                "medical_text": "",
            }
            for item in records
        ]

    workspace.collect_records = _collect_records_with_final_scope  # type: ignore[assignment]
    workspace.hydrate_records_with_medical_text = _hydrate_with_bundle_keys  # type: ignore[assignment]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    async def _should_not_call_bundle_eval(**kwargs: Any) -> Dict[str, Any]:
        raise AssertionError("单病历单规则样本验证应优先走 evaluate_rule_for_visit")

    monkeypatch.setattr(batch_worker, "evaluate_running_final_bundle", _should_not_call_bundle_eval)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert service.evaluate_rule_for_visit_calls == 2
    assert len(workspace.items) == 2
    assert {str(item.get("rule_id")) for item in workspace.items} == {"SC-039", "SC-069"}
    assert int(workspace.summary.get("issue_records") or 0) == 2


@pytest.mark.asyncio
async def test_workspace_batch_final_fast_screen_should_use_fast_screen_path(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["SC-023", "SC-024"],
        "rule_set_key": "sc_content_fast_v1",
        "execution_strategy": "fast_screen",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "max_refine_candidates": 0,
        "date_field": "discharge",
    }
    service = _ServiceStub(status_by_rule={"SC-023": "uncertain", "SC-024": "uncertain"})

    def _hydrate_with_bundle_keys(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **item,
                "institute_id": "HOSP-001",
                "patient_id": f"PAT-{item.get('visit_id')}",
                "medical_text": f"fast-screen-text-{item.get('visit_id')}",
            }
            for item in records
        ]

    workspace.hydrate_records_with_medical_text = _hydrate_with_bundle_keys  # type: ignore[assignment]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    fast_screen_calls: List[Dict[str, Any]] = []

    async def _fake_run_final_fast_screen(**kwargs: Any) -> Dict[str, Any]:
        fast_screen_calls.append(dict(kwargs))
        return {
            "evaluation_results": [
                {
                    "rule_id": "SC-023",
                    "rule_name": "规则-SC-023",
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "疑点",
                    "evidence": "证据",
                    "suggestion": "复核",
                    "confidence": 0.5,
                    "metadata": {
                        "executor_type": "llm",
                        "tokens_used": 100,
                        "api_time": 0.1,
                        "model_version": "test-model",
                        "cache_hit": False,
                    },
                },
                {
                    "rule_id": "SC-024",
                    "rule_name": "规则-SC-024",
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "疑点",
                    "evidence": "证据",
                    "suggestion": "复核",
                    "confidence": 0.5,
                    "metadata": {
                        "executor_type": "llm",
                        "tokens_used": 100,
                        "api_time": 0.1,
                        "model_version": "test-model",
                        "cache_hit": False,
                    },
                },
            ],
            "token_usage": {"total_tokens": 200, "prompt_tokens": 160, "completion_tokens": 40},
            "api_time": 0.2,
            "first_result_latency": 0.05,
            "first_result_source": "first_course_features",
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": 2.0,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "pack_parse_retry_count": 0,
                "context_tokens_estimate": 300,
                "bucket_strategy": "fixed_packs",
                "batch_output_mode": "minimal",
            },
            "cot_summary": {"disabled_calls": 1},
            "refine_summary": {"enabled": False},
        }

    monkeypatch.setattr(batch_worker, "run_final_fast_screen", _fake_run_final_fast_screen)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert len(fast_screen_calls) == 2
    assert all("pack_concurrency" not in call for call in fast_screen_calls)
    assert service.evaluate_calls == 0
    assert workspace.summary is not None
    assert workspace.summary.get("execution_strategy") == "fast_screen"
    assert int((workspace.summary.get("pack_metrics") or {}).get("total_packs") or 0) == 2


@pytest.mark.asyncio
async def test_workspace_batch_customer_final_fast_screen_should_bypass_sc_fixed_packs(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["CL-001", "CL-002"],
        "rule_set_key": "customer_luxian_full_v1",
        "validation_mode": "customer",
        "execution_strategy": "fast_screen",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "fixed_packs",
        "batch_output_mode": "minimal",
        "enable_selective_refine": False,
        "max_refine_candidates": 0,
        "date_field": "discharge",
    }
    service = _ServiceStub()

    def _hydrate_with_bundle_keys(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **item,
                "institute_id": "HOSP-001",
                "patient_id": f"PAT-{item.get('visit_id')}",
                "medical_text": f"customer-text-{item.get('visit_id')}",
            }
            for item in records
        ]

    workspace.hydrate_records_with_medical_text = _hydrate_with_bundle_keys  # type: ignore[assignment]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _fake_get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _fake_get_qc_service)

    fast_screen_calls: List[Dict[str, Any]] = []
    bundle_calls: List[Dict[str, Any]] = []

    async def _should_not_call_fast_screen(**kwargs: Any) -> Dict[str, Any]:
        fast_screen_calls.append(dict(kwargs))
        raise AssertionError("customer 全量规则不应走 SC fixed fast_screen 路径")

    async def _fake_evaluate_running_final_bundle(**kwargs: Any) -> Dict[str, Any]:
        bundle_calls.append(dict(kwargs))
        return {
            "evaluation_results": [
                {
                    "rule_id": "CL-001",
                    "rule_name": "规则-CL-001",
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "不适用",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {
                        "executor_type": "llm",
                        "tokens_used": 0,
                        "api_time": 0.0,
                        "model_version": "test-model",
                        "cache_hit": False,
                    },
                },
                {
                    "rule_id": "CL-002",
                    "rule_name": "规则-CL-002",
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "不适用",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.9,
                    "metadata": {
                        "executor_type": "llm",
                        "tokens_used": 0,
                        "api_time": 0.0,
                        "model_version": "test-model",
                        "cache_hit": False,
                    },
                },
            ],
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "api_time": 0.0,
            "first_result_latency": 0.0,
            "first_result_source": "final_bundle",
            "pack_metrics": {
                "total_packs": 1,
                "avg_pack_size": 2.0,
                "fallback_packs": 0,
                "single_rule_retries": 0,
                "pack_parse_retry_count": 0,
                "context_tokens_estimate": 0,
                "bucket_strategy": "domain_only",
                "batch_output_mode": "minimal",
            },
            "cot_summary": {"disabled_calls": 0},
            "refine_summary": {"enabled": False},
        }

    monkeypatch.setattr(batch_worker, "run_final_fast_screen", _should_not_call_fast_screen)
    monkeypatch.setattr(batch_worker, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert fast_screen_calls == []
    assert len(bundle_calls) == 2
    assert workspace.job["status"] == "completed"
    assert workspace.summary is not None
    assert int((workspace.summary.get("pack_metrics") or {}).get("total_packs") or 0) == 2


@pytest.mark.asyncio
async def test_create_workspace_batch_job_should_resolve_content_rule_set(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    request = SimpleNamespace(state=SimpleNamespace())
    payload = qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_set_key="sc_content_v1",
        rule_ids=["SC-999"],
        scope="final",
        date_field="discharge",
        record_ids=["visit-001"],
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=request,  # type: ignore[arg-type]
        payload=payload,
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None
    filters = dict(workspace.created_job.get("filters") or {})
    assert filters["rule_set_key"] == "sc_content_v1"
    assert filters["rule_set_name"] == "内涵质控首批 v1"
    assert filters["quality_profile"] == "effect_priority_v1"
    assert filters["bucket_strategy"] == "domain_family"
    assert filters["batch_output_mode"] == "minimal"
    assert filters["enable_selective_refine"] is True
    assert filters["max_refine_candidates"] == 3
    assert filters["run_mode"] == "parallel"
    assert filters["rule_ids"] == list(SC_CONTENT_V1_RULE_IDS)
    assert workspace.created_job["run_mode"] == "parallel"
    assert response["data"]["draft_ids"] == list(SC_CONTENT_V1_RULE_IDS)


@pytest.mark.asyncio
async def test_create_workspace_batch_job_rejects_luxian_legacy_record_ids_before_collect(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    collect_calls: List[Dict[str, Any]] = []

    def collect_records(**kwargs: Any) -> List[Dict[str, Any]]:
        collect_calls.append(kwargs)
        return []

    workspace.collect_records = collect_records  # type: ignore[method-assign]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)

    with pytest.raises(HTTPException) as error:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="all",
                record_ids=["VISIT-1"],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )

    assert error.value.status_code == 422
    assert "record_refs" in str(error.value.detail)
    assert collect_calls == []
    assert workspace.created_job is None


@pytest.mark.asyncio
async def test_create_workspace_batch_job_freezes_full_visit_filter_scope(monkeypatch):
    workspace = _WorkspaceStub()
    collect_calls: List[Dict[str, Any]] = []
    matched_records = [
        {
            "institute_id": "HOSP-001",
            "patient_id": f"PAT-{index}",
            "visit_id": f"VISIT-{index}",
            "scope": "running",
            "admission_datetime": "2026-05-10 08:00:00",
            "discharge_datetime": "",
        }
        for index in range(1, 4)
    ]

    def collect_records(**kwargs: Any) -> List[Dict[str, Any]]:
        collect_calls.append(kwargs)
        return list(matched_records)

    workspace.collect_records = collect_records  # type: ignore[method-assign]
    submitted_tasks: List[Dict[str, Any]] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda name, func, *args: submitted_tasks.append(
            {"name": name, "func": func, "args": args}
        ),
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
            scope="running",
            department="重症医学科",
            date_field="visit",
            start_date="2026-05-01",
            end_date="2026-05-31",
            keyword="待复核",
        ),
        qc_service=_ServiceStub(),  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert collect_calls == [
        {
            "scope": "running",
            "department": "重症医学科",
            "doctor": None,
            "date_field": "visit",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "keyword": "待复核",
            "record_ids": None,
            "record_refs": None,
        }
    ]
    assert workspace.created_job is not None
    assert workspace.created_job["record_refs"] == [
        CaseRef.from_mapping(item) for item in matched_records
    ]
    assert workspace.created_job["filters"]["date_field"] == "visit"
    assert workspace.created_job["filters"]["record_refs"] == [
        CaseRef.from_mapping(item).as_dict() for item in matched_records
    ]
    assert len(submitted_tasks) == 1


@pytest.mark.asyncio
async def test_create_workspace_batch_job_preserves_verified_today_inpatient_scope(monkeypatch):
    workspace = _WorkspaceStub()
    collect_calls: List[Dict[str, Any]] = []
    matched_records = [
        {
            "institute_id": "HOSP-001",
            "patient_id": "PAT-001",
            "visit_id": "VISIT-001",
            "scope": "running",
            "admission_datetime": "2026-09-03 08:00:00",
            "discharge_datetime": "",
        }
    ]

    def collect_records(**kwargs: Any) -> List[Dict[str, Any]]:
        collect_calls.append(kwargs)
        return list(matched_records)

    workspace.collect_records = collect_records  # type: ignore[method-assign]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_args: None)

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
            scope="running",
            sync_scope="today_inpatient",
            department="重症医学科",
            doctor="陈医师",
            date_field="visit",
        ),
        qc_service=_ServiceStub(),  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert collect_calls == [
        {
            "scope": "running",
            "department": "重症医学科",
            "doctor": "陈医师",
            "date_field": "visit",
            "start_date": None,
            "end_date": None,
            "keyword": None,
            "record_ids": None,
            "record_refs": None,
            "sync_scope": "today_inpatient",
        }
    ]
    assert workspace.created_job is not None
    assert workspace.created_job["filters"]["sync_scope"] == "today_inpatient"
    assert workspace.created_job["filters"]["idempotency_payload"]["sync_scope"] == "today_inpatient"


@pytest.mark.asyncio
async def test_create_workspace_batch_job_rejects_partial_or_duplicate_explicit_record_refs(
    monkeypatch,
):
    requested_refs = [
        {"institute_id": "HOSP-001", "patient_id": "PAT-1", "visit_id": "VISIT-1"},
        {"institute_id": "HOSP-001", "patient_id": "PAT-2", "visit_id": "VISIT-2"},
    ]

    partial_workspace = _WorkspaceStub()
    partial_workspace.collect_records = lambda **_: [  # type: ignore[method-assign]
        {**requested_refs[0], "scope": "final"}
    ]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: partial_workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_args: None)

    with pytest.raises(HTTPException) as partial_error:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="all",
                record_refs=requested_refs,
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )
    assert partial_error.value.status_code == 422
    assert partial_workspace.created_job is None

    duplicate_workspace = _WorkspaceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: duplicate_workspace)
    with pytest.raises(HTTPException) as duplicate_error:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                scope="all",
                record_refs=[requested_refs[0], dict(requested_refs[0])],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )
    assert duplicate_error.value.status_code == 422
    assert duplicate_workspace.created_job is None


@pytest.mark.asyncio
async def test_create_workspace_batch_job_accepts_reordered_complete_explicit_record_refs(
    monkeypatch,
):
    requested_refs = [
        {"institute_id": "HOSP-001", "patient_id": "PAT-1", "visit_id": "VISIT-1"},
        {"institute_id": "HOSP-001", "patient_id": "PAT-2", "visit_id": "VISIT-2"},
    ]
    workspace = _WorkspaceStub()
    workspace.collect_records = lambda **_: [  # type: ignore[method-assign]
        {**record_ref, "scope": "final"} for record_ref in reversed(requested_refs)
    ]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_args: None)

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
            scope="all",
            record_refs=requested_refs,
        ),
        qc_service=_ServiceStub(),  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None


@pytest.mark.asyncio
async def test_create_workspace_batch_job_accepts_native_luxian_customer_ids_without_legacy_mapping(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    workspace.collect_records = lambda **_: [  # type: ignore[method-assign]
        {
            "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-001",
            "record_id": "visit-001",
            "visit_id": "visit-001",
            "scope": "final",
            "admission_datetime": "2026-06-01 08:00:00",
            "discharge_datetime": "2026-06-13 18:00:00",
        },
        {
            "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-002",
            "record_id": "visit-002",
            "visit_id": "visit-002",
            "scope": "running",
            "admission_datetime": "2026-06-02 08:00:00",
            "discharge_datetime": "",
        },
    ]
    service = _ServiceStub()
    submitted_tasks: List[Dict[str, Any]] = []

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda name, func, *args: submitted_tasks.append(
            {"name": name, "func": func, "args": args}
        ),
    )

    native_rule_ids = ["LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"]
    request = SimpleNamespace(state=SimpleNamespace())
    payload = qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        rule_ids=native_rule_ids,
        scope="all",
        date_field="admission",
        record_refs=[
            {
                "institute_id": "HOSP-001",
                "patient_id": "PAT-visit-001",
                "visit_id": "visit-001",
            },
            {
                "institute_id": "HOSP-001",
                "patient_id": "PAT-visit-002",
                "visit_id": "visit-002",
            },
        ],
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=request,  # type: ignore[arg-type]
        payload=payload,
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None
    filters = dict(workspace.created_job.get("filters") or {})
    assert workspace.created_job["scope"] == "all"
    assert filters["rule_ids"] == native_rule_ids
    assert filters["selected_rule_ids"] == native_rule_ids
    assert filters["scoped_customer_rule_ids"] == native_rule_ids
    assert filters["validation_mode"] == "programmatic"
    assert filters["customer_rule_count"] == filters["execution_rule_count"] == 3
    task_frozen_date = filters["task_frozen_date"]
    assert date.fromisoformat(task_frozen_date).isoformat() == task_frozen_date
    assert filters["record_evaluation_snapshot"] == [
        {
            "record_id": "visit-001",
            "record_scene": "final",
            "admission_datetime": "2026-06-01 08:00:00",
            "discharge_datetime": "2026-06-13 18:00:00",
            "evaluation_horizon": "2026-06-13",
            "evaluation_basis": "discharge_datetime",
            "resolution_status": "resolved",
            "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-001",
            "visit_id": "visit-001",
            "record_key": CaseRef(
                "HOSP-001", "PAT-visit-001", "visit-001"
            ).as_key(),
        },
        {
            "record_id": "visit-002",
            "record_scene": "running",
            "admission_datetime": "2026-06-02 08:00:00",
            "discharge_datetime": "",
            "evaluation_horizon": task_frozen_date,
            "evaluation_basis": "task_frozen_date",
            "resolution_status": "resolved",
            "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-002",
            "visit_id": "visit-002",
            "record_key": CaseRef(
                "HOSP-001", "PAT-visit-002", "visit-002"
            ).as_key(),
        },
    ]
    assert (
        filters["idempotency_payload"]["record_evaluation_snapshot"]
        == filters["record_evaluation_snapshot"]
    )
    assert "evaluation_as_of_date" not in filters
    assert filters["record_rule_map"] == {
        CaseRef("HOSP-001", "PAT-visit-001", "visit-001").as_key(): native_rule_ids,
        CaseRef("HOSP-001", "PAT-visit-002", "visit-002").as_key(): native_rule_ids,
    }
    assert workspace.created_job["draft_ids"] == native_rule_ids
    assert response["data"]["draft_ids"] == native_rule_ids
    serialized = json.dumps(workspace.created_job, ensure_ascii=False, sort_keys=True)
    assert all(
        legacy_rule_id not in serialized
        for legacy_rule_id in ("CL-181", "SC-081", "LX-025", "SC-095", "SC-102", "LXE-33")
    )
    assert len(submitted_tasks) == 1


@pytest.mark.asyncio
async def test_create_workspace_batch_job_full_luxian_set_uses_current_customer_scope(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    service = _ServiceStub()
    submitted_tasks: List[Dict[str, Any]] = []
    customer_rule_ids = [f"LX0609-{index:03d}" for index in range(1, 76)]
    pending_rule_ids = [
        "LX0609-04-02-04",
        "LX0609-05-01-01",
        "LX0609-07-04-02",
        "LX0609-05-01-04",
        "LX0609-05-03-01",
        "LX0609-10-03-01",
    ]
    customer_rule_ids = [
        rule_id
        for rule_id in customer_rule_ids
        if rule_id not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    executable_rule_ids = [
        rule_id for rule_id in customer_rule_ids if rule_id not in pending_rule_ids
    ]

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda name, func, *args: submitted_tasks.append(
            {"name": name, "func": func, "args": args}
        ),
    )
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _luxian_native_settings(),
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
            scope="all",
            date_field="admission",
            record_refs=[
                {
                    "institute_id": "HOSP-001",
                    "patient_id": "PAT-visit-001",
                    "visit_id": "visit-001",
                },
                {
                    "institute_id": "HOSP-001",
                    "patient_id": "PAT-visit-002",
                    "visit_id": "visit-002",
                },
            ],
        ),
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None
    filters = dict(workspace.created_job.get("filters") or {})
    assert filters["rule_ids"] == executable_rule_ids
    assert filters["selected_rule_ids"] == customer_rule_ids
    assert filters["scoped_customer_rule_ids"] == customer_rule_ids
    assert filters["active_customer_rule_ids"] == executable_rule_ids
    assert filters["pending_customer_rule_ids"] == pending_rule_ids
    assert filters["idempotency_payload"]["customer_rule_ids"] == customer_rule_ids
    assert filters["customer_rule_count"] == 70
    assert filters["execution_rule_count"] == 64
    assert filters["pending_rule_count"] == 6
    assert {"LX0609-09-02-01", "LX0609-08-01-01", "LX0609-08-02-01", "LX0609-10-01-01"}.issubset(
        filters["active_customer_rule_ids"]
    )
    assert "LX0609-05-03-01" in filters["pending_customer_rule_ids"]
    assert all(
        selected == customer_rule_ids
        for selected in dict(filters["record_rule_map"]).values()
    )
    assert workspace.created_job["draft_ids"] == executable_rule_ids
    assert len(submitted_tasks) == 1


@pytest.mark.asyncio
async def test_create_workspace_batch_job_idempotency_separates_pending_delivery_scope(
    monkeypatch,
):
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: _luxian_native_settings())
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: None)

    async def _create(selected_rule_ids: List[str]) -> Dict[str, Any]:
        workspace = _WorkspaceStub()
        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
        response = await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                rule_ids=selected_rule_ids,
                scope="all",
                date_field="admission",
                record_refs=[
                    {
                        "institute_id": "HOSP-001",
                        "patient_id": "PAT-visit-001",
                        "visit_id": "visit-001",
                    }
                ],
            ),
            qc_service=_ServiceStub(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )
        assert response["success"] is True
        return dict(workspace.created_job["filters"])

    active_filters = await _create(["LX0609-03-01-01"])
    pending_filters = await _create(["LX0609-03-01-01", "LX0609-07-04-02"])

    assert active_filters["rule_ids"] == pending_filters["rule_ids"] == ["LX0609-03-01-01"]
    assert active_filters["idempotency_payload"]["customer_rule_ids"] == ["LX0609-03-01-01"]
    assert pending_filters["idempotency_payload"]["customer_rule_ids"] == [
        "LX0609-03-01-01",
        "LX0609-07-04-02",
    ]
    assert active_filters["idempotency_key"] != pending_filters["idempotency_key"]


@pytest.mark.asyncio
async def test_create_luxian_batch_single_family_off_fails_before_sc_source_check(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    source_guard_calls: List[str] = []

    class _CreateGuardService(_ServiceStub):
        def assert_sc_rule_source_ready(
            self, *, context: str, block_batch: bool = False
        ) -> Dict[str, Any]:
            source_guard_calls.append(context)
            return {"sc_source": "pg_governance"}

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: None)
    monkeypatch.setattr(
        qc_sichuan,
        "get_settings",
        lambda: _luxian_native_settings(
            LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=False
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
                rule_ids=["LX0609-07-01-02"],
                scope="all",
                record_refs=[
                    {
                        "institute_id": "HOSP-001",
                        "patient_id": "PAT-visit-001",
                        "visit_id": "visit-001",
                    }
                ],
            ),
            qc_service=_CreateGuardService(),  # type: ignore[arg-type]
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 503
    assert "正式质控禁止兼容执行" in str(exc_info.value.detail)
    assert source_guard_calls == []
    assert workspace.created_job is None


@pytest.mark.asyncio
@pytest.mark.parametrize("validation_mode", ["programmatic", "customer"])
async def test_full_luxian_batch_worker_uses_unified_customer_package_entry(
    monkeypatch,
    validation_mode: str,
):
    workspace = _WorkspaceStub()
    customer_rule_ids = [
        f"LX0609-{index:03d}"
        for index in range(1, 50)
        if f"LX0609-{index:03d}" not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    workspace.job["filters"] = {
        "rule_ids": customer_rule_ids,
        "selected_rule_ids": customer_rule_ids,
        "scoped_customer_rule_ids": customer_rule_ids,
        "record_rule_map": {
            "visit-001": customer_rule_ids,
            "visit-002": customer_rule_ids,
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": validation_mode,
    }
    captured: List[Dict[str, Any]] = []

    class _CustomerPackageService(_ServiceStub):
        def assert_sc_rule_source_ready(self, **_: Any) -> Dict[str, Any]:
            raise AssertionError("全原生0609批任务不应依赖旧SC规则来源")

        def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
            raise AssertionError(f"全原生0609批任务不应查询旧规则: {rule_id}")

        async def evaluate_document_with_rules(self, **_: Any) -> Dict[str, Any]:
            raise AssertionError("0609批任务应统一走 customer package bundle 入口")

        async def evaluate_running_final_bundle_input(self, **kwargs: Any) -> Dict[str, Any]:
            captured.append(
                {
                    "rule_ids": list(kwargs["rule_ids"]),
                    "scene": str(kwargs["bundle"].get("scene") or ""),
                    "data_quality_flags": list(
                        kwargs["bundle"].get("data_quality_flags") or []
                    ),
                }
            )
            return {
                "evaluation_results": [
                    {
                        "rule_id": rule_id,
                        "status": "compliant",
                        "is_compliant": True,
                        "reason_code": "requirement_satisfied",
                        "metadata": {
                            "execution_source": "lx0609_native",
                            "executor_type": "program",
                        },
                    }
                    for rule_id in kwargs["rule_ids"]
                ],
                "token_usage": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                },
            }

    service = _CustomerPackageService()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        _luxian_native_settings,
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "completed"
    assert len(captured) == 2
    assert all(item["rule_ids"] == customer_rule_ids for item in captured)
    assert all(item["scene"] == "final" for item in captured)
    assert all("text_unavailable" in item["data_quality_flags"] for item in captured)
    assert len(workspace.items) == 88
    assert {str(item.get("rule_id") or "") for item in workspace.items} == set(
        customer_rule_ids
    )
    assert {
        str(item.get("reason_code") or "") for item in workspace.items
    } == {"requirement_satisfied"}


@pytest.mark.asyncio
async def test_luxian_batch_worker_uses_record_scene_and_records_loaded_fallback(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["scope"] = "all"
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-01-01-01"],
        "selected_rule_ids": ["LX0609-01-01-01"],
        "scoped_customer_rule_ids": ["LX0609-01-01-01"],
        "record_rule_map": {
            "visit-001": ["LX0609-01-01-01"],
            "visit-002": ["LX0609-01-01-01"],
            "visit-003": ["LX0609-01-01-01"],
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "record_evaluation_snapshot": [
            {
                "record_id": "visit-001",
                "record_scene": "final",
                "admission_datetime": "2026-06-01 08:00:00",
                "discharge_datetime": "2026-06-13 18:00:00",
                "evaluation_horizon": "2026-06-13",
                "evaluation_basis": "discharge_datetime",
                "resolution_status": "resolved",
            },
            {
                "record_id": "visit-002",
                "record_scene": "running",
                "admission_datetime": "2026-06-02 08:00:00",
                "discharge_datetime": "",
                "evaluation_horizon": "2026-08-04",
                "evaluation_basis": "task_frozen_date",
                "resolution_status": "resolved",
            },
            {
                "record_id": "visit-003",
                "record_scene": "unknown",
                "admission_datetime": "2026-06-03 08:00:00",
                "discharge_datetime": "",
                "evaluation_horizon": "",
                "evaluation_basis": "",
                "resolution_status": "scene_uncertain",
            },
        ],
    }

    def _collect_mixed_records(**_: Any) -> List[Dict[str, Any]]:
        return [
            {"record_id": "visit-001", "visit_id": "visit-001", "scope": "final"},
            {"record_id": "visit-002", "visit_id": "visit-002", "scope": "running"},
            {"record_id": "visit-003", "visit_id": "visit-003", "scope": "unknown"},
        ]

    def _hydrate(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                **record,
                "institute_id": "HOSP-001",
                "patient_id": f"PAT-{record['visit_id']}",
                "medical_text": "fallback text",
            }
            for record in records
        ]

    workspace.collect_records = _collect_mixed_records  # type: ignore[assignment]
    workspace.hydrate_records_with_medical_text = _hydrate  # type: ignore[assignment]
    load_calls: List[Dict[str, str]] = []

    def _load_bundle(
        *, scene: str, visit_id: str, schema: str, **_: Any
    ) -> Dict[str, Any]:
        load_calls.append(
            {"visit_id": visit_id, "scene": scene, "schema": schema}
        )
        if visit_id == "visit-001" and scene == "final":
            raise RuntimeError("final bundle暂不可用")
        return {"scene": "stale-scene", "medical_text": "bundle text"}

    captured: List[Dict[str, Any]] = []

    class _SceneService(_ServiceStub):
        async def evaluate_running_final_bundle_input(self, **kwargs: Any) -> Dict[str, Any]:
            captured.append(
                {
                    "visit_id": kwargs["bundle"]["visit_id"],
                    "scene": kwargs["bundle"]["scene"],
                    "scene_resolution": dict(kwargs["bundle"]["scene_resolution"]),
                    "evaluation_horizon_snapshot": dict(
                        kwargs["bundle"]["evaluation_horizon_snapshot"]
                    ),
                    "evaluation_as_of_date": kwargs["evaluation_as_of_date"],
                    "evaluation_horizon_policy": kwargs[
                        "evaluation_horizon_policy"
                    ],
                }
            )
            return {
                "evaluation_results": [
                    {
                        "rule_id": "LX0609-01-01-01",
                        "status": "compliant",
                        "is_compliant": True,
                        "reason_code": "requirement_satisfied",
                        "metadata": {"execution_source": "lx0609_native"},
                    }
                ],
                "token_usage": {"total_tokens": 0},
            }

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", _load_bundle)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)

    async def _get_service():
        return _SceneService()

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert load_calls == [
        {"visit_id": "visit-001", "scene": "final", "schema": "public"},
        {"visit_id": "visit-001", "scene": "running", "schema": "public"},
        {"visit_id": "visit-002", "scene": "running", "schema": "public"},
        {"visit_id": "visit-003", "scene": "running", "schema": "public"},
    ]
    assert captured == [
        {
            "visit_id": "visit-001",
            "scene": "running",
            "scene_resolution": {
                "query_scope": "all",
                "record_scene": "final",
                "resolved_scene": "final",
                "attempted_scenes": ["final", "running"],
                "loaded_scene": "running",
                "used_fallback": True,
                "resolution_status": "fallback",
            },
            "evaluation_horizon_snapshot": workspace.job["filters"][
                "record_evaluation_snapshot"
            ][0],
            "evaluation_as_of_date": None,
            "evaluation_horizon_policy": "authoritative_discharge",
        },
        {
            "visit_id": "visit-002",
            "scene": "running",
            "scene_resolution": {
                "query_scope": "all",
                "record_scene": "running",
                "resolved_scene": "running",
                "attempted_scenes": ["running"],
                "loaded_scene": "running",
                "used_fallback": False,
                "resolution_status": "matched",
            },
            "evaluation_horizon_snapshot": workspace.job["filters"][
                "record_evaluation_snapshot"
            ][1],
            "evaluation_as_of_date": "2026-08-04",
            "evaluation_horizon_policy": "frozen_task_date",
        },
        {
            "visit_id": "visit-003",
            "scene": "running",
            "scene_resolution": {
                "query_scope": "all",
                "record_scene": "unknown",
                "resolved_scene": "",
                "attempted_scenes": ["running"],
                "loaded_scene": "running",
                "used_fallback": False,
                "resolution_status": "uncertain_fallback",
            },
            "evaluation_horizon_snapshot": workspace.job["filters"][
                "record_evaluation_snapshot"
            ][2],
            "evaluation_as_of_date": None,
            "evaluation_horizon_policy": "disabled",
        },
    ]


@pytest.mark.asyncio
async def test_worker_and_real_provider_keep_unresolved_record_horizons_empty(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    snapshots = [
        {
            "record_id": "visit-missing",
            "record_scene": "final",
            "admission_datetime": "2026-06-01 08:00:00",
            "discharge_datetime": "",
            "evaluation_horizon": "",
            "evaluation_basis": "",
            "resolution_status": "authoritative_time_missing",
        },
        {
            "record_id": "visit-conflict",
            "record_scene": "final",
            "admission_datetime": "2026-07-10 08:00:00",
            "discharge_datetime": "2026-07-03 08:00:00",
            "evaluation_horizon": "",
            "evaluation_basis": "",
            "resolution_status": "time_conflict",
        },
        {
            "record_id": "visit-unknown",
            "record_scene": "unknown",
            "admission_datetime": "invalid-admission",
            "discharge_datetime": "invalid-discharge",
            "evaluation_horizon": "",
            "evaluation_basis": "",
            "resolution_status": "scene_uncertain",
        },
    ]
    workspace.job["scope"] = "all"
    workspace.job["record_ids"] = [item["record_id"] for item in snapshots]
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-06-01-05"],
        "selected_rule_ids": ["LX0609-06-01-05"],
        "scoped_customer_rule_ids": ["LX0609-06-01-05"],
        "record_rule_map": {
            item["record_id"]: ["LX0609-06-01-05"] for item in snapshots
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "record_evaluation_snapshot": snapshots,
    }

    def _collect_records(**_: Any) -> List[Dict[str, Any]]:
        return [
            {
                "record_id": item["record_id"],
                "visit_id": item["record_id"],
                "scope": item["record_scene"],
            }
            for item in snapshots
        ]

    workspace.collect_records = _collect_records  # type: ignore[method-assign]
    workspace.hydrate_records_with_medical_text = lambda records: [  # type: ignore[method-assign]
        {
            **record,
            "institute_id": "HOSP-001",
            "patient_id": f"PAT-{record['visit_id']}",
            "medical_text": "病历文本",
        }
        for record in records
    ]
    provider_results: List[Dict[str, Any]] = []

    class _ProviderBackedService(_ServiceStub):
        async def evaluate_running_final_bundle_input(self, **kwargs: Any) -> Dict[str, Any]:
            bundle = kwargs["bundle"]
            visit_id = str(bundle["visit_id"])

            def _reader(**reader_kwargs: Any) -> SnapshotSourceRows:
                source_key = str(reader_kwargs["source_key"])
                rows: List[Dict[str, Any]] = []
                if source_key == "inpat_registration":
                    rows = [
                        {
                            "admission_datetime": (
                                "2026-07-10 08:00:00"
                                if visit_id == "visit-conflict"
                                else "2026-06-01 08:00:00"
                            )
                        }
                    ]
                elif (
                    source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY
                    and visit_id in {"visit-conflict", "visit-unknown"}
                ):
                    rows = [{"discharge_datetime": "2026-07-03 08:00:00"}]
                return SnapshotSourceRows.create(
                    source_key=source_key,
                    rows=rows,
                    truncated=False,
                    limit_rows=1 if rows else 50,
                )

            session = build_luxian_0609_evidence_read_session(
                selected_rule_ids=("LX0609-06-01-05",),
                institute_id=str(bundle["institute_id"]),
                patient_id=str(bundle["patient_id"]),
                visit_id=visit_id,
                source_schema=None,
                created_at="2026-08-04T12:00:00+08:00",
                evaluation_as_of_date=kwargs["evaluation_as_of_date"],
                evaluation_horizon_policy=kwargs["evaluation_horizon_policy"],
                horizon_unavailable_reason=kwargs[
                    "evaluation_horizon_unavailable_reason"
                ],
                row_reader=_reader,
            )
            horizon_observation = next(
                item
                for item in session.snapshot.observations
                if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
            )
            provider_results.append(
                {
                    "record_id": visit_id,
                    "evaluation_as_of_date": kwargs["evaluation_as_of_date"],
                    "evaluation_horizon_policy": kwargs[
                        "evaluation_horizon_policy"
                    ],
                    "horizon_unavailable_reason": kwargs[
                        "evaluation_horizon_unavailable_reason"
                    ],
                    "observation_reason": horizon_observation.reason_code,
                    "horizon_rows": session.materials.rows(
                        EVALUATION_HORIZON_SOURCE_KEY
                    ),
                }
            )
            return {
                "evaluation_results": [
                    {
                        "rule_id": "LX0609-06-01-05",
                        "status": "data_gap",
                        "is_compliant": None,
                        "reason_code": "required_field_missing",
                        "metadata": {"execution_source": "lx0609_native"},
                    }
                ],
                "token_usage": {"total_tokens": 0},
            }

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        batch_worker,
        "load_running_final_bundle",
        lambda **_: {"medical_text": "bundle text"},
    )
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)

    async def _get_service():
        return _ProviderBackedService()

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_service)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    expected_reasons = [
        "authoritative_time_missing",
        "authoritative_time_conflict",
        "authoritative_time_missing",
    ]
    assert provider_results == [
        {
            "record_id": item["record_id"],
            "evaluation_as_of_date": None,
            "evaluation_horizon_policy": "disabled",
            "horizon_unavailable_reason": reason,
            "observation_reason": reason,
            "horizon_rows": (),
        }
        for item, reason in zip(snapshots, expected_reasons)
    ]


@pytest.mark.asyncio
async def test_luxian_batch_single_family_off_fails_before_sc_source_or_evaluation(
    monkeypatch,
):
    workspace = _WorkspaceStub()
    customer_rule_ids = ["LX0609-07-01-02"]
    workspace.job["filters"] = {
        "rule_ids": customer_rule_ids,
        "selected_rule_ids": customer_rule_ids,
        "scoped_customer_rule_ids": customer_rule_ids,
        "record_rule_map": {
            "visit-001": customer_rule_ids,
            "visit-002": customer_rule_ids,
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    source_guard_calls: List[str] = []
    package_calls: List[List[str]] = []

    class _SingleFamilyRollbackService(_ServiceStub):
        def assert_sc_rule_source_ready(
            self, *, context: str, block_batch: bool = False
        ) -> Dict[str, Any]:
            source_guard_calls.append(context)
            return {"sc_source": "pg_governance"}

        async def evaluate_running_final_bundle_input(
            self, **kwargs: Any
        ) -> Dict[str, Any]:
            package_calls.append(list(kwargs["rule_ids"]))
            return {
                "evaluation_results": [
                    {
                        "rule_id": "LX0609-07-01-02",
                        "status": "data_gap",
                        "is_compliant": False,
                        "metadata": {"execution_source": "customer_aggregation"},
                    }
                ],
                "token_usage": {"total_tokens": 0},
            }

    service = _SingleFamilyRollbackService()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(
            LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=False
        ),
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "正式质控禁止兼容执行" in workspace.job["error_message"]
    assert source_guard_calls == []
    assert package_calls == []
    assert workspace.items == []


@pytest.mark.asyncio
async def test_create_workspace_batch_job_should_resolve_fast_screen_rule_set(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    request = SimpleNamespace(state=SimpleNamespace())
    payload = qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_set_key="sc_content_fast_v1",
        scope="final",
        date_field="discharge",
        record_ids=["visit-001"],
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=request,  # type: ignore[arg-type]
        payload=payload,
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None
    filters = dict(workspace.created_job.get("filters") or {})
    assert filters["rule_set_key"] == "sc_content_fast_v1"
    assert filters["execution_strategy"] == "fast_screen"
    assert filters["quality_profile"] == "throughput_v1"
    assert filters["bucket_strategy"] == "fixed_packs"
    assert filters["batch_output_mode"] == "minimal"
    assert filters["enable_selective_refine"] is False
    assert filters["max_refine_candidates"] == 0
    assert filters["run_mode"] == "parallel"
    assert workspace.created_job["run_mode"] == "parallel"
    assert response["data"]["execution_strategy"] == "fast_screen"


@pytest.mark.asyncio
async def test_create_workspace_batch_job_should_resolve_full_intrinsic_fast_screen_rule_set(monkeypatch):
    workspace = _WorkspaceStub()
    service = _ServiceStub()

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    request = SimpleNamespace(state=SimpleNamespace())
    payload = qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_set_key="sc_content_full_v1",
        scope="final",
        date_field="discharge",
        record_ids=["visit-001"],
    )

    response = await qc_sichuan.create_workspace_batch_job(
        request=request,  # type: ignore[arg-type]
        payload=payload,
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert workspace.created_job is not None
    filters = dict(workspace.created_job.get("filters") or {})
    assert filters["rule_set_key"] == "sc_content_full_v1"
    assert filters["execution_strategy"] == "fast_screen"
    assert filters["quality_profile"] == "throughput_v1"
    assert filters["bucket_strategy"] == "fixed_packs"
    assert filters["batch_output_mode"] == "minimal"
    assert filters["enable_selective_refine"] is False
    assert filters["max_refine_candidates"] == 0
    assert filters["run_mode"] == "parallel"
    assert len(filters["rule_ids"]) == 84
    assert workspace.created_job["run_mode"] == "parallel"
    assert response["data"]["execution_strategy"] == "fast_screen"


@pytest.mark.asyncio
async def test_create_workspace_batch_job_should_reuse_active_idempotent_job(monkeypatch):
    workspace = _IdempotentWorkspaceStub()
    service = _ServiceStub()
    submitted_tasks: List[Dict[str, Any]] = []

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda task_name, func, job_id: submitted_tasks.append(
            {"task_name": task_name, "func": func, "job_id": job_id}
        ),
    )

    request = SimpleNamespace(state=SimpleNamespace())
    payload = qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_ids=["SC-002", "SC-001"],
        scope="final",
        department="骨科",
        doctor="张医生",
        date_field="discharge",
        start_date="2026-06-01",
        end_date="2026-06-18",
        keyword="出院",
        record_ids=["visit-002", "visit-001"],
        run_mode="parallel",
    )

    first_records = workspace.collect_records(
        scope="final",
        department="骨科",
        doctor="张医生",
        date_field="discharge",
        start_date="2026-06-01",
        end_date="2026-06-18",
        keyword="出院",
        record_ids=["visit-002", "visit-001"],
    )
    idempotency_payload = {
        "scope": "final",
        "query_scope": "final",
        "department": "骨科",
        "doctor": "张医生",
        "date_field": "discharge",
        "start_date": "2026-06-01",
        "end_date": "2026-06-18",
        "keyword": "出院",
        "record_refs": [
            CaseRef.from_mapping(record).as_dict() for record in first_records
        ],
        "record_scene_snapshot": qc_sichuan._build_workspace_record_scene_snapshot(
            first_records,
            query_scope="final",
        ),
        "rule_set_key": "",
        "rule_ids": ["SC-001", "SC-002"],
        "execution_strategy": "standard",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "domain_only",
        "batch_output_mode": "full",
        "run_mode": "parallel",
    }
    workspace.job["filters"] = {
        "idempotency_key": "sichuan-workspace-run:"
        + hashlib.sha256(
            json.dumps(idempotency_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24],
        "idempotency_payload": idempotency_payload,
    }

    response = await qc_sichuan.create_workspace_batch_job(
        request=request,  # type: ignore[arg-type]
        payload=payload,
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert response["message"] == "已复用运行中的四川规则批量任务"
    assert response["data"]["id"] == "job-idempotent-active"
    assert response["data"]["idempotency_reused"] is True
    assert workspace.create_called is False
    assert submitted_tasks == []
    assert [call["status"] for call in workspace.list_calls] == ["queued", "running"]


@pytest.mark.asyncio
async def test_create_workspace_batch_job_should_not_reuse_running_job_after_record_becomes_final(
    monkeypatch,
):
    class _StatusChangedWorkspaceStub(_IdempotentWorkspaceStub):
        def collect_records(self, **_: Any) -> List[Dict[str, Any]]:
            return [
                {
                    "institute_id": "HOSP-001",
                    "patient_id": "PAT-visit-001",
                    "record_id": "visit-001",
                    "visit_id": "visit-001",
                    "scope": "final",
                    "discharge_datetime": "2026-08-03 09:30:00",
                }
            ]

        def create_batch_job(self, **kwargs: Any) -> Dict[str, Any]:
            self.create_called = True
            return _WorkspaceStub.create_batch_job(self, **kwargs)

    workspace = _StatusChangedWorkspaceStub()
    service = _ServiceStub()
    submitted_tasks: List[Dict[str, Any]] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "submit_detached_task",
        lambda task_name, func, job_id: submitted_tasks.append(
            {"task_name": task_name, "func": func, "job_id": job_id}
        ),
    )

    running_snapshot = qc_sichuan._build_workspace_record_scene_snapshot(
        [
            {
                "record_id": "visit-001",
                "visit_id": "visit-001",
                "scope": "running",
                "discharge_datetime": "",
            }
        ],
        query_scope="all",
    )
    active_payload = {
        "scope": "all",
        "query_scope": "all",
        "department": "",
        "doctor": "",
        "date_field": "admission",
        "start_date": "",
        "end_date": "",
        "keyword": "",
        "record_ids": ["visit-001"],
        "record_scene_snapshot": running_snapshot,
        "rule_set_key": "",
        "rule_ids": ["SC-001"],
        "execution_strategy": "standard",
        "quality_profile": "throughput_v1",
        "bucket_strategy": "domain_only",
        "batch_output_mode": "full",
        "run_mode": "parallel",
    }
    workspace.job["filters"] = {
        "idempotency_key": "sichuan-workspace-run:"
        + hashlib.sha256(
            json.dumps(active_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24],
        "idempotency_payload": active_payload,
    }

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),  # type: ignore[arg-type]
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_ids=["SC-001"],
            scope="all",
            date_field="admission",
            record_ids=["visit-001"],
            run_mode="parallel",
        ),
        qc_service=service,  # type: ignore[arg-type]
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert response["data"].get("idempotency_reused") is not True
    assert workspace.create_called is True
    assert workspace.created_job is not None
    assert workspace.created_job["filters"]["record_scene_snapshot"] == [
        {
            "record_id": "visit-001",
            "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-001",
            "visit_id": "visit-001",
            "record_key": CaseRef(
                "HOSP-001", "PAT-visit-001", "visit-001"
            ).as_key(),
            "record_scene": "final",
            "resolved_scene": "final",
            "discharge_snapshot": "2026-08-03 09:30:00",
        }
    ]
    assert len(submitted_tasks) == 1


@pytest.mark.asyncio
async def test_luxian_runtime_shadow_metadata_is_additive_and_precedes_evaluation(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-04-02-02"],
        "selected_rule_ids": ["LX0609-04-02-02"],
        "scoped_customer_rule_ids": ["LX0609-04-02-02"],
        "record_rule_map": {"visit-001": ["LX0609-04-02-02"], "visit-002": ["LX0609-04-02-02"]},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
        "date_field": "discharge",
    }
    service = _ServiceStub()
    sequence: List[str] = []
    evaluation_row: Dict[str, Any] = {"rule_id": "LX0609-04-02-02", "status": "compliant", "is_compliant": True, "metadata": {"tokens_used": 17}}

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        sequence.append("evaluate")
        return {
            "evaluation_results": [evaluation_row],
            "token_usage": {"total_tokens": 17, "prompt_tokens": 10, "completion_tokens": 7},
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    async def _get_qc_service():
        return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True),
    )
    monkeypatch.setattr(batch_worker, "load_luxian_0609_rules", lambda: [{"rule_id": "LX0609-04-02-02", "rule_code": "LX0609-04-02-02", "name": "规则-030"}])
    original_hook = batch_worker.run_luxian_0609_runtime_shadow

    def _hook(**kwargs: Any) -> Dict[str, Any]:
        sequence.append("hook")
        assert kwargs["source_query_observations"] is None and kwargs["extraction_inputs"] is None
        return original_hook(**kwargs)

    monkeypatch.setattr(batch_worker, "run_luxian_0609_runtime_shadow", _hook)
    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert sequence == ["hook", "evaluate", "hook", "evaluate"]
    summary = (evaluation_row.get("metadata") or {}).get("luxian_0609_runtime_shadow")
    assert summary and summary["disposition"] == "completed"
    assert evaluation_row["status"] == "compliant"
    assert workspace.items
    persisted_summary = (workspace.items[0].get("metadata") or {}).get("luxian_0609_runtime_shadow")
    assert persisted_summary and persisted_summary["disposition"] == "completed"
    assert persisted_summary["expected_llm_call_count"] == persisted_summary["llm_total_tokens"] == 0


async def _run_native_usage_batch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    llm_call_count: int,
) -> _WorkspaceStub:
    workspace = _WorkspaceStub()
    native_rule_ids = ["LX0609-04-01-01", "LX0609-04-02-02"]
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "rule_ids": native_rule_ids,
        "selected_rule_ids": native_rule_ids,
        "scoped_customer_rule_ids": native_rule_ids,
        "record_rule_map": {"visit-001": native_rule_ids},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        return {
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "status": "compliant",
                    "is_compliant": True,
                    "metadata": {
                        "executor_type": "program",
                        "executor_key": "extended_document",
                    },
                }
                for rule_id in native_rule_ids
            ],
            "token_usage": {
                "total_tokens": prompt_tokens + completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            "executor_breakdown": {"llm": llm_call_count},
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    return workspace


@pytest.mark.asyncio
async def test_native_usage_call_count_reaches_public_job_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = await _run_native_usage_batch(
        monkeypatch,
        prompt_tokens=80,
        completion_tokens=21,
        llm_call_count=2,
    )

    projected = workspace_module.project_customer_safe_batch_job(
        {
            **workspace.job,
            "summary": workspace.summary,
            "items": workspace.items,
        },
        hmac_key="unit-test-key",
        _validate_luxian=False,
    )

    assert workspace.summary is not None
    assert workspace.summary["performance_profile"]["llm_call_count"] == 2
    assert projected["summary"]["llm_call_count"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt_tokens", "completion_tokens", "expected_input", "expected_output", "expected_total"),
    [
        (80, 21, [40, 40], [11, 10], [51, 50]),
        (81, 21, [41, 40], [11, 10], [52, 50]),
    ],
)
async def test_native_usage_distribution_preserves_odd_token_totals(
    monkeypatch: pytest.MonkeyPatch,
    prompt_tokens: int,
    completion_tokens: int,
    expected_input: List[int],
    expected_output: List[int],
    expected_total: List[int],
) -> None:
    workspace = await _run_native_usage_batch(
        monkeypatch,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        llm_call_count=2,
    )

    metadata = [dict(item.get("metadata") or {}) for item in workspace.items]
    assert [item["input_tokens"] for item in metadata] == expected_input
    assert [item["output_tokens"] for item in metadata] == expected_output
    assert [item["tokens_used"] for item in metadata] == expected_total
    assert all(
        item["tokens_used"] == item["input_tokens"] + item["output_tokens"] >= 0
        for item in metadata
    )
    assert sum(item["input_tokens"] for item in metadata) == prompt_tokens
    assert sum(item["output_tokens"] for item in metadata) == completion_tokens
    assert sum(item["tokens_used"] for item in metadata) == prompt_tokens + completion_tokens
    assert workspace.summary is not None
    assert workspace.summary["total_tokens"] == prompt_tokens + completion_tokens
    assert workspace.summary["performance_profile"]["tokens_total"] == prompt_tokens + completion_tokens


@pytest.mark.asyncio
async def test_native_luxian_batch_worker_uses_customer_ids_without_sc_rule_lookup(monkeypatch):
    workspace = _WorkspaceStub()
    native_rule_ids = ["LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"]
    workspace.job["filters"] = {
        "rule_ids": native_rule_ids,
        "selected_rule_ids": native_rule_ids,
        "scoped_customer_rule_ids": native_rule_ids,
        "record_rule_map": {
            "visit-001": native_rule_ids,
            "visit-002": native_rule_ids,
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }

    class _NativeOnlyService(_ServiceStub):
        def assert_sc_rule_source_ready(self, **_: Any) -> Dict[str, Any]:
            raise AssertionError("原生0609批任务不应依赖SC规则来源")

        def get_rule_by_id(self, rule_id: str) -> Dict[str, Any]:
            raise AssertionError(f"原生客户ID不应查询旧规则: {rule_id}")

    service = _NativeOnlyService()
    captured_rule_ids: List[List[str]] = []

    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        captured_rule_ids.append(list(kwargs["rule_ids"]))
        assert callable(kwargs.get("execution_trace_sink"))
        return {
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "status": "compliant" if rule_id != "LX0609-04-03-01" else "non_compliant",
                    "is_compliant": rule_id != "LX0609-04-03-01",
                    "prompt_version": "native-should-hide",
                    "model_version": "native-should-hide",
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "program",
                        "prompt_version": "native-should-hide",
                        "performance_profile": {"tokens_total": 0},
                    },
                    "audit": {"model_name": "native-should-hide"},
                }
                for rule_id in native_rule_ids
            ],
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "luxian_0609_shadow_evaluations": {
                "luxian_0609_025_shadow": {
                    "shadow_only": True,
                    "release_eligible": False,
                    "status": "data_gap",
                    "reason_code": "surgery_text_fact_unknown",
                    "operation_count": 1,
                    "status_counts": {"data_gap": 1},
                    "missing_field_counts": {"implant_material": 1},
                    "llm_calls": 1,
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "elapsed_ms": 12,
                    "contract_version": "lx0609-025-shadow-v1",
                    "operations": [
                        {"source_document_id": "PRIVATE-SURGERY-DOCUMENT"}
                    ],
                }
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        _luxian_native_settings,
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "completed"
    assert captured_rule_ids == [native_rule_ids, native_rule_ids]
    assert len(workspace.items) == 6
    assert {str(item.get("rule_id") or "") for item in workspace.items} == set(
        native_rule_ids
    )
    assert int((workspace.summary or {}).get("total_tokens") or 0) == 0
    shadow_summary = (workspace.summary or {}).get("luxian_0609_shadow_evaluations")
    assert shadow_summary == {
        "luxian_0609_025_shadow": {
            "shadow_only": True,
            "release_eligible": False,
            "contract_version": "lx0609-025-shadow-v1",
            "records_evaluated": 2,
            "status_counts": {"data_gap": 2},
            "reason_counts": {"surgery_text_fact_unknown": 2},
            "operation_count": 2,
            "llm_calls": 2,
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "elapsed_ms": 24,
            "missing_field_counts": {"implant_material": 2},
        }
    }
    hidden_native_fields = {
        "prompt_version",
        "model_name",
        "model_version",
        "prompt_strategy",
        "prompt_tokens",
        "completion_tokens",
        "cot_mode",
        "requested_enable_thinking",
        "thinking_heuristic_applied",
        "llm_fallback",
        "performance_profile",
    }
    for item in workspace.items:
        assert hidden_native_fields.isdisjoint(item)
        assert hidden_native_fields.isdisjoint(dict(item.get("metadata") or {}))
        assert hidden_native_fields.isdisjoint(dict(item.get("audit") or {}))
        assert "luxian_0609_shadow_evaluations" not in dict(item.get("metadata") or {})


@pytest.mark.asyncio
@pytest.mark.parametrize("sample_pool_id", [None, "pool-live-phase-001"])
async def test_native_luxian_worker_coalesces_executor_phase_before_canonical_results(
    monkeypatch: pytest.MonkeyPatch,
    sample_pool_id: Optional[str],
) -> None:
    """Native族阶段按病历合并为一次终态回写，结果只在完整交付后写入。"""
    workspace = _WorkspaceStub()
    original_update_progress = workspace.update_batch_job_progress

    def _update_incremental_progress(**kwargs: Any) -> None:
        items = kwargs.pop("items", None)
        failed_records = kwargs.pop("failed_records", None)
        original_update_progress(**kwargs)
        if items is not None:
            workspace.items = list(items)
        if failed_records is not None:
            workspace.failed_records = list(failed_records)

    workspace.update_batch_job_progress = _update_incremental_progress  # type: ignore[method-assign]
    native_rule_ids = ["LX0609-04-01-01", "LX0609-04-02-02"]
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["parent_job_id"] = "parent-job-throughput-001"
    workspace.job["filters"] = {
        "record_refs": [
            {
                "institute_id": "HOSP-001",
                "patient_id": "PAT-visit-001",
                "visit_id": "visit-001",
            }
        ],
        "rule_ids": native_rule_ids,
        "selected_rule_ids": native_rule_ids,
        "scoped_customer_rule_ids": native_rule_ids,
        "record_rule_map": {"visit-001": native_rule_ids},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    if sample_pool_id:
        workspace.job["filters"]["sample_pool_id"] = sample_pool_id
    service = _ServiceStub()
    observed_stream_states: List[Dict[str, Any]] = []
    observed_llm_contexts: List[Any] = []

    def _capture_native_phase_updates(**kwargs: Any) -> None:
        stream_state = dict((kwargs.get("summary_patch") or {}).get("stream_state") or {})
        if stream_state.get("kind") == "native_executor_phase":
            observed_stream_states.append(stream_state)
        _update_incremental_progress(**kwargs)

    workspace.update_batch_job_progress = _capture_native_phase_updates  # type: ignore[method-assign]

    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        observed_llm_contexts.append(current_llm_observation_context())
        trace_sink = kwargs.get("execution_trace_sink")
        assert callable(trace_sink)
        trace_sink(
            {
                "event": "failed",
                "executor_key": "exam_lab",
                "rule_count": 1,
            }
        )
        trace_sink(
            {
                "event": "started",
                "executor_key": "surgery_document",
                "rule_count": 2,
            }
        )
        assert workspace.items == []
        trace_sink(
            {
                "event": "completed",
                "executor_key": "surgery_document",
                "rule_count": 2,
            }
        )
        assert workspace.items == []
        return {
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "status": "compliant",
                    "is_compliant": True,
                    "metadata": {},
                }
                for rule_id in native_rule_ids
            ],
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert len(observed_llm_contexts) == 1
    assert observed_llm_contexts[0].business_scene == "luxian_0609_qc"
    assert observed_llm_contexts[0].root_job_id == "parent-job-throughput-001"
    assert observed_llm_contexts[0].record_key_hash
    assert observed_llm_contexts[0].rule_set_key == qc_sichuan.LUXIAN_0609_RULE_SET_KEY
    assert observed_stream_states == [
        {
        "enabled": True,
        "kind": "native_executor_phase",
        "event": "completed",
        "executor_key": "surgery_document",
        "completed_batches": 1,
        "total_batches": 2,
        "active_executor_keys": [],
        "record_id": "visit-001",
        "updated_at": observed_stream_states[0]["updated_at"],
        "current_rule_count": 2,
        "completed_rule_count": 2,
        "total_rule_count": 2,
        }
    ]
    assert all(
        "rule_results" not in update["summary_patch"]
        for update in workspace.progress_updates
        if update["step_key"] == "run"
        and (update["summary_patch"].get("stream_state") or {}).get("kind")
        != "native_executor_phase"
    )
    aggregate_updates = [
        update for update in workspace.progress_updates if update["step_key"] == "aggregate"
    ]
    assert len(aggregate_updates) == 1
    assert aggregate_updates[0]["summary_patch"]["rule_results"] == []
    assert aggregate_updates[0]["summary_patch"]["performance_profile"] == {}
    assert aggregate_updates[0]["summary_patch"]["last_retry_performance_profile"] == {}
    assert workspace.summary["rule_results"]
    assert workspace.summary["performance_profile"]
    assert workspace.job["status"] == "completed"


@pytest.mark.asyncio
async def test_native_criterion_result_persists_canonical_contract_fields_for_single_record_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """018 的当前契约版本必须从原生 eval 顶层保存，而非只读 metadata。"""

    rule = get_luxian_0609_rule("LX0609-01-01-02")
    assert rule is not None
    rule_version = str(rule["rule_version"])
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-01-01-02"],
        "selected_rule_ids": ["LX0609-01-01-02"],
        "scoped_customer_rule_ids": ["LX0609-01-01-02"],
        "record_rule_map": {"visit-001": ["LX0609-01-01-02"]},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        return {
            "evaluation_results": [
                {
                    "rule_id": "LX0609-01-01-02",
                    "rule_version": rule_version,
                    "status": "data_gap",
                    "result_status": "data_gap",
                    "reason_code": "required_field_missing",
                    "is_compliant": None,
                    "criterion_results": [
                        {
                            "criterion_id": "chief_complaint_length",
                            "status": "non_compliant",
                        }
                    ],
                    "metadata": {
                        "rule_version": "obsolete-version",
                        "executor_type": "program",
                    },
                }
            ],
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(batch_worker, "load_luxian_0609_rules", lambda: [rule])

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    persisted = next(item for item in workspace.items if item["rule_id"] == "LX0609-01-01-02")
    assert persisted["rule_version"] == rule_version
    assert persisted["rule_version"] != persisted["metadata"]["rule_version"]
    assert persisted["status"] == "data_gap"
    assert persisted["result_status"] == "data_gap"
    assert persisted["reason_code"] == "required_field_missing"
    assert persisted["is_compliant"] is None
    assert workspace_module._is_current_rule_contract_result(persisted) is True


@pytest.mark.asyncio
async def test_native_luxian_paused_customer_rule_is_persisted_as_paused_not_missing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """样本池策略暂停必须经 worker 投影为客户可懂结果，而不是执行异常。"""

    active_rule = get_luxian_0609_rule("LX0609-03-01-01")
    paused_rule = get_luxian_0609_rule("LX0609-07-04-02")
    assert active_rule is not None and paused_rule is not None
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-03-01-01"],
        "selected_rule_ids": ["LX0609-03-01-01"],
        "scoped_customer_rule_ids": ["LX0609-03-01-01", "LX0609-07-04-02"],
        "paused_customer_rule_ids": ["LX0609-07-04-02"],
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        return {
            "evaluation_results": [
                {
                    "rule_id": "LX0609-03-01-01",
                    "status": "compliant",
                    "result_status": "compliant",
                    "reason_code": "requirement_satisfied",
                    "is_compliant": True,
                    "metadata": {"executor_type": "program"},
                }
            ],
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0609_rules",
        lambda: [active_rule, paused_rule],
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    paused_item = next(item for item in workspace.items if item["rule_id"] == "LX0609-07-04-02")
    assert workspace.failed_records == []
    assert paused_item["status"] == "not_executed"
    assert paused_item["result_status"] == "not_executed"
    assert paused_item["is_compliant"] is None
    assert not paused_item["evidence"]
    assert paused_item["metadata"]["reason_code"] == "policy_definition_pending"
    assert (
        paused_item["metadata"]["pending_reason_code"]
        == "charging_source_unavailable_customer_scope"
    )
    assert "不参与正式结论" in paused_item["findings"]


@pytest.mark.asyncio
async def test_native_copy_result_is_not_reinterpreted_by_legacy_batch_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = get_luxian_0609_rule("LX0609-12-01-01")
    assert rule is not None
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-12-01-01"],
        "selected_rule_ids": ["LX0609-12-01-01"],
        "scoped_customer_rule_ids": ["LX0609-12-01-01"],
        "record_rule_map": {"visit-001": ["LX0609-12-01-01"]},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        return {
            "evaluation_results": [
                {
                    "rule_id": "LX0609-12-01-01",
                    "status": "compliant",
                    "result_status": "compliant",
                    "reason_code": "requirement_satisfied",
                    "is_compliant": True,
                    "customer_display_facts": {
                        "failure_kind": "admission_first_course_not_identical",
                        "copy_similarity": 0.45,
                    },
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "program",
                    },
                }
            ],
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(batch_worker, "load_luxian_0609_rules", lambda: [rule])

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    persisted = next(item for item in workspace.items if item["rule_id"] == "LX0609-12-01-01")
    assert persisted["status"] == "compliant"
    assert persisted["result_status"] == "compliant"
    assert persisted["reason_code"] == "requirement_satisfied"
    assert persisted["is_compliant"] is True
    assert "copy_rule_priority_guard" not in persisted["metadata"]


@pytest.mark.asyncio
async def test_luxian_batch_aggregation_off_fails_without_legacy_rollback(monkeypatch):
    workspace = _WorkspaceStub()
    native_rule_ids = ["LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"]
    workspace.job["filters"] = {
        "rule_ids": native_rule_ids,
        "selected_rule_ids": native_rule_ids,
        "scoped_customer_rule_ids": native_rule_ids,
        "record_rule_map": {
            "visit-001": native_rule_ids,
            "visit-002": native_rule_ids,
        },
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    service = _ServiceStub()
    looked_up: List[str] = []
    source_guard_calls: List[str] = []
    captured_rule_ids: List[List[str]] = []

    def _assert_sc_rule_source_ready(*, context: str, **_: Any) -> Dict[str, Any]:
        source_guard_calls.append(context)
        return {"sc_source": "pg_governance"}

    def _get_rule_by_id(rule_id: str) -> Dict[str, Any]:
        looked_up.append(rule_id)
        return {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "name": f"规则-{rule_id}",
            "defect_level": "一般缺陷",
        }

    async def _evaluate_document_with_rules(**kwargs: Any) -> Dict[str, Any]:
        current_rule_ids = [
            str(rule.get("rule_id") or rule.get("rule_code") or "") for rule in kwargs["rules"]
        ]
        captured_rule_ids.append(current_rule_ids)
        return {
            "evaluation_results": [
                {
                    "rule_id": rule_id,
                    "status": "compliant",
                    "is_compliant": True,
                    "metadata": {"executor_type": "program"},
                }
                for rule_id in current_rule_ids
            ],
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        }

    service.assert_sc_rule_source_ready = _assert_sc_rule_source_ready  # type: ignore[method-assign]
    service.get_rule_by_id = _get_rule_by_id  # type: ignore[method-assign]
    service.evaluate_document_with_rules = _evaluate_document_with_rules  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=False
        ),
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.job["status"] == "failed"
    assert "正式Native主链未就绪" in workspace.job["error_message"]
    assert looked_up == []
    assert captured_rule_ids == []
    assert source_guard_calls == []
    assert workspace.items == []


@pytest.mark.asyncio
async def test_luxian_runtime_shadow_preserves_explicit_empty_selected_scope(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {
        "rule_ids": ["LX0609-04-02-02"], "selected_rule_ids": [],
        "scoped_customer_rule_ids": ["LX0609-04-02-02"],
        "record_rule_map": {"visit-001": ["LX0609-04-02-02"], "visit-002": ["LX0609-04-02-02"]},
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY, "validation_mode": "programmatic",
    }
    service = _ServiceStub()
    summaries: List[Dict[str, Any]] = []

    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]:
        return {"evaluation_results": [{"rule_id": "LX0609-04-02-02", "status": "compliant", "is_compliant": True, "metadata": {}}]}

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    async def _get_qc_service(): return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True),
    )
    original = batch_worker.run_luxian_0609_runtime_shadow
    def _hook(**kwargs: Any) -> Dict[str, Any]:
        assert kwargs["selected_rule_ids"] == []
        result = original(**kwargs)
        summaries.append(result)
        return result
    monkeypatch.setattr(batch_worker, "run_luxian_0609_runtime_shadow", _hook)
    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    assert summaries and {item["disposition"] for item in summaries} == {"skipped_no_effective_rules"}


@pytest.mark.asyncio
async def test_luxian_runtime_shadow_flag_off_does_not_call_hook(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {"rule_ids": ["LX0609-04-02-02"], "selected_rule_ids": ["LX0609-04-02-02"], "scoped_customer_rule_ids": ["LX0609-04-02-02"], "record_rule_map": {"visit-001": ["LX0609-04-02-02"], "visit-002": ["LX0609-04-02-02"]}, "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY, "validation_mode": "programmatic"}
    service = _ServiceStub()
    async def _evaluate_running_final_bundle_input(**_: Any) -> Dict[str, Any]: return {"evaluation_results": [{"rule_id": "LX0609-04-02-02", "status": "compliant", "is_compliant": True, "metadata": {}}]}
    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    async def _get_qc_service(): return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False),
    )
    monkeypatch.setattr(batch_worker, "run_luxian_0609_runtime_shadow", lambda **_: (_ for _ in ()).throw(AssertionError("hook should remain off")))
    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    assert workspace.job["status"] == "completed"


@pytest.mark.asyncio
async def test_luxian_runtime_shadow_router_uses_provider_coordinates_and_persists_completed(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.job["filters"] = {"rule_ids": ["LX0609-04-02-02"], "selected_rule_ids": ["LX0609-04-02-02"], "scoped_customer_rule_ids": ["LX0609-04-02-02"], "record_rule_map": {"visit-001": ["LX0609-04-02-02"], "visit-002": ["LX0609-04-02-02"]}, "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY, "validation_mode": "programmatic", "evaluation_as_of_date": "2026-07-17"}
    workspace.hydrate_records_with_medical_text = lambda rows: [{**row, "institute_id": "i", "patient_id": "p", "medical_text": "ignored"} for row in rows]  # type: ignore[assignment]
    service = _ServiceStub()
    service_calls: List[Dict[str, Any]] = []
    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        service_calls.append(dict(kwargs))
        return {"evaluation_results": [{"rule_id": "LX0609-04-02-02", "status": "compliant", "is_compliant": True, "metadata": {}}]}
    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    async def _get_qc_service(): return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: _luxian_native_settings(LUXIAN_0609_RUNTIME_SHADOW_ENABLED=True),
    )
    monkeypatch.setattr(batch_worker, "load_luxian_0609_rules", lambda: [{"rule_id": "LX0609-04-02-02", "rule_code": "LX0609-04-02-02", "name": "规则-030"}])
    def _reader(**kwargs: Any):
        assert kwargs["source_schema"] is None
        return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}] if kwargs["source_key"] == "surgery_record" else [{}]
    monkeypatch.setattr(runtime_shadow_input_provider, "read_luxian_0609_runtime_source_rows", _reader)
    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    assert workspace.items
    summary = (workspace.items[0].get("metadata") or {}).get("luxian_0609_runtime_shadow")
    assert summary and summary["disposition"] == "completed" and summary["final_state_counts"]["compliant_count"] == 1 and summary["llm_total_tokens"] == 0
    assert len(service_calls) == 2
    assert {call["evaluation_as_of_date"] for call in service_calls} == {"2026-07-17"}
    assert {
        (
            call["bundle"]["institute_id"],
            call["bundle"]["patient_id"],
            call["bundle"]["visit_id"],
            call["bundle"].get("source_schema"),
        )
        for call in service_calls
    } == {("i", "p", "visit-001", None), ("i", "p", "visit-002", None)}


@pytest.mark.asyncio
async def test_workspace_batch_long_text_fallback_preserves_native_source_coordinates(monkeypatch):
    workspace = _WorkspaceStub()
    workspace.hydrate_records_with_medical_text = lambda rows: [
        {
            **row,
            "institute_id": "i",
            "patient_id": "p",
            "medical_text": "fallback",
        }
        for row in rows
    ]  # type: ignore[assignment]
    service = _ServiceStub()

    async def _get_qc_service():
        return service

    async def _fail_bundle(**_: Any) -> Dict[str, Any]:
        raise RuntimeError("controlled bundle failure")

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "evaluate_running_final_bundle", _fail_bundle)
    monkeypatch.setattr(
        batch_worker,
        "get_settings",
        lambda: SimpleNamespace(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=False,
            LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
        ),
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert service.evaluate_calls == 2
    assert {
        (
            call["source_institute_id"],
            call["source_patient_id"],
            call["source_visit_id"],
            call["source_schema"],
        )
        for call in service.evaluate_document_args
    } == {("i", "p", "visit-001", None), ("i", "p", "visit-002", None)}


@pytest.mark.asyncio
@pytest.mark.parametrize("recover_on_call", [2, None], ids=["recovers", "exhausted"])
async def test_formal_customer_sample_model_failure_automatically_retries_failed_rule(
    monkeypatch: pytest.MonkeyPatch,
    recover_on_call: int | None,
) -> None:
    workspace = _WorkspaceStub()
    workspace.job["created_by"] = "tester"
    workspace.job["record_ids"] = ["visit-001"]
    workspace.job["filters"] = {
        "record_refs": [
            {
                "institute_id": "HOSP-001",
                "patient_id": "PAT-visit-001",
                "visit_id": "visit-001",
            }
        ],
        "rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05"],
        "selected_rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05"],
        "scoped_customer_rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05"],
        "record_rule_map": {
            "visit-001": ["LX0609-06-01-04", "LX0609-06-01-05"],
        },
        "sample_pool_id": "pool-model-failure-001",
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }
    original_update_progress = workspace.update_batch_job_progress

    def _update_incremental_progress(**kwargs: Any) -> None:
        items = kwargs.pop("items", None)
        failed_records = kwargs.pop("failed_records", None)
        original_update_progress(**kwargs)
        if items is not None:
            workspace.items = list(items)
        if failed_records is not None:
            workspace.failed_records = list(failed_records)

    workspace.update_batch_job_progress = _update_incremental_progress  # type: ignore[method-assign]
    retry_calls: list[dict[str, Any]] = []

    def _retry_batch_job(
        *,
        job_id: str,
        created_by: str,
        automatic: bool = False,
    ) -> Dict[str, Any] | None:
        assert job_id == workspace.job["id"]
        assert created_by == "tester"
        scope_result = build_failed_rule_retry_scope(workspace.job)
        assert scope_result is not None
        retry_scope, normalized_failures = scope_result
        workspace.job["filters"] = {
            **dict(workspace.job["filters"]),
            "failed_rule_retry": retry_scope,
        }
        workspace.job["failed_records"] = normalized_failures
        workspace.job["status"] = "queued"
        retry_calls.append({"automatic": automatic, "scope": retry_scope})
        return dict(workspace.job)

    workspace.retry_batch_job = _retry_batch_job  # type: ignore[attr-defined]
    service = _ServiceStub()
    model_calls: list[tuple[str, ...]] = []

    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        active_rule_ids = tuple(kwargs["rule_ids"])
        model_calls.append(active_rule_ids)
        if recover_on_call is not None and len(model_calls) >= recover_on_call:
            return {
                "evaluation_results": [
                    {
                        "rule_id": "LX0609-06-01-05",
                        "status": "compliant",
                        "result_status": "compliant",
                        "display_status": "compliant",
                        "is_compliant": True,
                        "metadata": {"executor_type": "program"},
                    }
                ],
                "token_usage": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                },
                "model_execution_stats": {
                    "requested_rule_count": 1,
                    "first_success_rule_count": 1,
                    "retried_rule_count": 0,
                    "recovered_rule_count": 0,
                    "failed_rule_count": 0,
                },
            }
        evaluation_results = []
        if "LX0609-06-01-04" in active_rule_ids:
            evaluation_results.append(
                {
                    "rule_id": "LX0609-06-01-04",
                    "status": "compliant",
                    "result_status": "compliant",
                    "display_status": "compliant",
                    "is_compliant": True,
                    "metadata": {"executor_type": "program"},
                }
            )
        evaluation_results.append(
                {
                    "rule_id": "LX0609-06-01-05",
                    "status": "technical_error",
                    "result_status": "technical_error",
                    "display_status": "technical_error",
                    "is_compliant": None,
                    "reason_code": "model_invalid_output",
                    "metadata": {
                        "executor_type": "program",
                        "technical_error_internal": True,
                    },
                }
        )
        requested_count = len(active_rule_ids)
        first_success_count = 1 if "LX0609-06-01-04" in active_rule_ids else 0
        return {
            "evaluation_results": evaluation_results,
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            "model_execution_stats": {
                "requested_rule_count": requested_count,
                "first_success_rule_count": first_success_count,
                "retried_rule_count": 1,
                "recovered_rule_count": 0,
                "failed_rule_count": 1,
            },
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    async def _skip_retry_delay(_: float) -> None:
        return None

    monkeypatch.setattr(batch_worker.asyncio, "sleep", _skip_retry_delay)
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0609_rules",
        lambda: [get_luxian_0609_rule("LX0609-06-01-04"), get_luxian_0609_rule("LX0609-06-01-05")],
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    if recover_on_call is not None:
        assert workspace.job["status"] == "completed"
        assert workspace.summary["execution_status"] == "completed"
        assert workspace.summary["failed_rule_count"] == 0
        assert workspace.summary["completed_rule_count"] == 2
        assert workspace.summary["failed_rule_ids"] == []
        assert workspace.summary["retry_recovered_count"] == 1
        assert model_calls == [("LX0609-06-01-04", "LX0609-06-01-05"), ("LX0609-06-01-05",)]
        assert len(retry_calls) == 1
        assert [item["rule_id"] for item in workspace.items] == [
            "LX0609-06-01-04",
            "LX0609-06-01-05",
        ]
        assert workspace.failed_records == []
    else:
        assert workspace.job["status"] == "failed"
        assert workspace.summary["execution_status"] == "partial_failed"
        assert workspace.summary["automatic_failed_rule_retry"]["status"] == "exhausted"
        assert len(model_calls) == 4
        assert len(retry_calls) == 3
        assert [item["rule_id"] for item in workspace.items] == ["LX0609-06-01-04"]
        assert [item["rule_id"] for item in workspace.failed_records] == ["LX0609-06-01-05"]
    assert all(call["automatic"] is True for call in retry_calls)
    assert all(call["scope"]["pending_count"] == 1 for call in retry_calls)


def _configure_formal_customer_sample_batch_fixture(
    workspace: _WorkspaceStub,
    *,
    rule_ids: List[str],
    record_ids: List[str],
) -> None:
    workspace.job["record_ids"] = list(record_ids)
    record_refs = [
        {
            "institute_id": "HOSP-001",
            "patient_id": f"PAT-{record_id}",
            "visit_id": record_id,
        }
        for record_id in record_ids
    ]
    workspace.job["filters"] = {
        "record_refs": record_refs,
        "rule_ids": list(rule_ids),
        "selected_rule_ids": list(rule_ids),
        "scoped_customer_rule_ids": list(rule_ids),
        "record_rule_map": {record_id: list(rule_ids) for record_id in record_ids},
        "sample_pool_id": "pool-model-failure-coverage",
        "rule_set_key": qc_sichuan.LUXIAN_0609_RULE_SET_KEY,
        "validation_mode": "programmatic",
    }


def _customer_batch_eval_item(
    rule_id: str,
    status: str,
    *,
    reason_code: str = "",
) -> Dict[str, Any]:
    normalized_status = str(status).strip().lower()
    metadata: Dict[str, Any] = {"executor_type": "program"}
    if normalized_status == "technical_error":
        metadata["technical_error_internal"] = True
    return {
        "rule_id": rule_id,
        "status": normalized_status,
        "result_status": normalized_status,
        "display_status": normalized_status,
        "is_compliant": True if normalized_status == "compliant" else None,
        "reason_code": reason_code,
        "metadata": metadata,
    }


async def _run_formal_customer_sample_batch_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rule_ids: List[str],
    record_ids: List[str],
    eval_items_by_record: Dict[str, List[Dict[str, Any]]],
    model_stats_by_record: Optional[Dict[str, Dict[str, int]]] = None,
) -> _WorkspaceStub:
    workspace = _WorkspaceStub()
    _configure_formal_customer_sample_batch_fixture(
        workspace,
        rule_ids=rule_ids,
        record_ids=record_ids,
    )
    original_update_progress = workspace.update_batch_job_progress

    def _update_incremental_progress(**kwargs: Any) -> None:
        items = kwargs.pop("items", None)
        failed_records = kwargs.pop("failed_records", None)
        original_update_progress(**kwargs)
        if items is not None:
            workspace.items = list(items)
        if failed_records is not None:
            workspace.failed_records = list(failed_records)

    workspace.update_batch_job_progress = _update_incremental_progress  # type: ignore[method-assign]
    service = _ServiceStub()

    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        visit_id = str(kwargs["bundle"]["visit_id"])
        return {
            "evaluation_results": [dict(item) for item in eval_items_by_record[visit_id]],
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
            **(
                {"model_execution_stats": dict(model_stats_by_record[visit_id])}
                if model_stats_by_record and visit_id in model_stats_by_record
                else {}
            ),
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def _get_qc_service() -> _ServiceStub:
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", _get_qc_service)
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0609_rules",
        lambda: [get_luxian_0609_rule(rule_id) for rule_id in rule_ids],
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    return workspace


@pytest.mark.asyncio
async def test_formal_customer_sample_all_model_rules_failed_has_no_items_and_failed_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule_ids = ["LX0609-06-01-04", "LX0609-06-01-05"]
    workspace = await _run_formal_customer_sample_batch_fixture(
        monkeypatch,
        rule_ids=rule_ids,
        record_ids=["visit-001"],
        eval_items_by_record={
            "visit-001": [
                _customer_batch_eval_item(rule_id, "technical_error", reason_code="model_invalid_output")
                for rule_id in rule_ids
            ],
        },
        model_stats_by_record={
            "visit-001": {
                "requested_rule_count": 2,
                "first_success_rule_count": 0,
                "retried_rule_count": 2,
                "recovered_rule_count": 0,
                "failed_rule_count": 2,
            }
        },
    )

    assert workspace.job["status"] == "failed"
    assert workspace.items == []
    assert len(workspace.failed_records) == 2
    assert workspace.summary is not None
    assert workspace.summary["execution_status"] == "failed"
    assert workspace.summary["completed_rule_count"] == 0
    assert workspace.summary["failed_rule_count"] == 2
    assert workspace.summary["failed_rule_ids"] == rule_ids
    assert workspace.summary["model_execution_stats"] == {
        "scope": "exam_lab",
        "requested_rule_count": 2,
        "first_success_rule_count": 0,
        "retried_rule_count": 2,
        "recovered_rule_count": 0,
        "failed_rule_count": 2,
        "first_answer_success_rate": 0.0,
        "recovery_success_rate": 0.0,
        "model_failure_rate": 1.0,
    }


@pytest.mark.asyncio
async def test_formal_customer_sample_true_data_gap_is_completed_without_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule_id = "LX0609-06-01-04"
    workspace = await _run_formal_customer_sample_batch_fixture(
        monkeypatch,
        rule_ids=[rule_id],
        record_ids=["visit-001"],
        eval_items_by_record={
            "visit-001": [
                {
                    **_customer_batch_eval_item(
                        rule_id,
                        "data_gap",
                        reason_code="required_field_missing",
                    ),
                    "missing_sources": ["exam_report"],
                    "missing_fields": ["result_text"],
                }
            ],
        },
    )

    assert workspace.job["status"] == "completed"
    assert workspace.failed_records == []
    assert workspace.items and workspace.items[0]["status"] == "data_gap"
    assert workspace.summary is not None
    assert workspace.summary["execution_status"] == "completed"
    assert workspace.summary["failed_count"] == 0
    assert workspace.summary["failed_record_count"] == 0
    assert workspace.summary["failed_rule_count"] == 0
    assert workspace.summary["failed_rule_ids"] == []
    assert workspace.summary["data_quality_gap_records"] == 1
    assert workspace.summary["record_status_breakdown"]["data_gap"] == 1


@pytest.mark.asyncio
async def test_formal_customer_sample_model_stats_sum_two_records_and_failed_record_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule_ids = ["LX0609-06-01-04", "LX0609-06-01-05"]
    workspace = await _run_formal_customer_sample_batch_fixture(
        monkeypatch,
        rule_ids=rule_ids,
        record_ids=["visit-001", "visit-002"],
        eval_items_by_record={
            "visit-001": [
                _customer_batch_eval_item("LX0609-06-01-04", "compliant"),
                _customer_batch_eval_item(
                    "LX0609-06-01-05",
                    "data_gap",
                    reason_code="required_field_missing",
                ),
            ],
            "visit-002": [
                _customer_batch_eval_item(
                    rule_id,
                    "technical_error",
                    reason_code="model_invalid_output",
                )
                for rule_id in rule_ids
            ],
        },
        model_stats_by_record={
            "visit-001": {
                "requested_rule_count": 1,
                "first_success_rule_count": 1,
                "retried_rule_count": 0,
                "recovered_rule_count": 0,
                "failed_rule_count": 0,
            },
            "visit-002": {
                "requested_rule_count": 2,
                "first_success_rule_count": 0,
                "retried_rule_count": 2,
                "recovered_rule_count": 0,
                "failed_rule_count": 2,
            },
        },
    )

    assert workspace.job["status"] == "failed"
    assert workspace.summary is not None
    assert workspace.summary["execution_status"] == "partial_failed"
    assert workspace.summary["success_count"] == 1
    assert workspace.summary["failed_record_count"] == 1
    assert workspace.summary["failed_rule_count"] == 2
    assert workspace.summary["completed_rule_count"] == 2
    assert workspace.summary["model_execution_stats"] == {
        "scope": "exam_lab",
        "requested_rule_count": 3,
        "first_success_rule_count": 1,
        "retried_rule_count": 2,
        "recovered_rule_count": 0,
        "failed_rule_count": 2,
        "first_answer_success_rate": 1 / 3,
        "recovery_success_rate": 0.0,
        "model_failure_rate": 2 / 3,
    }
    assert {
        rule_result["rule_code"]: {
            "total_records": rule_result["total_records"],
            "success_count": rule_result["success_count"],
            "failed_count": rule_result["failed_count"],
            "item_count": len(rule_result["items"]),
            "failed_record_count": len(rule_result["failed_records"]),
        }
        for rule_result in workspace.summary["rule_results"]
    } == {
        rule_id: {
            "total_records": 2,
            "success_count": 1,
            "failed_count": 1,
            "item_count": 1,
            "failed_record_count": 1,
        }
        for rule_id in rule_ids
    }
    assert len(workspace.items) == 2


@pytest.mark.asyncio
async def test_partial_failed_retry_executes_only_failed_pairs_and_merges_to_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _WorkspaceStub()
    all_rule_ids = ["LX0609-06-01-04", "LX0609-06-01-05", "LX0609-04-01-03"]
    _configure_formal_customer_sample_batch_fixture(
        workspace,
        rule_ids=all_rule_ids,
        record_ids=["visit-001", "visit-002"],
    )
    original_update_progress = workspace.update_batch_job_progress
    persisted_item_counts: list[int] = []

    def _update_incremental_progress(**kwargs: Any) -> None:
        items = kwargs.pop("items", None)
        failed_records = kwargs.pop("failed_records", None)
        original_update_progress(**kwargs)
        if items is not None:
            workspace.items = list(items)
            persisted_item_counts.append(len(workspace.items))
        if failed_records is not None:
            workspace.failed_records = list(failed_records)

    workspace.update_batch_job_progress = _update_incremental_progress  # type: ignore[method-assign]
    refs = list(workspace.job["filters"]["record_refs"])
    retry_scope = {
        "schema_version": "failed-rule-retry-v1",
        "attempt": 1,
        "record_refs": refs,
        "rule_ids": ["LX0609-06-01-05", "LX0609-04-01-03"],
        "record_rule_map": {
            CaseRef.from_mapping(refs[0]).as_key(): ["LX0609-06-01-05"],
            CaseRef.from_mapping(refs[1]).as_key(): ["LX0609-04-01-03"],
        },
        "pending_count": 2,
    }
    workspace.job["filters"]["failed_rule_retry"] = retry_scope

    def _item(visit_id: str, rule_id: str, status: str = "compliant") -> Dict[str, Any]:
        ref = next(ref for ref in refs if ref["visit_id"] == visit_id)
        return {
            **ref,
            "record_id": visit_id,
            "record_key": CaseRef.from_mapping(ref).as_key(),
            "rule_id": rule_id,
            "rule_code": rule_id,
            "rule_name": rule_id,
            "status": status,
            "result_status": status,
            "display_status": status,
            "is_compliant": status == "compliant",
            "schema_version": "lx0609-customer-result-v2",
            "rule_version": "2026-06-09",
            "reason_code": "verified",
            "findings": "已形成合法结果",
        }

    base_items = [
        _item("visit-001", "LX0609-06-01-04"),
        _item("visit-001", "LX0609-04-01-03"),
        _item("visit-002", "LX0609-06-01-04"),
        _item("visit-002", "LX0609-06-01-05"),
    ]
    base_failures = [
        {**_item("visit-001", "LX0609-06-01-05"), "error_phase": "result_status"},
        {**_item("visit-002", "LX0609-04-01-03"), "error_phase": "result_status"},
    ]
    base_rule_results = [
        {
            "rule_code": rule_id,
            "rule_name": rule_id,
            "status": "failed" if rule_id in {"LX0609-06-01-05", "LX0609-04-01-03"} else "completed",
        }
        for rule_id in all_rule_ids
    ]
    workspace.job.update(
        {
            "items": base_items,
            "failed_records": base_failures,
            "summary": {
                "execution_status": "partial_failed",
                "total_records": 2,
                "rule_count": 3,
                "execution_rule_count": 3,
                "completed_rule_count": 4,
                "failed_rule_count": 2,
                "rule_results": base_rule_results,
                "model_execution_stats": {
                    "scope": "exam_lab",
                    "requested_rule_count": 2,
                    "first_success_rule_count": 1,
                    "retried_rule_count": 1,
                    "recovered_rule_count": 0,
                    "failed_rule_count": 1,
                },
            },
            "total_records": 2,
        }
    )
    workspace.items = list(base_items)
    workspace.failed_records = list(base_failures)
    service = _ServiceStub()
    calls: list[tuple[str, tuple[str, ...]]] = []

    async def _evaluate_running_final_bundle_input(**kwargs: Any) -> Dict[str, Any]:
        visit_id = str(kwargs["bundle"]["visit_id"])
        active_rule_ids = tuple(kwargs["rule_ids"])
        calls.append((visit_id, active_rule_ids))
        return {
            "evaluation_results": [
                _customer_batch_eval_item(rule_id, "compliant")
                for rule_id in active_rule_ids
            ],
            "token_usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
        }

    service.evaluate_running_final_bundle_input = _evaluate_running_final_bundle_input  # type: ignore[attr-defined]
    monkeypatch.setattr(batch_worker, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(
        batch_worker,
        "load_luxian_0609_rules",
        lambda: [get_luxian_0609_rule(rule_id) for rule_id in all_rule_ids],
    )

    async def _get_qc_service() -> _ServiceStub:
        return service

    await batch_worker.run_sichuan_workspace_batch_job(
        workspace.job["id"],
        workspace=workspace,
        qc_service_provider=_get_qc_service,
    )

    assert calls == [
        ("visit-001", ("LX0609-06-01-05",)),
        ("visit-002", ("LX0609-04-01-03",)),
    ]
    assert persisted_item_counts
    assert min(persisted_item_counts) >= len(base_items)
    assert workspace.job["status"] == "completed"
    assert len(workspace.items) == 6
    assert workspace.failed_records == []
    assert workspace.summary is not None
    assert workspace.summary["execution_status"] == "completed"
    assert workspace.summary["rule_count"] == 3
    assert workspace.summary["retry_recovered_count"] == 2
    assert workspace.summary["retry_remaining_count"] == 0
    assert workspace.summary["model_execution_stats"]["requested_rule_count"] == 2
