from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from app.services.luxian_0609 import planner
from app.services.luxian_0609.runtime_shadow_assembler import (
    RuntimePairExtractionInput,
    RuntimeStructuredFactSignal,
    assemble_luxian_0609_runtime_shadow_inputs,
)
from app.services.luxian_0609.source_manifest_builder import SourceQueryObservation
from app.services.luxian_0609.shadow_execution import build_luxian_0609_shadow_execution

CREATED = "2026-07-12T18:00:00+08:00"
VISIT = "visit-runtime-001"


class Explosive:
    def __iter__(self): raise AssertionError("downstream input read")
    def __len__(self): raise AssertionError("downstream input read")


def _plan(*rules):
    return planner.build_luxian_0609_shadow_plan(visit_ref=VISIT, selected_rule_ids=list(rules), scoped_customer_rule_ids=list(rules), record_rule_map={VISIT: list(rules)}, planner_schema_version="planner-v1", rule_plan_version="slice-v1", created_at=CREATED)


def _signal(fact_type="current_visit_surgery_confirmed", source_key="surgery_record", event_status="performed", label="signal"):
    return RuntimeStructuredFactSignal(hashlib.sha256(label.encode()).hexdigest(), fact_type, source_key, event_status, hashlib.sha256((label + "-record").encode()).hexdigest(), "runtime_structured", "extractor-v1", "mapping-v1")


def _observations(plan, *, statuses=None):
    statuses = statuses or {}
    return tuple(SourceQueryObservation.create(source_key=source, query_status=statuses.get(source, "available"), query_version="query-v1", reason_code="source_paused" if statuses.get(source) == "unavailable" else "", error_code="source_failure" if statuses.get(source) == "error" else "") for source in sorted({source for rule in plan.planned_rules for source in rule.required_source_keys}))


def _inputs(plan, signal=None, *, statuses=None):
    statuses = statuses or {}
    pairs = sorted({(req.fact_type, source) for rule in plan.planned_rules for req in rule.trigger_requirements for source in req.allowed_source_keys})
    values = []
    for fact_type, source in pairs:
        status = statuses.get(source, "available")
        matching = (signal,) if signal and (fact_type, source) == (signal.fact_type, signal.source_key) else ()
        if status == "unavailable":
            values.append(RuntimePairExtractionInput(fact_type, source, "not_run", "extractor-v1", "mapping-v1", 0, (), "source_unavailable"))
        elif status == "error":
            values.append(RuntimePairExtractionInput(fact_type, source, "not_run", "extractor-v1", "mapping-v1", 0, (), "source_query_error"))
        elif status == "empty":
            values.append(RuntimePairExtractionInput(fact_type, source, "complete", "extractor-v1", "mapping-v1", 0, ()))
        else:
            values.append(RuntimePairExtractionInput(fact_type, source, "complete", "extractor-v1", "mapping-v1", 1, matching))
    return tuple(values)


def _payload(plan, *, statuses=None):
    statuses = statuses or {}
    sources = {source for rule in plan.planned_rules for source in rule.required_source_keys}
    return {"programmatic_timeline": {"documents": {source: ([] if statuses.get(source) in {"empty", "unavailable", "error"} else [{"content": "ignored"}]) for source in sources}}}


def _assemble(plan, signal=None, *, statuses=None, inputs=None, observations=None, payload=None):
    statuses = statuses or {}
    return assemble_luxian_0609_runtime_shadow_inputs(plan=plan, evidence_payload=_payload(plan, statuses=statuses) if payload is None else payload, source_query_observations=_observations(plan, statuses=statuses) if observations is None else observations, extraction_inputs=_inputs(plan, signal, statuses=statuses) if inputs is None else inputs, assembler_schema_version="assembler-v1", assembler_policy_version="policy-v1", created_at=CREATED)


