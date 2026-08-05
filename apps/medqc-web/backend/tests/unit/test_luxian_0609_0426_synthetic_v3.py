from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
)
from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609 import native_mdt_execution
from app.services.luxian_0609.decision_model import QcDirection
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
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
    assert module.V2.TARGET_SCENE == "final"
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
    assert len(answers) == 134
    assert len({answer["qc_point_id"] for answer in answers}) == 75
    assert all(answer["expected_status"] != "pending" for answer in answers)
    assert all(answer["evidence_refs"] for answer in answers)
    assert {answer["acceptance_tier"] for answer in answers} == {"formal", "provisional"}
    matrix = module.build_validation_matrix(cases)
    assert len(matrix) == 134
    assert Counter(row["acceptance_tier"] for row in matrix) == {
        "formal": 123,
        "provisional": 11,
    }
    statuses_by_rule = {
        rule_id: {
            row["expected_status"] for row in matrix if row["rule_id"] == rule_id
        }
        for rule_id in ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015")
    }
    assert all(statuses == {"compliant", "non_compliant"} for statuses in statuses_by_rule.values())
    timeliness_statuses = {
        rule_id: {
            row["expected_status"] for row in matrix if row["rule_id"] == rule_id
        }
        for rule_id in (
            "LX0609-001",
            "LX0609-002",
            "LX0609-004",
            "LX0609-005",
            "LX0609-006",
        )
    }
    assert all(
        statuses == {"compliant", "non_compliant"}
        for statuses in timeliness_statuses.values()
    )
    transfusion_statuses = {
        rule_id: {
            row["expected_status"] for row in matrix if row["rule_id"] == rule_id
        }
        for rule_id in (
            "LX0609-041",
            "LX0609-042",
            "LX0609-043",
            "LX0609-044",
            "LX0609-045",
            "LX0609-046",
            "LX0609-047",
            "LX0609-048",
        )
    }
    assert all(
        statuses == {"compliant", "non_compliant"}
        for statuses in transfusion_statuses.values()
    )
    for rule_ids in (
        ("LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"),
        ("LX0609-054", "LX0609-055", "LX0609-057", "LX0609-058"),
        ("LX0609-071", "LX0609-072", "LX0609-073", "LX0609-074"),
    ):
        assert all(
            {
                row["expected_status"]
                for row in matrix
                if row["rule_id"] == rule_id
            }
            == {"compliant", "non_compliant"}
            for rule_id in rule_ids
        )

    for rule_id in ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-069"):
        assert {
            row["expected_status"]
            for row in matrix
            if row["rule_id"] == rule_id
        } == {"compliant", "non_compliant", "not_applicable"}


def test_v3_gold_acceptance_contracts_freeze_37_reviewed_assertions() -> None:
    contracts = module.build_gold_acceptance_contracts()

    assert len(contracts) == 37
    assert len({row["rule_id"] for row in contracts}) == 37
    assert len(
        {(row["case_index"], row["rule_id"]) for row in contracts}
    ) == 37
    assert all(
        {
            "case_index",
            "fixture_ref",
            "rule_id",
            "expected_status",
            "expected_reason_code",
            "trigger_facts",
            "required_sources",
            "expected_evidence_roles",
        }
        <= row.keys()
        for row in contracts
    )
    assert all(row["trigger_facts"] for row in contracts)
    assert all(row["required_sources"] for row in contracts)
    assert all(row["expected_evidence_roles"] for row in contracts)

    case_017 = next(row for row in contracts if row["rule_id"] == "LX0609-017")
    assert case_017["case_index"] == 6
    assert case_017["expected_status"] == "compliant"
    assert case_017["expected_reason_code"] == "copy_similarity_within_threshold"


def test_v3_full_validation_freezes_all_38_records_as_complete_final_stays() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    audit = module.upgrade_full_validation_evidence(rows_by_table, cases)

    registrations = rows_by_table["inpat_registration"]
    assert len(registrations) == 38
    assert {row["visit_id"] for row in registrations} == {
        case.target_visit_id for case in cases
    }
    assert all(row["admission_datetime"] < row["discharge_datetime"] for row in registrations)
    assert audit["timeline"]["record_scene"] == "final"
    assert audit["timeline"]["case_count"] == 38
    assert audit["timeline"]["validated_event_row_count"] > 0
    assert audit["timeline"]["issue_count"] == 0


