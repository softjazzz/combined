from __future__ import annotations

from dataclasses import replace
from dataclasses import asdict
import ast
import importlib
import json
from pathlib import Path

import pytest

from app.services.luxian_0609 import fact_coverage as coverage_module
from app.services.luxian_0609.fact_coverage import (
    ExtractionCoverageState,
    FactCoverageObservation,
    build_luxian_0609_fact_coverage_shadow,
)
from app.services.luxian_0609.fact_schema import (
    Assertion,
    AssertionContext,
    CurrentVisitRelevance,
    EventStatus,
    FactV2,
    TriggerScope,
)
from app.services.luxian_0609.planner import ShadowRulePlan, build_luxian_0609_shadow_plan
from app.services.luxian_0609.shadow_fact_bundle import FactShadowBundle, FactShadowBundleItem
from app.services.luxian_0609.source_manifest import DocumentManifest, QueryStatus, SourceManifestEntry


CREATED_AT = "2026-07-12T10:00:00+08:00"
VISIT_REF = "visit-coverage-001"
SNAPSHOT = "a" * 64
SOURCES = ("inpat_nondrug_order", "mr_surgery", "surgery_application", "surgery_record")


def _plan(rule_ids=("LX0609-029", "LX0609-030", "LX0609-032")):
    return build_luxian_0609_shadow_plan(
        visit_ref=VISIT_REF,
        selected_rule_ids=list(rule_ids),
        scoped_customer_rule_ids=list(rule_ids),
        record_rule_map={VISIT_REF: list(rule_ids)},
        planner_schema_version="planner-v1",
        rule_plan_version="slice-v1",
        created_at=CREATED_AT,
    )


def _manifest(statuses: dict[str, QueryStatus] | None = None) -> DocumentManifest:
    statuses = statuses or {source: QueryStatus.AVAILABLE for source in SOURCES}
    entries = []
    for index, source in enumerate(sorted(statuses)):
        status = statuses[source]
        entries.append(
            SourceManifestEntry.create(
                source_key=source,
                query_status=status,
                record_count=2 if status is QueryStatus.AVAILABLE else (0 if status is QueryStatus.EMPTY else None),
                query_version="query-v1",
                snapshot_ref="sha256:" + (str(index + 1) * 64),
                error_code="source_failure" if status is QueryStatus.ERROR else "",
                reason_code="source_paused" if status is QueryStatus.UNAVAILABLE else "",
            )
        )
    return DocumentManifest(
        manifest_schema_version="manifest-v1",
        visit_ref=VISIT_REF,
        source_snapshot_hash=SNAPSHOT,
        entries=tuple(entries),
        created_at=CREATED_AT,
    )


def _fact(*, source_key: str, fact_type: str, document_id: str = "doc-ref") -> FactV2:
    event_status = EventStatus.ORDERED if fact_type.endswith("order_confirmed") else EventStatus.PERFORMED
    return FactV2.create(
        visit_ref=VISIT_REF,
        family="surgery_anesthesia",
        fact_type=fact_type,
        normalized_value={"kind": "coverage_fixture"},
        trigger_scope=TriggerScope.CURRENT_VISIT,
        current_visit_relevance=CurrentVisitRelevance.RELEVANT,
        assertion=Assertion.AFFIRMED,
        assertion_context=AssertionContext.CURRENT_NARRATIVE,
        event_status=event_status,
        source_key=source_key,
        source_document_id=document_id,
        source_document_type="coverage_fixture",
        record_time=None,
        submit_time=None,
        update_time=None,
        quote="safe quote",
        redaction_terms=(),
        confidence=0.9,
        extractor="coverage_fixture",
        extractor_version="extractor-v1",
        fact_schema_version="fact-v2",
        source_snapshot_hash=SNAPSHOT,
        created_at=CREATED_AT,
        extensions={},
        known_upstream_fact_ids=(),
    )


def _bundle(manifest: DocumentManifest, facts: tuple[FactV2, ...] = ()) -> FactShadowBundle:
    return FactShadowBundle(
        bundle_schema_version="bundle-v1",
        visit_ref=VISIT_REF,
        manifest_fingerprint=manifest.fingerprint(),
        source_snapshot_hash=SNAPSHOT,
        items=tuple(
            FactShadowBundleItem(pair_ref=f"{index + 1:064x}", fact=fact)
            for index, fact in enumerate(facts)
        ),
        created_at=CREATED_AT,
    )


