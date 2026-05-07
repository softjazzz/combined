from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.database.models.cdm import FirstCourseRecord, TransferInRecord, TransferOutRecord
from app.services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    classify_manual_issue_text,
    load_manual_case_rows_from_excel,
)
from app.services.etl_sync import expand_table_groups, list_sync_table_groups, list_sync_tables
import pandas as pd
import pytest
from types import SimpleNamespace


class _FakeMappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappingsResult(self._rows)


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _stmt):
        return _FakeExecuteResult(self._rows)

    def close(self):
        return None


class _FakeRefreshSession:
    def __init__(self, rows):
        self._rows = rows
        self.updates = []
        self.committed = False

    def execute(self, stmt):
        if getattr(stmt, "is_select", False):
            return _FakeExecuteResult(self._rows)
        if getattr(stmt, "is_update", False):
            compile_state = stmt._compile_state_factory(stmt, None)  # type: ignore[attr-defined]
            values = dict(getattr(compile_state, "_dict_parameters", {}) or {})
            self.updates.append(values)
            return _FakeExecuteResult([])
        return _FakeExecuteResult([])

    def commit(self):
        self.committed = True

    def close(self):
        return None


def test_classify_first_course_intrinsic_issue():
    result = classify_manual_issue_text("首次病程记录鉴别诊断不全面")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "first_course_reasoning"
    assert "SC-026" in result["candidate_rule_ids"]
    assert result["include_in_batch_1"] is True


def test_sample_pool_default_sync_uses_full_domain_group():
    plan = CustomQCSamplePoolService.resolve_sync_table_names()

    assert plan["group_ids"] == ["sample_full_domain"]
    assert "first_course_record_diagnosis" in plan["table_names"]
    assert "postsurg_firstcourse_record" in plan["table_names"]
    assert "inpat_bill_item" in plan["table_names"]
    assert "labtest_item_report" in plan["table_names"]
    assert "exam_item_report" in plan["table_names"]
    assert "blood_application" in plan["table_names"]
    assert "crisis_value_record" in plan["table_names"]
    assert "docpat_commu_record" in plan["table_names"]
    assert "postane_surveil_record" in plan["table_names"]


def test_sample_full_domain_group_is_available_for_source_coverage_audit():
    group_ids = {item["id"] for item in list_sync_table_groups()}
    table_names, missing = expand_table_groups(["sample_full_domain"])

    assert "sample_full_domain" in group_ids
    assert missing == []
    assert "admission_record" in table_names
    assert "consultation_record" in table_names
    assert "exam_item_report" in table_names
    assert "labtest_item_report" in table_names
    assert "blood_application" in table_names
    assert "pathology_exam_report" in table_names


def test_sample_full_domain_key_fields_cover_customer_source_tables():
    table_map = {item["name"]: item for item in list_sync_tables()}

    assert table_map["labtest_item_report"]["key_fields"] == ["patient_id", "visit_id", "test_no", "item_no"]
    assert table_map["exam_item_report"]["key_fields"] == ["patient_id", "visit_id", "exam_no", "item_no"]
    assert table_map["blood_application"]["key_fields"] == ["patient_id", "visit_id", "application_id"]


def test_first_course_record_model_contains_structured_content_fields():
    columns = set(FirstCourseRecord.__table__.columns.keys())

    assert "case_characteristic" in columns
    assert "diagnose_based_on" in columns
    assert "differential_diagnosis" in columns
    assert "treatment_plan" in columns


def test_transfer_record_models_contain_structured_content_fields():
    transfer_in_columns = set(TransferInRecord.__table__.columns.keys())
    transfer_out_columns = set(TransferOutRecord.__table__.columns.keys())

    assert "transfer_purpose" in transfer_in_columns
    assert "treatment_course" in transfer_in_columns
    assert "transfer_treatment_plan" in transfer_in_columns
    assert "current_situation" in transfer_in_columns
    assert "transfer_purpose" in transfer_out_columns
    assert "treatment_course" in transfer_out_columns
    assert "current_situation" in transfer_out_columns


def test_resolve_first_course_reasoning_should_route_sc025():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_course_reasoning",
        manual_issue_text="首次病程中只有主诊断有诊断依据及鉴别诊断，其余诊断均未书写诊断依据及鉴别诊断",
    )

    assert rule_ids == ["SC-025"]


def test_classify_programmatic_issue():
    result = classify_manual_issue_text("未及时书写日常病程记录及上级医师查房记录")
    assert result["coverage_type"] == "programmatic"
    assert result["include_in_batch_1"] is False
    assert result["candidate_rule_ids"] == []


def test_classify_consultation_execution_issue():
    result = classify_manual_issue_text("会诊意见未在病程中落实")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consultation_execution"
    assert result["candidate_rule_ids"] == ["SC-070", "LX-016"]


def test_classify_consultation_execution_followthrough_issue():
    result = classify_manual_issue_text("3月9日请会诊执行记录描述为遵执，但实际未按会诊意见执行")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consultation_execution"
    assert result["candidate_rule_ids"] == ["SC-070", "LX-016"]
    assert result["include_in_batch_1"] is True


