from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.shadow_execution import FactCoverageOutcomeInput, ShadowExecutionReport, build_luxian_0609_shadow_execution
from app.services.luxian_0609 import shadow_execution as module
from app.services.luxian_0609.source_manifest_builder import SourceQueryObservation
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.result_aggregator import AggregatedRuleResult
from app.services.luxian_0609.shadow_fact_bundle import FactShadowPairInput
from app.services.luxian_0609.legacy_fact_adapter import LegacyFactV2Mapping
from app.services.luxian_0609_fact_extraction import Luxian0609Fact
import hashlib

CREATED = "2026-07-12T16:00:00+08:00"


class Explosive:
    def __iter__(self): raise AssertionError("downstream input read")
    def __len__(self): raise AssertionError("downstream input read")


def _zero(**overrides):
    values = dict(visit_ref="visit-orch-001", selected_rule_ids=[], scoped_customer_rule_ids=[], record_rule_map={}, evidence_payload=Explosive(), source_query_observations=Explosive(), fact_pairs=Explosive(), deterministic_coverage_outcomes=Explosive(), redaction_terms=Explosive(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    values.update(overrides)
    return build_luxian_0609_shadow_execution(**values)


def _real_030_no_fact_inputs():
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order"), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record"))
    return dict(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload={"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}, source_query_observations=observations, fact_pairs=(), deterministic_coverage_outcomes=outcomes, redaction_terms=())


def _outcome(fact_type, source_key, *, state="complete", processed=1, refs=(), reason_code="", error_code=""):
    return FactCoverageOutcomeInput(fact_type, source_key, state, "extractor-v1", "mapping-v1", processed, tuple(refs), reason_code, error_code)


def _performed_pair(label="pair-probe"):
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_confirmed", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-safe", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    return FactShadowPairInput(pair_ref=hashlib.sha256(label.encode()).hexdigest(), legacy_fact=legacy, mapping=mapping)


def test_zero_scope_short_circuits_before_every_downstream_input():
    report = _zero()
    assert report.disposition == "skipped_no_effective_rules"
    assert report.planned_rule_ids == report.results == ()
    assert report.stage_order == ("planner",) and report.stage_fingerprints[0][0] == "planner"
    assert report.summary_dict()["expected_llm_call_count"] == report.summary_dict()["llm_total_tokens"] == 0
    assert all(report.summary_dict()[f"{state}_count"] == 0 for state in ("compliant", "non_compliant", "not_applicable", "data_gap", "technical_error", "evaluation_unknown"))


@pytest.mark.parametrize("field", ["selected_rule_ids", "scoped_customer_rule_ids"])
def test_zero_scope_from_scope_intersection(field):
    values = {field: ["LX0609-030"]}
    assert _zero(**values).disposition == "skipped_no_effective_rules"


def test_safe_report_constructor_identity_and_privacy():
    report = _zero()
    assert report.fingerprint() == replace(report, created_at="2026-07-13T16:00:00+08:00").fingerprint()
    assert not any(name in vars(report) for name in ("plan", "manifest", "bundle", "coverage", "gate", "finding", "aggregation"))
    assert "quote" not in repr(report) + str(asdict(report)) + report.canonical_json()
    with pytest.raises(ValueError):
        ShadowExecutionReport("execution-v1", "policy-v1", "package-v1", "visit-orch-001", "completed", (), (), (), (), CREATED)
    payload = report.to_dict(); payload["planned_rule_ids"].append("LX0609-030")
    assert report.planned_rule_ids == ()


@pytest.mark.parametrize("marker", ["full_text", "sk-secret", "prompt-v1", "13800138000"])
def test_public_execution_metadata_rejects_sensitive_values(marker):
    with pytest.raises(ValueError) as error:
        ShadowExecutionReport(marker, "policy-v1", "package-v1", "visit-orch-001", "skipped_no_effective_rules", (), ("planner",), (("planner", "a" * 64),), (), CREATED)
    assert marker not in str(error.value)


def test_direct_constructor_rejects_forged_topologies():
    with pytest.raises(ValueError): ShadowExecutionReport("execution-v1", "policy-v1", "package-v1", "visit-orch-001", "completed", (), module.FULL_STAGE_ORDER, (), (), CREATED)
    with pytest.raises(ValueError): ShadowExecutionReport("execution-v1", "policy-v1", "package-v1", "visit-orch-001", "completed", ("LX0609-030",), module.FULL_STAGE_ORDER, (("evil", "a" * 64),), (), CREATED)


def test_source_scope_requires_concrete_exact_observations_after_nonzero_plan():
    with pytest.raises(TypeError, match="concrete"):
        _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]})


