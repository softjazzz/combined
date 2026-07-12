from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.shadow_execution import ShadowExecutionReport, build_luxian_0609_shadow_execution
from app.services.luxian_0609 import shadow_execution as module
from app.services.luxian_0609.source_manifest_builder import SourceQueryObservation
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.result_aggregator import AggregatedRuleResult
from app.services.luxian_0609.source_manifest_builder import build_luxian_0609_source_manifest_shadow
from app.services.luxian_0609.shadow_fact_bundle import FactShadowPairInput, build_luxian_0609_fact_shadow_bundle
from app.services.luxian_0609.legacy_fact_adapter import LegacyFactV2Mapping
from app.services.luxian_0609_fact_extraction import Luxian0609Fact
from app.services.luxian_0609.fact_coverage import FactCoverageObservation
import hashlib

CREATED = "2026-07-12T16:00:00+08:00"


class Explosive:
    def __iter__(self): raise AssertionError("downstream input read")
    def __len__(self): raise AssertionError("downstream input read")


def _zero(**overrides):
    values = dict(visit_ref="visit-orch-001", selected_rule_ids=[], scoped_customer_rule_ids=[], record_rule_map={}, evidence_payload=Explosive(), source_query_observations=Explosive(), fact_pairs=Explosive(), coverage_observations=Explosive(), redaction_terms=Explosive(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    values.update(overrides)
    return build_luxian_0609_shadow_execution(**values)


def test_zero_scope_short_circuits_before_every_downstream_input():
    report = _zero()
    assert report.disposition == "skipped_no_effective_rules"
    assert report.planned_rule_ids == report.results == report.stage_order == ()
    assert report.summary_dict()["expected_llm_call_count"] == report.summary_dict()["llm_total_tokens"] == 0


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


def test_source_scope_requires_concrete_exact_observations_after_nonzero_plan():
    with pytest.raises(TypeError, match="concrete"):
        _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]})


def test_nonzero_stages_run_once_in_fixed_order(monkeypatch):
    calls = []
    class Value:
        def __init__(self, name): self.name = name
        def fingerprint(self): return ({"planner": "a", "manifest": "b", "bundle": "c", "coverage": "d", "gate": "e", "finding": "f", "aggregation": "0"}[self.name] * 64)
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
    values = dict(visit_ref="visit-orch-001", selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload={}, source_query_observations=observations, fact_pairs=(), coverage_observations=(), redaction_terms=(), planner_schema_version="planner-v1", rule_plan_version="slice-v1", manifest_schema_version="manifest-v1", bundle_schema_version="bundle-v1", coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", gate_schema_version="gate-v1", gate_policy_version="policy-v1", finding_schema_version="finding-v1", finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", execution_schema_version="execution-v1", execution_policy_version="policy-v1", package_version="package-v1", planner_created_at=CREATED, manifest_created_at=CREATED, bundle_created_at=CREATED, coverage_created_at=CREATED, gate_created_at=CREATED, finding_created_at=CREATED, aggregation_created_at=CREATED, created_at=CREATED)
    report = build_luxian_0609_shadow_execution(**values)
    assert calls == ["planner", "manifest", "bundle", "coverage", "gate", "finding", "aggregation"]
    assert report.disposition == "completed" and report.results[0].final_state.value == "not_applicable"


def test_real_nonzero_030_chain_returns_safe_not_applicable_result():
    sources = ("inpat_nondrug_order", "surgery_application", "surgery_record")
    observations = tuple(SourceQueryObservation.create(source_key=key, query_status="available", query_version="query-v1") for key in sources)
    payload = {"programmatic_timeline": {"documents": {key: [{"content": "safe"}] for key in sources}}}
    legacy = Luxian0609Fact(fact_type="surgery_presence", family="surgery_anesthesia", source_document_type="手术记录", source_document_id="doc-1", record_time="", quote="safe", confidence=0.9, extractor="structured", trace={})
    mapping = LegacyFactV2Mapping(source_key="surgery_record", normalized_value={"present": True}, trigger_scope="current_visit", current_visit_relevance="relevant", assertion="affirmed", assertion_context="current_narrative", event_status="performed", extractor_version="policy-v1", record_time_handling="absent", mapped_record_time=None, omit_reason_code="")
    pair = FactShadowPairInput(pair_ref=hashlib.sha256(b"pair").hexdigest(), legacy_fact=legacy, mapping=mapping)
    manifest = build_luxian_0609_source_manifest_shadow(visit_ref="visit-orch-001", evidence_payload=payload, observations=observations, manifest_schema_version="manifest-v1", created_at=CREATED)
    fact_bundle = build_luxian_0609_fact_shadow_bundle(visit_ref="visit-orch-001", manifest=manifest, paired_inputs=(pair,), bundle_schema_version="bundle-v1", created_at=CREATED, redaction_terms=())
    fact_id = fact_bundle.items[0].fact.fact_id
    coverage = (
        FactCoverageObservation("current_visit_surgery_order_confirmed", "inpat_nondrug_order", "complete", "extractor-v1", "mapping-v1", 1, ()),
        FactCoverageObservation("current_visit_surgery_confirmed", "surgery_application", "complete", "extractor-v1", "mapping-v1", 1, ()),
        FactCoverageObservation("current_visit_surgery_confirmed", "surgery_record", "complete", "extractor-v1", "mapping-v1", 1, ()),
    )
    report = _zero(selected_rule_ids=["LX0609-030"], scoped_customer_rule_ids=["LX0609-030"], record_rule_map={"visit-orch-001": ["LX0609-030"]}, evidence_payload=payload, source_query_observations=observations, fact_pairs=(pair,), coverage_observations=coverage, redaction_terms=())
    assert report.disposition == "completed"
    assert report.results[0].final_state.value == "not_applicable"
