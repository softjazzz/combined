"""029/030/032 runtime shadow 输入组装；不读取文书内容或接入运行时。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from app.services.luxian_0609 import planner
from app.services.luxian_0609 import shadow_execution
from app.services.luxian_0609 import shadow_fact_bundle
from app.services.luxian_0609 import source_manifest_builder
from app.services.luxian_0609.legacy_fact_adapter import LegacyFactV2Mapping
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609_fact_extraction import Luxian0609Fact

_SHA = re.compile(r"^[a-f0-9]{64}$")
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SENSITIVE = re.compile(r"(?i)(full[_ -]?text|medical[_ -]?text|raw[_ -]?(text|response|output)|patient[_ -]?name|mobile|address|source[_ -]?document|record[_ -]?content|error[_ -]?stack|sql|private[_ -]?key|prompt|quote|value|trace|response|authorization|bearer|api[_ -]?key|password|(?:^|[_-])sk[_-]|phone|id[_ -]?card)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_MAX_INPUTS = 64
_MAX_SIGNALS = 512
_ALLOWED_FACT_TYPES = {"current_visit_surgery_order_confirmed", "current_visit_surgery_confirmed"}
_STATES = {"complete", "partial", "not_run", "error"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _code(name: str, value: Any, maximum: int = 96) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum or not _CODE.fullmatch(value) or _SENSITIVE.search(value) or _PHONE.search(value) or _ID_CARD.search(value):
        raise ValueError(f"invalid {name}")
    return value


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _created(value: Any) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        raise ValueError("invalid created_at") from None


@dataclass(frozen=True)
class RuntimeStructuredFactSignal:
    signal_ref: str
    fact_type: str
    source_key: str
    event_status: str
    source_record_ref: str
    source_document_type: str
    extractor_version: str
    mapping_policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_ref", _sha("signal_ref", self.signal_ref))
        object.__setattr__(self, "source_record_ref", _sha("source_record_ref", self.source_record_ref))
        object.__setattr__(self, "fact_type", _code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _code("source_key", self.source_key))
        object.__setattr__(self, "source_document_type", _code("source_document_type", self.source_document_type))
        object.__setattr__(self, "extractor_version", _code("extractor_version", self.extractor_version))
        object.__setattr__(self, "mapping_policy_version", _code("mapping_policy_version", self.mapping_policy_version))
        if self.fact_type not in _ALLOWED_FACT_TYPES or self.event_status not in {"ordered", "performed"}:
            raise ValueError("invalid structured signal semantics")
        if self.fact_type == "current_visit_surgery_confirmed" and self.event_status != "performed":
            raise ValueError("invalid structured signal semantics")


@dataclass(frozen=True)
class RuntimePairExtractionInput:
    fact_type: str
    source_key: str
    state: str
    extractor_version: str
    mapping_policy_version: str
    processed_record_count: int
    positive_signals: tuple[RuntimeStructuredFactSignal, ...]
    reason_code: str = ""
    error_code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_type", _code("fact_type", self.fact_type))
        object.__setattr__(self, "source_key", _code("source_key", self.source_key))
        object.__setattr__(self, "extractor_version", _code("extractor_version", self.extractor_version))
        object.__setattr__(self, "mapping_policy_version", _code("mapping_policy_version", self.mapping_policy_version))
        if self.fact_type not in _ALLOWED_FACT_TYPES or self.state not in _STATES:
            raise ValueError("invalid extraction input")
        if type(self.positive_signals) is not tuple or len(self.positive_signals) > _MAX_SIGNALS or not all(isinstance(item, RuntimeStructuredFactSignal) for item in self.positive_signals):
            raise TypeError("positive_signals must be bounded tuple")
        if isinstance(self.processed_record_count, bool) or not isinstance(self.processed_record_count, int) or self.processed_record_count < 0 or (self.positive_signals and self.processed_record_count == 0):
            raise ValueError("invalid processed_record_count")
        if any((item.fact_type, item.source_key) != (self.fact_type, self.source_key) for item in self.positive_signals):
            raise ValueError("signal pair mismatch")
        refs = [item.signal_ref for item in self.positive_signals]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate signal_ref")
        object.__setattr__(self, "positive_signals", tuple(sorted(self.positive_signals, key=lambda item: item.signal_ref)))
        object.__setattr__(self, "reason_code", _code("reason_code", self.reason_code, 64) if self.reason_code else "")
        object.__setattr__(self, "error_code", _code("error_code", self.error_code, 64) if self.error_code else "")


@dataclass(frozen=True)
class RuntimeShadowAssembly:
    assembler_schema_version: str
    assembler_policy_version: str
    visit_ref: str
    plan_fingerprint: str
    disposition: str
    planned_rule_ids: tuple[str, ...]
    source_query_observations: tuple[source_manifest_builder.SourceQueryObservation, ...]
    fact_pairs: tuple[shadow_fact_bundle.FactShadowPairInput, ...] = field(repr=False)
    deterministic_coverage_outcomes: tuple[shadow_execution.FactCoverageOutcomeInput, ...]
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "assembler_schema_version", _code("assembler_schema_version", self.assembler_schema_version))
        object.__setattr__(self, "assembler_policy_version", _code("assembler_policy_version", self.assembler_policy_version))
        object.__setattr__(self, "visit_ref", _code("visit_ref", self.visit_ref))
        object.__setattr__(self, "plan_fingerprint", _sha("plan_fingerprint", self.plan_fingerprint))
        object.__setattr__(self, "created_at", _created(self.created_at))
        if self.disposition not in {"assembled", "skipped_no_effective_rules"}:
            raise ValueError("invalid disposition")
        for values, value_type in ((self.planned_rule_ids, str), (self.source_query_observations, source_manifest_builder.SourceQueryObservation), (self.fact_pairs, shadow_fact_bundle.FactShadowPairInput), (self.deterministic_coverage_outcomes, shadow_execution.FactCoverageOutcomeInput)):
            if type(values) is not tuple or not all(isinstance(item, value_type) for item in values):
                raise TypeError("assembly collections must be tuple")
        if self.disposition == "skipped_no_effective_rules" and (self.planned_rule_ids or self.source_query_observations or self.fact_pairs or self.deterministic_coverage_outcomes):
            raise ValueError("invalid skipped assembly")
        if self.disposition == "assembled":
            if not self.planned_rule_ids or self.planned_rule_ids != tuple(rule for rule in ("LX0609-029", "LX0609-030", "LX0609-032") if rule in self.planned_rule_ids) or not self.source_query_observations or not self.deterministic_coverage_outcomes:
                raise ValueError("invalid assembled scope")
            if tuple(item.source_key for item in self.source_query_observations) != tuple(sorted(item.source_key for item in self.source_query_observations)) or len({item.source_key for item in self.source_query_observations}) != len(self.source_query_observations):
                raise ValueError("invalid assembly sources")
            if tuple((item.fact_type, item.source_key) for item in self.deterministic_coverage_outcomes) != tuple(sorted((item.fact_type, item.source_key) for item in self.deterministic_coverage_outcomes)) or len({(item.fact_type, item.source_key) for item in self.deterministic_coverage_outcomes}) != len(self.deterministic_coverage_outcomes):
                raise ValueError("invalid assembly outcomes")
            if tuple(item.pair_ref for item in self.fact_pairs) != tuple(sorted(item.pair_ref for item in self.fact_pairs)) or len({item.pair_ref for item in self.fact_pairs}) != len(self.fact_pairs):
                raise ValueError("invalid assembly pairs")
            outcome_pairs = {(item.fact_type, item.source_key) for item in self.deterministic_coverage_outcomes}
            claimed = {ref for item in self.deterministic_coverage_outcomes for ref in item.produced_pair_refs}
            relevant = {item.pair_ref for item in self.fact_pairs if (item.legacy_fact.fact_type, item.mapping.source_key) in outcome_pairs}
            if claimed != relevant:
                raise ValueError("invalid assembly pair claims")
            for pair in self.fact_pairs:
                fact, mapping = pair.legacy_fact, pair.mapping
                if fact.fact_type not in _ALLOWED_FACT_TYPES or fact.family != "surgery_anesthesia" or not _SHA.fullmatch(fact.source_document_id) or fact.quote != "runtime_structured_signal" or fact.confidence != 1.0 or fact.extractor != "runtime_structured" or fact.trace != {}:
                    raise ValueError("invalid assembly fact pair")
                if mapping.source_key not in {item.source_key for item in self.deterministic_coverage_outcomes} or str(mapping.trigger_scope) != "current_visit" or str(mapping.current_visit_relevance) != "relevant" or str(mapping.assertion) != "affirmed" or str(mapping.assertion_context) != "current_narrative" or str(mapping.event_status) not in {"ordered", "performed"}:
                    raise ValueError("invalid assembly fact mapping")
                expected = {"event": str(mapping.event_status), "fact": fact.fact_type, "source": mapping.source_key}
                if mapping.normalized_value != expected or not isinstance(mapping.extractor_version, str) or not mapping.extractor_version.startswith(self.assembler_policy_version + "."):
                    raise ValueError("invalid assembly fact mapping")

    def summary_dict(self) -> dict[str, Any]:
        return {"source_count": len(self.source_query_observations), "pair_count": len(self.deterministic_coverage_outcomes), "fact_count": len(self.fact_pairs), "zero_llm": True, "llm_call_count": 0, "llm_total_tokens": 0}

    def safe_to_dict(self) -> dict[str, Any]:
        facts = [{"pair_ref": item.pair_ref, "fact_type": item.legacy_fact.fact_type, "source_key": item.mapping.source_key, "event_status": str(item.mapping.event_status), "source_record_ref": item.legacy_fact.source_document_id, "extractor_version": item.mapping.extractor_version} for item in self.fact_pairs]
        return {"assembler_schema_version": self.assembler_schema_version, "assembler_policy_version": self.assembler_policy_version, "visit_ref": self.visit_ref, "plan_fingerprint": self.plan_fingerprint, "disposition": self.disposition, "planned_rule_ids": list(self.planned_rule_ids), "sources": [{"source_key": item.source_key, "query_status": item.query_status.value} for item in self.source_query_observations], "facts": facts, "coverage": [item.to_dict() for item in self.deterministic_coverage_outcomes], "summary": self.summary_dict(), "created_at": self.created_at}

    def fingerprint(self) -> str:
        value = self.safe_to_dict(); value.pop("created_at")
        return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _required_pairs(plan: planner.ShadowRulePlan) -> tuple[tuple[str, str], ...]:
    pairs = {(requirement.fact_type, source) for rule in plan.planned_rules for requirement in rule.trigger_requirements for source in requirement.allowed_source_keys}
    return tuple(sorted(pairs))


def _document_counts(evidence_payload: Mapping[str, Any] | None, sources: set[str]) -> dict[str, int]:
    if evidence_payload is None:
        documents: Any = {}
    elif not isinstance(evidence_payload, Mapping):
        raise TypeError("evidence_payload must be mapping")
    else:
        timeline = evidence_payload.get("programmatic_timeline", {})
        if not isinstance(timeline, Mapping):
            raise ValueError("invalid evidence payload")
        documents = timeline.get("documents", {})
    if not isinstance(documents, Mapping):
        raise ValueError("invalid evidence payload")
    counts: dict[str, int] = {}
    for source in sources:
        values = documents.get(source, [])
        if not isinstance(values, list):
            raise ValueError("invalid evidence documents")
        counts[source] = len(values)
    return counts


def assemble_luxian_0609_runtime_shadow_inputs(*, plan: planner.ShadowRulePlan, evidence_payload: Mapping[str, Any] | None, source_query_observations: Sequence[source_manifest_builder.SourceQueryObservation], extraction_inputs: Sequence[RuntimePairExtractionInput], assembler_schema_version: str, assembler_policy_version: str, created_at: str) -> RuntimeShadowAssembly:
    if not isinstance(plan, planner.ShadowRulePlan):
        raise TypeError("plan must be ShadowRulePlan")
    planned_rule_ids = tuple(item.rule_id for item in plan.planned_rules)
    if not planned_rule_ids:
        return RuntimeShadowAssembly(assembler_schema_version, assembler_policy_version, plan.visit_ref, plan.fingerprint(), "skipped_no_effective_rules", (), (), (), (), created_at)
    if type(source_query_observations) not in (tuple, list) or type(extraction_inputs) not in (tuple, list):
        raise TypeError("assembler inputs must be concrete collections")
    if len(source_query_observations) > _MAX_INPUTS or len(extraction_inputs) > _MAX_INPUTS or not all(isinstance(item, source_manifest_builder.SourceQueryObservation) for item in source_query_observations) or not all(isinstance(item, RuntimePairExtractionInput) for item in extraction_inputs):
        raise TypeError("invalid assembler inputs")
    expected_sources = {source for rule in plan.planned_rules for source in rule.required_source_keys}
    observed = {item.source_key for item in source_query_observations}
    if observed != expected_sources or len(observed) != len(source_query_observations):
        raise ValueError("source observations do not match plan scope")
    required_pairs = _required_pairs(plan)
    input_by_pair = {(item.fact_type, item.source_key): item for item in extraction_inputs}
    if set(input_by_pair) != set(required_pairs) or len(input_by_pair) != len(extraction_inputs):
        raise ValueError("extraction inputs do not match trigger requirements")
    counts = _document_counts(evidence_payload, expected_sources)
    observations = tuple(sorted(source_query_observations, key=lambda item: item.source_key))
    source_status = {item.source_key: item.query_status for item in observations}
    pairs: list[shadow_fact_bundle.FactShadowPairInput] = []
    outcomes: list[shadow_execution.FactCoverageOutcomeInput] = []
    seen_refs: set[str] = set()
    for fact_type, source_key in required_pairs:
        item = input_by_pair[(fact_type, source_key)]
        status, count = source_status[source_key], counts[source_key]
        if status is QueryStatus.AVAILABLE and count == 0 or status is QueryStatus.EMPTY and count != 0 or status in {QueryStatus.UNAVAILABLE, QueryStatus.ERROR} and count != 0:
            raise ValueError("source status and document count mismatch")
        if status in {QueryStatus.UNAVAILABLE, QueryStatus.ERROR}:
            expected_reason = "source_unavailable" if status is QueryStatus.UNAVAILABLE else "source_query_error"
            if item.state != "not_run" or item.processed_record_count != 0 or item.positive_signals or item.reason_code != expected_reason or item.error_code:
                raise ValueError("invalid unavailable source extraction")
        elif status is QueryStatus.EMPTY:
            valid_empty = (item.state == "complete" and item.processed_record_count == 0 and not item.reason_code and not item.error_code) or (item.state == "not_run" and item.processed_record_count == 0 and item.reason_code == "extractor_not_run" and not item.error_code)
            if item.positive_signals or not valid_empty:
                raise ValueError("invalid empty source extraction")
        elif item.state == "complete" and (item.processed_record_count != count or item.reason_code or item.error_code):
            raise ValueError("invalid complete extraction count")
        elif item.state == "partial" and (item.processed_record_count >= count or item.reason_code not in {"partial_budget_limit", "partial_unsupported_record"} or item.error_code):
            raise ValueError("invalid partial extraction")
        elif item.state == "not_run" and (item.processed_record_count != 0 or item.positive_signals or item.reason_code != "extractor_not_run" or item.error_code):
            raise ValueError("invalid not_run extraction")
        elif item.state == "error" and (item.processed_record_count > count or item.reason_code != "extraction_error" or not item.error_code):
            raise ValueError("invalid extraction error")
        for signal in item.positive_signals:
            if signal.extractor_version != item.extractor_version or signal.mapping_policy_version != item.mapping_policy_version:
                raise ValueError("signal provenance mismatch")
            if signal.signal_ref in seen_refs:
                raise ValueError("duplicate signal_ref")
            seen_refs.add(signal.signal_ref)
            requirement_ok = any(requirement.fact_type == signal.fact_type and signal.source_key in requirement.allowed_source_keys and signal.event_status in requirement.allowed_event_statuses for rule in plan.planned_rules for requirement in rule.trigger_requirements)
            if not requirement_ok:
                raise ValueError("signal violates trigger requirement")
            normalized = {"event": signal.event_status, "fact": signal.fact_type, "source": signal.source_key}
            legacy = Luxian0609Fact(fact_type=signal.fact_type, family="surgery_anesthesia", source_document_type=signal.source_document_type, source_document_id=signal.source_record_ref, record_time="", quote="runtime_structured_signal", confidence=1.0, extractor="runtime_structured", trace={})
            mapping = LegacyFactV2Mapping(source_key=signal.source_key, normalized_value=normalized, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status=signal.event_status, extractor_version=f"{assembler_policy_version}.{signal.mapping_policy_version}.{signal.extractor_version}", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
            pairs.append(shadow_fact_bundle.FactShadowPairInput(signal.signal_ref, legacy, mapping))
        outcomes.append(shadow_execution.FactCoverageOutcomeInput(item.fact_type, item.source_key, item.state, item.extractor_version, item.mapping_policy_version, item.processed_record_count, tuple(signal.signal_ref for signal in item.positive_signals), item.reason_code, item.error_code))
    return RuntimeShadowAssembly(assembler_schema_version, assembler_policy_version, plan.visit_ref, plan.fingerprint(), "assembled", planned_rule_ids, observations, tuple(sorted(pairs, key=lambda item: item.pair_ref)), tuple(sorted(outcomes, key=lambda item: (item.fact_type, item.source_key))), created_at)
