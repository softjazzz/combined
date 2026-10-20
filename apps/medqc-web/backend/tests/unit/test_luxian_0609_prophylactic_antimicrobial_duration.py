"""028 Ⅰ、Ⅱ类切口预防用抗菌药物时长（院方口径 2026-10-11），全部为合成数据。

源库医嘱停止时间待同步（用户 2026-10-11 确认测试用合成数据），停止时间字段为
stop_datetime。
"""

from __future__ import annotations

from datetime import datetime
import json

import pytest

from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.prophylactic_antimicrobial_duration import (
    SCHEMA_VERSION,
    SurgeryEventInput,
    evaluate_prophylactic_antimicrobial_duration,
    incision_class_value,
    is_cardiac_surgery,
    is_systemic_antibacterial,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.surgery_gate_result_mapping import safe_surgery_gate_customer_display_facts
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts


class _Client:
    def __init__(self, states):
        self.states, self.prompts = states, []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        docs = json.loads(prompt[prompt.rindex("\n") + 1:])
        items = []
        for doc, state in zip(docs, self.states):
            quote = doc["text"][:8] if state == "present" else None
            items.append({"id": doc["id"], "state": state, "quote": quote})
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
                {"schema_version": SCHEMA_VERSION, "documents": items}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


def _event(*, incision="I", cardiac=False, begin="2026-06-01 08:00", end="2026-06-01 10:00"):
    return SurgeryEventInput(
        begin=datetime.fromisoformat(begin) if begin else None,
        end=datetime.fromisoformat(end) if end else None,
        incision_class=incision,
        cardiac=cardiac,
    )


def _order(name, start, stop=None, *, temporary=False):
    return {
        "generic_name": name,
        "repeat_indicator": "临时" if temporary else "长期",
        "drug_frequency": "St" if temporary else "Q12h",
        "planned_start_datetime": start,
        "stop_datetime": stop,
        "order_status": "已停止" if stop else "新开",
    }


def _course(time, text):
    return {"record_time": time, "record_content": text}


@pytest.mark.parametrize(("value", "expected"), [
    ("Ⅰ", "I"), ("II", "II"), ("2", "II"), ("Ⅲ", "outside"), ("0", "outside"), ("-", "unknown"), (None, "unknown"),
])
def test_incision_class_normalization(value, expected) -> None:
    assert incision_class_value(value) == expected


@pytest.mark.parametrize(("order", "expected"), [
    ({"generic_name": "注射用头孢呋辛钠"}, True),
    ({"generic_name": "左氧氟沙星氯化钠注射液"}, True),
    ({"generic_name": "注射用盐酸表柔比星"}, False),
    ({"generic_name": "氟康唑注射液"}, False),
    ({"generic_name": "莫匹罗星软膏"}, False),
    ({"generic_name": "左氧氟沙星滴眼液"}, False),
    ({"generic_name": "注射用头孢唑林钠", "order_status": "作废"}, False),
])
def test_systemic_antibacterial_recognition(order, expected) -> None:
    assert is_systemic_antibacterial(order) is expected


def test_cardiac_surgery_by_icd9_code_or_name() -> None:
    assert is_cardiac_surgery(("36.1001",), ("",))
    assert is_cardiac_surgery((None,), ("二尖瓣瓣膜置换术",))
    assert not is_cardiac_surgery(("51.2301",), ("腹腔镜胆囊切除术",))


@pytest.mark.asyncio
@pytest.mark.parametrize(("event", "orders", "expected_status", "facts"), [
    # Ⅰ类切口：术前单剂 + 术后 20 小时停药 → 合规。
    (_event(), (_order("注射用头孢唑林钠", "2026-06-01 07:30", temporary=True),
                _order("注射用头孢唑林钠", "2026-06-01 12:00", "2026-06-02 06:00")),
     "compliant", {"duration_hours": 20.0, "threshold_hours": 24, "infection_evidence": "not_required"}),
    # Ⅱ类切口 30 小时、病程无感染证据 → 不合规（模型逐份 absent）。
    (_event(incision="II"), (_order("注射用头孢呋辛钠", "2026-06-01 07:30", "2026-06-02 16:00"),),
     "non_compliant", {"duration_hours": 30.0, "infection_evidence": "not_recorded"}),
    # Ⅰ类心脏手术 40 小时 → 时限 48 小时，合规。
    (_event(cardiac=True), (_order("注射用头孢唑林钠", "2026-06-01 07:30", "2026-06-03 02:00"),),
     "compliant", {"duration_hours": 40.0, "threshold_hours": 48, "cardiac_surgery": True}),
    # Ⅱ类切口不适用心脏手术 48 小时（指导原则只给Ⅰ类心脏手术）。
    (_event(incision="II", cardiac=True), (_order("注射用头孢呋辛钠", "2026-06-01 07:30", "2026-06-03 02:00"),),
     "non_compliant", {"threshold_hours": 24, "cardiac_surgery": False}),
    # 长期医嘱缺停止时间 → 资料不足。
    (_event(), (_order("注射用头孢唑林钠", "2026-06-01 07:30"),), "data_gap",
     {"failure_kind": "order_stop_time_unavailable"}),
    # 切口等级取不到 → 资料不足；Ⅲ类、0 类 → 不适用。
    (_event(incision="unknown"), (_order("注射用头孢唑林钠", "2026-06-01 07:30", "2026-06-01 20:00"),), "data_gap",
     {"failure_kind": "incision_class_unavailable"}),
    (_event(incision="outside"), (_order("注射用头孢唑林钠", "2026-06-01 07:30", "2026-06-05 20:00"),),
     "not_applicable", None),
    # 围术期（术前24小时至术后24小时）未开始全身抗菌药物 → 不适用。
    (_event(), (_order("注射用头孢唑林钠", "2026-06-05 07:30", "2026-06-06 20:00"),), "not_applicable", None),
])
async def test_028_duration_decisions(event, orders, expected_status, facts) -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(event,), drug_order_rows=orders,
        course_rows=(("daily:0", _course("2026-06-02 09:00", "术后第一天，切口干燥，体温正常。")),),
        llm_client=_Client(["absent"]),
    )
    assert outcome.status == expected_status
    if facts is None:
        assert outcome.display_facts is None
    else:
        assert {key: outcome.display_facts[key] for key in facts} == facts
        assert safe_surgery_gate_customer_display_facts(rule_id="LX0609-05-01-01", raw=outcome.display_facts)


