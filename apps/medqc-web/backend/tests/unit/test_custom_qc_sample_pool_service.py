from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.core.settings import Settings
from app.database.models.cdm import FirstCourseRecord, TransferInRecord, TransferOutRecord
from app.services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    build_sample_validation_execution_scope_hash,
    classify_manual_issue_text,
    load_manual_case_rows_from_excel,
    summarize_sample_validation_run_readiness,
)
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.case_identity import CaseRef
from app.services.etl_sync import expand_table_groups, list_sync_table_groups, list_sync_tables
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import pytest
import sqlalchemy as sa
import threading
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
        self.last_statement = None

    def execute(self, statement):
        self.last_statement = statement
        return _FakeExecuteResult(self._rows)

    def close(self):
        return None


def test_sample_validation_execution_scope_hash_is_stable_and_non_echoing():
    first = build_sample_validation_execution_scope_hash(
        created_by="operator-raw",
        pool_id="pool-sensitive",
        validation_mode="customer",
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-021", "LX0609-020"],
        record_ids=["visit-secret-2", "visit-secret-1"],
        sample_item_ids=["item-secret-2", "item-secret-1"],
        group_by_luxian_family=True,
        hmac_key="test-only-key",
    )
    reordered = build_sample_validation_execution_scope_hash(
        created_by="operator-raw",
        pool_id="pool-sensitive",
        validation_mode="customer",
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-020", "LX0609-021"],
        record_ids=["visit-secret-1", "visit-secret-2"],
        sample_item_ids=["item-secret-1", "item-secret-2"],
        group_by_luxian_family=True,
        hmac_key="test-only-key",
    )

    assert first == reordered
    assert first != build_sample_validation_execution_scope_hash(
        created_by="operator-raw",
        pool_id="pool-sensitive",
        validation_mode="customer",
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-020", "LX0609-021"],
        record_ids=["visit-secret-1", "visit-secret-2"],
        sample_item_ids=["item-secret-1", "item-secret-2"],
        group_by_luxian_family=True,
        hmac_key="different-test-key",
    )
    assert len(first) == 64
    assert "operator" not in first
    assert "pool-sensitive" not in first
    assert "visit-secret" not in first
    assert "item-secret" not in first


@pytest.mark.parametrize(
    ("patch", "expected_reason"),
    [
        ({"match_status": "unmatched"}, "unmatched"),
        ({"match_status": "ambiguous"}, "ambiguous"),
        ({"sync_status": "pending"}, "not_synced"),
        ({"bundle_status": "building"}, "bundle_not_ready"),
    ],
)
def test_sample_validation_readiness_rejects_any_blocked_selected_item(patch, expected_reason):
    ready_row = {
        "id": "item-ready",
        "matched_visit_id": "visit-ready",
        "match_status": "matched",
        "sync_status": "synced",
        "bundle_status": "ready",
    }
    blocked_row = {
        "id": "item-blocked",
        "matched_visit_id": "visit-blocked",
        "match_status": "matched",
        "sync_status": "synced",
        "bundle_status": "ready",
        **patch,
    }

    result = summarize_sample_validation_run_readiness(
        rows=[ready_row, blocked_row],
        validation_mode="customer",
        item_ids=["item-ready", "item-blocked"],
        record_ids=[],
    )

    assert result["ready"] is False
    assert result["reason_code"] == expected_reason
    assert result["selected_item_count"] == 2
    assert result["blocker_counts"][expected_reason] == 1
    assert "visit-ready" not in repr(result)
    assert "visit-blocked" not in repr(result)


def test_sample_validation_readiness_rejects_item_record_intersection_shrink():
    rows = [
        {
            "id": "item-1",
            "matched_visit_id": "visit-1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
        },
        {
            "id": "item-2",
            "matched_visit_id": "visit-2",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
        },
    ]

    result = summarize_sample_validation_run_readiness(
        rows=rows,
        validation_mode="customer",
        item_ids=["item-1"],
        record_ids=["visit-1", "visit-2"],
    )

    assert result["ready"] is False
    assert result["reason_code"] == "selection_mismatch"
    assert result["blocker_counts"]["selection_mismatch"] == 1


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
    # 041～049、070 以首页输血事件作为正式触发事实；样本全域同步
    # 不得只同步输血文书而遗漏该结构化锚点。
    assert "mr_bloodtrans" in plan["table_names"]
    # 手术知情同意书不能替代通用/麻醉/输血同意书来源；033～035、037、
    # 038、041、042需要独立的 consent_form 物理来源。
    assert "consent_form" in plan["table_names"]
    assert "crisis_value_record" in plan["table_names"]
    assert "docpat_commu_record" in plan["table_names"]
    assert "postane_surveil_record" in plan["table_names"]


def test_sample_full_domain_group_is_available_for_source_coverage_audit():
    group_ids = {item["id"] for item in list_sync_table_groups()}
    table_names, missing = expand_table_groups(["sample_full_domain"])

    assert "sample_full_domain" in group_ids
    assert missing == []
    assert "inpat_registration" in table_names
    assert "admission_record" in table_names
    assert "consultation_record" in table_names
    assert "exam_item_report" in table_names
    assert "labtest_item_report" in table_names
    assert "blood_application" in table_names
    assert "mr_bloodtrans" in table_names
    assert "consent_form" in table_names
    assert "pathology_exam_report" in table_names


def test_sample_full_domain_key_fields_cover_customer_source_tables():
    table_map = {item["name"]: item for item in list_sync_tables()}

    assert table_map["inpat_registration"]["procedure"] == "web.inpat_registration"
    assert table_map["inpat_registration"]["params"] == 1
    assert table_map["inpat_registration"]["key_fields"] == [
        "institute_id",
        "patient_id",
        "visit_id",
    ]
    # 客户源库实测使用 test_id / print_order_id 与 exam_id / item_id；
    # 不得把历史假设的 test_no、item_no、exam_no 当作同步身份。
    assert table_map["labtest_item_report"]["key_fields"] == [
        "patient_id",
        "visit_id",
        "test_id",
        "print_order_id",
    ]
    assert table_map["exam_item_report"]["key_fields"] == [
        "patient_id",
        "visit_id",
        "exam_id",
        "item_id",
    ]
    assert table_map["blood_application"]["key_fields"] == ["patient_id", "visit_id", "application_id"]
    assert table_map["mr_bloodtrans"]["procedure"] == "web.mr_bloodtrans"
    assert table_map["mr_bloodtrans"]["key_fields"] == [
        "patient_id",
        "visit_id",
        "bloodtrans_id",
    ]
    # 本地逻辑表仍名为 consent_form；客户源库实际输血同意书表为
    # bloodtrans_inform_consent，不能回退假设存在同名 web.consent_form。
    assert table_map["consent_form"]["source_table"] == "bloodtrans_inform_consent"
    assert table_map["consent_form"]["procedure"] == "web.bloodtrans_inform_consent"
    assert table_map["consent_form"]["key_fields"] == [
        "patient_id",
        "visit_id",
        "document_id",
    ]


def test_customer_test_record_table_specific_ids_cover_order_and_blood_application():
    service = CustomQCSamplePoolService()

    assert service._test_record_table_specific_ids(
        table_name="inpat_nondrug_order",
        visit_id="CUSTOMER_TEST_001",
        index=3,
    ) == {"order_id": "CUSTOMER_TEST_001-ORDER-003"}
    assert service._test_record_table_specific_ids(
        table_name="blood_application",
        visit_id="CUSTOMER_TEST_001",
        index=4,
    ) == {"application_id": "CUSTOMER_TEST_001-BLOOD-APP-004"}
    assert service._test_record_table_specific_ids(
        table_name="daily_course_record",
        visit_id="CUSTOMER_TEST_001",
        index=5,
    ) == {}


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
            ["住院号", "病案号", "visit_id", "流水号", "存在问题"],
            ["IP0000135258", "362948", "", "", ""],
            ["", "", "VISIT-001", "", "首次病程记录鉴别诊断不全面"],
            ["", "", "", "2431973", "按客户界面流水号导入"],
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: dataframe)

    rows = load_manual_case_rows_from_excel(file_path="demo.xlsx", sheet_name="Sheet2")

    assert len(rows) == 3
    assert rows[0]["inpat_no"] == "IP0000135258"
    assert rows[0]["mr_no"] == "362948"
    assert rows[0]["visit_id"] == ""
    assert rows[1]["mr_no"] == ""
    assert rows[1]["inpat_no"] == ""
    assert rows[1]["visit_id"] == "VISIT-001"
    assert rows[1]["manual_issue_text"] == "首次病程记录鉴别诊断不全面"
    assert rows[2]["mr_no"] == ""
    assert rows[2]["inpat_no"] == ""
    assert rows[2]["visit_id"] == "2431973"
    assert rows[2]["manual_issue_text"] == "按客户界面流水号导入"


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
    assert rows[0]["inpat_no"] == "161241"
    assert rows[0]["mr_no"] == ""
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

    assert [row["inpat_no"] for row in rows] == ["2248248", "161241"]
    assert all(row["mr_no"] == "" for row in rows)
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
    assert rows[0]["inpat_no"] == "2248248"
    assert [call["sheet_name"] for call in calls] == ["Sheet2", 0]


def test_resolve_sync_table_names_defaults_cover_core_groups():
    result = CustomQCSamplePoolService.resolve_sync_table_names()
    assert result["group_ids"] == ["sample_full_domain"]
    assert "mr" in result["table_names"]
    assert "admission_record" in result["table_names"]
    assert "consultation_record" in result["table_names"]
    assert "inpat_bill_item" in result["table_names"]
    assert result["missing_group_ids"] == []


def test_admission_filter_item_should_keep_display_fields_and_matched_identity():
    now = datetime(2026, 7, 29, 8, 0, 0)

    result = sample_pool_module._build_admission_filter_pool_item(
        item_id="item-admission-1",
        pool_id="pool-admission",
        row_no=7,
        source_row={
            "institute_id": "hospital-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
            "patient_name": "测试患者",
            "department": "骨科",
            "mr_no": "MR-001",
            "inpat_no": "IP-001",
            "admission_time": "2026-07-28 08:30:00",
        },
        qc_date=datetime(2026, 7, 28).date(),
        now=now,
    )

    assert result["patient_name"] == "测试患者"
    assert result["department"] == "骨科"
    assert result["matched_institute_id"] == "hospital-1"
    assert result["matched_patient_id"] == "patient-1"
    assert result["matched_visit_id"] == "visit-1"
    payload = sample_pool_module._safe_json_loads(result["raw_payload_json"], {})
    assert payload["patient_name"] == "测试患者"
    assert payload["department"] == "骨科"


