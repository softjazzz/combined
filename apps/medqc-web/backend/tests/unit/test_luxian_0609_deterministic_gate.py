from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.luxian_0609.deterministic_gate import (
    GateReadiness,
    TargetResolution,
    TriggerResolution,
    build_luxian_0609_deterministic_gate_shadow,
)
from app.services.luxian_0609.fact_coverage import ExtractionCoverageState
from test_luxian_0609_fact_coverage import _build, _bundle, _fact, _manifest, _observation, _pairs, _plan


def _gate(*, plan=None, manifest=None, bundle=None, coverage=None):
    plan = _plan(("LX0609-032",)) if plan is None else plan
    manifest = _manifest() if manifest is None else manifest
    bundle = _bundle(manifest) if bundle is None else bundle
    coverage = _build(plan=plan, manifest=manifest, bundle=bundle) if coverage is None else coverage
    return build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=bundle, coverage=coverage, gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at="2026-07-12T12:00:00+08:00")


def test_zero_and_absent_complete_gate_are_internal_only() -> None:
    zero_plan = _plan(())
    manifest = _manifest()
    report = _gate(plan=zero_plan, manifest=manifest, bundle=_bundle(manifest), coverage=_build(plan=zero_plan, manifest=manifest, bundle=_bundle(manifest), observations=()))
    assert report.decisions == ()
    absent = _gate()
    assert absent.decisions[0].trigger_resolution is TriggerResolution.ABSENT_COMPLETE
    assert absent.decisions[0].readiness is GateReadiness.NOT_TRIGGERED
    assert "compliant" not in absent.canonical_json()


def test_claimed_exact_fact_matches_and_unclaimed_fact_is_ignored() -> None:
    plan = _plan(("LX0609-030",)); manifest = _manifest(); pair = _pairs(plan)[0]
    fact = _fact(source_key=pair[1], fact_type=pair[0]); bundle = _bundle(manifest, (fact,))
    unclaimed = _build(plan=plan, manifest=manifest, bundle=bundle)
    assert _gate(plan=plan, manifest=manifest, bundle=bundle, coverage=unclaimed).decisions[0].trigger_resolution is TriggerResolution.ABSENT_COMPLETE
    coverage = _build(plan=plan, manifest=manifest, bundle=bundle, observations=(_observation(pair, fact_ids=(fact.fact_id,)), _observation(_pairs(plan)[1]), _observation(_pairs(plan)[2])))
    decision = _gate(plan=plan, manifest=manifest, bundle=bundle, coverage=coverage).decisions[0]
    assert decision.trigger_resolution is TriggerResolution.MATCHED
    assert decision.target_resolution is TargetResolution.PRESENT
    assert decision.readiness is GateReadiness.READY


def test_semantic_conflict_and_target_matrix() -> None:
    plan = _plan(("LX0609-032",)); manifest = _manifest(); pair = _pairs(plan)[0]
    fact = _fact(source_key=pair[1], fact_type=pair[0]); object.__setattr__(fact, "assertion", type(fact.assertion).NEGATED)
    bundle = _bundle(manifest, (fact,))
    coverage = _build(plan=plan, manifest=manifest, bundle=bundle, observations=(_observation(pair, fact_ids=(fact.fact_id,)), _observation(_pairs(plan)[1])))
    assert _gate(plan=plan, manifest=manifest, bundle=bundle, coverage=coverage).decisions[0].trigger_resolution is TriggerResolution.SEMANTIC_CONFLICT


def test_coverage_precedence_and_safe_object_graph() -> None:
    plan = _plan(("LX0609-032",)); manifest = _manifest(); pairs = _pairs(plan)
    coverage = _build(plan=plan, manifest=manifest, observations=(
        _observation(pairs[0], state=ExtractionCoverageState.PARTIAL, processed=1, reason="partial_budget_limit"),
        _observation(pairs[1], state=ExtractionCoverageState.ERROR, processed=1, reason="extraction_error", error="extractor_timeout"),
    ))
    report = _gate(plan=plan, manifest=manifest, coverage=coverage)
    assert report.decisions[0].trigger_resolution is TriggerResolution.COVERAGE_ERROR
    assert not any(hasattr(report, name) for name in ("plan", "manifest", "bundle", "coverage"))
    with pytest.raises(ValueError):
        replace(report, decisions=(report.decisions[0], report.decisions[0]))