@pytest.mark.asyncio
async def test_028_continuous_reordered_course_is_one_chain() -> None:
    """同一用药过程分次续开（相隔不超过24小时）连成一条，时长到最后停用。"""
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(),),
        drug_order_rows=(
            _order("注射用头孢呋辛钠", "2026-06-01 07:30", "2026-06-02 08:00"),
            _order("注射用头孢呋辛钠", "2026-06-02 08:00", "2026-06-03 10:00"),
            # 相隔超过24小时的新用药过程不并入。
            _order("左氧氟沙星注射液", "2026-06-10 08:00", "2026-06-12 08:00"),
        ),
        course_rows=(), llm_client=_Client([]),
    )
    assert outcome.status == "non_compliant"
    assert outcome.display_facts["duration_hours"] == 48.0
    assert outcome.llm_call_count == 0


@pytest.mark.asyncio
async def test_028_exceeded_with_recorded_infection_evidence_is_treatment() -> None:
    client = _Client(["absent", "present"])
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("注射用头孢呋辛钠", "2026-06-01 07:30", "2026-06-04 10:00"),),
        course_rows=(
            ("daily:0", _course("2026-06-02 09:00", "术后第一天，切口干燥。")),
            ("daily:1", _course("2026-06-03 09:00", "体温38.9℃，白细胞18×10^9/L，引流液浑浊，考虑腹腔感染。")),
            # 用药结束 24 小时后的病程不送模型。
            ("daily:2", _course("2026-06-08 09:00", "病情稳定。")),
        ),
        llm_client=client,
    )
    assert outcome.status == "compliant"
    assert outcome.display_facts["infection_evidence"] == "recorded"
    assert outcome.llm_call_count == 1 and len(client.prompts) == 1
    assert "病情稳定" not in client.prompts[0]