def test_admission_filter_should_backfill_running_patient_name_from_patient_index():
    result = sample_pool_module._backfill_admission_source_patient_names(
        source_rows=[
            {
                "institute_id": "hospital-1",
                "patient_id": "patient-1",
                "visit_id": "running-visit-1",
                "patient_name": "",
            },
            {
                "institute_id": "hospital-1",
                "patient_id": "patient-2",
                "visit_id": "final-visit-1",
                "patient_name": "出院患者",
            },
        ],
        demographic_rows=[
            {
                "institute_id": "hospital-1",
                "patient_id": "patient-1",
                "patient_name": "在院患者",
            }
        ],
    )

    assert result[0]["patient_name"] == "在院患者"
    assert result[1]["patient_name"] == "出院患者"


def test_admission_filter_should_repair_existing_blank_display_fields():
    patch = sample_pool_module._build_existing_admission_item_display_patch(
        existing_row={
            "patient_name": "",
            "department": "",
            "mr_no": "",
            "raw_payload_json": '{"visit_id":"running-visit-1"}',
        },
        source_row={
            "institute_id": "hospital-1",
            "patient_id": "patient-1",
            "visit_id": "running-visit-1",
            "patient_name": "在院患者",
            "department": "重症医学科",
            "mr_no": "MR-001",
            "inpat_no": "IP-001",
            "admission_time": "2026-07-30 08:00:00",
        },
    )

    assert patch["patient_name"] == "在院患者"
    assert patch["department"] == "重症医学科"
    assert patch["mr_no"] == "MR-001"
    payload = sample_pool_module._safe_json_loads(patch["raw_payload_json"], {})
    assert payload["patient_name"] == "在院患者"
    assert payload["patient_id"] == "patient-1"


def test_hospitalization_scope_adapter_delegates_to_public_case_scope(monkeypatch):
    captured = {}
    selected = {
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "V1",
        "hospitalization_status": "active",
        "department": "重症医学科（ICU）",
        "department_basis": "current_department",
        "source_table": "inpat_registration",
    }

    class _PublicScopeService:
        def __init__(self, **kwargs):
            captured["dependencies"] = kwargs

        def resolve_hospitalization_scope(self, **kwargs):
            captured["request"] = kwargs
            return HospitalizationScopeResult(
                case_refs=(),
                selected=(selected,),
                all_selected=(selected,),
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    monkeypatch.setattr(sample_pool_module, "CaseScopeService", _PublicScopeService)
    service = CustomQCSamplePoolService()

    result = service._resolve_remote_hospitalization_scope(
        scope_mode="active",
        as_of_date=date(2026, 7, 30),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=["重症医学科（ICU）"],
    )

    assert result["selected"] == [selected]
    assert result["all_selected"] == [selected]
    assert result["sources_used"] == ["inpat_registration"]
    assert captured["request"]["scope_mode"] == "active"
    assert captured["request"]["departments"] == ["重症医学科（ICU）"]
    assert captured["dependencies"]["remote_url_loader"] is (
        sample_pool_module.get_remote_db_url
    )


def test_hospitalization_preview_and_append_preserve_counts_coordinates_and_departments(
    monkeypatch,
):
    db_engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    pool_table = sa.Table(
        "scope_pools",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("updated_at", sa.DateTime),
        *[
            sa.Column(name, sa.Integer, default=0)
            for name in (
                "total_items",
                "llm_intrinsic_items",
                "programmatic_items",
                "unsupported_items",
                "matched_items",
                "ambiguous_items",
                "unmatched_items",
                "ready_items",
            )
        ],
    )
    item_table = sa.Table(
        "scope_pool_items",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("pool_id", sa.String),
        sa.Column("row_no", sa.Integer),
        sa.Column("department", sa.String),
        sa.Column("patient_name", sa.String),
        sa.Column("mr_no", sa.String),
        sa.Column("manual_issue_text", sa.String),
        sa.Column("normalized_issue_text", sa.String),
        sa.Column("doctor_name", sa.String),
        sa.Column("qc_date", sa.Date),
        sa.Column("qc_user", sa.String),
        sa.Column("coverage_type", sa.String),
        sa.Column("issue_category", sa.String),
        sa.Column("expected_scene", sa.String),
        sa.Column("candidate_rule_ids_json", sa.Text),
        sa.Column("include_in_batch_1", sa.Boolean),
        sa.Column("exclude_reason", sa.String),
        sa.Column("matched_institute_id", sa.String),
        sa.Column("matched_patient_id", sa.String),
        sa.Column("matched_visit_id", sa.String),
        sa.Column("match_status", sa.String),
        sa.Column("sync_status", sa.String),
        sa.Column("bundle_status", sa.String),
        sa.Column("latest_job_id", sa.String),
        sa.Column("latest_match_status", sa.String),
        sa.Column("raw_payload_json", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    metadata.create_all(db_engine)
    session_factory = sa.orm.sessionmaker(bind=db_engine)
    monkeypatch.setattr(sample_pool_module, "_session", session_factory)
    service = object.__new__(CustomQCSamplePoolService)
    service._pool_table = pool_table
    service._item_table = item_table
    selected = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "patient_name": "在院患者",
            "mr_no": "MR-1",
            "admission_time": datetime(2026, 7, 1, 8, 0),
            "discharge_time": None,
            "hospitalization_status": "active",
            "department": "重症医学科（ICU）",
            "department_basis": "current_department",
            "source_table": "inpat_registration",
        },
        {
            "institute_id": "H1",
            "patient_id": "P2",
            "visit_id": "V2",
            "patient_name": "出院患者",
            "mr_no": "MR-2",
            "admission_time": None,
            "discharge_time": datetime(2026, 7, 31, 10, 0),
            "hospitalization_status": "discharged",
            "department": "神经外科",
            "department_basis": "discharge_department",
            "source_table": "discharge_record",
        },
    ]
    all_selected = [
        *selected,
        {
            **selected[0],
            "patient_id": "P3",
            "visit_id": "V3",
            "department": "心内科",
        },
    ]
    resolved = {
        "selected": selected,
        "all_selected": all_selected,
        "sources_used": ["inpat_registration", "discharge_record"],
        "source_status": "ready",
        "warnings": [],
    }
    monkeypatch.setattr(
        service,
        "_resolve_remote_hospitalization_scope",
        lambda **_kwargs: resolved,
    )
    with db_engine.begin() as connection:
        connection.execute(pool_table.insert().values(id="pool-1"))
        connection.execute(
            item_table.insert().values(
                id="existing-1",
                pool_id="pool-1",
                row_no=1,
                department="重症医学科（ICU）",
                patient_name="在院患者",
                mr_no="MR-1",
                coverage_type="llm_intrinsic",
                matched_institute_id="H1",
                matched_patient_id="P1",
                matched_visit_id="V1",
                match_status="matched",
                sync_status="pending",
                bundle_status="pending",
                raw_payload_json="{}",
            )
        )

    preview = service.preview_hospitalization_scope(
        pool_id="pool-1",
        scope_mode="active_and_discharged",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=date(2026, 7, 31),
        discharge_end_date=date(2026, 7, 31),
        departments=(),
    )
    appended = service.append_pool_items_by_hospitalization_scope(
        pool_id="pool-1",
        scope_mode="active_and_discharged",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=date(2026, 7, 31),
        discharge_end_date=date(2026, 7, 31),
        departments=(),
    )

    assert preview["counts"] == {
        "active": 1,
        "discharged": 1,
        "deduplicated": 2,
        "existing_in_pool": 1,
        "new_to_pool": 1,
    }
    assert {
        item["name"]: (item["active_count"], item["discharged_count"])
        for item in preview["departments"]
    } == {
        "心内科": (1, 0),
        "神经外科": (0, 1),
        "重症医学科（ICU）": (1, 0),
    }
    assert appended["matched_source_count"] == 2
    assert appended["existing_count"] == 1
    assert appended["new_count"] == 1
    with db_engine.connect() as connection:
        identities = connection.execute(
            sa.select(
                item_table.c.matched_institute_id,
                item_table.c.matched_patient_id,
                item_table.c.matched_visit_id,
            ).order_by(item_table.c.row_no)
        ).all()
    assert identities == [("H1", "P1", "V1"), ("H1", "P2", "V2")]


@pytest.mark.parametrize(
    ("status", "expected_scene"),
    [("active", "running"), ("discharged", "final")],
)
def test_hospitalization_scope_builder_writes_controlled_state_and_scene(
    status,
    expected_scene,
):
    now = datetime(2026, 7, 31, 8, 0)
    item = sample_pool_module._build_hospitalization_scope_pool_item(
        item_id="item-1",
        pool_id="pool-1",
        row_no=1,
        source_row={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "hospitalization_status": status,
            "source_table": "inpat_registration",
            "discharge_time": (
                "2026-07-31 07:00:00" if status == "discharged" else ""
            ),
        },
        qc_date=date(2026, 7, 31),
        now=now,
    )

    payload = sample_pool_module._safe_json_loads(item["raw_payload_json"], {})
    assert item["expected_scene"] == expected_scene
    assert payload["_sample_sync_state"]["hospitalization_status"] == status
    assert "hospitalization_status" not in payload


def test_current_hospitalization_state_requires_registration_for_active_and_prioritizes_discharge():
    states = sample_pool_module._collect_current_hospitalization_states(
        {
            "admission_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "ADMISSION-ONLY",
                    "admission_datetime": "2026-07-30 08:00:00",
                }
            ],
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "discharge_datetime": "2026-07-31 09:00:00",
                }
            ],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "ACTIVE",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "discharge_datetime": None,
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "discharge_datetime": "2026-07-31 10:00:00",
                },
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "discharge_time": "2026-07-31 11:00:00",
                }
            ],
        }
    )

    assert ("H1", "P1", "ADMISSION-ONLY") not in states
    assert states[("H1", "P1", "ACTIVE")]["hospitalization_status"] == "active"
    assert states[("H1", "P2", "V2")]["status_source"] == "discharge_record"
    assert states[("H1", "P2", "V2")]["discharge_time"].startswith(
        "2026-07-31T11:00:00"
    )


def test_trusted_previous_state_ignores_customer_hospitalization_status():
    assert (
        sample_pool_module._trusted_item_hospitalization_state(
            {
                "raw_payload": {
                    "hospitalization_status": "active",
                }
            }
        )
        is None
    )
    trusted = sample_pool_module._trusted_item_hospitalization_state(
        {
            "raw_payload": {
                "_sample_sync_state": {
                    "hospitalization_status": "active",
                    "status_source": "inpat_registration",
                }
            }
        }
    )
    assert trusted["hospitalization_status"] == "active"


def test_resolve_remote_visit_keys_prefers_mr_over_running_anchors(monkeypatch):
    service = CustomQCSamplePoolService()
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        service,
        "_lookup_remote_match_candidates",
        lambda **kwargs: {
            "visit_id": {
                "V001": [
                    {
                        "source_anchor_table": "admission_record",
                        "institute_id": "H1",
                        "patient_id": "P-ADMISSION",
                        "visit_id": "V001",
                    },
                    {
                        "source_anchor_table": "inpat_registration",
                        "institute_id": "H1",
                        "patient_id": "P-REGISTRATION",
                        "visit_id": "V001",
                    },
                    {
                        "source_anchor_table": "mr",
                        "institute_id": "H1",
                        "patient_id": "P-MR",
                        "visit_id": "V001",
                    },
                ]
            },
            "mr_no": {},
            "inpat_no": {},
        },
    )

    result = service._resolve_remote_visit_keys(
        items=[{"visit_id": "V001", "expected_scene": "running"}]
    )

    assert result["matched"] == 1
    assert result["ambiguous"] == 0
    assert result["unmatched"] == 0
    assert result["visit_keys"] == [("P-MR", "V001")]
    assert result["case_refs"] == [
        sample_pool_module.CaseRef("H1", "P-MR", "V001")
    ]


