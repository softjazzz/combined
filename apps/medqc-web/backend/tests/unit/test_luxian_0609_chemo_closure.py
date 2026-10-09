"""05-02-01 化疗收尾：只用合成快照验证正式交付链。"""
from __future__ import annotations

import pytest

from chemotherapy_administration_test_support import FrozenChemotherapyAdministrationClient, fact

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

RULE = "LX0609-05-02-01"
ORDER = {
    "document_id": "synthetic-chemo-order",
    "generic_name": "奥沙利铂",
    "single_dose": "130",
    "single_dose_unit": "mg",
    "drug_apply_method": "静滴",
    "prescribed_datetime": "2026-04-26 09:00:00",
    "drug_type": "抗肿瘤化疗药物",
    "order_status": "执行",
}


class _NoModel:
    async def generate(self, *_args, **_kwargs):
        raise AssertionError("合成化疗比较不得访问模型")


async def _run(course_rows, *, order=None, orders=None, annotations=None, coverage_unknown=()):
    rows = {
        "diagnosis": ({"document_id": "synthetic-diagnosis", "diagnosis_code": "C18.9"},),
        "inpat_drug_order": tuple(orders) if orders is not None else (ORDER if order is None else order,),
        "daily_course_record": tuple(course_rows),
        "discharge_record": ({"document_id": "synthetic-discharge", "discharge_order": "出院后随访。"},),
    }

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="synthetic-I", patient_id="synthetic-P",
        visit_id="synthetic-V", source_schema=None, created_at="2026-10-08T10:00:00+08:00",
        row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=(RULE,),
        ),
    )
    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[], evidence_payload=None,
        institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, llm_client=FrozenChemotherapyAdministrationClient(
            annotations, auto=True, coverage={text: "unknown" for text in coverage_unknown}), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    # 026 每例至多一次给药原子事实抽取（标注替身，token 为 0）。
    assert execution.llm_call_count <= 1 and execution.total_tokens == 0
    assert execution.results == ()
    return execution, reduced, final