@pytest.mark.asyncio
async def test_028_unresolved_or_invalid_evidence_never_becomes_non_compliant() -> None:
    args = dict(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("注射用头孢呋辛钠", "2026-06-01 07:30", "2026-06-04 10:00"),),
        course_rows=(("daily:0", _course("2026-06-02 09:00", "术后第一天。")),),
    )
    unresolved = await evaluate_prophylactic_antimicrobial_duration(**args, llm_client=_Client(["unknown"]))
    assert (unresolved.status, unresolved.display_facts) == ("data_gap", {"failure_kind": "infection_evidence_unresolved"})

    class _Bad:
        async def generate(self, *_args, **_kwargs):
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}], "usage": {}}

    invalid = await evaluate_prophylactic_antimicrobial_duration(**args, llm_client=_Bad())
    assert invalid.status == "technical_error"


def test_028_display_facts_whitelist_rejects_inconsistent_facts() -> None:
    good = {
        "verification_kind": "prophylaxis_duration_check", "incision_class": "II", "cardiac_surgery": False,
        "threshold_hours": 24, "duration_hours": 30.0, "anchor": "surgery_end",
        "anchor_time": "2026-06-01 10:00:00", "last_antibacterial_time": "2026-06-02 16:00:00",
        "infection_evidence": "not_recorded", "requirement_met": False,
    }
    assert safe_surgery_gate_customer_display_facts(rule_id="LX0609-05-01-01", raw=good) == good
    for change in (
        {"threshold_hours": 48}, {"infection_evidence": "not_required"}, {"requirement_met": True},
        {"incision_class": "III"}, {"cardiac_surgery": True}, {"quote": "原文"},
    ):
        assert safe_surgery_gate_customer_display_facts(rule_id="LX0609-05-01-01", raw={**good, **change}) is None
    text = customer_finding_from_controlled_facts(rule_id="LX0609-05-01-01", facts=good, status="non_compliant")
    assert text == (
        "Ⅱ类切口手术，自手术结束 2026-06-01 10:00:00 至抗菌药物最后停用 2026-06-02 16:00:00，"
        "共 30.0 小时（时限 24 小时），已超过预防用药时限，病程未记录感染证据，不能作为延长用药理由。"
    )


def _wrapper(rule_id):
    return {"rule_id": rule_id, "rule_code": rule_id, "rule_name": rule_id}


