from __future__ import annotations

from dataclasses import replace
import ast
import hashlib
import importlib
import json
from pathlib import Path
import re

import pytest

from app.services.luxian_0609 import planner as planner_module
from app.services.luxian_0609.planner import (
    MAX_RECORD_VISITS,
    MAX_RULES_PER_VISIT,
    MAX_SCOPE_RULE_IDS,
    MAX_TOTAL_RECORD_RULES,
    PlannedRule,
    PlanningExclusion,
    ShadowRulePlan,
    build_luxian_0609_shadow_plan,
)


CREATED_AT = "2026-07-12T09:00:00+08:00"
ALL_SLICE_RULES = ["LX0609-029", "LX0609-030", "LX0609-032"]


def _build(
    *,
    visit_ref: str = "visit-001",
    selected_rule_ids=None,
    scoped_customer_rule_ids=None,
    record_rule_map=None,
    planner_schema_version: str = "planner-v1",
    rule_plan_version: str = "slice-029-030-032-v1",
    created_at: str = CREATED_AT,
) -> ShadowRulePlan:
    selected = ALL_SLICE_RULES if selected_rule_ids is None else selected_rule_ids
    scoped = ALL_SLICE_RULES if scoped_customer_rule_ids is None else scoped_customer_rule_ids
    record_map = {visit_ref: list(ALL_SLICE_RULES)} if record_rule_map is None else record_rule_map
    return build_luxian_0609_shadow_plan(
        visit_ref=visit_ref,
        selected_rule_ids=selected,
        scoped_customer_rule_ids=scoped,
        record_rule_map=record_map,
        planner_schema_version=planner_schema_version,
        rule_plan_version=rule_plan_version,
        created_at=created_at,
    )


@pytest.mark.parametrize(
    ("selected", "scoped", "record_map"),
    [
        ([], ALL_SLICE_RULES, {"visit-001": ALL_SLICE_RULES}),
        (ALL_SLICE_RULES, [], {"visit-001": ALL_SLICE_RULES}),
        (ALL_SLICE_RULES, ALL_SLICE_RULES, {}),
        (ALL_SLICE_RULES, ALL_SLICE_RULES, {"other-visit": ALL_SLICE_RULES}),
        (ALL_SLICE_RULES, ALL_SLICE_RULES, {"visit-001": []}),
    ],
)
def test_empty_or_missing_explicit_scope_never_means_all(selected, scoped, record_map) -> None:
    plan = _build(
        selected_rule_ids=selected,
        scoped_customer_rule_ids=scoped,
        record_rule_map=record_map,
    )
    assert plan.planned_rules == ()
    assert plan.summary_dict() == {
        "expected_llm_call_count": 0,
        "planned_rule_count": 0,
        "zero_llm_expected": True,
    }


@pytest.mark.parametrize("rule_id", ALL_SLICE_RULES)
def test_single_supported_rule_is_planned_only_through_all_three_scopes(rule_id: str) -> None:
    plan = _build(
        selected_rule_ids=[rule_id],
        scoped_customer_rule_ids=[rule_id],
        record_rule_map={"visit-001": [rule_id]},
    )
    assert [item.rule_id for item in plan.planned_rules] == [rule_id]


def test_scope_intersection_order_and_duplicates_are_stable() -> None:
    left = _build(
        selected_rule_ids=["lx0609-032", "LX0609-029", "LX0609-030", "LX0609-029"],
        scoped_customer_rule_ids=["LX0609-030", "LX0609-032", "LX0609-029"],
        record_rule_map={"visit-001": ["LX0609-032", "lx0609-029", "LX0609-030"]},
    )
    right = _build()
    assert [item.rule_id for item in left.planned_rules] == ALL_SLICE_RULES
    assert left.fingerprint() == right.fingerprint()


def test_scope_exclusions_remain_bounded_and_traceable() -> None:
    plan = _build(
        selected_rule_ids=["LX0609-029", "LX0609-030", "LX0609-028"],
        scoped_customer_rule_ids=["LX0609-030", "LX0609-032", "LX0609-028"],
        record_rule_map={"visit-001": ["LX0609-032", "LX0609-028"]},
    )
    assert plan.planned_rules == ()
    assert [(item.rule_id, item.reason_code) for item in plan.exclusions] == [
        ("LX0609-028", "unsupported_slice_rule"),
        ("LX0609-029", "selected_not_scoped"),
        ("LX0609-030", "record_excluded"),
        ("LX0609-032", "scoped_not_selected"),
    ]