@pytest.mark.parametrize("observations", [(), (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="extra_source", query_status="available", query_version="query-v1")), (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="available", query_version="query-v1"))])
def test_nonzero_source_scope_missing_extra_or_duplicate_rejects(observations):
    with pytest.raises(ValueError, match="source observations"):
        _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload={}, source_query_observations=observations, fact_pairs=(), deterministic_coverage_outcomes=(), redaction_terms=())


def test_nonzero_stages_run_once_in_fixed_order(monkeypatch):
    calls = []
    class Value:
        def __init__(self, name): self.name = name
        def fingerprint(self): return ({"planner": "a", "manifest": "b", "bundle": "c", "coverage": "d", "gate": "e", "finding": "f", "aggregation": "0"}[self.name] * 64)
        items = ()
    class Rule:
        rule_id = "LX0609-030"
        required_source_keys = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    class Plan(Value):
        visit_ref = "visit-orch-001"
        planned_rules = (Rule(),)
    plan = Plan("planner")
    def stage(name, value):
        def build(*args, **kwargs): calls.append(name); return value
        return build
    monkeypatch.setattr(module.planner, "build_luxian_0609_shadow_plan", stage("planner", plan))
    monkeypatch.setattr(module.manifest_builder, "build_luxian_0609_source_manifest_shadow", stage("manifest", Value("manifest")))
    monkeypatch.setattr(module.bundle, "build_luxian_0609_fact_shadow_bundle", stage("bundle", Value("bundle")))
    monkeypatch.setattr(module.coverage, "build_luxian_0609_fact_coverage_shadow", stage("coverage", Value("coverage")))
    monkeypatch.setattr(module.gate, "build_luxian_0609_deterministic_gate_shadow", stage("gate", Value("gate")))
    monkeypatch.setattr(module.rules, "build_luxian_0609_programmatic_findings_shadow", stage("finding", Value("finding")))
    aggregate = Value("aggregation"); aggregate.results = (AggregatedRuleResult("LX0609-030", "trigger_absent", "not_applicable"),)
    monkeypatch.setattr(module.aggregator, "aggregate_luxian_0609_programmatic_findings_shadow", stage("aggregation", aggregate))
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status=QueryStatus.AVAILABLE, query_version="query-v1") for key in Rule.required_source_keys)
    values = dict(visit_ref="visit-orch-001", selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload={}, source_query_observations=observations, fact_pairs=(), deterministic_coverage_outcomes=(), redaction_terms=(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    report = build_luxian_0609_shadow_execution(**values)
    assert calls == ["planner", "manifest", "bundle", "coverage", "gate", "finding", "aggregation"]
    assert report.disposition == "completed" and report.results[0].final_state.value == "not_applicable"


def test_real_nonzero_030_chain_returns_safe_not_applicable_result():
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order"), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record"))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.disposition == "completed"
    assert report.results[0].final_state.value == "not_applicable"
    assert report.summary_dict()["not_applicable_count"] == 1


