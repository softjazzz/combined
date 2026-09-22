"""LX0609-04-02-04 植入物信息影子运行。

影子运行只复用正式请求已经冻结的 Evidence Session，不创建新快照、不回读
源库，也不参与正式规则结果、Token 汇总或 Canonical 写入。
"""

from __future__ import annotations

from collections import Counter
from time import perf_counter
from typing import Any, Mapping, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_surgery_gate_execution import (
    NativeSurgeryGateExecutionResult,
    SurgeryGateLLMClient,
    execute_luxian_0609_native_surgery_gate_rules,
)
from .surgery_text_fact_contract import LX0609_025_REQUIRED_FIELDS


LUXIAN_0609_025_SHADOW_CONTRACT_VERSION = "lx0609-025-shadow-v1"
_RULE_ID = "LX0609-04-02-04"
_ALLOWED_FIELDS = frozenset(LX0609_025_REQUIRED_FIELDS)
_ALLOWED_FINAL_STATES = frozenset(
    {"compliant", "non_compliant", "not_applicable", "data_gap"}
)
_SHADOW_REASON_BY_STATUS = {
    "compliant": "surgery_text_fact_satisfied",
    "non_compliant": "surgery_text_fact_defect",
    "not_applicable": "surgery_text_fact_absent",
    "data_gap": "surgery_text_fact_unknown",
}
_ALLOWED_DECISION_REASONS_BY_STATUS = {
    "compliant": frozenset({"requirement_satisfied"}),
    "non_compliant": frozenset({"requirement_violated"}),
    "not_applicable": frozenset({"trigger_absent_complete"}),
    "data_gap": frozenset({
        "required_field_missing",
        "applicability_source_gap",
    }),
}


def _safe_error(reason_code: str, *, elapsed_ms: int) -> dict[str, Any]:
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": "shadow_error",
        "reason_code": reason_code,
        "operation_count": 0,
        "status_counts": {},
        "missing_field_counts": {},
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": max(0, elapsed_ms),
        "contract_version": LUXIAN_0609_025_SHADOW_CONTRACT_VERSION,
    }


def _decision_status(decision: RuleDecision) -> str:
    dimensions = (
        decision.applicability,
        decision.evidence_state,
        decision.qc_direction,
    )
    states = {
        (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
        ): "compliant",
        (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
        ): "non_compliant",
        (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ): "not_applicable",
        (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
        ): "data_gap",
    }
    status = states.get(dimensions)
    if status is None:
        raise ValueError("invalid 025 shadow decision")
    return status