def test_classify_consultation_record_quality_issue():
    result = classify_manual_issue_text("2026年2月4日会诊记录中存在大量复制其他科室会诊意见的情况，并无综合会诊结果提出建设性诊疗意见。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consultation_record_quality"
    assert result["candidate_rule_ids"] == ["SC-069"]


def test_consultation_family_prompt_includes_multi_subitem_contract():
    prompt = sample_pool_module.build_consultation_family_prompt(
        manual_issue_text="会诊意见未落实，后续医嘱与会诊记录不一致。",
        consultation_bundle={"consultation_records": [], "course_records": [], "order_summary": []},
    )

    assert "一次 LLM 调用" in prompt
    assert "sub_items" in prompt
    assert "SC-069" in prompt
    assert "SC-070" in prompt
    assert "LX-016" in prompt
    assert "SC-146" in prompt
    assert "SC-046" in prompt
    assert "不要把人工问题文本当作事实" in prompt


def test_resolve_consultation_family_recommendations_keeps_partial_not_exact():
    result = sample_pool_module.resolve_consultation_family_rule_recommendations(
        "康复会诊拒绝后仍开康复治疗，且清创术无操作记录。",
        llm_output={
            "primary_rule_id": "SC-069",
            "recommended_rule_ids": ["SC-069", "LX-016", "SC-146", "SC-046"],
            "overall_result": "partial_hit",
            "overall_status": "non_compliant",
            "qc_result": "non_compliant",
            "sub_items": [
                {
                    "rule_id": "LX-016",
                    "status": "non_compliant",
                    "item": "会诊意见落实",
                    "evidence": "会诊记录写患者拒绝康复治疗，后续病程仍写继续康复治疗。",
                    "reason": "会诊沟通结论与后续执行记录不一致。",
                },
                {
                    "rule_id": "SC-046",
                    "status": "compliant",
                    "item": "清创操作记录",
                    "evidence": "病程记录可见左膝清创引流术记录。",
                    "reason": "人工问题称无操作记录与当前原文冲突。",
                },
                {
                    "rule_id": "SC-146",
                    "status": "uncertain",
                    "item": "康复治疗医嘱一致性",
                    "evidence": "",
                    "reason": "缺医嘱明细，无法核准实际开具项目。",
                },
            ],
            "conflicts": ["清创术无操作记录与现有清创记录冲突"],
            "missing_evidence": ["缺康复治疗医嘱明细"],
            "qc_conclusion": "只能确认会诊执行链路部分成立，不能整条 exact。",
            "confidence": 0.77,
        },
    )

    assert result["primary_rule_id"] == "SC-069"
    assert result["secondary_rule_ids"] == ["LX-016", "SC-146", "SC-046"]
    assert result["overall_result"] == "partial_hit"
    assert result["overall_status"] == "non_compliant"
    assert len(result["sub_items"]) == 3
    assert result["sub_items"][0]["rule_id"] == "LX-016"
    assert result["sub_items"][1]["status"] == "compliant"
    assert result["conflicts"] == ["清创术无操作记录与现有清创记录冲突"]
    assert result["missing_evidence"] == ["缺康复治疗医嘱明细"]


def test_resolve_consultation_family_recommendations_accepts_exact_hit_contract():
    result = sample_pool_module.resolve_consultation_family_rule_recommendations(
        "会诊后无执行记录。",
        llm_output={
            "primary_rule_id": "SC-070",
            "recommended_rule_ids": ["SC-070", "LX-016"],
            "overall_result": "exact_hit",
            "overall_status": "non_compliant",
            "qc_result": "non_compliant",
            "sub_items": [
                {
                    "rule_id": "SC-070",
                    "status": "non_compliant",
                    "item": "会诊执行记录缺失",
                    "evidence": "会诊记录存在，后续病程和执行清单均无执行记录。",
                    "reason": "核心锚点完整覆盖。",
                }
            ],
            "confidence": 0.9,
        },
    )

    assert result["primary_rule_id"] == "SC-070"
    assert result["overall_result"] == "exact_hit"
    assert result["overall_status"] == "non_compliant"


def test_classify_senior_round_content_issue():
    result = classify_manual_issue_text("3月10日副主任医师查房记录内容空洞，无病情分析，无诊疗意见。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "senior_round_content"
    assert result["candidate_rule_ids"] == ["SC-049", "SC-050", "SC-052"]


def test_classify_unreasonable_copy_content_issue_should_route_cl275():
    result = classify_manual_issue_text("2月4日副主任医师查房记录与2月3日主治医师查房记录复制粘贴严重（相似度100%）。")

    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "unreasonable_copy_content"
    assert result["candidate_rule_ids"] == ["CL-273", "CL-274", "CL-275", "CL-276"]


def test_classify_unreasonable_copy_content_issue_should_route_cl273():
    result = classify_manual_issue_text("首次病程记录病例特点与入院记录、现病史完全相同。")

    assert result["issue_category"] == "unreasonable_copy_content"
    assert result["candidate_rule_ids"] == ["CL-273", "CL-274", "CL-275", "CL-276"]


def test_classify_unreasonable_copy_content_issue_should_route_cl274():
    result = classify_manual_issue_text("拟诊讨论部分重复病例特点，缺少新增诊断推理。")

    assert result["issue_category"] == "unreasonable_copy_content"
    assert result["candidate_rule_ids"] == ["CL-273", "CL-274", "CL-275", "CL-276"]


def test_classify_unreasonable_copy_content_issue_should_route_cl276():
    result = classify_manual_issue_text("同科同种疾病拟诊讨论内容完全相同，存在模板化照抄。")

    assert result["issue_category"] == "unreasonable_copy_content"
    assert result["candidate_rule_ids"] == ["CL-273", "CL-274", "CL-275", "CL-276"]


def test_classify_senior_round_timeliness_issue_should_remain_programmatic():
    result = classify_manual_issue_text("48小时无主治医师查房记录、72小时无高级职称医师查房记录")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "first_round_timeliness"
    assert result["candidate_rule_ids"] == ["SC-048", "SC-049"]


def test_classify_first_course_timeliness_issue_should_route_sc021_sc022():
    result = classify_manual_issue_text("入院8小时内未完成首次病程记录")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "first_course_timeliness"
    assert result["candidate_rule_ids"] == ["SC-021", "SC-022"]
    assert result["include_in_batch_1"] is True


def test_classify_course_gap_timeliness_issue_should_route_lxe18():
    result = classify_manual_issue_text("1月16日以后，无病程记录")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "course_gap_timeliness"
    assert result["candidate_rule_ids"] == ["LXE-18"]
    assert result["include_in_batch_1"] is True


def test_classify_consultation_timeliness_issue_should_route_sc071_sc072():
    result = classify_manual_issue_text("会诊记录时间节点早于呼吸科会诊接收时间")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "consultation_timeliness"
    assert result["candidate_rule_ids"] == ["SC-071", "SC-072"]
    assert result["include_in_batch_1"] is True


def test_classify_operation_record_timeliness_issue_should_route_sc096():
    result = classify_manual_issue_text("手术记录未在术后24小时内完成")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "operation_record_timeliness"
    assert result["candidate_rule_ids"] == ["SC-096"]
    assert result["include_in_batch_1"] is True


def test_classify_daily_course_analysis_issue():
    result = classify_manual_issue_text("4.1异常检查检验结果病程记录未分析和记录")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "daily_course_analysis"
    assert result["candidate_rule_ids"] == ["SC-032", "SC-033", "SC-036"]


def test_classify_invasive_operation_record_issue():
    result = classify_manual_issue_text("患者行了骨髓穿刺，无有创操作记录")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "invasive_operation_record_quality"
    assert result["candidate_rule_ids"] == ["SC-045", "SC-046"]


def test_classify_invasive_operation_record_quality_issue():
    result = classify_manual_issue_text("有创操作记录书写不规范，未明确记录操作者、操作时间及术后注意事项。")
    assert result["issue_category"] == "invasive_operation_record_quality"
    assert result["candidate_rule_ids"] == ["SC-046", "SC-045"]


def test_classify_transfer_record_quality_issue():
    result = classify_manual_issue_text("转科记录中转出记录未书写拟转入科室，转入记录中未书写转入时间。")
    assert result["coverage_type"] == "programmatic"
    assert result["issue_category"] == "transfer_record_quality"
    assert result["candidate_rule_ids"] == ["SC-064"]


def test_classify_difficult_case_discussion_issue():
    result = classify_manual_issue_text("患者入院超过3天未明确诊断未进行疑难病历讨论")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "difficult_case_discussion"
    assert result["candidate_rule_ids"] == ["SC-056", "SC-057", "SC-058"]


def test_classify_transfusion_record_quality_issue():
    result = classify_manual_issue_text("输血后评价时间未书写")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "transfusion_record_quality"
    assert result["candidate_rule_ids"] == ["SC-074", "LX-018", "SC-073"]


def test_classify_operation_preop_risk_assessment_issue():
    result = classify_manual_issue_text("急诊手术术前准备不充分，预案不清晰。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "operation_preop_risk_assessment"
    assert result["candidate_rule_ids"] == ["SC-081", "SC-082", "SC-097"]


def test_classify_diagnosis_or_treatment_followup_issue():
    result = classify_manual_issue_text("有血管彩超，且结果阳性，入院后无诊断，无相关处理。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "daily_course_analysis"
    assert result["candidate_rule_ids"] == ["SC-036", "SC-032", "SC-033"]


def test_resolve_first_course_timeliness_should_prefer_sc021():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_course_timeliness",
        manual_issue_text="入院8小时内未完成首次病程记录",
    )
    assert rule_ids == ["SC-021"]


def test_resolve_first_course_timeliness_should_remap_reasoning_issue_to_sc026():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_course_timeliness",
        manual_issue_text="首次病程鉴别诊断不全面，诊断依据不充分。",
    )
    assert rule_ids == ["SC-026"]


def test_resolve_first_course_timeliness_should_remap_postsurg_quality_to_sc105():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_course_timeliness",
        manual_issue_text="术后首次病程记录书写不规范，缺少术后处理措施。",
    )
    assert rule_ids == ["SC-105"]


def test_resolve_first_course_timeliness_should_remap_upper_round_issue_to_sc049():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_course_timeliness",
        manual_issue_text="入院72小时以内无副主任医师以上首次查房记录。",
    )
    assert rule_ids == ["SC-049"]


