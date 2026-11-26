"""P0-1, P0-3, P0-5, P1-6 扩展文书族确定性修复回归测试（全合成无 PHI）。"""

from __future__ import annotations

import json
import pytest

from app.services.luxian_0609 import native_extended_document_execution as ned
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    QueryStatus,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION,
    resolve_luxian_0609_physical_source_entry,
)
from special_antimicrobial_test_support import FrozenSpecialApprovalClient


def _build_session(
    rows_by_source: dict[str, tuple[dict, ...]],
    *,
    created_at: str = "2026-10-26T10:00:00+08:00",
    material_scopes: dict[str, dict] | None = None,
):
    source_keys = (
        "inpat_registration",
        "admission_record",
        "death_record",
        "death_discussion",
        "discharge_record",
        "daily_course_record",
        "senior_course_record",
        "consultation_record",
        "crisis_value_record",
        "labtest_master",
        "labtest_item_report",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "inpat_prescription",
        "inpat_prescription_item",
        "surgery_record",
        "pathology_exam_report",
        "bloodtrans_record",
        "rescue_record",
        "transfer_out_record",
        "transfer_in_record",
        "discharge_record_diagnosis",
        "evaluation_context.horizon",
    )
    observations = []
    sources = {}
    all_refs = []
    for source_key in source_keys:
        rows = tuple(rows_by_source.get(source_key, ()))
        scope = (material_scopes or {}).get(source_key)
        query_version = resolve_luxian_0609_physical_source_entry(source_key).query_version
        document_refs = build_material_document_refs(source_key, rows)
        all_refs.extend(document_refs)
        query_state = QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
        completeness = SourceCompleteness.COMPLETE
        sources[source_key] = SnapshotSourceRows(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=max(100, len(rows) + 10),
            material_scope=scope,
        )
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=len(rows),
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=document_refs,
                    material_scope=scope,
                ),
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        institute_id="SYNTH-INST",
        patient_id="SYNTH-PAT",
        visit_id="SYNTH-VIS",
        observations=tuple(observations),
        facts=(),
        document_refs=tuple(dict.fromkeys(all_refs)),
        created_at=created_at,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )
    return snapshot, materials


async def _run_rules(
    rule_ids: tuple[str, ...],
    rows_by_source: dict[str, tuple[dict, ...]],
    *,
    llm_client=None,
    created_at: str = "2026-10-26T10:00:00+08:00",
    material_scopes: dict[str, dict] | None = None,
):
    """通过正式 Evidence Session + 执行 + Binding + Finalizer 链路执行并返回每条规则结果。"""

    snapshot, materials = _build_session(
        rows_by_source,
        created_at=created_at,
        material_scopes=material_scopes,
    )
    execution = await ned.execute_luxian_0609_native_extended_document_rules(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=llm_client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=snapshot,
        evidence_materials=materials,
    )
    facts_map = dict(execution.customer_display_facts)
    finals = {
        decision.rule_id: finalize_luxian_0609_reduced_customer_result(
            decision=decision,
            raw_customer_display_facts=facts_map.get(decision.rule_id),
            evidence_snapshot=snapshot,
            evidence_materials=materials,
        )
        for decision in reduced
    }
    return execution, finals


# =====================================================================
# P0-1: LX0609-06-04-01 & LX0609-06-04-02 危急值病程处置合并取材
# =====================================================================