def _pairs(plan):
    return tuple(
        sorted(
            {
                (requirement.fact_type, source)
                for rule in plan.planned_rules
                for requirement in rule.trigger_requirements
                for source in requirement.allowed_source_keys
            }
        )
    )


def _observation(
    pair: tuple[str, str],
    *,
    state: ExtractionCoverageState = ExtractionCoverageState.COMPLETE,
    processed: int = 2,
    fact_ids: tuple[str, ...] = (),
    reason: str = "",
    error: str = "",
) -> FactCoverageObservation:
    return FactCoverageObservation(
        fact_type=pair[0],
        source_key=pair[1],
        state=state,
        extractor_version="extractor-v1",
        mapping_policy_version="mapping-v1",
        processed_record_count=processed,
        produced_fact_ids=fact_ids,
        reason_code=reason,
        error_code=error,
    )


def _build(*, plan=None, manifest=None, bundle=None, observations=None):
    plan = _plan() if plan is None else plan
    manifest = _manifest() if manifest is None else manifest
    bundle = _bundle(manifest) if bundle is None else bundle
    observations = tuple(_observation(pair) for pair in _pairs(plan)) if observations is None else observations
    return build_luxian_0609_fact_coverage_shadow(
        plan=plan,
        manifest=manifest,
        bundle=bundle,
        observations=observations,
        coverage_schema_version="coverage-v1",
        coverage_policy_version="policy-v1",
        created_at=CREATED_AT,
    )


def test_pair_expansion_uses_trigger_requirements_not_query_union_or_target_source() -> None:
    plan_029 = _plan(("LX0609-029",))
    plan_032 = _plan(("LX0609-032",))
    assert _pairs(plan_029) == (
        ("current_visit_surgery_confirmed", "mr_surgery"),
        ("current_visit_surgery_confirmed", "surgery_application"),
        ("current_visit_surgery_confirmed", "surgery_record"),
        ("current_visit_surgery_order_confirmed", "inpat_nondrug_order"),
    )
    assert _pairs(plan_032) == (
        ("current_visit_surgery_confirmed", "mr_surgery"),
        ("current_visit_surgery_confirmed", "surgery_application"),
        ("current_visit_surgery_confirmed", "surgery_record"),
    )
    report = _build(plan=plan_029)
    assert [(item.fact_type, item.source_key) for item in report.required_pairs] == list(_pairs(plan_029))
    assert "presurg_summary" not in report.canonical_json()


def test_zero_rule_plan_requires_zero_observations_and_is_not_qc_state() -> None:
    plan = _plan(())
    manifest = _manifest()
    report = _build(plan=plan, manifest=manifest, bundle=_bundle(manifest), observations=())
    assert report.summary_dict() == {
        "all_required_pairs_complete": True,
        "complete_pair_count": 0,
        "error_pair_count": 0,
        "not_run_pair_count": 0,
        "partial_pair_count": 0,
        "required_pair_count": 0,
    }
    with pytest.raises(ValueError, match="exactly cover"):
        _build(plan=plan, manifest=manifest, bundle=_bundle(manifest), observations=(_observation(("current_visit_surgery_confirmed", "surgery_record")),))


def test_available_complete_zero_facts_is_distinct_from_partial_not_run_and_error() -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    pairs = _pairs(plan)
    complete = _build(plan=plan, manifest=manifest, observations=tuple(_observation(pair) for pair in pairs))
    assert complete.summary_dict()["complete_pair_count"] == 3
    partial = tuple(_observation(pair, state=ExtractionCoverageState.PARTIAL, processed=1, reason="partial_budget_limit") for pair in pairs)
    not_run = tuple(_observation(pair, state=ExtractionCoverageState.NOT_RUN, processed=0, reason="extractor_not_run") for pair in pairs)
    errors = tuple(_observation(pair, state=ExtractionCoverageState.ERROR, processed=0, reason="extraction_error", error="extractor_timeout") for pair in pairs)
    assert _build(plan=plan, manifest=manifest, observations=partial).summary_dict()["partial_pair_count"] == 3
    assert _build(plan=plan, manifest=manifest, observations=not_run).summary_dict()["not_run_pair_count"] == 3
    assert _build(plan=plan, manifest=manifest, observations=errors).summary_dict()["error_pair_count"] == 3


