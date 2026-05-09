from __future__ import annotations

from app.services.formal_qc_subitem_anchors import (
    attach_subitem_anchors_to_parent_results,
    evaluate_formal_qc_p0_subitem_anchors,
)


def _bundle_with_docs(documents: dict[str, list[dict]]) -> dict:
    return {
        "structured_context": {
            "documents": documents,
        },
        "document_hits": {key: bool(value) for key, value in documents.items()},
    }


def test_sc009_trauma_location_should_not_emit_anchor_when_scene_and_mechanism_exist():
    bundle = _bundle_with_docs(
        {
            "admission_record": [
                {
                    "history_of_present_illness": "患者1小时前在家里用电剪子剪花椒丫时损伤左手示指，院外未做处理，急诊入院。"
                }
            ]
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)

    assert not [item for item in anchors if item["anchor_id"] == "SC-009-trauma-location"]


def test_sc009_trauma_location_missing_scene_should_emit_needs_review_anchor():
    bundle = _bundle_with_docs(
        {
            "admission_record": [
                {
                    "history_of_present_illness": "患者1小时前外伤致左手疼痛出血，院外未做处理后急诊入院。"
                }
            ]
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)
    trauma = [item for item in anchors if item["anchor_id"] == "SC-009-trauma-location"]

    assert len(trauma) == 1
    assert trauma[0]["parent_rule_id"] == "SC-009"
    assert trauma[0]["display_status"] == "needs_review"
    assert trauma[0]["can_show_as_defect"] is False
    assert "受伤地点/场景" in trauma[0]["anchor_decision_reason"]


def test_sc009_post_injury_outside_hospital_should_not_count_as_scene():
    bundle = _bundle_with_docs(
        {
            "admission_record": [
                {
                    "history_of_present_illness": "患者外伤致腰部疼痛2小时，院外未予特殊处理，家属送入我院急诊。"
                }
            ]
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)
    trauma = [item for item in anchors if item["anchor_id"] == "SC-009-trauma-location"]

    assert len(trauma) == 1
    assert "受伤地点/场景" in trauma[0]["anchor_decision_reason"]


def test_sc036_without_abnormal_result_should_not_emit_anchor():
    bundle = _bundle_with_docs(
        {
            "daily_course_record": [
                {"record_content": "今日查房，患者一般情况可，继续当前治疗。"}
            ]
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)

    assert not [item for item in anchors if item["anchor_id"] == "SC-036-abnormal-result-unaddressed"]


def test_sc036_with_abnormal_result_and_course_should_emit_needs_review_not_defect():
    bundle = _bundle_with_docs(
        {
            "labtest_item_report": [
                {"item_name": "血钾", "result": "2.9mmol/L", "abnormal_flag": "L"}
            ],
            "daily_course_record": [
                {"record_content": "今日查房，患者一般情况可，继续治疗，明日复查。"}
            ],
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)
    abnormal = [item for item in anchors if item["anchor_id"] == "SC-036-abnormal-result-unaddressed"]

    assert len(abnormal) == 1
    assert abnormal[0]["display_status"] == "needs_review"
    assert abnormal[0]["can_show_as_defect"] is False
    assert "异常" in abnormal[0]["anchor_decision_reason"] or "异常" in abnormal[0]["anchor_evidence"]


def test_sc070_missing_execution_evidence_should_emit_data_gap_not_defect():
    bundle = _bundle_with_docs(
        {
            "consultation_record": [
                {"record_content": "康复科会诊意见：建议予以康复治疗，并遵会诊意见执行。"}
            ]
        }
    )

    anchors = evaluate_formal_qc_p0_subitem_anchors(bundle=bundle)
    consult = [item for item in anchors if item["anchor_id"] == "SC-070-consultation-not-implemented"]

    assert len(consult) == 1
    assert consult[0]["display_status"] == "data_quality_gap"
    assert consult[0]["can_show_as_defect"] is False
    assert consult[0]["postprocess_label"] == "data_gap_not_defect"


def test_attach_subitem_anchors_should_keep_result_count_and_add_parent_metadata():
    results = [{"rule_id": "SC-009", "status": "compliant", "metadata": {}}]
    anchors = [
        {
            "parent_rule_id": "SC-009",
            "anchor_id": "SC-009-trauma-location",
            "subitem_id": "SC-009-trauma-location",
            "subitem_name": "外伤现病史地点/场景/致伤机制完整性",
            "anchor_evidence_status": "potential_missing_trauma_context",
            "anchor_decision_reason": "缺地点。",
        }
    ]

    attached = attach_subitem_anchors_to_parent_results(results, anchors)

    assert len(attached) == 1
    assert attached[0]["metadata"]["subitem_anchor_count"] == 1
    assert attached[0]["metadata"]["subitem_anchors"][0]["anchor_id"] == "SC-009-trauma-location"