def _course(text):
    return [{"document_id": "synthetic-chemo-course", "record_content": text,
             "record_time": "2026-04-26 16:00:00"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("course_rows", [[], _course(""), _course(" \n\t ")])
async def test_empty_course_delivers_controlled_data_gap(course_rows):
    execution, reduced, final = await _run(course_rows)
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert execution.decisions[0].reason_code == "source_unavailable"
    assert "customer_display_facts" not in final
    assert not final.get("customer_evidence")
    assert "继续保持" not in str(final)


@pytest.mark.asyncio
async def test_complete_course_keeps_exact_facts_and_evidence():
    _execution, reduced, final = await _run(_course("2026-04-26 使用奥沙利铂130mg 静滴。"))
    assert reduced.final_state.value == final["status"] == "compliant"
    assert final["customer_display_facts"]["field_results"] == {
        "drug_name": "matched", "dose": "matched", "route": "matched", "time": "matched",
    }
    assert {(ref["source_type"], ref["source_document_id"]) for ref in final["customer_evidence"]} == {
        ("inpat_drug_order", "synthetic-chemo-order"),
        ("daily_course_record", "synthetic-chemo-course"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("key,missing", [
    ("single_dose", "dose"), ("single_dose_unit", "dose"),
    ("generic_name", "drug_name"), ("drug_apply_method", "route"),
    ("prescribed_datetime", "time"),
])
async def test_missing_order_field_never_claims_skipped_comparison_matched(key, missing):
    _execution, _reduced, final = await _run(
        _course("2026-04-26 使用奥沙利铂130mg 静滴。"), order={**ORDER, key: ""},
    )
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["missing_order_fields"] == [missing]
    assert facts["missing_order_event_count"] == 1
    assert set(facts["field_results"].values()) == {"unknown"}
    assert "继续保持" not in str(final)
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("dose,state", [("130", "unknown"), ("120", "mismatched")])
async def test_missing_event_preserves_complete_event_comparison_in_both_orders(reverse, dose, state):
    orders = [ORDER, {**ORDER, "document_id": "synthetic-missing-order",
                      "generic_name": "顺铂", "single_dose_unit": ""}]
    if reverse:
        orders.reverse()
    _execution, _reduced, final = await _run(
        _course(f"2026-04-26 使用奥沙利铂{dose}mg 静滴。"), orders=orders,
    )
    assert final["status"] == ("non_compliant" if state == "mismatched" else "data_gap")
    if state == "mismatched":
        assert "剂量记录不一致" in final["findings"]
        assert "尚无法核对" in final["findings"]
        assert "继续保持" not in final["suggestion"]
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == 1
    assert facts["field_results"] == {
        "drug_name": "unknown", "dose": state, "route": "unknown", "time": "unknown",
    }
    assert {(r["source_type"], r["source_document_id"]) for r in final["customer_evidence"]} == {
        ("inpat_drug_order", "synthetic-chemo-order"),
        ("inpat_drug_order", "synthetic-missing-order"),
        ("daily_course_record", "synthetic-chemo-course"),
    }
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


def _missing_facts(**changes):
    return {
        "verification_kind": "chemotherapy_order_course_comparison", "order_count": 2,
        "field_results": dict.fromkeys(("drug_name", "dose", "route", "time"), "unknown"),
        "missing_order_fields": ["dose"], "missing_order_event_count": 1,
        "unresolved_event_count": 0, "missing_course_event_count": 0,
        "unknown_time_event_count": 0, **changes,
    }


@pytest.mark.parametrize("count", [-1, True, False, 1.0, "1", None, 3])
def test_missing_event_count_is_a_bounded_integer(count):
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=_missing_facts(missing_order_event_count=count)) is None


@pytest.mark.parametrize("changes", [
    {"missing_order_event_count": 0}, {"missing_order_fields": []},
    {"unresolved_event_count": 2}, {"missing_course_event_count": 2},
    {"unknown_time_event_count": 2},
    {"field_results": dict.fromkeys(("drug_name", "dose", "route", "time"), "matched")},
])
def test_missing_event_count_rejects_inconsistent_facts(changes):
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=_missing_facts(**changes)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("kind,counter", [
    ("absent", "missing_course_event_count"),
    ("ambiguous", "unresolved_event_count"),
    ("unknown_time", "unknown_time_event_count"),
])
async def test_missing_order_and_other_event_gap_have_disjoint_counts(reverse, kind, counter):
    orders = [ORDER, {**ORDER, "document_id": "synthetic-missing-order",
                      "generic_name": "顺铂", "single_dose_unit": ""}]
    if reverse:
        orders.reverse()
    courses = _course("2026-04-26 使用奥沙利铂130mg 静滴。")
    if kind == "absent":
        courses = _course("2026-04-26 使用紫杉醇130mg 静滴。")
    elif kind == "ambiguous":
        courses += [{**courses[0], "document_id": "synthetic-second-course"}]
    else:
        courses = _course("使用奥沙利铂130mg 静滴。")
    _execution, _reduced, final = await _run(courses, orders=orders)
    assert final["status"] == ("non_compliant" if kind == "absent" else "data_gap")
    if kind == "absent":
        assert "药物名称记录不一致" in final["findings"]
        assert "尚无法核对" in final["findings"]
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == facts[counter] == 1
    assert "matched" not in facts["field_results"].values()
    assert facts["field_results"]["drug_name"] == ("mismatched" if kind == "absent" else "unknown")
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.parametrize("counter", [
    "unresolved_event_count", "missing_course_event_count", "unknown_time_event_count",
])
def test_new_count_expresses_mixed_events_without_relaxing_legacy_contract(counter):
    from app.services.luxian_0609.tumor_pathology_result_mapping import (
        safe_tumor_pathology_customer_display_facts,
        tumor_pathology_customer_fact_status_is_valid,
    )
    raw = _missing_facts(**{counter: 1})
    if counter == "missing_course_event_count":
        raw["field_results"]["drug_name"] = "mismatched"
    legacy = dict(raw)
    del legacy["missing_order_event_count"]
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=legacy) is None
    safe = safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=raw)
    assert safe is not None
    expected = "non_compliant" if counter == "missing_course_event_count" else "data_gap"
    assert tumor_pathology_customer_fact_status_is_valid(rule_id=RULE, status=expected, safe_facts=safe)
    for status in {"compliant", "data_gap", "non_compliant"} - {expected}:
        assert not tumor_pathology_customer_fact_status_is_valid(rule_id=RULE, status=status, safe_facts=safe)


def test_all_missing_events_cannot_claim_an_observed_mismatch():
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    raw = _missing_facts(missing_order_event_count=2)
    raw["field_results"]["dose"] = "mismatched"
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_incomplete_known_drug_keeps_clause_boundary_for_complete_event(reverse):
    orders = [ORDER, {**ORDER, "document_id": "synthetic-missing-order",
                      "generic_name": "顺铂", "single_dose_unit": ""}]
    if reverse:
        orders.reverse()
    _execution, _reduced, final = await _run(
        _course("2026-04-26 使用奥沙利铂120mg 静滴。另予顺铂130mg 静滴。"), orders=orders,
    )
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["field_results"]["dose"] == "mismatched"
    assert final["customer_display_facts"]["missing_order_event_count"] == 1
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_missing_field_does_not_turn_shared_unassociated_clause_into_defect(reverse):
    orders = [ORDER,
              {**ORDER, "document_id": "synthetic-second-order", "generic_name": "顺铂", "single_dose": "150"},
              {**ORDER, "document_id": "synthetic-missing-order", "generic_name": "紫杉醇", "single_dose_unit": ""}]
    if reverse:
        orders.reverse()
    text = "2026-04-26 使用奥沙利铂和顺铂130mg 静滴。"
    _execution, _reduced, final = await _run(_course(text), orders=orders, annotations={text: ()},
                                             coverage_unknown=(text,))
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == 1
    assert facts["unresolved_event_count"] == 2
    assert set(facts["field_results"].values()) == {"unknown"}
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("case,expected,unresolved", [
    ("same_day", "data_gap", 1),
    pytest.param("different_day_explicit", "non_compliant", 0, marks=pytest.mark.business_oracle),
    pytest.param("different_day_relative", "non_compliant", 0, marks=pytest.mark.business_oracle),
    ("different_day_document_time_only", "data_gap", 1),
    ("different_day_submit_only", "data_gap", 1),
    ("different_day_multiple_dates", "data_gap", 1),
    ("missing_name_same_day", "data_gap", 1),
    pytest.param("missing_name_different_day", "non_compliant", 0, marks=pytest.mark.business_oracle),
    ("missing_date", "data_gap", 1),
    ("order_ids_without_course_link", "data_gap", 1),
])
async def test_incomplete_order_remains_possible_owner_unless_identity_or_clinical_date_excludes_it(
    reverse, case, expected, unresolved,
):
    partial = {**ORDER, "document_id": "synthetic-partial-same-drug",
               "single_dose": "150", "single_dose_unit": ""}
    complete = dict(ORDER)
    text = "2026-04-26 使用奥沙利铂120mg 静滴。"
    rows = _course(text)
    if case.startswith("different_day") or case == "missing_name_different_day":
        partial["prescribed_datetime"] = "2026-04-27 09:00:00"
    if case == "different_day_relative":
        rows = _course("今日使用奥沙利铂120mg 静滴。")
    elif case == "different_day_document_time_only":
        rows = _course("使用奥沙利铂120mg 静滴。")
    elif case == "different_day_submit_only":
        rows = _course("今日使用奥沙利铂120mg 静滴。")
        rows[0].pop("record_time")
        rows[0]["submit_datetime"] = "2026-04-26 16:00:00"
    elif case == "different_day_multiple_dates":
        rows = _course("2026-04-26、2026-04-27 使用奥沙利铂120mg 静滴。")
    if case.startswith("missing_name"):
        partial["generic_name"] = ""
    elif case == "missing_date":
        partial["prescribed_datetime"] = ""
    elif case == "order_ids_without_course_link":
        complete["order_id"] = "synthetic-order-A"
        partial["order_id"] = "synthetic-order-B"
    orders = [complete, partial]
    if reverse:
        orders.reverse()
    _execution, _reduced, final = await _run(rows, orders=orders)
    assert final["status"] == expected
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == 1
    assert facts["unresolved_event_count"] == unresolved
    if expected == "data_gap":
        assert set(facts["field_results"].values()) == {"unknown"}
        assert "记录不一致" not in final["findings"]
    else:
        assert facts["field_results"]["dose"] == "mismatched"
        assert "剂量记录不一致" in final["findings"]
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("text", [
    "今日复查血常规，昨日给予奥沙利铂120mg 静滴。",
    "2026-04-26复查血常规，昨日给予奥沙利铂120mg 静滴。",
    "2026-04-26复查血常规。给予奥沙利铂120mg 静滴。",
    "今日复查血常规。给予奥沙利铂120mg 静滴。",
])
async def test_unrelated_date_cannot_exclude_possible_same_drug_order(reverse, text):
    orders = [ORDER, {**ORDER, "document_id": "synthetic-other-day-partial",
                      "single_dose": "150", "single_dose_unit": "",
                      "prescribed_datetime": "2026-04-25 09:00:00"}]
    if reverse:
        orders.reverse()
    annotations = {}
    if "昨日" in text:
        annotations[text] = (fact("昨日给予奥沙利铂120mg 静滴", dose="120mg", route="静滴", date="昨日"),)
    _execution, _reduced, final = await _run(_course(text), orders=orders, annotations=annotations)
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == facts["unresolved_event_count"] == 1
    assert set(facts["field_results"].values()) == {"unknown"}
    assert "记录不一致" not in final["findings"]
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("case,text", [
    ("explicit", "2026-04-26 使用奥沙利铂120mg 静滴。"),
    ("relative", "今日使用奥沙利铂120mg 静滴。"),
    ("unknown_name", "2026-04-26 使用奥沙利铂120mg 静滴。"),
])
async def test_explicit_date_capability_gap_is_reported_without_changing_business_oracle(reverse, case, text):
    """原能力缺口：他日缺字段医嘱现可由该次给药临床日期排除，达到原业务口径不合规。"""
    partial = {**ORDER, "document_id": "synthetic-other-day-partial", "single_dose": "150",
               "single_dose_unit": "", "prescribed_datetime": "2026-04-27 09:00:00"}
    if case == "unknown_name":
        partial["generic_name"] = ""
    orders = [ORDER, partial]
    if reverse:
        orders.reverse()
    _execution, _reduced, final = await _run(_course(text), orders=orders)
    assert final["status"] == "non_compliant"
    facts = final["customer_display_facts"]
    assert facts["missing_order_event_count"] == 1
    assert facts["unresolved_event_count"] == 0
    assert facts["field_results"]["dose"] == "mismatched"
    from test_026_association_contract import assert_sqlite_roundtrip
    assert_sqlite_roundtrip(final)
