"""1019 核对确认问题的合成回归，不含患者原文。"""

from dataclasses import replace

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609 import native_extended_document_execution as medication_module
from app.services.qc_workspace.canonical_result_store import safe_customer_display_facts
from tests.unit.test_luxian_0609_consultation_measure_check import _setup
from tests.unit.test_luxian_0609_discharge_medication_integration import FakeClient, _run, _payload
from tests.unit.test_luxian_0609_pathology_event_association import (
    RESULT, _documents, _rows, _run as run_pathology,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from tests.unit.test_luxian_0609_native_extended_document_execution import _canonical_extended_result


@pytest.mark.asyncio
async def test_pathology_result_in_senior_course_is_checked_and_cited():
    rows = _rows()
    rows["senior_course_record"] = rows.pop("daily_course_record")
    final = await run_pathology(rows, RESULT)
    assert final["status"] == "compliant"
    assert "course-A" in _documents(final)
    assert any(item["source_type"] == "senior_course_record" for item in final["customer_evidence"])
    assert safe_customer_display_facts(final, rule_id=RESULT) == final["customer_display_facts"]


@pytest.mark.asyncio
async def test_pathology_result_without_record_time_uses_formal_submission_for_document_presence():
    rows = _rows()
    course = rows.pop("daily_course_record")[0]
    course["submit_datetime"] = course.pop("record_time")
    rows["senior_course_record"] = [course]
    final = await run_pathology(rows, RESULT)
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_tablet_dose_unit_resolves_route_before_reporting_other_missing_field():
    text = "院外继续服用合成药甲，每次1片。"
    payload = _payload(missing_route=True)
    payload["items"][0]["dose"]["quote"] = "每次1片"
    payload["items"][0]["medication_time"] = {"state": "missing", "quote": None}
    _, final = await _run(FakeClient(payload), text=text)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields"] == ["duration"]
    assert "给药途径" not in final["findings"]


@pytest.mark.asyncio
async def test_local_tablet_specification_survives_short_drug_name_quote():
    text = "合成药甲（5mg/片），每次1.25mg，每日一次。"
    payload = _payload(missing_route=True)
    payload["items"][0]["dose"]["quote"] = "每次1.25mg"
    payload["items"][0]["medication_time"]["quote"] = "每日一次"
    _, final = await _run(FakeClient(payload), text=text)
    assert final["status"] == "compliant"


def test_actual_family_refusal_after_communication_only_exempts_that_consultation():
    completed, _, _, _ = _setup()
    recommendation = replace(completed[0].recommendation, action_type="test",
                             source_quote="建议完善头颅MRI、骨代谢相关检查",
                             normalized_action="完善头颅MRI、骨代谢相关检查")
    # 拒绝由第一阶段模型按各自会诊文书抽取（2026-10-22）：只有沟通后拒绝的那次会诊带拒绝事实。
    current = replace(completed[0], recommendation=replace(
        recommendation, decline_state="full", decline_quote="与患者家属沟通后,拒绝进一步检查"))
    unrelated = replace(completed[0], episode_ref="consultation_record-2",
                        recommendation=replace(recommendation, opinion_ref="consultation_record-2",
                                               recommendation_ref="consultation_record-2#r1"))
    annotated = episode._annotate_order_scope((current, unrelated), documents_by_ref={
        current.recommendation.opinion_ref: {"text": "会诊意见:建议完善头颅MRI、骨代谢相关检查。处理;遵会诊意见,与患者家属沟通后,拒绝进一步检查,要求随访观察。"},
        unrelated.recommendation.opinion_ref: {"text": "会诊意见:建议完善头颅MRI、骨代谢相关检查。处理:遵照执行。"},
    })
    assert annotated[0].fully_declined
    assert not annotated[1].fully_declined


@pytest.mark.asyncio
@pytest.mark.parametrize("variant,expected", [
    ("valid", "compliant"), ("inpatient", "non_compliant"),
    ("canceled", "non_compliant"), ("orphan", "non_compliant"),
    ("deleted", "non_compliant"), ("nonoral", "non_compliant"),
    ("conflict", "non_compliant"), ("other_drug", "non_compliant"),
])
async def test_discharge_prescription_identifies_oral_form_for_abbreviated_drug_name(variant, expected):
    rule = "LX0609-08-01-02"
    rows = {
        "discharge_record": [{"document_id": "discharge", "discharge_order": "出院带药合成药甲，每次5毫克，每日一次。"}],
        "inpat_prescription": [{"prescription_id": "rx1", "order_type": "出院带药", "order_status": "新开"}],
        "inpat_prescription_item": [{"prescription_id": "rx1", "prescription_item_id": "rx1-item",
                                     "generic_name": "合成药甲片", "drug_apply_method": "口服"}],
    }
    header = rows["inpat_prescription"][0]
    item = rows["inpat_prescription_item"][0]
    if variant == "inpatient":
        header["order_type"] = "普通医嘱"
    elif variant == "canceled":
        header["order_status"] = "撤销"
    elif variant == "orphan":
        item["prescription_id"] = "other"
    elif variant == "deleted":
        item["is_deleted"] = "1"
    elif variant == "nonoral":
        item["drug_apply_method"] = "外用"
    elif variant == "conflict":
        rows["inpat_prescription_item"].append({**item, "drug_apply_method": "外用"})
    elif variant == "other_drug":
        item["generic_name"] = "合成药乙片"

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []), truncated=False, limit_rows=500)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-10T00:00:00+08:00", row_reader=reader,
    )
    payload = _payload(missing_route=True)
    payload["items"][0]["medication_time"]["quote"] = "每日一次"
    client = FakeClient(payload)
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    final = _canonical_extended_result(rule_id=rule, snapshot=session.snapshot, materials=session.materials,
                                       result=result, reduced=reduced)
    assert final["status"] == expected
    assert result.llm_call_count == 1


@pytest.mark.parametrize("feedback", [
    "处理;若与患者家属沟通后,拒绝进一步检查,则随访观察。",
    "处理;遵会诊意见,与患者家属沟通后,同意进一步检查。",
])
def test_hypothetical_or_accepted_checks_are_not_declined(feedback):
    completed, _, _, _ = _setup()
    item = replace(completed[0], recommendation=replace(
        completed[0].recommendation, action_type="test", source_quote="完善头颅MRI"))
    annotated = episode._annotate_order_scope((item,), documents_by_ref={
        item.recommendation.opinion_ref: {"text": "会诊意见:建议完善头颅MRI。" + feedback},
    })
    assert not annotated[0].fully_declined


def test_oral_route_never_fills_unknown_dose_or_timing():
    from app.services.luxian_0609.extended_document.discharge_medication_extraction import Extraction

    extraction = Extraction(
        state="unknown", reason_code="uncertain", medications=({"drug_name": "合成药甲片"},),
        field_assertions=({"drug_name": "present", "dose": "uncertain", "route": "missing", "duration": "uncertain"},),
    )
    resolved = medication_module._with_oral_route_uncertainty_resolved(extraction)
    assert resolved.state == "unknown"
    assert resolved.field_assertions[0]["route"] == "present"
    assert resolved.field_assertions[0]["dose"] == resolved.field_assertions[0]["duration"] == "uncertain"
