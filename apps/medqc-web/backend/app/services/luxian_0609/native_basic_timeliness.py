"""LX0609 基础时限族的原生确定性执行器。"""

from __future__ import annotations

import re
from typing import Any, Sequence

from .native_execution import NativeExecutionResult, build_luxian_0609_native_result
from ..luxian_0609_rule_catalog import load_luxian_0609_rules
from ..luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules


BASIC_TIMELINESS_RULE_IDS = (
    "LX0609-001",
    "LX0609-002",
    "LX0609-004",
    "LX0609-005",
    "LX0609-006",
)
EXECUTOR_KEY = "basic_timeliness"
_FIRST_COURSE_RULE_ID = "LX0609-002"
_FIRST_COURSE_BODY_FIELDS = (
    "record_content",
    "content",
    "assembled_text",
    "raw_text",
)
_MIN_FIRST_COURSE_BODY_CHARS = 6


def _technical_result(rule_id: str, reason_code: str) -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state="technical_error",
        finding_kind="technical_failure",
        reason_code=reason_code,
    )


def _has_substantive_first_course_body(
    evidence_payload: dict[str, Any] | None,
) -> bool:
    if not isinstance(evidence_payload, dict):
        return False
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, dict):
        return False
    documents = timeline.get("documents")
    if not isinstance(documents, dict):
        return False
    rows = documents.get("first_course_record")
    if not isinstance(rows, (list, tuple)):
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in _FIRST_COURSE_BODY_FIELDS:
            value = row.get(field)
            if not isinstance(value, str):
                continue
            normalized = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
            shell_remainder = re.sub(
                r"(?:首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|"
                r"sourcetable|firstcourserecord|assemblystatus|partial|"
                r"年|月|日|时|分|秒|\d+)",
                "",
                normalized,
                flags=re.IGNORECASE,
            )
            if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS:
                return True
    return False


def _first_course_data_gap_result() -> dict[str, Any]:
    return build_luxian_0609_native_result(
        rule_id=_FIRST_COURSE_RULE_ID,
        final_state="data_gap",
        finding_kind="source_data_gap",
        reason_code="first_course_substantive_content_unavailable",
    )


def execute_luxian_0609_native_basic_timeliness(
    *,
    rule_ids: Sequence[str],
    evidence_payload: dict[str, Any] | None,
) -> NativeExecutionResult:
    """一次执行所选基础时限点；不调用模型、不展开旧映射 ID。"""

    requested = {
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    }
    selected = tuple(
        rule_id for rule_id in BASIC_TIMELINESS_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeExecutionResult((), ())

    try:
        first_course_data_gap = (
            _FIRST_COURSE_RULE_ID in selected
            and not _has_substantive_first_course_body(evidence_payload)
        )
        selected_set = set(selected)
        evaluated_rule_ids = selected_set - (
            {_FIRST_COURSE_RULE_ID} if first_course_data_gap else set()
        )
        wrappers = [
            rule
            for rule in load_luxian_0609_rules()
            if str(rule.get("rule_id") or "").strip().upper() in evaluated_rule_ids
        ]
        evaluated = evaluate_luxian_0609_programmatic_rules(
            wrapper_rules=wrappers,
            evidence_payload=evidence_payload,
        )
        by_rule_id = {
            str(item.get("rule_id") or "").strip().upper(): item
            for item in evaluated
            if isinstance(item, dict)
        }
    except Exception:
        return NativeExecutionResult(
            results=tuple(
                _technical_result(rule_id, "native_basic_execution_failure")
                for rule_id in selected
            ),
            planned_rule_ids=selected,
            terminal_reason_code="native_basic_execution_failure",
        )

    results: list[dict[str, Any]] = []
    for rule_id in selected:
        if rule_id == _FIRST_COURSE_RULE_ID and first_course_data_gap:
            results.append(_first_course_data_gap_result())
            continue
        raw = by_rule_id.get(rule_id)
        if raw is None:
            results.append(_technical_result(rule_id, "native_basic_result_incomplete"))
            continue
        item = dict(raw)
        metadata = dict(item.get("metadata") or {})
        metadata.update(
            {
                "execution_source": "lx0609_native",
                "executor_type": "program",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        )
        item["metadata"] = metadata
        results.append(item)

    return NativeExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
    )