def test_resolve_remote_visit_keys_uses_inpat_registration_without_mr(monkeypatch):
    service = CustomQCSamplePoolService()
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        service,
        "_lookup_remote_match_candidates",
        lambda **kwargs: {
            "visit_id": {
                "V002": [
                    {
                        "source_anchor_table": "inpat_registration",
                        "institute_id": "H1",
                        "patient_id": "P002",
                        "visit_id": "V002",
                    },
                    {
                        "source_anchor_table": "admission_record",
                        "institute_id": "H1",
                        "patient_id": "P-LOWER",
                        "visit_id": "V002",
                    },
                ]
            },
            "mr_no": {},
            "inpat_no": {},
        },
    )

    result = service._resolve_remote_visit_keys(
        items=[{"visit_id": "V002", "expected_scene": "running"}]
    )

    assert result["matched"] == 1
    assert result["visit_keys"] == [("P002", "V002")]


def test_resolve_remote_visit_keys_injects_fixed_institute_for_single_hospital_source(
    monkeypatch,
):
    service = CustomQCSamplePoolService()
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        sample_pool_module,
        "load_db_config",
        lambda: {"remote_schema": "public", "default_institute_id": "LOCAL-HOSPITAL"},
    )
    monkeypatch.setattr(
        service,
        "_lookup_remote_match_candidates",
        lambda **kwargs: {
            "visit_id": {
                "V-NO-INSTITUTE": [
                    {
                        "source_anchor_table": "mr",
                        "patient_id": "P001",
                        "visit_id": "V-NO-INSTITUTE",
                    }
                ]
            },
            "mr_no": {},
            "inpat_no": {},
        },
    )

    result = service._resolve_remote_visit_keys(
        items=[{"visit_id": "V-NO-INSTITUTE", "expected_scene": "running"}]
    )

    assert result["matched"] == 1
    assert result["case_refs"] == [
        sample_pool_module.CaseRef(
            "LOCAL-HOSPITAL", "P001", "V-NO-INSTITUTE"
        )
    ]


def test_resolve_remote_visit_keys_uses_admission_record_and_rejects_incomplete_identity(monkeypatch):
    service = CustomQCSamplePoolService()
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        service,
        "_lookup_remote_match_candidates",
        lambda **kwargs: {
            "visit_id": {
                "V003": [
                    {
                        "source_anchor_table": "admission_record",
                        "institute_id": "H1",
                        "patient_id": "P003",
                        "visit_id": "V003",
                    }
                ],
                "V004": [
                    {
                        "source_anchor_table": "admission_record",
                        "institute_id": "H1",
                        "patient_id": "",
                        "visit_id": "V004",
                    }
                ],
            },
            "mr_no": {},
            "inpat_no": {},
        },
    )

    result = service._resolve_remote_visit_keys(
        items=[
            {"visit_id": "V003", "expected_scene": "running"},
            {"visit_id": "V004", "expected_scene": "running"},
        ]
    )

    assert result["matched"] == 1
    assert result["unmatched"] == 1
    assert result["visit_keys"] == [("P003", "V003")]
    assert result["case_scene_by_ref"] == {
        CaseRef("H1", "P003", "V003"): "running"
    }


@pytest.mark.parametrize(
    ("candidate", "stale_expected_scene", "expected_scene"),
    [
        (
            {
                "source_anchor_table": "inpat_registration",
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "admission_datetime": "2026-08-01 08:00:00",
                "discharge_datetime": None,
            },
            "final",
            "running",
        ),
        (
            {
                "source_anchor_table": "mr",
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "discharge_datetime": "2026-08-10 09:00:00",
            },
            "running",
            "final",
        ),
    ],
)
def test_resolve_remote_visit_keys_prefers_current_controlled_hospitalization_state(
    monkeypatch,
    candidate,
    stale_expected_scene,
    expected_scene,
):
    service = CustomQCSamplePoolService()
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        service,
        "_lookup_remote_match_candidates",
        lambda **_: {
            "visit_id": {"V1": [candidate]},
            "mr_no": {},
            "inpat_no": {},
        },
    )

    result = service._resolve_remote_visit_keys(
        items=[{"visit_id": "V1", "expected_scene": stale_expected_scene}]
    )

    assert result["case_scene_by_ref"] == {
        CaseRef("H1", "P1", "V1"): expected_scene
    }


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
            "case_refs": [("", "P001", "V001")],
            "case_scene_by_ref": {
                CaseRef("LOCAL-HOSPITAL", "P001", "V001"): "running"
            },
        },
    )
    match_calls = []

    def _match_pool_items(**kwargs):
        match_calls.append(dict(kwargs))
        return {
            "pool": {"id": "pool-1", "matched_items": 1, "ready_items": 1},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        }

    monkeypatch.setattr(service, "match_pool_items", _match_pool_items)

    monkeypatch.setattr(
        sample_pool_module,
        "list_sync_tables",
        lambda: [
            {"name": "mr", "source_table": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "admission_record", "source_table": "admission_record", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {"name": "daily_course_record", "source_table": "daily_course_record", "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"]},
            {"name": "procedure_record", "source_table": "procedure_record", "key_fields": ["institute_id", "patient_id", "visit_id", "document_id"]},
        ],
    )
    monkeypatch.setattr(
        service,
        "resolve_sync_table_names",
        lambda **_: {
            "table_names": ["mr", "admission_record", "daily_course_record", "procedure_record"],
            "group_ids": ["core_8"],
            "missing_group_ids": [],
        },
    )
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        sample_pool_module,
        "load_db_config",
        lambda: {
            "remote_schema": "public",
            "default_institute_id": "LOCAL-HOSPITAL",
        },
    )

    rows_by_table = {
        "mr": [],
        "admission_record": [{"patient_id": "P001", "visit_id": "V001"}],
        "daily_course_record": [
            {"patient_id": "P001", "visit_id": "V001", "document_id": "D1"}
        ],
        "procedure_record": [
            {"patient_id": "P001", "visit_id": "V001", "document_id": "P1"}
        ],
    }
    remote_read_calls = []
    local_write_calls = []
    detail_release = threading.Event()
    detail_lock = threading.Lock()
    active_detail_reads = 0
    max_active_detail_reads = 0

    def _fetch_remote_rows(**kwargs):
        nonlocal active_detail_reads, max_active_detail_reads
        remote_read_calls.append(dict(kwargs))
        source_table = kwargs["source_table"]
        if source_table not in {"mr", "admission_record"}:
            assert not match_calls
            with detail_lock:
                active_detail_reads += 1
                max_active_detail_reads = max(max_active_detail_reads, active_detail_reads)
                if active_detail_reads >= 2:
                    detail_release.set()
            detail_release.wait(timeout=0.5)
            with detail_lock:
                active_detail_reads -= 1
        return list(rows_by_table.get(source_table, []))

    def _upsert_local_rows(**kwargs):
        local_write_calls.append(dict(kwargs))
        return len(kwargs["records"])

    monkeypatch.setattr(
        sample_pool_module,
        "fetch_remote_rows_by_case_refs",
        _fetch_remote_rows,
    )
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", _upsert_local_rows)

    ingest_calls = []
    refresh_calls = []
    progress_events = []
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: ingest_calls.append(kwargs))

    def _refresh_all(**kwargs):
        refresh_calls.append(kwargs)
        return {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 4,
            "scenes": {
                "running": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
                "final": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
            },
            "domains": {},
        }

    monkeypatch.setattr(
        sample_pool_module,
        "refresh_all_bundle_variants_for_rows",
        _refresh_all,
    )

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
    assert [item["table_name"] for item in result["synced_tables"]] == [
        "mr",
        "admission_record",
        "daily_course_record",
        "procedure_record",
    ]
    assert len(ingest_calls) == 1
    assert len(refresh_calls) == 1
    assert refresh_calls[0]["scenes"] == ("running", "final")
    assert refresh_calls[0]["policy_version"] == "sample_pool_incremental_sync"
    assert result["bundle_refresh"]["material_reads"] == 4
    assert max_active_detail_reads >= 2
    assert progress_events[0]["step_key"] == "resolving"
    assert progress_events[1]["step_key"] == "resolved"
    assert progress_events[1]["record_progress"] == {
        "total": 1,
        "completed": 0,
        "remaining": 1,
        "missing_mr": 1,
        "missing_primary_record": 1,
        "basis": "primary_record_visible",
        "label": "病历池可见进度",
    }
    assert any(
        int((event.get("record_progress") or {}).get("completed") or 0) == 1
        for event in progress_events
    )
    assert progress_events[-1]["step_key"] == "matching"
    assert progress_events[-1]["record_progress"] == {
        "total": 1,
        "completed": 1,
        "remaining": 0,
        "missing_mr": 0,
        "missing_primary_record": 0,
        "basis": "primary_record_visible",
        "label": "病历池可见进度",
    }
    assert result["record_progress"]["completed"] == 1
    assert result["record_progress"]["total"] == 1
    assert len(remote_read_calls) == 4
    assert all(call["remote_url"] == "postgresql://demo" for call in remote_read_calls)
    assert len(local_write_calls) == 4
    assert all("remote_url" not in call for call in local_write_calls)
    assert all(call["batch_size"] == 500 for call in local_write_calls)
    assert all(
        row["institute_id"] == "LOCAL-HOSPITAL"
        for call in local_write_calls
        for row in call["records"]
    )
    assert refresh_calls[0]["rows"] == [
        {
            "institute_id": "LOCAL-HOSPITAL",
            "patient_id": "P001",
            "visit_id": "V001",
        }
    ]
    assert result["sync_performance"]["detail_table_workers"] == 2
    assert result["sync_performance"]["source_resolve_ms"] >= 0
    assert result["sync_performance"]["primary_visible_ms"] >= 0
    assert result["sync_performance"]["detail_sync_ms"] >= 0
    assert result["sync_performance"]["bundle_refresh_ms"] >= 0
    assert result["sync_performance"]["visits_refreshed"] == 1
    assert result["sync_performance"]["retry_count"] == 0
    assert [call["item_ids"] for call in match_calls] == [["item-1"]]
    detail_progress = [
        event
        for event in progress_events
        if event.get("phase") == "detail_sync"
    ]
    assert detail_progress
    assert all(event["primary_visible"] is True for event in detail_progress)