def test_nonempty_record_map_missing_current_visit_never_falls_back() -> None:
    plan = _build(record_rule_map={"VISIT-001": ALL_SLICE_RULES})
    assert plan.record_scope_state == "current_visit_absent"
    assert plan.record_rule_ids == ()
    assert plan.planned_rules == ()


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        29,
        True,
        "LX0609-29",
        "LX0609-0029",
        "LX0609-000",
        "LX0609-050",
        "LX0609-999",
        "SC-029",
        "",
        "LX0609-029\nsecret",
    ],
)
def test_invalid_rule_ids_fail_closed_without_echo(invalid) -> None:
    with pytest.raises((TypeError, ValueError)) as exc_info:
        _build(selected_rule_ids=[invalid])
    if str(invalid):
        assert str(invalid) not in str(exc_info.value)


@pytest.mark.parametrize("field", ["selected_rule_ids", "scoped_customer_rule_ids"])
def test_scope_iterables_are_bounded_and_bare_text_is_rejected(field: str) -> None:
    kwargs = {field: "LX0609-029"}
    with pytest.raises(TypeError):
        _build(**kwargs)

    values = ["LX0609-029"] * (MAX_SCOPE_RULE_IDS + 1)
    with pytest.raises(ValueError, match="too many"):
        _build(**{field: values})


def test_scope_generator_consumes_at_most_max_plus_one() -> None:
    consumed = 0

    def values():
        nonlocal consumed
        for _ in range(MAX_SCOPE_RULE_IDS + 100):
            consumed += 1
            yield "LX0609-029"

    with pytest.raises(ValueError, match="too many selected_rule_ids"):
        _build(selected_rule_ids=values())
    assert consumed == MAX_SCOPE_RULE_IDS + 1


def test_record_map_requires_exact_concrete_mapping_and_values() -> None:
    class DictSubclass(dict):
        pass

    with pytest.raises(TypeError):
        _build(record_rule_map=DictSubclass({"visit-001": ALL_SLICE_RULES}))
    for invalid_value in ("LX0609-029", (item for item in ALL_SLICE_RULES), {"LX0609-029"}):
        with pytest.raises(TypeError):
            _build(record_rule_map={"visit-001": invalid_value})


def test_record_visit_lookup_is_exact_without_strip_or_case_alias() -> None:
    lower = _build(visit_ref="visit-a", record_rule_map={"VISIT-A": ALL_SLICE_RULES})
    assert lower.planned_rules == ()
    with pytest.raises(ValueError, match="invalid record_rule_map visit_ref"):
        _build(record_rule_map={" visit-001": ALL_SLICE_RULES})


def test_record_map_visit_and_per_visit_limits() -> None:
    allowed_visits = {f"visit-{index:04d}": [] for index in range(MAX_RECORD_VISITS)}
    _build(record_rule_map=allowed_visits)
    with pytest.raises(ValueError, match="too many record_rule_map visits"):
        _build(record_rule_map={**allowed_visits, "visit-overflow": []})

    _build(record_rule_map={"visit-001": ["LX0609-029"] * MAX_RULES_PER_VISIT})
    with pytest.raises(ValueError, match="too many record_rule_map rules for visit"):
        _build(record_rule_map={"visit-001": ["LX0609-029"] * (MAX_RULES_PER_VISIT + 1)})


def test_record_map_total_limit_counts_duplicates_before_dedupe(monkeypatch) -> None:
    monkeypatch.setattr(planner_module, "MAX_TOTAL_RECORD_RULES", 3)
    _build(record_rule_map={"visit-001": ["LX0609-029", "LX0609-029"], "other": ["LX0609-030"]})
    with pytest.raises(ValueError, match="too many total record_rule_map rules"):
        _build(
            record_rule_map={
                "visit-001": ["LX0609-029", "LX0609-029"],
                "other": ["LX0609-030", "LX0609-030"],
            }
        )