def test_v3_timeline_removes_cross_stay_events_but_keeps_history_fields() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    case = next(item for item in cases if item.target_index == 2)
    rows_by_table: dict[str, list[dict]] = {
        "mr_surgery": [
            {
                "visit_id": case.target_visit_id,
                "surgery_id": "stale-surgery",
                "surgery_begin_datetime": module.datetime(2025, 10, 1, 9, 0),
                "surgery_end_datetime": module.datetime(2025, 10, 1, 11, 0),
            },
            {
                "visit_id": case.target_visit_id,
                "surgery_id": "future-surgery",
                "surgery_begin_datetime": module.datetime(2026, 7, 1, 9, 0),
                "surgery_end_datetime": module.datetime(2026, 7, 1, 11, 0),
            },
        ],
        "medical_record_frontpage": [
            {
                "visit_id": case.target_visit_id,
                "frontpage_id": "current-frontpage",
                "past_surgery_datetime": module.datetime(2025, 10, 1, 9, 0),
                "record_time": module.datetime(2026, 6, 2, 9, 0),
            }
        ],
    }

    audit = module.upgrade_full_validation_evidence(rows_by_table, cases)

    assert {"stale-surgery", "future-surgery"}.isdisjoint({
        row.get("surgery_id") for row in rows_by_table["mr_surgery"]
    })
    assert [row["frontpage_id"] for row in rows_by_table["medical_record_frontpage"]] == [
        "current-frontpage"
    ]
    assert audit["timeline"]["removed_out_of_window_rows"] == 2
    assert audit["timeline"]["removed_by_table"] == {"mr_surgery": 2}


def test_v3_case_006_course_notes_are_genuinely_distinct_and_below_70_percent() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_full_validation_evidence(rows_by_table, cases)

    texts = [
        row["record_content"]
        for row in rows_by_table["daily_course_record"]
        if row["visit_id"] == "LX0609_0426_SYN_V3_006"
    ]
    assert len(texts) == 4
    assert any("症状" in text for text in texts)
    assert any("检查" in text for text in texts)
    assert any("调整" in text for text in texts)
    assert any("疗效" in text for text in texts)

    normalized = [re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text).lower() for text in texts]
    maximum = max(
        SequenceMatcher(None, left, right, autojunk=False).ratio()
        for index, left in enumerate(normalized)
        for right in normalized[index + 1 :]
    )
    assert maximum <= 0.70


def test_v3_020_explains_actual_multidisciplinary_participation() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_full_validation_evidence(rows_by_table, cases)

    discussion = next(
        row
        for row in rows_by_table["presurg_discussion"]
        if row["visit_id"] == "LX0609_0426_SYN_V3_020"
    )
    content = discussion["record_content"]
    assert "外科陈某医师" in content
    assert "麻醉科李某医师" in content
    assert "影像科王某医师" in content
    assert "实际参加" in content
    assert "经多学科讨论后一致认为" in content
    assert "可实施手术" in content


@pytest.mark.asyncio
async def test_v3_020_mdt_executes_programmatically_as_compliant() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    visit_id = "LX0609_0426_SYN_V3_020"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[
                row
                for row in rows_by_table.get(source_key, [])
                if row.get("visit_id") == visit_id
            ],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-040",),
        institute_id="I",
        patient_id="P",
        visit_id=visit_id,
        source_schema=None,
        created_at="2026-08-03T09:00:00+08:00",
        row_reader=read,
        additional_source_keys=(
            "mr_surgery",
            "presurg_discussion",
            "consultation_record",
        ),
    )

    class FailIfCalled:
        async def generate(self, _prompt: str) -> dict:
            raise AssertionError("明确的多学科参与事实不得调用 LLM")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id=visit_id,
        source_schema=None,
        llm_client=FailIfCalled(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-040",),
    )

    assert execution.llm_call_count == 0
    assert execution.decisions[0].qc_direction is QcDirection.SATISFIED
    assert dict(execution.customer_display_facts)["LX0609-040"][
        "mdt_discussion_state"
    ] == "completed"