@pytest.mark.parametrize(
    "candidate_model",
    [
        sample_pool_module.InpatRegistration,
        sample_pool_module.AdmissionRecord,
    ],
)
def test_match_pool_items_falls_back_to_running_primary_records(
    monkeypatch,
    candidate_model,
):
    service = object.__new__(CustomQCSamplePoolService)
    service._item_table = sa.table(
        "sample_pool_items",
        sa.column("id"),
        sa.column("pool_id"),
        sa.column("row_no"),
    )
    source_row = {
        "id": "item-inpatient",
        "raw_payload_json": '{"visit_id":"V-INPATIENT","patient_name":"在院患者"}',
    }
    admission_candidate = SimpleNamespace(
        institute_id="H1",
        patient_id="P1",
        visit_id="V-INPATIENT",
        name="在院患者",
        dept_name="重症医学科（ICU）",
        admission_datetime=datetime(2026, 7, 30, 8, 0, 0),
        discharge_datetime=None,
        update_time=datetime(2026, 7, 30, 9, 0, 0),
    )

    class _Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args):
            return self

        def all(self):
            if self.model is sample_pool_module.MedicalRecordFrontpage:
                return []
            if self.model is candidate_model:
                return [admission_candidate]
            return []

    class _Result:
        def mappings(self):
            return _FakeMappingsResult([source_row])

    class _MatchSession:
        def __init__(self):
            self.update_params = []

        def execute(self, statement):
            if isinstance(statement, sa.sql.Select):
                return _Result()
            self.update_params.append(statement)
            return None

        def query(self, model):
            return _Query(model)

        def commit(self):
            return None

        def close(self):
            return None

    class _Update:
        def where(self, *_args):
            return self

        def values(self, **kwargs):
            self.values_payload = kwargs
            return self

    fake_session = _MatchSession()
    monkeypatch.setattr(sample_pool_module, "_session", lambda: fake_session)
    monkeypatch.setattr(sample_pool_module, "update", lambda *_args: _Update())
    monkeypatch.setattr(service, "_update_pool_counters", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "get_pool", lambda **_: {"id": "pool-1"})
    monkeypatch.setattr(service, "_check_running_bundle_status", lambda **_: "ready")

    result = service.match_pool_items(
        pool_id="pool-1",
        item_ids=["item-inpatient"],
    )

    assert result["matched"] == 1
    assert result["unmatched"] == 0


def test_sync_pool_records_skips_optional_source_table_unavailable(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)
    match_calls = []
    pending_calls = []

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
            "case_refs": [("H1", "P001", "V001")],
            "case_scene_by_ref": {
                CaseRef("H1", "P001", "V001"): "running"
            },
        },
    )
    def _match(**kwargs):
        match_calls.append(dict(kwargs))
        return {
            "pool": {"id": "pool-1", "matched_items": 1, "ready_items": 1},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        }

    monkeypatch.setattr(service, "match_pool_items", _match)
    monkeypatch.setattr(service, "get_pool", lambda **_: {"id": "pool-1"})
    monkeypatch.setattr(
        service,
        "_mark_sync_items_bundle_pending",
        lambda **kwargs: pending_calls.append(dict(kwargs)),
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

    monkeypatch.setattr(sample_pool_module, "fetch_remote_rows_by_case_refs", fake_fetch)
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: None)
    monkeypatch.setattr(
        sample_pool_module,
        "refresh_all_bundle_variants_for_rows",
        lambda **kwargs: {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 0,
            "scenes": {},
            "domains": {},
        },
    )

    result = service.sync_pool_records(
        pool_id="pool-1",
        only_intrinsic=True,
        include_in_batch_1=True,
        table_groups=["sample_full_domain"],
    )

    assert result["total_rows_pulled"] == 1
    assert result["total_rows_upserted"] == 1
    skipped_by_table = {
        item["table_name"]: item
        for item in result["skipped_optional_tables"]
    }
    assert skipped_by_table["docpat_commu_record"]["sync_status"] == (
        "source_table_unavailable"
    )
    assert skipped_by_table["docpat_commu_record"]["source_table"] == (
        "docpat_commu_record"
    )
    assert skipped_by_table["docpat_commu_record"]["skip_reason"] == (
        "该类资料暂未从源系统提供，本次同步已跳过。"
    )
    assert skipped_by_table["docpat_commu_record"]["error_category"] == (
        "source_field_missing"
    )
    assert result["primary_visible"] is True
    assert result["sync_ready"] is False
    assert result["sync_block_reason"] == "details_incomplete"
    assert result["bundle_refresh"] == {}
    assert result["primary_match"] is None
    assert result["post_match"] is None
    assert pending_calls == [{"pool_id": "pool-1", "item_ids": ["item-1"]}]
    assert match_calls == []


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
            "case_refs": [("H1", "P001", "V001")],
            "case_scene_by_ref": {
                CaseRef("H1", "P001", "V001"): "running"
            },
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
    monkeypatch.setattr(
        service,
        "match_pool_items",
        lambda **_: {
            "pool": {"id": "pool-1"},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        },
    )

    def fake_fetch(**kwargs):
        if kwargs["source_table"] == "docpat_commu_record":
            raise RuntimeError("permission denied for table docpat_commu_record")
        return [{"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}]

    monkeypatch.setattr(sample_pool_module, "fetch_remote_rows_by_case_refs", fake_fetch)
    monkeypatch.setattr(sample_pool_module, "upsert_to_local", lambda **kwargs: len(kwargs["records"]))
    monkeypatch.setattr(sample_pool_module, "ingest_sync_rows", lambda **kwargs: None)
    monkeypatch.setattr(
        sample_pool_module,
        "refresh_all_bundle_variants_for_rows",
        lambda **kwargs: {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 0,
            "scenes": {},
            "domains": {},
        },
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        service.sync_pool_records(
            pool_id="pool-1",
            only_intrinsic=True,
            include_in_batch_1=True,
            table_groups=["sample_full_domain"],
        )


def _run_two_stage_primary_sync(
    monkeypatch,
    primary_outcomes,
    capture=None,
    upsert_impl=None,
    table_config_overrides=None,
    item_payload=None,
    item_payloads=None,
    extra_table_names=None,
    refresh_scene_impl=None,
    resolved_visit_keys=None,
    resolved_case_scene_by_ref=None,
):
    service = object.__new__(CustomQCSamplePoolService)
    service._item_table = sa.table(
        "custom_qc_sample_pool_items",
        sa.column("id"),
        sa.column("raw_payload_json"),
        sa.column("expected_scene"),
        sa.column("updated_at"),
    )
    operations = []
    progress_events = []
    match_calls = []
    pending_calls = []
    fetch_calls = []
    bundle_refresh_calls = []
    visit_index_calls = []
    if capture is not None:
        capture.update(
            {
                "operations": operations,
                "progress_events": progress_events,
                "match_calls": match_calls,
                "pending_calls": pending_calls,
                "fetch_calls": fetch_calls,
                "bundle_refresh_calls": bundle_refresh_calls,
                "visit_index_calls": visit_index_calls,
            }
        )
    table_names = [
        "mr",
        "inpat_registration",
        "admission_record",
        "daily_course_record",
        *(extra_table_names or []),
    ]
    table_configs = [
        {
            "name": table_name,
            "source_table": table_name,
            "key_fields": ["institute_id", "patient_id", "visit_id"],
            **dict((table_config_overrides or {}).get(table_name) or {}),
        }
        for table_name in table_names
    ]
    monkeypatch.setattr(
        service,
        "_list_sync_candidate_items",
        lambda **_: list(item_payloads or [dict(item_payload or {
            "id": "item-1",
            "visit_id": "V001",
            "matched_institute_id": "H1",
            "matched_patient_id": "P001",
            "matched_visit_id": "V001",
            "expected_scene": "running",
        })]),
    )
    resolved_pairs = list(resolved_visit_keys or [("P001", "V001")])
    resolved_case_refs = tuple(
        CaseRef("H1", patient_id, visit_id)
        for patient_id, visit_id in resolved_pairs
    )
    resolved_scenes = resolved_case_scene_by_ref or {
        case_ref: "running" for case_ref in resolved_case_refs
    }
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "visit_keys": resolved_pairs,
            "case_refs": resolved_case_refs,
            "case_scene_by_ref": resolved_scenes,
        },
    )
    monkeypatch.setattr(
        service,
        "resolve_sync_table_names",
        lambda **_: {
            "table_names": table_names,
            "group_ids": ["sample_full_domain"],
            "missing_group_ids": [],
        },
    )
    monkeypatch.setattr(sample_pool_module, "list_sync_tables", lambda: table_configs)
    monkeypatch.setattr(sample_pool_module, "get_remote_db_url", lambda: "postgresql://demo")
    monkeypatch.setattr(
        sample_pool_module,
        "load_db_config",
        lambda: {
            "remote_schema": "public",
            "remote_host": "source-db",
            "remote_port": "5432",
            "remote_database": "clinical",
        },
    )

    def _fetch(**kwargs):
        fetch_calls.append(dict(kwargs))
        table_name = kwargs["source_table"]
        operations.append(f"fetch:{table_name}")
        outcome = primary_outcomes.get(table_name)
        if isinstance(outcome, Exception):
            raise outcome
        if table_name in primary_outcomes:
            return list(outcome or [])
        return [
            {
                "institute_id": "H1",
                "patient_id": "P001",
                "visit_id": "V001",
                "document_id": "D1",
            }
        ]

    def _match(**kwargs):
        operations.append("match")
        match_calls.append(dict(kwargs))
        return {
            "pool": {"id": "pool-1"},
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
        }

    monkeypatch.setattr(sample_pool_module, "fetch_remote_rows_by_case_refs", _fetch)
    monkeypatch.setattr(
        sample_pool_module,
        "upsert_to_local",
        upsert_impl or (lambda **kwargs: len(kwargs["records"])),
    )
    monkeypatch.setattr(
        sample_pool_module,
        "ingest_sync_rows",
        lambda **kwargs: visit_index_calls.append(kwargs),
    )
    monkeypatch.setattr(service, "match_pool_items", _match)
    monkeypatch.setattr(
        service,
        "_mark_sync_items_bundle_pending",
        lambda **kwargs: (
            operations.append("bundle:pending"),
            pending_calls.append(dict(kwargs)),
        ),
    )
    monkeypatch.setattr(service, "get_pool", lambda **_: {"id": "pool-1"})
    def _refresh_all(**kwargs):
        operations.append("bundle:all")
        bundle_refresh_calls.append(dict(kwargs))
        return {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 8,
            "scenes": {
                "running": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
                "final": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
            },
            "domains": {},
        }

    monkeypatch.setattr(
        sample_pool_module,
        "refresh_all_bundle_variants_for_rows",
        refresh_scene_impl or _refresh_all,
    )

    result = service.sync_pool_records(
        pool_id="pool-1",
        table_groups=["sample_full_domain"],
        progress_callback=lambda progress: progress_events.append(dict(progress)),
    )
    return result, operations, match_calls, progress_events


def test_sync_pool_records_makes_inpat_registration_only_case_visible_before_details(
    monkeypatch,
):
    primary_row = {
        "institute_id": "H1",
        "patient_id": "P001",
        "visit_id": "V001",
    }
    result, operations, match_calls, progress_events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [primary_row],
            "admission_record": [],
        },
    )

    assert result["primary_visible"] is True
    assert result["primary_progress"]["completed"] == 1
    assert len(match_calls) == 1
    assert all(call["item_ids"] == ["item-1"] for call in match_calls)
    assert operations.index("fetch:daily_course_record") < operations.index("match")
    assert operations.index("fetch:daily_course_record") < operations.index("bundle:all")
    primary_visible_events = [
        event
        for event in progress_events
        if event.get("step_key") == "primary_visible"
    ]
    assert len(primary_visible_events) == 1
    assert primary_visible_events[0]["phase"] == "primary_visible"
    assert primary_visible_events[0]["step_label"] == (
        "病历已进入样本池，文书整理中"
    )
    assert all(
        event["primary_visible"] is True
        for event in progress_events
        if event.get("phase") == "detail_sync"
    )