def test_record_map_actual_total_contract_constant_exceeds_single_visit_limit() -> None:
    assert MAX_TOTAL_RECORD_RULES > MAX_RULES_PER_VISIT


def test_rule_metadata_declares_exact_sources_facts_and_dependency() -> None:
    items = {item.rule_id: item for item in _build().planned_rules}
    assert items["LX0609-029"].target_source_key == "presurg_summary"
    assert items["LX0609-030"].target_source_key == "surgery_record"
    assert items["LX0609-032"].target_source_key == "surgery_safecheck_record"
    assert items["LX0609-029"].required_trigger_fact_types == (
        "current_visit_surgery_confirmed",
        "current_visit_surgery_order_confirmed",
    )
    assert items["LX0609-030"].required_trigger_fact_types == items["LX0609-029"].required_trigger_fact_types
    safecheck = items["LX0609-032"]
    assert safecheck.required_trigger_fact_types == ("current_visit_surgery_confirmed",)
    assert safecheck.parent_rule_ids == ("LX0609-030",)
    assert safecheck.dependency_reason_codes == ("informational_parent_only",)
    assert safecheck.independent_target_source is True
    assert safecheck.required_source_keys == ("surgery_safecheck_record",)
    assert safecheck.trigger_source_match_policy == "any"
    assert safecheck.trigger_source_keys != ("surgery_record",)
    assert items["LX0609-029"].required_source_keys == ("presurg_summary",)
    assert items["LX0609-030"].required_source_keys == ("surgery_record",)
    assert items["LX0609-029"].parent_rule_ids == ()


def test_planner_only_declares_metadata_and_zero_llm_expectation() -> None:
    plan = _build()
    serialized = plan.canonical_json()
    assert plan.summary_dict()["expected_llm_call_count"] == 0
    assert "programmatic_zero_llm" in serialized
    for forbidden_key in ("manifest", "fact_bundle", "source_query_status", "llm_model"):
        assert forbidden_key not in serialized


def test_direct_planned_rule_construction_cannot_change_fixed_metadata() -> None:
    item = PlannedRule.for_rule_id("LX0609-029")
    with pytest.raises(ValueError, match="metadata mismatch"):
        replace(item, target_source_key="surgery_record")
    with pytest.raises(ValueError, match="metadata mismatch"):
        replace(item, family="other")


def test_global_rule_metadata_is_deeply_immutable() -> None:
    with pytest.raises(TypeError):
        planner_module._RULE_METADATA["LX0609-029"]["target_source_key"] = "changed"
    assert PlannedRule.for_rule_id("LX0609-029").target_source_key == "presurg_summary"


def test_direct_plan_construction_revalidates_order_scope_and_exclusions() -> None:
    plan = _build()
    with pytest.raises(ValueError, match="effective scope"):
        replace(plan, planned_rules=tuple(reversed(plan.planned_rules)))
    with pytest.raises(ValueError, match="exclusions"):
        replace(
            plan,
            exclusions=(PlanningExclusion("LX0609-029", "record_excluded"),),
        )
    with pytest.raises(ValueError, match="record_scope_state"):
        replace(plan, record_scope_state="global")
    with pytest.raises(ValueError, match="cannot carry record rules"):
        replace(plan, record_scope_state="current_visit_absent")
    with pytest.raises(TypeError, match="concrete tuple or list"):
        replace(plan, planned_rules=(item for item in plan.planned_rules))
    with pytest.raises(TypeError, match="concrete tuple or list"):
        replace(plan, exclusions=(item for item in plan.exclusions))


def test_direct_exclusion_rejects_customer_status_reason() -> None:
    for reason in ("compliant", "non_compliant", "ai_suggested", "technical_error"):
        with pytest.raises(ValueError):
            PlanningExclusion("LX0609-029", reason)


