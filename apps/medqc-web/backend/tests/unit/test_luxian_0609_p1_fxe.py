"""1016 输血、出院及转科程序缺陷的合成回归。"""

from datetime import datetime
import json

import pytest

from app.services.luxian_0609.extended_document.discharge_course import (
    evaluate_predischarge_course_presence,
)
from app.services.luxian_0609.extended_document.transfusion_performance_extraction import (
    SCHEMA_VERSION, extract_transfusion_performance,
)
from app.services.luxian_0609.extended_document.transfer_documentation import (
    evaluate_transfer_documentation,
)


@pytest.mark.parametrize("rule_id,expected", [
    ("LX0609-10-02-01", "non_compliant"),
    ("LX0609-10-02-02", "compliant"),
])
def test_separate_transfer_events_are_checked_individually(rule_id, expected):
    outcome = evaluate_transfer_documentation(
        rule_id=rule_id, nondrug_order_error="", transfer_in_error="", transfer_out_error="",
        nondrug_order_rows=[
            {"order_name": "转入内科", "order_time": "2026-06-01 10:00:00"},
            {"order_name": "转入外科", "order_time": "2026-06-05 10:00:00"},
        ],
        transfer_in_rows=[
            {"record_time": "2026-06-02 12:00:00"},
            {"record_time": "2026-06-05 12:00:00"},
        ],
        transfer_out_rows=[
            {"record_time": "2026-06-01 11:00:00"},
            {"record_time": "2026-06-05 11:00:00"},
        ],
        evaluation_horizon_datetime=datetime(2026, 6, 8),
    )
    assert outcome.final_state == expected


def test_later_transfer_record_cannot_satisfy_earlier_missing_event():
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02", nondrug_order_error="", transfer_in_error="", transfer_out_error="",
        nondrug_order_rows=[
            {"order_name": "转入内科", "order_time": "2026-06-01 10:00:00"},
            {"order_name": "转入外科", "order_time": "2026-06-05 10:00:00"},
        ],
        transfer_in_rows=[{"record_time": "2026-06-05 12:00:00"}],
        transfer_out_rows=[{"record_time": "2026-06-05 11:00:00"}],
    )
    assert (outcome.final_state, outcome.reason_code) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("effect,expected", [("", "non_compliant"), ("输血后复查血红蛋白改善，治疗有效。", "compliant")])
async def test_transfusion_completeness_requires_effect_separately_from_reaction(effect, expected):
    from test_luxian_0609_transfusion_performance_043_047 import _run
    from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER

    body = (
        "输血目的：纠正贫血。开始时间10:00，输注O型红细胞2U，12:00输血结束。"
        "输血过程中严密观察生命体征，未见输血反应。" + effect
    )
    result = await _run("LX0609-07-02-02", {
        "inpat_nondrug_order": [OPEN_TRANSFUSION_ORDER], "inpat_drug_order": [],
        "bloodtrans_record": [{"document_id": "synthetic-course", "record_time": "2026-06-02 13:00:00", "record_content": body}],
    }, {body: "record"})
    assert result["final"]["status"] == expected, result["final"]


@pytest.mark.asyncio
async def test_transfusion_purpose_improvement_is_not_a_posttransfusion_effect():
    from test_luxian_0609_transfusion_performance_043_047 import _run
    from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER

    body = "输血目的：改善贫血；开始时间10:00，输注红细胞2U，12:00输血结束。输血过程中严密观察，未见输血反应。"
    result = await _run("LX0609-07-02-02", {
        "inpat_nondrug_order": [OPEN_TRANSFUSION_ORDER], "inpat_drug_order": [],
        "bloodtrans_record": [{"document_id": "synthetic-purpose", "record_time": "2026-06-02 13:00:00", "record_content": body}],
    }, {body: "record"})
    assert result["final"]["status"] == "non_compliant", result["final"]