def test_zero_plan_does_not_read_downstream_inputs():
    assembly = assemble_luxian_0609_runtime_shadow_inputs(plan=_plan(), evidence_payload=Explosive(), source_query_observations=Explosive(), extraction_inputs=Explosive(), assembler_schema_version="assembler-v1", assembler_policy_version="policy-v1", created_at=CREATED)
    assert assembly.disposition == "skipped_no_effective_rules" and assembly.summary_dict()["llm_total_tokens"] == 0


def test_required_pairs_are_trigger_derived_not_targets_and_032_has_no_order_pair():
    assembly = _assemble(_plan("LX0609-032"))
    assert {(item.fact_type, item.source_key) for item in assembly.deterministic_coverage_outcomes} == {("current_visit_surgery_confirmed", "surgery_application"), ("current_visit_surgery_confirmed", "surgery_record")}
    assert "surgery_safecheck_record" not in {item.source_key for item in assembly.deterministic_coverage_outcomes}


def test_signal_maps_to_pair_ref_and_safe_outcome():
    plan = _plan("LX0609-030")
    signal = _signal()
    assembly = _assemble(plan, signal)
    assert assembly.fact_pairs[0].pair_ref == signal.signal_ref
    outcome = next(item for item in assembly.deterministic_coverage_outcomes if item.source_key == "surgery_record")
    assert outcome.produced_pair_refs == (signal.signal_ref,)
    assert "ignored" not in repr(assembly) + str(assembly.safe_to_dict())


@pytest.mark.parametrize("event_status", ["planned", "cancelled"])
def test_invalid_surgery_signal_event_is_rejected(event_status):
    with pytest.raises(ValueError):
        _signal(event_status=event_status)


def test_order_signal_allows_ordered_and_source_requirement_blocks_cross_source():
    plan = _plan("LX0609-030")
    assembly = _assemble(plan, _signal("current_visit_surgery_order_confirmed", "inpat_nondrug_order", "ordered"))
    assert assembly.summary_dict()["fact_count"] == 1
    with pytest.raises(ValueError, match="signal pair"):
        RuntimePairExtractionInput("current_visit_surgery_order_confirmed", "inpat_nondrug_order", "complete", "extractor-v1", "mapping-v1", 1, (_signal(),))


@pytest.mark.parametrize("status", ["empty", "unavailable", "error"])
def test_source_status_truth_table(status):
    plan = _plan("LX0609-030")
    assembly = _assemble(plan, statuses={"surgery_record": status})
    assert assembly.summary_dict()["fact_count"] == 0


@pytest.mark.parametrize("status,state,reason,error", [("empty", "not_run", "", ""), ("unavailable", "not_run", "source_unavailable", "bad"), ("error", "not_run", "source_query_error", "bad")])
def test_empty_and_query_boundaries_reject_late_failure_combinations(status, state, reason, error):
    plan = _plan("LX0609-030")
    values = list(_inputs(plan, statuses={"surgery_record": status}))
    index = next(index for index, item in enumerate(values) if item.source_key == "surgery_record")
    item = values[index]
    values[index] = RuntimePairExtractionInput(item.fact_type, item.source_key, state, "extractor-v1", "mapping-v1", 0, (), reason, error)
    with pytest.raises(ValueError):
        _assemble(plan, statuses={"surgery_record": status}, inputs=tuple(values))


def test_available_count_and_partial_truth_are_fail_closed():
    plan = _plan("LX0609-030")
    values = list(_inputs(plan))
    index = next(index for index, item in enumerate(values) if item.source_key == "surgery_record")
    values[index] = RuntimePairExtractionInput(values[index].fact_type, values[index].source_key, "complete", "extractor-v1", "mapping-v1", 0, ())
    with pytest.raises(ValueError, match="complete extraction"):
        _assemble(plan, inputs=tuple(values))


