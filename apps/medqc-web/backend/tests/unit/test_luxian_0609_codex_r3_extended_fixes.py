"""Codex Round-3 复审反例回归单测（全合成无 PHI）：
1. 危急值 06-04-01/02：
   - 1a: 紧跟冒号的检验实测值（血钾：6.7 mmol/L、pH:7.18、pCO2:71）不得被误作时钟排除，
         同时真实时钟（08:25、10:20、2026-06-01T08:25）仍严格排除；
   - 1b: 按目标危急值事件逐句绑定已执行临床处置，严禁“血钾危急值 2.8，未予补钾。另因发热予以退热治疗”
         借无关治疗过关，同时保留既有已执行重置、直接承接句、专用危急值单事件标题与 ICU 呼吸机处置。
2. 特殊级抗菌药 05-01-06：
   - 支配发言人守卫：无论引文是否含“同意特殊级”等短语，只要紧邻前文的直接支配发言人为
     临床药师/药师/主治/住院/他科医师且未再切换回授权专家，所有分支均立即拒绝；
     同时保留 C04、多行缩进感染科专家落款、匿名专家支持及 #02/#04/#05/#09 真实结构。
3. 跨午夜转科 10-02-01/02：
   - 23:55 医嘱 + 次日 00:10/00:20 书写且 transfer_date=次日，单次与多次转科均判 compliant；
   - 既有 27日 09:30/10:01 书写但 transfer_date=28日、缺书写时间且 transfer_date=28日、
     以及超出 24h 日期边界（transfer_date=29日）的记录仍严格判 non_compliant。
"""

from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from tests.unit.test_luxian_0609_p0_extended_doc_fixes import _run_rules
from tests.unit.test_luxian_0609_s3_extended_doc_fixes import (
    _TargetedSpecialApprovalClient,
)


# =====================================================================
# 1a. 危急值紧跟冒号检验值 vs 真实时钟排除
# =====================================================================


