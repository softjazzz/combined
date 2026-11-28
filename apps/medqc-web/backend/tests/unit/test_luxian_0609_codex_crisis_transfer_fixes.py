"""Codex 审查回归测试：危急值(Issue #1)、转科(Issue #4)与特殊级抗菌药 P1-3（全合成无 PHI）。"""

from __future__ import annotations

import json
import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_document_evidence,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.extended_document import (
    antimicrobial_order_reason as abx_reason,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from tests.unit.test_luxian_0609_p0_extended_doc_fixes import _run_rules
from tests.unit.test_luxian_0609_s3_extended_doc_fixes import (
    _TargetedSpecialApprovalClient,
)


async def _run_with_session(rule_ids: tuple[str, ...], rows: dict[str, tuple[dict, ...]], llm_client=None):
    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key,
            rows=rows.get(key, ()),
            truncated=False,
            limit_rows=200,
        )

    horizon_rows = rows.get("evaluation_context.horizon", ())
    horizon_date = horizon_rows[0].get("horizon_date") if horizon_rows else "2026-08-10"
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id="syn-I",
        patient_id="syn-P",
        visit_id="syn-V",
        source_schema=None,
        created_at="2026-08-10T10:00:00+08:00",
        row_reader=read,
        evaluation_as_of_date=horizon_date,
        evaluation_horizon_policy="frozen_task_date",
        evaluation_horizon_snapshot={
            "institute_id": "syn-I",
            "patient_id": "syn-P",
            "visit_id": "syn-V",
            "record_scene": "running",
            "evaluation_basis": "task_frozen_date",
            "resolution_status": "resolved",
            "evaluation_horizon": horizon_date,
        },
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("extended_document",), selected_rule_ids=rule_ids,
        ),
    )
    execution = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        llm_client=llm_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rid} for rid in rule_ids],
        execution_results=execution.results,
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    return session, execution, reduced, {item["rule_id"]: item for item in canonical}


