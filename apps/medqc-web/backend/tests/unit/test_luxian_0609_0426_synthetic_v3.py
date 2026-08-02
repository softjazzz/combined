from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "build_luxian_0609_0426_synthetic_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_luxian_0609_0426_synthetic_v3",
    SCRIPT_PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _case(index: int, family: str):
    return module.V2.CandidateCase(
        target_index=index,
        family=family,
        selected_rule_ids=[],
        source_item={"matched_visit_id": f"SOURCE-{index}"},
        source_reason="unit",
        source_status="selected",
        target_visit_id=f"LX0609_0426_SYN_V3_{index:03d}",
        target_patient_id=f"P-LX0609_0426_SYN_V3_{index:03d}",
        target_mr_no=f"LX0609V3-{index:03d}",
        target_patient_name="李某某",
    )


def _all_v3_cases():
    cases = []
    index = 1
    for family, quota in module.FAMILY_QUOTAS.items():
        for _ in range(quota):
            cases.append(_case(index, family))
            index += 1
    return cases


def test_v3_family_projection_covers_the_unique_75_rule_master() -> None:
    all_rules = module.build_master_family_rule_ids()
    active_rules = module.build_master_family_rule_ids(statuses={"active"})

    flattened_all = [rule_id for rules in all_rules.values() for rule_id in rules]
    flattened_active = [rule_id for rules in active_rules.values() for rule_id in rules]
    assert len(flattened_all) == len(set(flattened_all)) == 75
    assert len(flattened_active) == len(set(flattened_active)) == 75
    assert "LX0609-052" in all_rules["检查检验"]
    assert "LX0609-052" in active_rules["检查检验"]
    assert "LX0609-075" in all_rules["手术麻醉"]
    assert "LX0609-075" in active_rules["手术麻醉"]


def test_v3_coverage_ledger_never_activates_ready_or_pending_rules() -> None:
    raw_cases = [
        _case(index, family)
        for index, family in enumerate(module.FAMILY_QUOTAS, start=1)
    ]
    cases = module._assign_full_active_family_scope(raw_cases)

    ledger = module.build_coverage_ledger(cases)
    counts = Counter(row["coverage_status"] for row in ledger)

    assert len(ledger) == 75
    assert counts == {"assigned_pending_golden_review": 75}
    assert all(
        row["candidate_visit_ids"]
        for row in ledger
        if row["implementation_status"] == "active"
    )
    assert all(
        not row["candidate_visit_ids"]
        for row in ledger
        if row["implementation_status"] == "pending_definition"
    )


def test_v3_compatibility_configuration_keeps_v2_logic_but_uses_v3_identity() -> None:
    module._configure_v2_compatibility()

    assert module.V2.TARGET_POOL_ID == "luxian-0609-0426-syn-v3"
    assert module.V2.TARGET_VISIT_PREFIX == "LX0609_0426_SYN_V3_"
    assert module.V2.TARGET_MR_PREFIX == "LX0609V3-"
    assert module.V2.TARGET_ITEM_PREFIX == "lx0609-v3"
    assert module.V2.BUNDLE_POLICY_VERSION == "luxian_0609_0426_syn_v3"
    assert sum(module.V2.FAMILY_QUOTAS.values()) == 38
    assert len(
        {
            rule_id
            for rule_ids in module.V2.FAMILY_RULE_IDS.values()
            for rule_id in rule_ids
        }
    ) == 75


def test_v3_exam_lab_upgrade_builds_rich_grouped_reports_with_complete_links() -> None:
    module._configure_v2_compatibility()
    cases = [_case(index, "检查检验") for index in range(9, 13)]
    rows_by_table: dict[str, list[dict]] = {}

    audit = module.upgrade_exam_lab_evidence(rows_by_table, cases)

    assert audit["case_count"] == 4
    assert audit["exam_master_count"] == 8
    assert audit["exam_report_count"] == 8
    assert audit["lab_master_count"] == 16
    assert audit["lab_item_count"] >= 100
    exam_ids = {row["exam_id"] for row in rows_by_table["exam_master"]}
    assert {row["exam_id"] for row in rows_by_table["exam_item_report"]} == exam_ids
    test_ids = {row["test_id"] for row in rows_by_table["labtest_master"]}
    assert {row["test_id"] for row in rows_by_table["labtest_item_report"]} == test_ids
    assert all(row.get("report_time") for row in rows_by_table["exam_item_report"])
    assert all(row.get("report_time") for row in rows_by_table["labtest_item_report"])
    assert all(
        row["request_datetime"] < row["report_datetime"]
        for row in rows_by_table["labtest_master"]
    )

    for case in cases:
        case_rows = {
            table_name: [
                row for row in rows if row.get("visit_id") == case.target_visit_id
            ]
            for table_name, rows in rows_by_table.items()
        }
        projection = build_exam_lab_text_projection(rows_by_source=case_rows)
        assert projection.imaging_event is not None
        assert projection.imaging_event.positive_hint == "positive"
        assert not projection.imaging_event.conflict_roles
        assert projection.culture_event is not None
        assert projection.culture_event.positive_hint == "positive"
        assert not projection.culture_event.conflict_roles