@pytest.mark.asyncio
async def test_automatic_discharge_notice_is_accepted_as_signed_automatic_document():
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected

    _, _, result, _ = await _evaluate_selected(("LX0609-08-02-02",), {
        "inpat_registration": [{"discharge_datetime": "2026-06-02 12:00:00"}],
        "daily_course_record": [{
            "document_id": "synthetic-automatic-discharge", "record_time": "2026-06-02 10:00:00",
            "record_content": "家属要求自动出院，告知出院风险，家属理解仍要求自动出院，请示主治医师和签署《自动出院告知书》后办理出院。",
        }],
    })
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["approval_path"] == "automatic_discharge"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-07-01-01", "LX0609-07-03-01"])
async def test_order_without_performance_cannot_produce_definite_conclusion(rule_id):
    from test_luxian_0609_transfusion_performance_043_047 import _run
    from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER

    result = await _run(rule_id, {
        "inpat_nondrug_order": [OPEN_TRANSFUSION_ORDER], "inpat_drug_order": [],
    }, {})
    assert result["final"]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_senior_course_actual_transfusion_provides_course_for_open_order():
    from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER
    from test_luxian_0609_transfusion_performance_043_047 import _run

    body = "今日10:00开始输注红细胞2U，12:00输毕，过程顺利。"
    result = await _run("LX0609-07-02-01", {
        "inpat_nondrug_order": [OPEN_TRANSFUSION_ORDER], "inpat_drug_order": [],
        "senior_course_record": [{"document_id": "synthetic-senior-transfusion",
                                  "record_time": "2026-06-02 13:00:00", "record_content": body}],
    }, {body: "record"})
    assert result["final"]["status"] == "compliant", result["final"]


@pytest.mark.asyncio
async def test_regular_pretransfusion_check_uses_explicit_start_in_dedicated_body():
    from test_luxian_0609_transfusion_performance_043_047 import _run, REGULAR_ITEM_LABS
    from transfusion_order_test_support import FrozenTransfusionProtocolClient

    body = "2026年06月05日 14:20开始输注红细胞2U，16:20输毕。"

    class Client(FrozenTransfusionProtocolClient):
        async def generate(self, prompt, **kwargs):
            if SCHEMA_VERSION in prompt:
                return {"choices": [{"message": {"content": json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "documents": [{"document_ref": "d1", "state": "performed", "quote": body,
                                   "start_time_quote": "2026年06月05日 14:20"}],
                }, ensure_ascii=False)}, "finish_reason": "stop"}]}
            return await super().generate(prompt, **kwargs)

    result = await _run("LX0609-07-01-01", {
        "bloodtrans_record": [{"document_id": "synthetic-time-in-body", "record_content": body}],
        "labtest_item_report": REGULAR_ITEM_LABS,
    }, {body: "record"}, client=Client(course_labels={body: "record"}))
    assert result["final"]["status"] == "compliant", result["final"]


@pytest.mark.asyncio
@pytest.mark.parametrize("title,expected", [("主治医师查房记录", "non_compliant"), ("输血后效果评价记录", "compliant")])
async def test_posttransfusion_effect_in_senior_course_keeps_24_hour_window(title, expected):
    from test_luxian_0609_transfusion_performance_043_047 import _run, FIRST_RECORD_NO_EVALUATION
    from transfusion_order_test_support import FrozenTransfusionProtocolClient

    result = await _run("LX0609-07-03-01", {
        "bloodtrans_record": [{"document_id": "synthetic-performed", "record_time": "2026-06-05 16:30:00", "record_content": FIRST_RECORD_NO_EVALUATION}],
        "senior_course_record": [{"document_title": title, "document_id": "synthetic-effect", "record_time": "2026-06-06 09:00:00",
                                  "record_content": "输血后复查血红蛋白较前改善，输血有效。"}],
    }, {FIRST_RECORD_NO_EVALUATION: "record"}, horizon_date="2026-06-07", client=FrozenTransfusionProtocolClient(
        course_labels={FIRST_RECORD_NO_EVALUATION: "record"},
        effect_labels={"输血后复查血红蛋白较前改善，输血有效。": ("evaluated", "输血后复查血红蛋白较前改善，输血有效。")},
    ))
    assert result["final"]["status"] == expected, result["final"]