def test_resolve_course_gap_timeliness_should_route_lxe18():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="course_gap_timeliness",
        manual_issue_text="1月16日以后，无病程记录",
    )
    assert rule_ids == ["LXE-18"]


def test_resolve_first_round_timeliness_should_route_sc049_for_upper_round_only():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="first_round_timeliness",
        manual_issue_text="入院72小时以内未查见副主任医师查房记录。",
    )
    assert rule_ids == ["SC-049"]


def test_resolve_consultation_timeliness_should_route_sc071():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="consultation_timeliness",
        manual_issue_text="会诊记录时间节点早于呼吸科会诊接收时间",
    )
    assert rule_ids == ["SC-071"]


def test_resolve_operation_record_timeliness_should_route_sc096():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="operation_record_timeliness",
        manual_issue_text="手术记录未在术后24小时内完成",
    )
    assert rule_ids == ["SC-096"]


def test_daily_course_analysis_should_prefer_sc032_for_brief_change_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="daily_course_analysis",
        manual_issue_text="病程记录过于简略，未描述患者病情变化、目前症状及体征。",
    )

    assert rule_ids == ["SC-032"]


def test_daily_course_analysis_should_remap_admission_consistency_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="daily_course_analysis",
        manual_issue_text="现病史记录不全，未记录肿物性状，专科检查未描述左下肢情况。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_daily_course_analysis_should_remap_upper_round_timeliness_text_to_sc049():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="daily_course_analysis",
        manual_issue_text="72小时以内无副主任医师以上查房，已新建病程但无具体内容。",
    )

    assert rule_ids == ["SC-049"]


def test_resolve_unreasonable_copy_customer_rule_ids_should_pick_cl275_for_round_copy():
    rule_ids = sample_pool_module._resolve_unreasonable_copy_customer_rule_ids(
        "2月4日副主任医师查房记录与2月3日主治医师查房记录复制粘贴严重（相似度100%）。"
    )

    assert rule_ids == ["CL-275"]


def test_resolve_unreasonable_copy_customer_rule_ids_should_pick_cl273():
    rule_ids = sample_pool_module._resolve_unreasonable_copy_customer_rule_ids(
        "首次病程记录病例特点与入院记录、现病史完全相同。"
    )

    assert rule_ids == ["CL-273"]


def test_resolve_unreasonable_copy_customer_rule_ids_should_pick_cl274():
    rule_ids = sample_pool_module._resolve_unreasonable_copy_customer_rule_ids(
        "拟诊讨论部分重复病例特点，诊断依据和鉴别诊断没有新增内容。"
    )

    assert rule_ids == ["CL-274"]


def test_resolve_unreasonable_copy_customer_rule_ids_should_pick_cl276():
    rule_ids = sample_pool_module._resolve_unreasonable_copy_customer_rule_ids(
        "同科同种疾病拟诊讨论内容完全相同，属于模板化照抄。"
    )

    assert rule_ids == ["CL-276"]


def test_classify_presurg_summary_quality_issue():
    result = classify_manual_issue_text("未按要求书写术前小结记录，术前小结记录：手术要点归纳把握不准确。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "presurg_summary_quality"
    assert result["candidate_rule_ids"] == ["SC-081"]


def test_classify_postsurg_firstcourse_quality_issue():
    result = classify_manual_issue_text("术后首次病程记录书写不规范，缺少术后处理措施、术后注意事项及向家属告知手术情况等内容。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "postsurg_firstcourse_quality"
    assert result["candidate_rule_ids"] == ["SC-105"]


def test_classify_critical_value_management_issue():
    result = classify_manual_issue_text("2026年3月11日危急值处理记录仅描写K 2.76mmol/L，行静脉补钾，未描述危急值报告、处置时间及具体补钾情况。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "critical_value_management"
    assert result["candidate_rule_ids"] == ["SC-039"]


def test_classify_handover_communication_issue():
    result = classify_manual_issue_text("管床医生发生变更未书写交接班记录")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "handover_communication"
    assert result["candidate_rule_ids"] == ["SC-062", "SC-063"]


def test_classify_consent_quality_issue_should_not_fall_back_to_programmatic():
    result = classify_manual_issue_text("手术同意书签字人员非授权受托人")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consent_quality"
    assert result["candidate_rule_ids"] == ["SC-128", "SC-087", "SC-089", "LX-021"]


def test_classify_progress_order_consistency_issue():
    result = classify_manual_issue_text("在术前小结及术前讨论之前，已经下达手术医嘱。")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "progress_order_consistency"
    assert result["candidate_rule_ids"] == ["SC-146"]


def test_resolve_admission_consistency_should_route_sc018():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="入院记录中无专科检查",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc019():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史中检查项目记录有错误，院外辅助检查记录不完善。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc020():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者既往有高血压病史，入院诊断未诊断高血压。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_classify_admission_diagnosis_with_special_exam_should_route_admission_consistency():
    result = sample_pool_module.classify_manual_issue_text(
        "入院诊断疼痛，诊断不准确，专科查体中显示主被动活动受限，但入院诊断未体现"
    )

    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "admission_consistency"
    assert result["include_in_batch_1"] is True
    assert "SC-020" in result["candidate_rule_ids"]


def test_resolve_admission_consistency_should_prefer_sc020_over_sc018_in_mixed_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者既往有高血压病史，入院诊断未诊断高血压，体格检查无相关描述。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc011():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史阴性症状采集不全面，不能支撑鉴别诊断。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc012():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史治疗经过不详细，门诊检查项目及结果未记录。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc010():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="既往史患者用药情况未详细记录，婚育情况不详。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_prefer_sc012_over_sc020_in_mixed_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者双膝疼痛10年，现病史治疗经过不详细，不能很好的指导本次住院治疗；患者既往有类风湿关节炎，入院诊断未体现。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_should_route_sc009():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史未描述疼痛性质、持续时间、缓解方式等。",
    )

    assert rule_ids == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)


def test_resolve_admission_consistency_recommendations_should_return_multi_rule_items():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "主诉书写不完整，既往史患者用药情况未详细记录，体格检查中无专科检查，入院诊断未体现高血压。",
        llm_output={
            "primary_rule_id": "SC-008",
            "recommended_rule_ids": ["SC-008", "SC-010", "SC-018", "SC-020"],
            "sub_items": [
                {
                    "rule_id": "SC-008",
                    "item": "主诉规范性",
                    "status": "non_compliant",
                    "matched_manual_issue_part": "主诉书写不完整",
                    "evidence": "主诉无法导出第一诊断",
                    "reason": "主诉锚点明确",
                },
                {
                    "rule_id": "SC-010",
                    "item": "既往史完整性",
                    "status": "non_compliant",
                    "matched_manual_issue_part": "既往史患者用药情况未详细记录",
                    "evidence": "既往用药缺剂量",
                    "reason": "既往史缺项",
                },
                {
                    "rule_id": "SC-018",
                    "item": "查体专科",
                    "status": "non_compliant",
                    "matched_manual_issue_part": "体格检查中无专科检查",
                    "evidence": "未见专科检查",
                    "reason": "查体缺项",
                },
                {
                    "rule_id": "SC-020",
                    "item": "初步诊断",
                    "status": "uncertain",
                    "matched_manual_issue_part": "入院诊断未体现高血压",
                    "evidence": "需结合入院诊断核对",
                    "reason": "诊断锚点明确",
                },
            ],
            "overall_result": "partial_hit",
            "qc_conclusion": "多锚点问题",
            "confidence": 0.82,
        },
    )

    assert recommendation["primary_rule_id"] == "SC-008"
    assert recommendation["secondary_rule_ids"] == ["SC-010", "SC-018", "SC-020"]
    assert recommendation["recommended_rule_ids"] == ["SC-008", "SC-010", "SC-018", "SC-020"]
    assert [item["rule_id"] for item in recommendation["sub_items"]] == ["SC-008", "SC-010", "SC-018", "SC-020"]
    assert recommendation["overall_result"] == "partial_hit"
    assert recommendation["review_required"] is False


