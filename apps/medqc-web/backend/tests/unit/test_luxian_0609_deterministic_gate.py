from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.deterministic_gate import (
    GateDecision,
    GateFactRef,
    GateReadiness,
    GateReport,
    TargetQualification,
    TargetResolution,
    TriggerResolution,
    build_luxian_0609_deterministic_gate_shadow,
)
from app.services.luxian_0609.fact_coverage import FactCoverageObservation, build_luxian_0609_fact_coverage_shadow
from app.services.luxian_0609.fact_schema import Assertion, AssertionContext, CurrentVisitRelevance, EventStatus, FactV2, TriggerScope
from app.services.luxian_0609.planner import build_luxian_0609_shadow_plan
from app.services.luxian_0609.shadow_fact_bundle import FactShadowBundle, FactShadowBundleItem
from app.services.luxian_0609.source_manifest import DocumentManifest, QueryStatus, SourceManifestEntry

CREATED = "2026-07-12T12:00:00+08:00"
VISIT = "visit-gate-001"
SNAPSHOT = "a" * 64
SOURCES = (
    "inpat_nondrug_order",
    "mr_surgery",
    "surgery_application",
    "surgery_record",
    "presurg_summary",
    "surgery_safecheck_record",
)


def _plan(rule_ids=("LX0609-04-02-02",)):
    return build_luxian_0609_shadow_plan(visit_ref=VISIT, selected_rule_ids=list(rule_ids), scoped_customer_rule_ids=list(rule_ids), record_rule_map={VISIT: list(rule_ids)}, planner_schema_version="planner-v1", rule_plan_version="slice-v1", created_at=CREATED)


def _manifest(statuses=None, *, omit=()):
    statuses = statuses or {}
    entries = []
    for index, source in enumerate(SOURCES):
        if source in omit:
            continue
        status = statuses.get(source, QueryStatus.AVAILABLE)
        entries.append(SourceManifestEntry.create(source_key=source, query_status=status, record_count=2 if status is QueryStatus.AVAILABLE else (0 if status is QueryStatus.EMPTY else None), query_version="query-v1", snapshot_ref="sha256:" + f"{index + 1:064x}", error_code="source_failure" if status is QueryStatus.ERROR else "", reason_code="source_paused" if status is QueryStatus.UNAVAILABLE else ""))
    return DocumentManifest(manifest_schema_version="manifest-v1", visit_ref=VISIT, source_snapshot_hash=SNAPSHOT, entries=tuple(entries), created_at=CREATED)


def _pairs(plan):
    return tuple(sorted({(requirement.fact_type, source) for rule in plan.planned_rules for requirement in rule.trigger_requirements for source in requirement.allowed_source_keys}))


def _fact(*, fact_type, source_key, document_id="doc-ref", trigger_scope=TriggerScope.CURRENT_VISIT, relevance=CurrentVisitRelevance.RELEVANT, assertion=Assertion.AFFIRMED, event_status=None, quote="safe quote", value=None):
    if event_status is None:
        event_status = EventStatus.ORDERED if fact_type.endswith("order_confirmed") else EventStatus.PERFORMED
    return FactV2.create(visit_ref=VISIT, family="surgery_anesthesia", fact_type=fact_type, normalized_value={"kind": "gate_fixture"} if value is None else value, trigger_scope=trigger_scope, current_visit_relevance=relevance, assertion=assertion, assertion_context=AssertionContext.CURRENT_NARRATIVE, event_status=event_status, source_key=source_key, source_document_id=document_id, source_document_type="gate_fixture", record_time=None, submit_time=None, update_time=None, quote=quote, redaction_terms=(), confidence=0.9, extractor="gate_fixture", extractor_version="extractor-v1", fact_schema_version="fact-v2", source_snapshot_hash=SNAPSHOT, created_at=CREATED, extensions={}, known_upstream_fact_ids=())


def _bundle(manifest, facts=()):
    return FactShadowBundle(bundle_schema_version="bundle-v1", visit_ref=VISIT, manifest_fingerprint=manifest.fingerprint(), source_snapshot_hash=SNAPSHOT, items=tuple(FactShadowBundleItem(pair_ref=f"{index + 1:064x}", fact=fact) for index, fact in enumerate(facts)), created_at=CREATED)


