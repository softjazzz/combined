"""LX0609 规则族执行结果的 exactly-once 契约。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .native_execution import build_luxian_0609_native_result


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


@dataclass(frozen=True)
class FamilyExecutionEnvelope:
    results: tuple[Any, ...]
    planned_rule_ids: tuple[str, ...]
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.results, tuple)
            or not isinstance(self.planned_rule_ids, tuple)
            or not self.planned_rule_ids
            or len(self.planned_rule_ids) != len(set(self.planned_rule_ids))
            or any(
                not isinstance(rule_id, str)
                or not rule_id.startswith("LX0609-")
                for rule_id in self.planned_rule_ids
            )
        ):
            raise ValueError("invalid planned_rule_ids")
        metrics = (
            self.llm_call_count,
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )
        if not all(_is_non_negative_int(value) for value in metrics):
            raise ValueError("invalid token metrics")
        if (
            isinstance(self.api_time, bool)
            or not isinstance(self.api_time, (int, float))
            or not math.isfinite(self.api_time)
            or self.api_time < 0
        ):
            raise ValueError("invalid api_time")


@dataclass(frozen=True)
class FamilyExecutionValidation:
    valid: bool
    reason_code: str
    envelope: FamilyExecutionEnvelope


def build_family_technical_envelope(
    *,
    expected_rule_ids: tuple[str, ...],
    reason_code: str,
    source_envelope: FamilyExecutionEnvelope | None = None,
) -> FamilyExecutionEnvelope:
    technical_results = tuple(
        build_luxian_0609_native_result(
            rule_id=rule_id,
            final_state="technical_error",
            finding_kind="technical_failure",
            reason_code=reason_code,
        )
        for rule_id in expected_rule_ids
    )
    return FamilyExecutionEnvelope(
        results=technical_results,
        planned_rule_ids=expected_rule_ids,
        llm_call_count=(source_envelope.llm_call_count if source_envelope else 0),
        prompt_tokens=(source_envelope.prompt_tokens if source_envelope else 0),
        completion_tokens=(source_envelope.completion_tokens if source_envelope else 0),
        total_tokens=(source_envelope.total_tokens if source_envelope else 0),
        api_time=(source_envelope.api_time if source_envelope else 0.0),
    )


def validate_family_execution_envelope(
    *,
    envelope: FamilyExecutionEnvelope,
    expected_rule_ids: tuple[str, ...],
) -> FamilyExecutionValidation:
    if not isinstance(envelope, FamilyExecutionEnvelope):
        raise TypeError("envelope must be FamilyExecutionEnvelope")
    if (
        not isinstance(expected_rule_ids, tuple)
        or not expected_rule_ids
        or len(expected_rule_ids) != len(set(expected_rule_ids))
        or any(
            not isinstance(rule_id, str) or not rule_id.startswith("LX0609-")
            for rule_id in expected_rule_ids
        )
    ):
        raise ValueError("invalid expected_rule_ids")

    actual_rule_ids: list[str] = []
    reason_code = ""
    for result in envelope.results:
        if not isinstance(result, Mapping):
            reason_code = "family_result_invalid"
            break
        rule_id = result.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            reason_code = "family_result_invalid"
            break
        actual_rule_ids.append(rule_id)

    if not reason_code:
        actual = tuple(actual_rule_ids)
        if len(actual) != len(set(actual)):
            reason_code = "family_result_duplicate"
        elif any(rule_id not in expected_rule_ids for rule_id in actual):
            reason_code = "family_result_extra"
        elif any(rule_id not in actual for rule_id in expected_rule_ids):
            reason_code = "family_result_missing"
        elif actual != expected_rule_ids:
            reason_code = "family_result_order_mismatch"
        elif envelope.planned_rule_ids != expected_rule_ids:
            reason_code = "family_result_scope_mismatch"

    if not reason_code:
        return FamilyExecutionValidation(True, "", envelope)
    return FamilyExecutionValidation(
        False,
        reason_code,
        build_family_technical_envelope(
            expected_rule_ids=expected_rule_ids,
            reason_code=reason_code,
            source_envelope=envelope,
        ),
    )
