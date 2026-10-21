"""054/057 医嘱驱动：用药事件、开医嘱当日病程窗口、引文校验与状态映射（用户口径 2026-10-21）。"""

from datetime import datetime, timedelta
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.extended_document.antimicrobial_order_reason import (
    derive_antimicrobial_use_events,
    planned_duration,
    extract_antimicrobial_reasons,
    window_documents,
)
from app.services.luxian_0609.native_extended_document_execution import (
    _antimicrobial_names_in,
    _material_text,
)
from test_luxian_0609_native_extended_document_execution import _evaluate, _session


def _order(order_id, name, start, end=None, **extra):
    return {
        "order_id": order_id, "generic_name": name,
        "planned_start_datetime": start, "planned_end_datetime": end, **extra,
    }


def _course(document_id, time, text):
    return {"document_id": document_id, "record_time": time, "record_content": text}


class _ReasonClient:
    """按事件给出引文的受控模型桩；fields 为 {药名: {字段: 引文}}。"""

    def __init__(self, fields=None, documented_use="yes", broken=False):
        self.fields = fields or {}
        self.documented_use = documented_use
        self.broken = broken
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append(prompt)
        payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
        texts = {doc["doc_ref"]: doc["text"] for doc in payload["documents"]}
        events = []
        for event in payload["events"]:
            item = {"event_id": event["event_id"], "documented_use": self.documented_use, "quote_doc_refs": {}}
            for kind, quote in self.fields.get(event["drug"], {}).items():
                ref = next((r for r in event["doc_refs"] if quote in texts[r]), None)
                if ref is None:
                    # 受控桩只引用该事件窗口内确实存在的原文。
                    continue
                item[f"{kind}_quote"] = "篡改的引文" if self.broken else quote
                item["quote_doc_refs"][kind] = ref
            events.append(item)
        content = json.dumps({"schema_version": "lx0609_antimicrobial_order_reason_v1", "events": events},
                             ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


# ---- 医嘱事件 ----

def test_events_merge_same_drug_course_and_exclude_skin_test_and_canceled() -> None:
    resolution = derive_antimicrobial_use_events((
        _order("S", "青霉素", "2026-01-01 08:00:00", drug_apply_method="皮试"),
        _order("A1", "头孢曲松", "2026-01-01 09:00:00", "2026-01-03 09:00:00"),
        _order("A2", "头孢曲松", "2026-01-03 10:00:00", "2026-01-05 09:00:00"),
        _order("X", "左氧氟沙星", "2026-01-02 09:00:00", canceled_datetime="2026-01-02 09:10:00"),
    ), _antimicrobial_names_in)

    assert [(e.antimicrobial, e.kind, len(e.orders)) for e in resolution.events if e.kind != "stop"] == [
        ("头孢曲松", "start", 2),
    ]


def test_events_classify_restart_combine_and_switch() -> None:
    resolution = derive_antimicrobial_use_events((
        # 左氧氟沙星开出时头孢曲松仍在用且两天后才停：联合，不是更换。
        _order("A1", "头孢曲松", "2026-01-01 09:00:00", "2026-01-05 18:00:00"),
        _order("B1", "左氧氟沙星", "2026-01-02 09:00:00", "2026-01-04 09:00:00"),
        _order("C1", "美罗培南", "2026-01-04 12:00:00", "2026-01-08 09:00:00"),
        _order("A2", "头孢曲松", "2026-01-10 09:00:00", "2026-01-12 09:00:00"),
    ), _antimicrobial_names_in)

    # 美罗培南开出前3小时左氧氟沙星停用：更换；头孢曲松停用5天后再开：重新开始。
    assert [(e.antimicrobial, e.kind) for e in resolution.events if e.kind != "stop"] == [
        ("头孢曲松", "start"), ("左氧氟沙星", "combine"), ("美罗培南", "switch"), ("头孢曲松", "start"),
    ]


def test_missing_order_start_time_is_reported_not_guessed() -> None:
    resolution = derive_antimicrobial_use_events(({"order_id": "A", "generic_name": "头孢曲松"},),
                                                 _antimicrobial_names_in)
    assert resolution.events == () and resolution.time_missing_names == ("头孢曲松",)


# ---- 开医嘱当日窗口 ----

def test_window_is_order_calendar_day_and_untimed_rows_bounded_by_modification() -> None:
    """用户口径（2026-10-21）：抗菌调整医嘱当日必须有对应病程理由；开嘱前的同日查房同样有效（1019 C05）。"""
    events = derive_antimicrobial_use_events((
        _order("Z", "左氧氟沙星", "2025-12-20 09:00:00", "2025-12-31 20:00:00"),
        _order("A", "头孢曲松", "2026-01-01 09:00:00"),
    ), _antimicrobial_names_in).events[1:]
    assert events[0].kind == "switch"
    rows = (
        _course("prev-day", "2025-12-31 23:59:00", "入院评估"),
        _course("before", "2026-01-01 08:00:00", "原方案无效，拟改用头孢曲松"),
        _course("same-day", "2026-01-01 22:00:00", "考虑肺部感染"),
        _course("next-day", "2026-01-02 08:00:00", "复查"),
        {"document_id": "old", "record_content": "早期记录", "last_modified_datetime": "2025-12-31 07:00:00"},
    )
    documents, per_event, untimed = window_documents(events, (("daily_course_record", rows),), _material_text)

    assert [doc.row["document_id"] for doc in documents] == ["before", "same-day"]
    assert per_event == {"E2": ("D1", "D2")} and untimed == frozenset()
    later = rows + ({"document_id": "late", "record_content": "缺时记录",
                     "last_modified_datetime": "2026-01-01 12:00:00"},)
    assert window_documents(events, (("daily_course_record", later),), _material_text)[2] == {"E2"}


def test_start_event_also_covers_24h_after_order() -> None:
    """首次开始用药：入院当日开药、次日上午写首程/查房仍在窗口内；超过24小时不算。"""
    events = derive_antimicrobial_use_events((_order("A", "头孢曲松", "2026-01-01 14:00:00"),),
                                             _antimicrobial_names_in).events
    rows = (_course("next-morning", "2026-01-02 10:00:00", "考虑肺部感染"),
            _course("too-late", "2026-01-02 15:00:00", "复查"))
    documents, _, _ = window_documents(events, (("daily_course_record", rows),), _material_text)
    assert [doc.row["document_id"] for doc in documents] == ["next-morning"]


# ---- 抽取与引文校验 ----

@pytest.mark.asyncio
async def test_unverified_quote_retries_once_then_is_technical_error() -> None:
    events = derive_antimicrobial_use_events((_order("A", "头孢曲松", "2026-01-01 09:00:00"),),
                                             _antimicrobial_names_in).events
    documents, per_event, _ = window_documents(
        events, (("daily_course_record", (_course("in", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松"),)),),
        _material_text,
    )
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}}, broken=True)
    result = await extract_antimicrobial_reasons(events, documents, per_event, client)

    assert (result.state, result.reason_code, result.llm_call_count) == ("technical_error", "model_invalid_output", 2)


# ---- 执行器状态映射 ----

# 未停用的疗程：只有开始事件（停用另见停用测试）。
_ORDERS = (_order("A", "头孢曲松", "2026-01-01 09:00:00"),)


async def _run(rule_id, rows, client):
    return await _evaluate(rule_id, {"inpat_drug_order": _ORDERS, "first_course_record": (),
                                      "senior_course_record": (), "consultation_record": (),
                                      "transfer_in_record": (), **rows}, llm_client=client)


@pytest.mark.asyncio
async def test_054_same_day_course_with_infection_judgment_is_compliant_and_publishes() -> None:
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}})
    rows = {"daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，继续当前抗感染治疗。"),)}
    result, reduced = await _run("LX0609-05-01-02", rows, client)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 1
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["reason_documented"] is True and facts["antimicrobials"] == ["头孢曲松"]


