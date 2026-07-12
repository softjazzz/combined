"""029/030/032 的纯 deterministic shadow gate。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any

from .fact_coverage import CoveragePair, ExtractionCoverageState, FactCoverageReport
from .fact_schema import Assertion, CurrentVisitRelevance, EventStatus, FactV2, TriggerScope
from .planner import PlannedRule, ShadowRulePlan
from .shadow_fact_bundle import FactShadowBundle
from .source_manifest import DocumentManifest, QueryStatus

MAX_GATE_DECISIONS = 3
MAX_MATCHED_FACT_REFS = 512
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_FORBIDDEN = re.compile(r"(?i)(not[_ -]?applicable|data[_ -]?gap|non[_ -]?compliant|ai[_ -]?suggested|technical[_ -]?error|evaluation[_ -]?unknown|suppressed|(?<!non[_ -])compliant)")
_RULE_ORDER = ("LX0609-029", "LX0609-030", "LX0609-032")
_ORDER_PAIR = ("current_visit_surgery_order_confirmed", "inpat_nondrug_order")
_PERFORMED_PAIRS = frozenset({("current_visit_surgery_confirmed", "surgery_application"), ("current_visit_surgery_confirmed", "surgery_record")})
_RULE_CONTRACT = MappingProxyType({
    "LX0609-029": ("presurg_summary", (), (), frozenset({_ORDER_PAIR, *_PERFORMED_PAIRS})),
    "LX0609-030": ("surgery_record", (), (), frozenset({_ORDER_PAIR, *_PERFORMED_PAIRS})),
    "LX0609-032": ("surgery_safecheck_record", ("LX0609-030",), ("informational_parent_only",), _PERFORMED_PAIRS),
})


class TriggerResolution(str, Enum):
    MATCHED = "matched"
    ABSENT_COMPLETE = "absent_complete"
    SEMANTIC_CONFLICT = "semantic_conflict"
    SOURCE_ERROR = "source_error"
    COVERAGE_ERROR = "coverage_error"
    SOURCE_UNAVAILABLE = "source_unavailable"
    COVERAGE_PARTIAL = "coverage_partial"
    COVERAGE_NOT_RUN = "coverage_not_run"


class TargetResolution(str, Enum):
    PRESENT = "present"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class GateReadiness(str, Enum):
    READY = "ready"
    NOT_TRIGGERED = "not_triggered"
    BLOCKED = "blocked"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _code(name: str, value: Any, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum or not _CODE.fullmatch(value) or _FORBIDDEN.search(value):
        raise ValueError(f"invalid {name}")
    return value


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _created(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("created_at must be explicit ISO-8601 text")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("created_at must be valid ISO-8601 text") from None
    return value


@dataclass(frozen=True)
class GateFactRef:
    fact_id: str
    fact_type: str
    source_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_id", _sha("fact_id", self.fact_id))
        object.__setattr__(self, "fact_type", _code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _code("source_key", self.source_key))

    def to_dict(self) -> dict[str, str]:
        return {"fact_id": self.fact_id, "fact_type": self.fact_type, "source_key": self.source_key}


@dataclass(frozen=True)
class GateDecision:
    rule_id: str
    trigger_resolution: TriggerResolution | str
    target_source_key: str
    target_resolution: TargetResolution | str | None
    readiness: GateReadiness | str
    matched_fact_refs: tuple[GateFactRef, ...]
    parent_rule_ids: tuple[str, ...]
    dependency_reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.matched_fact_refs) is not tuple or type(self.parent_rule_ids) is not tuple or type(self.dependency_reason_codes) is not tuple:
            raise TypeError("gate decision collections must be tuple")
        trigger = TriggerResolution(self.trigger_resolution)
        target = TargetResolution(self.target_resolution) if self.target_resolution is not None else None
        readiness = GateReadiness(self.readiness)
        refs = tuple(sorted(self.matched_fact_refs, key=lambda item: item.fact_id))
        if len(refs) > MAX_MATCHED_FACT_REFS or not all(isinstance(item, GateFactRef) for item in refs) or len({item.fact_id for item in refs}) != len(refs):
            raise ValueError("invalid matched fact refs")
        rule_id = _code("rule_id", self.rule_id)
        contract = _RULE_CONTRACT.get(rule_id)
        if contract is None:
            raise ValueError("unsupported gate rule")
        expected_target, expected_parents, expected_reasons, allowed_pairs = contract
        if self.target_source_key != expected_target or self.parent_rule_ids != expected_parents or self.dependency_reason_codes != expected_reasons:
            raise ValueError("gate rule metadata mismatch")
        if any((ref.fact_type, ref.source_key) not in allowed_pairs for ref in refs):
            raise ValueError("matched fact ref is not allowed for rule")
        if trigger is TriggerResolution.MATCHED:
            if not refs or target is None or (target in (TargetResolution.PRESENT, TargetResolution.EMPTY) and readiness is not GateReadiness.READY) or (target in (TargetResolution.UNAVAILABLE, TargetResolution.ERROR) and readiness is not GateReadiness.BLOCKED):
                raise ValueError("invalid matched gate decision")
        elif trigger is TriggerResolution.ABSENT_COMPLETE:
            if refs or target is not None or readiness is not GateReadiness.NOT_TRIGGERED:
                raise ValueError("invalid absent gate decision")
        elif refs or target is not None or readiness is not GateReadiness.BLOCKED:
            raise ValueError("invalid blocked gate decision")
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "trigger_resolution", trigger)
        object.__setattr__(self, "target_source_key", _code("target_source_key", self.target_source_key))
        object.__setattr__(self, "target_resolution", target)
        object.__setattr__(self, "readiness", readiness)
        object.__setattr__(self, "matched_fact_refs", refs)

    def to_dict(self) -> dict[str, Any]:
        return {"dependency_reason_codes": list(self.dependency_reason_codes), "matched_fact_refs": [x.to_dict() for x in self.matched_fact_refs], "parent_rule_ids": list(self.parent_rule_ids), "readiness": self.readiness.value, "rule_id": self.rule_id, "target_resolution": self.target_resolution.value if self.target_resolution else None, "target_source_key": self.target_source_key, "trigger_resolution": self.trigger_resolution.value}


@dataclass(frozen=True)
class GateReport:
    gate_schema_version: str
    gate_policy_version: str
    visit_ref: str
    plan_fingerprint: str
    manifest_fingerprint: str
    source_snapshot_hash: str
    bundle_fingerprint: str
    coverage_fingerprint: str
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[GateDecision, ...]
    created_at: str

    def __post_init__(self) -> None:
        if type(self.decisions) is not tuple or type(self.planned_rule_ids) is not tuple or len(self.decisions) > MAX_GATE_DECISIONS or not all(isinstance(x, GateDecision) for x in self.decisions):
            raise ValueError("invalid gate decisions")
        if self.planned_rule_ids != tuple(x for x in _RULE_ORDER if x in self.planned_rule_ids) or len(set(self.planned_rule_ids)) != len(self.planned_rule_ids):
            raise ValueError("invalid planned rule ids")
        if tuple(x.rule_id for x in self.decisions) != self.planned_rule_ids:
            raise ValueError("gate decisions do not exactly match planned rules")
        if len({x.rule_id for x in self.decisions}) != len(self.decisions):
            raise ValueError("duplicate gate decision rule")
        object.__setattr__(self, "gate_schema_version", _code("gate_schema_version", self.gate_schema_version, 64))
        object.__setattr__(self, "gate_policy_version", _code("gate_policy_version", self.gate_policy_version, 64))
        object.__setattr__(self, "visit_ref", _code("visit_ref", self.visit_ref))
        for name in ("plan_fingerprint", "manifest_fingerprint", "source_snapshot_hash", "bundle_fingerprint", "coverage_fingerprint"):
            object.__setattr__(self, name, _sha(name, getattr(self, name)))
        object.__setattr__(self, "created_at", _created(self.created_at))

    def summary_dict(self) -> dict[str, Any]:
        decisions = self.decisions
        return {"absent_complete_count": sum(x.trigger_resolution is TriggerResolution.ABSENT_COMPLETE for x in decisions), "blocked_count": sum(x.readiness is GateReadiness.BLOCKED for x in decisions), "decision_count": len(decisions), "expected_llm_call_count": 0, "matched_count": sum(x.trigger_resolution is TriggerResolution.MATCHED for x in decisions), "ready_count": sum(x.readiness is GateReadiness.READY for x in decisions), "zero_llm_expected": True}

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_fingerprint": self.bundle_fingerprint, "coverage_fingerprint": self.coverage_fingerprint, "created_at": self.created_at, "decisions": [x.to_dict() for x in self.decisions], "gate_policy_version": self.gate_policy_version, "gate_schema_version": self.gate_schema_version, "manifest_fingerprint": self.manifest_fingerprint, "plan_fingerprint": self.plan_fingerprint, "planned_rule_ids": list(self.planned_rule_ids), "source_snapshot_hash": self.source_snapshot_hash, "summary": self.summary_dict(), "visit_ref": self.visit_ref}

    def identity_dict(self) -> dict[str, Any]:
        d = self.to_dict(); d.pop("created_at"); return d
    def canonical_json(self) -> str: return _json(self.to_dict())
    def fingerprint(self) -> str: return hashlib.sha256(_json(self.identity_dict()).encode()).hexdigest()


def _pair_resolution(item, context) -> TriggerResolution | None:
    if context.query_status is QueryStatus.EMPTY: return None
    if context.query_status is QueryStatus.ERROR: return TriggerResolution.SOURCE_ERROR
    if context.query_status is QueryStatus.UNAVAILABLE: return TriggerResolution.SOURCE_UNAVAILABLE
    if item.observation.state is ExtractionCoverageState.COMPLETE: return None
    if item.observation.state is ExtractionCoverageState.ERROR: return TriggerResolution.COVERAGE_ERROR
    if item.observation.state is ExtractionCoverageState.PARTIAL: return TriggerResolution.COVERAGE_PARTIAL
    return TriggerResolution.COVERAGE_NOT_RUN


def build_luxian_0609_deterministic_gate_shadow(*, plan: ShadowRulePlan, manifest: DocumentManifest, bundle: FactShadowBundle, coverage: FactCoverageReport, gate_schema_version: str, gate_policy_version: str, created_at: str) -> GateReport:
    if tuple(type(value).__name__ for value in (plan, manifest, bundle, coverage)) != ("ShadowRulePlan", "DocumentManifest", "FactShadowBundle", "FactCoverageReport"): raise TypeError("gate inputs must be accepted value objects")
    if plan.visit_ref != manifest.visit_ref or plan.visit_ref != bundle.visit_ref or plan.visit_ref != coverage.visit_ref: raise ValueError("gate visit_ref mismatch")
    if bundle.manifest_fingerprint != manifest.fingerprint() or bundle.source_snapshot_hash != manifest.source_snapshot_hash: raise ValueError("gate bundle manifest mismatch")
    if coverage.plan_fingerprint != plan.fingerprint() or coverage.manifest_fingerprint != manifest.fingerprint() or coverage.bundle_fingerprint != bundle.fingerprint() or coverage.source_snapshot_hash != manifest.source_snapshot_hash: raise ValueError("gate coverage fingerprint mismatch")
    entries = {x.source_key: x for x in manifest.entries}; contexts = {x.source_key: x for x in coverage.source_contexts}; coverage_items = {x.pair: x for x in coverage.items}; facts = {x.fact.fact_id: x.fact for x in bundle.items}
    for rule in plan.planned_rules:
        if rule.target_source_key not in entries:
            raise ValueError("gate target source absent manifest")
    decisions=[]
    precedence=[TriggerResolution.SOURCE_ERROR, TriggerResolution.COVERAGE_ERROR, TriggerResolution.SOURCE_UNAVAILABLE, TriggerResolution.COVERAGE_PARTIAL, TriggerResolution.COVERAGE_NOT_RUN]
    for rule in plan.planned_rules:
        matched=[]; conflict=False; blockers=[]
        for req in rule.trigger_requirements:
            for source in req.allowed_source_keys:
                pair=(req.fact_type, source); item=coverage_items.get(CoveragePair(req.fact_type, source))
                if item is None or source not in contexts: raise ValueError("gate coverage pair mismatch")
                for ref in item.produced_fact_refs:
                    fact=facts.get(ref.fact_id)
                    if fact is None: raise ValueError("gate fact reference missing bundle")
                    if fact.fact_type==req.fact_type and fact.source_key==source:
                        if fact.trigger_scope.value==req.trigger_scope and fact.current_visit_relevance.value==req.current_visit_relevance and fact.assertion.value==req.assertion and fact.event_status.value in req.allowed_event_statuses:
                            matched.append(GateFactRef(fact.fact_id, fact.fact_type, fact.source_key))
                        else: conflict=True
                outcome=_pair_resolution(item, contexts[source])
                if outcome: blockers.append(outcome)
        if matched:
            target=entries.get(rule.target_source_key)
            if target is None: raise ValueError("gate target source absent manifest")
            mapping={QueryStatus.AVAILABLE:TargetResolution.PRESENT, QueryStatus.EMPTY:TargetResolution.EMPTY, QueryStatus.UNAVAILABLE:TargetResolution.UNAVAILABLE, QueryStatus.ERROR:TargetResolution.ERROR}
            decisions.append(GateDecision(rule.rule_id, TriggerResolution.MATCHED, rule.target_source_key, mapping[target.query_status], GateReadiness.READY if target.query_status in (QueryStatus.AVAILABLE,QueryStatus.EMPTY) else GateReadiness.BLOCKED, tuple(matched), rule.parent_rule_ids, rule.dependency_reason_codes))
        elif conflict:
            decisions.append(GateDecision(rule.rule_id, TriggerResolution.SEMANTIC_CONFLICT, rule.target_source_key, None, GateReadiness.BLOCKED, (), rule.parent_rule_ids, rule.dependency_reason_codes))
        elif not blockers:
            decisions.append(GateDecision(rule.rule_id, TriggerResolution.ABSENT_COMPLETE, rule.target_source_key, None, GateReadiness.NOT_TRIGGERED, (), rule.parent_rule_ids, rule.dependency_reason_codes))
        else:
            outcome=next(x for x in precedence if x in blockers)
            decisions.append(GateDecision(rule.rule_id, outcome, rule.target_source_key, None, GateReadiness.BLOCKED, (), rule.parent_rule_ids, rule.dependency_reason_codes))
    return GateReport(gate_schema_version, gate_policy_version, plan.visit_ref, plan.fingerprint(), manifest.fingerprint(), manifest.source_snapshot_hash, bundle.fingerprint(), coverage.fingerprint(), tuple(rule.rule_id for rule in plan.planned_rules), tuple(decisions), created_at)
