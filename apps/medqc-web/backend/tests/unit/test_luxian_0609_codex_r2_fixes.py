"""Codex Round-2 复审反例回归单测（全合成无 PHI）：
1. P1 · 危急值 06-04-01/02：
   - 1a: 分句级否定/条件计划（未予补钾、若再次下降再予补钾）vs 既往未处理+后续已执行（当时尚未处理；10:20 已静脉补钾）；
   - 1b: 数值绑定最近检验项目标签（血钾 2.8 + 血糖 2.5 mmol/L 绝不得串配第二份血钾 2.5 报告）。
2. P1 · 特殊级抗菌药 05-01-06：
   - 连续文书内授权专家段落之后切换为临床药师/药学会诊/非授权发言人时，所有分支均严格拒绝借用专家署名，
     同时保留 C04（请临床药学会诊后同意加用）及 #02/#04/#05/#09 真实授权场景。
3. P2 · 转科记录 10-02-02/01：
   - transfer_date 显式晚于医嘱日期（如 27日 10:00 医嘱 vs transfer_date=28日）时，
     无论 record_time 在医嘱前（09:30）或医嘱后（10:01）均不得满足本次医嘱。
4. Acceptance Matrix 对齐：
   - LX0609-06-02-02、LX0609-06-02-03、LX0609-01-01-02 的 max_llm_calls_per_rule 与语义契约均为 2。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.extended_document import antimicrobial_family as amf
from app.services.luxian_0609.extended_document import critical_value_family as cvf
from tests.unit.test_luxian_0609_p0_extended_doc_fixes import _run_rules
from tests.unit.test_luxian_0609_s3_extended_doc_fixes import (
    _TargetedSpecialApprovalClient,
)


# =====================================================================
# 1a. P1 · 危急值分句级否定/条件 vs 后续已执行处置
# =====================================================================


@pytest.mark.parametrize(
    "body,expected",
    [
        # Codex Round-2 精确反例
        ("血钾危急值 2.8，未予补钾", False),
        ("血钾危急值 2.8，若再次下降再予补钾", False),
        ("血钾危急值 2.8，若再次下降，再予补钾", False),
        ("血钾危急值 2.8，如果继续下降则予补钾", False),
        ("血钾危急值 2.8，必要时再予补钾", False),
        ("血钾危急值 2.8，待复查后再决定是否补钾", False),
        ("血钾危急值 2.8，暂未予补钾，不予处理", False),
        ("收到血钾危急值，尚未处理，等待医师", False),
        # 历史未处理分句不得否决后续明确已执行动作
        ("当时尚未处理；10:20 已静脉补钾", True),
        ("当时尚未处理，10:20 已静脉补钾", True),
        ("接血钾危急值2.50mmol/L，暂未复查，已予补钾处理。", True),
        ("接检验科报告危急值：PT 35.34S，患者家属已签字拒绝再次输血治疗，故密切观察出血表现。", True),
        ("若复查仍低再予补钾，目前已予口服氯化钾补钾。", True),
    ],
)
def test_codex_r2_1a_affirmative_critical_value_handling_clause_semantics(
    body: str, expected: bool
) -> None:
    assert cvf._has_affirmative_critical_value_handling(body) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "title,content,expected_status",
    [
        ("危急值处理记录", "血钾危急值 2.8，未予补钾", "non_compliant"),
        ("日常病程记录", "血钾危急值 2.8，未予补钾", "non_compliant"),
        ("危急值处理记录", "血钾危急值 2.8，若再次下降再予补钾", "non_compliant"),
        ("日常病程记录", "血钾危急值 2.8，若再次下降，再予补钾", "non_compliant"),
        ("危急值处理记录", "收到血钾危急值，尚未处理，等待医师", "non_compliant"),
        ("危急值处理记录", "血钾危急值 2.8，当时尚未处理；10:20 已静脉补钾", "compliant"),
        ("日常病程记录", "血钾危急值 2.8mmol/L，当时尚未处理；10:20 已静脉补钾", "compliant"),
    ],
)
async def test_codex_r2_1a_crisis_rules_end_to_end_negated_conditional_and_executed(
    title: str, content: str, expected_status: str
) -> None:
    rows = {
        "labtest_master": ({"test_id": "t-k1", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {
                "document_id": "li-k1",
                "test_id": "t-k1",
                "item_name": "钾离子",
                "result": "2.8",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-1",
                "document_title": title,
                "record_time": "2026-06-01 08:20:00",
                "record_content": content,
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == expected_status
    assert finals["LX0609-06-04-02"]["status"] == expected_status


# =====================================================================
# 1b. P1 · 危急值数值项目归属绑定（血糖 2.5 不得满足血钾 2.5）
# =====================================================================


@pytest.mark.parametrize(
    "item_name,tokens,text,expected",
    [
        # 血钾 2.8 命中，血糖 2.5 严禁命中血钾 2.5
        ("钾离子", ("2.8",), "血钾 2.8，已静脉补钾，血糖 2.5 mmol/L", True),
        ("钾离子", ("2.5",), "血钾 2.8，已静脉补钾，血糖 2.5 mmol/L", False),
        ("钾离子", ("2.5",), "血钾 2.8，已静脉补钾；血糖 2.5 mmol/L", False),
        ("钾离子", ("2",), "血钾 2.8，已静脉补钾，血糖 2 mmol/L", False),
        # 药物剂量 2.5g 不得误作血钾 2.5
        ("钾离子", ("2.5",), "血钾 2.8，予氯化钾 2.5g 静脉补钾", False),
        # 真实 EMR 缩写 K 2.50mmol/l 紧接 Alb 32.0g/L 须正确识别为血钾
        ("钾离子", ("2.50", "2.5"), "生化示Alb 32.0g/L,K 2.50mmol/l,Na 139.1mmol/l", True),
        # 同一句多检验项目各归各值
        (
            "二氧化碳分压",
            ("18.00", "18"),
            "床旁血气分析危急值报告：pH 7.74,pCO2 18.00mmHg,钾测定:K+ 2.60mmol/L。",
            True,
        ),
        (
            "pH",
            ("18.00", "18"),
            "床旁血气分析危急值报告：pH 7.74,pCO2 18.00mmHg,钾测定:K+ 2.60mmol/L。",
            False,
        ),
        (
            "钾离子",
            ("2.60", "2.6"),
            "床旁血气分析危急值报告：pH 7.74,pCO2 18.00mmHg,钾测定:K+ 2.60mmol/L。",
            True,
        ),
    ],
)
def test_codex_r2_1b_value_match_is_bound_to_nearest_lab_item_label(
    item_name: str, tokens: tuple[str, ...], text: str, expected: bool
) -> None:
    keywords = cvf._critical_value_item_keywords(item_name)
    assert (
        cvf._text_mentions_critical_result_value(text, text.lower(), tokens, keywords)
        is expected
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["日常病程记录", "危急值处理记录"])
async def test_codex_r2_1b_two_potassium_reports_glucose_2_5_never_credits_second_potassium(
    title: str,
) -> None:
    """Codex Round-2 精确反例：2 份血钾报告（2.8 与 2.5），病程仅处理血钾 2.8 且提及血糖 2.5 mmol/L。"""
    rows = {
        "labtest_master": (
            {"test_id": "t-k1", "labtest_subject": "电解质"},
            {"test_id": "t-k2", "labtest_subject": "电解质"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-k1",
                "test_id": "t-k1",
                "item_name": "钾离子",
                "result": "2.8",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
            {
                "document_id": "li-k2",
                "test_id": "t-k2",
                "item_name": "钾离子",
                "result": "2.5",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 10:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-1",
                "document_title": title,
                "record_time": "2026-06-01 10:30:00",
                "record_content": "血钾 2.8 mmol/L，已静脉补钾，动态复查；同日测血糖 2.5 mmol/L。",
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "non_compliant"
    assert finals["LX0609-06-04-02"]["status"] == "non_compliant"
    outcomes_by_time = {
        ev["report_time"]: ev["outcome"]
        for ev in finals["LX0609-06-04-02"]["customer_display_facts"]["event_results"]
    }
    assert outcomes_by_time == {
        "2026-06-01 08:00:00": "handled",
        "2026-06-01 10:00:00": "unhandled",
    }


# =====================================================================
# 2. P1 · 特殊级抗菌药 05-01-06 连续文书发言人切换守卫
# =====================================================================


@pytest.mark.parametrize(
    "text,quote,expected",
    [
        # Codex Round-2 精确反例：感染科专家段后切换为临床药师/临床药学会诊/非授权发言人
        (
            "感染科副主任医师意见：病情待查。\n临床药师会诊意见：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n临床药师会诊意见：同意使用美罗培南。",
            "临床药师会诊意见：同意使用美罗培南。",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n临床药师：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n临床药学会诊：同意使用。",
            "同意使用",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。临床药师会诊意见：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n药师会诊意见：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n药学部：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n经治医师：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。\n呼吸科副主任医师：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "感染科副主任医师意见：病情待查。呼吸科副主任医师意见：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        (
            "专家会诊：病情待查。\n临床药师：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        # 扩展上下文（>80字）内切换非授权发言人同样必须拒绝
        (
            "故请ICU合成甲主任医师行抗生素使用权限会诊，患者反复发热，炎症指标偏高，目前抗感染方案待评估，暂继续观察生命体征及痰培养药敏回报情况。\n"
            "临床药师会诊意见：同意使用美罗培南。",
            "同意使用美罗培南",
            False,
        ),
        # 申请单+副高意见但引文自身夹带后续临床药师切换
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:病情待查。临床药师:同意使用美罗培南。",
            "合成甲副主任医师会诊意见:病情待查。临床药师:同意使用美罗培南。",
            False,
        ),
        # 关键正向保护：C04（授权专家句内提及“请临床药学会诊后”）必须保持 True
        (
            "感染科张某副主任医师会诊意见：抗感染效果不佳，请临床药学会诊后同意加用万古霉素联合抗感染。",
            "请临床药学会诊后同意加用万古霉素联合抗感染",
            True,
        ),
        # 关键正向保护：#02/#04/#05/#09 真实结构必须保持 True
        (
            "鉴于临床药学会诊意见,故请ICU合成甲主任医师行抗生素使用权限会诊,"
            "经会诊后指出:2025-12-14 痰培养肺炎克雷伯菌多耐。故同意使用美罗培南加强抗感染治疗。",
            "同意使用美罗培南加强抗感染治疗",
            True,
        ),
        (
            "感染性疾病科合成乙,2026-04-07,09:59:00病史敬悉同意使用，美罗培南加强抗感染。",
            "同意使用，美罗培南加强抗感染",
            True,
        ),
        (
            "请会诊执行记录\n临床药学会诊后建议给予美罗培南抗感染，故邀请重症医学科合成丙医生协助诊治：患者重症肺部感染，同意使用美罗培南加强抗感染。",
            "同意使用美罗培南加强抗感染",
            True,
        ),
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成丁副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "合成丁副主任医师会诊意见:同意升级抗生素为美罗培南。",
            True,
        ),
    ],
)
def test_codex_r2_2_special_approval_blocks_non_authorized_speaker_switch(
    text: str, quote: str, expected: bool
) -> None:
    assert amf._special_approval_by_authorized_expert(text, quote) is expected


@pytest.mark.asyncio
async def test_codex_r2_2_special_antimicrobial_end_to_end_rejects_pharmacist_paragraph_after_id_expert() -> None:
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "注射用美罗培南",
                "drug_apply_method": "静脉滴注",
                "order_status": "已执行",
                "planned_start_datetime": "2026-07-05 12:00:00+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": "cons-mixed",
                "document_title": "请会诊执行记录",
                "record_time": "2026-07-05 10:00:00",
                "record_content": (
                    "感染科副主任医师意见：病情待查。\n"
                    "临床药师会诊意见：同意使用美罗培南。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-07-10", "basis": "discharge_date"},),
    }
    client = _TargetedSpecialApprovalClient({"美罗培南": "同意使用美罗培南"})
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "non_compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "required_document_missing"


# =====================================================================
# 3. P2 · 转科记录 10-02-02/01：transfer_date 晚于医嘱日期不得满足本次医嘱
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-10-02-02", "LX0609-10-02-01"])
@pytest.mark.parametrize(
    "record_time,transfer_date",
    [
        ("2026-06-27 09:30:00", "2026-06-28"),  # 医嘱前、书写日早于声明转科日
        ("2026-06-27 10:01:00", "2026-06-28"),  # 医嘱后、书写日早于声明转科日（Codex Round-2 精确反例）
        ("2026-06-29 08:00:00", "2026-06-29"),  # 超出医嘱 24h 日期边界的后续事件转科日
        (None, "2026-06-28"),  # 缺书写时间但显式标注次日 transfer_date，不得误判为 time_unknown
    ],
)
async def test_codex_r2_3_single_transfer_future_transfer_date_never_satisfies_order(
    rule_id: str, record_time: str | None, transfer_date: str
) -> None:
    out_row: dict[str, object] = {"document_id": "U-NEXT", "transfer_date": transfer_date}
    if record_time is not None:
        out_row["record_time"] = record_time
    rows = {
        "inpat_registration": (
            {"admission_datetime": "2026-06-20 08:00:00", "discharge_datetime": "2026-07-05 10:00:00"},
        ),
        "inpat_nondrug_order": (
            {
                "order_id": "O1",
                "order_name": "转入内四科",
                "order_status": "核实",
                "prescribed_datetime": "2026-06-27 10:00:00",
            },
        ),
        "transfer_in_record": ({"document_id": "I1", "record_time": "2026-06-27 10:28:16"},),
        "transfer_out_record": (out_row,),
        "evaluation_context.horizon": (
            {
                "horizon_date": "2026-07-05",
                "horizon_datetime": "2026-07-05 10:00:00",
                "basis": "discharge_date",
                "task_frozen_date": "2026-07-10",
            },
        ),
    }
    _, finals = await _run_rules((rule_id,), rows)
    assert finals[rule_id]["status"] == "non_compliant"
    assert finals[rule_id]["reason_code"] == "required_document_missing"
    if rule_id == "LX0609-10-02-02":
        assert finals[rule_id]["customer_display_facts"]["transfer_out_associated"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("record_time", ["2026-06-27 09:30:00", "2026-06-27 10:01:00"])
async def test_codex_r2_3_multi_transfer_future_transfer_date_never_satisfies_today_order(
    record_time: str,
) -> None:
    rows = {
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入ICU", "order_status": "核实", "prescribed_datetime": "2026-06-23 16:32:26"},
            {"order_id": "O2", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 10:00:00"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-23 17:03:00"},
            {"document_id": "I2", "record_time": "2026-06-27 10:28:16"},
        ),
        "transfer_out_record": (
            {"document_id": "U1", "record_time": "2026-06-23 16:33:00"},
            {"document_id": "U2-NEXT", "record_time": record_time, "transfer_date": "2026-06-28"},
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "non_compliant"
    assert finals["LX0609-10-02-02"]["reason_code"] == "required_document_missing"


@pytest.mark.asyncio
async def test_codex_r2_3_unrelated_future_transfer_date_record_does_not_conflict_with_current_record() -> None:
    rows = {
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 10:00:00"},
        ),
        "transfer_in_record": ({"document_id": "I1", "record_time": "2026-06-27 10:28:16"},),
        "transfer_out_record": (
            {"document_id": "U1-CUR", "record_time": "2026-06-27 10:05:00", "transfer_date": "2026-06-27"},
            {"document_id": "U2-FUTURE", "record_time": "2026-06-27 10:10:00", "transfer_date": "2026-06-28"},
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "compliant"
    assert finals["LX0609-10-02-02"]["reason_code"] == "requirement_satisfied"


# =====================================================================
# 4. Acceptance Matrix max_llm_calls_per_rule 对齐校验
# =====================================================================


def test_codex_r2_4_acceptance_matrix_aligns_retry_rules_to_max_2_llm_calls() -> None:
    matrix_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "data"
        / "luxian_0609_acceptance_matrix.json"
    )
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    by_id = {rule["rule_id"]: rule for rule in payload["rules"]}
    for rule_id in ("LX0609-06-02-02", "LX0609-06-02-03", "LX0609-01-01-02"):
        rule = by_id[rule_id]
        assert rule["max_llm_calls_per_rule"] == 2
        assert rule["semantic_contract"]["max_llm_calls_per_rule"] == 2