@pytest.mark.parametrize(
    ("query_status", "state", "processed", "reason", "error", "is_valid"),
    [
        (QueryStatus.AVAILABLE, ExtractionCoverageState.COMPLETE, 2, "", "", True),
        (QueryStatus.AVAILABLE, ExtractionCoverageState.PARTIAL, 1, "partial_budget_limit", "", True),
        (QueryStatus.AVAILABLE, ExtractionCoverageState.NOT_RUN, 0, "extractor_not_run", "", True),
        (QueryStatus.AVAILABLE, ExtractionCoverageState.ERROR, 1, "extraction_error", "extractor_timeout", True),
        (QueryStatus.AVAILABLE, ExtractionCoverageState.COMPLETE, 1, "", "", False),
        (QueryStatus.EMPTY, ExtractionCoverageState.COMPLETE, 0, "", "", True),
        (QueryStatus.EMPTY, ExtractionCoverageState.NOT_RUN, 0, "extractor_not_run", "", True),
        (QueryStatus.EMPTY, ExtractionCoverageState.PARTIAL, 0, "partial_budget_limit", "", False),
        (QueryStatus.UNAVAILABLE, ExtractionCoverageState.NOT_RUN, 0, "source_unavailable", "", True),
        (QueryStatus.UNAVAILABLE, ExtractionCoverageState.COMPLETE, 0, "", "", False),
        (QueryStatus.ERROR, ExtractionCoverageState.NOT_RUN, 0, "source_query_error", "", True),
        (QueryStatus.ERROR, ExtractionCoverageState.ERROR, 0, "extraction_error", "extractor_timeout", False),
    ],
)
def test_source_query_truth_table(query_status, state, processed, reason, error, is_valid) -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest({source: query_status for source in SOURCES})
    observations = tuple(_observation(pair, state=state, processed=processed, reason=reason, error=error) for pair in _pairs(plan))
    if is_valid:
        _build(plan=plan, manifest=manifest, bundle=_bundle(manifest), observations=observations)
    else:
        with pytest.raises(ValueError):
            _build(plan=plan, manifest=manifest, bundle=_bundle(manifest), observations=observations)


def test_observations_must_exactly_match_required_pairs() -> None:
    plan = _plan(("LX0609-032",))
    pairs = _pairs(plan)
    with pytest.raises(ValueError, match="exactly cover"):
        _build(plan=plan, observations=(_observation(pairs[0]),))
    with pytest.raises(ValueError, match="exactly cover"):
        _build(plan=plan, observations=(_observation(pairs[0]), _observation(pairs[0])))
    extra = _observation(("current_visit_surgery_order_confirmed", "inpat_nondrug_order"))
    with pytest.raises(ValueError, match="exactly cover"):
        _build(plan=plan, observations=tuple(_observation(pair) for pair in pairs) + (extra,))


def test_fact_refs_must_exist_match_pair_and_be_claimed_once() -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    facts = tuple(_fact(source_key=source, fact_type=fact_type) for fact_type, source in _pairs(plan))
    bundle = _bundle(manifest, facts)
    observations = tuple(_observation(pair, fact_ids=(fact.fact_id,)) for pair, fact in zip(_pairs(plan), facts))
    report = _build(plan=plan, manifest=manifest, bundle=bundle, observations=observations)
    assert all(item.observation.produced_fact_ids for item in report.items)
    missing = tuple(_observation(pair, fact_ids=("f" * 64,)) for pair in _pairs(plan))
    with pytest.raises(ValueError, match="does not match coverage pair"):
        _build(plan=plan, manifest=manifest, bundle=bundle, observations=missing)
    pairs = _pairs(plan)
    wrong = tuple(
        _observation(pair, fact_ids=(facts[1].fact_id,) if index == 0 else ())
        for index, pair in enumerate(pairs)
    )
    with pytest.raises(ValueError, match="does not match coverage pair"):
        _build(plan=plan, manifest=manifest, bundle=bundle, observations=wrong)
    claimed_twice = tuple(_observation(pair, fact_ids=(facts[0].fact_id,)) for pair in _pairs(plan))
    with pytest.raises(ValueError, match="does not match coverage pair|multiple"):
        _build(plan=plan, manifest=manifest, bundle=bundle, observations=claimed_twice)