@pytest.mark.parametrize(
    "item_name,tokens,text,expected",
    [
        # Codex Round-3 精确反例：冒号后无空格与有空格均须匹配
        ("钾离子", ("6.7",), "血钾：6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。", True),
        ("钾离子", ("6.7",), "血钾： 6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。", True),
        ("钾离子", ("6.7",), "血钾:6.7mmol/L，已予降钾治疗。", True),
        ("pH", ("7.18",), "血气分析 pH:7.18，予碳酸氢钠纠酸。", True),
        ("pH", ("7.18",), "血气分析 pH：7.18，予碳酸氢钠纠酸。", True),
        ("二氧化碳分压", ("71.00", "71"), "血气分析 pCO2:71.00mmHg，调整呼吸机参数。", True),
        ("氧分压", ("55",), "血气分析 pO2:55mmHg，上调氧流量。", True),
        ("血小板计数", ("21",), "血常规 血小板：21×10^9/L，预约输注血小板。", True),
        # 真实时钟严禁误作检验实测值
        ("血小板计数", ("25",), "于08:25接检验科危急值报告，血小板偏低，已予处理。", False),
        ("血小板计数", ("20",), "血小板危急值，当时尚未处理；10:20 已予处理。", False),
        ("血小板计数", ("25",), "记录时间2026-06-01T08:25，血小板危急值已处理。", False),
        ("血小板计数", ("08", "8"), "于08:25接检验科血小板危急值报告，已予处理。", False),
    ],
)
def test_codex_r3_1a_colon_adjacent_lab_value_matches_while_clock_times_excluded(
    item_name: str, tokens: tuple[str, ...], text: str, expected: bool
) -> None:
    keywords = ned._critical_value_item_keywords(item_name)
    assert (
        ned._text_mentions_critical_result_value(text, text.lower(), tokens, keywords)
        is expected
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["日常病程记录", "危急值处理记录"])
@pytest.mark.parametrize(
    "content",
    [
        "血钾：6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。",
        "血钾： 6.7 mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。",
        "血钾:6.7mmol/L，已予葡萄糖酸钙及胰岛素降钾治疗。",
    ],
)
async def test_codex_r3_1a_potassium_colon_without_space_counts_as_one_disposition(
    title: str, content: str
) -> None:
    rows = {
        "labtest_master": ({"test_id": "t-k-high", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {
                "document_id": "li-k-high",
                "test_id": "t-k-high",
                "item_name": "钾离子",
                "result": "6.7",
                "abnormal_indicator": "PH",
                "report_time": "2026-06-01 08:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-k-high",
                "document_title": title,
                "record_time": "2026-06-01 08:15:00",
                "record_content": content,
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["customer_display_facts"]["event_results"][0]["outcome"] == "handled"


# =====================================================================
# 1b. 危急值按事件/项目绑定已执行临床处置（无关发热退热不得替未补钾过关）
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["日常病程记录", "危急值处理记录"])
@pytest.mark.parametrize(
    "content,expected_status",
    [
        # Codex Round-3 精确反例：血钾未予补钾 + 无关发热退热 -> 0 处置
        ("血钾危急值 2.8，未予补钾。另因发热予以退热治疗", "non_compliant"),
        ("血钾危急值 2.8 mmol/L，未予补钾，另因发热予以退热治疗。", "non_compliant"),
        ("血钾危急值 2.8，未予补钾。此外因头痛予以镇痛治疗。", "non_compliant"),
        ("血钾危急值 2.8，未予补钾。血压升高予以硝苯地平降压。", "non_compliant"),
        ("血钾危急值 2.8，未予补钾。血糖 2.5 mmol/L，予以静脉推注高糖。", "non_compliant"),
        ("收到血钾危急值 2.8，尚未处理，等待医师。另因发热予以退热治疗。", "non_compliant"),
        ("血钾危急值 2.8，若再次下降再予补钾。另因发热予以退热治疗。", "non_compliant"),
        # 既有反例继续保持 non_compliant
        ("血钾危急值 2.8，若再次下降再予补钾", "non_compliant"),
        ("收到血钾危急值，尚未处理，等待医师", "non_compliant"),
        # 正向保护：真正针对血钾的已执行处置必须保持 compliant
        ("血钾危急值 2.8，当时尚未处理；10:20 已静脉补钾", "compliant"),
        ("血钾危急值 2.8，未予补钾。10:20 已静脉补钾。", "compliant"),
        ("血钾危急值 2.8，未予补钾。复查电解质并予以口服氯化钾补钾。", "compliant"),
    ],
)
async def test_codex_r3_1b_unrelated_treatment_never_satisfies_negated_potassium_event(
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


@pytest.mark.asyncio
async def test_codex_r3_1b_multi_event_note_credits_handled_ph_but_rejects_negated_potassium() -> None:
    """同一病程记录中 pH 已予纠酸而血钾明确未予补钾，仅 pH 计为已处置，血钾必须为未处置。"""
    rows = {
        "labtest_master": (
            {"test_id": "t-k", "labtest_subject": "电解质"},
            {"test_id": "t-bg", "labtest_subject": "血气分析"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-k",
                "test_id": "t-k",
                "item_name": "钾离子",
                "result": "2.8",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
            {
                "document_id": "li-ph",
                "test_id": "t-bg",
                "item_name": "pH",
                "result": "7.18",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:05:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-mix",
                "document_title": "危急值处理记录",
                "record_time": "2026-06-01 08:20:00",
                "record_content": "血钾危急值 2.8，未予补钾。pH:7.18，已予碳酸氢钠纠酸并动态复查血气。",
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
        "2026-06-01 08:00:00": "unhandled",
        "2026-06-01 08:05:00": "handled",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item_name,result_val,title,content",
    [
        # 直接承接句（前句未否定，后句无无关主题切换）
        ("肌酐", "750", "日常病程记录", "接危急值报告：肌酐 750 umol/L。已请肾内科会诊，予对症支持治疗。"),
        # 单事件专用《危急值处理记录》标题兜底（未提及具体项目名但有明确处理且无否定/无关主题）
        ("钾离子", "2.8", "危急值处理记录", "接检验科危急值报告，已予对症处理并复查。"),
        # ICU 呼吸机管理同句包含“镇静镇痛”与“继续呼吸机辅助通气”
        (
            "二氧化碳分压",
            "72",
            "日常病程记录",
            "血气分析示二氧化碳分压 72 mmHg。予镇静镇痛，继续呼吸机辅助通气，加强排痰，复查血气。",
        ),
    ],
)
async def test_codex_r3_1b_valid_continuation_generic_title_and_icu_ventilation_remain_compliant(
    item_name: str, result_val: str, title: str, content: str
) -> None:
    rows = {
        "labtest_master": ({"test_id": "t-1", "labtest_subject": "检验"},),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": item_name,
                "result": result_val,
                "abnormal_indicator": "PH",
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
    assert finals["LX0609-06-04-01"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"


# =====================================================================
# 2. 特殊级抗菌药 05-01-06 支配发言人守卫（“同意特殊级”不得绕过临床药师）
# =====================================================================


@pytest.mark.parametrize(
    "text,quote,expected",
    [
        # Codex Round-3 精确反例：临床药师意见下出现“同意特殊级”
        (
            "感染科主任意见：待进一步诊治。\n临床药师意见：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任意见：待进一步诊治。\n临床药师：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "临床药师意见：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任意见：待进一步诊治。\n临床药学会诊：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任意见：待进一步诊治。\n药师：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任意见：待进一步诊治。\n主治医师：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "感染科主任意见：待进一步诊治。\n住院医师：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "呼吸科副主任医师意见：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        (
            "临床药师意见：建议专家会诊，同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            False,
        ),
        # 正向保护：C04 与授权专家意见下出现“同意特殊级”
        (
            "感染科副主任医师意见：请临床药学会诊后同意加用万古霉素联合抗感染。",
            "请临床药学会诊后同意加用万古霉素联合抗感染",
            True,
        ),
        (
            "感染科副主任医师意见：请临床药学会诊后同意加用万古霉素联合抗感染。",
            "同意加用万古霉素联合抗感染",
            True,
        ),
        (
            "请会诊执行记录\n    感染科合成甲副主任医师会诊意见：同意特殊级抗菌药物美罗培南。",
            "同意特殊级抗菌药物美罗培南",
            True,
        ),
        (
            "感染专家会诊同意特殊级抗菌药物方案。",
            "同意特殊级抗菌药物方案",
            True,
        ),
        (
            "鉴于临床药学会诊意见,故请ICU合成甲主任医师行抗生素使用权限会诊,"
            "经会诊后指出:同意特殊级抗菌药物美罗培南加强抗感染治疗。",
            "同意特殊级抗菌药物美罗培南加强抗感染治疗",
            True,
        ),
    ],
)
def test_codex_r3_2_special_approval_governing_speaker_blocks_non_authorized_support_marker(
    text: str, quote: str, expected: bool
) -> None:
    assert ned._special_approval_by_authorized_expert(text, quote) is expected


@pytest.mark.asyncio
async def test_codex_r3_2_special_antimicrobial_end_to_end_rejects_pharmacist_agree_special_grade() -> None:
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
                "document_id": "cons-r3",
                "document_title": "请会诊执行记录",
                "record_time": "2026-07-05 10:00:00",
                "record_content": (
                    "感染科主任意见：待进一步诊治。\n"
                    "临床药师意见：同意特殊级抗菌药物美罗培南。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-07-10", "basis": "discharge_date"},),
    }
    client = _TargetedSpecialApprovalClient({"美罗培南": "同意特殊级抗菌药物美罗培南"})
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "non_compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "required_document_missing"


# =====================================================================
# 3. 跨午夜转科 10-02-01/02
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-10-02-01", "LX0609-10-02-02"])
async def test_codex_r3_3_single_overnight_transfer_is_compliant(rule_id: str) -> None:
    """Codex Round-3 精确反例：23:55 转科医嘱，次日 00:10 转出、00:20 转入且 transfer_date=次日。"""
    rows = {
        "inpat_registration": (
            {"admission_datetime": "2026-06-20 08:00:00", "discharge_datetime": "2026-07-05 10:00:00"},
        ),
        "inpat_nondrug_order": (
            {
                "order_id": "O-NIGHT",
                "order_name": "转入内四科",
                "order_status": "核实",
                "prescribed_datetime": "2026-06-27 23:55:00",
                "current_department": "ICU",
                "transferin_department": "内四科",
            },
        ),
        "transfer_out_record": (
            {
                "document_id": "U-NIGHT",
                "record_time": "2026-06-28 00:10:00",
                "transfer_date": "2026-06-28",
                "transferout_department": "ICU",
                "transferin_department": "内四科",
            },
        ),
        "transfer_in_record": (
            {
                "document_id": "I-NIGHT",
                "record_time": "2026-06-28 00:20:00",
                "transfer_date": "2026-06-28",
                "transferout_department": "ICU",
                "transferin_department": "内四科",
            },
        ),
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
    assert finals[rule_id]["status"] == "compliant"
    expected_reason = (
        "requirement_within_threshold" if rule_id == "LX0609-10-02-01" else "requirement_satisfied"
    )
    assert finals[rule_id]["reason_code"] == expected_reason


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-10-02-01", "LX0609-10-02-02"])
async def test_codex_r3_3_multi_event_overnight_transfer_is_compliant(rule_id: str) -> None:
    rows = {
        "inpat_registration": (
            {"admission_datetime": "2026-06-20 08:00:00", "discharge_datetime": "2026-07-05 10:00:00"},
        ),
        "inpat_nondrug_order": (
            {
                "order_id": "O1",
                "order_name": "转入ICU",
                "order_status": "核实",
                "prescribed_datetime": "2026-06-23 16:32:26",
            },
            {
                "order_id": "O2",
                "order_name": "转入内四科",
                "order_status": "核实",
                "prescribed_datetime": "2026-06-27 23:55:00",
            },
        ),
        "transfer_out_record": (
            {"document_id": "U1", "record_time": "2026-06-23 16:35:00", "transfer_date": "2026-06-23"},
            {"document_id": "U2", "record_time": "2026-06-28 00:10:00", "transfer_date": "2026-06-28"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-23 17:03:00", "transfer_date": "2026-06-23"},
            {"document_id": "I2", "record_time": "2026-06-28 00:20:00", "transfer_date": "2026-06-28"},
        ),
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
    assert finals[rule_id]["status"] == "compliant"
    assert len(finals[rule_id]["customer_display_facts"]["event_checks"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-10-02-01", "LX0609-10-02-02"])
@pytest.mark.parametrize(
    "record_time,transfer_date",
    [
        # 27日书写但显式声明次日 28日 transfer_date（Codex 前序反例必须继续拒绝）
        ("2026-06-27 09:30:00", "2026-06-28"),
        ("2026-06-27 10:01:00", "2026-06-28"),
        # 缺书写时间且声明次日 28日 transfer_date
        (None, "2026-06-28"),
        # 超出医嘱 + 24h 日期边界的未来事件 transfer_date=29日
        ("2026-06-29 00:10:00", "2026-06-29"),
    ],
)
async def test_codex_r3_3_future_transfer_date_counterexamples_stay_non_compliant(
    rule_id: str, record_time: str | None, transfer_date: str
) -> None:
    out_row: dict[str, object] = {"document_id": "U-BAD", "transfer_date": transfer_date}
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