def test_sync_pool_records_preserves_mixed_running_and_final_visit_index_scenes(
    monkeypatch,
):
    running_ref = CaseRef("H1", "P001", "V001")
    final_ref = CaseRef("H1", "P002", "V002")
    capture = {}
    _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [running_ref.as_dict(), final_ref.as_dict()],
            "inpat_registration": [],
            "admission_record": [],
        },
        capture=capture,
        item_payloads=[
            {
                "id": "item-running",
                "matched_institute_id": "H1",
                "matched_patient_id": "P001",
                "matched_visit_id": "V001",
                "expected_scene": "running",
            },
            {
                "id": "item-final",
                "matched_institute_id": "H1",
                "matched_patient_id": "P002",
                "matched_visit_id": "V002",
                "expected_scene": "final",
            },
        ],
        resolved_visit_keys=[("P001", "V001"), ("P002", "V002")],
        resolved_case_scene_by_ref={running_ref: "running", final_ref: "final"},
    )

    mr_calls = [
        call
        for call in capture["visit_index_calls"]
        if call["table_name"] == "mr"
    ]
    assert [call["sync_scene"] for call in mr_calls] == ["running", "final"]
    assert mr_calls[0]["rows"] == [running_ref.as_dict()]
    assert mr_calls[1]["rows"] == [final_ref.as_dict()]


def test_sync_pool_records_refreshes_changed_visit_once_and_reports_material_reads(
    monkeypatch,
):
    capture = {}
    result, operations, _match_calls, _events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                }
            ],
            "admission_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                }
            ],
            "daily_course_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "document_id": "D1",
                }
            ],
        },
        capture=capture,
    )

    assert operations.count("bundle:all") == 1
    assert len(capture["bundle_refresh_calls"]) == 1
    refresh_call = capture["bundle_refresh_calls"][0]
    assert refresh_call["rows"] == [
        {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}
    ]
    assert refresh_call["scenes"] == ("running", "final")
    assert refresh_call["policy_version"] == "sample_pool_incremental_sync"
    assert result["bundle_refresh"]["material_reads"] == 8


def test_sync_pool_records_passes_only_changed_visits_to_bundle_refresh(
    monkeypatch,
):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")
    rows_by_table = {
        "mr": [],
        "inpat_registration": [
            {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"},
            {"institute_id": "H1", "patient_id": "P002", "visit_id": "V002"},
        ],
        "admission_record": [
            {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"},
            {"institute_id": "H1", "patient_id": "P002", "visit_id": "V002"},
        ],
        "daily_course_record": [
            {
                "institute_id": "H1",
                "patient_id": "P001",
                "visit_id": "V001",
                "document_id": "D1",
            },
            {
                "institute_id": "H1",
                "patient_id": "P002",
                "visit_id": "V002",
                "document_id": "D2",
            },
        ],
    }
    unchanged_signatures = {
        table_name: sample_pool_module.build_sample_sync_content_signature(
            [
                row
                for row in rows
                if row.get("patient_id") == "P002" and row.get("visit_id") == "V002"
            ]
        )
        for table_name, rows in rows_by_table.items()
    }

    class _LocalSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, *, source_identity, visit_keys, table_names):
            table_name = table_names[0]
            return {
                sample_pool_module.CursorKey(
                    source_identity,
                    "H1",
                    "P002",
                    "V002",
                    table_name,
                ): SimpleNamespace(
                    content_signature=unchanged_signatures[table_name],
                    watermark_value=None,
                )
            }

        def mark_full_sync(self, **_kwargs):
            return None

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module,
        "SampleSyncCursorRepository",
        _Repository,
    )
    capture = {}
    result, _operations, _match_calls, _events = _run_two_stage_primary_sync(
        monkeypatch,
        rows_by_table,
        capture=capture,
        item_payloads=[
            {
                "id": "item-1",
                "matched_institute_id": "H1",
                "matched_patient_id": "P001",
                "matched_visit_id": "V001",
            },
            {
                "id": "item-2",
                "matched_institute_id": "H1",
                "matched_patient_id": "P002",
                "matched_visit_id": "V002",
            },
        ],
        resolved_visit_keys=[("P001", "V001"), ("P002", "V002")],
    )

    assert result["bundle_refresh"]["processed"] == 2
    assert capture["bundle_refresh_calls"][0]["rows"] == [
        {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"},
        {"institute_id": "H1", "patient_id": "P002", "visit_id": "V002"},
    ]


@pytest.mark.parametrize(
    ("previous_status", "expected_reconciliation_count"),
    [("active", 1), ("discharged", 0), ("", 0)],
)
def test_sync_pool_records_reconciles_only_explicit_active_to_discharged_transition(
    monkeypatch,
    previous_status,
    expected_reconciliation_count,
):
    captured_persist = []
    monkeypatch.setattr(
        sample_pool_module,
        "_persist_hospitalization_sync_states",
        lambda **kwargs: captured_persist.append(kwargs),
    )
    system_state = (
        {
            "_sample_sync_state": {
                "hospitalization_status": previous_status,
                "status_source": "inpat_registration",
            }
        }
        if previous_status
        else {}
    )
    capture = {}
    result, operations, _match_calls, _events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "discharge_datetime": "2026-07-31 09:00:00",
                }
            ],
            "admission_record": [],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "discharge_time": "2026-07-31 10:00:00",
                }
            ],
            "daily_course_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "document_id": "D1",
                    "update_time": datetime(2026, 7, 31, 10, 1),
                }
            ],
        },
        capture=capture,
        extra_table_names=["discharge_record"],
        table_config_overrides={
            "daily_course_record": {
                "incremental_strategy": "updated_at",
                "watermark_columns": ["update_time"],
            },
            "discharge_record": {
                "incremental_strategy": "updated_at",
                "watermark_columns": ["update_time"],
            },
        },
        item_payload={
            "id": "item-1",
            "matched_institute_id": "H1",
            "matched_patient_id": "P001",
            "matched_visit_id": "V001",
            "raw_payload": system_state,
        },
    )

    assert result["final_reconciliation_count"] == expected_reconciliation_count
    assert result["final_reconciliation"] is bool(expected_reconciliation_count)
    assert result["hard_delete_reconciliation"] == "not_supported"
    assert operations.count("fetch:discharge_record") == 1
    assert operations.index("fetch:discharge_record") < operations.index("bundle:all")
    assert operations.index("fetch:daily_course_record") < operations.index("bundle:all")
    discharge_fetch = next(
        call
        for call in capture["fetch_calls"]
        if call["source_table"] == "discharge_record"
    )
    assert "watermark_column" not in discharge_fetch
    assert captured_persist
    assert len(captured_persist[0]["transition_identities"]) == (
        expected_reconciliation_count
    )


def test_sync_pool_records_does_not_complete_transition_when_bundle_refresh_fails(
    monkeypatch,
):
    persisted = []
    monkeypatch.setattr(
        sample_pool_module,
        "_persist_hospitalization_sync_states",
        lambda **kwargs: persisted.append(kwargs),
    )
    with pytest.raises(RuntimeError, match="bundle failed"):
        _run_two_stage_primary_sync(
            monkeypatch,
            {
                "mr": [],
                "inpat_registration": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                        "admission_datetime": "2026-07-30 08:00:00",
                        "discharge_datetime": "2026-07-31 09:00:00",
                    }
                ],
                "admission_record": [],
                "discharge_record": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                        "discharge_time": "2026-07-31 10:00:00",
                    }
                ],
            },
            extra_table_names=["discharge_record"],
            refresh_scene_impl=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("bundle failed")
            ),
            item_payload={
                "id": "item-1",
                "matched_institute_id": "H1",
                "matched_patient_id": "P001",
                "matched_visit_id": "V001",
                "raw_payload": {
                    "_sample_sync_state": {
                        "hospitalization_status": "active",
                        "status_source": "inpat_registration",
                    }
                },
            },
        )

    assert persisted == []


def test_sync_pool_records_does_not_persist_transition_when_any_bundle_refresh_reports_failure(
    monkeypatch,
):
    persisted = []
    monkeypatch.setattr(
        sample_pool_module,
        "_persist_hospitalization_sync_states",
        lambda **kwargs: persisted.append(kwargs),
    )

    def _refresh_with_domain_failure(**kwargs):
        return {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 12,
            "scenes": {
                "running": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
                "final": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
            },
            "domains": {
                "medical_document": {
                    "processed": 1,
                    "updated": 0,
                    "failed": 1,
                    "skipped": 0,
                }
            },
        }

    with pytest.raises(RuntimeError, match="Bundle统一刷新失败"):
        _run_two_stage_primary_sync(
            monkeypatch,
            {
                "mr": [],
                "inpat_registration": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                        "admission_datetime": "2026-07-30 08:00:00",
                        "discharge_datetime": "2026-07-31 09:00:00",
                    }
                ],
                "admission_record": [],
                "discharge_record": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                        "discharge_time": "2026-07-31 10:00:00",
                    }
                ],
            },
            extra_table_names=["discharge_record"],
            refresh_scene_impl=_refresh_with_domain_failure,
            item_payload={
                "id": "item-1",
                "matched_institute_id": "H1",
                "matched_patient_id": "P001",
                "matched_visit_id": "V001",
                "raw_payload": {
                    "_sample_sync_state": {
                        "hospitalization_status": "active",
                        "status_source": "inpat_registration",
                    }
                },
            },
        )

    assert persisted == []


def test_sync_pool_records_reports_nontransition_bundle_failure_fail_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        sample_pool_module,
        "_persist_hospitalization_sync_states",
        lambda **_kwargs: None,
    )

    def _refresh_with_final_failure(**kwargs):
        return {
            "processed": len(kwargs["rows"]),
            "skipped": 0,
            "material_reads": 6,
            "scenes": {
                "running": {"processed": 1, "updated": 1, "failed": 0, "skipped": 0},
                "final": {"processed": 1, "updated": 0, "failed": 1, "skipped": 0},
            },
            "domains": {},
        }

    with pytest.raises(RuntimeError, match="Bundle统一刷新失败"):
        _run_two_stage_primary_sync(
            monkeypatch,
            {
                "mr": [],
                "inpat_registration": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                        "admission_datetime": "2026-07-30 08:00:00",
                        "discharge_datetime": None,
                    }
                ],
                "admission_record": [],
            },
            refresh_scene_impl=_refresh_with_final_failure,
        )


