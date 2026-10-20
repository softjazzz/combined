"""Regression coverage for the 2026-10-20 transfusion audit findings."""

from app.services.luxian_0609 import native_transfusion_execution as native
from app.services.luxian_0609.transfusion_result_mapping import (
    safe_transfusion_customer_display_facts,
)
from tests.unit.test_luxian_0609_transfusion_order_execution import (
    FrozenOrderClient,
    RULES,
    order_rows,
    run_case,
)


COMPLETE_COURSE = (
    "输血目的：纠正贫血；09:00开始输注红细胞2U，10:00结束；"
    "输血过程中生命体征平稳，未见输血不良反应；"
    "输血后指标改善，治疗有效。"
)


def test_046_independently_uses_senior_course_fallback_selected_for_045() -> None:
    rows = order_rows()
    rows.update(
        {
            "bloodtrans_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {"document_id": "synthetic-senior-course", "record_content": COMPLETE_COURSE}
            ],
        }
    )

    _, final = run_case(rows, client=FrozenOrderClient())

    assert final[RULES[1]]["status"] == "compliant"
    assert final[RULES[2]]["status"] == "compliant"
    assert any(
        item["source_type"] == "senior_course_record"
        for item in final[RULES[2]]["customer_evidence"]
    )


def test_046_keeps_dedicated_course_priority_over_complete_senior_fallback() -> None:
    rows = order_rows()
    rows.update(
        {
            "bloodtrans_record": [
                {
                    "document_id": "synthetic-dedicated-course",
                    "record_content": "已输注红细胞2U。",
                }
            ],
            "senior_course_record": [
                {"document_id": "synthetic-senior-course", "record_content": COMPLETE_COURSE}
            ],
        }
    )

    _, final = run_case(rows, client=FrozenOrderClient())

    assert final[RULES[2]]["status"] == "non_compliant"
    assert not any(
        item["source_type"] == "senior_course_record"
        for item in final[RULES[2]]["customer_evidence"]
    )


def test_046_fallback_classifier_unknown_stays_data_gap() -> None:
    rows = order_rows()
    rows["senior_course_record"] = [
        {"document_id": "synthetic-senior-course", "record_content": COMPLETE_COURSE}
    ]

    _, final = run_case(rows, client=FrozenOrderClient(record_kind="unknown"))

    assert final[RULES[2]]["status"] == "data_gap"


def test_046_fallback_source_failure_stays_technical_error() -> None:
    rows = order_rows()

    _, final = run_case(
        rows,
        client=FrozenOrderClient(),
        failed="senior_course_record",
    )

    assert final[RULES[2]]["status"] == "technical_error"


def test_044_legacy_missing_projection_uses_current_two_field_contract() -> None:
    raw = native._programmatic_transfusion_display_facts(
        rule_id="LX0609-07-01-02",
        status="non_compliant",
        reason_code="pretransfusion_assessment_missing",
        documents={
            "bloodtrans_record": [
                {
                    "document_id": "synthetic-course",
                    "record_content": "已实施输血，但未形成输血前评估。",
                }
            ],
            "blood_application": [],
            "daily_course_record": [],
            "senior_course_record": [],
        },
    )

    assert raw is not None
    assert raw["checked_fields"] == ["application_reason", "laboratory_indicator"]
    assert raw["missing_fields"] == ["application_reason", "laboratory_indicator"]
    projected = {**raw, "transfusion_order_present": True}
    projected.pop("performed_transfusion_confirmed", None)
    safe = safe_transfusion_customer_display_facts(
        rule_id="LX0609-07-01-02", raw=projected
    )
    assert safe is not None
    assert safe["checked_fields"] == ["application_reason", "laboratory_indicator"]
    assert safe["missing_fields"] == ["application_reason", "laboratory_indicator"]