@pytest.mark.asyncio
@pytest.mark.parametrize("title,expected", [("主治医师查房记录", "non_compliant"), ("输血后效果评价记录", "compliant")])
async def test_posttransfusion_objective_lab_trend_in_senior_course_is_evaluation(title, expected):
    from test_luxian_0609_transfusion_performance_043_047 import _run, FIRST_RECORD_NO_EVALUATION
    from transfusion_order_test_support import FrozenTransfusionProtocolClient

    result = await _run("LX0609-07-03-01", {
        "bloodtrans_record": [{"document_id": "synthetic-performed", "record_time": "2026-06-05 16:30:00", "record_content": FIRST_RECORD_NO_EVALUATION}],
        "senior_course_record": [{"document_title": title, "document_id": "synthetic-lab-effect", "record_time": "2026-06-06 09:00:00",
                                  "record_content": "今日复查血常规示HGB 84g/L，较前明显上升，继续观察。"}],
    }, {FIRST_RECORD_NO_EVALUATION: "record"}, horizon_date="2026-06-07", client=FrozenTransfusionProtocolClient(
        course_labels={FIRST_RECORD_NO_EVALUATION: "record"},
        effect_labels={"今日复查血常规示HGB 84g/L，较前明显上升，继续观察。": ("evaluated", "今日复查血常规示HGB 84g/L，较前明显上升，继续观察。")},
    ))
    assert result["final"]["status"] == expected, result["final"]


@pytest.mark.asyncio
async def test_nine_items_order_without_performance_is_unresolved():
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected

    _, _, result, _ = await _evaluate_selected(("LX0609-07-01-03",), {
        "inpat_nondrug_order": [{"order_id": "synthetic-order", "order_name": "输注红细胞2U", "order_status": "新开"}],
    })
    assert result.decisions[0].reason_code != "trigger_absent_complete"


@pytest.mark.asyncio
@pytest.mark.parametrize("title,expected", [("主治医师查房记录", "non_compliant"), ("输血前评估", "compliant")])
async def test_pretransfusion_assessment_reads_full_senior_course_body(title, expected):
    from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER
    from test_luxian_0609_transfusion_performance_043_047 import _run, FIRST_RECORD

    assessment = "一般情况记录。" * 250 + "输血前评估：存在输血指征，贫血，输血风险已评估，既往无不良反应。"
    result = await _run("LX0609-07-01-02", {
        "inpat_nondrug_order": [OPEN_TRANSFUSION_ORDER], "inpat_drug_order": [],
        "bloodtrans_record": [{"document_id": "synthetic-blood", "record_time": "2026-06-05 17:00:00",
                               "transfusion_start_time": "2026-06-05 14:20:00", "record_content": FIRST_RECORD}],
        "senior_course_record": [{"document_title": title, "document_id": "synthetic-full-senior", "record_time": "2026-06-05 09:00:00", "record_content": assessment}],
    }, {FIRST_RECORD: "record"})
    assert result["final"]["status"] == expected, result["final"]


@pytest.mark.asyncio
async def test_multi_transfer_outcome_survives_binding_and_finalization():
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected, _canonical_extended_result

    rule = "LX0609-10-02-01"
    snapshot, materials, result, reduced = await _evaluate_selected((rule,), {
        "inpat_nondrug_order": [
            {"order_id": "synthetic-first-order", "order_name": "转入内科", "order_time": "2026-06-01 10:00:00"},
            {"order_id": "synthetic-second-order", "order_name": "转入外科", "order_time": "2026-06-05 10:00:00"},
        ],
        "transfer_in_record": [
            {"document_id": "synthetic-first-in", "record_time": "2026-06-02 12:00:00"},
            {"document_id": "synthetic-second-in", "record_time": "2026-06-05 12:00:00"},
        ],
        "transfer_out_record": [
            {"document_id": "synthetic-first-out", "record_time": "2026-06-01 11:00:00"},
            {"document_id": "synthetic-second-out", "record_time": "2026-06-05 11:00:00"},
        ],
    })
    final = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials, result=result, reduced=reduced)
    assert final["status"] == "non_compliant", final
    assert "synthetic-first-in" in {item["source_document_id"] for item in final["customer_evidence"]}