def test_v3_full_validation_upgrade_supplies_course_gate_facts_for_every_case() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_full_validation_evidence(rows_by_table, cases)

    registration_counts = Counter(
        row.get("visit_id") for row in rows_by_table.get("inpat_registration", [])
    )
    assert registration_counts == Counter(
        {case.target_visit_id: 1 for case in cases}
    )

    severe_case = next(case for case in cases if case.target_index == 6)
    severe_registration = next(
        row
        for row in rows_by_table["inpat_registration"]
        if row.get("visit_id") == severe_case.target_visit_id
    )
    assert severe_registration["discharge_datetime"] is not None

    critical_case = next(case for case in cases if case.target_index == 7)
    critical_order = next(
        row
        for row in rows_by_table["inpat_nondrug_order"]
        if row.get("visit_id") == critical_case.target_visit_id
    )
    critical_day_zero = next(
        row
        for row in rows_by_table["daily_course_record"]
        if row.get("visit_id") == critical_case.target_visit_id
        and row.get("document_id") == f"{critical_case.target_visit_id}-course-0"
    )
    assert critical_day_zero["record_time"] > critical_order["prescribed_datetime"]

    stable_case = next(case for case in cases if case.target_index == 5)
    primary_diagnosis = next(
        row
        for row in rows_by_table["admission_record_diagnosis"]
        if row.get("visit_id") == stable_case.target_visit_id
        and row.get("diagnosis_main") == "1"
    )
    assert primary_diagnosis["diagnosis_type"] == "入院诊断"


def test_v3_surgery_cases_replace_cloned_events_with_one_authoritative_event() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    surgery_cases = {
        case.target_index: case for case in cases if 17 <= case.target_index <= 22
    }
    inherited_visit = surgery_cases[21].target_visit_id
    rows_by_table: dict[str, list[dict]] = {
        "mr_surgery": [
            {"visit_id": inherited_visit, "surgery_id": "legacy-1"},
            {"visit_id": inherited_visit, "surgery_id": "legacy-2"},
        ],
        "rescue_record": [
            {"visit_id": surgery_cases[20].target_visit_id, "document_id": "legacy-rescue"},
        ],
    }

    module.upgrade_full_validation_evidence(rows_by_table, cases)

    for case_index in range(17, 22):
        visit_id = surgery_cases[case_index].target_visit_id
        mr_rows = [
            row for row in rows_by_table["mr_surgery"] if row.get("visit_id") == visit_id
        ]
        record = next(
            row
            for row in rows_by_table["surgery_record"]
            if row.get("visit_id") == visit_id
        )
        assert len(mr_rows) == 1
        assert mr_rows[0]["surgery_id"] == record["surgery_id"]
        assert mr_rows[0]["surgical_level"] == "4"

    procedure_visit = surgery_cases[22].target_visit_id
    assert not any(
        row.get("visit_id") == procedure_visit for row in rows_by_table["mr_surgery"]
    )
    assert not any(
        row.get("visit_id") == surgery_cases[20].target_visit_id
        for row in rows_by_table.get("rescue_record", [])
    )

    implant_record = next(
        row
        for row in rows_by_table["surgery_record"]
        if row.get("visit_id") == surgery_cases[17].target_visit_id
    )
    for label in ("植入物名称", "种类", "规格/型号", "材质", "数量", "植入物条码"):
        assert label in implant_record["record_content"]


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
    status, reason, facts = transfusion._programmatic_042_status(
        {
            "consent_form": [consent],
            "__logical_source_states__": {"consent_form": "available"},
        }
    )
    assert (status, reason) == ("compliant", "transfusion_consent_complete")
    assert facts and set(facts["checked_fields"]) >= {
        "indication",
        "component",
        "risks",
        "alternatives",
        "patient_or_agent_signature",
        "physician_signature",
        "signed_time",
    }

    fake_rows = [
        row
        for row in rows_by_table.get("surgery_inform_consent", [])
        if row.get("visit_id") == transfusion_case.target_visit_id
        and row.get("document_title") == "输血知情同意书"
    ]
    assert fake_rows == []