# =====================================================================
# Codex Issue #1a: 危急值未处理/待处理表述不得计作已处理
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "title,content",
    [
        ("危急值处理记录", "收到血钾危急值，尚未处理，等待医师"),
        ("日常病程记录", "收到血钾危急值2.50mmol/L，尚未处理，等待医师"),
        ("危急值处理记录", "接检验科血钾危急值2.50mmol/L，未处理，待医师处理。"),
        ("危急值记录", "收到血钾危急值2.50mmol/L，暂未处置，等待值班医生。"),
        ("危急值处理记录", "接血钾危急值2.50mmol/L，未予处理，未采取措施。"),
        ("危急值处理记录", "血钾2.50mmol/L危急值报告，暂无处理，待处置。"),
        ("危急值处理记录", "收到血钾危急值2.50mmol/L，尚未处理，已通知值班医师。"),
        ("", "今日08:05接检验科危急值报告：血钾 2.50mmol/L，查看患者，神志清，医师签名："),
    ],
)
async def test_codex_1a_unhandled_or_pending_crisis_note_is_rejected(title: str, content: str):
    rows = {
        "labtest_master": ({"test_id": "t-1", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "钾离子",
                "result": "2.50",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-unhandled",
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
    assert finals["LX0609-06-04-01"]["status"] == "non_compliant"
    assert finals["LX0609-06-04-01"]["reason_code"] == "threshold_exceeded"
    assert finals["LX0609-06-04-02"]["status"] == "non_compliant"
    assert finals["LX0609-06-04-02"]["reason_code"] == "required_document_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item_name,result_val,content",
    [
        ("钾离子", "2.50", "接血钾危急值2.50mmol/L，暂未复查，已予补钾处理。"),
        (
            "血小板计数",
            "21",
            "接检验科报告危急值：PLT 21×10^9/L，已预约血小板，但血库紧张暂无法输注，继续预约，动态复查血常规。",
        ),
        (
            "凝血酶原时间测定",
            "35.34",
            "接检验科报告危急值：PT 35.34S，患者家属已签字拒绝再次输血治疗，故密切观察出血表现。",
        ),
        (
            "二氧化碳分压",
            "71.00",
            "接危急值报告：pCO2 71.00mmHg，家属表示暂不转ICU，继续无创呼吸机辅助通气，调整呼吸机参数，动态复查。",
        ),
    ],
)
async def test_codex_1a_genuine_handling_with_partial_negation_remains_compliant(
    item_name: str, result_val: str, content: str
):
    rows = {
        "labtest_master": ({"test_id": "t-1", "labtest_subject": "检验"},),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": item_name,
                "result": result_val,
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-handled",
                "document_title": "危急值处理记录",
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


# =====================================================================
# Codex Issue #1b: 同项目多事件不得跨事件串配
# =====================================================================


@pytest.mark.asyncio
async def test_codex_1b_two_same_item_reports_note_only_for_first_does_not_cover_second():
    rows = {
        "labtest_master": (
            {"test_id": "t-1", "labtest_subject": "电解质"},
            {"test_id": "t-2", "labtest_subject": "电解质"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "钾离子",
                "result": "2.50",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
            {
                "document_id": "li-2",
                "test_id": "t-2",
                "item_name": "钾离子",
                "result": "2.30",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 10:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            # 写于两次报告之后、均在 6h 内，但明确仅记录第一次报告数值 2.50
            {
                "document_id": "dc-r1",
                "document_title": "危急值处理记录",
                "record_time": "2026-06-01 10:30:00",
                "record_content": "于08:00接检验科血钾危急值2.50mmol/L，已予氯化钾静脉补钾并动态复查电解质。",
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


@pytest.mark.asyncio
async def test_codex_1b_later_event_note_does_not_backfill_earlier_same_item_event():
    """复现 #09 真实结构：12:13 仅记录 12:06 pH 7.07 的危急值处理记录不得回填 07:00 pH 7.13。"""
    rows = {
        "labtest_master": (
            {"test_id": "t-1", "labtest_subject": "血气分析"},
            {"test_id": "t-2", "labtest_subject": "血气分析"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "pH",
                "result": "7.13",
                "abnormal_indicator": "PL",
                "report_time": "2026-07-29 07:00:30",
            },
            {
                "document_id": "li-2",
                "test_id": "t-2",
                "item_name": "pH",
                "result": "7.07",
                "abnormal_indicator": "PL",
                "report_time": "2026-07-29 12:06:26",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-r2",
                "document_title": "危急值处理记录",
                "record_time": "2026-07-29 12:13:00",
                "record_content": "于12:06床旁血气分析危急值报告：pH 7.07，予以碳酸氢钠纠酸，动态监测血气。",
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-07-31", "horizon_datetime": "2026-07-31 10:00:00", "basis": "discharge_date"},
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
        "2026-07-29 07:00:30": "unhandled",
        "2026-07-29 12:06:26": "handled",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "v2,note_content,expected_first,expected_second",
    [
        # 无数值危急值记录不得双计两份同项目报告
        ("2.30", "接血钾危急值，予以氯化钾补钾并复查电解质。", "unhandled", "handled"),
        # 同数值双报告 + 明确点出第一次报告时刻 08:00 -> 仅归属第一次报告
        ("2.50", "于08:00接血钾危急值2.50mmol/L，予以氯化钾补钾并复查电解质。", "handled", "unhandled"),
        # 同数值双报告 + 无时刻 -> 严禁一条病程双计两事件
        ("2.50", "接血钾危急值2.50mmol/L，予以氯化钾补钾并复查电解质。", "unhandled", "handled"),
    ],
)
async def test_codex_1b_single_note_never_double_credits_two_same_item_events(
    v2: str, note_content: str, expected_first: str, expected_second: str
):
    rows = {
        "labtest_master": (
            {"test_id": "t-1", "labtest_subject": "电解质"},
            {"test_id": "t-2", "labtest_subject": "电解质"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "钾离子",
                "result": "2.50",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
            {
                "document_id": "li-2",
                "test_id": "t-2",
                "item_name": "钾离子",
                "result": v2,
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 10:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-1",
                "document_title": "危急值处理记录",
                "record_time": "2026-06-01 10:30:00",
                "record_content": note_content,
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-02"]["status"] == "non_compliant"
    outcomes_by_time = {
        ev["report_time"]: ev["outcome"]
        for ev in finals["LX0609-06-04-02"]["customer_display_facts"]["event_results"]
    }
    assert outcomes_by_time == {
        "2026-06-01 08:00:00": expected_first,
        "2026-06-01 10:00:00": expected_second,
    }


@pytest.mark.asyncio
async def test_codex_1b_single_note_documenting_two_distinct_events_with_newline_split_matches_both():
    """复现 #04 2026-04-14 07:46 真实结构：同份危急值记录同时记载血气 pH/pCO2(含折行小数) 与血钾 2.60。"""
    rows = {
        "labtest_master": (
            {"test_id": "t-bg", "labtest_subject": "血气分析"},
            {"test_id": "t-k", "labtest_subject": "钾测定"},
        ),
        "labtest_item_report": (
            {
                "document_id": "li-bg1",
                "test_id": "t-bg",
                "item_name": "二氧化碳分压",
                "result": "18.00",
                "abnormal_indicator": "PL",
                "report_time": "2026-04-14 07:36:15",
            },
            {
                "document_id": "li-bg2",
                "test_id": "t-bg",
                "item_name": "pH",
                "result": "7.74",
                "abnormal_indicator": "PH",
                "report_time": "2026-04-14 07:36:15",
            },
            {
                "document_id": "li-k",
                "test_id": "t-k",
                "item_name": "钾离子",
                "result": "2.60",
                "abnormal_indicator": "PL",
                "report_time": "2026-04-14 07:43:22",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-both",
                "document_title": "危急值处理记录",
                "record_time": "2026-04-14 07:46:00",
                "record_content": (
                    "于07:43床旁血气分析危急值报告：pH 7.74,pCO2 18.\n00mmHg,"
                    "钾测定:K+ 2.60mmol/L。患者钾低，予以中心静脉补钾，动态监测电解质；"
                    "患者PH高，调整呼吸参数，动态监测血气分析。"
                ),
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-04-16", "horizon_datetime": "2026-04-16 10:00:00", "basis": "discharge_date"},
        ),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"


# =====================================================================
# Codex Issue #1c: 病程处置必须精确绑定到 fact_refs 与 customer_evidence
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "course_source,doc_id,title,content",
    [
        (
            "daily_course_record",
            "dc-matched",
            "危急值处理记录",
            "于08:05接血钾危急值2.50mmol/L，已予氯化钾补钾并复查电解质。",
        ),
        (
            "senior_course_record",
            "sc-matched",
            "主任医师查房记录",
            "查房示血钾2.50mmol/L偏低，予以氯化钾静脉补钾，动态复查电解质。",
        ),
    ],
)
async def test_codex_1c_matched_course_doc_is_bound_to_fact_refs_and_customer_evidence(
    course_source: str, doc_id: str, title: str, content: str
):
    rows = {
        "labtest_master": ({"test_id": "t-1", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {
                "document_id": "li-1",
                "test_id": "t-1",
                "item_name": "钾离子",
                "result": "2.50",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 08:00:00",
            },
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-unrelated",
                "document_title": "日常病程记录",
                "record_time": "2026-06-01 09:00:00",
                "record_content": "患者一般情况可，无特殊不适，继续观察。",
            },
            *(
                ({
                    "document_id": doc_id,
                    "document_title": title,
                    "record_time": "2026-06-01 08:15:00",
                    "record_content": content,
                },)
                if course_source == "daily_course_record"
                else ()
            ),
        ),
        "senior_course_record": (
            *(
                ({
                    "document_id": doc_id,
                    "document_title": title,
                    "record_time": "2026-06-01 08:15:00",
                    "record_content": content,
                },)
                if course_source == "senior_course_record"
                else ()
            ),
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    session, execution, reduced, by_rule = await _run_with_session(
        ("LX0609-06-04-01", "LX0609-06-04-02"), rows
    )
    matched_ref = next(
        ref
        for ref, row in session.materials.document_rows(course_source, snapshot=session.snapshot)
        if row.get("document_id") == doc_id
    )
    unrelated_ref = next(
        ref
        for ref, row in session.materials.document_rows("daily_course_record", snapshot=session.snapshot)
        if row.get("document_id") == "dc-unrelated"
    )
    for decision in reduced:
        result = by_rule[decision.rule_id]
        assert result["status"] == "compliant"
        assert matched_ref in decision.fact_refs
        assert unrelated_ref not in decision.fact_refs
        evidence_pairs = {
            (ev["source_type"], ev["source_document_id"])
            for ev in result.get("customer_evidence", [])
        }
        assert (course_source, doc_id) in evidence_pairs
        assert ("labtest_item_report", "li-1") in evidence_pairs
        assert ("daily_course_record", "dc-unrelated") not in evidence_pairs
        # 公开边界校验保持 100% 一致
        assert result["customer_display_facts"] == validate_luxian_0609_published_customer_display_facts(
            rule_id=decision.rule_id, raw=result["customer_display_facts"]
        )
        projected_pairs = {
            (ev["source_type"], ev["source_document_id"])
            for ev in project_selected_document_evidence(
                decision=decision,
                evidence_snapshot=session.snapshot,
                evidence_materials=session.materials,
            )
        }
        assert evidence_pairs == projected_pairs


@pytest.mark.asyncio
async def test_codex_1c_over_128_refs_fallback_includes_matched_course_source_key():
    """超过 128 条逐行引用降级为来源快照引用时，必须包含命中的 daily_course_record 来源。"""
    item_rows = tuple(
        {
            "document_id": f"li-{i}",
            "test_id": "t-bulk",
            "item_name": "钾离子",
            "result": "2.50",
            "abnormal_indicator": "PL",
            "report_time": "2026-06-01 08:00:00",
        }
        for i in range(130)
    )
    rows = {
        "labtest_master": ({"test_id": "t-bulk", "labtest_subject": "电解质"},),
        "labtest_item_report": item_rows,
        "crisis_value_record": (),
        "daily_course_record": (
            {
                "document_id": "dc-bulk",
                "document_title": "危急值处理记录",
                "record_time": "2026-06-01 08:15:00",
                "record_content": "接血钾危急值2.50mmol/L，已予氯化钾补钾并复查。",
            },
        ),
        "senior_course_record": (
            {
                "document_id": "sc-unused",
                "document_title": "查房记录",
                "record_time": "2026-06-01 09:00:00",
                "record_content": "查房一般情况可。",
            },
        ),
        "evaluation_context.horizon": (
            {"horizon_date": "2026-06-03", "horizon_datetime": "2026-06-03 10:00:00", "basis": "discharge_date"},
        ),
    }
    session, _execution, reduced, _by_rule = await _run_with_session(
        ("LX0609-06-04-02",), rows
    )
    assert reduced[0].final_state.value == "compliant"
    obs_by_source = {obs.source_key: obs.snapshot_ref.removeprefix("sha256:") for obs in session.snapshot.observations}
    fact_refs = set(reduced[0].fact_refs)
    assert obs_by_source["daily_course_record"] in fact_refs
    assert obs_by_source["labtest_item_report"] in fact_refs
    assert obs_by_source["senior_course_record"] not in fact_refs


# =====================================================================
# Codex Issue #4: LX0609-10-02-02 次日 transfer_date 不得回挂当日医嘱
# =====================================================================


@pytest.mark.asyncio
async def test_codex_4_multi_transfer_next_day_transfer_date_does_not_back_match_today_order():
    """Codex 精确反例：当日 09:30 书写但 transfer_date=次日，绝不得挂靠当日 10:00 医嘱。"""
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
            # 09:30 写于 O2 (10:00) 前 30 分钟内，但显式标明 transfer_date 为次日 2026-06-28
            {"document_id": "U2-NEXT-DAY", "record_time": "2026-06-27 09:30:00", "transfer_date": "2026-06-28"},
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "non_compliant"
    assert finals["LX0609-10-02-02"]["reason_code"] == "required_document_missing"


@pytest.mark.asyncio
async def test_codex_4_single_transfer_next_day_transfer_date_does_not_back_match_today_order():
    rows = {
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 10:00:00"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-27 10:28:16"},
        ),
        "transfer_out_record": (
            {"document_id": "U1-NEXT-DAY", "record_time": "2026-06-27 09:30:00", "transfer_date": "2026-06-28"},
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "non_compliant"
    assert finals["LX0609-10-02-02"]["reason_code"] == "required_document_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("transfer_date", [None, "2026-06-27"])
async def test_codex_4_same_day_81s_early_unlabelled_transfer_out_still_matches(transfer_date):
    out_row = {"document_id": "U2", "record_time": "2026-06-27 09:51:00"}
    if transfer_date is not None:
        out_row["transfer_date"] = transfer_date
    rows = {
        "inpat_nondrug_order": (
            {"order_id": "O1", "order_name": "转入ICU", "order_status": "核实", "prescribed_datetime": "2026-06-23 16:32:26"},
            {"order_id": "O2", "order_name": "转入内四科", "order_status": "核实", "prescribed_datetime": "2026-06-27 09:52:21"},
        ),
        "transfer_in_record": (
            {"document_id": "I1", "record_time": "2026-06-23 17:03:00"},
            {"document_id": "I2", "record_time": "2026-06-27 10:28:16"},
        ),
        "transfer_out_record": (
            {"document_id": "U1", "record_time": "2026-06-23 16:33:00"},
            out_row,
        ),
    }
    _, finals = await _run_rules(("LX0609-10-02-02",), rows)
    assert finals["LX0609-10-02-02"]["status"] == "compliant"


# =====================================================================
# P1-3: #05 & #09 LX0609-05-01-06 专家签名起头引文与提示词对齐
# =====================================================================


@pytest.mark.asyncio
async def test_p1_3_case_09_quote_starting_with_deputy_chief_signature_is_compliant():
    """复现 #09 真实模型输出：引文以“合成甲副主任医师会诊意见:”起头时须通过授权专家校验。"""
    full_quote = (
        "合成甲副主任医师会诊意见:患者重症肺炎,哌拉西林他唑巴坦抗感染疗效差,同意升级抗生素为美罗培南。"
    )
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "(JC)注射用美罗培南(0.25g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2026-07-05 21:54:13+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": "cons-m",
                "document_title": None,
                "record_time": "2026-07-05 20:14:04",
                "record_content": (
                    "本病人建议使用【(JC)注射用美罗培南(0.25g)】,使用目的为:治疗-内科-经验,"
                    "指征:急性细菌性下呼吸道感染。" + full_quote + "遵嘱执行。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-07-20", "basis": "discharge_date"},),
    }
    client = _TargetedSpecialApprovalClient({"美罗培南": full_quote})
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "requirement_satisfied"


@pytest.mark.asyncio
async def test_p1_3_case_05_invited_consult_header_quote_and_prompt_alignment():
    """复现 #05 真实结构：《请会诊执行记录》受邀重症医学科/感染科医师意见含落款引文与提示词覆盖。"""
    icu_quote = "故邀请重症医学科合成乙医生协助诊治：患者合并重症肺部感染，同意使用美罗培南加强抗感染。"
    id_quote = "故邀请感染科合成丙医生协助诊治：考虑肺真菌感染。建议给予伏立康唑抗感染。"
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "(4+7)注射用美罗培南(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2025-12-16 10:43:49+08:00",
            },
            {
                "document_id": "ord-v",
                "order_id": "O-V",
                "generic_name": "(JC)伏立康唑片(50mg)",
                "drug_apply_method": "口服",
                "order_status": "新开",
                "planned_start_datetime": "2025-12-22 11:47:07+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": "cons-icu",
                "document_title": "请会诊执行记录",
                "record_time": "2025-12-16 10:20:00",
                "record_content": (
                    "2025-12-16 10:20 请会诊执行记录\n"
                    "临床药学会诊后建议给予美罗培南抗感染，" + icu_quote + "尊会诊意见执行。"
                ),
            },
            {
                "document_id": "cons-id",
                "document_title": "请会诊执行记录",
                "record_time": "2025-12-21 17:10:00",
                "record_content": "2025-12-21 17:10 请会诊执行记录\n" + id_quote + "尊会诊意见执行。",
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-01-05", "basis": "discharge_date"},),
    }

    seen_prompts: list[str] = []

    class _PromptCapturingClient(_TargetedSpecialApprovalClient):
        async def generate(self, prompt: str, **kwargs):
            seen_prompts.append(prompt)
            return await super().generate(prompt, **kwargs)

    client = _PromptCapturingClient({"美罗培南": icu_quote, "伏立康唑": id_quote})
    _, finals = await _run_rules(("LX0609-05-01-06",), rows, llm_client=client)
    assert finals["LX0609-05-01-06"]["status"] == "compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "requirement_satisfied"
    assert seen_prompts
    assert "请会诊执行记录" in seen_prompts[0]
    assert "重症医学科" in seen_prompts[0]
    assert "临床药师" in seen_prompts[0]


@pytest.mark.parametrize(
    "text,quote,expected",
    [
        # #09 真实引文形状：以副主任医师署名起头
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            True,
        ),
        # 负向守卫：夹带申请单前缀“使用目的为…”不得放行
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            "使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意升级抗生素为美罗培南。",
            False,
        ),
        # 负向守卫：引用受邀ICU会诊落款之前的临床药学建议不得放行
        (
            "请会诊执行记录\n临床药学会诊后建议给予美罗培南抗感染，故邀请重症医学科合成乙医生协助诊治：暂观察。",
            "临床药学会诊后建议给予美罗培南抗感染",
            False,
        ),
        # 负向守卫：C05 跨段借用署名（申请单/药师意见）仍严格拒绝
        (
            "本病人建议使用【注射用美罗培南】,使用目的为:治疗-内科-经验。合成甲副主任医师会诊意见:同意。临床药学合成丙主管药师:建议换用万古霉素。",
            "建议换用万古霉素",
            False,
        ),
    ],
)
def test_p1_3_special_approval_signature_overlap_and_c05_guards(text: str, quote: str, expected: bool):
    assert ned._special_approval_by_authorized_expert(text, quote) is expected