def test_resolve_admission_consistency_should_keep_family_level_contract_fields():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "现病史疼痛性质缺失，既往史用药不详，体格检查缺专科情况。",
        llm_output={
            "primary_rule_id": "SC-009",
            "matched_rule_ids": ["SC-009", "SC-010", "SC-018"],
            "sub_items": [
                {"rule_id": "SC-009", "status": "non_compliant", "item": "疼痛性质"},
                {"rule_id": "SC-010", "status": "non_compliant", "item": "用药史"},
                {"rule_id": "SC-018", "status": "uncertain", "item": "专科情况"},
            ],
            "overall_status": "non_compliant",
            "overall_result": "partial_hit",
            "conflicts": ["专科情况原文存在但不完整"],
            "missing_evidence": ["缺门诊治疗经过原句"],
            "confidence": 0.86,
        },
    )

    assert recommendation["primary_rule_id"] == "SC-009"
    assert recommendation["recommended_rule_ids"] == ["SC-009", "SC-010", "SC-018"]
    assert recommendation["matched_rule_ids"] == ["SC-009", "SC-010", "SC-018"]
    assert recommendation["overall_status"] == "non_compliant"
    assert recommendation["conflicts"] == ["专科情况原文存在但不完整"]
    assert recommendation["missing_evidence"] == ["缺门诊治疗经过原句"]


def test_resolve_admission_consistency_should_mark_invalid_rule_id_uncertain():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "入院记录问题",
        llm_output={
            "primary_rule_id": "SC-999",
            "recommended_rule_ids": ["SC-999", "SC-018"],
            "sub_items": [{"rule_id": "SC-999", "status": "non_compliant"}],
            "overall_result": "hit",
            "confidence": 0.7,
        },
        fallback_primary_rule_id="SC-008",
    )

    assert recommendation["primary_rule_id"] == "SC-008"
    assert recommendation["recommended_rule_ids"] == ["SC-008", "SC-018"]
    assert recommendation["overall_result"] == "uncertain"
    assert recommendation["review_required"] is True
    assert recommendation["invalid_rule_ids"] == ["SC-999"]


def test_resolve_admission_consistency_should_not_keep_non_compliant_items_for_no_hit():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "入院记录中未记录患儿喂养史",
        llm_output={
            "primary_rule_id": "SC-010",
            "recommended_rule_ids": ["SC-010"],
            "sub_items": [
                {
                    "rule_id": "SC-010",
                    "item": "既往史完整性",
                    "status": "non_compliant",
                    "matched_manual_issue_part": "未记录患儿喂养史",
                    "evidence": "原文已记录母乳喂养、辅食添加及当前人工喂养。",
                    "reason": "人工问题与原文冲突，判定为无命中。",
                }
            ],
            "overall_result": "no_hit",
            "confidence": 0.95,
        },
    )

    assert recommendation["overall_result"] == "no_hit"
    assert recommendation["sub_items"][0]["status"] == "compliant"


def test_resolve_admission_consistency_should_keep_sc020_structured_diagnosis_fields():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "入院诊断疼痛，诊断不准确，专科查体显示活动受限。",
        llm_output={
            "primary_rule_id": "SC-020",
            "recommended_rule_ids": ["SC-020"],
            "sub_items": [
                {
                    "rule_id": "SC-020",
                    "item": "初步诊断",
                    "status": "non_compliant",
                    "matched_manual_issue_part": "诊断不准确",
                    "evidence": "诊断仅写疼痛，现病史/专科查体已有明确损伤部位和活动受限。",
                    "reason": "症状性诊断未覆盖核心阳性证据。",
                }
            ],
            "admission_diagnoses": ["疼痛"],
            "symptom_or_sign_only_diagnoses": ["疼痛"],
            "core_abnormal_evidence": ["明确损伤部位", "主被动活动受限"],
            "diagnosis_coverage": "not_covered",
            "qc_result": "non_compliant",
            "overall_result": "hit",
            "confidence": 0.92,
        },
    )

    assert recommendation["primary_rule_id"] == "SC-020"
    assert recommendation["admission_diagnoses"] == ["疼痛"]
    assert recommendation["symptom_or_sign_only_diagnoses"] == ["疼痛"]
    assert recommendation["core_abnormal_evidence"] == ["明确损伤部位", "主被动活动受限"]
    assert recommendation["diagnosis_coverage"] == "not_covered"
    assert recommendation["qc_result"] == "non_compliant"


def test_resolve_admission_consistency_should_not_force_uncertain_diagnosis_to_non_compliant():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "入院诊断待查，需结合现病史。",
        llm_output={
            "primary_rule_id": "SC-020",
            "recommended_rule_ids": ["SC-020"],
            "sub_items": [
                {
                    "rule_id": "SC-020",
                    "item": "初步诊断",
                    "status": "uncertain",
                    "matched_manual_issue_part": "入院诊断待查",
                    "evidence": "证据不足，诊断带待查表达。",
                    "reason": "不能强打。",
                }
            ],
            "admission_diagnoses": ["腹痛原因待查？"],
            "symptom_or_sign_only_diagnoses": ["腹痛原因待查？"],
            "core_abnormal_evidence": [],
            "diagnosis_coverage": "uncertain",
            "qc_result": "uncertain",
            "overall_result": "uncertain",
            "confidence": 0.7,
        },
    )

    assert recommendation["diagnosis_coverage"] == "uncertain"
    assert recommendation["qc_result"] == "uncertain"
    assert recommendation["sub_items"][0]["status"] == "uncertain"


def test_resolve_admission_consistency_without_llm_should_require_review():
    recommendation = sample_pool_module.resolve_admission_consistency_rule_recommendations(
        "现病史未描述发病时间",
        fallback_primary_rule_id="SC-009",
    )

    assert recommendation["primary_rule_id"] == "SC-009"
    assert recommendation["recommended_rule_ids"] == ["SC-009"]
    assert recommendation["overall_result"] == "uncertain"
    assert recommendation["review_required"] is True


def test_classify_operation_record_quality_issue():
    result = classify_manual_issue_text("手术记录手术结束时间错误（1月26日10：00误写为1月27日10:00）")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "operation_record_quality"
    assert result["candidate_rule_ids"] == ["SC-097", "SC-098"]


def test_classify_operation_preop_mdt_issue():
    result = classify_manual_issue_text("四级肿瘤手术，多学科会诊不能代替MDT")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "operation_preop_mdt"
    assert result["candidate_rule_ids"] == ["SC-083"]


def test_classify_operation_preop_conclusion_issue():
    result = classify_manual_issue_text("术前讨论记录未明确手术时间及手术医生")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "operation_preop_conclusion"
    assert result["candidate_rule_ids"] == ["SC-084", "SC-085"]


