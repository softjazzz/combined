"""程序化 finding 的唯一最终状态聚合纯 shadow 契约。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any

from . import programmatic_rules as rules_module

_SHA = re.compile(r"^[a-f0-9]{64}$")
_RULES = ("LX0609-029", "LX0609-030", "LX0609-032")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SENSITIVE = re.compile(r"(?i)(full[_ -]?text|medical[_ -]?text|raw[_ -]?(text|response|output)|record[_ -]?content|internal[_ -]?data|source[_ -]?document|patient[_ -]?name|id[_ -]?card|phone|mobile|address|quote|value|(record|submit|update)[_ -]?time|trace|prompt|response|error[_ -]?stack|sql|authorization|bearer|api[_ -]?key|password|private[_ -]?key|(?:^|[_-])sk[_-])")
_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_MAP = {
    rules_module.FindingKind.REQUIREMENT_SATISFIED: "compliant",
    rules_module.FindingKind.REQUIRED_DOCUMENT_MISSING: "non_compliant",
    rules_module.FindingKind.TRIGGER_ABSENT: "not_applicable",
    rules_module.FindingKind.SOURCE_INCOMPLETE: "data_gap",
    rules_module.FindingKind.TECHNICAL_FAILURE: "technical_error",
    rules_module.FindingKind.EVIDENCE_CONFLICT: "evaluation_unknown",
}


class FinalState(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    DATA_GAP = "data_gap"
    TECHNICAL_ERROR = "technical_error"
    EVALUATION_UNKNOWN = "evaluation_unknown"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _code(name: str, value: Any, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum or not _CODE.fullmatch(value) or _SENSITIVE.search(value) or _ID_CARD.search(value) or _PHONE.search(value):
        raise ValueError(f"invalid {name}")
    return value


def _coerce_kind(value: rules_module.FindingKind | str) -> rules_module.FindingKind:
    if isinstance(value, rules_module.FindingKind): return value
    if isinstance(value, str):
        try: return rules_module.FindingKind(value)
        except ValueError: pass
    raise ValueError("invalid finding_kind")


def _coerce_final_state(value: FinalState | str) -> FinalState:
    if isinstance(value, FinalState): return value
    if isinstance(value, str):
        try: return FinalState(value)
        except ValueError: pass
    raise ValueError("invalid final_state")


def _created(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid created_at")
    try: datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: raise ValueError("invalid created_at") from None
    return value


@dataclass(frozen=True)
class AggregatedRuleResult:
    rule_id: str
    finding_kind: rules_module.FindingKind | str
    final_state: FinalState | str

    def __post_init__(self) -> None:
        rule = _code("rule_id", self.rule_id)
        if rule not in _RULES: raise ValueError("invalid rule_id")
        kind = _coerce_kind(self.finding_kind)
        state = _coerce_final_state(self.final_state)
        if state.value != _MAP[kind]: raise ValueError("final state mapping mismatch")
        object.__setattr__(self, "rule_id", rule); object.__setattr__(self, "finding_kind", kind); object.__setattr__(self, "final_state", state)

    def to_dict(self) -> dict[str, str]: return {"rule_id": self.rule_id, "finding_kind": self.finding_kind.value, "final_state": self.final_state.value}


@dataclass(frozen=True)
class AggregationReport:
    aggregation_schema_version: str
    aggregation_policy_version: str
    visit_ref: str
    finding_fingerprint: str
    results: tuple[AggregatedRuleResult, ...]
    created_at: str

    def __post_init__(self) -> None:
        if type(self.results) is not tuple or len(self.results) > 3 or not all(isinstance(item, AggregatedRuleResult) for item in self.results): raise ValueError("invalid aggregated results")
        order = tuple(item.rule_id for item in self.results)
        if len(order) != len(set(order)) or order != tuple(rule for rule in _RULES if rule in order): raise ValueError("invalid aggregated result order")
        object.__setattr__(self, "aggregation_schema_version", _code("aggregation_schema_version", self.aggregation_schema_version, 64))
        object.__setattr__(self, "aggregation_policy_version", _code("aggregation_policy_version", self.aggregation_policy_version, 64))
        object.__setattr__(self, "visit_ref", _code("visit_ref", self.visit_ref))
        object.__setattr__(self, "finding_fingerprint", _sha("finding_fingerprint", self.finding_fingerprint)); object.__setattr__(self, "created_at", _created(self.created_at))

    def summary_dict(self) -> dict[str, Any]:
        counts = {state.value: 0 for state in FinalState}
        for result in self.results: counts[result.final_state.value] += 1
        return {**{f"{name}_count": value for name, value in counts.items()}, "expected_llm_call_count": 0, "shadow_only": True, "release_eligible": False}

    def to_dict(self) -> dict[str, Any]: return {"aggregation_schema_version": self.aggregation_schema_version, "aggregation_policy_version": self.aggregation_policy_version, "visit_ref": self.visit_ref, "finding_fingerprint": self.finding_fingerprint, "results": [item.to_dict() for item in self.results], "summary": self.summary_dict(), "created_at": self.created_at}
    def canonical_json(self) -> str: return _json(self.to_dict())
    def fingerprint(self) -> str:
        value = self.to_dict(); value.pop("created_at"); return hashlib.sha256(_json(value).encode()).hexdigest()


def aggregate_luxian_0609_programmatic_findings_shadow(*, finding_report: Any, aggregation_schema_version: str, aggregation_policy_version: str, created_at: str) -> AggregationReport:
    if not isinstance(finding_report, rules_module.ProgrammaticFindingReport): raise TypeError("finding_report must be accepted ProgrammaticFindingReport")
    results = tuple(AggregatedRuleResult(item.rule_id, item.finding_kind, _MAP[item.finding_kind]) for item in finding_report.findings)
    return AggregationReport(aggregation_schema_version, aggregation_policy_version, finding_report.visit_ref, finding_report.fingerprint(), results, created_at)