@pytest.mark.asyncio
async def test_054_without_course_in_window_is_non_compliant_without_model_call() -> None:
    client = _ReasonClient()
    rows = {"daily_course_record": (_course("D-1", "2026-01-03 10:00:00", "考虑肺部感染。"),)}
    result, reduced = await _run("LX0609-05-01-02", rows, client)

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert client.calls == []
    assert dict(result.customer_display_facts)["LX0609-05-01-02"]["unmatched_antimicrobials"] == ["头孢曲松"]


@pytest.mark.asyncio
async def test_054_course_without_reason_quote_is_non_compliant() -> None:
    rows = {"daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "予头孢曲松静滴。"),)}
    _, reduced = await _run("LX0609-05-01-02", rows, _ReasonClient())
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_057_prior_pathogen_result_makes_event_targeted_not_applicable() -> None:
    rows = {
        "daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "痰培养示肺炎链球菌，予头孢曲松。"),),
        "labtest_master": ({"test_id": "L1", "labtest_subject": "痰培养", "report_datetime": "2026-01-01 08:00:00",
                            "result": "肺炎链球菌"},),
        "labtest_item_report": ({"test_id": "L1", "item_name": "细菌培养", "result": "肺炎链球菌",
                                 "report_datetime": "2026-01-01 08:00:00"},),
    }
    _, reduced = await _run("LX0609-05-01-05", rows, _ReasonClient())
    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_057_prophylaxis_is_not_empiric_use() -> None:
    rows = {"daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "术前予头孢曲松预防切口感染。"),),
            "labtest_master": (), "labtest_item_report": ()}
    client = _ReasonClient({"头孢曲松": {"prophylaxis": "术前予头孢曲松预防切口感染"}})
    _, reduced = await _run("LX0609-05-01-05", rows, client)
    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_057_empiric_use_with_infection_judgment_is_compliant() -> None:
    rows = {"daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松抗感染。"),),
            "labtest_master": (), "labtest_item_report": ()}
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}})
    result, reduced = await _run("LX0609-05-01-05", rows, client)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-05-01-05"]["empiric_use_confirmed"] is True