@pytest.mark.asyncio
async def test_028_executor_end_to_end_with_synthetic_stop_time() -> None:
    rows = {
        "surgery_record": ({
            "document_id": "S1", "surgery_name": "腹腔镜胆囊切除术",
            "surgery_begin_time": "2026-06-01 08:00:00+08:00", "surgery_end_time": "2026-06-01 10:00:00+08:00",
            "surgery_process": "手术顺利。",
        },),
        "mr_surgery": ({
            "surgery_begin_datetime": datetime(2026, 6, 1, 8, 0), "surgery_end_datetime": datetime(2026, 6, 1, 10, 0),
            "surgial_incision_level": "Ⅱ", "surgery_code": "51.2301", "surgery_name": "腹腔镜胆囊切除术",
        },),
        "inpat_drug_order": (_order("注射用头孢呋辛钠", "2026-06-01 07:30:00", "2026-06-02 16:00:00"),),
        "senior_course_record": ({
            "document_id": "R1", "record_time": "2026-06-02 09:00:00", "record_content": "术后第一天，切口干燥，体温正常。",
        },),
    }

    def reader(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows.get(kwargs["source_key"], ()), truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-05-01-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-10T00:00:00+08:00", row_reader=reader,
    )
    client = _Client(["absent"])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-05-01-01",), decision_rule_ids=("LX0609-05-01-01",),
        wrapper_rules=[_wrapper("LX0609-05-01-01")], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-05-01-01",),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == "non_compliant"
    facts = dict(result.customer_display_facts)["LX0609-05-01-01"]
    assert (facts["incision_class"], facts["duration_hours"], facts["infection_evidence"]) == ("II", 30.0, "not_recorded")
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_028_public_entry_keeps_prophylaxis_check_after_excluding_linked_treatment_order() -> None:
    """同例不同药逐项判目的；治疗药缺停药时间不应遮蔽预防药的时长结论。"""
    rows = {
        "surgery_record": ({
            "document_id": "S-MIXED", "surgery_name": "合成腹部手术",
            "surgery_begin_time": "2026-06-01 08:00:00+08:00",
            "surgery_end_time": "2026-06-01 10:00:00+08:00",
            "surgery_process": "合成手术记录。",
        },),
        "mr_surgery": ({
            "surgery_begin_datetime": datetime(2026, 6, 1, 8, 0),
            "surgery_end_datetime": datetime(2026, 6, 1, 10, 0),
            "surgial_incision_level": "Ⅱ", "surgery_code": "00.0000", "surgery_name": "合成腹部手术",
        },),
        "inpat_drug_order": (
            _order("注射用头孢呋辛钠", "2026-06-01 07:30:00", "2026-06-02 16:00:00"),
            _order("左氧氟沙星氯化钠注射液", "2026-06-01 18:30:00"),
        ),
        "senior_course_record": ({
            "document_id": "R-MIXED", "record_time": "2026-06-02 09:00:00",
            "record_content": "因合成的呼吸道感染诊断，左氧氟沙星用于抗感染治疗；头孢呋辛为围术期预防感染用药。",
        },),
    }

    def reader(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows.get(kwargs["source_key"], ()),
            truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-05-01-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-10T00:00:00+08:00", row_reader=reader,
    )
    client = _Client(["absent"])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-05-01-01",), decision_rule_ids=("LX0609-05-01-01",),
        wrapper_rules=[_wrapper("LX0609-05-01-01")], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-05-01-01",),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert reduced[0].final_state.value == "non_compliant"
    facts = dict(result.customer_display_facts)["LX0609-05-01-01"]
    assert (facts["duration_hours"], facts["infection_evidence"]) == (30.0, "not_recorded")
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_028_explicitly_linked_treatment_order_without_stop_is_not_applicable() -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("左氧氟沙星氯化钠注射液", "2026-06-01 18:30"),),
        course_rows=((
            "daily:0",
            _course("2026-06-02 09:00", "专科建议使用左氧氟沙星控制合成肺部感染。"),
        ),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.reason_code, outcome.display_facts) == (
        "not_applicable", "trigger_absent_complete", None,
    )
    assert outcome.llm_call_count == 0


@pytest.mark.asyncio
async def test_028_unlinked_infection_text_does_not_exclude_unknown_purpose_order() -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("左氧氟沙星氯化钠注射液", "2026-06-01 18:30"),),
        course_rows=((
            "daily:0",
            _course("2026-06-02 09:00", "合成感染诊断明确，改用头孢他啶进行抗感染治疗。"),
        ),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.display_facts) == (
        "data_gap", {"failure_kind": "order_stop_time_unavailable"},
    )


@pytest.mark.asyncio
async def test_028_generic_anti_infection_wording_does_not_prove_treatment_purpose() -> None:
    """围术期常写“予某药抗感染”，没有治疗性适应证时仍须核对停药时间。"""
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("注射用头孢呋辛钠", "2026-06-01 07:30"),),
        course_rows=((
            "daily:0", _course("2026-06-01 12:00", "术后予头孢呋辛抗感染，切口情况稳定。"),
        ),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.display_facts) == (
        "data_gap", {"failure_kind": "order_stop_time_unavailable"},
    )


