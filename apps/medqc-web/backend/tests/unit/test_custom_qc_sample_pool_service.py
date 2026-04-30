from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services.custom_qc_sample_pool_service import (
    CustomQCSamplePoolService,
    classify_manual_issue_text,
    load_manual_case_rows_from_excel,
)
import pandas as pd
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
    assert result["issue_category"] == "timeliness_or_presence"


def test_classify_daily_course_analysis_issue():
    result = classify_manual_issue_text("4.1异常检查检验结果病程记录未分析和记录")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "daily_course_analysis"
    assert result["candidate_rule_ids"] == ["SC-032", "SC-033", "SC-036"]


def test_daily_course_analysis_should_prefer_sc032_for_brief_change_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="daily_course_analysis",
        manual_issue_text="病程记录过于简略，未描述患者病情变化、目前症状及体征。",
    )

    assert rule_ids == ["SC-032"]


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

    assert rule_ids == ["SC-018"]


def test_resolve_admission_consistency_should_route_sc019():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史中检查项目记录有错误，院外辅助检查记录不完善。",
    )

    assert rule_ids == ["SC-019"]


def test_resolve_admission_consistency_should_route_sc020():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者既往有高血压病史，入院诊断未诊断高血压。",
    )

    assert rule_ids == ["SC-020"]


def test_resolve_admission_consistency_should_prefer_sc020_over_sc018_in_mixed_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者既往有高血压病史，入院诊断未诊断高血压，体格检查无相关描述。",
    )

    assert rule_ids == ["SC-020"]


def test_resolve_admission_consistency_should_route_sc011():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史阴性症状采集不全面，不能支撑鉴别诊断。",
    )

    assert rule_ids == ["SC-011"]


def test_resolve_admission_consistency_should_route_sc012():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史治疗经过不详细，门诊检查项目及结果未记录。",
    )

    assert rule_ids == ["SC-012"]


def test_resolve_admission_consistency_should_prefer_sc012_over_sc020_in_mixed_text():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="患者双膝疼痛10年，现病史治疗经过不详细，不能很好的指导本次住院治疗；患者既往有类风湿关节炎，入院诊断未体现。",
    )

    assert rule_ids == ["SC-012"]


def test_resolve_admission_consistency_should_route_sc009():
    rule_ids = sample_pool_module._resolve_sample_sc_primary_rule_ids(
        issue_category="admission_consistency",
        manual_issue_text="现病史未描述疼痛性质、持续时间、缓解方式等。",
    )

    assert rule_ids == ["SC-009"]


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


def test_resolve_sync_table_names_defaults_cover_core_groups():
    result = CustomQCSamplePoolService.resolve_sync_table_names()
    assert "core_8" in result["group_ids"]
    assert "document_extended" in result["group_ids"]
    assert "mr" in result["table_names"]
    assert "admission_record" in result["table_names"]
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
    assert runnable[0]["candidate_rule_ids"] == ["SC-008"]


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