@pytest.mark.asyncio
async def test_054_and_057_share_one_model_call() -> None:
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rows = {"inpat_drug_order": _ORDERS, "first_course_record": (), "senior_course_record": (),
            "consultation_record": (), "transfer_in_record": (), "labtest_master": (), "labtest_item_report": (),
            "daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松。"),)}
    snapshot, materials = _session(rows)
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}})
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-05-01-02", "LX0609-05-01-05"),
        decision_rule_ids=("LX0609-05-01-02", "LX0609-05-01-05"),
        evidence_snapshot=snapshot, evidence_materials=materials, llm_client=client,
    )
    assert len(client.calls) == 1 and result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ("LX0609-05-01-02", "LX0609-05-01-05"))
async def test_finalized_results_bind_order_and_quoted_course(rule_id) -> None:
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rows = {"inpat_drug_order": _ORDERS, "first_course_record": (), "senior_course_record": (),
            "consultation_record": (), "transfer_in_record": (), "labtest_master": (), "labtest_item_report": (),
            "daily_course_record": (_course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松。"),)}
    snapshot, materials = _session(rows)
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule_id,), decision_rule_ids=(rule_id,), evidence_snapshot=snapshot,
        evidence_materials=materials, llm_client=_ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}}),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule_id,), snapshot=snapshot, evidence_materials=materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts)[rule_id],
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    assert final["status"] == "compliant"
    assert {item["source_type"] for item in final["customer_evidence"]} == {"inpat_drug_order", "daily_course_record"}


# ---- 停用 ----

def _stops(orders, **kwargs):
    events = derive_antimicrobial_use_events(orders, _antimicrobial_names_in, **kwargs).events
    return [(e.antimicrobial, e.time.isoformat(sep=" ")) for e in events if e.kind == "stop"]


