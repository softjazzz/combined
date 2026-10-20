"""LX0609 规则族执行结果的 exactly-once 契约。"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
from typing import Any, Mapping

from .decision_model import RuleDecision
from .native_execution import build_luxian_0609_native_result


_RULE_ID_PATTERN = re.compile(r"^LX0609-\d{2}-\d{2}-\d{2}$")
_EXECUTOR_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_MODEL_EXECUTION_STATS_KEYS = (
    "requested_rule_count",
    "first_success_rule_count",
    "retried_rule_count",
    "recovered_rule_count",
    "failed_rule_count",
    "first_answer_success_rate",
    "recovery_success_rate",
    "model_failure_rate",
)
_MODEL_EXECUTION_STATS_KEY_SET = frozenset(_MODEL_EXECUTION_STATS_KEYS)
_MODEL_EXECUTION_STATS_COUNT_KEYS = frozenset(
    {
        "requested_rule_count",
        "first_success_rule_count",
        "retried_rule_count",
        "recovered_rule_count",
        "failed_rule_count",
    }
)
_MODEL_EXECUTION_STATS_RATE_FIELDS = {
    "first_answer_success_rate": (
        "first_success_rule_count",
        "requested_rule_count",
    ),
    "recovery_success_rate": (
        "recovered_rule_count",
        "retried_rule_count",
    ),
    "model_failure_rate": (
        "failed_rule_count",
        "requested_rule_count",
    ),
}


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_rate(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _normalize_model_execution_stats(
    value: Mapping[str, int | float | None] | None,
) -> dict[str, int | float | None] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("model execution stats must be a mapping")
    if not value:
        return None
    if set(value) != _MODEL_EXECUTION_STATS_KEY_SET:
        raise ValueError("invalid model execution stats")

    stats = {key: value[key] for key in _MODEL_EXECUTION_STATS_KEYS}
    if any(
        not _is_non_negative_int(stats[key])
        for key in _MODEL_EXECUTION_STATS_COUNT_KEYS
    ):
        raise ValueError("invalid model execution stats")
    requested = stats["requested_rule_count"]
    first_success = stats["first_success_rule_count"]
    retried = stats["retried_rule_count"]
    recovered = stats["recovered_rule_count"]
    failed = stats["failed_rule_count"]
    if (
        first_success + retried > requested
        or recovered > retried
        or first_success + recovered + failed != requested
    ):
        raise ValueError("invalid model execution stats")

    # retried 仅统计实际进入恢复的首答失败规则；模型调用异常可能没有重试，
    # 因此 first_success + retried 不要求恰好等于 requested。
    for rate_key, (numerator_key, denominator_key) in _MODEL_EXECUTION_STATS_RATE_FIELDS.items():
        rate = stats[rate_key]
        denominator = stats[denominator_key]
        if denominator == 0:
            if rate is not None:
                raise ValueError("invalid model execution stats")
        elif (
            not _is_rate(rate)
            or not math.isclose(
                float(rate),
                stats[numerator_key] / denominator,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("invalid model execution stats")
    return stats


@dataclass(frozen=True)
class FamilyUsageAttribution:
    """单病例内一个规则族的安全模型成本归因。"""

    executor_key: str
    llm_call_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    covered_customer_rule_ids: tuple[str, ...]
    latency_ms: float
    model_execution_stats: Mapping[str, int | float | None] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.executor_key, str)
            or not _EXECUTOR_KEY_PATTERN.fullmatch(self.executor_key)
        ):
            raise ValueError("invalid executor_key")
        rule_ids = self.covered_customer_rule_ids
        if (
            type(rule_ids) is not tuple
            or not rule_ids
            or len(rule_ids) != len(set(rule_ids))
            or any(
                not isinstance(rule_id, str)
                or not _RULE_ID_PATTERN.fullmatch(rule_id)
                for rule_id in rule_ids
            )
        ):
            raise ValueError("invalid covered_customer_rule_ids")
        metrics = (
            self.llm_call_count,
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )
        if not all(_is_non_negative_int(value) for value in metrics):
            raise ValueError("invalid token metrics")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("invalid token arithmetic")
        if self.llm_call_count == 0 and self.total_tokens != 0:
            raise ValueError("zero-call usage must have zero tokens")
        # 部分供应商会返回成功调用与耗时，但不返回 token usage。
        # 此时 0 表示“未提供”，不能把已完成的规则族误判为契约失败。
        if (
            isinstance(self.latency_ms, bool)
            or not isinstance(self.latency_ms, (int, float))
            or not math.isfinite(self.latency_ms)
            or self.latency_ms < 0
        ):
            raise ValueError("invalid latency_ms")
        object.__setattr__(
            self,
            "model_execution_stats",
            _normalize_model_execution_stats(self.model_execution_stats),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        safe = {
            "executor_key": self.executor_key,
            "llm_call_count": self.llm_call_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "covered_customer_rule_ids": list(self.covered_customer_rule_ids),
            "latency_ms": round(float(self.latency_ms), 3),
        }
        if self.model_execution_stats is not None:
            safe["model_execution_stats"] = {
                key: self.model_execution_stats[key]
                for key in _MODEL_EXECUTION_STATS_KEYS
            }
        return safe


def build_family_usage_attribution(
    *,
    executor_key: str,
    covered_customer_rule_ids: tuple[str, ...],
    llm_call_count: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    api_time: float,
    model_execution_stats: Mapping[str, int | float | None] | None = None,
) -> FamilyUsageAttribution:
    if (
        isinstance(api_time, bool)
        or not isinstance(api_time, (int, float))
        or not math.isfinite(api_time)
        or api_time < 0
    ):
        raise ValueError("invalid api_time")
    return FamilyUsageAttribution(
        executor_key=executor_key,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        covered_customer_rule_ids=covered_customer_rule_ids,
        latency_ms=float(api_time) * 1000.0,
        model_execution_stats=model_execution_stats,
    )


@dataclass(frozen=True)
class FamilyExecutionEnvelope:
    results: tuple[Any, ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    diagnostic_semantic_snapshot: Mapping[str, Any] | None = None
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    usage_attribution: FamilyUsageAttribution | None = None
    usage_observation_complete: bool = True

    def __post_init__(self) -> None:
        if type(self.usage_observation_complete) is not bool:
            raise TypeError("usage_observation_complete must be bool")
        if (
            type(self.results) is not tuple
            or type(self.decisions) is not tuple
            or type(self.planned_rule_ids) is not tuple
            or not self.planned_rule_ids
            or len(self.planned_rule_ids) != len(set(self.planned_rule_ids))
            or any(
                not isinstance(rule_id, str)
                or not _RULE_ID_PATTERN.fullmatch(rule_id)
                for rule_id in self.planned_rule_ids
            )
        ):
            raise ValueError("invalid planned_rule_ids")
        if any(type(item) is not RuleDecision for item in self.decisions):
            raise TypeError("decisions must contain RuleDecision values")
        display_rule_ids: list[str] = []
        for item in self.customer_display_facts:
            if (
                type(item) is not tuple
                or len(item) != 2
                or not isinstance(item[0], str)
                or not _RULE_ID_PATTERN.fullmatch(item[0])
                or not isinstance(item[1], Mapping)
            ):
                raise TypeError("invalid customer_display_facts")
            display_rule_ids.append(item[0])
        if (
            len(display_rule_ids) != len(set(display_rule_ids))
            or any(rule_id not in self.planned_rule_ids for rule_id in display_rule_ids)
        ):
            raise ValueError("customer display facts outside planned scope")
        if self.diagnostic_semantic_snapshot is not None and not isinstance(
            self.diagnostic_semantic_snapshot, Mapping
        ):
            raise TypeError("diagnostic_semantic_snapshot must be a mapping")
        metrics = (
            self.llm_call_count,
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )
        if not all(_is_non_negative_int(value) for value in metrics):
            raise ValueError("invalid token metrics")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("invalid token arithmetic")
        if self.llm_call_count == 0 and self.total_tokens != 0:
            raise ValueError("zero-call envelope must have zero tokens")
        # 部分供应商会返回成功调用与耗时，但不返回 token usage。
        # 保留调用次数，token 以 0 表示供应商未提供。
        if (
            isinstance(self.api_time, bool)
            or not isinstance(self.api_time, (int, float))
            or not math.isfinite(self.api_time)
            or self.api_time < 0
        ):
            raise ValueError("invalid api_time")
        if self.usage_attribution is not None:
            usage = self.usage_attribution
            if not isinstance(usage, FamilyUsageAttribution):
                raise TypeError("usage_attribution must be FamilyUsageAttribution")
            if (
                usage.covered_customer_rule_ids != self.planned_rule_ids
                or usage.llm_call_count != self.llm_call_count
                or usage.prompt_tokens != self.prompt_tokens
                or usage.completion_tokens != self.completion_tokens
                or usage.total_tokens != self.total_tokens
                or not math.isclose(
                    usage.latency_ms,
                    float(self.api_time) * 1000.0,
                    rel_tol=0.0,
                    abs_tol=0.001,
                )
            ):
                raise ValueError("usage attribution does not match envelope")


@dataclass(frozen=True)
class FamilyExecutionValidation:
    valid: bool
    reason_code: str
    envelope: FamilyExecutionEnvelope
    # 逐点修复后仍有效的信封中，被单独改判技术错误的规则。
    repaired_rule_ids: tuple[str, ...] = ()


def build_family_technical_envelope(
    *,
    expected_rule_ids: tuple[str, ...],
    reason_code: str,
    source_envelope: FamilyExecutionEnvelope | None = None,
) -> FamilyExecutionEnvelope:
    source_usage = source_envelope.usage_attribution if source_envelope else None
    usage_attribution = (
        build_family_usage_attribution(
            executor_key=source_usage.executor_key,
            covered_customer_rule_ids=expected_rule_ids,
            llm_call_count=source_envelope.llm_call_count,
            prompt_tokens=source_envelope.prompt_tokens,
            completion_tokens=source_envelope.completion_tokens,
            total_tokens=source_envelope.total_tokens,
            api_time=source_envelope.api_time,
            model_execution_stats=source_usage.model_execution_stats,
        )
        if source_envelope is not None and source_usage is not None
        else None
    )
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
        usage_attribution=usage_attribution,
        usage_observation_complete=(
            source_envelope.usage_observation_complete if source_envelope else True
        ),
    )


def validate_family_execution_envelope(
    *,
    envelope: FamilyExecutionEnvelope,
    expected_rule_ids: tuple[str, ...],
) -> FamilyExecutionValidation:
    if not isinstance(envelope, FamilyExecutionEnvelope):
        raise TypeError("envelope must be FamilyExecutionEnvelope")
    if (
        type(expected_rule_ids) is not tuple
        or not expected_rule_ids
        or len(expected_rule_ids) != len(set(expected_rule_ids))
        or any(
            not isinstance(rule_id, str) or not _RULE_ID_PATTERN.fullmatch(rule_id)
            for rule_id in expected_rule_ids
        )
    ):
        raise ValueError("invalid expected_rule_ids")

    if envelope.planned_rule_ids != expected_rule_ids:
        # 执行器声明的范围与调度范围不一致属于整族结构错误，不能逐点修补。
        return FamilyExecutionValidation(
            False,
            "family_result_scope_mismatch",
            build_family_technical_envelope(
                expected_rule_ids=expected_rule_ids,
                reason_code="family_result_scope_mismatch",
                source_envelope=envelope,
            ),
        )

    results_by_rule: dict[str, list[Any]] = {}
    unattributable_result_count = 0
    for result in envelope.results:
        rule_id = result.get("rule_id") if isinstance(result, Mapping) else None
        if not isinstance(rule_id, str) or not rule_id.strip():
            unattributable_result_count += 1
            continue
        results_by_rule.setdefault(rule_id, []).append(result)
    decisions_by_rule: dict[str, list[RuleDecision]] = {}
    for decision in envelope.decisions:
        decisions_by_rule.setdefault(decision.rule_id, []).append(decision)

    expected_rule_id_set = set(expected_rule_ids)
    extra_rule_ids = {
        rule_id
        for rule_id in (*results_by_rule, *decisions_by_rule)
        if rule_id not in expected_rule_id_set
    }
    repaired_reasons: dict[str, str] = {}
    for rule_id in expected_rule_ids:
        delivered_count = len(results_by_rule.get(rule_id, ())) + len(
            decisions_by_rule.get(rule_id, ())
        )
        if delivered_count > 1:
            repaired_reasons[rule_id] = "family_result_duplicate"
        elif delivered_count == 0:
            repaired_reasons[rule_id] = (
                "family_result_invalid"
                if unattributable_result_count
                else "family_result_missing"
            )

    if len(repaired_reasons) == len(expected_rule_ids):
        # 没有任何可保留的结果时仍按整族合同失败处理，保持既有失败统计与用量语义。
        reason_code = next(iter(repaired_reasons.values()))
        return FamilyExecutionValidation(
            False,
            reason_code,
            build_family_technical_envelope(
                expected_rule_ids=expected_rule_ids,
                reason_code=reason_code,
                source_envelope=envelope,
            ),
        )

    kept_results = tuple(
        results_by_rule[rule_id][0]
        for rule_id in expected_rule_ids
        if rule_id not in repaired_reasons and rule_id in results_by_rule
    )
    kept_decisions = tuple(
        decisions_by_rule[rule_id][0]
        for rule_id in expected_rule_ids
        if rule_id not in repaired_reasons and rule_id in decisions_by_rule
    )
    if (
        not repaired_reasons
        and not extra_rule_ids
        and not unattributable_result_count
        and kept_results == envelope.results
        and kept_decisions == envelope.decisions
    ):
        return FamilyExecutionValidation(True, "", envelope)

    # 只把缺失、重复的规则改判技术错误；多余或无法归属的条目丢弃，顺序按调度
    # 范围重排。其余规则已形成的结果与展示事实原样保留，不因同族一个点连坐。
    technical_results = {
        rule_id: build_luxian_0609_native_result(
            rule_id=rule_id,
            final_state="technical_error",
            finding_kind="technical_failure",
            reason_code=reason,
        )
        for rule_id, reason in repaired_reasons.items()
    }
    kept_result_by_rule = {str(item["rule_id"]): item for item in kept_results}
    repaired_results = tuple(
        kept_result_by_rule.get(rule_id) or technical_results[rule_id]
        for rule_id in expected_rule_ids
        if rule_id in kept_result_by_rule or rule_id in technical_results
    )
    repaired_display_facts = tuple(
        item
        for item in envelope.customer_display_facts
        if item[0] in expected_rule_id_set and item[0] not in repaired_reasons
    )
    reason_code = (
        next(iter(repaired_reasons.values()))
        if repaired_reasons
        else "family_result_extra"
        if extra_rule_ids
        else "family_result_invalid"
        if unattributable_result_count
        else "family_result_order_mismatch"
    )
    return FamilyExecutionValidation(
        True,
        reason_code,
        replace(
            envelope,
            results=repaired_results,
            decisions=kept_decisions,
            customer_display_facts=repaired_display_facts,
        ),
        repaired_rule_ids=tuple(
            rule_id for rule_id in expected_rule_ids if rule_id in repaired_reasons
        ),
    )