@pytest.mark.asyncio
async def test_p0_1_crisis_handling_in_daily_course_satisfies_both_rules_when_crisis_table_empty():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-04-01 08:00:00", "discharge_datetime": "2026-05-05 10:00:00"},),
        "labtest_master": (
            {"test_id": "t-k", "labtest_subject": "电解质"},
            {"test_id": "t-bg", "labtest_subject": "血气分析"},
            {"test_id": "t-plt", "labtest_subject": "血常规"},
            {"test_id": "t-aptt", "labtest_subject": "凝血功能"},
        ),
        "labtest_item_report": (
            {"document_id": "li-1", "test_id": "t-k", "item_name": "*钾测定", "result_value": "2.50",
             "abnormal_indicator": "PL", "report_datetime": "2026-04-07 07:51:14"},
            {"document_id": "li-2", "test_id": "t-bg", "item_name": "二氧化碳分压", "result_value": "18.00",
             "abnormal_indicator": "PL", "report_datetime": "2026-04-14 07:36:15"},
            {"document_id": "li-3", "test_id": "t-bg", "item_name": "pH", "result_value": "7.74",
             "abnormal_indicator": "PH", "report_datetime": "2026-04-14 07:36:15"},
            {"document_id": "li-4", "test_id": "t-plt", "item_name": "*血小板计数", "result_value": "17",
             "abnormal_indicator": "PL", "report_datetime": "2026-04-15 08:50:31"},
            {"document_id": "li-5", "test_id": "t-aptt", "item_name": "*活化部分凝血活酶时间测定", "result_value": ">180.00",
             "abnormal_indicator": "PH", "report_datetime": "2026-04-16 09:58:53"},
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {"document_id": "dc-1", "document_title": "危急值处理记录", "record_time": "2026-04-07 07:56:00",
             "record_content": "接检验科危急值报告：血钾 2.50mmol/L，予氯化钾静脉补钾并复查。"},
            {"document_id": "dc-2", "document_title": "危急值处理记录", "record_time": "2026-04-14 07:46:00",
             "record_content": "血气危急值：pH 7.74，pCO2 18.00mmHg，调整呼吸机参数后复查。"},
            # 血培养危急值记录不在 labtest_item_report PL/PH 中，不能引发 association_failed
            {"document_id": "dc-bc", "document_title": "危急值记录", "record_time": "2026-04-14 09:52:00",
             "record_content": "检验科报危急值：血培养双瓶报阳，已加用抗真菌治疗。"},
            {"document_id": "dc-3", "document_title": "危急值记录", "record_time": "2026-04-15 09:00:00",
             "record_content": "危急值：血小板 17×10^9/L，予输注血小板并复查血常规。"},
            {"document_id": "dc-4", "document_title": "危急值记录", "record_time": "2026-04-16 10:10:00",
             "record_content": "危急值：APTT >180.00s，予输注血浆改善凝血功能并复查。"},
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-05-05", "horizon_datetime": "2026-05-05 10:00:00", "basis": "discharge_date"},),
    }
    execution, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert execution.llm_call_count == 0
    assert finals["LX0609-06-04-01"]["status"] == "compliant"
    assert finals["LX0609-06-04-01"]["reason_code"] == "requirement_within_threshold"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["reason_code"] == "requirement_satisfied"
    assert all(
        ev["outcome"] == "timely"
        for ev in finals["LX0609-06-04-01"]["customer_display_facts"]["event_results"]
    )