def test_stop_event_excludes_discharge_switch_and_order_planned_duration() -> None:
    discharge = datetime(2026, 1, 10, 9, 0)
    assert _stops((_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-05 09:00:00"),),
                  discharge_time=discharge) == [("头孢曲松", "2026-01-05 09:00:00")]
    # 出院当日随出院停用不核对。
    assert _stops((_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-10 08:00:00"),),
                  discharge_time=discharge) == []
    # 停后24小时内改用他药：按更换核对，不另查停用。
    assert _stops((_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-05 09:00:00"),
                   _order("B", "美罗培南", "2026-01-05 10:00:00")), discharge_time=discharge) == []
    # 医嘱用药天数3天、到期停用：按计划停用不核对。
    assert _stops((_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-04 08:00:00",
                          medication_duration="3"),), discharge_time=discharge) == []


@pytest.mark.parametrize(("text", "expected"), [
    ("拟用3天", timedelta(days=3)), ("疗程五日", timedelta(days=5)),
    ("预防用药24小时", timedelta(hours=24)), ("疗程十四天", timedelta(days=14)),
    ("先用3天，必要时延长至7天", None), ("继续抗感染", None),
])
def test_planned_duration_parsing(text, expected) -> None:
    assert planned_duration(text) == expected


_STOP_ORDERS = (_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-04 10:00:00"),)


async def _run_stop(rows, client):
    return await _evaluate("LX0609-05-01-02", {"inpat_drug_order": _STOP_ORDERS, "first_course_record": (),
                                                "senior_course_record": (), "consultation_record": (),
                                                "transfer_in_record": (), **rows}, llm_client=client)


@pytest.mark.asyncio
async def test_054_stop_without_reason_on_stop_day_is_non_compliant() -> None:
    rows = {"daily_course_record": (
        _course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松。"),
        _course("D-2", "2026-01-04 11:00:00", "停用头孢曲松。"),
    )}
    _, reduced = await _run_stop(rows, _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染"}}))
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_054_stop_with_reason_on_stop_day_is_compliant() -> None:
    rows = {"daily_course_record": (
        _course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松。"),
        _course("D-2", "2026-01-04 11:00:00", "体温正常、感染指标下降，感染控制，停用头孢曲松。"),
    )}
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染", "stop_reason": "感染控制"}})
    _, reduced = await _run_stop(rows, client)
    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_054_stop_at_course_planned_in_start_record_needs_no_stop_reason() -> None:
    rows = {"daily_course_record": (
        _course("D-1", "2026-01-01 20:00:00", "考虑肺部感染，予头孢曲松抗感染，拟用3天。"),
        _course("D-2", "2026-01-04 11:00:00", "停用头孢曲松。"),
    )}
    client = _ReasonClient({"头孢曲松": {"infection_judgment": "考虑肺部感染", "planned_duration": "拟用3天"}})
    _, reduced = await _run_stop(rows, client)
    assert reduced.final_state is CustomerFinalState.COMPLIANT


# ---- 055 医嘱驱动 ----

@pytest.mark.asyncio
async def test_055_course_stopped_before_48h_needs_no_effect_evaluation() -> None:
    _, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": (_order("A", "头孢曲松", "2026-01-01 09:00:00", "2026-01-02 09:00:00"),),
        "daily_course_record": (), "senior_course_record": (),
    })
    assert (reduced.final_state, reduced.reason_code) == (CustomerFinalState.NOT_APPLICABLE, "trigger_absent_complete")


@pytest.mark.asyncio
async def test_055_canceled_order_is_not_a_course() -> None:
    _, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": (_order("A", "头孢曲松", "2026-01-01 09:00:00",
                                    canceled_datetime="2026-01-01 09:05:00"),),
        "daily_course_record": (), "senior_course_record": (),
    })
    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_055_restart_after_gap_opens_a_new_window() -> None:
    result, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": (
            _order("A1", "头孢曲松", "2026-01-01 09:00:00", "2026-01-05 09:00:00"),
            _order("A2", "头孢曲松", "2026-01-10 09:00:00", "2026-01-15 09:00:00"),
        ),
        "daily_course_record": (_course("D-1", "2026-01-03 10:00:00",
                                        "抗菌药物效果评价：抗感染治疗有效；安全性评价：未见药物不良反应。"),),
        "senior_course_record": (),
    })
    # 第二个疗程（1月10日起）的48–72小时窗内无评价。
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    windows = dict(result.customer_display_facts)["LX0609-05-01-03"]["event_windows"]
    assert [item["start_time"] for item in windows] == ["2026-01-01 09:00:00", "2026-01-10 09:00:00"]