def test_real_nonzero_030_matched_target_present_is_compliant(monkeypatch):
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_confirmed", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-2", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-compliant").hexdigest(), legacy_fact=legacy, mapping=mapping)
    captured = {}
    original_bundle = module.bundle.build_luxian_0609_fact_shadow_bundle
    original_coverage = module.coverage.build_luxian_0609_fact_coverage_shadow
    def capture_bundle(*args, **kwargs):
        value = original_bundle(*args, **kwargs)
        captured["fact_id"] = value.items[0].fact.fact_id
        return value
    def capture_coverage(*args, **kwargs):
        captured["coverage_fact_ids"] = tuple(item.produced_fact_ids for item in kwargs["observations"])
        return original_coverage(*args, **kwargs)
    monkeypatch.setattr(module.bundle, "build_luxian_0609_fact_shadow_bundle", capture_bundle)
    monkeypatch.setattr(module.coverage, "build_luxian_0609_fact_coverage_shadow", capture_coverage)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order"), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", refs=(pair.pair_ref,)))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.results[0].final_state.value == "compliant"
    assert captured["coverage_fact_ids"][-1] == (captured["fact_id"],)


def test_real_nonzero_030_order_trigger_target_empty_is_non_compliant():
    observations = (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="empty", query_version="query-v1"))
    payload = {"programmatic_timeline": {"documents": {"inpat_nondrug_order": [{"content": "safe"}], "surgery_application": [{"content": "safe"}]}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_order_confirmed", family="surgery_anesthesia", source_document_type="医嘱", source_document_id="order-1", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="inpat_nondrug_order", normalized_value={"ordered": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="ordered", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-empty").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order", refs=(pair.pair_ref,)), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", processed=0))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.results[0].final_state.value == "non_compliant"


def test_real_nonzero_030_order_trigger_target_unavailable_is_data_gap():
    observations = (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="unavailable", query_version="query-v1", reason_code="source_paused"))
    payload = {"programmatic_timeline": {"documents": {"inpat_nondrug_order": [{"content": "safe"}], "surgery_application": [{"content": "safe"}]}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_order_confirmed", family="surgery_anesthesia", source_document_type="医嘱", source_document_id="order-2", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="inpat_nondrug_order", normalized_value={"ordered": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="ordered", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-gap").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order", refs=(pair.pair_ref,)), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", state="not_run", processed=0, reason_code="source_unavailable"))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.results[0].final_state.value == "data_gap"


def test_real_nonzero_030_order_trigger_target_error_is_technical_error():
    observations = (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="error", query_version="query-v1", error_code="source_failure"))
    payload = {"programmatic_timeline": {"documents": {"inpat_nondrug_order": [{"content": "safe"}], "surgery_application": [{"content": "safe"}]}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_order_confirmed", family="surgery_anesthesia", source_document_type="医嘱", source_document_id="order-error", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="inpat_nondrug_order", normalized_value={"ordered": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="ordered", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-error").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order", refs=(pair.pair_ref,)), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", state="not_run", processed=0, reason_code="source_query_error"))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.results[0].final_state.value == "technical_error"


def test_real_nonzero_030_claimed_semantic_conflict_is_evaluation_unknown():
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_confirmed", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-conflict", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="negated", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-conflict").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order"), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", refs=(pair.pair_ref,)))
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.results[0].final_state.value == "evaluation_unknown"