def test_transition_visit_fetches_full_while_other_visit_keeps_watermark(
    monkeypatch,
):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")

    class _LocalSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, *, source_identity, visit_keys, table_names):
            table_name = table_names[0]
            if table_name != "daily_course_record":
                return {}
            return {
                sample_pool_module.CursorKey(
                    source_identity, "H1", "P002", "V002", table_name
                ): SimpleNamespace(
                    content_signature=None,
                    watermark_value=datetime(2026, 7, 31, 8, 0),
                )
            }

        def mark_full_sync(self, **_kwargs):
            return None

        def mark_success(self, **_kwargs):
            return None

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module, "SampleSyncCursorRepository", _Repository
    )
    monkeypatch.setattr(
        sample_pool_module,
        "_persist_hospitalization_sync_states",
        lambda **_kwargs: None,
    )
    capture = {}
    _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "discharge_datetime": "2026-07-31 09:00:00",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P002",
                    "visit_id": "V002",
                    "admission_datetime": "2026-07-30 08:00:00",
                    "discharge_datetime": None,
                },
            ],
            "admission_record": [],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "discharge_time": "2026-07-31 10:00:00",
                }
            ],
            "daily_course_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "document_id": "D1",
                    "update_time": datetime(2026, 7, 31, 8, 1),
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P002",
                    "visit_id": "V002",
                    "document_id": "D2",
                    "update_time": datetime(2026, 7, 31, 8, 2),
                },
            ],
        },
        capture=capture,
        extra_table_names=["discharge_record"],
        table_config_overrides={
            "daily_course_record": {
                "incremental_strategy": "updated_at",
                "watermark_columns": ["update_time"],
            }
        },
        item_payloads=[
            {
                "id": "item-1",
                "matched_institute_id": "H1",
                "matched_patient_id": "P001",
                "matched_visit_id": "V001",
                "raw_payload": {
                    "_sample_sync_state": {
                        "hospitalization_status": "active",
                        "status_source": "inpat_registration",
                    }
                },
            },
            {
                "id": "item-2",
                "matched_institute_id": "H1",
                "matched_patient_id": "P002",
                "matched_visit_id": "V002",
                "raw_payload": {
                    "_sample_sync_state": {
                        "hospitalization_status": "active",
                        "status_source": "inpat_registration",
                    }
                },
            },
        ],
        resolved_visit_keys=[("P001", "V001"), ("P002", "V002")],
    )

    detail_fetches = [
        call
        for call in capture["fetch_calls"]
        if call["source_table"] == "daily_course_record"
    ]
    assert len(detail_fetches) == 1
    assert detail_fetches[0]["case_refs"] == [
        sample_pool_module.CaseRef("H1", "P001", "V001"),
        sample_pool_module.CaseRef("H1", "P002", "V002"),
    ]
    assert "watermark_column" not in detail_fetches[0]


def test_sync_pool_records_degrades_missing_primary_relation_to_admission_record(
    monkeypatch,
):
    primary_row = {
        "institute_id": "H1",
        "patient_id": "P001",
        "visit_id": "V001",
    }
    result, operations, match_calls, _progress_events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": RuntimeError('relation "public.mr" does not exist'),
            "inpat_registration": [],
            "admission_record": [primary_row],
        },
    )

    assert result["primary_visible"] is True
    assert result["skipped_optional_tables"][0]["table_name"] == "mr"
    assert result["skipped_optional_tables"][0]["sync_status"] == "source_table_unavailable"
    assert result["sync_ready"] is True
    assert result["sync_block_reason"] == ""
    assert len(match_calls) == 1
    assert operations.index("fetch:daily_course_record") < operations.index("bundle:all")
    assert operations.index("bundle:all") < operations.index("match")


def test_sync_pool_records_stops_before_details_when_all_primary_records_unavailable(
    monkeypatch,
):
    unavailable = RuntimeError("relation does not exist")
    capture = {}
    with pytest.raises(RuntimeError, match="源系统未提供可用"):
        _run_two_stage_primary_sync(
            monkeypatch,
            {
                "mr": unavailable,
                "inpat_registration": unavailable,
                "admission_record": unavailable,
            },
            capture=capture,
        )

    assert capture["match_calls"] == []
    assert "fetch:daily_course_record" not in capture["operations"]
    assert not any(
        operation.startswith("bundle:")
        for operation in capture["operations"]
    )


def test_sync_pool_records_returns_missing_primary_when_sources_are_available_but_empty(
    monkeypatch,
):
    result, operations, match_calls, progress_events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [],
            "admission_record": [],
        },
    )

    assert result["primary_visible"] is False
    assert result["record_progress"]["missing_primary_record"] == 1
    assert match_calls == []
    assert "fetch:daily_course_record" not in operations
    assert not any(operation.startswith("bundle:") for operation in operations)
    assert progress_events[-1]["step_key"] == "primary_unavailable"


def test_sample_sync_content_signature_is_order_stable_and_content_sensitive():
    first = [
        {"b": 2, "a": 1, "payload": b"\x01"},
        {"a": 3, "b": datetime(2026, 7, 31, 8, 0)},
    ]
    reordered = [
        {"b": datetime(2026, 7, 31, 8, 0), "a": 3},
        {"payload": b"\x01", "a": 1, "b": 2},
    ]
    changed = [
        {"b": 2, "a": 1, "payload": b"\x01"},
        {"a": 4, "b": datetime(2026, 7, 31, 8, 0)},
    ]

    assert sample_pool_module.build_sample_sync_content_signature(
        first
    ) == sample_pool_module.build_sample_sync_content_signature(reordered)
    assert sample_pool_module.build_sample_sync_content_signature(
        first
    ) != sample_pool_module.build_sample_sync_content_signature(changed)


def test_sync_watermark_normalizes_naive_and_aware_values_to_utc():
    naive = datetime(2026, 7, 31, 8, 0)
    aware = datetime(2026, 7, 31, 16, 0, tzinfo=timezone(timedelta(hours=8)))

    assert sample_pool_module._coerce_sync_watermark(naive) == datetime(
        2026, 7, 31, 8, 0, tzinfo=timezone.utc
    )
    assert sample_pool_module._coerce_sync_watermark(aware) == datetime(
        2026, 7, 31, 8, 0, tzinfo=timezone.utc
    )
    assert sample_pool_module.build_sample_sync_content_signature(
        [{"time": naive}]
    ) == sample_pool_module.build_sample_sync_content_signature(
        [{"time": aware}]
    )


def test_public_case_set_sync_reloads_requested_cases_and_refreshes_bundles(
    monkeypatch,
):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")
    rows_by_table = {
        "mr": [],
        "inpat_registration": [
            {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}
        ],
        "admission_record": [],
        "daily_course_record": [
            {
                "institute_id": "H1",
                "patient_id": "P001",
                "visit_id": "V001",
                "document_id": "D1",
            }
        ],
    }
    signatures = {
        table_name: sample_pool_module.build_sample_sync_content_signature(rows)
        for table_name, rows in rows_by_table.items()
    }

    class _LocalSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, *, source_identity, visit_keys, table_names):
            table_name = table_names[0]
            return {
                sample_pool_module.CursorKey(
                    source_identity, "H1", "P001", "V001", table_name
                ): SimpleNamespace(
                    content_signature=signatures[table_name],
                    watermark_value=None,
                )
            }

        def mark_full_sync(self, **_kwargs):
            return None

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module, "SampleSyncCursorRepository", _Repository
    )
    upsert_records = []
    capture = {}
    result, operations, _match_calls, _events = _run_two_stage_primary_sync(
        monkeypatch,
        rows_by_table,
        capture=capture,
        upsert_impl=lambda **kwargs: upsert_records.append(
            list(kwargs["records"])
        )
        or 0,
    )

    assert result["primary_visible"] is True
    assert any(records for records in upsert_records)
    assert operations.count("bundle:all") == 1
    assert result["sync_performance"]["tables_skipped_unchanged"] == 0
    assert result["sync_performance"]["visits_refreshed"] == 1


def test_public_case_set_sync_does_not_advance_sample_cursor_when_upsert_fails(monkeypatch):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")
    sessions = []
    marks = []

    class _LocalSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            sessions.append(self)

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, **_kwargs):
            return {}

        def mark_full_sync(self, **kwargs):
            marks.append(kwargs)

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module, "SampleSyncCursorRepository", _Repository
    )
    with pytest.raises(RuntimeError, match="local upsert failed"):
        _run_two_stage_primary_sync(
            monkeypatch,
            {
                "mr": [],
                "inpat_registration": [
                    {
                        "institute_id": "H1",
                        "patient_id": "P001",
                        "visit_id": "V001",
                    }
                ],
                "admission_record": [],
            },
            upsert_impl=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("local upsert failed")
            ),
        )

    assert marks == []
    assert all(session.commits == 0 for session in sessions)
    assert all(session.rollbacks == 0 for session in sessions)


def test_public_case_set_sync_uses_exact_case_set_without_watermark_projection(monkeypatch):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")
    watermark = datetime(2026, 7, 31, 8, 0)

    class _LocalSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, *, source_identity, visit_keys, table_names):
            table_name = table_names[0]
            if table_name != "daily_course_record":
                return {}
            return {
                sample_pool_module.CursorKey(
                    source_identity, "H1", "P001", "V001", table_name
                ): SimpleNamespace(
                    content_signature=None,
                    watermark_value=watermark,
                )
            }

        def mark_full_sync(self, **_kwargs):
            return None

        def mark_success(self, **_kwargs):
            return None

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module, "SampleSyncCursorRepository", _Repository
    )
    capture = {}
    _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}
            ],
            "admission_record": [],
            "daily_course_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "document_id": "D1",
                    "update_time": datetime(2026, 7, 31, 8, 1),
                }
            ],
        },
        capture=capture,
        table_config_overrides={
            "daily_course_record": {
                "incremental_strategy": "updated_at",
                "watermark_columns": ["update_time"],
            }
        },
        item_payload={
            "id": "item-1",
            "visit_id": "V001",
            "matched_institute_id": "H1",
            "matched_patient_id": "P001",
            "matched_visit_id": "V001",
        },
    )

    detail_fetch = next(
        call
        for call in capture["fetch_calls"]
        if call["source_table"] == "daily_course_record"
    )
    assert detail_fetch["case_refs"] == [
        sample_pool_module.CaseRef("H1", "P001", "V001")
    ]
    assert "watermark_column" not in detail_fetch
    assert "watermark_after" not in detail_fetch