@pytest.mark.asyncio
async def test_p0_1_general_daily_and_senior_course_handling_with_exact_value_and_action_matches():
    rows = {
        "labtest_master": (
            {"test_id": "t-ph", "labtest_subject": "血气分析"},
            {"test_id": "t-plt", "labtest_subject": "血常规"},
        ),
        "labtest_item_report": (
            {"document_id": "li-ph", "test_id": "t-ph", "item_name": "pH", "result_value": "7.18",
             "abnormal_indicator": "PL", "report_datetime": "2026-05-01 17:27:34"},
            {"document_id": "li-plt", "test_id": "t-plt", "item_name": "*血小板计数", "result_value": "9",
             "abnormal_indicator": "PL", "report_datetime": "2026-05-02 09:00:22"},
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {"document_id": "dc-ph", "document_title": "日常病程记录", "record_time": "2026-05-01 17:36:50",
             "record_content": "复查血气示 pH 7.18，严重代谢性酸中毒，立即予碳酸氢钠纠酸处理并调整呼吸机参数。"},
        ),
        "senior_course_record": (
            {"document_id": "sc-plt", "document_title": "主任医师查房记录", "record_time": "2026-05-02 10:12:00",
             "record_content": "今日血常规提示血小板计数 9×10^9/L，出血风险极高，予积极输注血小板并复查。"},
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-05-05", "horizon_datetime": "2026-05-05 10:00:00", "basis": "discharge_date"},),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"


@pytest.mark.asyncio
async def test_p0_1_unrelated_routine_course_does_not_mask_genuine_missing_handling():
    rows = {
        "labtest_master": ({"test_id": "t-k", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {"document_id": "li-k", "test_id": "t-k", "item_name": "*钾测定", "result_value": "2.40",
             "abnormal_indicator": "PL", "report_datetime": "2026-05-01 08:00:00"},
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {"document_id": "dc-1", "document_title": "日常病程记录", "record_time": "2026-05-01 09:30:00",
             "record_content": "患者夜间睡眠尚可，生命体征平稳，继续目前对症支持治疗。"},
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-05-02", "horizon_datetime": "2026-05-02 10:00:00", "basis": "evaluation_as_of"},),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "non_compliant"
    assert finals["LX0609-06-04-02"]["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_p0_1_overdue_course_crisis_note_fails_6h_timeliness_but_satisfies_presence():
    rows = {
        "labtest_master": ({"test_id": "t-k", "labtest_subject": "电解质"},),
        "labtest_item_report": (
            {"document_id": "li-k", "test_id": "t-k", "item_name": "*钾测定", "result_value": "2.40",
             "abnormal_indicator": "PL", "report_datetime": "2026-05-01 08:00:00"},
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            {"document_id": "dc-late", "document_title": "危急值处理记录", "record_time": "2026-05-01 16:00:00",
             "record_content": "危急值处理：血钾 2.40mmol/L，予氯化钾补钾并复查。"},
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-05-02", "horizon_datetime": "2026-05-02 10:00:00", "basis": "evaluation_as_of"},),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    assert finals["LX0609-06-04-01"]["status"] == "non_compliant"
    assert finals["LX0609-06-04-01"]["reason_code"] == "threshold_exceeded"
    assert finals["LX0609-06-04-02"]["status"] == "compliant"
    assert finals["LX0609-06-04-02"]["reason_code"] == "requirement_satisfied"


@pytest.mark.asyncio
async def test_p0_1_later_event_crisis_note_does_not_cross_match_earlier_unhandled_event():
    rows = {
        "labtest_master": (
            {"test_id": "t-po2", "labtest_subject": "血气分析"},
            {"test_id": "t-k", "labtest_subject": "血气分析"},
        ),
        "labtest_item_report": (
            {"document_id": "li-po2", "test_id": "t-po2", "item_name": "氧分压", "result_value": "30.00",
             "abnormal_indicator": "PL", "report_datetime": "2026-07-03 07:27:39"},
            {"document_id": "li-k", "test_id": "t-k", "item_name": "钾离子", "result_value": "2.70",
             "abnormal_indicator": "PL", "report_datetime": "2026-07-03 18:58:53"},
        ),
        "crisis_value_record": (),
        "daily_course_record": (
            # 晚间血气钾危急值记录虽顺带抄录了正常 pO2 108mmHg，不应误归为上午氧分压30的12h超时处置
            {"document_id": "dc-k", "document_title": "危急值处理记录", "record_time": "2026-07-03 19:43:00",
             "record_content": "危急值：血气示钾离子 2.70mmol/L，pO2 108mmHg，予补钾处理并复查。"},
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-07-05", "horizon_datetime": "2026-07-05 10:00:00", "basis": "discharge_date"},),
    }
    _, finals = await _run_rules(("LX0609-06-04-01", "LX0609-06-04-02"), rows)
    events_01 = {
        ev["report_time"]: ev["outcome"]
        for ev in finals["LX0609-06-04-01"]["customer_display_facts"]["event_results"]
    }
    assert events_01["2026-07-03 18:58:53"] == "timely"
    assert events_01["2026-07-03 07:27:39"] == "unhandled"
    assert finals["LX0609-06-04-02"]["status"] == "non_compliant"


# =====================================================================
# P0-3: 空壳出院记录、全空/PDF无时间死亡记录行、死亡准入对齐
# =====================================================================


@pytest.mark.asyncio
async def test_p0_3_death_case_with_empty_discharge_shell_is_not_applicable_on_08_01_05_and_08_01_02():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-03-27 18:07:00"},),
        "death_record": ({
            "document_id": "death-1",
            "document_title": "死亡记录",
            "death_datetime": "2026-05-04 09:53:00+08:00",
            "record_time": "2026-05-04 16:31:34",
            "record_content": "患者临床死亡，抢救经过完整记录。",
            "treatment_course": "抢救诊疗经过完整。",
            "document_status": "Save",
        },),
        "discharge_record": ({
            "document_id": "shell-1",
            "document_title": None,
            "record_content": None,
            "treatment_course": None,
            "discharge_order": "随访方式:随访周期:随访日期:。",
            "discharge_time": "2026-05-04 09:53:00",
        },),
        "rescue_record": ({
            "document_id": "res-1",
            "record_time": "2026-05-04 09:20:00",
            "record_content": "心肺复苏抢救记录。",
        },),
    }
    execution, finals = await _run_rules(("LX0609-08-01-05", "LX0609-08-01-02"), rows)
    assert execution.llm_call_count == 0
    assert finals["LX0609-08-01-05"]["status"] == "not_applicable"
    assert finals["LX0609-08-01-05"]["reason_code"] == "eligibility_not_met"
    assert finals["LX0609-08-01-02"]["status"] == "not_applicable"
    assert finals["LX0609-08-01-02"]["reason_code"] == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_p0_3_alive_empty_body_discharge_shell_downgrades_to_data_gap_on_08_01_02_and_08_01_05():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-10-02 09:00:00", "discharge_datetime": "2026-10-11 08:27:00"},),
        "death_record": (),
        "discharge_record": ({
            "document_id": "dis-18",
            "document_title": None,
            "record_content": None,
            "treatment_course": None,
            "discharge_order": "1.注意休息,软食;2.定期复查血常规。随访方式:门诊随访周期:每1个月随访日期:2026年10月11日。",
            "record_time": "2026-10-11 22:37:00",
            "discharge_time": "2026-10-11 08:27:00",
        },),
        "inpat_prescription": ({
            "prescription_id": "rx-1",
            "order_type": "出院带药",
            "order_status": "完成",
        },),
        "inpat_prescription_item": ({
            "prescription_id": "rx-1",
            "prescription_item_id": "item-1",
            "generic_name": "合成颗粒(4g*12袋)",
            "drug_apply_method": "口服",
        },),
    }
    execution, finals = await _run_rules(("LX0609-08-01-02", "LX0609-08-01-05"), rows)
    assert execution.llm_call_count == 0
    assert finals["LX0609-08-01-02"]["status"] == "data_gap"
    assert finals["LX0609-08-01-02"]["reason_code"] == "required_field_missing"
    assert finals["LX0609-08-01-05"]["status"] == "data_gap"
    assert finals["LX0609-08-01-05"]["reason_code"] == "source_readiness_unproven"


@pytest.mark.asyncio
async def test_p0_3_alive_full_body_discharge_still_detects_missing_prescription_drug():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-10-02 09:00:00", "discharge_datetime": "2026-10-11 08:27:00"},),
        "death_record": (),
        "discharge_record": ({
            "document_id": "dis-full",
            "document_title": "出院记录",
            "record_content": "完整出院记录正文：诊疗经过平稳，病情好转出院。",
            "discharge_order": "1.注意休息，清淡饮食，门诊随访。",
            "record_time": "2026-10-11 10:00:00",
            "discharge_time": "2026-10-11 08:27:00",
        },),
        "inpat_prescription": ({
            "prescription_id": "rx-1",
            "order_type": "出院带药",
            "order_status": "完成",
        },),
        "inpat_prescription_item": ({
            "prescription_id": "rx-1",
            "prescription_item_id": "item-1",
            "generic_name": "合成颗粒",
            "drug_apply_method": "口服",
        },),
    }
    _, finals = await _run_rules(("LX0609-08-01-02",), rows)
    assert finals["LX0609-08-01-02"]["status"] == "non_compliant"
    assert finals["LX0609-08-01-02"]["customer_display_facts"]["missing_drug_names"] == ["合成颗粒"]


@pytest.mark.asyncio
async def test_p0_3_ghost_all_null_death_row_and_bare_pdf_duplicate_do_not_block_04_02_09():
    rows = {
        "inpat_registration": ({"admission_datetime": "2025-10-05 08:00:00"},),
        "death_record": (
            {
                "document_id": "death-emr",
                "document_title": "死亡记录",
                "document_status": "Save",
                "death_datetime": "2026-01-29 09:26:00+08:00",
                "record_time": "2026-01-29 09:51:26",
                "submit_datetime": "2026-01-29 09:51:26",
                "record_content": "结构化死亡记录正文。",
                "treatment_course": "住院诊疗与抢救经过。",
            },
            # 全空幽灵行
            {
                "document_id": "death-ghost",
                "document_title": None,
                "record_content": None,
                "treatment_course": None,
                "death_datetime": None,
                "record_time": None,
            },
            # 无时间/无状态 PDF 补录重复行（visit_type='I'，正文死亡时刻一致）
            {
                "document_id": "death-pdf-dup",
                "visit_type": "I",
                "document_title": "死亡记录",
                "document_status": None,
                "death_datetime": None,
                "death_time": None,
                "record_time": None,
                "submit_datetime": None,
                "last_modified_datetime": None,
                "update_time": None,
                "treatment_course": None,
                "record_content": "死亡时间：2026年01月29日 09:26。PDF 补录完整死亡记录文本。",
            },
        ),
        "discharge_record": (),
    }
    _, finals = await _run_rules(("LX0609-04-02-06", "LX0609-04-02-08", "LX0609-04-02-09"), rows)
    assert finals["LX0609-04-02-06"]["status"] == "compliant"
    assert finals["LX0609-04-02-08"]["status"] == "compliant"
    assert finals["LX0609-04-02-09"]["status"] == "compliant"
    assert finals["LX0609-04-02-09"]["customer_display_facts"]["elapsed_seconds"] == 1526.0


@pytest.mark.asyncio
async def test_p0_3_untimed_death_duplicate_with_conflicting_body_death_time_still_blocks():
    rows = {
        "inpat_registration": ({"admission_datetime": "2025-10-05 08:00:00"},),
        "death_record": (
            {
                "document_id": "death-emr",
                "document_title": "死亡记录",
                "document_status": "Save",
                "death_datetime": "2026-01-29 09:26:00+08:00",
                "record_time": "2026-01-29 09:51:26",
                "record_content": "结构化死亡记录正文。",
                "treatment_course": "诊疗经过。",
            },
            {
                "document_id": "death-pdf-conflict",
                "document_title": "死亡记录",
                "record_content": "死亡时间：2026年01月29日 11:30。与权威死亡时刻冲突。",
            },
        ),
    }
    _, finals = await _run_rules(("LX0609-04-02-09",), rows)
    assert finals["LX0609-04-02-09"]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_p0_3_alive_discharge_without_document_title_is_not_applicable_on_04_02_09():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-10-02 09:00:00"},),
        "death_record": (),
        "discharge_record": ({
            "document_id": "dis-untitled",
            "document_title": None,
            "record_content": None,
            "treatment_course": "入院后完善相关检查:",
            "discharge_order": "注意休息，门诊随访。",
            "record_time": "2026-10-11 22:37:00",
            "discharge_time": "2026-10-11 08:27:00",
        },),
    }
    _, finals = await _run_rules(("LX0609-04-02-06", "LX0609-04-02-08", "LX0609-04-02-09"), rows)
    assert finals["LX0609-04-02-06"]["status"] == "not_applicable"
    assert finals["LX0609-04-02-08"]["status"] == "not_applicable"
    assert finals["LX0609-04-02-09"]["status"] == "not_applicable"
    assert finals["LX0609-04-02-09"]["reason_code"] == "trigger_absent_complete"


# =====================================================================
# P0-5: LX0609-09-02-01 死亡讨论 7 天时限终末评价时点修复
# =====================================================================


@pytest.mark.asyncio
async def test_p0_5_final_qc_discharge_horizon_pinned_to_death_matures_using_snapshot_created_at():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-01-01 08:00:00", "last_modified_datetime": "2026-03-22 11:00:09"},),
        "death_record": ({
            "document_id": "death-1",
            "document_title": "死亡记录",
            "death_datetime": "2026-01-29 09:26:00+08:00",
            "record_time": "2026-01-29 09:51:26",
            "record_content": "死亡记录正文。",
        },),
        "death_discussion": (),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-01-29",
            "horizon_datetime": "2026-01-29T09:26:00",
            "basis": "discharge_date",
        },),
    }
    _, finals = await _run_rules(
        ("LX0609-09-02-01",), rows, created_at="2026-10-26T10:00:00+08:00",
    )
    assert finals["LX0609-09-02-01"]["status"] == "non_compliant"
    assert finals["LX0609-09-02-01"]["reason_code"] == "required_document_missing"
    assert finals["LX0609-09-02-01"]["customer_display_facts"]["failure_kind"] == "death_discussion_missing_after_deadline"


@pytest.mark.asyncio
async def test_p0_5_final_qc_within_7_days_of_death_waits_with_actual_remaining_time():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-10-01 08:00:00"},),
        "death_record": ({
            "document_id": "death-recent",
            "document_title": "死亡记录",
            "death_datetime": "2026-10-23 10:00:00+08:00",
            "record_time": "2026-10-23 11:00:00",
            "record_content": "死亡记录正文。",
        },),
        "death_discussion": (),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-10-23",
            "horizon_datetime": "2026-10-23T10:00:00",
            "basis": "discharge_date",
        },),
    }
    _, finals = await _run_rules(
        ("LX0609-09-02-01",), rows, created_at="2026-10-26T10:00:00+08:00",
    )
    assert finals["LX0609-09-02-01"]["status"] == "data_gap"
    assert finals["LX0609-09-02-01"]["reason_code"] == "evaluation_window_not_mature"
    # 已过3天（72h），尚余4天（96h = 345600s），不再恒为 168h
    assert finals["LX0609-09-02-01"]["customer_display_facts"]["remaining_seconds"] == 4 * 86400


