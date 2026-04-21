from __future__ import annotations

from typing import Any, Dict, List, Optional
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

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

    def mark_batch_job_running(self, *, job_id: str) -> None:
        if job_id == self.job["id"]:
            self.job["status"] = "running"

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
    assert service.evaluate_calls == 0
    assert workspace.summary is not None
    assert workspace.summary.get("execution_strategy") == "fast_screen"
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
        background_tasks=BackgroundTasks(),
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
        background_tasks=BackgroundTasks(),
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
        background_tasks=BackgroundTasks(),
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