def _observation(pair, *, state="complete", processed=2, fact_ids=(), reason="", error=""):
    return FactCoverageObservation(fact_type=pair[0], source_key=pair[1], state=state, extractor_version="extractor-v1", mapping_policy_version="mapping-v1", processed_record_count=processed, produced_fact_ids=tuple(fact_ids), reason_code=reason, error_code=error)


def _coverage(*, plan, manifest, bundle, overrides=None):
    overrides = overrides or {}
    observations = []
    for pair in _pairs(plan):
        status = next(entry.query_status for entry in manifest.entries if entry.source_key == pair[1])
        if pair in overrides:
            observations.append(overrides[pair])
        elif status is QueryStatus.EMPTY:
            observations.append(_observation(pair, processed=0))
        elif status is QueryStatus.UNAVAILABLE:
            observations.append(_observation(pair, state="not_run", processed=0, reason="source_unavailable"))
        elif status is QueryStatus.ERROR:
            observations.append(_observation(pair, state="not_run", processed=0, reason="source_query_error"))
        else:
            observations.append(_observation(pair))
    return build_luxian_0609_fact_coverage_shadow(plan=plan, manifest=manifest, bundle=bundle, observations=tuple(observations), coverage_schema_version="coverage-v1", coverage_policy_version="policy-v1", created_at=CREATED)


def _gate(*, rule_ids=("LX0609-04-02-02",), statuses=None, facts=(), overrides=None, manifest=None, qualifications=None):
    plan = _plan(rule_ids)
    manifest = _manifest(statuses) if manifest is None else manifest
    bundle = _bundle(manifest, facts)
    coverage = _coverage(plan=plan, manifest=manifest, bundle=bundle, overrides=overrides)
    if qualifications is None:
        qualifications = tuple(
            TargetQualification(VISIT, rule.rule_id, rule.target_source_key, "target-qualification-v1", "f" * 64, 1)
            for rule in plan.planned_rules
            if rule.rule_id in ("LX0609-04-01-01", "LX0609-04-03-01")
            and next(entry.query_status for entry in manifest.entries if entry.source_key == rule.target_source_key) is QueryStatus.AVAILABLE
        )
    return build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=bundle, coverage=coverage, target_qualifications=qualifications, gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)


def test_available_qualified_targets_require_exact_safe_sidecar_scope_and_order():
    order_fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    with pytest.raises(ValueError, match="qualification"):
        _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=())
    qualification = TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "f" * 64, 1)
    extra = TargetQualification(VISIT, "LX0609-04-03-01", "surgery_safecheck_record", "target-qualification-v1", "e" * 64, 1)
    with pytest.raises(ValueError, match="qualification"):
        _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=(qualification, extra))
    wrong_visit = TargetQualification("visit-other-001", "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "f" * 64, 1)
    with pytest.raises(ValueError, match="qualification"):
        _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=(wrong_visit,))


def test_nonavailable_target_cannot_be_overridden_by_target_qualification():
    order_fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    qualification = TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "f" * 64, 1)
    with pytest.raises(ValueError, match="qualification"):
        _gate(
            rule_ids=("LX0609-04-01-01",), facts=(order_fact,),
            statuses={"presurg_summary": QueryStatus.EMPTY}, qualifications=(qualification,),
        )


def test_target_qualification_safe_identity_changes_gate_fingerprint_not_created_at():
    order_fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    first = TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "f" * 64, 1)
    second = TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "e" * 64, 1)
    first_gate = _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=(first,))
    second_gate = _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=(second,))
    assert first_gate.fingerprint() != second_gate.fingerprint()
    assert first_gate.fingerprint() == replace(first_gate, created_at="2026-07-13T12:00:00+08:00").fingerprint()


def test_target_qualification_rejects_unapproved_policy_and_count_above_target_records():
    with pytest.raises(ValueError, match="target qualification"):
        TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v2", "f" * 64, 1)
    order_fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    excessive = TargetQualification(VISIT, "LX0609-04-01-01", "presurg_summary", "target-qualification-v1", "f" * 64, 3)
    with pytest.raises(ValueError, match="target qualification"):
        _gate(rule_ids=("LX0609-04-01-01",), facts=(order_fact,), qualifications=(excessive,))


