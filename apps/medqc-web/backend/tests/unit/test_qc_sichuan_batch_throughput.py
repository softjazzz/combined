from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from types import SimpleNamespace

import pytest

from app.routers import qc_sichuan
from app.services.qc_rule_sets import SC_CONTENT_V1_RULE_IDS


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
    ) -> List[Dict[str, Any]]:
        ids = list(record_ids or [])
        return [
            {
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
    ) -> None:
        if job_id != self.job["id"]:
            return
        progress = {
            "step_key": step_key,
            "rule_index": rule_index,
            "rule_count": rule_count,
            "processed_records": processed_records,
            "total_records": total_records,
        }
        self.job["progress"] = progress
        self.progress_updates.append(
            {
                **progress,
                "summary_patch": dict(summary_patch or {}),
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
        self.job["status"] = "completed"
        self.summary = dict(summary)
        self.items = list(items)
        self.failed_records = list(failed_records)

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


class _ServiceStub:
    def __init__(self, status_by_rule: Optional[Dict[str, str]] = None) -> None:
        self.evaluate_calls = 0
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
        **_: Any,
    ) -> Dict[str, Any]:
        self.evaluate_calls += 1
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


def test_resolve_workspace_bundle_scene_should_follow_record_scope_when_scope_is_all():
    assert qc_sichuan._resolve_workspace_bundle_scene(current_scope="all", record_scope="final") == "final"
    assert qc_sichuan._resolve_workspace_bundle_scene(current_scope="all", record_scope="running") == "running"
    assert qc_sichuan._resolve_workspace_bundle_scene(current_scope="final", record_scope="running") == "final"
    assert qc_sichuan._resolve_workspace_bundle_scene(current_scope="running", record_scope="final") == "running"
    assert qc_sichuan._resolve_workspace_bundle_scene(current_scope="all", record_scope="") == ""


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
    assert service.evaluate_rule_for_visit_calls == 0


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

    monkeypatch.setattr(qc_sichuan, "adjudicate_postprocessed_qc_results", _fake_adjudicate)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")

    assert workspace.summary is not None
    assert len(workspace.items) == 9
    postprocess_summary = dict(workspace.summary.get("postprocess_summary") or {})
    assert postprocess_summary["confirmed_defect_count"] == 0
    assert postprocess_summary["qc_review_candidate_count"] == 0
    assert postprocess_summary["needs_review_count"] == 0
    assert postprocess_summary["data_quality_gap_count"] == 4
    assert postprocess_summary["rejected_by_system_count"] == 5
    assert postprocess_summary["technical_error_internal_count"] == 0
    assert workspace.summary["confirmed_defect_count"] == 0
    assert workspace.summary["qc_review_candidate_count"] == 0
    assert workspace.summary["needs_review_count"] == 0
    assert workspace.summary["data_quality_gap_count"] == 4
    assert workspace.summary["rejected_by_system_count"] == 5
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

    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

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

    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

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

    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", _should_not_call_bundle_eval)

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

    monkeypatch.setattr(qc_sichuan, "run_final_fast_screen", _fake_run_final_fast_screen)

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

    monkeypatch.setattr(qc_sichuan, "run_final_fast_screen", _should_not_call_fast_screen)
    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", _fake_evaluate_running_final_bundle)

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
        "department": "骨科",
        "doctor": "张医生",
        "date_field": "discharge",
        "start_date": "2026-06-01",
        "end_date": "2026-06-18",
        "keyword": "出院",
        "record_ids": sorted(
            {
                str(record.get("record_id") or record.get("visit_id") or "").strip()
                for record in first_records
                if str(record.get("record_id") or record.get("visit_id") or "").strip()
            }
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