def test_inputs_and_defensive_outputs_are_isolated_from_mutation() -> None:
    selected = list(ALL_SLICE_RULES)
    scoped = list(ALL_SLICE_RULES)
    mapped = list(ALL_SLICE_RULES)
    record_map = {"visit-001": mapped}
    plan = _build(
        selected_rule_ids=selected,
        scoped_customer_rule_ids=scoped,
        record_rule_map=record_map,
    )
    original_json = plan.canonical_json()
    original_fingerprint = plan.fingerprint()
    selected.clear()
    scoped.clear()
    mapped.clear()
    record_map.clear()
    output = plan.to_dict()
    output["selected_rule_ids"].clear()
    output["planned_rules"][0]["required_source_keys"].append("changed")
    output["exclusions"].append({"rule_id": "LX0609-099", "reason_code": "changed"})
    assert plan.canonical_json() == original_json
    assert plan.fingerprint() == original_fingerprint


def test_fingerprint_is_canonical_and_excludes_created_at() -> None:
    left = _build(created_at="2026-07-12T09:00:00+08:00")
    right = _build(created_at="2026-07-13T09:00:00+08:00")
    assert left.fingerprint() == right.fingerprint()
    assert left.fingerprint() == hashlib.sha256(
        json.dumps(
            left.identity_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "changes",
    [
        {"planner_schema_version": "planner-v2"},
        {"rule_plan_version": "slice-v2"},
        {"visit_ref": "visit-002", "record_rule_map": {"visit-002": ALL_SLICE_RULES}},
        {"selected_rule_ids": ["LX0609-029", "LX0609-030"]},
        {"scoped_customer_rule_ids": ["LX0609-029", "LX0609-032"]},
        {"record_rule_map": {"visit-001": ["LX0609-029"]}},
        {"selected_rule_ids": [*ALL_SLICE_RULES, "LX0609-028"]},
    ],
)
def test_each_identity_dimension_changes_fingerprint(changes) -> None:
    assert _build(**changes).fingerprint() != _build().fingerprint()


def test_unrelated_record_map_order_and_content_do_not_leak_into_current_plan() -> None:
    left = _build(record_rule_map={"other-a": ["LX0609-028"], "visit-001": ALL_SLICE_RULES})
    right = _build(record_rule_map={"visit-001": ALL_SLICE_RULES, "other-b": ["LX0609-033"]})
    assert left.fingerprint() == right.fingerprint()
    serialized = left.canonical_json()
    assert "other-a" not in serialized
    assert "LX0609-028" not in serialized


def test_output_recursively_contains_no_customer_status_tokens() -> None:
    payload = _build(selected_rule_ids=[*ALL_SLICE_RULES, "LX0609-028"]).to_dict()
    serialized = json.dumps(payload, ensure_ascii=False)
    compact = re.sub(r"[_\s-]+", "", serialized).lower()
    for token in (
        "compliant",
        "noncompliant",
        "notapplicable",
        "datagap",
        "technicalerror",
        "evaluationunknown",
        "suppressed",
        "aisuggested",
    ):
        assert token not in compact


@pytest.mark.parametrize(
    "sensitive",
    [
        "138" + "0000" + "0000",
        "510000" + "000000" + "000000",
        "Author" + "ization: Bear" + "er hidden",
        "api_key=hidden",
        "patient_name",
        "full_text",
    ],
)
def test_sensitive_visit_keys_fail_with_fixed_non_echoing_errors(sensitive: str) -> None:
    with pytest.raises((TypeError, ValueError)) as exc_info:
        _build(visit_ref=sensitive, record_rule_map={sensitive: ALL_SLICE_RULES})
    assert sensitive not in str(exc_info.value)


def test_canonical_output_contains_only_controlled_scope_and_metadata() -> None:
    serialized = _build().canonical_json()
    for forbidden in (
        "patient_name",
        "id_card",
        "source_document_id",
        "full_text",
        "prompt",
        "response",
        "trace",
        "quote",
        "Authorization",
    ):
        assert forbidden not in serialized


def test_module_has_no_runtime_side_effect_imports_or_mutable_runtime_objects() -> None:
    path = Path(planner_module.__file__ or "")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imported_roots & {
        "app",
        "asyncio",
        "httpx",
        "logging",
        "os",
        "requests",
        "sqlalchemy",
    }
    source = path.read_text(encoding="utf-8")
    assert "DocumentManifest" not in source
    assert "FactShadowBundle" not in source
    assert importlib.reload(planner_module).SUPPORTED_RULE_IDS == tuple(ALL_SLICE_RULES)