@pytest.mark.asyncio
async def test_p0_5_final_qc_respects_empty_unconfirmed_death_discussion_table_scope():
    rows = {
        "inpat_registration": ({"admission_datetime": "2026-01-01 08:00:00"},),
        "death_record": ({
            "document_id": "death-1",
            "document_title": "死亡记录",
            "death_datetime": "2026-01-29 09:26:00+08:00",
            "record_time": "2026-01-29 09:51:26",
            "record_content": "死亡记录正文。",
        },),
        "death_discussion": (),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-01-29",
            "horizon_datetime": "2026-01-29T09:26:00",
            "basis": "discharge_date",
        },),
    }
    _, finals = await _run_rules(
        ("LX0609-09-02-01",),
        rows,
        created_at="2026-10-26T10:00:00+08:00",
        material_scopes={
            "death_discussion": {
                "status": "empty_unconfirmed",
                "can_judge_clinical_absence": False,
            },
        },
    )
    assert finals["LX0609-09-02-01"]["status"] == "data_gap"
    assert finals["LX0609-09-02-01"]["reason_code"] == "source_unavailable"


@pytest.mark.asyncio
async def test_p0_5_in_progress_evaluation_as_of_cutoff_preserved():
    rows = {
        "death_record": ({
            "document_id": "death-prog",
            "death_datetime": "2026-07-30 12:00:00",
            "record_content": "死亡记录正文。",
        },),
        "death_discussion": (),
        "evaluation_context.horizon": ({
            "horizon_date": "2026-08-04",
            "horizon_datetime": "2026-08-04T12:00:00",
            "basis": "evaluation_as_of",
        },),
    }
    _, finals = await _run_rules(
        ("LX0609-09-02-01",), rows, created_at="2026-10-26T10:00:00+08:00",
    )
    assert finals["LX0609-09-02-01"]["status"] == "data_gap"
    assert finals["LX0609-09-02-01"]["reason_code"] == "evaluation_window_not_mature"
    assert finals["LX0609-09-02-01"]["customer_display_facts"]["remaining_seconds"] == 2 * 86400