def test_incremental_updated_at_first_run_fetches_full_visit(monkeypatch):
    monkeypatch.setenv("SAMPLE_SYNC_INCREMENTAL_ENABLED", "true")

    class _LocalSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Repository:
        def __init__(self, _session):
            pass

        def get_many(self, **_kwargs):
            return {}

        def mark_full_sync(self, **_kwargs):
            return None

        def mark_success(self, **_kwargs):
            return None

    monkeypatch.setattr(sample_pool_module, "_session", _LocalSession)
    monkeypatch.setattr(
        sample_pool_module, "SampleSyncCursorRepository", _Repository
    )
    capture = {}
    _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {"institute_id": "H1", "patient_id": "P001", "visit_id": "V001"}
            ],
            "admission_record": [],
            "daily_course_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                    "document_id": "D1",
                    "update_time": datetime(2026, 7, 31, 8, 1),
                }
            ],
        },
        capture=capture,
        table_config_overrides={
            "daily_course_record": {
                "incremental_strategy": "updated_at",
                "watermark_columns": ["update_time"],
            }
        },
    )

    detail_fetch = next(
        call
        for call in capture["fetch_calls"]
        if call["source_table"] == "daily_course_record"
    )
    assert "watermark_column" not in detail_fetch
    assert "watermark_after" not in detail_fetch


def test_sample_sync_settings_enforce_safe_bounds():
    settings = Settings(
        _env_file=None,
        JWT_SECRET="test-secret",
        SAMPLE_SYNC_DETAIL_TABLE_WORKERS=6,
        SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX=4,
        SAMPLE_SYNC_UPSERT_BATCH_SIZE=50,
        SAMPLE_SYNC_WATERMARK_OVERLAP_MINUTES=0,
    )
    assert settings.SAMPLE_SYNC_DETAIL_TABLE_WORKERS == 6
    assert settings.SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX == 4
    assert settings.SAMPLE_SYNC_UPSERT_BATCH_SIZE == 50
    assert settings.SAMPLE_SYNC_WATERMARK_OVERLAP_MINUTES == 0

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            JWT_SECRET="test-secret",
            SAMPLE_SYNC_DETAIL_TABLE_WORKERS=7,
        )
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            JWT_SECRET="test-secret",
            SAMPLE_SYNC_UPSERT_BATCH_SIZE=49,
        )


def test_sync_pool_records_uses_runtime_worker_and_batch_limits(monkeypatch):
    monkeypatch.setattr(
        sample_pool_module,
        "get_settings",
        lambda: SimpleNamespace(
            SAMPLE_SYNC_INCREMENTAL_ENABLED=False,
            SAMPLE_SYNC_DETAIL_TABLE_WORKERS=6,
            SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX=2,
            SAMPLE_SYNC_UPSERT_BATCH_SIZE=100,
            SAMPLE_SYNC_WATERMARK_OVERLAP_MINUTES=7,
        ),
    )
    upsert_calls = []
    result, _operations, _match_calls, _events = _run_two_stage_primary_sync(
        monkeypatch,
        {
            "mr": [],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P001",
                    "visit_id": "V001",
                }
            ],
            "admission_record": [],
        },
        upsert_impl=lambda **kwargs: upsert_calls.append(dict(kwargs))
        or len(kwargs["records"]),
    )

    assert result["sync_performance"]["detail_table_workers"] == 1
    assert upsert_calls
    assert all(call["batch_size"] == 100 for call in upsert_calls)


def test_create_sync_job_rejects_same_pool_until_active_job_finishes(monkeypatch):
    db_engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sync_jobs = sa.Table(
        "custom_qc_sample_pool_sync_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("summary_json", sa.Text, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    metadata.create_all(db_engine)
    session_factory = sa.orm.sessionmaker(bind=db_engine)
    monkeypatch.setattr(sample_pool_module, "_session", session_factory)
    service = object.__new__(CustomQCSamplePoolService)
    service._sync_job_table = sync_jobs

    first = service.create_sync_job(
        pool_id="pool-1",
        created_by="tester",
        payload={},
    )
    with pytest.raises(
        sample_pool_module.SampleSyncJobConflictError,
        match="已有同步任务",
    ):
        service.create_sync_job(
            pool_id="pool-1",
            created_by="tester",
            payload={},
        )

    other_pool = service.create_sync_job(
        pool_id="pool-2",
        created_by="tester",
        payload={},
    )
    assert other_pool["pool_id"] == "pool-2"

    with db_engine.begin() as connection:
        connection.execute(
            sync_jobs.update()
            .where(sync_jobs.c.id == first["id"])
            .values(status="completed")
        )
    next_job = service.create_sync_job(
        pool_id="pool-1",
        created_by="tester",
        payload={},
    )
    assert next_job["id"] != first["id"]


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
            "raw_payload_json": (
                '{"_sample_sync_state":{"hospitalization_status":"active",'
                '"status_source":"inpat_registration"}}'
            ),
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
            "raw_payload_json": (
                '{"admission_time":"2026-07-01T09:15:00+00:00",'
                '"_sample_sync_state":{"hospitalization_status":"discharged",'
                '"status_source":"discharge_record",'
                '"discharge_time":"2026-07-30T15:20:00+00:00"}}'
            ),
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
    assert record["hospitalization_status"] == "discharged"
    assert record["admission_time"] == "2026-07-01T09:15:00+00:00"
    assert record["discharge_time"] == "2026-07-30T15:20:00+00:00"
    assert "首次病程记录鉴别诊断不全面" in record["issue_preview_text"]


def test_list_pool_records_should_resolve_legacy_hospitalization_state(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-legacy",
            "pool_id": "pool-1",
            "row_no": 1,
            "patient_name": "冯丽平",
            "mr_no": "208790",
            "department": "重症医学科（ICU）",
            "manual_issue_text": "",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": "[]",
            "include_in_batch_1": True,
            "matched_visit_id": "2496813",
            "matched_patient_id": "0000225510",
            "matched_institute_id": "泸县人民医院",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": '{"visit_id":"2496813"}',
        }
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(service, "_load_record_display_map", lambda **kwargs: {})
    monkeypatch.setattr(
        sample_pool_module,
        "_load_previous_hospitalization_states",
        lambda _items: {
            ("泸县人民医院", "0000225510", "2496813"): {
                "hospitalization_status": "discharged",
                "discharge_time": "2026-07-13T18:22:50",
                "status_source": "legacy_local",
            }
        },
    )

    result = service.list_pool_records(pool_id="pool-1", include_in_batch_1=True)

    assert result.items[0]["hospitalization_status"] == "discharged"
    assert result.items[0]["discharge_time"] == "2026-07-13T18:22:50"


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
            ("H1", "P001", "V001"): {
                "patient_name": "张三",
                "patient_sex": "女",
                "patient_age": "67",
                "mr_no": "147640",
                "department": "普外科",
            }
        },
    )

    result = service.list_pool_records(pool_id="pool-1", include_in_batch_1=True)

    assert result.total == 1
    record = result.items[0]
    assert record["patient_name"] == "张三"
    assert record["patient_sex"] == "女"
    assert record["patient_age"] == "67"
    assert record["department"] == "普外科"
    assert record["mr_no"] == "147640"


def test_record_display_map_should_fallback_to_running_registration_when_frontpage_is_blank():
    service = CustomQCSamplePoolService()
    session = _FakeSession(
        [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "RUNNING-001",
                "source_priority": 0,
                "patient_name": "",
                "patient_sex": "",
                "patient_age": "",
                "mr_no": "",
                "department": "",
            },
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "RUNNING-001",
                "source_priority": 1,
                "patient_name": "在院患者",
                "patient_sex": "女",
                "patient_age": "68",
                "mr_no": "ZY-RUNNING-001",
                "department": "呼吸与危重症医学科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "RUNNING-001",
                "source_priority": 2,
                "patient_name": "入院记录患者",
                "patient_sex": "女",
                "patient_age": "68",
                "mr_no": "ZY-ADMISSION-001",
                "department": "普通内科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P2",
                "visit_id": "RUNNING-002",
                "source_priority": 2,
                "patient_name": "仅入院记录患者",
                "patient_sex": "男",
                "patient_age": "57",
                "mr_no": "ZY-ADMISSION-002",
                "department": "消化内科",
            },
        ]
    )

    display_map = service._load_record_display_map(
        session=session,
        case_keys=[("H1", "P1", "RUNNING-001"), ("H1", "P2", "RUNNING-002")],
    )

    assert display_map[("H1", "P1", "RUNNING-001")] == {
        "patient_name": "在院患者",
        "patient_sex": "女",
        "patient_age": "68",
        "mr_no": "ZY-RUNNING-001",
        "department": "呼吸与危重症医学科",
    }
    assert display_map[("H1", "P2", "RUNNING-002")] == {
        "patient_name": "仅入院记录患者",
        "patient_sex": "男",
        "patient_age": "57",
        "mr_no": "ZY-ADMISSION-002",
        "department": "消化内科",
    }
    assert "discharge_dept_name" not in str(session.last_statement)


def test_list_customer_test_pool_records_orders_newest_first(monkeypatch):
    service = CustomQCSamplePoolService()
    rows = [
        {
            "id": "item-old",
            "pool_id": sample_pool_module.CUSTOMER_TEST_POOL_ID,
            "row_no": 1718600000,
            "patient_name": "陈某某",
            "mr_no": "CUSTOMER_TEST_OLD",
            "department": "消化内科",
            "manual_issue_text": "旧会诊测试病历",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["LX0609-020"]',
            "include_in_batch_1": True,
            "matched_visit_id": "CUSTOMER_TEST_OLD",
            "matched_patient_id": "P-OLD",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": '{"case_title":"会诊质量质控病历｜LX020｜0617-0900"}',
            "created_at": datetime(2026, 6, 17, 9, 0, 0),
            "updated_at": datetime(2026, 6, 17, 9, 0, 0),
        },
        {
            "id": "item-new",
            "pool_id": sample_pool_module.CUSTOMER_TEST_POOL_ID,
            "row_no": 1718700000,
            "patient_name": "王某某",
            "mr_no": "CUSTOMER_TEST_NEW",
            "department": "普通外科",
            "manual_issue_text": "新手术测试病历",
            "coverage_type": "llm_intrinsic",
            "candidate_rule_ids_json": '["LX0609-003"]',
            "include_in_batch_1": True,
            "matched_visit_id": "CUSTOMER_TEST_NEW",
            "matched_patient_id": "P-NEW",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "ready",
            "raw_payload_json": '{"case_title":"手术麻醉质控病历｜LX003｜0618-1015"}',
            "created_at": datetime(2026, 6, 18, 10, 15, 0),
            "updated_at": datetime(2026, 6, 18, 10, 15, 0),
        },
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))
    monkeypatch.setattr(service, "_load_record_display_map", lambda **kwargs: {})

    result = service.list_pool_records(
        pool_id=sample_pool_module.CUSTOMER_TEST_POOL_ID,
        include_in_batch_1=True,
    )

    assert [item["matched_visit_id"] for item in result.items] == [
        "CUSTOMER_TEST_NEW",
        "CUSTOMER_TEST_OLD",
    ]
    assert result.items[0]["sample_items"][0]["raw_payload"]["case_title"] == "手术麻醉质控病历｜LX003｜0618-1015"


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
            "matched_institute_id": "H1",
            "matched_patient_id": "P001",
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
            ("H1", "P001", "V001"): {"discharge_record", "surgery_record", "anesthesia_record"},
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
            ("H1", "P001", "V001"): {"surgery_record", "anesthesia_record", "postsurg_firstcourse_record"},
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
        lambda **kwargs: {("H1", "P001", "V001"): {"consultation_record", "daily_course_record", "senior_course_record"}},
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
        lambda **kwargs: {("H1", "P002", "V002"): {"senior_course_record", "admission_record", "discharge_record"}},
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
        lambda **kwargs: {("H1", "P003", "V003"): {"daily_course_record", "lab_attention_report", "consultation_record"}},
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
        lambda **kwargs: {("H1", "P006", "V006"): {"first_course_record", "admission_record"}},
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
        lambda **kwargs: {("H1", "P007", "V007"): {"admission_record"}},
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
        lambda **kwargs: {("H1", "P009", "V009"): {"admission_record"}},
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
        lambda **kwargs: {("H1", "P008", "V008"): {"daily_course_record", "lab_attention_report"}},
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
        lambda **kwargs: {("H1", "P004", "V004"): {"consultation_record", "daily_course_record"}},
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
        lambda **kwargs: {("H1", "P005", "V005"): {"daily_course_record"}},
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
        lambda **kwargs: {("H1", "P006", "V006"): {"presurg_summary", "presurg_discussion", "daily_course_record"}},
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
        lambda **kwargs: {("H1", "P009", "1888334"): {"surgery_record", "presurg_summary", "presurg_discussion"}},
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
        lambda **kwargs: {("H1", "P011", "287562"): {"presurg_discussion", "consultation_record"}},
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
        lambda **kwargs: {("H1", "P012", "371285"): {"presurg_discussion", "presurg_summary"}},
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