def test_v3_transfusion_and_tumor_surgery_records_are_current_stay_structured_events() -> None:
    """048、病理场景中的手术资料不能退化为无结构化时间的文本占位。"""

    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}

    module.upgrade_full_validation_evidence(rows_by_table, cases)

    cases_by_index = {case.target_index: case for case in cases}
    registrations = {
        row["visit_id"]: row
        for row in rows_by_table["inpat_registration"]
    }
    for case_index in (*range(23, 28), 28, 29):
        visit_id = cases_by_index[case_index].target_visit_id
        surgery_record = next(
            row
            for row in rows_by_table["surgery_record"]
            if row.get("visit_id") == visit_id
        )
        surgery_event = next(
            row
            for row in rows_by_table["mr_surgery"]
            if row.get("visit_id") == visit_id
        )
        admission = registrations[visit_id]["admission_datetime"]
        discharge = registrations[visit_id]["discharge_datetime"]

        assert surgery_record["surgery_id"] == surgery_event["surgery_id"]
        assert surgery_record["surgery_name"] == surgery_event["surgery_name"]
        assert surgery_event["surgery_begin_datetime"] < surgery_event["surgery_end_datetime"]
        assert admission <= surgery_event["surgery_begin_datetime"]
        assert surgery_event["surgery_end_datetime"] <= discharge

    assert "术中输注悬浮红细胞2U" in next(
        row["record_content"]
        for row in rows_by_table["surgery_record"]
        if row.get("visit_id") == cases_by_index[23].target_visit_id
    )
    assert "胃癌根治术" in next(
        row["record_content"]
        for row in rows_by_table["surgery_record"]
        if row.get("visit_id") == cases_by_index[28].target_visit_id
    )


def test_transfusion_complete_case_has_reviewable_process_and_24h_evaluation() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    visit_id = next(case.target_visit_id for case in cases if case.target_index == 23)

    course = next(
        row
        for row in rows_by_table["bloodtrans_record"]
        if row.get("visit_id") == visit_id
    )
    assert transfusion._is_complete_transfusion_course_entry(course["record_content"])

    evaluation = next(
        row
        for row in rows_by_table["daily_course_record"]
        if row.get("visit_id") == visit_id
        and row.get("document_title") == "输血后评价记录"
    )
    assert "输血结束时间" in evaluation["record_content"]
    assert "输血后评价时间" in evaluation["record_content"]
    assert "复查Hb 82g/L" in evaluation["record_content"]
    event = next(
        row
        for row in rows_by_table.get("mr_bloodtrans", [])
        if row.get("visit_id") == visit_id
    )
    assert event["transfution_datetime"]
    assert event["transfuse_variety"] == "悬浮红细胞"
    status, reason, facts = transfusion.evaluate_pretransfusion_nine_items(
        {
            "mr_bloodtrans": [event],
            "labtest_item_report": [
                row
                for row in rows_by_table["labtest_item_report"]
                if row.get("visit_id") == visit_id
            ],
            "blood_application": [
                row
                for row in rows_by_table["blood_application"]
                if row.get("visit_id") == visit_id
            ],
            "__logical_source_states__": {
                "labtest_item_report": "available",
            },
        }
    )
    assert (status, reason) == ("compliant", "pretransfusion_items_complete")
    assert facts and len(facts["checked_items"]) == 9