def test_build_sample_pool_item_classification_update_should_support_second_batch_categories():
    consultation_patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "2026年2月4日会诊记录中存在大量复制其他科室会诊意见的情况，并无综合会诊结果提出建设性诊疗意见。"}
    )
    critical_patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "2026年3月11日危急值处理记录仅描写K 2.76mmol/L，行静脉补钾，未描述危急值报告、处置时间及具体补钾情况。"}
    )
    order_patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "在术前小结及术前讨论之前，已经下达手术医嘱。"}
    )

    assert consultation_patch["issue_category"] == "consultation_record_quality"
    assert consultation_patch["candidate_rule_ids_json"] == '["SC-069"]'
    assert critical_patch["issue_category"] == "critical_value_management"
    assert critical_patch["candidate_rule_ids_json"] == '["SC-039"]'
    assert order_patch["issue_category"] == "progress_order_consistency"
    assert order_patch["candidate_rule_ids_json"] == '["SC-146"]'


def test_build_sample_pool_item_classification_update_should_support_operation_record_quality():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "手术记录中手术名称与术前讨论及术前小结中手术名称不一致"}
    )

    assert patch["issue_category"] == "operation_record_quality"
    assert patch["candidate_rule_ids_json"] == '["SC-097", "SC-098"]'


def test_build_sample_pool_item_classification_update_should_support_operation_preop_mdt():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "四级肿瘤手术，多学科会诊不能代替MDT"}
    )

    assert patch["issue_category"] == "operation_preop_mdt"
    assert patch["candidate_rule_ids_json"] == '["SC-083"]'


def test_build_sample_pool_item_classification_update_should_support_operation_preop_conclusion():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "术前讨论记录未明确手术时间及手术医生"}
    )

    assert patch["issue_category"] == "operation_preop_conclusion"
    assert patch["candidate_rule_ids_json"] == '["SC-084", "SC-085"]'


def test_build_sample_pool_item_classification_update_should_support_unreasonable_copy_content():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "2月4日副主任医师查房记录与2月3日主治医师查房记录复制粘贴严重（相似度100%）。"}
    )

    assert patch["issue_category"] == "unreasonable_copy_content"
    assert patch["candidate_rule_ids_json"] == '["CL-273", "CL-274", "CL-275", "CL-276"]'


def test_build_sample_pool_item_classification_update_should_support_handover_communication():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "管床医生发生变更未书写交接班记录"}
    )

    assert patch["issue_category"] == "handover_communication"
    assert patch["candidate_rule_ids_json"] == '["SC-062", "SC-063"]'


def test_build_sample_pool_item_classification_update_should_support_consent_quality():
    patch = sample_pool_module.build_sample_pool_item_classification_update(
        {"manual_issue_text": "手术同意书签字人员非授权受托人"}
    )

    assert patch["issue_category"] == "consent_quality"
    assert patch["candidate_rule_ids_json"] == '["SC-128", "SC-087", "SC-089", "LX-021"]'


def test_refresh_pool_item_classifications_should_update_existing_items(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "manual_issue_text": "2026年2月4日会诊记录中存在大量复制其他科室会诊意见的情况，并无综合会诊结果提出建设性诊疗意见。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_execution",
            "expected_scene": "running",
            "candidate_rule_ids_json": '["SC-070"]',
            "include_in_batch_1": True,
            "exclude_reason": "",
        },
        {
            "id": "item-2",
            "pool_id": "pool-1",
            "row_no": 2,
            "manual_issue_text": "在术前小结及术前讨论之前，已经下达手术医嘱。",
            "coverage_type": "unsupported",
            "issue_category": "unclassified",
            "expected_scene": "running",
            "candidate_rule_ids_json": "[]",
            "include_in_batch_1": False,
            "exclude_reason": "当前未归入首批内涵问题分类，请人工确认",
        },
    ]
    fake_session = _FakeRefreshSession(rows)
    monkeypatch.setattr(sample_pool_module, "_session", lambda: fake_session)
    monkeypatch.setattr(service, "_update_pool_counters", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "get_pool", lambda **_: {"id": "pool-1"})

    result = service.refresh_pool_item_classifications(pool_id="pool-1")

    assert result["scanned"] == 2
    assert result["updated"] == 2
    assert result["changed_categories"] == 2
    assert result["changed_coverages"] == 1
    assert fake_session.committed is True
    categories = {getattr(item["issue_category"], "value", item["issue_category"]) for item in fake_session.updates}
    candidate_rules = {
        getattr(item["candidate_rule_ids_json"], "value", item["candidate_rule_ids_json"])
        for item in fake_session.updates
    }
    assert "consultation_record_quality" in categories
    assert "progress_order_consistency" in categories
    assert '["SC-069"]' in candidate_rules
    assert '["SC-146"]' in candidate_rules


def test_classify_empty_issue_defaults_to_intrinsic_record_batch():
    result = classify_manual_issue_text("")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "record_list_intrinsic"
    assert result["include_in_batch_1"] is True
    assert "SC-023" in result["candidate_rule_ids"]


def test_load_manual_case_rows_from_excel_supports_minimal_identifier_columns(monkeypatch):
    dataframe = pd.DataFrame(
        [
            ["住院号", "visit_id", "存在问题"],
            ["2248248", "", ""],
            ["", "VISIT-001", "首次病程记录鉴别诊断不全面"],
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: dataframe)

    rows = load_manual_case_rows_from_excel(file_path="demo.xlsx", sheet_name="Sheet2")

    assert len(rows) == 2
    assert rows[0]["mr_no"] == "2248248"
    assert rows[0]["visit_id"] == ""
    assert rows[1]["mr_no"] == ""
    assert rows[1]["visit_id"] == "VISIT-001"
    assert rows[1]["manual_issue_text"] == "首次病程记录鉴别诊断不全面"


def test_load_manual_case_rows_from_excel_keeps_mr_no_only_rows(monkeypatch):
    dataframe = pd.DataFrame(
        [
            ["住院号", "visit_id", "存在问题"],
            ["161241", "", ""],
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: dataframe)

    rows = load_manual_case_rows_from_excel(file_path="demo.xlsx", sheet_name="Sheet2")

    assert len(rows) == 1
    assert rows[0]["mr_no"] == "161241"
    assert rows[0]["visit_id"] == ""


def test_load_manual_case_rows_from_excel_supports_mr_no_only_template(monkeypatch):
    dataframe = pd.DataFrame(
        [
            ["住院号"],
            ["2248248"],
            ["161241"],
        ]
    )
    calls = []

    def fake_read_excel(*args, **kwargs):
        calls.append(kwargs)
        return dataframe

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    rows = load_manual_case_rows_from_excel(file_path="demo.xlsx", sheet_name="")

    assert [row["mr_no"] for row in rows] == ["2248248", "161241"]
    assert all(row["visit_id"] == "" for row in rows)
    assert calls[0]["sheet_name"] == 0


def test_load_manual_case_rows_from_excel_falls_back_to_first_sheet_when_sheet2_missing(monkeypatch):
    dataframe = pd.DataFrame(
        [
            ["住院号"],
            ["2248248"],
        ]
    )
    calls = []

    def fake_read_excel(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("sheet_name") == "Sheet2":
            raise ValueError("Worksheet named 'Sheet2' not found")
        return dataframe

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    rows = load_manual_case_rows_from_excel(file_path="demo.xlsx", sheet_name="Sheet2")

    assert len(rows) == 1
    assert rows[0]["mr_no"] == "2248248"
    assert [call["sheet_name"] for call in calls] == ["Sheet2", 0]


def test_resolve_sync_table_names_defaults_cover_core_groups():
    result = CustomQCSamplePoolService.resolve_sync_table_names()
    assert result["group_ids"] == ["sample_full_domain"]
    assert "mr" in result["table_names"]
    assert "admission_record" in result["table_names"]
    assert "consultation_record" in result["table_names"]
    assert "inpat_bill_item" in result["table_names"]
    assert result["missing_group_ids"] == []


def test_sync_pool_records_aggregates_rows_and_refreshes_running_and_final_bundles(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)

    monkeypatch.setattr(
        service,
        "_list_sync_candidate_items",
        lambda **_: [
            {"id": "item-1", "mr_no": "ZY001", "patient_name": "张三", "department": "普外科", "qc_date": "2026-04-20"},
        ],
    )
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "visit_keys": [("P001", "V001")],
        },
    )
    monkeypatch.setattr(
        service,
        "match_pool_items",
        lambda **_: {
            "pool": {"id": "pool-1", "matched_items": 1, "ready_items": 1},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        },
    )

    monkeypatch.setattr(
        sample_pool_module,
        "list_sync_tables",
        lambda: [
            {"name": "mr", "source_table": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "admission_record", "source_table": "admission_record", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "daily_course_record", "source_table": "daily_course_record", "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"]},
        ],
    )
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(sample_pool_module, "load_db_config", lambda: {"remote_schema": "public"})

    rows_by_table = {
        "mr": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}],
        "admission_record": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}],
        "daily_course_record": [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001", "document_id": "D1"}],
    }
    monkeypatch.setattr(
        sample_pool_module,
        "fetch_remote_rows_by_visit_keys",
        lambda **kwargs: list(rows_by_table.get(kwargs["source_table"], [])),
    )
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))

    ingest_calls = []
    refresh_calls = []
    progress_events = []
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: ingest_calls.append(kwargs))
    monkeypatch.setattr(sample_pool_module, "refresh_scene_bundles_for_rows", lambda **kwargs: refresh_calls.append(kwargs))

    result = service.sync_pool_records(
        pool_id="pool-1",
        only_intrinsic=True,
        include_in_batch_1=True,
        table_groups=["core_8"],
        progress_callback=lambda progress: progress_events.append(progress.copy()),
    )

    assert result["eligible_visits"] == 1
    assert result["matched"] == 1
    assert result["total_rows_pulled"] == 3
    assert result["total_rows_upserted"] == 3
    assert [item["table_name"] for item in result["synced_tables"]] == ["mr", "admission_record", "daily_course_record"]
    assert len(ingest_calls) == 2
    assert len(refresh_calls) == 6
    assert [call["scene"] for call in refresh_calls] == ["running", "final", "running", "final", "running", "final"]
    assert progress_events[0]["step_key"] == "resolving"
    assert progress_events[1]["step_key"] == "resolved"
    assert progress_events[-1]["step_key"] == "matching"