def test_unrelated_bundle_facts_do_not_expand_or_leak_coverage_pairs() -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    related = _fact(source_key="surgery_record", fact_type="current_visit_surgery_confirmed")
    unrelated = _fact(source_key="inpat_nondrug_order", fact_type="unrelated_fact_type")
    bundle = _bundle(manifest, (related, unrelated))
    observations = tuple(
        _observation(pair, fact_ids=(related.fact_id,) if pair[1] == "surgery_record" else ())
        for pair in _pairs(plan)
    )
    report = _build(plan=plan, manifest=manifest, bundle=bundle, observations=observations)
    assert "unrelated_fact_type" not in report.canonical_json()
    assert unrelated.fact_id not in report.canonical_json()


def test_cross_value_object_consistency_and_concrete_observations_fail_closed() -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    bundle = _bundle(manifest)
    with pytest.raises(TypeError):
        _build(plan=plan, manifest=manifest, bundle=bundle, observations=(item for item in ()))
    with pytest.raises(ValueError, match="bundle manifest mismatch"):
        _build(plan=plan, manifest=manifest, bundle=replace(bundle, manifest_fingerprint="b" * 64))
    other_plan = build_luxian_0609_shadow_plan(
        visit_ref="other-visit",
        selected_rule_ids=["LX0609-032"],
        scoped_customer_rule_ids=["LX0609-032"],
        record_rule_map={"other-visit": ["LX0609-032"]},
        planner_schema_version="planner-v1",
        rule_plan_version="slice-v1",
        created_at=CREATED_AT,
    )
    with pytest.raises(ValueError, match="visit_ref mismatch"):
        _build(plan=other_plan, manifest=manifest, bundle=bundle)


def test_public_observation_boundary_and_defensive_output() -> None:
    with pytest.raises(TypeError):
        FactCoverageObservation("current_visit_surgery_confirmed", "surgery_record", "complete", "v", "p", 1, ["a" * 64])
    with pytest.raises(ValueError):
        FactCoverageObservation("current_visit_surgery_confirmed", "surgery_record", "compliant", "v", "p", 1, ())
    report = _build()
    original = report.canonical_json()
    output = report.to_dict()
    output["items"][0]["produced_fact_ids"].append("changed")
    output["required_pairs"].clear()
    assert report.canonical_json() == original


def test_direct_report_revalidates_exact_pairs_refs_and_bounded_collections(monkeypatch) -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    facts = tuple(_fact(source_key=source, fact_type=fact_type) for fact_type, source in _pairs(plan))
    report = _build(
        plan=plan,
        manifest=manifest,
        bundle=_bundle(manifest, facts),
        observations=tuple(_observation(pair, fact_ids=(fact.fact_id,)) for pair, fact in zip(_pairs(plan), facts)),
    )
    with pytest.raises(ValueError, match="exactly match"):
        replace(report, items=(report.items[0],))
    with pytest.raises(ValueError, match="not in bundle index"):
        replace(report, bundle_fact_index=())
    with pytest.raises(ValueError, match="source contexts"):
        replace(report, source_contexts=())
    monkeypatch.setattr(coverage_module, "MAX_COVERAGE_PAIRS", 2)
    with pytest.raises(ValueError, match="too many observations"):
        _build()
    monkeypatch.setattr(coverage_module, "MAX_FACT_REFS_PER_PAIR", 1)
    with pytest.raises(ValueError, match="too many produced_fact_ids"):
        _observation(_pairs(plan)[0], fact_ids=(facts[0].fact_id, facts[1].fact_id))


