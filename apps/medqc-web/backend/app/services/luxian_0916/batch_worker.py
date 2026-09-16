"""Luxian0916 独立批量执行器。

此模块只负责病历装载、规则执行与结果搬运；规则的业务判定完全归属各规则执行器。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from ..custom_qc_workspace_service import CustomQCWorkspaceService
from ..llm_config_loader import LLMConfigLoader
from ..qc_llm_client import SichuanQCLLMClient
from ..sample_programmatic_evidence import build_programmatic_evidence_payload
from .bundle_reader import load_luxian_0916_bundle
from .contracts import Luxian0916RuleResult
from .input_context import (
    add_luxian_0916_evidence_sources,
    build_luxian_0916_context,
    merge_luxian_0916_semantic_facts,
)
from .orchestrator import Luxian0916Execution, execute_luxian_0916
from .rule_catalog import LUXIAN_0916_RULE_CATALOG
from .semantic_extractor import extract_luxian_0916_facts


LUXIAN_0916_RULE_SET_KEY = "luxian_0916_qc_v1"
_RULE_IDS = tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
_RULE_ORDER = {rule_id: index for index, rule_id in enumerate(_RULE_IDS)}
_RULE_NAMES = {rule.rule_id: rule.name for rule in LUXIAN_0916_RULE_CATALOG}
SemanticGenerate = Callable[..., Awaitable[dict[str, Any]]]


async def run_luxian_0916_batch_job(
    job_id: str,
    *,
    workspace: CustomQCWorkspaceService,
    max_record_concurrency: int | None = None,
    semantic_generate: SemanticGenerate | None = None,
) -> None:
    """执行一个 Luxian0916 批量任务，任何失败只隔离在该任务内。"""

    job = workspace.get_batch_job_for_processing(job_id=job_id)
    if not job:
        return
    if str(job.get("job_kind") or "").strip().lower() == "parent":
        return

    filters = _mapping(job.get("filters"))
    try:
        if str(filters.get("rule_set_key") or "").strip() != LUXIAN_0916_RULE_SET_KEY:
            raise ValueError("Luxian0916 worker only accepts luxian_0916_qc_v1")
        _validate_requested_rule_ids(filters.get("rule_ids"))
    except Exception as exc:
        workspace.fail_batch_job(
            job_id=job_id,
            error_message=f"Luxian0916 任务配置无效: {type(exc).__name__}",
        )
        return

    if not workspace.mark_batch_job_running(job_id=job_id):
        return

    try:
        records = _collect_records(workspace=workspace, job=job, filters=filters)
        hydrated_records = workspace.hydrate_records_with_medical_text(records)
        total_records = len(hydrated_records)
        if total_records == 0:
            raise ValueError("批量任务未收集到可执行病历，请确认样本病历已同步到当前病历库")

        concurrency = _resolve_concurrency(
            requested=max_record_concurrency,
            filter_value=filters.get("max_parallel_records"),
            total_records=total_records,
        )
        generate = semantic_generate or await _build_semantic_generate(filters)
        workspace.update_batch_job_progress(
            job_id=job_id,
            step_key="prepare",
            rule_index=0,
            rule_count=len(_RULE_IDS),
            processed_records=0,
            total_records=total_records,
            summary_patch={
                "rule_count": len(_RULE_IDS),
                "total_records": total_records,
                "rule_set_key": LUXIAN_0916_RULE_SET_KEY,
                "max_parallel_records": concurrency,
            },
            progress_patch={
                "max_parallel_records": concurrency,
                "active_record_count": 0,
                "queued_record_count": total_records,
            },
        )

        semaphore = asyncio.Semaphore(concurrency)
        progress_lock = asyncio.Lock()
        processed_records = 0

        async def execute_record(record: Mapping[str, Any]) -> _RecordExecution:
            nonlocal processed_records
            async with semaphore:
                outcome = await _execute_record(
                    record=record,
                    job=job,
                    semantic_generate=generate,
                )
            async with progress_lock:
                processed_records += 1
                workspace.update_batch_job_progress(
                    job_id=job_id,
                    step_key="run",
                    rule_index=len(_RULE_IDS),
                    rule_count=len(_RULE_IDS),
                    processed_records=processed_records,
                    total_records=total_records,
                    summary_patch={
                        "rule_count": len(_RULE_IDS),
                        "total_records": total_records,
                        "rule_set_key": LUXIAN_0916_RULE_SET_KEY,
                    },
                    progress_patch={
                        "max_parallel_records": concurrency,
                        "active_record_count": max(0, min(concurrency, total_records - processed_records)),
                        "queued_record_count": max(0, total_records - processed_records),
                    },
                )
            return outcome

        outcomes = await asyncio.gather(
            *(execute_record(record) for record in hydrated_records),
        )
        items = [item for outcome in outcomes for item in outcome.items]
        diagnostic_failures = [
            failure for outcome in outcomes for failure in outcome.diagnostic_failures
        ]
        failed_records = [
            failure for outcome in outcomes for failure in outcome.failed_records
        ]
        all_failures = [*diagnostic_failures, *failed_records]
        items.sort(key=_item_sort_key)
        all_failures.sort(key=_failure_sort_key)

        completed_records = sum(1 for outcome in outcomes if not outcome.failed_records)
        issue_records = len(
            {
                _record_identity_from_item(item)
                for item in items
                if item.get("status") == "non_compliant"
            }
        )
        compliant_records = len(
            {
                _record_identity_from_item(item)
                for item in items
                if item.get("status") == "compliant"
            }
        )
        status_counts = _status_counts(items)
        semantic_diagnostics = [
            outcome.semantic_diagnostic
            for outcome in outcomes
            if outcome.semantic_diagnostic
        ]
        semantic_extraction_failures = _semantic_extraction_failures(outcomes)
        summary = {
            "execution_status": (
                "completed_with_record_failures" if failed_records else "completed"
            ),
            "rule_set_key": LUXIAN_0916_RULE_SET_KEY,
            "rule_count": len(_RULE_IDS),
            "total_records": total_records,
            "max_parallel_records": concurrency,
            "success_count": completed_records,
            "failed_count": len(failed_records),
            "failed_record_count": len(failed_records),
            "issue_records": issue_records,
            "compliant_records": compliant_records,
            "status_counts": status_counts,
            "display_status_counts": status_counts,
            "diagnostic_rule_failure_count": len(diagnostic_failures),
            "semantic_llm_call_count": sum(
                int(item.get("llm_call_count") or 0) for item in semantic_diagnostics
            ),
            "semantic_extraction_invalid_count": len(semantic_extraction_failures),
            "semantic_extraction_failures": semantic_extraction_failures,
            "progress": {
                "step_key": "completed",
                "processed_records": total_records,
                "total_records": total_records,
                "max_parallel_records": concurrency,
            },
        }
        workspace.complete_batch_job(
            job_id=job_id,
            summary=summary,
            items=items,
            failed_records=all_failures,
            persist_record_envelopes=False,
        )
    except Exception as exc:  # noqa: BLE001 - 仅标记当前任务失败
        workspace.fail_batch_job(job_id=job_id, error_message=f"Luxian0916 执行失败: {type(exc).__name__}")


class _RecordExecution:
    def __init__(
        self,
        *,
        items: Sequence[dict[str, Any]] = (),
        diagnostic_failures: Sequence[dict[str, Any]] = (),
        failed_records: Sequence[dict[str, Any]] = (),
        semantic_diagnostic: Mapping[str, Any] | None = None,
        semantic_extraction_failure: Mapping[str, Any] | None = None,
    ) -> None:
        self.items = tuple(items)
        self.diagnostic_failures = tuple(diagnostic_failures)
        self.failed_records = tuple(failed_records)
        self.semantic_diagnostic = dict(semantic_diagnostic or {})
        self.semantic_extraction_failure = dict(semantic_extraction_failure or {})


async def _execute_record(
    *,
    record: Mapping[str, Any],
    job: Mapping[str, Any],
    semantic_generate: SemanticGenerate,
) -> _RecordExecution:
    identity = _record_identity(record)
    try:
        bundle = await asyncio.to_thread(
            load_luxian_0916_bundle,
            scene=_resolve_scene(record=record, job=job),
            institute_id=identity["institute_id"],
            patient_id=identity["patient_id"],
            visit_id=identity["visit_id"],
        )
        evidence_payload = await asyncio.to_thread(
            build_programmatic_evidence_payload,
            bundle=bundle,
            medical_text=str(record.get("medical_text") or ""),
        )
        evidence_payload = add_luxian_0916_evidence_sources(
            bundle=bundle,
            evidence_payload=evidence_payload,
        )
        context = build_luxian_0916_context(
            bundle=bundle,
            evidence_payload=evidence_payload,
        )
        extracted = await extract_luxian_0916_facts(
            evidence_payload=evidence_payload,
            rule_ids=_RULE_IDS,
            generate=semantic_generate,
        )
        context = merge_luxian_0916_semantic_facts(
            context=context,
            extracted=extracted,
        )
        execution = await asyncio.to_thread(execute_luxian_0916, context, _RULE_IDS)
        outcome = _execution_to_record_outcome(
            identity=identity,
            record=record,
            execution=execution,
        )
        return _RecordExecution(
            items=outcome.items,
            diagnostic_failures=outcome.diagnostic_failures,
            failed_records=outcome.failed_records,
            semantic_diagnostic=_mapping(extracted.get("diagnostic")),
            semantic_extraction_failure=_semantic_extraction_failure(
                identity=identity,
                record=record,
                diagnostic=_mapping(extracted.get("diagnostic")),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 单病历必须隔离
        return _RecordExecution(
            failed_records=(
                {
                    **identity,
                    "record_id": str(record.get("record_id") or identity["visit_id"]),
                    "error_phase": "record_execution",
                    "error_type": type(exc).__name__,
                },
            ),
        )


def _execution_to_record_outcome(
    *,
    identity: Mapping[str, str],
    record: Mapping[str, Any],
    execution: Luxian0916Execution,
) -> _RecordExecution:
    items = [
        _transport_item(identity=identity, record=record, result=result)
        for result in execution.results
    ]
    failures = [
        {
            **identity,
            "record_id": str(record.get("record_id") or identity["visit_id"]),
            "error_phase": "rule_execution",
            **failure.to_dict(),
        }
        for failure in execution.failures
    ]
    return _RecordExecution(items=items, diagnostic_failures=failures)


def _transport_item(
    *,
    identity: Mapping[str, str],
    record: Mapping[str, Any],
    result: Luxian0916RuleResult,
) -> dict[str, Any]:
    """仅追加病例与规则身份；规则合同字段不改写。"""

    return {
        **result.to_dict(),
        **identity,
        "record_id": str(record.get("record_id") or identity["visit_id"]),
        "record_key": "|".join(
            (identity["institute_id"], identity["patient_id"], identity["visit_id"])
        ),
        "patient_name": str(record.get("patient_name") or ""),
        "rule_code": result.rule_id,
        "customer_rule_id": result.rule_id,
        "qc_point_id": result.rule_id,
        "rule_name": _RULE_NAMES[result.rule_id],
    }


def _collect_records(
    *,
    workspace: CustomQCWorkspaceService,
    job: Mapping[str, Any],
    filters: Mapping[str, Any],
) -> list[dict[str, Any]]:
    persisted_refs = filters.get("record_refs")
    has_persisted_refs = isinstance(persisted_refs, list) and bool(persisted_refs)
    if str(filters.get("sample_pool_id") or "").strip() and not has_persisted_refs:
        raise ValueError("样本池任务缺少 filters.record_refs")
    return workspace.collect_records(
        scope=str(job.get("scope") or "all"),
        department=filters.get("department"),
        doctor=filters.get("doctor"),
        date_field=filters.get("date_field") or "admission",
        start_date=filters.get("start_date"),
        end_date=filters.get("end_date"),
        keyword=filters.get("keyword"),
        record_ids=None if has_persisted_refs else job.get("record_ids") or None,
        record_refs=persisted_refs if has_persisted_refs else None,
    )


def _validate_requested_rule_ids(value: Any) -> None:
    if value in (None, []):
        return
    if not isinstance(value, list):
        raise ValueError("Luxian0916 rule_ids must be a list when present")
    requested = tuple(str(item or "").strip().upper() for item in value)
    if requested != _RULE_IDS:
        raise ValueError("Luxian0916 批量任务必须执行完整 32 条规则")


def _resolve_concurrency(*, requested: int | None, filter_value: Any, total_records: int) -> int:
    candidates = [value for value in (requested, filter_value) if value is not None]
    raw = candidates[0] if candidates else 1
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1
    return max(1, min(value, max(1, total_records)))


async def _build_semantic_generate(filters: Mapping[str, Any]) -> SemanticGenerate:
    """为本任务构造一个模型客户端；每份病历由提取器最多调用一次。"""

    config = dict(await LLMConfigLoader.load_config(config_name="default", user_id=None) or {})
    custom_parameters = dict(_mapping(config.get("custom_parameters")))
    for filter_key, config_key in (
        ("temperature", "temperature"),
        ("top_p", "top_p"),
        ("max_tokens", "max_tokens"),
    ):
        value = filters.get(filter_key)
        if value is not None:
            custom_parameters[config_key] = value
    config["custom_parameters"] = custom_parameters
    model_code = str(filters.get("model_code") or "").strip()
    if model_code:
        config["model"] = model_code
    return SichuanQCLLMClient(config or None).generate


def _record_identity(record: Mapping[str, Any]) -> dict[str, str]:
    institute_id = str(record.get("institute_id") or "").strip()
    patient_id = str(record.get("patient_id") or "").strip()
    visit_id = str(record.get("visit_id") or record.get("record_id") or "").strip()
    if not all((institute_id, patient_id, visit_id)):
        raise ValueError("病历三坐标不完整")
    return {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
    }


def _resolve_scene(*, record: Mapping[str, Any], job: Mapping[str, Any]) -> str:
    scene = str(record.get("scope") or job.get("scope") or "").strip().lower()
    return "final" if scene == "final" else "running"


def _status_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _item_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(item.get("institute_id") or ""),
        str(item.get("patient_id") or ""),
        str(item.get("visit_id") or ""),
        _RULE_ORDER.get(str(item.get("rule_id") or ""), len(_RULE_ORDER)),
    )


def _failure_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str, int, str]:
    return (
        str(item.get("institute_id") or ""),
        str(item.get("patient_id") or ""),
        str(item.get("visit_id") or ""),
        _RULE_ORDER.get(str(item.get("rule_id") or ""), len(_RULE_ORDER)),
        str(item.get("error_phase") or ""),
    )


def _record_identity_from_item(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("institute_id") or ""),
        str(item.get("patient_id") or ""),
        str(item.get("visit_id") or ""),
    )


def _semantic_extraction_failure(
    *,
    identity: Mapping[str, str],
    record: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    """为提取无效保留一次、可定位且不含病历原文的任务级诊断。"""

    if diagnostic.get("code") != "semantic_extraction_invalid":
        return {}
    return {
        **identity,
        "record_id": str(record.get("record_id") or identity["visit_id"]),
        "code": "semantic_extraction_invalid",
        "document_count": _nonnegative_int(diagnostic.get("document_count")),
        "llm_call_count": _nonnegative_int(diagnostic.get("llm_call_count")),
    }


def _semantic_extraction_failures(
    outcomes: Sequence[_RecordExecution],
) -> list[dict[str, Any]]:
    """按病历三坐标去重，确保汇总计数与可定位异常明细严格一致。"""

    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for outcome in outcomes:
        failure = outcome.semantic_extraction_failure
        if not failure:
            continue
        identity = _record_identity_from_item(failure)
        unique.setdefault(identity, dict(failure))
    return [unique[identity] for identity in sorted(unique)]


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["LUXIAN_0916_RULE_SET_KEY", "run_luxian_0916_batch_job"]