def _safe_fields(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("invalid 025 shadow fields")
    fields = tuple(value)
    if (
        len(fields) != len(set(fields))
        or any(not isinstance(item, str) or item not in _ALLOWED_FIELDS for item in fields)
    ):
        raise ValueError("invalid 025 shadow fields")
    return fields


def _safe_operation_details(
    display_facts: Mapping[str, Any] | None,
) -> tuple[tuple[dict[str, Any], ...], Counter[str]]:
    if display_facts is None:
        return (), Counter()
    if not isinstance(display_facts, Mapping):
        raise ValueError("invalid 025 shadow facts")
    raw_details = display_facts.get("implant_event_details", [])
    if not isinstance(raw_details, list):
        raise ValueError("invalid 025 shadow facts")
    if len(raw_details) > 8:
        raise ValueError("invalid 025 shadow facts")
    operations: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for position, detail in enumerate(raw_details, start=1):
        if not isinstance(detail, Mapping):
            raise ValueError("invalid 025 shadow facts")
        missing_fields = _safe_fields(detail.get("missing_fields", []))
        operations.append(
            {
                "event_position": position,
                "status": "non_compliant",
                "reason_code": "required_field_missing",
                "missing_fields": list(missing_fields),
            }
        )
        counts.update(missing_fields)
    return tuple(operations), counts


def _safe_operation_count(materials: Luxian0609EvidenceMaterialStore) -> int:
    try:
        rows = materials.rows("surgery_record")
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return 0
    if not isinstance(rows, tuple) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("invalid 025 shadow materials")
    return len(rows)


def _surgery_record_preflight(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> str | None:
    """影子不把手术记录来源不可用伪装成可供人工复核的数据不足。"""

    observation = next(
        (
            item
            for item in snapshot.observations
            if item.source_key == "surgery_record"
        ),
        None,
    )
    if observation is None:
        return "source_missing"
    if observation.query_state.value == "error":
        return "source_query_error"
    if observation.query_state.value != "available":
        return "source_unavailable"
    if observation.completeness.value != "complete":
        return "source_truncated"
    try:
        rows = materials.rows("surgery_record")
    except EvidenceMaterialTruncated:
        return "source_truncated"
    except EvidenceMaterialUnavailable:
        return "source_unavailable"
    if not isinstance(rows, tuple) or not all(isinstance(row, Mapping) for row in rows):
        return "source_material_invalid"
    return None


def _summary(
    result: NativeSurgeryGateExecutionResult,
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    elapsed_ms: int,
) -> dict[str, Any]:
    if not isinstance(result, NativeSurgeryGateExecutionResult):
        raise ValueError("invalid 025 shadow result")
    if result.planned_rule_ids != (_RULE_ID,) or result.results:
        raise ValueError("invalid 025 shadow result")
    if len(result.decisions) != 1 or result.decisions[0].rule_id != _RULE_ID:
        raise ValueError("invalid 025 shadow result")
    decision = result.decisions[0]
    if decision.snapshot_hash != snapshot.snapshot_hash:
        raise ValueError("invalid 025 shadow result")
    status = _decision_status(decision)
    if status not in _ALLOWED_FINAL_STATES:
        raise ValueError("invalid 025 shadow result")
    if decision.reason_code not in _ALLOWED_DECISION_REASONS_BY_STATUS[status]:
        raise ValueError("invalid 025 shadow reason")
    numbers = (
        result.llm_call_count,
        result.prompt_tokens,
        result.completion_tokens,
        result.total_tokens,
    )
    if (
        any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in numbers)
        or result.llm_call_count > 1
        or result.total_tokens != result.prompt_tokens + result.completion_tokens
    ):
        raise ValueError("invalid 025 shadow result")
    display_fact_entries = tuple(result.customer_display_facts)
    if any(rule_id != _RULE_ID for rule_id, _ in display_fact_entries):
        raise ValueError("invalid 025 shadow result")
    if len(display_fact_entries) > 1:
        raise ValueError("invalid 025 shadow result")
    display_facts = display_fact_entries[0][1] if display_fact_entries else None
    operations, missing_field_counts = _safe_operation_details(display_facts)
    operation_count = _safe_operation_count(materials)
    payload: dict[str, Any] = {
        "shadow_only": True,
        "release_eligible": False,
        "status": status,
        "reason_code": _SHADOW_REASON_BY_STATUS[status],
        "operation_count": operation_count,
        "status_counts": {status: operation_count} if operation_count else {},
        "missing_field_counts": {
            field_name: missing_field_counts[field_name]
            for field_name in LX0609_025_REQUIRED_FIELDS
            if missing_field_counts[field_name]
        },
        "llm_calls": result.llm_call_count,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "elapsed_ms": max(0, elapsed_ms),
        "contract_version": LUXIAN_0609_025_SHADOW_CONTRACT_VERSION,
    }
    if operations:
        payload["operations"] = list(operations)
    return payload


async def run_luxian_0609_025_shadow(
    *,
    enabled: bool,
    selected_rule_ids: Sequence[str],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    llm_client: SurgeryGateLLMClient | None,
) -> dict[str, Any] | None:
    """运行025影子评估；所有前置条件不足时不触发任何模型调用。"""

    normalized_rule_ids = {
        str(rule_id or "").strip().upper() for rule_id in selected_rule_ids
    }
    coordinates = (institute_id, patient_id, visit_id)
    if (
        not enabled
        or _RULE_ID not in normalized_rule_ids
        or not all(isinstance(value, str) and value.strip() for value in coordinates)
        or type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        return None
    started = perf_counter()
    if reason_code := _surgery_record_preflight(
        snapshot=evidence_snapshot,
        materials=evidence_materials,
    ):
        return _safe_error(
            reason_code, elapsed_ms=round((perf_counter() - started) * 1000)
        )
    try:
        result = await execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=(_RULE_ID,),
            decision_rule_ids=(_RULE_ID,),
            wrapper_rules=(),
            evidence_payload=None,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=None,
            llm_client=llm_client,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
        )
    except Exception:
        return _safe_error(
            "evaluation_failed", elapsed_ms=round((perf_counter() - started) * 1000)
        )
    elapsed_ms = round((perf_counter() - started) * 1000)
    try:
        return _summary(
            result,
            snapshot=evidence_snapshot,
            materials=evidence_materials,
            elapsed_ms=elapsed_ms,
        )
    except (TypeError, ValueError):
        return _safe_error("result_contract_invalid", elapsed_ms=elapsed_ms)


__all__ = [
    "LUXIAN_0609_025_SHADOW_CONTRACT_VERSION",
    "run_luxian_0609_025_shadow",
]