def test_sync_pool_records_skips_optional_source_table_unavailable(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)

    monkeypatch.setattr(
        service,
        "_list_sync_candidate_items",
        lambda **_: [
            {"id": "item-1", "mr_no": "ZY001", "patient_name": "张三", "department": "普外科", "qc_date": "2026-04-20"},
        ],
    )
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "visit_keys": [("P001", "V001")],
        },
    )
    monkeypatch.setattr(
        service,
        "match_pool_items",
        lambda **_: {
            "pool": {"id": "pool-1", "matched_items": 1, "ready_items": 1},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        },
    )

    monkeypatch.setattr(
        sample_pool_module,
        "list_sync_tables",
        lambda: [
            {"name": "mr", "source_table": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {
                "name": "docpat_commu_record",
                "source_table": "docpat_commu_record",
                "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"],
            },
        ],
    )
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(sample_pool_module, "load_db_config", lambda: {"remote_schema": "public"})

    def fake_fetch(**kwargs):
        if kwargs["source_table"] == "docpat_commu_record":
            raise ValueError("docpat_commu_record 缺少 patient_id/visit_id 字段，无法按病例集合抽取")
        return [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}]

    monkeypatch.setattr(sample_pool_module, "fetch_remote_rows_by_visit_keys", fake_fetch)
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: None)
    monkeypatch.setattr(sample_pool_module, "refresh_scene_bundles_for_rows", lambda **kwargs: None)
    monkeypatch.setattr(sample_pool_module, "refresh_domain_bundles_for_rows", lambda **kwargs: None)

    result = service.sync_pool_records(
        pool_id="pool-1",
        only_intrinsic=True,
        include_in_batch_1=True,
        table_groups=["sample_full_domain"],
    )

    assert result["total_rows_pulled"] == 1
    assert result["total_rows_upserted"] == 1
    assert result["synced_tables"][1]["table_name"] == "docpat_commu_record"
    assert result["synced_tables"][1]["sync_status"] == "source_table_unavailable"
    assert result["skipped_optional_tables"][0]["source_table"] == "docpat_commu_record"


def test_sync_pool_records_should_fail_on_optional_table_runtime_error(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)

    monkeypatch.setattr(
        service,
        "_list_sync_candidate_items",
        lambda **_: [
            {"id": "item-1", "mr_no": "ZY001", "patient_name": "张三", "department": "普外科", "qc_date": "2026-04-20"},
        ],
    )
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "visit_keys": [("P001", "V001")],
        },
    )
    monkeypatch.setattr(
        sample_pool_module,
        "list_sync_tables",
        lambda: [
            {"name": "mr", "source_table": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {
                "name": "docpat_commu_record",
                "source_table": "docpat_commu_record",
                "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"],
            },
        ],
    )
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(sample_pool_module, "load_db_config", lambda: {"remote_schema": "public"})

    def fake_fetch(**kwargs):
        if kwargs["source_table"] == "docpat_commu_record":
            raise RuntimeError("permission denied for table docpat_commu_record")
        return [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}]

    monkeypatch.setattr(sample_pool_module, "fetch_remote_rows_by_visit_keys", fake_fetch)
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: None)
    monkeypatch.setattr(sample_pool_module, "refresh_scene_bundles_for_rows", lambda **kwargs: None)

    with pytest.raises(RuntimeError, match="permission denied"):
        service.sync_pool_records(
            pool_id="pool-1",
            only_intrinsic=True,
            include_in_batch_1=True,
            table_groups=["sample_full_domain"],
        )