@pytest.mark.parametrize("state", [ExtractionCoverageState.PARTIAL, ExtractionCoverageState.ERROR])
def test_zero_processed_records_cannot_claim_produced_fact_ids(state) -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    fact = _fact(source_key="surgery_application", fact_type="current_visit_surgery_confirmed")
    app_pair = next(pair for pair in _pairs(plan) if pair[1] == "surgery_application")
    with pytest.raises(ValueError, match="produced facts require processed records"):
        _observation(
            app_pair,
            state=state,
            processed=0,
            fact_ids=(fact.fact_id,),
            reason="partial_budget_limit" if state is ExtractionCoverageState.PARTIAL else "extraction_error",
            error="extractor_timeout" if state is ExtractionCoverageState.ERROR else "",
        )
    observations = tuple(
        _observation(
            pair,
            state=state if pair == app_pair else ExtractionCoverageState.COMPLETE,
            processed=1 if pair == app_pair else 2,
            fact_ids=(fact.fact_id,) if pair == app_pair else (),
            reason=("partial_budget_limit" if state is ExtractionCoverageState.PARTIAL else "extraction_error") if pair == app_pair else "",
            error="extractor_timeout" if pair == app_pair and state is ExtractionCoverageState.ERROR else "",
        )
        for pair in _pairs(plan)
    )
    report = _build(plan=plan, manifest=manifest, bundle=_bundle(manifest, (fact,)), observations=observations)
    app_item = next(
        item
        for item in report.items
        if (item.observation.fact_type, item.observation.source_key) == app_pair
    )
    assert app_item.observation.produced_fact_ids == (fact.fact_id,)


def test_multiple_produced_fact_ids_are_canonicalized_independent_of_input_order() -> None:
    plan = _plan(("LX0609-032",))
    manifest = _manifest()
    first = _fact(source_key="surgery_record", fact_type="current_visit_surgery_confirmed", document_id="doc-a")
    second = _fact(source_key="surgery_record", fact_type="current_visit_surgery_confirmed", document_id="doc-b")
    bundle = _bundle(manifest, (first, second))
    pairs = _pairs(plan)
    record_pair = next(pair for pair in pairs if pair[1] == "surgery_record")
    left = _build(
        plan=plan, manifest=manifest, bundle=bundle,
        observations=tuple(
            _observation(pair, fact_ids=(first.fact_id, second.fact_id) if pair == record_pair else ())
            for pair in pairs
        ),
    )
    right = _build(
        plan=plan, manifest=manifest, bundle=bundle,
        observations=tuple(
            _observation(pair, fact_ids=(second.fact_id, first.fact_id) if pair == record_pair else ())
            for pair in pairs
        ),
    )
    assert left.fingerprint() == right.fingerprint()
    assert left.canonical_json() == right.canonical_json()


def test_returned_report_object_graph_retains_only_safe_values() -> None:
    report = _build()
    assert not hasattr(report, "plan")
    assert not hasattr(report, "manifest")
    assert not hasattr(report, "bundle")
    forbidden_types = (ShadowRulePlan, DocumentManifest, FactShadowBundle, FactV2)
    assert not any(isinstance(value, forbidden_types) for value in vars(report).values())
    safe_graph = asdict(report)
    serialized = repr(report) + json.dumps(safe_graph, default=str, ensure_ascii=False)
    for forbidden in ("safe quote", "normalized_value", "doc-ref", "record_time", "source_document", "FactV2", "FactShadowBundle", "DocumentManifest", "ShadowRulePlan"):
        assert forbidden not in serialized


def test_fingerprint_excludes_created_at_and_output_is_private() -> None:
    left = _build()
    right = build_luxian_0609_fact_coverage_shadow(
        plan=_plan(), manifest=_manifest(), bundle=_bundle(_manifest()),
        observations=tuple(_observation(pair) for pair in _pairs(_plan())),
        coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1",
        created_at="2026-07-13T10:00:00+08:00",
    )
    assert left.fingerprint() == right.fingerprint()
    serialized = left.canonical_json()
    for forbidden in ("quote", "normalized_value", "source_document", "record_time", "trace", "prompt", "response", "compliant", "ai_suggested"):
        assert forbidden not in serialized
    changed_version = build_luxian_0609_fact_coverage_shadow(
        plan=_plan(), manifest=_manifest(), bundle=_bundle(_manifest()),
        observations=tuple(_observation(pair) for pair in _pairs(_plan())),
        coverage_schema_version="coverage-v2", coverage_policy_version="policy-v1",
        created_at=CREATED_AT,
    )
    assert changed_version.fingerprint() != left.fingerprint()


def test_module_has_no_runtime_side_effect_imports() -> None:
    path = Path(coverage_module.__file__ or "")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    roots |= {(node.module or "").split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not roots & {"asyncio", "httpx", "logging", "os", "requests", "sqlalchemy"}
    assert importlib.reload(coverage_module).MAX_COVERAGE_PAIRS > 0
