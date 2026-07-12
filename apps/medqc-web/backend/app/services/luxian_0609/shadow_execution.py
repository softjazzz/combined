"""029/030/032 纯 shadow 纵向执行编排；不接生产运行时。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from . import deterministic_gate as gate
from . import fact_coverage as coverage
from . import planner
from . import programmatic_rules as rules
from . import result_aggregator as aggregator
from . import shadow_fact_bundle as bundle
from . import source_manifest_builder as manifest_builder

_RULES = ("LX0609-029", "LX0609-030", "LX0609-032")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_SENSITIVE = re.compile(r"(?i)(full[_ -]?text|medical[_ -]?text|raw[_ -]?(text|response|output)|patient[_ -]?name|mobile|address|source[_ -]?document|record[_ -]?content|error[_ -]?stack|sql|private[_ -]?key|prompt|quote|value|trace|response|authorization|bearer|api[_ -]?key|password|(?:^|[_-])sk[_-]|phone|id[_ -]?card)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
FULL_STAGE_ORDER = ("planner", "manifest", "bundle", "coverage", "gate", "finding", "aggregation")
MAX_COVERAGE_OUTCOMES = 64


def _json(value: Any) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def _code(name: str, value: Any, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum or not _CODE.fullmatch(value) or _SENSITIVE.search(value) or _PHONE.search(value) or _ID_CARD.search(value): raise ValueError(f"invalid {name}")
    return value
def _created(value: Any) -> str:
    try:
        if not isinstance(value, str): raise ValueError
        datetime.fromisoformat(value.replace("Z", "+00:00")); return value
    except ValueError: raise ValueError("invalid created_at") from None


@dataclass(frozen=True)
class FactCoverageOutcomeInput:
    fact_type: str
    source_key: str
    state: coverage.ExtractionCoverageState | str
    extractor_version: str
    mapping_policy_version: str
    processed_record_count: int
    produced_pair_refs: tuple[str, ...]
    reason_code: str = ""
    error_code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_type", _code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _code("source_key", self.source_key))
        object.__setattr__(self, "extractor_version", _code("extractor_version", self.extractor_version, 96))
        object.__setattr__(self, "mapping_policy_version", _code("mapping_policy_version", self.mapping_policy_version, 96))
        try:
            state = coverage.ExtractionCoverageState(self.state)
        except (TypeError, ValueError):
            raise ValueError("invalid coverage state") from None
        object.__setattr__(self, "state", state.value)
        if type(self.produced_pair_refs) is not tuple or len(self.produced_pair_refs) > bundle.MAX_SHADOW_FACTS: raise TypeError("produced_pair_refs must be bounded tuple")
        refs = tuple(sorted(self.produced_pair_refs))
        if not all(isinstance(item, str) and _SHA.fullmatch(item) for item in refs) or len(refs) != len(set(refs)): raise ValueError("invalid produced_pair_refs")
        if isinstance(self.processed_record_count, bool) or not isinstance(self.processed_record_count, int) or self.processed_record_count < 0 or (refs and self.processed_record_count == 0): raise ValueError("invalid processed_record_count")
        object.__setattr__(self, "produced_pair_refs", refs)
        object.__setattr__(self, "reason_code", _code("reason_code", self.reason_code, 64) if self.reason_code else "")
        object.__setattr__(self, "error_code", _code("error_code", self.error_code, 64) if self.error_code else "")

    def to_dict(self) -> dict[str, Any]:
        return {"fact_type": self.fact_type, "source_key": self.source_key, "state": self.state, "extractor_version": self.extractor_version, "mapping_policy_version": self.mapping_policy_version, "processed_record_count": self.processed_record_count, "produced_pair_refs": list(self.produced_pair_refs), "reason_code": self.reason_code, "error_code": self.error_code}


@dataclass(frozen=True)
class ShadowExecutionReport:
    execution_schema_version: str
    execution_policy_version: str
    package_version: str
    visit_ref: str
    disposition: str
    planned_rule_ids: tuple[str, ...]
    stage_order: tuple[str, ...]
    stage_fingerprints: tuple[tuple[str, str], ...]
    results: tuple[aggregator.AggregatedRuleResult, ...]
    created_at: str

    def __post_init__(self) -> None:
        if self.disposition not in ("completed", "skipped_no_effective_rules"): raise ValueError("invalid disposition")
        if type(self.planned_rule_ids) is not tuple or type(self.stage_order) is not tuple or type(self.stage_fingerprints) is not tuple or type(self.results) is not tuple: raise TypeError("execution collections must be tuple")
        if self.planned_rule_ids != tuple(rule for rule in _RULES if rule in self.planned_rule_ids) or len(set(self.planned_rule_ids)) != len(self.planned_rule_ids): raise ValueError("invalid planned rule ids")
        if self.disposition == "skipped_no_effective_rules" and (self.planned_rule_ids or self.stage_order != ("planner",) or len(self.stage_fingerprints) != 1 or self.stage_fingerprints[0][0] != "planner" or self.results): raise ValueError("invalid skipped execution")
        if self.disposition == "completed" and (not self.planned_rule_ids or self.stage_order != FULL_STAGE_ORDER or len(self.stage_fingerprints) != len(FULL_STAGE_ORDER) or tuple(item[0] for item in self.stage_fingerprints) != FULL_STAGE_ORDER): raise ValueError("invalid stage order")
        if tuple(result.rule_id for result in self.results) != self.planned_rule_ids: raise ValueError("result scope mismatch")
        if not all(isinstance(result, aggregator.AggregatedRuleResult) for result in self.results): raise TypeError("invalid results")
        if not all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and _SHA.fullmatch(item[1]) for item in self.stage_fingerprints): raise ValueError("invalid stage fingerprints")
        object.__setattr__(self, "execution_schema_version", _code("execution_schema_version", self.execution_schema_version, 64)); object.__setattr__(self, "execution_policy_version", _code("execution_policy_version", self.execution_policy_version, 64)); object.__setattr__(self, "package_version", _code("package_version", self.package_version, 64)); object.__setattr__(self, "visit_ref", _code("visit_ref", self.visit_ref)); object.__setattr__(self, "created_at", _created(self.created_at))

    def summary_dict(self) -> dict[str, Any]:
        counts = {"compliant": 0, "non_compliant": 0, "not_applicable": 0, "data_gap": 0, "technical_error": 0, "evaluation_unknown": 0}
        for result in self.results:
            counts[result.final_state.value] += 1
        return {**{f"{name}_count": value for name, value in counts.items()}, "expected_llm_call_count": 0, "llm_input_tokens": 0, "llm_output_tokens": 0, "llm_total_tokens": 0, "shadow_only": True, "release_eligible": False, "result_count": len(self.results)}
    def to_dict(self) -> dict[str, Any]: return {"execution_schema_version": self.execution_schema_version, "execution_policy_version": self.execution_policy_version, "package_version": self.package_version, "visit_ref": self.visit_ref, "disposition": self.disposition, "planned_rule_ids": list(self.planned_rule_ids), "stage_order": list(self.stage_order), "stage_fingerprints": [list(item) for item in self.stage_fingerprints], "results": [item.to_dict() for item in self.results], "summary": self.summary_dict(), "created_at": self.created_at}
    def canonical_json(self) -> str: return _json(self.to_dict())
    def fingerprint(self) -> str:
        value=self.to_dict();value.pop("created_at");return hashlib.sha256(_json(value).encode()).hexdigest()


def build_luxian_0609_shadow_execution(*, visit_ref: str, selected_rule_ids: Any, scoped_customer_rule_ids: Any, record_rule_map: Any, evidence_payload: Mapping[str, Any] | None, source_query_observations: Sequence[manifest_builder.SourceQueryObservation], fact_pairs: Sequence[bundle.FactShadowPairInput], deterministic_coverage_outcomes: Sequence[FactCoverageOutcomeInput], redaction_terms: Sequence[str], planner_schema_version: str, rule_plan_version: str, manifest_schema_version: str, bundle_schema_version: str, coverage_schema_version: str, coverage_policy_version: str, gate_schema_version: str, gate_policy_version: str, finding_schema_version: str, finding_policy_version: str, aggregation_schema_version: str, aggregation_policy_version: str, execution_schema_version: str, execution_policy_version: str, package_version: str, planner_created_at: str, manifest_created_at: str, bundle_created_at: str, coverage_created_at: str, gate_created_at: str, finding_created_at: str, aggregation_created_at: str, created_at: str) -> ShadowExecutionReport:
    plan = planner.build_luxian_0609_shadow_plan(visit_ref=visit_ref, selected_rule_ids=selected_rule_ids, scoped_customer_rule_ids=scoped_customer_rule_ids, record_rule_map=record_rule_map, planner_schema_version=planner_schema_version, rule_plan_version=rule_plan_version, created_at=planner_created_at)
    planned_ids = tuple(item.rule_id for item in plan.planned_rules)
    if not planned_ids:
        return ShadowExecutionReport(execution_schema_version, execution_policy_version, package_version, plan.visit_ref, "skipped_no_effective_rules", (), ("planner",), (("planner", plan.fingerprint()),), (), created_at)
    if type(source_query_observations) not in (tuple, list) or type(fact_pairs) not in (tuple, list) or type(deterministic_coverage_outcomes) not in (tuple, list) or type(redaction_terms) not in (tuple, list): raise TypeError("nonzero execution inputs must be concrete collections")
    if len(deterministic_coverage_outcomes) > MAX_COVERAGE_OUTCOMES or not all(isinstance(item, manifest_builder.SourceQueryObservation) for item in source_query_observations) or not all(isinstance(item, bundle.FactShadowPairInput) for item in fact_pairs) or not all(isinstance(item, FactCoverageOutcomeInput) for item in deterministic_coverage_outcomes) or not all(isinstance(item, str) for item in redaction_terms): raise TypeError("nonzero execution inputs contain invalid values")
    expected_sources = {source for item in plan.planned_rules for source in item.required_source_keys}
    observed_sources = {item.source_key for item in source_query_observations if isinstance(item, manifest_builder.SourceQueryObservation)}
    if len(observed_sources) != len(source_query_observations) or observed_sources != expected_sources: raise ValueError("source observations do not exactly match plan scope")
    manifest = manifest_builder.build_luxian_0609_source_manifest_shadow(visit_ref=plan.visit_ref, evidence_payload=evidence_payload, observations=source_query_observations, manifest_schema_version=manifest_schema_version, created_at=manifest_created_at)
    facts = bundle.build_luxian_0609_fact_shadow_bundle(visit_ref=plan.visit_ref, manifest=manifest, paired_inputs=fact_pairs, bundle_schema_version=bundle_schema_version, created_at=bundle_created_at, redaction_terms=redaction_terms)
    pair_index = {item.pair_ref: item.fact for item in facts.items}
    outcome_pairs = {(item.fact_type, item.source_key) for item in deterministic_coverage_outcomes}
    relevant_bundle_pair_refs = {
        item.pair_ref
        for item in facts.items
        if (item.fact.fact_type, item.fact.source_key) in outcome_pairs
    }
    claimed_refs: set[str] = set()
    observations: list[coverage.FactCoverageObservation] = []
    for outcome in deterministic_coverage_outcomes:
        fact_ids: list[str] = []
        for pair_ref in outcome.produced_pair_refs:
            fact = pair_index.get(pair_ref)
            if fact is None or pair_ref in claimed_refs: raise ValueError("invalid coverage pair reference")
            if fact.fact_type != outcome.fact_type or fact.source_key != outcome.source_key: raise ValueError("coverage pair reference mismatch")
            claimed_refs.add(pair_ref); fact_ids.append(fact.fact_id)
        observations.append(coverage.FactCoverageObservation(outcome.fact_type, outcome.source_key, outcome.state, outcome.extractor_version, outcome.mapping_policy_version, outcome.processed_record_count, tuple(fact_ids), outcome.reason_code, outcome.error_code))
    if claimed_refs != relevant_bundle_pair_refs:
        raise ValueError("missing coverage pair reference")
    coverage_report = coverage.build_luxian_0609_fact_coverage_shadow(plan=plan, manifest=manifest, bundle=facts, observations=tuple(observations), coverage_schema_version=coverage_schema_version, coverage_policy_version=coverage_policy_version, created_at=coverage_created_at)
    gate_report = gate.build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=facts, coverage=coverage_report, gate_schema_version=gate_schema_version, gate_policy_version=gate_policy_version, created_at=gate_created_at)
    finding = rules.build_luxian_0609_programmatic_findings_shadow(gate_report=gate_report, finding_schema_version=finding_schema_version, finding_policy_version=finding_policy_version, created_at=finding_created_at)
    aggregated = aggregator.aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate_report, finding_report=finding, expected_finding_schema_version=finding_schema_version, expected_finding_policy_version=finding_policy_version, aggregation_schema_version=aggregation_schema_version, aggregation_policy_version=aggregation_policy_version, created_at=aggregation_created_at)
    fingerprints = (("planner", plan.fingerprint()), ("manifest", manifest.fingerprint()), ("bundle", facts.fingerprint()), ("coverage", coverage_report.fingerprint()), ("gate", gate_report.fingerprint()), ("finding", finding.fingerprint()), ("aggregation", aggregated.fingerprint()))
    return ShadowExecutionReport(execution_schema_version, execution_policy_version, package_version, plan.visit_ref, "completed", planned_ids, FULL_STAGE_ORDER, fingerprints, tuple(aggregated.results), created_at)