def test_real_nonzero_032_is_standalone_and_compliant():
    sources = ("surgery_application", "surgery_record", "surgery_safecheck_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_confirmed", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-32", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-32").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", refs=(pair.pair_ref,)))
    report = _zero(selected_rule_ids=["LX0609-032"], scoped_customer_rule_ids=["LX0609-032"], record_rule_map={"visit-orch-001": ["LX0609-032"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert tuple(result.rule_id for result in report.results) == ("LX0609-032",)
    assert report.results[0].final_state.value == "compliant"


def test_real_nonzero_029_single_scope_is_non_compliant_only():
    observations = (SourceQueryObservation.create(source_key="inpat_nondrug_order", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_application", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="surgery_record", query_status="available", query_version="query-v1"), SourceQueryObservation.create(source_key="presurg_summary", query_status="empty", query_version="query-v1"))
    payload = {"programmatic_timeline": {"documents": {"inpat_nondrug_order": [{"content": "safe"}], "surgery_application": [{"content": "safe"}], "surgery_record": [{"content": "safe"}]}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_order_confirmed", family="surgery_anesthesia", source_document_type="医嘱", source_document_id="order-29", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="inpat_nondrug_order", normalized_value={"ordered": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="ordered", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-29").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order", refs=(pair.pair_ref,)), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record"))
    report = _zero(selected_rule_ids=["LX0609-029"], scoped_customer_rule_ids=["LX0609-029"], record_rule_map={"visit-orch-001": ["LX0609-029"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert tuple(result.rule_id for result in report.results) == ("LX0609-029",)
    assert report.results[0].final_state.value == "non_compliant"


def test_real_multi_029_030_032_stable_order_and_counts():
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record", "presurg_summary", "surgery_safecheck_record")
    statuses = {"presurg_summary": "empty"}
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status=statuses.get(key, "available"), query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources if key != "presurg_summary"}}}
    legacy = Luxian0609Fact(fact_type="current_visit_surgery_confirmed", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-multi", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair-multi").hexdigest(), legacy_fact=legacy, mapping=mapping)
    outcomes = (_outcome("current_visit_surgery_order_confirmed", "inpat_nondrug_order"), _outcome("current_visit_surgery_confirmed", "surgery_application"), _outcome("current_visit_surgery_confirmed", "surgery_record", refs=(pair.pair_ref,)))
    report = _zero(selected_rule_ids=["LX0609-029", "LX0609-030", "LX0609-032"], scoped_customer_rule_ids=["LX0609-029", "LX0609-030", "LX0609-032"], record_rule_map={"visit-orch-001": ["LX0609-029", "LX0609-030", "LX0609-032"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), deterministic_coverage_outcomes=outcomes, redaction_terms=())
    assert report.planned_rule_ids == ("LX0609-029", "LX0609-030", "LX0609-032")
    assert tuple(item.rule_id for item in report.results) == report.planned_rule_ids
    assert tuple(item.final_state.value for item in report.results) == ("non_compliant", "compliant", "compliant")
    assert report.summary_dict()["non_compliant_count"] == 1 and report.summary_dict()["compliant_count"] == 2
    assert tuple(name for name, _ in report.stage_fingerprints) == module.FULL_STAGE_ORDER


def test_real_builder_wrappers_execute_each_stage_once(monkeypatch):
    calls = []
    state = {"inside_aggregation": False}
    stages = (("planner", module.planner, "build_luxian_0609_shadow_plan"), ("manifest", module.manifest_builder, "build_luxian_0609_source_manifest_shadow"), ("bundle", module.bundle, "build_luxian_0609_fact_shadow_bundle"), ("coverage", module.coverage, "build_luxian_0609_fact_coverage_shadow"), ("gate", module.gate, "build_luxian_0609_deterministic_gate_shadow"), ("finding", module.rules, "build_luxian_0609_programmatic_findings_shadow"), ("aggregation", module.aggregator, "aggregate_luxian_0609_programmatic_findings_shadow"))
    for name, owner, attr in stages:
        original = getattr(owner, attr)
        def wrapper(*args, _original=original, _name=name, **kwargs):
            if _name == "finding" and state["inside_aggregation"]:
                return _original(*args, **kwargs)
            calls.append(_name)
            if _name == "aggregation":
                state["inside_aggregation"] = True
                try: return _original(*args, **kwargs)
                finally: state["inside_aggregation"] = False
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, attr, wrapper)
    assert _zero(**_real_030_no_fact_inputs()).disposition == "completed"
    assert calls == list(module.FULL_STAGE_ORDER)


@pytest.mark.parametrize("failed_stage", ["manifest", "bundle", "coverage", "gate", "finding", "aggregation"])
def test_real_builder_failure_stops_later_stages(monkeypatch, failed_stage):
    calls = []
    stages = (("planner", module.planner, "build_luxian_0609_shadow_plan"), ("manifest", module.manifest_builder, "build_luxian_0609_source_manifest_shadow"), ("bundle", module.bundle, "build_luxian_0609_fact_shadow_bundle"), ("coverage", module.coverage, "build_luxian_0609_fact_coverage_shadow"), ("gate", module.gate, "build_luxian_0609_deterministic_gate_shadow"), ("finding", module.rules, "build_luxian_0609_programmatic_findings_shadow"), ("aggregation", module.aggregator, "aggregate_luxian_0609_programmatic_findings_shadow"))
    for name, owner, attr in stages:
        original = getattr(owner, attr)
        def wrapper(*args, _original=original, _name=name, **kwargs):
            calls.append(_name)
            if _name == failed_stage: raise RuntimeError("stage_failure")
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, attr, wrapper)
    with pytest.raises(RuntimeError, match="stage_failure"):
        _zero(**_real_030_no_fact_inputs())
    index = list(module.FULL_STAGE_ORDER).index(failed_stage)
    assert calls == list(module.FULL_STAGE_ORDER[:index + 1])


@pytest.mark.parametrize("refs,processed", [(("a" * 64, "a" * 64), 1), (("a" * 64,), 0)])
def test_coverage_outcome_rejects_duplicate_or_unprocessed_pair_references(refs, processed):
    with pytest.raises(ValueError):
        _outcome("current_visit_surgery_confirmed", "surgery_record", refs=refs, processed=processed)


@pytest.mark.parametrize("kind", ["unknown", "duplicate_claim", "wrong_fact_type", "wrong_source"])
def test_pair_reference_mapping_is_fail_closed(kind):
    values = _real_030_no_fact_inputs()
    pair = _performed_pair(kind)
    values["fact_pairs"] = (pair,)
    outcomes = list(values["deterministic_coverage_outcomes"])
    if kind == "unknown":
        outcomes[-1] = _outcome("current_visit_surgery_confirmed", "surgery_record", refs=("b" * 64,))
    elif kind == "duplicate_claim":
        outcomes[1] = _outcome("current_visit_surgery_confirmed", "surgery_application", refs=(pair.pair_ref,))
        outcomes[2] = _outcome("current_visit_surgery_confirmed", "surgery_record", refs=(pair.pair_ref,))
    elif kind == "wrong_fact_type":
        outcomes[-1] = _outcome("current_visit_surgery_order_confirmed", "surgery_record", refs=(pair.pair_ref,))
    else:
        outcomes[-1] = _outcome("current_visit_surgery_confirmed", "surgery_application", refs=(pair.pair_ref,))
    values["deterministic_coverage_outcomes"] = tuple(outcomes)
    with pytest.raises(ValueError, match="coverage pair"):
        _zero(**values)


class OutcomeList(list):
    pass


@pytest.mark.parametrize("outcomes", ["bare", b"binary", (item for item in ()), OutcomeList(), ["wrong-item"]])
def test_nonzero_outcomes_require_exact_concrete_current_values(outcomes):
    values = _real_030_no_fact_inputs()
    values["deterministic_coverage_outcomes"] = outcomes
    with pytest.raises(TypeError, match="concrete|invalid values"):
        _zero(**values)


def test_outcome_budget_rejects_max_plus_one_before_bundle_construction():
    values = _real_030_no_fact_inputs()
    values["deterministic_coverage_outcomes"] = tuple(
        _outcome("current_visit_surgery_confirmed", "surgery_record")
        for _ in range(module.MAX_COVERAGE_OUTCOMES + 1)
    )
    with pytest.raises(TypeError, match="invalid values"):
        _zero(**values)


def test_outcome_order_is_canonical_and_does_not_change_execution_identity():
    values = _real_030_no_fact_inputs()
    first = _zero(**values)
    values["deterministic_coverage_outcomes"] = tuple(reversed(values["deterministic_coverage_outcomes"]))
    second = _zero(**values)
    assert first.fingerprint() == second.fingerprint()