@pytest.mark.asyncio
async def test_028_nearby_other_drug_treatment_purpose_is_not_shared() -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("注射用头孢呋辛钠", "2026-06-01 07:30"),),
        course_rows=((
            "daily:0",
            _course("2026-06-01 12:00", "专科建议使用左氧氟沙星控制合成肺部感染，另予头孢呋辛调整方案。"),
        ),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.display_facts) == (
        "data_gap", {"failure_kind": "order_stop_time_unavailable"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose_text", (
    "未见合成肺部感染，予左氧氟沙星抗感染。",
    "停用左氧氟沙星治疗合成肺部感染。",
    "未使用左氧氟沙星治疗合成肺部感染。",
))
async def test_028_negated_infection_or_drug_use_does_not_prove_treatment_purpose(
    purpose_text: str,
) -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("左氧氟沙星氯化钠注射液", "2026-06-01 18:30"),),
        course_rows=(("daily:0", _course("2026-06-02 09:00", purpose_text)),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.display_facts) == (
        "data_gap", {"failure_kind": "order_stop_time_unavailable"},
    )


@pytest.mark.asyncio
async def test_028_same_drug_with_prophylactic_and_treatment_purposes_stays_in_scope() -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(incision="II"),),
        drug_order_rows=(_order("注射用头孢呋辛钠", "2026-06-01 07:30"),),
        course_rows=((
            "daily:0",
            _course("2026-06-01 12:00", "头孢呋辛先用于围术期预防感染，后因合成感染继续抗感染治疗。"),
        ),),
        llm_client=_Client([]),
    )

    assert (outcome.status, outcome.display_facts) == (
        "data_gap", {"failure_kind": "order_stop_time_unavailable"},
    )


@pytest.mark.asyncio
async def test_028_antibacterial_order_without_any_time_is_data_gap_not_absent() -> None:
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(),), drug_order_rows=({"generic_name": "注射用头孢唑林钠", "repeat_indicator": "长期"},),
        course_rows=(), llm_client=_Client([]),
    )
    assert (outcome.status, outcome.display_facts) == ("data_gap", {"failure_kind": "order_start_time_unavailable"})


@pytest.mark.asyncio
async def test_028_postoperative_order_in_window_is_counted_even_after_gap() -> None:
    """0910 C04 形态：术前一日单剂，术后当日另开长期医嘱（相隔超过24小时）仍属围术期。"""
    outcome = await evaluate_prophylactic_antimicrobial_duration(
        events=(_event(begin="2026-06-02 09:45", end=None),),
        drug_order_rows=(
            _order("注射用头孢唑林钠", "2026-06-01 10:27", temporary=True),
            _order("盐酸莫西沙星注射液", "2026-06-02 12:37"),
        ),
        course_rows=(), llm_client=_Client([]),
    )
    assert (outcome.status, outcome.display_facts) == ("data_gap", {"failure_kind": "order_stop_time_unavailable"})


def test_028_preoperative_only_use_wording() -> None:
    facts = {
        "verification_kind": "prophylaxis_duration_check", "incision_class": "I", "cardiac_surgery": False,
        "threshold_hours": 24, "duration_hours": 0.0, "anchor": "surgery_begin",
        "anchor_time": "2026-06-02 09:25:00", "last_antibacterial_time": "2026-06-01 15:33:31",
        "infection_evidence": "not_required", "requirement_met": True,
    }
    assert customer_finding_from_controlled_facts(rule_id="LX0609-05-01-01", facts=facts, status="compliant") == (
        "Ⅰ类切口手术，围术期抗菌药物仅在手术开始前使用（最后一次 2026-06-01 15:33:31），未超过预防用药时限。"
    )