@pytest.mark.parametrize(("status", "resolution", "readiness"), [(QueryStatus.AVAILABLE, TargetResolution.PRESENT, GateReadiness.READY), (QueryStatus.EMPTY, TargetResolution.EMPTY, GateReadiness.READY), (QueryStatus.UNAVAILABLE, TargetResolution.UNAVAILABLE, GateReadiness.BLOCKED), (QueryStatus.ERROR, TargetResolution.ERROR, GateReadiness.BLOCKED)])
def test_a_matched_target_matrix(status, resolution, readiness):
    # 术后记录义务以已实施事实触发，计划医嘱不证明实施。
    fact = _fact(fact_type="current_visit_surgery_confirmed", source_key="mr_surgery")
    pair = (fact.fact_type, fact.source_key)
    report = _gate(statuses={"surgery_record": status}, facts=(fact,), overrides={pair: _observation(pair, fact_ids=(fact.fact_id,))})
    assert (report.decisions[0].target_resolution, report.decisions[0].readiness) == (resolution, readiness)


@pytest.mark.parametrize(("rule_id", "source"), [("LX0609-04-01-01", "presurg_summary"), ("LX0609-04-03-01", "surgery_safecheck_record")])
def test_target_qualification_keeps_raw_available_but_resolves_unqualified_as_empty(rule_id, source):
    fact = _fact(fact_type="current_visit_surgery_confirmed", source_key="surgery_record")
    pair = (fact.fact_type, fact.source_key)
    qualification = TargetQualification(VISIT, rule_id, source, "target-qualification-v1", "f" * 64, 0)
    report = _gate(rule_ids=(rule_id,), facts=(fact,), overrides={pair: _observation(pair, fact_ids=(fact.fact_id,))}, qualifications=(qualification,))
    assert next(entry for entry in _manifest().entries if entry.source_key == source).query_status is QueryStatus.AVAILABLE
    assert report.decisions[0].target_resolution is TargetResolution.EMPTY