def test_overlapping_transfer_windows_remain_unassociated():
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02", nondrug_order_error="", transfer_in_error="", transfer_out_error="",
        nondrug_order_rows=[
            {"order_name": "转入内科", "order_time": "2026-06-01 10:00:00"},
            {"order_name": "转入外科", "order_time": "2026-06-01 10:02:00"},
        ], transfer_in_rows=[{"record_time": "2026-06-01 11:00:00"}],
        transfer_out_rows=[{"record_time": "2026-06-01 10:30:00"}],
    )
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_unrelated_symptom_improvement_is_not_transfusion_effect():
    from test_luxian_0609_transfusion_performance_043_047 import _run, FIRST_RECORD_NO_EVALUATION

    result = await _run("LX0609-07-03-01", {
        "bloodtrans_record": [{"document_id": "synthetic-performed", "record_time": "2026-06-05 16:30:00", "record_content": FIRST_RECORD_NO_EVALUATION}],
        "senior_course_record": [{"document_id": "synthetic-unrelated", "record_time": "2026-06-06 09:00:00",
                                  "record_content": "继续联系红细胞输注；患者腹痛较前缓解，继续解痉治疗。"}],
    }, {FIRST_RECORD_NO_EVALUATION: "record"}, horizon_date="2026-06-07")
    assert result["final"]["status"] == "non_compliant", result["final"]


@pytest.mark.parametrize("name,abbreviation,expected", [
    ("乙型肝炎病毒表面抗原定性", "HBsAg", "hbsag"),
    ("乙型肝炎病毒表面抗体定性", "Anti-HBs", "hbsab"),
    ("乙型肝炎E抗原定性", "HBeAg", "hbeag"),
    ("乙型肝炎E抗体定性", "Anti-HBe", "hbeab"),
    ("乙型肝炎核心抗体定性", "Anti-HBc", "hbcab"),
    ("丙型肝炎抗体测定", "HCVAb", "hcv"),
    ("人免疫缺陷病毒抗原抗体检测", "HIVAgAb", "hiv"),
])
def test_pretransfusion_labs_accept_standard_long_names_and_abbreviations(name, abbreviation, expected):
    from app.services.luxian_0609.native_transfusion_execution import resolve_pretransfusion_required_item

    assert resolve_pretransfusion_required_item({"item_name": name, "item_abbreviation": abbreviation}) == expected


@pytest.mark.asyncio
async def test_nine_items_use_admission_document_when_registration_lacks_admission_time():
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected
    from test_luxian_0609_transfusion_performance_043_047 import NINE_ITEM_LABS

    _, _, result, reduced = await _evaluate_selected(("LX0609-07-01-03",), {
        "inpat_registration": [{"discharge_datetime": "2026-06-06 12:00:00"}],
        "admission_record": [{"document_id": "synthetic-admission", "admission_datetime": "2026-06-01 10:00:00"}],
        "mr_bloodtrans": [{"document_id": "synthetic-event", "transfution_datetime": "2026-06-05 14:20:00"}],
        "labtest_item_report": NINE_ITEM_LABS,
    })
    assert reduced[0].final_state.value == "compliant", result.decisions


@pytest.mark.asyncio
async def test_course_summary_time_cannot_replace_actual_transfusion_start():
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected
    from test_luxian_0609_transfusion_performance_043_047 import NINE_ITEM_LABS

    body = "本次住院已予输血，过程顺利。"

    class Client:
        async def generate(self, prompt, **kwargs):
            data = json.loads(prompt.split("INPUT_JSON=", 1)[1])
            if "records" in data:
                payload = {"schema_version": "lx0609-transfusion-course-presence-v1", "records": [
                    {"index": row["index"], "kind": "record", "quote": row["content"]} for row in data["records"]
                ]}
            else:
                payload = {"schema_version": SCHEMA_VERSION, "documents": [
                    {"document_ref": "d1", "state": "performed", "quote": body, "start_time_quote": None},
                ]}
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

    _, _, result, reduced = await _evaluate_selected(("LX0609-07-01-03",), {
        "inpat_registration": [{"admission_datetime": "2026-06-01 10:00:00"}],
        "senior_course_record": [{"document_id": "synthetic-summary", "record_time": "2026-06-05 16:00:00", "record_content": body}],
        "labtest_item_report": NINE_ITEM_LABS,
    }, llm_client=Client())
    assert reduced[0].final_state.value == "data_gap", result.decisions