def test_list_pool_records_groups_multiple_sample_items_into_real_record(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "张三",
            "mr_no": "ZY001",
            "department": "普外科",
            "manual_issue_text": "首次病程记录鉴别诊断不全面",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["SC-026"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        },
        {
            "id": "item-2",
            "pool_id": "pool-1",
            "row_no": 2,
            "patient_name": "张三",
            "mr_no": "ZY001",
            "department": "普外科",
            "manual_issue_text": "病程记录未分析异常检查",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["SC-033"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        },
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(service, "_load_record_display_map", lambda **kwargs: {})

    result = service.list_pool_records(pool_id="pool-1", include_in_batch_1=True)

    assert result.total == 1
    assert len(result.items) == 1
    record = result.items[0]
    assert record["id"] == "V001"
    assert record["issue_count"] == 2
    assert record["sample_item_ids"] == ["item-1", "item-2"]
    assert record["candidate_rule_ids"] == ["SC-026", "SC-033"]
    assert "首次病程记录鉴别诊断不全面" in record["issue_preview_text"]


def test_list_pool_records_should_backfill_patient_name_and_department_from_matched_record(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "nan",
            "mr_no": "147640",
            "department": "nan",
            "manual_issue_text": "",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["SC-023"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_record_display_map",
        lambda **kwargs: {
            "V001": {
                "patient_name": "张三",
                "mr_no": "147640",
                "department": "普外科",
            }
        },
    )

    result = service.list_pool_records(pool_id="pool-1", include_in_batch_1=True)

    assert result.total == 1
    record = result.items[0]
    assert record["patient_name"] == "张三"
    assert record["department"] == "普外科"
    assert record["mr_no"] == "147640"


def test_row_to_item_should_read_visit_id_from_raw_payload():
    service = CustomQCSamplePoolService()

    item = service._row_to_item(
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "mr_no": "",
            "raw_payload_json": '{"visit_id":"VISIT-001"}',
        }
    )

    assert item["visit_id"] == "VISIT-001"


def test_row_to_item_should_fallback_candidate_rules_for_intrinsic_history_rows():
    service = CustomQCSamplePoolService()

    item = service._row_to_item(
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "manual_issue_text": "",
            "coverage_type": "llm_intrinsic",
            "issue_category": "record_list_intrinsic",
            "candidate_rule_ids_json": "not-json-array",
            "raw_payload_json": '{"visit_id":"VISIT-001"}',
        }
    )

    assert item["visit_id"] == "VISIT-001"
    assert item["candidate_rule_ids"] == sample_pool_module._DEFAULT_INTRINSIC_RULE_IDS


def test_derive_dynamic_candidate_rule_ids_from_source_tables_should_cover_operation_and_discharge():
    rule_ids = sample_pool_module._derive_dynamic_candidate_rule_ids_from_source_tables(
        ["discharge_record", "surgery_record", "anesthesia_record"]
    )

    assert "SC-118" in rule_ids
    assert "SC-093" in rule_ids
    assert "SC-114" in rule_ids


def test_document_scope_labels_should_cover_attention_reports():
    labels = sample_pool_module._derive_document_scope_labels_from_source_tables(
        ["lab_attention_report", "exam_attention_report"]
    )

    assert labels == ["检查检验"]


def test_apply_dynamic_candidate_rule_ids_should_replace_default_rules_for_blank_intrinsic_rows(monkeypatch):
    service = CustomQCSamplePoolService()
    items = [
        {
            "id": "item-1",
            "matched_visit_id": "V001",
            "coverage_type": "llm_intrinsic",
            "manual_issue_text": "",
            "candidate_rule_ids": sample_pool_module._DEFAULT_INTRINSIC_RULE_IDS,
        }
    ]
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {
            "V001": {"discharge_record", "surgery_record", "anesthesia_record"},
        },
    )

    enriched = service._apply_dynamic_candidate_rule_ids(items=items)

    assert len(enriched) == 1
    assert "SC-118" in enriched[0]["candidate_rule_ids"]
    assert "SC-093" in enriched[0]["candidate_rule_ids"]
    assert "SC-008" not in enriched[0]["candidate_rule_ids"]


def test_get_runnable_items_should_enrich_candidate_rules_from_bundle(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "",
            "mr_no": "161241",
            "department": "",
            "manual_issue_text": "",
            "coverage_type": "llm_intrinsic",
            "issue_category": "record_list_intrinsic",
            "candidate_rule_ids_json": '["SC-008","SC-023"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {
            "V001": {"surgery_record", "anesthesia_record", "postsurg_firstcourse_record"},
        },
    )

    result = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(result) == 1
    assert "SC-093" in result[0]["candidate_rule_ids"]
    assert "SC-114" in result[0]["candidate_rule_ids"]
    assert "SC-008" not in result[0]["candidate_rule_ids"]


def test_choose_scored_candidate_should_fallback_to_most_recent_candidate():
    candidates = [
        {
            "visit_id": "V001",
            "admission_datetime": "2025-06-15",
            "discharge_datetime": "2025-06-21",
            "update_time": "2025-06-21",
        },
        {
            "visit_id": "V002",
            "admission_datetime": "2025-07-04",
            "discharge_datetime": "2025-07-10",
            "update_time": "2025-07-10",
        },
    ]

    chosen = sample_pool_module._choose_scored_candidate(
        [(0, candidate) for candidate in candidates],
        get_recency_key=lambda candidate: sample_pool_module._candidate_recency_key(
            admission_value=candidate.get("admission_datetime"),
            discharge_value=candidate.get("discharge_datetime"),
            update_value=candidate.get("update_time"),
            visit_id=candidate.get("visit_id"),
        ),
    )

    assert chosen is not None
    assert chosen["visit_id"] == "V002"


def test_pick_best_local_candidate_should_choose_department_and_date_match():
    candidates = [
        SimpleNamespace(
            visit_id="V001",
            name="刘德荣",
            admission_dept_name="疼痛科",
            discharge_dept_name="疼痛科",
            admission_datetime="2025-08-14",
            discharge_datetime="2025-08-19",
            update_time="2025-08-19",
        ),
        SimpleNamespace(
            visit_id="V002",
            name="刘德荣",
            admission_dept_name="关节与运动医学科",
            discharge_dept_name="关节与运动医学科",
            admission_datetime="2026-03-22",
            discharge_datetime="2026-04-07",
            update_time="2026-04-07",
        ),
    ]

    chosen = sample_pool_module._pick_best_local_candidate(
        candidates=candidates,
        patient_name="刘德荣",
        department="关节与运动医学科",
        qc_date_value=sample_pool_module._parse_date("2026-04-01"),
    )

    assert chosen is not None
    assert chosen.visit_id == "V002"


def test_pick_best_remote_candidate_should_fallback_to_latest_when_only_mr_no_available():
    candidates = [
        {
            "visit_id": "2183055",
            "name": "罗享金",
            "admission_dept_name": "心血管内科",
            "discharge_dept_name": "心血管内科",
            "admission_datetime": "2026-01-18",
            "discharge_datetime": "2026-01-25",
            "update_time": "2026-01-25",
        },
        {
            "visit_id": "2306811",
            "name": "罗享金",
            "admission_dept_name": "泌尿血管外科",
            "discharge_dept_name": "泌尿血管外科",
            "admission_datetime": "2026-03-25",
            "discharge_datetime": "2026-04-03",
            "update_time": "2026-04-03",
        },
    ]

    chosen = sample_pool_module._pick_best_remote_candidate(
        candidates=candidates,
        patient_name="罗亨金",
        department="",
        qc_date_value=None,
    )

    assert chosen is not None
    assert chosen["visit_id"] == "2306811"


def test_pick_best_local_candidate_should_choose_latest_when_same_patient_matches_multiple_visits():
    candidates = [
        SimpleNamespace(
            visit_id="V001",
            name="刘德荣",
            admission_dept_name="关节与运动医学科",
            discharge_dept_name="关节与运动医学科",
            admission_datetime="2026-02-01",
            discharge_datetime="2026-02-10",
            update_time="2026-02-10",
        ),
        SimpleNamespace(
            visit_id="V002",
            name="刘德荣",
            admission_dept_name="关节与运动医学科",
            discharge_dept_name="关节与运动医学科",
            admission_datetime="2026-03-22",
            discharge_datetime="2026-04-07",
            update_time="2026-04-07",
        ),
    ]

    chosen = sample_pool_module._pick_best_local_candidate(
        candidates=candidates,
        patient_name="刘德荣",
        department="关节与运动医学科",
        qc_date_value=None,
    )

    assert chosen is not None
    assert chosen.visit_id == "V002"


def test_get_runnable_items_filters_by_selected_record_ids(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "张三",
            "mr_no": "ZY001",
            "department": "普外科",
            "manual_issue_text": "",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["SC-023"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))

    runnable = service.get_runnable_items(
        pool_id="pool-1",
        validation_mode="sc",
        record_ids=["V001"],
    )

    assert len(runnable) == 1
    assert runnable[0]["matched_visit_id"] == "V001"


