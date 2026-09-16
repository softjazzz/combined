"""Luxian0916 的薄编排器：逐条调用、隔离失败、保持目录顺序。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .admission_rules import execute_admission_rules
from .contracts import Luxian0916RuleResult
from .course_event_rules import execute_course_event_rules
from .discharge_rules import execute_discharge_rules
from .first_course_rules import execute_first_course_rules
from .rule_catalog import LUXIAN_0916_RULE_CATALOG
from .surgery_consent_rules import execute_surgery_consent_rules


RuleExecutor = Callable[
    [Mapping[str, Any], Sequence[str] | None], list[Luxian0916RuleResult]
]


@dataclass(frozen=True)
class Luxian0916RuleFailure:
    """只用于任务诊断的技术失败，不进入客户规则结果。"""

    rule_id: str
    error_type: str

    def to_dict(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "error_type": self.error_type}


@dataclass(frozen=True)
class Luxian0916Execution:
    results: tuple[Luxian0916RuleResult, ...]
    failures: tuple[Luxian0916RuleFailure, ...] = ()

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts


_CATALOG_RULE_IDS = tuple(item.rule_id for item in LUXIAN_0916_RULE_CATALOG)
_FAMILY_EXECUTORS: tuple[tuple[frozenset[str], RuleExecutor], ...] = (
    (frozenset(f"LX0916-{number:03d}" for number in range(1, 10)), execute_admission_rules),
    (frozenset(f"LX0916-{number:03d}" for number in range(10, 15)), execute_first_course_rules),
    (frozenset(f"LX0916-{number:03d}" for number in range(15, 21)), execute_course_event_rules),
    (frozenset(f"LX0916-{number:03d}" for number in range(21, 31)), execute_surgery_consent_rules),
    (frozenset(f"LX0916-{number:03d}" for number in range(31, 33)), execute_discharge_rules),
)


def execute_luxian_0916(
    context: Mapping[str, Any],
    rule_ids: Sequence[str] | None = None,
) -> Luxian0916Execution:
    """执行所选规则；业务状态完全由规则执行器形成，编排器不做二次解释。"""

    if not isinstance(context, Mapping):
        raise TypeError("context must be a mapping")
    requested = _normalize_rule_ids(rule_ids)
    results: list[Luxian0916RuleResult] = []
    failures: list[Luxian0916RuleFailure] = []
    for rule_id in requested:
        executor = _executor_for(rule_id)
        try:
            family_results = executor(context, (rule_id,))
            if len(family_results) != 1 or family_results[0].rule_id != rule_id:
                raise RuntimeError("rule executor returned an invalid result contract")
            result = family_results[0]
            if not isinstance(result, Luxian0916RuleResult):
                raise TypeError("rule executor must return Luxian0916RuleResult")
            results.append(result)
        except Exception as exc:  # noqa: BLE001 - 每条规则必须独立失败
            failures.append(
                Luxian0916RuleFailure(rule_id=rule_id, error_type=type(exc).__name__)
            )
    return Luxian0916Execution(results=tuple(results), failures=tuple(failures))


def _normalize_rule_ids(rule_ids: Sequence[str] | None) -> tuple[str, ...]:
    if rule_ids is None:
        return _CATALOG_RULE_IDS
    requested = tuple(str(rule_id or "").strip().upper() for rule_id in rule_ids)
    if not requested or any(not rule_id for rule_id in requested):
        raise ValueError("rule_ids cannot be empty")
    if len(set(requested)) != len(requested):
        raise ValueError("rule_ids cannot contain duplicates")
    unknown = set(requested).difference(_CATALOG_RULE_IDS)
    if unknown:
        raise ValueError(f"unknown Luxian0916 rule_ids: {sorted(unknown)}")
    requested_set = set(requested)
    return tuple(rule_id for rule_id in _CATALOG_RULE_IDS if rule_id in requested_set)


def _executor_for(rule_id: str) -> RuleExecutor:
    for family_rule_ids, executor in _FAMILY_EXECUTORS:
        if rule_id in family_rule_ids:
            return executor
    raise ValueError(f"no Luxian0916 executor registered for {rule_id}")


__all__ = [
    "Luxian0916Execution",
    "Luxian0916RuleFailure",
    "execute_luxian_0916",
]