# =====================================================================
# P1-6: LX0609-05-01-06 特殊级抗菌药专家会诊识别
# =====================================================================


@pytest.mark.asyncio
async def test_p1_6_infectious_disease_econsult_without_printed_title_recognized():
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-m",
                "order_id": "O-M",
                "generic_name": "(4+7)注射用美罗培南(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2026-04-07 10:05:00+08:00",
            },
            {
                "document_id": "ord-v",
                "order_id": "O-V",
                "generic_name": "(JC)注射用盐酸万古霉素(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2026-04-20 14:58:23+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": "cons-m",
                "document_title": "请会诊执行记录",
                "record_time": "2026-04-07 10:30:00",
                "record_content": (
                    "2026-04-07 10:30 请会诊执行记录\n"
                    "本病人建议使用【(4+7)注射用美罗培南(0.5g)】使用目的为：治疗-内科-经验。"
                    "感染性疾病科合成甲,2026-04-07,09:59:00病史敬悉同意使用，美罗培南加强抗感染，遵嘱。"
                ),
            },
            {
                "document_id": "cons-v",
                "record_time": "2026-04-20 16:59:18",
                "record_content": (
                    "感染科合成乙副主任医师会诊意见:病史敬悉,患者反复发热,同意加用万古霉素联合抗感染。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-05-04", "basis": "discharge_date"},),
    }
    class _ApprovalClient:
        async def generate(self, prompt, **kwargs):
            payload = json.loads(prompt.rsplit("INPUT_JSON=", 1)[1])
            texts = {doc["doc_ref"]: doc["text"] for doc in payload["documents"]}
            events = []
            for ev in payload["events"]:
                if ev["drug"] == "美罗培南":
                    ref = next(r for r in ev["doc_refs"] if "同意使用，美罗培南加强抗感染" in texts[r])
                    events.append({
                        "event_id": ev["event_id"],
                        "documented_use": "yes",
                        "approval_quote": "同意使用，美罗培南加强抗感染",
                        "quote_doc_refs": {"approval": ref},
                    })
                else:
                    ref = next(r for r in ev["doc_refs"] if "同意加用万古霉素联合抗感染" in texts[r])
                    events.append({
                        "event_id": ev["event_id"],
                        "documented_use": "yes",
                        "approval_quote": "同意加用万古霉素联合抗感染",
                        "quote_doc_refs": {"approval": ref},
                    })
            return {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({
                        "schema_version": "lx0609_special_antimicrobial_approval_v1",
                        "events": events,
                    }, ensure_ascii=False)},
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    _, finals = await _run_rules(
        ("LX0609-05-01-06",), rows, llm_client=_ApprovalClient(),
    )
    assert finals["LX0609-05-01-06"]["status"] == "compliant"
    assert finals["LX0609-05-01-06"]["reason_code"] == "requirement_satisfied"