def test_get_runnable_items_sc_should_whitelist_consultation_execution_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "黄显秀",
            "mr_no": "ZY001",
            "department": "神经内科",
            "manual_issue_text": "遵会诊意见但实际并未按照会诊意见执行。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_execution",
            "candidate_rule_ids_json": '["SC-070","LX-016"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V001",
            "matched_patient_id": "P001",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V001": {"consultation_record", "daily_course_record", "senior_course_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-070"]


def test_get_runnable_items_sc_should_whitelist_senior_round_content_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "付学云",
            "mr_no": "ZY002",
            "department": "肿瘤科",
            "manual_issue_text": "主治医师查房记录无内容。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "senior_round_content",
            "candidate_rule_ids_json": '["SC-049","SC-050","SC-052"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V002",
            "matched_patient_id": "P002",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V002": {"senior_course_record", "admission_record", "discharge_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-050"]


def test_get_runnable_items_sc_should_whitelist_daily_course_analysis_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "范永勤",
            "mr_no": "ZY003",
            "department": "脊柱外科",
            "manual_issue_text": "检验结果异常，病程记录未分析。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "candidate_rule_ids_json": '["SC-032","SC-033","SC-036"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V003",
            "matched_patient_id": "P003",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V003": {"daily_course_record", "lab_attention_report", "consultation_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-036"]


def test_get_runnable_items_sc_should_narrow_sc026_for_first_course_reasoning(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "患者甲",
            "mr_no": "ZY006",
            "department": "妇科",
            "manual_issue_text": "育龄期女性右下腹痛入院，未查HCG，未考虑宫外孕，鉴别诊断考虑欠妥。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "first_course_reasoning",
            "candidate_rule_ids_json": '["SC-023","SC-024","SC-025","SC-026","SC-027"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V006",
            "matched_patient_id": "P006",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V006": {"first_course_record", "admission_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-026"]


def test_get_runnable_items_sc_should_narrow_sc008_for_admission_consistency(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "患者乙",
            "mr_no": "ZY007",
            "department": "创伤外科",
            "manual_issue_text": "主诉仅写车祸伤40+分钟，没有主要症状或体征，无法导出第一诊断。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "admission_consistency",
            "candidate_rule_ids_json": '["SC-008","SC-009","SC-010","SC-011","SC-012","SC-018","SC-019","SC-020"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V007",
            "matched_patient_id": "P007",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V007": {"admission_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)
    assert "recommended_rule_ids" not in runnable[0]
    assert "sub_items" not in runnable[0]


def test_get_runnable_items_sc_should_attach_admission_recommended_rule_ids(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "患者丁",
            "mr_no": "ZY009",
            "department": "普外科",
            "manual_issue_text": "主诉书写不完整，既往史患者用药情况未详细记录，体格检查中无专科检查，入院诊断未体现高血压。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "admission_consistency",
            "candidate_rule_ids_json": '["SC-008","SC-009","SC-010","SC-011","SC-012","SC-018","SC-019","SC-020"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V009",
            "matched_patient_id": "P009",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V009": {"admission_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == list(sample_pool_module.ADMISSION_ISSUE_FAMILY_RULE_IDS)
    assert "primary_rule_id" not in runnable[0]
    assert "recommended_rule_ids" not in runnable[0]


def test_get_runnable_items_sc_should_narrow_sc033_for_daily_course_analysis(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "患者丙",
            "mr_no": "ZY008",
            "department": "普外科",
            "manual_issue_text": "低钾血症持续加重，病程未做诊断也未给出处理措施。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "candidate_rule_ids_json": '["SC-032","SC-033","SC-036"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V008",
            "matched_patient_id": "P008",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V008": {"daily_course_record", "lab_attention_report"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-033"]


def test_get_runnable_items_sc_should_whitelist_consultation_record_quality_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "张某",
            "mr_no": "ZY004",
            "department": "肿瘤科",
            "manual_issue_text": "会诊记录中存在大量复制其他科室会诊意见的情况，并无综合会诊结果提出建设性诊疗意见。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_record_quality",
            "candidate_rule_ids_json": '["SC-069"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V004",
            "matched_patient_id": "P004",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V004": {"consultation_record", "daily_course_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-069"]


def test_get_runnable_items_sc_should_whitelist_critical_value_management_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "李某",
            "mr_no": "ZY005",
            "department": "心内科",
            "manual_issue_text": "危急值处理记录仅描写补钾，未描述危急值报告、处置时间及具体补钾情况。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "critical_value_management",
            "candidate_rule_ids_json": '["SC-039"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V005",
            "matched_patient_id": "P005",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V005": {"daily_course_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-039"]


def test_get_runnable_items_sc_should_whitelist_progress_order_consistency_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "王某",
            "mr_no": "ZY006",
            "department": "普外科",
            "manual_issue_text": "在术前小结及术前讨论之前，已经下达手术医嘱。",
            "coverage_type": "llm_intrinsic",
            "issue_category": "progress_order_consistency",
            "candidate_rule_ids_json": '["SC-146"]',
            "include_in_batch_1": True,
            "matched_visit_id": "V006",
            "matched_patient_id": "P006",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"V006": {"presurg_summary", "presurg_discussion", "daily_course_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-146"]


def test_get_runnable_items_sc_should_whitelist_operation_record_quality_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "蒋齐芬",
            "mr_no": "337281",
            "department": "骨科",
            "manual_issue_text": "手术记录中手术名称与术前讨论及术前小结中手术名称不一致",
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_record_quality",
            "candidate_rule_ids_json": '["SC-097","SC-098"]',
            "include_in_batch_1": True,
            "matched_visit_id": "1888334",
            "matched_patient_id": "P009",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"1888334": {"surgery_record", "presurg_summary", "presurg_discussion"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-097"]


def test_get_runnable_items_sc_should_whitelist_operation_preop_mdt_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "测试患者",
            "mr_no": "1001",
            "department": "外科",
            "manual_issue_text": "四级肿瘤手术，多学科会诊不能代替MDT",
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_mdt",
            "candidate_rule_ids_json": '["SC-083"]',
            "include_in_batch_1": True,
            "matched_visit_id": "287562",
            "matched_patient_id": "P011",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"287562": {"presurg_discussion", "consultation_record"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-083"]


def test_get_runnable_items_sc_should_whitelist_operation_preop_conclusion_primary_rule(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "测试患者",
            "mr_no": "1002",
            "department": "外科",
            "manual_issue_text": "术前讨论记录未明确手术时间及手术医生",
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_conclusion",
            "candidate_rule_ids_json": '["SC-084","SC-085"]',
            "include_in_batch_1": True,
            "matched_visit_id": "371285",
            "matched_patient_id": "P012",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(
        service,
        "_load_bundle_source_table_map",
        lambda **kwargs: {"371285": {"presurg_discussion", "presurg_summary"}},
    )

    runnable = service.get_runnable_items(pool_id="pool-1", validation_mode="sc")

    assert len(runnable) == 1
    assert runnable[0]["candidate_rule_ids"] == ["SC-085"]


def test_get_runnable_items_should_allow_programmatic_without_bundle_ready_or_batch1(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-1",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "张三",
            "mr_no": "ZY001",
            "department": "普外科",
            "manual_issue_text": "三天未记录病程",
            "coverage_type": "programmatic",
            "candidate_rule_ids_json": "[]",
            "include_in_batch_1": False,
            "matched_visit_id": "V009",
            "matched_patient_id": "P009",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "missing",
            "raw_payload_json": "{}",
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))

    runnable = service.get_runnable_items(
        pool_id="pool-1",
        validation_mode="programmatic",
        record_ids=["V009"],
    )

    assert len(runnable) == 1
    assert runnable[0]["coverage_type"] == "programmatic"