def test_transfusion_issue_variants_have_distinct_reviewable_defects() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    visit_ids = {
        index: next(case.target_visit_id for case in cases if case.target_index == index)
        for index in range(24, 28)
    }

    assert not any(
        row.get("visit_id") == visit_ids[24]
        for row in rows_by_table.get("consent_form", [])
    )
    incomplete_consent = next(
        row
        for row in rows_by_table["consent_form"]
        if row.get("visit_id") == visit_ids[25]
    )
    assert not incomplete_consent.get("patient_sign")
    assert not any(
        row.get("visit_id") == visit_ids[25]
        and str(row.get("item_abbreviation") or "").upper() == "ALT"
        for row in rows_by_table["labtest_item_report"]
    )
    incomplete_assessment = next(
        row
        for row in rows_by_table["bloodtrans_record"]
        if row.get("visit_id") == visit_ids[25]
    )
    assert "未记录输血前评估" in incomplete_assessment["record_content"]
    assert transfusion._programmatic_044_status(
        {
            "bloodtrans_record": [incomplete_assessment],
            "blood_application": [
                row
                for row in rows_by_table["blood_application"]
                if row.get("visit_id") == visit_ids[25]
            ],
            "daily_course_record": [
                row
                for row in rows_by_table["daily_course_record"]
                if row.get("visit_id") == visit_ids[25]
            ],
        }
    ) == ("non_compliant", "pretransfusion_assessment_missing")
    missing_item_status = transfusion.evaluate_pretransfusion_nine_items(
        {
            "mr_bloodtrans": [
                row
                for row in rows_by_table["mr_bloodtrans"]
                if row.get("visit_id") == visit_ids[25]
            ],
            "labtest_item_report": [
                row
                for row in rows_by_table["labtest_item_report"]
                if row.get("visit_id") == visit_ids[25]
            ],
            "__logical_source_states__": {
                "labtest_item_report": "available",
            },
        }
    )
    assert missing_item_status[:2] == (
        "non_compliant",
        "pretransfusion_items_incomplete",
    )
    assert missing_item_status[2] and missing_item_status[2]["missing_items"] == [
        "alt"
    ]
    missing_course = next(
        row
        for row in rows_by_table.get("bloodtrans_record", [])
        if row.get("visit_id") == visit_ids[26]
    )
    assert "未记录输血病程主要内容" in missing_course["record_content"]
    assert "未记录输血结束后评价" in missing_course["record_content"]
    assert any(
        row.get("visit_id") == visit_ids[26]
        for row in rows_by_table.get("mr_bloodtrans", [])
    )
    assert transfusion._programmatic_045_status(
        {
            "bloodtrans_record": [missing_course],
            "__logical_source_states__": {"bloodtrans_record": "available"},
        }
    ) == ("non_compliant", "transfusion_course_record_missing")
    assert transfusion._programmatic_047_status(
        {"bloodtrans_record": [missing_course], "daily_course_record": []}
    ) == ("non_compliant", "posttransfusion_evaluation_missing")
    incomplete_course = next(
        row
        for row in rows_by_table["bloodtrans_record"]
        if row.get("visit_id") == visit_ids[27]
    )
    assert transfusion._programmatic_046_status(
        {"bloodtrans_record": [incomplete_course]}
    ) == ("non_compliant", "transfusion_course_record_incomplete")
    inconsistent_contents = {
        table_name: next(
            row["record_content"]
            for row in rows_by_table[table_name]
            if row.get("visit_id") == visit_ids[27]
        )
        for table_name in (
            "surgery_record",
            "anesthesia_record",
            "postsurg_firstcourse_record",
        )
    }
    assert len(set(inconsistent_contents.values())) == 3


def test_tumor_antimicrobial_and_transfer_issue_variants_change_source_facts() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    visit_id = {
        index: next(case.target_visit_id for case in cases if case.target_index == index)
        for index in (29, 35, 37, 38)
    }

    tumor_course = "\n".join(
        row["record_content"]
        for row in rows_by_table["daily_course_record"]
        if row.get("visit_id") == visit_id[29]
    )
    assert "病理报告" not in tumor_course
    assert "奥沙利铂100mg/m²" in tumor_course
    assert not any(
        row.get("visit_id") == visit_id[35]
        for row in rows_by_table.get("consultation_record", [])
    )
    antimicrobial_orders = [
        row
        for row in rows_by_table.get("inpat_drug_order", [])
        if row.get("visit_id") == visit_id[35]
    ]
    assert antimicrobial_orders
    assert all(
        "经验性启用" in str(row.get("record_content") or "")
        for row in antimicrobial_orders
    )
    assert not any(
        row.get("visit_id") == visit_id[35]
        for table_name in ("daily_course_record", "senior_course_record")
        for row in rows_by_table.get(table_name, [])
    )
    assert not any(
        row.get("visit_id") == visit_id[37]
        for row in rows_by_table.get("handoff_record", [])
    )
    assert not any(
        row.get("visit_id") == visit_id[38]
        for table_name in ("transfer_out_record", "transfer_in_record")
        for row in rows_by_table.get(table_name, [])
    )


def test_consultation_cases_do_not_inherit_uncontrolled_senior_course_rows() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    consultation_visits = {
        case.target_visit_id for case in cases if case.target_index in {13, 14}
    }

    assert not any(
        row.get("visit_id") in consultation_visits
        for row in rows_by_table.get("senior_course_record", [])
    )


def test_transfer_complete_case_has_explicit_physician_change_trigger() -> None:
    module._configure_v2_compatibility()
    cases = _all_v3_cases()
    rows_by_table: dict[str, list[dict]] = {}
    module.upgrade_full_validation_evidence(rows_by_table, cases)
    visit_id = next(case.target_visit_id for case in cases if case.target_index == 36)

    change_order = next(
        row
        for row in rows_by_table["inpat_nondrug_order"]
        if row.get("visit_id") == visit_id
        and row.get("order_name") == "经治医师变更"
    )
    assert change_order["prescribed_datetime"]
    assert "陈某医师" in change_order["record_content"]
    assert "李某医师" in change_order["record_content"]