@pytest.mark.asyncio
async def test_p1_6_icu_chief_antimicrobial_consult_recognized_while_missing_drug_remains_flagged():
    rows = {
        "inpat_drug_order": (
            {
                "document_id": "ord-imp",
                "order_id": "O-IMP",
                "generic_name": "注射用亚胺培南西司他丁钠(1.0g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2025-10-20 08:56:49+08:00",
            },
            {
                "document_id": "ord-mer",
                "order_id": "O-MER",
                "generic_name": "(4+7)注射用美罗培南(0.5g)",
                "drug_apply_method": "静脉滴注",
                "order_status": "新开",
                "planned_start_datetime": "2025-12-15 16:21:46+08:00",
            },
        ),
        "consultation_record": (
            {
                "document_id": "cons-icu",
                "record_time": "2025-12-15 16:46:00",
                "record_content": (
                    "鉴于临床药学会诊意见,故请ICU合成主任主任医师行抗生素使用权限会诊,"
                    "经会诊后指出:使用目的为:治疗-外科-药敏,指征:急性细菌性下呼吸道感染,"
                    "2025-12-14 痰一般细菌培养:细菌结果(质谱法)1: 肺炎克雷伯菌3+多耐感染。"
                    "故同意使用美罗培南加强抗感染治疗。"
                ),
            },
        ),
        "evaluation_context.horizon": ({"horizon_date": "2026-01-29", "basis": "discharge_date"},),
    }
    _, finals = await _run_rules(
        ("LX0609-05-01-06",), rows, llm_client=FrozenSpecialApprovalClient(),
    )
    # 亚胺培南确无会诊 -> 仍判 non_compliant；但美罗培南已被 ICU 主任医师权限会诊覆盖，不再列入缺支持清单
    assert finals["LX0609-05-01-06"]["status"] == "non_compliant"
    assert finals["LX0609-05-01-06"]["customer_display_facts"]["unmatched_special_antimicrobials"] == ["亚胺培南"]