def test_v3_exam_lab_upgrade_contains_paired_course_and_critical_value_scenarios() -> None:
    module._configure_v2_compatibility()
    cases = [_case(index, "检查检验") for index in range(9, 13)]
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_exam_lab_evidence(rows_by_table, cases)

    course_texts = {
        visit_id: "\n".join(
            row["record_content"]
            for row in rows_by_table["daily_course_record"]
            if row["visit_id"] == visit_id
        )
        for visit_id in (case.target_visit_id for case in cases)
    }
    assert "为明确腰椎神经受压" in course_texts[cases[0].target_visit_id]
    assert "结合症状分析" in course_texts[cases[0].target_visit_id]
    assert course_texts[cases[1].target_visit_id] == ""
    assert "已查看腰椎MRI报告" in course_texts[cases[2].target_visit_id]
    assert "结合症状分析" not in course_texts[cases[2].target_visit_id]
    critical_flags = {
        row["visit_id"]: row["abnormal_indicator"]
        for row in rows_by_table["labtest_item_report"]
        if row.get("abnormal_indicator") in {"PL", "PH"}
    }
    assert critical_flags == {
        cases[2].target_visit_id: "PL",
        cases[3].target_visit_id: "PH",
    }
    assert [row["visit_id"] for row in rows_by_table["crisis_value_record"]] == [
        cases[3].target_visit_id
    ]


def test_v3_exam_lab_upgrade_attaches_reviewable_expected_results() -> None:
    module._configure_v2_compatibility()
    cases = [_case(index, "检查检验") for index in range(9, 13)]
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_exam_lab_evidence(rows_by_table, cases)

    expectations = {
        case.target_visit_id: {
            row["qc_point_id"]: row["expected_status"]
            for row in case.source_item["synthetic_golden_answers"]
        }
        for case in cases
    }
    assert expectations[cases[0].target_visit_id]["LX0609-010"] == "compliant"
    assert expectations[cases[1].target_visit_id]["LX0609-010"] == "non_compliant"
    assert expectations[cases[2].target_visit_id]["LX0609-012"] == "non_compliant"
    assert expectations[cases[2].target_visit_id]["LX0609-052"] == "non_compliant"
    assert expectations[cases[3].target_visit_id]["LX0609-052"] == "compliant"


def test_v3_full_validation_upgrade_assigns_all_rules_and_preserves_real_status_variants() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    audit = module.upgrade_full_validation_evidence(rows_by_table, cases)

    answers = [
        answer
        for case in cases
        for answer in case.source_item.get("synthetic_golden_answers") or []
    ]
    assert audit["rule_count"] == 75
    assert len(answers) == 96
    assert len({answer["qc_point_id"] for answer in answers}) == 75
    assert all(answer["expected_status"] != "pending" for answer in answers)
    assert all(answer["evidence_refs"] for answer in answers)
    assert {answer["acceptance_tier"] for answer in answers} == {"formal", "provisional"}
    matrix = module.build_validation_matrix(cases)
    assert len(matrix) == 96
    assert Counter(row["acceptance_tier"] for row in matrix) == {
        "formal": 88,
        "provisional": 8,
    }
    statuses_by_rule = {
        rule_id: {
            row["expected_status"] for row in matrix if row["rule_id"] == rule_id
        }
        for rule_id in ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015")
    }
    assert all(statuses == {"compliant", "non_compliant"} for statuses in statuses_by_rule.values())


def test_transfusion_case_uses_typed_consent_form() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    transfusion_case = next(case for case in cases if case.target_index == 23)

    typed_rows = [
        row
        for row in rows_by_table.get("consent_form", [])
        if row.get("visit_id") == transfusion_case.target_visit_id
    ]
    assert len(typed_rows) == 1
    consent = typed_rows[0]
    assert consent["document_title"] == "输血知情同意书"
    assert consent["consent_type"] == "blood_transfusion"
    assert consent["patient_sign"]
    assert consent["physician_sign"]
    assert consent["patient_sign_datetime"]
    assert consent["physician_sign_datetime"]

    fake_rows = [
        row
        for row in rows_by_table.get("surgery_inform_consent", [])
        if row.get("visit_id") == transfusion_case.target_visit_id
        and row.get("document_title") == "输血知情同意书"
    ]
    assert fake_rows == []
