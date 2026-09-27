from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "verify_formal_qc_subitem_anchor_output_shape.py"
SPEC = importlib.util.spec_from_file_location("verify_formal_qc_subitem_anchor_output_shape", SCRIPT_PATH)
assert SPEC and SPEC.loader
shape_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shape_module)


def _anchor() -> dict:
    return {
        "rule_id": "SC-070",
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "subitem_id": "SC-070-consultation-not-implemented",
        "subitem_name": "会诊意见落实与医嘱/执行闭环",
        "status": "uncertain",
        "findings": "找到会诊意见，但缺少医嘱/执行清单或病程落实对照，不能确认缺陷。",
        "evidence": "康复科会诊意见：建议予以康复治疗，并遵会诊意见执行。",
        "anchor_evidence_status": "missing_execution_evidence",
        "anchor_evidence": "康复科会诊意见：建议予以康复治疗，并遵会诊意见执行。",
        "anchor_decision_reason": "找到会诊意见，但缺少医嘱/执行清单或病程落实对照，不能确认缺陷。",
        "display_status": "data_quality_gap",
        "display_bucket": "数据缺口",
        "can_show_as_defect": False,
        "internal_only": False,
        "metadata": {
            "formal_subitem_anchor": True,
            "anchor_id": "SC-070-consultation-not-implemented",
        },
    }


def test_output_shape_should_preserve_required_subitem_anchor_fields():
    anchor = _anchor()
    parent_meta = shape_module._parent_metadata_by_rule([anchor])["SC-070"]

    row = shape_module.assess_anchor_output_shape(
        visit_id="2268187",
        patient_id="p1",
        patient_name="代云聪",
        anchor=anchor,
        parent_metadata=parent_meta,
    )

    assert row["anchor_id"] == "SC-070-consultation-not-implemented"
    assert row["subitem_id"] == "SC-070-consultation-not-implemented"
    assert row["subitem_name"] == "会诊意见落实与医嘱/执行闭环"
    assert row["anchor_evidence_status"] == "missing_execution_evidence"
    assert row["display_status"] == "data_quality_gap"
    assert row["can_show_as_defect"] == "False"
    assert row["field_loss_risk"] == "False"
    assert row["metadata_has_anchor"] == "True"


def test_output_shape_should_neutralize_anchor_even_if_input_marks_defect():
    anchor = _anchor()
    anchor["display_status"] = "confirmed_defect"
    anchor["display_bucket"] = "确认缺陷"
    anchor["can_show_as_defect"] = True
    parent_meta = shape_module._parent_metadata_by_rule([anchor])["SC-070"]

    row = shape_module.assess_anchor_output_shape(
        visit_id="2268187",
        patient_id="p1",
        patient_name="代云聪",
        anchor=anchor,
        parent_metadata=parent_meta,
    )

    assert row["display_status"] == "qc_review_candidate"
    assert row["can_show_as_defect"] == "False"
    assert row["doctor_display_risk"] == "False"
    assert row["anchor_display_safety"] == "safe_for_review_bucket"


def test_output_csv_should_include_required_shape_fields(tmp_path):
    row = {
        "visit_id": "2268187",
        "patient_id": "p1",
        "patient_name": "代云聪",
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "display_status": "data_quality_gap",
        "can_show_as_defect": "False",
        "field_loss_risk": "False",
    }
    output = tmp_path / "shape.csv"

    shape_module._write_csv(output, [row])

    with output.open("r", encoding="utf-8", newline="") as f:
        saved = list(csv.DictReader(f))
    assert saved[0]["anchor_id"] == "SC-070-consultation-not-implemented"
    assert "can_show_as_defect" in saved[0]
