"""Luxian0916 独立批量执行器。

此模块只负责病历装载、规则执行与结果搬运；规则的业务判定完全归属各规则执行器。
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from ..custom_qc_workspace_service import CustomQCWorkspaceService
from ..llm_config_loader import LLMConfigLoader
from ..qc_llm_client import SichuanQCLLMClient
from ..sample_programmatic_evidence import build_programmatic_evidence_payload
from .bundle_reader import load_luxian_0916_bundle
from .contracts import Luxian0916RuleResult
from .critical_value_018 import (
    build_critical_value_018_facts,
    merge_critical_value_018_facts,
)
from .critical_value_018_stage2 import extract_critical_value_018_stage2_facts
from .disease_change_015016 import (
    load_disease_change_015016_facts,
    merge_disease_change_015016_facts,
)
from .disease_change_stage2 import extract_disease_change_stage2_facts
from .execution_integrity import (
    LUXIAN_0916_RULE_SET_KEY,
    validate_luxian_0916_task_delivery,
)
from .input_context import (
    add_luxian_0916_evidence_sources,
    build_luxian_0916_context,
    merge_luxian_0916_semantic_facts,
)
from .orchestrator import Luxian0916Execution, execute_luxian_0916
from .rule_catalog import LUXIAN_0916_RULE_CATALOG
from .semantic_extractor import (
    SEMANTIC_CONTRACT_FAILURE_DETAILS,
    extract_luxian_0916_facts,
)


_RULE_IDS = tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
_STRUCTURED_DISEASE_CHANGE_RULE_IDS = frozenset({"LX0916-015", "LX0916-016"})
_CRITICAL_VALUE_018_RULE_IDS = frozenset({"LX0916-018"})
_CRITICAL_VALUE_018_STRICT_SOURCE_LIMITS = {
    "labtest_master": 100,
    "labtest_item_report": 400,
}
_SHARED_SEMANTIC_RULE_IDS = tuple(
    rule_id
    for rule_id in _RULE_IDS
    if rule_id
    not in (
        _STRUCTURED_DISEASE_CHANGE_RULE_IDS
        | _CRITICAL_VALUE_018_RULE_IDS
    )
)
_RULE_ORDER = {rule_id: index for index, rule_id in enumerate(_RULE_IDS)}
_RULE_NAMES = {rule.rule_id: rule.name for rule in LUXIAN_0916_RULE_CATALOG}
_SEMANTIC_FAILURE_STAGES = frozenset(
    {
        "generation",
        "response_shape",
        "output_truncated",
        "content_type",
        "json_syntax",
        "contract_validation",
        "grounding_validation",
    }
)
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
        raw_generate = semantic_generate or await _build_semantic_generate(filters)
        total_tokens = 0
        total_api_time = 0.0
        generate_call_count = 0
        usage_incomplete_count = 0
        time_incomplete_count = 0

        async def generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal total_tokens, total_api_time, generate_call_count
            nonlocal usage_incomplete_count, time_incomplete_count
            generate_call_count += 1
            try:
                response = await raw_generate(*args, **kwargs)
            except BaseException:
                usage_incomplete_count += 1
                time_incomplete_count += 1
                raise

            response_stats = response if isinstance(response, Mapping) else {}
            sdk_usage = _mapping(response_stats.get("_usage_breakdown"))
            raw_usage = _mapping(response_stats.get("usage"))
            tokens = (
                sdk_usage["total_tokens"]
                if "total_tokens" in sdk_usage
                else raw_usage.get("total_tokens")
            )
            valid_tokens = (
                isinstance(tokens, int)
                and not isinstance(tokens, bool)
                and tokens >= 0
            )
            if valid_tokens:
                total_tokens += tokens
            # SDK 在完全没有上游 usage 时也合成零汇总，不能将其视为真实零成本。
            raw_tokens = raw_usage.get("total_tokens")
            synthetic_zero = (
                "total_tokens" in sdk_usage
                and valid_tokens
                and tokens == 0
                and not (
                    isinstance(raw_tokens, int)
                    and not isinstance(raw_tokens, bool)
                    and raw_tokens >= 0
                )
            )
            if not valid_tokens or synthetic_zero:
                usage_incomplete_count += 1
            api_time = response_stats.get("_api_time")
            try:
                valid_time = (
                    isinstance(api_time, (int, float))
                    and not isinstance(api_time, bool)
                    and math.isfinite(api_time)
                    and api_time >= 0
                )
            except OverflowError:
                valid_time = False
            if valid_time:
                total_api_time += api_time
            else:
                time_incomplete_count += 1
            return response
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
        rule_failures = [
            failure for outcome in outcomes for failure in outcome.rule_failures
        ]
        failed_records = [
            failure for outcome in outcomes for failure in outcome.failed_records
        ]
        all_failures = [*rule_failures, *failed_records]
        items.sort(key=_item_sort_key)
        all_failures.sort(key=_failure_sort_key)

        failed_record_identities = {
            _record_identity_from_item(failure) for failure in all_failures
        }
        completed_records = total_records - len(failed_record_identities)
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
        disease_change_stage2_diagnostics = [
            outcome.disease_change_stage2_diagnostic
            for outcome in outcomes
            if outcome.disease_change_stage2_diagnostic
        ]
        critical_value_018_stage2_diagnostics = [
            outcome.critical_value_018_stage2_diagnostic
            for outcome in outcomes
            if outcome.critical_value_018_stage2_diagnostic
        ]
        semantic_extraction_failures = _semantic_extraction_failures(outcomes)
        semantic_contract_retries = _semantic_contract_retries(outcomes)
        summary = {
            "total_tokens": total_tokens,
            "total_processing_time": total_api_time,
            "llm_generate_call_count": generate_call_count,
            "llm_usage_incomplete_count": usage_incomplete_count,
            "llm_time_incomplete_count": time_incomplete_count,
            "llm_usage_complete": usage_incomplete_count == 0,
            "llm_time_complete": time_incomplete_count == 0,
            "execution_status": (
                "partial_failed"
                if all_failures and items
                else "failed"
                if all_failures
                else "completed"
            ),
            "rule_set_key": LUXIAN_0916_RULE_SET_KEY,
            "rule_count": len(_RULE_IDS),
            "total_records": total_records,
            "max_parallel_records": concurrency,
            "success_count": completed_records,
            "failed_count": len(failed_record_identities),
            "failed_record_count": len(failed_record_identities),
            "completed_rule_count": len(items),
            "failed_rule_count": len(all_failures),
            "issue_records": issue_records,
            "compliant_records": compliant_records,
            "status_counts": status_counts,
            "display_status_counts": status_counts,
            "diagnostic_rule_failure_count": len(rule_failures),
            "semantic_llm_call_count": sum(
                int(item.get("llm_call_count") or 0) for item in semantic_diagnostics
            ),
            "semantic_extraction_invalid_count": len(semantic_extraction_failures),
            "semantic_extraction_failures": semantic_extraction_failures,
            "semantic_contract_retry_count": len(semantic_contract_retries),
            "semantic_contract_retries": semantic_contract_retries,
            "disease_change_stage2_llm_call_count": _diagnostic_total(
                disease_change_stage2_diagnostics, "llm_call_count"
            ),
            "disease_change_stage2_prompt_tokens": _diagnostic_total(
                disease_change_stage2_diagnostics, "prompt_tokens"
            ),
            "disease_change_stage2_completion_tokens": _diagnostic_total(
                disease_change_stage2_diagnostics, "completion_tokens"
            ),
            "disease_change_stage2_total_tokens": _diagnostic_total(
                disease_change_stage2_diagnostics, "total_tokens"
            ),
            "disease_change_stage2_model_elapsed_ms": _diagnostic_total(
                disease_change_stage2_diagnostics, "model_elapsed_ms"
            ),
            "disease_change_stage2_failure_count": _diagnostic_total(
                disease_change_stage2_diagnostics, "failure_count"
            ),
            "disease_change_stage2_usage_incomplete_count": sum(
                item.get("usage_incomplete") is True
                for item in disease_change_stage2_diagnostics
            ),
            "critical_value_018_stage2_llm_call_count": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "llm_call_count"
            ),
            "critical_value_018_stage2_prompt_tokens": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "prompt_tokens"
            ),
            "critical_value_018_stage2_completion_tokens": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "completion_tokens"
            ),
            "critical_value_018_stage2_total_tokens": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "total_tokens"
            ),
            "critical_value_018_stage2_model_elapsed_ms": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "model_elapsed_ms"
            ),
            "critical_value_018_stage2_failure_count": _diagnostic_total(
                critical_value_018_stage2_diagnostics, "failure_count"
            ),
            "critical_value_018_stage2_usage_incomplete_count": sum(
                item.get("usage_incomplete") is True
                for item in critical_value_018_stage2_diagnostics
            ),
            "critical_value_018_stage2_model_parameters": _diagnostic_parameters(
                critical_value_018_stage2_diagnostics
            ),
            "progress": {
                "step_key": "completed",
                "processed_records": total_records,
                "total_records": total_records,
                "max_parallel_records": concurrency,
            },
        }
        validate_luxian_0916_task_delivery(
            summary=summary,
            items=items,
            failures=all_failures,
            expected_rule_ids=_RULE_IDS,
            expected_record_refs=hydrated_records,
        )
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
        rule_failures: Sequence[dict[str, Any]] = (),
        failed_records: Sequence[dict[str, Any]] = (),
        semantic_diagnostic: Mapping[str, Any] | None = None,
        disease_change_stage2_diagnostic: Mapping[str, Any] | None = None,
        critical_value_018_stage2_diagnostic: Mapping[str, Any] | None = None,
        semantic_extraction_failure: Mapping[str, Any] | None = None,
        semantic_contract_retry: Mapping[str, Any] | None = None,
    ) -> None:
        self.items = tuple(items)
        self.rule_failures = tuple(rule_failures)
        self.failed_records = tuple(failed_records)
        self.semantic_diagnostic = dict(semantic_diagnostic or {})
        self.disease_change_stage2_diagnostic = dict(
            disease_change_stage2_diagnostic or {}
        )
        self.critical_value_018_stage2_diagnostic = dict(
            critical_value_018_stage2_diagnostic or {}
        )
        self.semantic_extraction_failure = dict(semantic_extraction_failure or {})
        self.semantic_contract_retry = dict(semantic_contract_retry or {})


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
            strict_structured_source_limits=(
                _CRITICAL_VALUE_018_STRICT_SOURCE_LIMITS
            ),
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
            # 015/016 与 018 已迁入独立族；共享 Prompt 不再重复提取其同名事件事实。
            rule_ids=_SHARED_SEMANTIC_RULE_IDS,
            generate=semantic_generate,
        )
        context = merge_luxian_0916_semantic_facts(
            context=context,
            extracted=extracted,
        )
        critical_value_018_stage1: Mapping[str, Any] = {}
        try:
            critical_value_018_stage1_output = build_critical_value_018_facts(
                bundle=bundle,
                evidence_payload=evidence_payload,
            )
            if not isinstance(critical_value_018_stage1_output, Mapping):
                raise TypeError("Critical value 018 Stage1 output must be a mapping")
            critical_value_018_stage1 = critical_value_018_stage1_output
            critical_value_018 = await extract_critical_value_018_stage2_facts(
                evidence_payload=evidence_payload,
                structured_facts=critical_value_018_stage1,
                scene=_resolve_scene(record=record, job=job),
                generate=semantic_generate,
            )
            if not isinstance(critical_value_018, Mapping):
                raise TypeError("Critical value 018 Stage2 output must be a mapping")
        except Exception:  # noqa: BLE001 - 族内异常只能降级 018
            critical_value_018 = _critical_value_018_internal_failure(
                critical_value_018_stage1,
                scene=_resolve_scene(record=record, job=job),
            )
        context = merge_critical_value_018_facts(
            context=context,
            structured_facts=critical_value_018,
        )
        # 015/016 的触发事实由本次住院三坐标的原始结构化行独立读取。
        # 必须在共享模型事实合并后覆盖，防止旧 disease_changes 回流。
        structured_disease_change = await asyncio.to_thread(
            load_disease_change_015016_facts,
            institute_id=identity["institute_id"],
            patient_id=identity["patient_id"],
            visit_id=identity["visit_id"],
        )
        try:
            stage2_output = await extract_disease_change_stage2_facts(
                evidence_payload=evidence_payload,
                structured_facts=structured_disease_change,
                scene=_resolve_scene(record=record, job=job),
                generate=semantic_generate,
            )
            if not isinstance(stage2_output, Mapping):
                raise TypeError("Stage2 output must be a mapping")
            structured_disease_change = dict(stage2_output)
        except Exception:  # noqa: BLE001 - Stage2 异常只能降级 015/016
            structured_disease_change = _stage2_internal_failure(
                structured_disease_change
            )
        context = merge_disease_change_015016_facts(
            context=context,
            structured_facts=structured_disease_change,
        )
        execution = await asyncio.to_thread(execute_luxian_0916, context, _RULE_IDS)
        outcome = _execution_to_record_outcome(
            identity=identity,
            record=record,
            execution=execution,
            semantic_diagnostic=_mapping(extracted.get("diagnostic")),
        )
        return _RecordExecution(
            items=outcome.items,
            rule_failures=outcome.rule_failures,
            failed_records=outcome.failed_records,
            semantic_diagnostic=_mapping(extracted.get("diagnostic")),
            disease_change_stage2_diagnostic=_mapping(
                structured_disease_change.get("diagnostic")
            ),
            critical_value_018_stage2_diagnostic=_mapping(
                critical_value_018.get("diagnostic")
            ),
            semantic_extraction_failure=_semantic_extraction_failure(
                identity=identity,
                record=record,
                diagnostic=_mapping(extracted.get("diagnostic")),
            ),
            semantic_contract_retry=_semantic_contract_retry(
                identity=identity,
                record=record,
                diagnostic=_mapping(extracted.get("diagnostic")),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 单病历必须隔离
        return _RecordExecution(
            failed_records=tuple(
                {
                    **identity,
                    "record_id": str(record.get("record_id") or identity["visit_id"]),
                    "error_phase": "record_execution",
                    "rule_id": rule_id,
                    "error_type": type(exc).__name__,
                }
                for rule_id in _RULE_IDS
            ),
        )


def _execution_to_record_outcome(
    *,
    identity: Mapping[str, str],
    record: Mapping[str, Any],
    execution: Luxian0916Execution,
    semantic_diagnostic: Mapping[str, Any],
) -> _RecordExecution:
    extraction_failed = (
        semantic_diagnostic.get("code") == "semantic_extraction_invalid"
        and isinstance(semantic_diagnostic.get("failure_stage"), str)
        and semantic_diagnostic.get("failure_stage") in _SEMANTIC_FAILURE_STAGES
    )
    failed_rule_ids = semantic_diagnostic.get("failed_rule_ids")
    failed_rule_ids = (
        set(failed_rule_ids).intersection(_SHARED_SEMANTIC_RULE_IDS)
        if isinstance(failed_rule_ids, (list, tuple))
        and all(isinstance(rule_id, str) for rule_id in failed_rule_ids)
        else set()
    )
    items = []
    failures = [
        {
            **identity,
            "record_id": str(record.get("record_id") or identity["visit_id"]),
            "error_phase": "rule_execution",
            **failure.to_dict(),
        }
        for failure in execution.failures
    ]
    for result in execution.results:
        if (
            extraction_failed
            and result.rule_id in failed_rule_ids
            and result.status == "data_quality_gap"
            and result.reason_code in {"semantic_fact_unavailable", "event_fact_unavailable"}
            and not _has_existing_gap_facts(result)
        ):
            failures.append(
                {
                    **identity,
                    "record_id": str(record.get("record_id") or identity["visit_id"]),
                    "error_phase": "semantic_extraction",
                    "rule_id": result.rule_id,
                    "error_type": (
                        "SemanticGenerationError"
                        if semantic_diagnostic.get("failure_stage") == "generation"
                        else "SemanticExtractionError"
                    ),
                }
            )
            continue
        items.append(_transport_item(identity=identity, record=record, result=result))
    return _RecordExecution(items=items, rule_failures=failures)


def _has_existing_gap_facts(result: Luxian0916RuleResult) -> bool:
    """已有来源缺口或合法未知事实不归因于本次抽取失败。"""
    facts = result.decision_facts
    return (
        (result.rule_id == "LX0916-002" and facts.get("history_narrator_available") is False)
        or (result.rule_id == "LX0916-008" and facts.get("age_years_available") is False)
        or "semantic_state" in facts
        or "item_states" in facts
        or facts.get("document_completeness") in ("complete", "incomplete", "unknown")
        or (
            result.rule_id == "LX0916-017"
            and any(
                isinstance(event, Mapping) and event.get("appropriateness") == "unknown"
                for event in facts.get("events", ())
            )
        )
    )


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
    """构造固定采样客户端；每份病历最多调用两次，第二次仅用于合同无效重试。"""

    config = dict(await LLMConfigLoader.load_config(config_name="default", user_id=None) or {})
    custom_parameters = dict(_mapping(config.get("custom_parameters")))
    max_tokens = filters.get("max_tokens")
    if max_tokens is not None:
        custom_parameters["max_tokens"] = max_tokens
    # 0916 的语义事实抽取需要固定采样，任务筛选和保存的默认模型配置均不得覆盖。
    custom_parameters["temperature"] = 0.0
    custom_parameters["top_p"] = 1.0
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
    failure = {
        **identity,
        "record_id": str(record.get("record_id") or identity["visit_id"]),
        "code": "semantic_extraction_invalid",
        "document_count": _nonnegative_int(diagnostic.get("document_count")),
        "llm_call_count": _nonnegative_int(diagnostic.get("llm_call_count")),
    }
    failure_stage = diagnostic.get("failure_stage")
    if isinstance(failure_stage, str) and failure_stage in _SEMANTIC_FAILURE_STAGES:
        failure["failure_stage"] = failure_stage
    failure_detail = diagnostic.get("failure_detail")
    if (
        failure_stage == "contract_validation"
        and isinstance(failure_detail, str)
        and failure_detail in SEMANTIC_CONTRACT_FAILURE_DETAILS
    ):
        failure["failure_detail"] = failure_detail
    contract_retry_detail = diagnostic.get("contract_retry_detail")
    if (
        isinstance(contract_retry_detail, str)
        and contract_retry_detail in SEMANTIC_CONTRACT_FAILURE_DETAILS
    ):
        failure["contract_retry_detail"] = contract_retry_detail
    return failure


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


def _semantic_contract_retry(
    *,
    identity: Mapping[str, str],
    record: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    """保留已恢复合同抖动的病历坐标和固定子码，不保存模型输出或病历原文。"""

    detail = diagnostic.get("contract_retry_detail")
    if (
        diagnostic.get("code") != "semantic_extraction_ready"
        or diagnostic.get("contract_retry_applied") is not True
        or not isinstance(detail, str)
        or detail not in SEMANTIC_CONTRACT_FAILURE_DETAILS
    ):
        return {}
    return {
        **identity,
        "record_id": str(record.get("record_id") or identity["visit_id"]),
        "code": "semantic_contract_retry_applied",
        "llm_call_count": _nonnegative_int(diagnostic.get("llm_call_count")),
        "contract_retry_detail": detail,
    }


def _semantic_contract_retries(
    outcomes: Sequence[_RecordExecution],
) -> list[dict[str, Any]]:
    """按病历三坐标去重汇总已恢复的合同重试。"""

    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for outcome in outcomes:
        retry = outcome.semantic_contract_retry
        if not retry:
            continue
        identity = _record_identity_from_item(retry)
        unique.setdefault(identity, dict(retry))
    return [unique[identity] for identity in sorted(unique)]


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _diagnostic_total(diagnostics: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(_nonnegative_int(item.get(key)) for item in diagnostics)


def _diagnostic_parameters(
    diagnostics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """保留任务实际使用过的去重模型参数，不记录 Prompt 或病例内容。"""

    distinct: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        parameters = _mapping(diagnostic.get("model_parameters"))
        if parameters and parameters not in distinct:
            distinct.append(parameters)
    return distinct


def _critical_value_018_internal_failure(
    structured_facts: Mapping[str, Any], *, scene: str
) -> dict[str, Any]:
    """018 族未预期异常的安全壳，不伪造无危急值结论。"""

    result = dict(structured_facts)
    event_facts = dict(_mapping(structured_facts.get("event_facts")))
    protected_events: list[dict[str, Any]] = []
    triggered_count = 0
    for source_event in _sequence_of_mappings(event_facts.get("critical_values")):
        event = dict(source_event)
        if event.get("trigger_confirmed") is True:
            triggered_count += 1
            event["evaluation_window_mature"] = True
            event["stage2_state_by_rule"] = {"LX0916-018": "internal_failure"}
            event.pop("stage2_facts", None)
        protected_events.append(event)
    event_facts["critical_values"] = protected_events
    result["event_facts"] = event_facts
    states = _mapping(structured_facts.get("event_source_state_by_rule"))
    if states.get("LX0916-018") != "critical_value_source_complete":
        result["event_source_state_by_rule"] = {
            **states,
            "LX0916-018": "critical_value_source_invalid",
        }
    return {
        **result,
        "diagnostic": {
            "code": "critical_value_018_internal_failure",
            "event_count": triggered_count,
            "llm_call_count": 0,
            "attempt_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model_elapsed_ms": 0,
            "failure_count": max(1, triggered_count),
            "usage_incomplete": True,
            "model_parameters": {},
        },
    }


def _stage2_internal_failure(
    structured_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Stage2 未预期异常的安全壳：保留触发事实，不泄露异常或病例正文。"""

    result = dict(structured_facts)
    event_facts = dict(_mapping(structured_facts.get("event_facts")))
    protected_events: list[dict[str, Any]] = []
    triggered_count = 0
    for source_event in _sequence_of_mappings(event_facts.get("disease_changes")):
        event = dict(source_event)
        if event.get("trigger_confirmed") is True:
            triggered_count += 1
            event["stage2_state_by_rule"] = {
                "LX0916-015": "internal_failure",
                "LX0916-016": "internal_failure",
            }
            event.pop("stage2_facts", None)
        protected_events.append(event)
    event_facts["disease_changes"] = protected_events
    result["event_facts"] = event_facts
    result["diagnostic"] = {
        "code": "disease_change_stage2_internal_failure",
        "event_count": triggered_count,
        "llm_call_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model_elapsed_ms": 0,
        "failure_count": triggered_count * len(_STRUCTURED_DISEASE_CHANGE_RULE_IDS),
        "usage_incomplete": True,
    }
    return result


def _sequence_of_mappings(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["LUXIAN_0916_RULE_SET_KEY", "run_luxian_0916_batch_job"]
