"""029/030/032 的程序化 finding 纯 shadow 契约。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any

from . import deterministic_gate as gate_module

MAX_FINDINGS = 3
_SHA = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_RULES = ("LX0609-029", "LX0609-030", "LX0609-032")
_SENSITIVE = re.compile(r"(?i)(full[_ -]?text|medical[_ -]?text|raw[_ -]?(text|response|output)|record[_ -]?content|source[_ -]?document|patient[_ -]?name|id[_ -]?card|phone|mobile|address|quote|value|(record|submit|update)[_ -]?time|trace|prompt|response|error[_ -]?stack|sql|authorization|bearer|api[_ -]?key|password|private[_ -]?key|(?:^|[_-])sk[_-])")


class FindingKind(str, Enum):
    REQUIREMENT_SATISFIED = "requirement_satisfied"
    REQUIRED_DOCUMENT_MISSING = "required_document_missing"
    TRIGGER_ABSENT = "trigger_absent"
    EVIDENCE_CONFLICT = "evidence_conflict"
    SOURCE_INCOMPLETE = "source_incomplete"
    TECHNICAL_FAILURE = "technical_failure"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _code(name: str, value: Any, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum or not _CODE.fullmatch(value) or _SENSITIVE.search(value):
        raise ValueError(f"invalid {name}")
    return value


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _created(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("invalid created_at")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid created_at") from None
    return value


def _kind_for(decision: gate_module.GateDecision) -> FindingKind:
    trigger = decision.trigger_resolution
    target = decision.target_resolution
    if trigger is gate_module.TriggerResolution.MATCHED:
        if target is gate_module.TargetResolution.PRESENT:
            return FindingKind.REQUIREMENT_SATISFIED
        if target is gate_module.TargetResolution.EMPTY:
            return FindingKind.REQUIRED_DOCUMENT_MISSING
        if target is gate_module.TargetResolution.UNAVAILABLE:
            return FindingKind.SOURCE_INCOMPLETE
        if target is gate_module.TargetResolution.ERROR:
            return FindingKind.TECHNICAL_FAILURE
    if trigger is gate_module.TriggerResolution.ABSENT_COMPLETE:
        return FindingKind.TRIGGER_ABSENT
    if trigger is gate_module.TriggerResolution.SEMANTIC_CONFLICT:
        return FindingKind.EVIDENCE_CONFLICT
    if trigger in (gate_module.TriggerResolution.SOURCE_UNAVAILABLE, gate_module.TriggerResolution.COVERAGE_PARTIAL, gate_module.TriggerResolution.COVERAGE_NOT_RUN):
        return FindingKind.SOURCE_INCOMPLETE
    if trigger in (gate_module.TriggerResolution.SOURCE_ERROR, gate_module.TriggerResolution.COVERAGE_ERROR):
        return FindingKind.TECHNICAL_FAILURE
    raise ValueError("invalid gate decision mapping")


@dataclass(frozen=True)
class ProgrammaticFinding:
    rule_id: str
    finding_kind: FindingKind | str
    target_source_key: str
    parent_rule_ids: tuple[str, ...]
    dependency_reason_codes: tuple[str, ...]
    matched_fact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(type(item) is not tuple for item in (self.parent_rule_ids, self.dependency_reason_codes, self.matched_fact_ids)):
            raise TypeError("finding collections must be tuple")
        rule = _code("rule_id", self.rule_id)
        if rule not in _RULES:
            raise ValueError("unsupported rule_id")
        kind = FindingKind(self.finding_kind)
        parent = tuple(_code("parent_rule_id", item) for item in self.parent_rule_ids)
        dependency = tuple(_code("dependency_reason_code", item) for item in self.dependency_reason_codes)
        facts = tuple(sorted(_sha("matched_fact_id", item) for item in self.matched_fact_ids))
        if len(facts) != len(set(facts)):
            raise ValueError("duplicate matched_fact_id")
        if kind in (FindingKind.TRIGGER_ABSENT, FindingKind.EVIDENCE_CONFLICT) and facts:
            raise ValueError("finding kind cannot carry matched facts")
        if rule == "LX0609-032":
            if parent != ("LX0609-030",) or dependency != ("informational_parent_only",):
                raise ValueError("032 dependency metadata mismatch")
        elif parent or dependency:
            raise ValueError("unexpected dependency metadata")
        object.__setattr__(self, "rule_id", rule)
        object.__setattr__(self, "finding_kind", kind)
        object.__setattr__(self, "target_source_key", _code("target_source_key", self.target_source_key))
        object.__setattr__(self, "parent_rule_ids", parent)
        object.__setattr__(self, "dependency_reason_codes", dependency)
        object.__setattr__(self, "matched_fact_ids", facts)

    def to_dict(self) -> dict[str, Any]:
        return {"dependency_reason_codes": list(self.dependency_reason_codes), "finding_kind": self.finding_kind.value, "matched_fact_ids": list(self.matched_fact_ids), "parent_rule_ids": list(self.parent_rule_ids), "rule_id": self.rule_id, "target_source_key": self.target_source_key}


@dataclass(frozen=True)
class ProgrammaticFindingReport:
    finding_schema_version: str
    finding_policy_version: str
    visit_ref: str
    gate_fingerprint: str
    findings: tuple[ProgrammaticFinding, ...]
    created_at: str

    def __post_init__(self) -> None:
        if type(self.findings) is not tuple or len(self.findings) > MAX_FINDINGS or not all(isinstance(item, ProgrammaticFinding) for item in self.findings):
            raise ValueError("invalid findings")
        expected = tuple(rule for rule in _RULES if rule in tuple(item.rule_id for item in self.findings))
        if tuple(item.rule_id for item in self.findings) != expected:
            raise ValueError("findings do not match supported rule order")
        object.__setattr__(self, "finding_schema_version", _code("finding_schema_version", self.finding_schema_version, 64))
        object.__setattr__(self, "finding_policy_version", _code("finding_policy_version", self.finding_policy_version, 64))
        object.__setattr__(self, "visit_ref", _code("visit_ref", self.visit_ref))
        object.__setattr__(self, "gate_fingerprint", _sha("gate_fingerprint", self.gate_fingerprint))
        object.__setattr__(self, "created_at", _created(self.created_at))

    def summary_dict(self) -> dict[str, Any]:
        return {"expected_llm_call_count": 0, "finding_count": len(self.findings), "zero_llm_expected": True}

    def to_dict(self) -> dict[str, Any]:
        return {"created_at": self.created_at, "finding_policy_version": self.finding_policy_version, "finding_schema_version": self.finding_schema_version, "findings": [item.to_dict() for item in self.findings], "gate_fingerprint": self.gate_fingerprint, "summary": self.summary_dict(), "visit_ref": self.visit_ref}

    def canonical_json(self) -> str:
        return _json(self.to_dict())

    def fingerprint(self) -> str:
        value = self.to_dict(); value.pop("created_at")
        return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def build_luxian_0609_programmatic_findings_shadow(*, gate_report: Any, finding_schema_version: str, finding_policy_version: str, created_at: str) -> ProgrammaticFindingReport:
    if not isinstance(gate_report, gate_module.GateReport):
        raise TypeError("gate_report must be accepted GateReport")
    findings = tuple(ProgrammaticFinding(decision.rule_id, _kind_for(decision), decision.target_source_key, decision.parent_rule_ids, decision.dependency_reason_codes, tuple(ref.fact_id for ref in decision.matched_fact_refs)) for decision in gate_report.decisions)
    return ProgrammaticFindingReport(finding_schema_version, finding_policy_version, gate_report.visit_ref, gate_report.fingerprint(), findings, created_at)