def test_get_runnable_items_should_allow_formal_fast_screen_without_bundle_ready_or_batch1(monkeypatch):
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
            "candidate_rule_ids_json": '["SC-023"]',
            "include_in_batch_1": False,
            "matched_visit_id": "V010",
            "matched_patient_id": "P010",
            "matched_institute_id": "H1",
            "match_status": "matched",
            "sync_status": "synced",
            "bundle_status": "missing",
            "raw_payload_json": "{}",
        },
    ]
    monkeypatch.setattr(sample_pool_module, "_session", lambda: _FakeSession(rows))

    runnable = service.get_runnable_items(
        pool_id="pool-1",
        validation_mode="formal_fast_screen_full",
        record_ids=["V010"],
    )

    assert len(runnable) == 1
    assert runnable[0]["matched_visit_id"] == "V010"
    assert runnable[0]["bundle_status"] == "missing"


def _deletion_test_service(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    pool_table = sa.Table(
        "sample_pools",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String),
        sa.Column("latest_job_id", sa.String),
        sa.Column("latest_job_status", sa.String),
    )
    item_table = sa.Table(
        "sample_pool_items",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("pool_id", sa.String),
    )
    sync_job_table = sa.Table(
        "sample_pool_sync_jobs",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("pool_id", sa.String),
        sa.Column("status", sa.String),
    )
    batch_job_status_table = sa.Table(
        "batch_job_status",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("status", sa.String),
        sa.Column("created_by", sa.String),
    )
    metadata.create_all(engine)
    session_factory = sa.orm.sessionmaker(bind=engine)
    monkeypatch.setattr(sample_pool_module, "_session", session_factory)
    service = object.__new__(CustomQCSamplePoolService)
    service._pool_table = pool_table
    service._item_table = item_table
    service._sync_job_table = sync_job_table
    service._batch_job_status_table = batch_job_status_table
    return (
        service,
        session_factory,
        pool_table,
        item_table,
        sync_job_table,
        batch_job_status_table,
    )


@pytest.mark.parametrize(
    ("pool_rows", "expected"),
    [
        ([], None),
        (
            [{"id": "pool-1", "latest_job_id": "job-1"}],
            ("pool-1", "admin-001"),
        ),
        (
            [
                {"id": "pool-1", "latest_job_id": "job-1"},
                {"id": "pool-2", "latest_job_id": "job-1"},
            ],
            None,
        ),
    ],
    ids=["not-shared-latest", "unique-shared-latest", "duplicate-pool-pointer"],
)
def test_resolve_unique_pool_id_for_latest_job_fails_closed(
    monkeypatch,
    pool_rows,
    expected,
):
    service, session_factory, pool_table, _item_table, _sync_job_table, batch_job_table = (
        _deletion_test_service(monkeypatch)
    )
    session = session_factory()
    if pool_rows:
        session.execute(pool_table.insert(), pool_rows)
    session.execute(
        batch_job_table.insert().values(
            id="job-1",
            status="completed",
            created_by="admin-001",
        )
    )
    session.commit()
    session.close()

    assert service.resolve_unique_pool_id_for_latest_job(job_id="job-1") == expected


def test_delete_pool_removes_only_pool_owned_rows(monkeypatch):
    service, session_factory, pool_table, item_table, sync_job_table, _batch_job_table = (
        _deletion_test_service(monkeypatch)
    )
    session = session_factory()
    session.execute(
        pool_table.insert(),
        [
            {"id": "pool-delete", "name": "待删除池", "latest_job_status": "completed"},
            {"id": "pool-keep", "name": "保留池", "latest_job_status": "completed"},
        ],
    )
    session.execute(
        item_table.insert(),
        [
            {"id": "item-delete", "pool_id": "pool-delete"},
            {"id": "item-keep", "pool_id": "pool-keep"},
        ],
    )
    session.execute(
        sync_job_table.insert(),
        [
            {"id": "sync-delete", "pool_id": "pool-delete", "status": "completed"},
            {"id": "sync-keep", "pool_id": "pool-keep", "status": "completed"},
        ],
    )
    session.commit()
    session.close()

    result = service.delete_pool(pool_id="pool-delete")

    assert result == {
        "deleted": True,
        "reason": "deleted",
        "pool_id": "pool-delete",
        "pool_name": "待删除池",
        "deleted_item_count": 1,
        "deleted_sync_job_count": 1,
    }
    session = session_factory()
    assert session.execute(sa.select(pool_table.c.id)).scalars().all() == ["pool-keep"]
    assert session.execute(sa.select(item_table.c.id)).scalars().all() == ["item-keep"]
    assert session.execute(sa.select(sync_job_table.c.id)).scalars().all() == ["sync-keep"]
    session.close()


def test_get_pool_uses_actual_batch_job_status_instead_of_stale_cached_status(
    monkeypatch,
):
    (
        service,
        session_factory,
        pool_table,
        _item_table,
        _sync_job_table,
        batch_job_table,
    ) = _deletion_test_service(monkeypatch)
    session = session_factory()
    session.execute(
        pool_table.insert().values(
            id="pool-finished",
            name="已完成池",
            latest_job_id="job-finished",
            latest_job_status="queued",
        )
    )
    session.execute(
        batch_job_table.insert().values(
            id="job-finished",
            status="completed",
        )
    )
    session.commit()
    session.close()

    pool = service.get_pool(pool_id="pool-finished")

    assert pool is not None
    assert pool["latest_job_status"] == "completed"


@pytest.mark.parametrize(
    ("pool_id", "job_status", "sync_status", "reason"),
    [
        (sample_pool_module.CUSTOMER_TEST_POOL_ID, "completed", "completed", "protected_pool"),
        ("pool-active-qc", "running", "completed", "active_qc_job"),
        ("pool-active-sync", "completed", "queued", "active_sync_job"),
    ],
)
def test_delete_pool_blocks_protected_or_active_pool(
    monkeypatch,
    pool_id,
    job_status,
    sync_status,
    reason,
):
    service, session_factory, pool_table, _item_table, sync_job_table, batch_job_table = (
        _deletion_test_service(monkeypatch)
    )
    session = session_factory()
    session.execute(
        pool_table.insert().values(
            id=pool_id,
            name="不可删除池",
            latest_job_status=job_status,
        )
    )
    session.execute(
        sync_job_table.insert().values(
            id=f"sync-{pool_id}",
            pool_id=pool_id,
            status=sync_status,
        )
    )
    if job_status in {"queued", "running", "cancel_requested"}:
        session.execute(
            batch_job_table.insert().values(
                id=f"job-{pool_id}",
                status=job_status,
            )
        )
        session.execute(
            pool_table.update()
            .where(pool_table.c.id == pool_id)
            .values(
                latest_job_id=f"job-{pool_id}",
                latest_job_status=job_status,
            )
        )
    session.commit()
    session.close()

    result = service.delete_pool(pool_id=pool_id)

    assert result == {"deleted": False, "reason": reason}


@pytest.mark.parametrize("old_time", ["", "2026-01-01 00:00:00"])
@pytest.mark.parametrize("registration_case,registration_time", [
    (("H1", "P1", "V1"), datetime(2026, 2, 2, 10)),
    (("H2", "P1", "V1"), datetime(2026, 2, 2, 10)),
    (("H1", "P2", "V1"), datetime(2026, 2, 2, 10)),
    (("H1", "P1", "V1"), None),
])
def test_list_pool_records_reads_current_registration_admission_time(
    monkeypatch, old_time, registration_case, registration_time
):
    import json
    service = CustomQCSamplePoolService()
    row = {
        "id": "item-1", "pool_id": "pool-1", "row_no": 1,
        "mr_no": "test", "patient_name": "测试", "department": "测试科",
        "matched_institute_id": "H1", "matched_patient_id": "P1",
        "matched_visit_id": "V1", "match_status": "matched",
        "sync_status": "synced", "bundle_status": "ready",
        "raw_payload_json": json.dumps({"admission_time": old_time,
            "_sample_sync_state": {"hospitalization_status": "active",
                                   "status_source": "inpat_registration"}}),
    }
    class RegistrationSession(_FakeSession):
        def execute(self, statement):
            if "inpat_registration" in str(statement):
                return _FakeExecuteResult([{
                    "institute_id": registration_case[0], "patient_id": registration_case[1],
                    "visit_id": registration_case[2], "admission_datetime": registration_time,
                }])
            return super().execute(statement)
    monkeypatch.setattr(sample_pool_module, "_session", lambda: RegistrationSession([row]))
    monkeypatch.setattr(service, "_load_record_display_map", lambda **kwargs: {})
    monkeypatch.setattr(service, "_load_patient_display_map", lambda **kwargs: {})
    monkeypatch.setattr(service, "_load_bundle_source_table_map", lambda **kwargs: {})
    result = service.list_pool_records(pool_id="pool-1")
    expected = ("2026-02-02 10:00:00"
                if registration_case == ("H1", "P1", "V1") and registration_time else old_time)
    assert result.items[0]["admission_time"] == expected
