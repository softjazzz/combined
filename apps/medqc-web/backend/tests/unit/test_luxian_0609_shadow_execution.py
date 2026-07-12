from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.shadow_execution import ShadowExecutionReport, build_luxian_0609_shadow_execution

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
