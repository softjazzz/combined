from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "build_luxian_0609_0426_synthetic_v2.py"
SPEC = importlib.util.spec_from_file_location("build_luxian_0609_0426_synthetic_v2", SCRIPT_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

DEID_VERSION = module.DEID_VERSION
build_selection = module.build_selection
classify_family = module.classify_family
_deid_text = module._deid_text
add_supplemental_evidence_rows = module.add_supplemental_evidence_rows
is_meaningful_core_document = module.is_meaningful_core_document
transform_row = module.transform_row


def test_classify_family_prefers_lx0609_rule_id() -> None:
    assert classify_family(rule_ids=["LX0609-041"], text="") == "输血"
    assert classify_family(rule_ids=["LX0609-013"], text="普通病程") == "肿瘤病理/化疗"


def test_classify_family_uses_keywords_when_rule_id_missing() -> None:
    assert classify_family(rule_ids=[], text="患者输血后未见疗效评价") == "输血"
    assert classify_family(rule_ids=[], text="病理报告出具后病程未回看") == "肿瘤病理/化疗"


def test_deid_text_replaces_patient_identifiers() -> None:
    source_identity = {
        "patient_name": "张三",
        "mr_no": "MR123456",
        "visit_id": "1883111",
        "patient_id": "P001",
        "doctor_name": "李医生",
        "qc_user": "王质控",
    }
    target_identity = {
        "patient_name": "李某某",
        "mr_no": "LX0609V2-001",
        "visit_id": "LX0609_0426_SYN_001",
        "patient_id": "P-LX0609_0426_SYN_001",
    }
    text = "张三，住院号MR123456，身份证510521196001010011，电话13912345678，李医生记录。"

    result = _deid_text(text, source_identity=source_identity, target_identity=target_identity)

    assert "张三" not in result
    assert "MR123456" not in result
    assert "13912345678" not in result
    assert "510521196001010011" not in result
    assert "李某某" in result
    assert "LX0609V2-001" in result
    assert DEID_VERSION == "local-rule-deid-v1"


def test_core_document_shell_title_should_not_be_meaningful() -> None:
    row = {
        "document_title": "首次病程记录",
        "record_content": "",
    }

    assert is_meaningful_core_document("first_course_record", row) is False


def test_transform_row_should_not_fill_empty_core_content_with_title() -> None:
    class _Column:
        def __init__(self, name: str) -> None:
            self.name = name
            self.type = object()

    class _PrimaryKey:
        columns = []

    class _Table:
        primary_key = _PrimaryKey()
        c = {
            "visit_id": _Column("visit_id"),
            "patient_id": _Column("patient_id"),
            "document_title": _Column("document_title"),
            "record_content": _Column("record_content"),
        }

    case = module.CandidateCase(
        target_index=1,
        family="时限",
        selected_rule_ids=["LX0609-001"],
        source_item={"matched_visit_id": "V1", "patient_name": "张三"},
        source_reason="unit",
        source_status="selected",
        target_visit_id="LX0609_0426_SYN_001",
        target_patient_id="P-LX0609_0426_SYN_001",
        target_mr_no="LX0609V2-001",
        target_patient_name="李某某",
    )

    row, _ = transform_row(
        table=_Table(),
        table_name="first_course_record",
        source_row={"visit_id": "V1", "patient_id": "P1", "document_title": "首次病程记录", "record_content": None},
        case=case,
        row_index=1,
    )

    assert row["record_content"] is None


def test_supplemental_rows_should_add_required_family_evidence() -> None:
    cases = [
        module.CandidateCase(
            target_index=9,
            family="检查检验",
            selected_rule_ids=["LX0609-012", "LX0609-014"],
            source_item={"matched_visit_id": "V9", "department": "骨科"},
            source_reason="unit",
            source_status="selected",
            target_visit_id="LX0609_0426_SYN_009",
            target_patient_id="P-LX0609_0426_SYN_009",
            target_mr_no="LX0609V2-009",
            target_patient_name="李某某",
        ),
        module.CandidateCase(
            target_index=23,
            family="输血",
            selected_rule_ids=["LX0609-041"],
            source_item={"matched_visit_id": "V23", "department": "胃肠外科"},
            source_reason="unit",
            source_status="selected",
            target_visit_id="LX0609_0426_SYN_023",
            target_patient_id="P-LX0609_0426_SYN_023",
            target_mr_no="LX0609V2-023",
            target_patient_name="陈某某",
        ),
        module.CandidateCase(
            target_index=28,
            family="肿瘤病理/化疗",
            selected_rule_ids=["LX0609-013"],
            source_item={"matched_visit_id": "V28", "department": "胃肠外科"},
            source_reason="unit",
            source_status="selected",
            target_visit_id="LX0609_0426_SYN_028",
            target_patient_id="P-LX0609_0426_SYN_028",
            target_mr_no="LX0609V2-028",
            target_patient_name="王某某",
        ),
    ]
    rows_by_table: dict[str, list[dict]] = {}

    supplements = add_supplemental_evidence_rows(rows_by_table, cases)

    assert {item["table"] for item in supplements} == {
        "first_course_record",
        "first_course_record_diagnosis",
        "exam_item_report",
        "labtest_item_report",
        "blood_application",
        "inpat_bill_item",
        "pathology_exam_master",
        "pathology_exam_report",
    }
    assert rows_by_table["exam_item_report"][0]["record_content"]
    assert rows_by_table["blood_application"][0]["record_content"]
    assert rows_by_table["pathology_exam_report"][0]["diagnosis"]
    assert len(rows_by_table["first_course_record"]) == 3
    assert all(
        is_meaningful_core_document("first_course_record", row)
        for row in rows_by_table["first_course_record"]
    )
    assert "腰椎MRI" in rows_by_table["first_course_record"][0]["treatment_plan"]
    assert rows_by_table["first_course_record_diagnosis"][0]["diagnosis_name"] == "腰椎间盘突出症"


def test_build_selection_backfills_to_target_size_when_family_source_gap() -> None:
    source_pool = {"id": "pool-0426", "name": "0426"}
    items = [
        {
            "id": f"item-{index}",
            "row_no": index,
            "matched_visit_id": f"V{index}",
            "manual_issue_text": "会诊意见笼统，后续病程未记录执行情况",
            "candidate_rule_ids": ["LX0609-020"],
            "bundle_status": "ready",
        }
        for index in range(1, 6)
    ]

    selected, summary = build_selection(source_pool=source_pool, source_items=items, target_size=5)

    assert len(selected) == 5
    assert any(case.source_status == "quota_backfill_due_source_gap" for case in selected)
    assert "输血" in summary["source_gaps"]
