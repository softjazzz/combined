"""LX0609-04-02-08：死亡记录死亡时间完整性。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from ..decision_model import CriterionResult, CriterionStatus


_LABELED_TIME_PATTERNS = (
    re.compile(
        r"死亡时间\s*[:：]\s*"
        r"(?P<value>\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?"
        r"\s+\d{1,2}(?::\d{1,2}(?::\d{1,2})?|时\d{1,2}分(?:\d{1,2}秒)?))"
    ),
    re.compile(
        r"于\s*(?P<value>\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?"
        r"\s+\d{1,2}(?::\d{1,2}(?::\d{1,2})?|时\d{1,2}分(?:\d{1,2}秒)?))"
        r"\s*(?:宣告|宣布)?临床死亡"
    ),
)


@dataclass(frozen=True)
class Rule076Outcome:
    status: str
    reason_code: str
    document_refs: tuple[str, ...]
    criterion_results: tuple[CriterionResult, ...] = ()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_time(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("时", ":")
        .replace("分", ":")
        .replace("秒", "")
        .replace("/", "-")
        .replace(".", "-")
        .strip()
    )
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized.endswith(":"):
        normalized = normalized[:-1]
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _death_time(row: Mapping[str, Any]) -> datetime | None:
    for field in ("death_datetime", "death_time"):
        if parsed := _parse_time(row.get(field)):
            return parsed
    body = _clean(row.get("record_content") or row.get("content"))
    for pattern in _LABELED_TIME_PATTERNS:
        match = pattern.search(body)
        if match and (parsed := _parse_time(match.group("value"))):
            return parsed
    return None


def _criterion(
    *,
    status: CriterionStatus,
    reason_code: str,
    refs: Sequence[str],
    complete: bool | None,
) -> CriterionResult:
    return CriterionResult(
        criterion_id="death_time_complete",
        status=status,
        reason_code=reason_code,
        fact_refs=tuple(dict.fromkeys(refs)),
        actual_value=complete,
        expected_value=True,
        operator="complete",
        unit="boolean",
    )


def evaluate_rule_076(
    *,
    death_state: str,
    death_rows: Sequence[tuple[str, Mapping[str, Any]]],
    source_error: str = "",
) -> Rule076Outcome:
    """只核对死亡记录自身，不用文书完成时间替代死亡时间。"""

    refs = tuple(reference for reference, _row in death_rows)
    if source_error and (death_state == "unknown" or not death_rows):
        return Rule076Outcome("data_gap", source_error, refs)
    if death_state == "absent":
        return Rule076Outcome("not_applicable", "trigger_absent_complete", refs)
    if death_state == "conflict":
        return Rule076Outcome("data_gap", "authoritative_time_conflict", refs)
    if death_state != "present":
        return Rule076Outcome("data_gap", "applicability_source_gap", refs)
    if not death_rows:
        # 死亡病例无死亡记录由 060 报告；076 不制造重复问题。
        return Rule076Outcome("not_applicable", "eligibility_not_met", ())

    missing_refs = tuple(
        reference
        for reference, row in death_rows
        if _death_time(row) is None
        and _clean(row.get("record_content") or row.get("content"))
    )
    if missing_refs:
        return Rule076Outcome(
            "non_compliant",
            "defect_proven",
            missing_refs,
            (
                _criterion(
                    status=CriterionStatus.FAILED,
                    reason_code="required_field_missing",
                    refs=missing_refs,
                    complete=False,
                ),
            ),
        )
    unreadable_refs = tuple(
        reference
        for reference, row in death_rows
        if _death_time(row) is None
        and not _clean(row.get("record_content") or row.get("content"))
    )
    if unreadable_refs:
        # 只有元数据的文书不能证明医生漏填；其他文书的死亡时间也不能代填。
        return Rule076Outcome("data_gap", "source_empty", unreadable_refs)
    return Rule076Outcome(
        "compliant",
        "requirement_satisfied",
        refs,
        (
            _criterion(
                status=CriterionStatus.PASSED,
                reason_code="requirement_satisfied",
                refs=refs,
                complete=True,
            ),
        ),
    )