@pytest.mark.asyncio
async def test_explicit_transfusion_start_does_not_require_document_time():
    body = "2026年06月02日 14:20开始输注红细胞2U，16:20结束。"

    class Client:
        async def generate(self, prompt, **kwargs):
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                "schema_version": SCHEMA_VERSION,
                "documents": [{"document_ref": "d1", "state": "performed",
                               "quote": body, "start_time_quote": "2026年06月02日 14:20"}],
            }, ensure_ascii=False)}}]}

    result = await extract_transfusion_performance([
        {"document_id": "synthetic-transfusion", "record_content": body, "record_time": None},
    ], Client())
    assert result.states == ("performed",)
    assert result.event_times == (datetime(2026, 6, 2, 14, 20),)


@pytest.mark.parametrize("daily_rows", [[], [{
    "document_id": "synthetic-old-course",
    "record_time": "2026-06-01 09:00:00",
    "record_content": "病情稳定。",
}]])
def test_complete_course_sources_without_window_record_are_clinical_defect(daily_rows):
    outcome = evaluate_predischarge_course_presence(
        death_state="absent", death_error="", registration_error="",
        discharge_error="", discharge_time=datetime(2026, 6, 5, 12),
        daily_error="", senior_error="", daily_rows=daily_rows, senior_rows=[],
    )
    assert (outcome.final_state, outcome.reason_code) == (
        "non_compliant", "required_document_missing",
    )


@pytest.mark.parametrize("text", [
    "18:00 输注A型悬浮红细胞2U，过程顺利。",
    "输血2U过程顺利，无不良反应。",
    "今日予输注血浆200ml。",
    "患者既往有输血史。",
    "拟申请输血。",
])
def test_course_candidate_selector_keeps_every_transfusion_mention(text):
    """候选筛选只求召回；本次实施、既往史与计划由受控抽取区分。"""
    from app.services.luxian_0609.transfusion_course_presence import select_transfusion_course_candidates

    assert select_transfusion_course_candidates([{"record_content": text}]) == ({"record_content": text},)


def test_course_candidate_selector_drops_rows_without_transfusion_mention():
    from app.services.luxian_0609.transfusion_course_presence import select_transfusion_course_candidates

    rows = [{"record_content": "患者咳嗽减轻，继续抗感染治疗。"}, {"content": "复查血常规。"}]
    assert select_transfusion_course_candidates(rows) == ()


@pytest.mark.parametrize("out_row,expected", [
    # 早于医嘱几分钟、未填科室：单次转科唯一候选，按时间接受（Claude 代定 2026-10-22，C03/C09）。
    ({"record_time": "2026-06-01 09:55:00"}, "compliant"),
    # 填了科室但与医嘱不对应：仍不接受。
    ({"record_time": "2026-06-01 09:55:00", "transferin_department": "骨科"}, "data_gap"),
])
def test_early_transfer_out_record_without_department_fields_is_accepted_for_single_transfer(out_row, expected):
    outcome = evaluate_transfer_documentation(
        rule_id="LX0609-10-02-02", nondrug_order_error="", transfer_in_error="", transfer_out_error="",
        nondrug_order_rows=[{"order_name": "转入内科", "order_time": "2026-06-01 10:00:00"}],
        transfer_in_rows=[{"record_time": "2026-06-01 12:00:00"}],
        transfer_out_rows=[out_row],
        evaluation_horizon_datetime=datetime(2026, 6, 8),
    )
    assert outcome.final_state == expected