@pytest.mark.parametrize(("target", "readiness"), [("present", "blocked"), ("empty", "blocked"), ("unavailable", "ready"), ("error", "ready")])
def test_a_public_constructor_rejects_illegal_matched_crosses(target, readiness):
    ref = GateFactRef("b" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order")
    with pytest.raises(ValueError, match="invalid matched"):
        GateDecision("LX0609-04-02-02", "matched", "surgery_record", target, readiness, (ref,), (), ())


def test_b_exact_rule_metadata_and_allowed_ref_pairs():
    assert GateDecision("LX0609-04-01-01", "absent_complete", "presurg_summary", None, "not_triggered", (), (), ()).rule_id == "LX0609-04-01-01"
    assert GateDecision("LX0609-04-03-01", "absent_complete", "surgery_safecheck_record", None, "not_triggered", (), ("LX0609-04-02-02",), ("informational_parent_only",)).rule_id == "LX0609-04-03-01"
    bad = GateFactRef("c" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order")
    with pytest.raises(ValueError, match="not allowed"):
        GateDecision("LX0609-04-03-01", "matched", "surgery_safecheck_record", "present", "ready", (bad,), ("LX0609-04-02-02",), ("informational_parent_only",))
    with pytest.raises(ValueError, match="metadata"):
        GateDecision("LX0609-04-02-02", "absent_complete", "wrong_target", None, "not_triggered", (), (), ())


@pytest.mark.parametrize("marker", ["Bearer_secret", "sk-secret", "full_text", "medical_text", "raw_response", "patient_name", "phone_13800000000", "11010519491231002X"])
def test_a_public_code_fields_reject_sensitive_or_credential_markers_without_echo(marker):
    with pytest.raises(ValueError) as fact_error:
        GateFactRef("a" * 64, marker, "safe_source")
    assert marker not in str(fact_error.value)
    with pytest.raises(ValueError) as report_error:
        GateReport(marker, "policy-v1", VISIT, "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, (), (), CREATED)
    assert marker not in str(report_error.value)
    with pytest.raises(ValueError) as visit_error:
        GateReport("gate-v1", "policy-v1", marker, "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, (), (), CREATED)
    assert marker not in str(visit_error.value)


@pytest.mark.parametrize(("field", "value", "message"), [("trigger", "raw_response", "trigger_resolution"), ("target", "sk-secret", "target_resolution"), ("readiness", "Bearer_secret", "readiness")])
def test_b_invalid_enums_are_non_echo(field, value, message):
    values = {"trigger": "absent_complete", "target": None, "readiness": "not_triggered"}
    values[field] = value
    with pytest.raises(ValueError) as error:
        GateDecision("LX0609-04-02-02", values["trigger"], "surgery_record", values["target"], values["readiness"], (), (), ())
    assert str(error.value) == f"invalid {message}"


@pytest.mark.parametrize("mode", ["matched", "absent", "conflict", "blocker"])
def test_c_missing_target_rejects_before_every_resolution(mode):
    plan = _plan(("LX0609-04-01-01",))
    manifest = _manifest(omit=("presurg_summary",))
    pair = ("current_visit_surgery_order_confirmed", "inpat_nondrug_order")
    facts = ()
    overrides = {}
    if mode == "matched":
        fact = _fact(fact_type=pair[0], source_key=pair[1]); facts = (fact,); overrides[pair] = _observation(pair, fact_ids=(fact.fact_id,))
    elif mode == "conflict":
        fact = _fact(fact_type=pair[0], source_key=pair[1], assertion=Assertion.NEGATED); facts = (fact,); overrides[pair] = _observation(pair, fact_ids=(fact.fact_id,))
    elif mode == "blocker":
        overrides[pair] = _observation(pair, state="partial", processed=1, reason="partial_budget_limit")
    bundle = _bundle(manifest, facts)
    coverage = _coverage(plan=plan, manifest=manifest, bundle=bundle, overrides=overrides)
    with pytest.raises(ValueError, match="target source"):
        build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=bundle, coverage=coverage, gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)


@pytest.mark.parametrize(("field", "value"), [("trigger_scope", TriggerScope.PRIOR_HISTORY), ("relevance", CurrentVisitRelevance.NOT_RELEVANT), ("assertion", Assertion.NEGATED), ("event_status", EventStatus.PLANNED)])
def test_d_valid_fact_semantic_conflicts(field, value):
    kwargs = {field: value}
    fact = _fact(fact_type="current_visit_surgery_confirmed", source_key="surgery_record", **kwargs)
    pair = (fact.fact_type, fact.source_key)
    report = _gate(facts=(fact,), overrides={pair: _observation(pair, fact_ids=(fact.fact_id,))})
    assert report.decisions[0].trigger_resolution is TriggerResolution.SEMANTIC_CONFLICT


def test_d_order_and_performed_semantics_and_e_positive_wins():
    order = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    performed = _fact(fact_type="current_visit_surgery_confirmed", source_key="surgery_record", document_id="doc-performed")
    bad_pair = ("current_visit_surgery_confirmed", "surgery_application")
    report = _gate(facts=(order, performed), overrides={(order.fact_type, order.source_key): _observation((order.fact_type, order.source_key), fact_ids=(order.fact_id,)), (performed.fact_type, performed.source_key): _observation((performed.fact_type, performed.source_key), fact_ids=(performed.fact_id,)), bad_pair: _observation(bad_pair, state="partial", processed=1, reason="partial_budget_limit")})
    assert report.decisions[0].trigger_resolution is TriggerResolution.MATCHED


def test_typed_mr_surgery_fact_is_accepted_and_overrides_other_source_error():
    fact = _fact(
        fact_type="current_visit_surgery_confirmed",
        source_key="mr_surgery",
        document_id="mr-surgery-ref",
    )
    positive_pair = (fact.fact_type, fact.source_key)
    report = _gate(
        facts=(fact,),
        statuses={"surgery_record": QueryStatus.ERROR},
        overrides={positive_pair: _observation(positive_pair, fact_ids=(fact.fact_id,))},
    )

    assert report.decisions[0].trigger_resolution is TriggerResolution.MATCHED
    assert report.decisions[0].matched_fact_refs[0].source_key == "mr_surgery"


def test_strict_surgery_record_fact_overrides_mr_surgery_source_error():
    fact = _fact(
        fact_type="current_visit_surgery_confirmed",
        source_key="surgery_record",
        document_id="surgery-record-ref",
    )
    positive_pair = (fact.fact_type, fact.source_key)
    report = _gate(
        facts=(fact,),
        statuses={"mr_surgery": QueryStatus.ERROR},
        overrides={positive_pair: _observation(positive_pair, fact_ids=(fact.fact_id,))},
    )

    assert report.decisions[0].trigger_resolution is TriggerResolution.MATCHED
    assert report.decisions[0].matched_fact_refs[0].source_key == "surgery_record"


def test_mr_surgery_source_error_blocks_only_when_no_alternative_positive():
    report = _gate(statuses={"mr_surgery": QueryStatus.ERROR})
    assert report.decisions[0].trigger_resolution is TriggerResolution.SOURCE_ERROR
    assert report.decisions[0].readiness is GateReadiness.BLOCKED


def test_gate_decision_rejects_unapproved_performed_source():
    bad = GateFactRef(
        "9" * 64,
        "current_visit_surgery_confirmed",
        "presurg_summary",
    )
    with pytest.raises(ValueError, match="not allowed"):
        GateDecision(
            "LX0609-04-02-02",
            "matched",
            "surgery_record",
            "present",
            "ready",
            (bad,),
            (),
            (),
        )


@pytest.mark.parametrize("mode", ["coverage_partial", "coverage_not_run", "coverage_error", "source_unavailable", "source_error"])
def test_c_positive_claimed_match_overrides_every_other_alternative_blocker(mode):
    fact = _fact(fact_type="current_visit_surgery_confirmed", source_key="surgery_record")
    positive_pair = (fact.fact_type, fact.source_key)
    blocked_pair = ("current_visit_surgery_confirmed", "surgery_application")
    statuses = {}
    overrides = {positive_pair: _observation(positive_pair, fact_ids=(fact.fact_id,))}
    if mode == "coverage_partial":
        overrides[blocked_pair] = _observation(blocked_pair, state="partial", processed=1, reason="partial_budget_limit")
    elif mode == "coverage_not_run":
        overrides[blocked_pair] = _observation(blocked_pair, state="not_run", processed=0, reason="extractor_not_run")
    elif mode == "coverage_error":
        overrides[blocked_pair] = _observation(blocked_pair, state="error", processed=1, reason="extraction_error", error="extractor_timeout")
    elif mode == "source_unavailable":
        statuses[blocked_pair[1]] = QueryStatus.UNAVAILABLE
    else:
        statuses[blocked_pair[1]] = QueryStatus.ERROR
    assert _gate(facts=(fact,), statuses=statuses, overrides=overrides).decisions[0].trigger_resolution is TriggerResolution.MATCHED


def test_e_unclaimed_fact_is_ignored_and_all_blocker_precedence():
    fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    assert _gate(facts=(fact,)).decisions[0].trigger_resolution is TriggerResolution.ABSENT_COMPLETE
    pairs = _pairs(_plan())
    overrides = {
        pairs[0]: _observation(pairs[0], state="partial", processed=1, reason="partial_budget_limit"),
        pairs[1]: _observation(pairs[1], state="error", processed=1, reason="extraction_error", error="extractor_timeout"),
        pairs[2]: _observation(pairs[2], state="not_run", processed=0, reason="extractor_not_run"),
    }
    assert _gate(overrides=overrides).decisions[0].trigger_resolution is TriggerResolution.COVERAGE_ERROR
    assert _gate(statuses={"inpat_nondrug_order": QueryStatus.ERROR}, overrides={}).decisions[0].trigger_resolution is TriggerResolution.SOURCE_ERROR


def test_f_complete_absence_empty_not_run_and_one_incomplete_alternative():
    assert _gate().decisions[0].trigger_resolution is TriggerResolution.ABSENT_COMPLETE
    assert _gate(statuses={"inpat_nondrug_order": QueryStatus.EMPTY}).decisions[0].trigger_resolution is TriggerResolution.ABSENT_COMPLETE
    pair = ("current_visit_surgery_confirmed", "surgery_application")
    assert _gate(overrides={pair: _observation(pair, state="not_run", processed=0, reason="extractor_not_run")}).decisions[0].trigger_resolution is TriggerResolution.COVERAGE_NOT_RUN


@pytest.mark.parametrize(("statuses", "override", "expected"), [
    ({"inpat_nondrug_order": QueryStatus.UNAVAILABLE}, None, TriggerResolution.SOURCE_UNAVAILABLE),
    (None, ("partial", "partial_budget_limit"), TriggerResolution.COVERAGE_PARTIAL),
    (None, ("error", "extraction_error"), TriggerResolution.COVERAGE_ERROR),
])
def test_f_each_nonconclusive_blocker(statuses, override, expected):
    pair = ("current_visit_surgery_order_confirmed", "inpat_nondrug_order")
    overrides = {}
    if override is not None:
        state, reason = override
        overrides[pair] = _observation(pair, state=state, processed=1, reason=reason, error="extractor_timeout" if state == "error" else "")
    assert _gate(statuses=statuses, overrides=overrides).decisions[0].trigger_resolution is expected


@pytest.mark.parametrize(("statuses", "overrides", "expected"), [
    ({"inpat_nondrug_order": QueryStatus.ERROR}, {("current_visit_surgery_confirmed", "surgery_record"): _observation(("current_visit_surgery_confirmed", "surgery_record"), state="error", processed=1, reason="extraction_error", error="extractor_timeout")}, TriggerResolution.SOURCE_ERROR),
    ({"inpat_nondrug_order": QueryStatus.UNAVAILABLE}, {("current_visit_surgery_confirmed", "surgery_record"): _observation(("current_visit_surgery_confirmed", "surgery_record"), state="error", processed=1, reason="extraction_error", error="extractor_timeout")}, TriggerResolution.COVERAGE_ERROR),
    ({"inpat_nondrug_order": QueryStatus.UNAVAILABLE}, {("current_visit_surgery_confirmed", "surgery_record"): _observation(("current_visit_surgery_confirmed", "surgery_record"), state="partial", processed=1, reason="partial_budget_limit")}, TriggerResolution.SOURCE_UNAVAILABLE),
    (None, {("current_visit_surgery_confirmed", "surgery_application"): _observation(("current_visit_surgery_confirmed", "surgery_application"), state="partial", processed=1, reason="partial_budget_limit"), ("current_visit_surgery_confirmed", "surgery_record"): _observation(("current_visit_surgery_confirmed", "surgery_record"), state="not_run", processed=0, reason="extractor_not_run")}, TriggerResolution.COVERAGE_PARTIAL),
])
def test_d_explicit_blocker_precedence(statuses, overrides, expected):
    assert _gate(statuses=statuses, overrides=overrides).decisions[0].trigger_resolution is expected


def test_g_030_empty_target_and_standalone_032():
    fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order")
    pair = (fact.fact_type, fact.source_key)
    report = _gate(statuses={"surgery_record": QueryStatus.EMPTY}, facts=(fact,), overrides={pair: _observation(pair, fact_ids=(fact.fact_id,))})
    assert report.decisions[0].target_resolution is None
    assert report.decisions[0].trigger_resolution is TriggerResolution.SEMANTIC_CONFLICT
    surgical = _fact(fact_type="current_visit_surgery_confirmed", source_key="surgery_record")
    standalone = _gate(rule_ids=("LX0609-04-03-01",), facts=(surgical,), overrides={(surgical.fact_type, surgical.source_key): _observation((surgical.fact_type, surgical.source_key), fact_ids=(surgical.fact_id,))})
    assert standalone.decisions[0].trigger_resolution is TriggerResolution.MATCHED
    assert standalone.decisions[0].parent_rule_ids == ("LX0609-04-02-02",)


def test_h_zero_multi_constructor_bounds_and_ref_identity():
    assert _gate(rule_ids=()).decisions == ()
    multi = _gate(rule_ids=("LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"))
    assert tuple(item.rule_id for item in multi.decisions) == ("LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01")
    with pytest.raises(ValueError):
        replace(multi, decisions=multi.decisions[::-1])
    with pytest.raises(ValueError):
        GateDecision("LX0609-04-02-02", "absent_complete", "surgery_record", None, "not_triggered", (GateFactRef("d" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"),), (), ())
    refs = (GateFactRef("f" * 64, "current_visit_surgery_confirmed", "surgery_record"), GateFactRef("e" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"))
    decision = GateDecision("LX0609-04-02-02", "matched", "surgery_record", "present", "ready", refs, (), ())
    assert tuple(ref.fact_id for ref in decision.matched_fact_refs) == ("e" * 64, "f" * 64)
    too_many = tuple(GateFactRef(f"{index:064x}", "current_visit_surgery_order_confirmed", "inpat_nondrug_order") for index in range(1, 514))
    with pytest.raises(ValueError, match="matched fact refs"):
        GateDecision("LX0609-04-02-02", "matched", "surgery_record", "present", "ready", too_many, (), ())


def test_i_cross_object_fingerprint_mismatch():
    plan = _plan(); manifest = _manifest(); bundle = _bundle(manifest); coverage = _coverage(plan=plan, manifest=manifest, bundle=bundle)
    with pytest.raises(ValueError, match="coverage fingerprint"):
        build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=bundle, coverage=replace(coverage, plan_fingerprint="b" * 64), gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)
    class ShadowRulePlan: pass
    with pytest.raises(TypeError, match="accepted value objects"):
        build_luxian_0609_deterministic_gate_shadow(plan=ShadowRulePlan(), manifest=manifest, bundle=bundle, coverage=coverage, gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)
    other_plan = build_luxian_0609_shadow_plan(visit_ref="visit-gate-002", selected_rule_ids=["LX0609-04-02-02"], scoped_customer_rule_ids=["LX0609-04-02-02"], record_rule_map={"visit-gate-002": ["LX0609-04-02-02"]}, planner_schema_version="planner-v1", rule_plan_version="slice-v1", created_at=CREATED)
    with pytest.raises(ValueError, match="visit_ref"):
        build_luxian_0609_deterministic_gate_shadow(plan=other_plan, manifest=manifest, bundle=bundle, coverage=coverage, gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)


@pytest.mark.parametrize("field", ["plan_fingerprint", "manifest_fingerprint", "source_snapshot_hash", "bundle_fingerprint"])
def test_e_coverage_cross_object_fingerprint_dimensions_reject(field):
    plan = _plan(); manifest = _manifest(); bundle = _bundle(manifest); coverage = _coverage(plan=plan, manifest=manifest, bundle=bundle)
    with pytest.raises(ValueError, match="coverage fingerprint"):
        build_luxian_0609_deterministic_gate_shadow(plan=plan, manifest=manifest, bundle=bundle, coverage=replace(coverage, **{field: "b" * 64}), gate_schema_version="gate-v1", gate_policy_version="policy-v1", created_at=CREATED)


def test_j_safe_only_output_non_echo_and_forbidden_status_scan():
    fact = _fact(fact_type="current_visit_surgery_order_confirmed", source_key="inpat_nondrug_order", quote="quote-marker", value={"detail": "value-marker"})
    pair = (fact.fact_type, fact.source_key)
    report = _gate(facts=(fact,), overrides={pair: _observation(pair, fact_ids=(fact.fact_id,))})
    serialized = repr(report) + str(asdict(report)) + report.canonical_json()
    for marker in ("quote-marker", "value-marker", "gate_fixture", "doc-ref", "Authorization", "api_key", "13800000000", "11010519491231002X"):
        assert marker not in serialized
    assert not any(name in vars(report) for name in ("plan", "manifest", "bundle", "coverage"))
    for token in ("compliant", "not_applicable", "data_gap", "ai_suggested", "technical_error"):
        assert token not in report.canonical_json()
    with pytest.raises(ValueError, match="invalid"):
        GateDecision("LX0609-04-02-02", "matched", "surgery_record", "patient_name", "ready", (), (), ())


def test_report_constructor_exact_order_and_created_at_independent_identity():
    report = _gate()
    assert report.fingerprint() == replace(report, created_at="2026-07-13T12:00:00+08:00").fingerprint()
    with pytest.raises(ValueError):
        GateReport("gate-v1", "policy-v1", VISIT, "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-04-02-02",), (), CREATED)