@pytest.mark.parametrize("text,quote,expected", [
    (
        "感染性疾病科合成甲,2026-04-07,09:59:00病史敬悉同意使用，美罗培南加强抗感染。",
        "同意使用，美罗培南加强抗感染",
        True,
    ),
    (
        "故请ICU合成甲主任医师行抗生素使用权限会诊,经会诊后指出:使用目的为:治疗-外科-药敏,"
        "2025-12-14 痰一般细菌培养:肺炎克雷伯菌3+多耐感染。故同意使用美罗培南加强抗感染。",
        "同意使用美罗培南加强抗感染",
        True,
    ),
    # 负向守卫：初级/主治职称、临床药师、申请单文本不得放行
    ("感染科合成甲主治医师,2026-04-07,09:59:00同意使用美罗培南。", "同意使用美罗培南", False),
    ("感染科合成乙住院医师,2026-04-07,09:59:00同意使用美罗培南。", "同意使用美罗培南", False),
    ("临床药学科合成丙主管药师会诊意见:建议加用万古霉素。", "建议加用万古霉素", False),
    (
        "故请ICU合成甲主任医师行抗生素使用权限会诊。本病人建议使用【注射用伏立康唑】，使用目的为：治疗-经验。",
        "本病人建议使用【注射用伏立康唑】",
        False,
    ),
])
def test_p1_6_authorized_expert_helper_boundaries(text: str, quote: str, expected: bool):
    assert ned._special_approval_by_authorized_expert(text, quote) is expected