def test_scope_and_duplicate_input_reject_without_payload_inference():
    plan = _plan("LX0609-030")
    observations = _observations(plan)[:-1]
    with pytest.raises(ValueError, match="source observations"):
        _assemble(plan, observations=observations)
    values = _inputs(plan)
    with pytest.raises(ValueError, match="trigger requirements"):
        _assemble(plan, inputs=values + values[:1])


def test_safe_identity_created_at_and_mutation_boundary():
    assembly = _assemble(_plan("LX0609-030"), _signal())
    data = assembly.safe_to_dict(); data["facts"].clear()
    assert assembly.summary_dict()["fact_count"] == 1
    assert assembly.fingerprint() == assemble_luxian_0609_runtime_shadow_inputs(plan=_plan("LX0609-030"), evidence_payload=_payload(_plan("LX0609-030")), source_query_observations=_observations(_plan("LX0609-030")), extraction_inputs=_inputs(_plan("LX0609-030"), _signal()), assembler_schema_version="assembler-v1", assembler_policy_version="policy-v1", created_at="2026-07-13T18:00:00+08:00").fingerprint()


def test_real_orch_accepts_assembled_performed_signal():
    plan = _plan("LX0609-030")
    payload = _payload(plan)
    assembly = _assemble(plan, _signal())
    report = build_luxian_0609_shadow_execution(visit_ref=VISIT, selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={VISIT: ["LX0609-030"]}, evidence_payload=payload, source_query_observations=assembly.source_query_observations, fact_pairs=assembly.fact_pairs, deterministic_coverage_outcomes=assembly.deterministic_coverage_outcomes, redaction_terms=(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    assert report.results[0].final_state.value == "compliant"


@pytest.mark.parametrize("status,expected", [("unavailable", "data_gap"), ("error", "technical_error")])
def test_real_orch_target_unavailable_and_error(status, expected):
    plan = _plan("LX0609-030")
    assembly = _assemble(plan, _signal("current_visit_surgery_order_confirmed", "inpat_nondrug_order", "ordered", "order-" + status), statuses={"surgery_record": status})
    report = build_luxian_0609_shadow_execution(visit_ref=VISIT, selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={VISIT: ["LX0609-030"]}, evidence_payload=_payload(plan, statuses={"surgery_record": status}), source_query_observations=assembly.source_query_observations, fact_pairs=assembly.fact_pairs, deterministic_coverage_outcomes=assembly.deterministic_coverage_outcomes, redaction_terms=(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    assert report.results[0].final_state.value == expected


def test_public_assembly_rejects_forged_nested_quote_or_trace():
    assembly = _assemble(_plan("LX0609-030"), _signal())
    pair = assembly.fact_pairs[0]
    forged = replace(pair, legacy_fact=replace(pair.legacy_fact, quote="SECRET_RAW_QUOTE", trace={"prompt": "SECRET"}))
    with pytest.raises(ValueError, match="assembly fact pair"):
        replace(assembly, fact_pairs=(forged,))


@pytest.mark.parametrize("marker", ["13800138000", "11010519491231002X", "Bearer_secret", "patient_name", "raw_text"])
def test_signal_sensitive_metadata_rejects_without_echo(marker):
    with pytest.raises(ValueError) as error:
        RuntimeStructuredFactSignal("a" * 64, marker, "surgery_record", "performed", "b" * 64, "runtime_structured", "extractor-v1", "mapping-v1")
    assert marker not in str(error.value)


def test_top_level_generator_and_subclass_reject_after_nonzero_plan():
    plan = _plan("LX0609-030")
    with pytest.raises(TypeError):
        assemble_luxian_0609_runtime_shadow_inputs(plan=plan, evidence_payload=_payload(plan), source_query_observations=(item for item in _observations(plan)), extraction_inputs=_inputs(plan), assembler_schema_version="assembler-v1", assembler_policy_version="policy-v1", created_at=CREATED)
    class Inputs(list): pass
    with pytest.raises(TypeError):
        _assemble(plan, inputs=Inputs(_inputs(plan)))
