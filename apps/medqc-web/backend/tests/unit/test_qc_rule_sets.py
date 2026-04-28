from app.services.qc_rule_sets import (
    SC_CONTENT_FULL_V1_RULE_IDS,
    SC_CONTENT_LAUNCH_A_V1_RULE_IDS,
    SC_CONTENT_LAUNCH_B_V1_RULE_IDS,
    SC_CONTENT_LAUNCH_C_V1_RULE_IDS,
    SC_CONTENT_V1_RULE_IDS,
    get_sichuan_rule_set,
    list_sichuan_rule_sets,
)
from app.services.sichuan_qc_service import SichuanQCService
from app.services.rule_domain_router import route_rule_to_domain
from app.services.rule_domain_router import RuleExecutionInput


def test_sc_content_v1_rule_set_should_be_fixed_first_batch():
    rule_set = get_sichuan_rule_set("sc_content_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控首批 v1"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "effect_priority_v1"
    assert rule_set.bucket_strategy == "domain_family"
    assert rule_set.enable_selective_refine is True
    assert rule_set.refine_confidence_threshold == 0.75
    assert rule_set.batch_output_mode == "minimal"
    assert rule_set.max_refine_candidates == 3
    assert list(rule_set.rule_ids) == [
        "SC-023",
        "SC-024",
        "SC-025",
        "SC-026",
        "SC-027",
        "SC-032",
        "SC-033",
        "SC-036",
        "SC-121",
        "SC-122",
        "SC-123",
        "SC-125",
    ]


def test_split_launch_rule_sets_should_match_latest_p1a_decision():
    hard_rule_set = get_sichuan_rule_set("sc_content_hard_v1")
    review_rule_set = get_sichuan_rule_set("sc_content_review_v1")
    full_rule_set = get_sichuan_rule_set("sc_content_v1")

    assert hard_rule_set is not None
    assert review_rule_set is not None
    assert full_rule_set is not None

    assert hard_rule_set.name == "内涵质控硬判定首发 v1"
    assert hard_rule_set.enable_selective_refine is True
    assert hard_rule_set.max_refine_candidates == 2
    assert list(hard_rule_set.rule_ids) == [
        "SC-033",
        "SC-121",
        "SC-123",
    ]

    assert review_rule_set.name == "内涵质控待复核首发 v1"
    assert review_rule_set.enable_selective_refine is False
    assert review_rule_set.max_refine_candidates == 0
    assert list(review_rule_set.rule_ids) == [
        "SC-023",
        "SC-024",
        "SC-025",
        "SC-026",
        "SC-027",
        "SC-032",
        "SC-036",
        "SC-122",
        "SC-125",
    ]

    assert set(hard_rule_set.rule_ids).isdisjoint(set(review_rule_set.rule_ids))
    assert set(hard_rule_set.rule_ids) | set(review_rule_set.rule_ids) == set(full_rule_set.rule_ids)


def test_sc_content_v1_rules_should_exist_in_sichuan_rule_source():
    rule_set = get_sichuan_rule_set("sc_content_v1")
    assert rule_set is not None

    service = SichuanQCService()
    missing = [rule_id for rule_id in rule_set.rule_ids if not service.get_rule_by_id(rule_id)]

    assert missing == []


def test_sc_036_should_use_stricter_abnormal_exam_analysis_prompt():
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id("SC-036")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert "仅罗列检查结果" in prompt
    assert "较前好转" in prompt
    assert "炎症指标好转" in prompt
    assert "默认视为分析不足" in prompt


def test_sc_039_should_use_text_only_critical_value_prompt():
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id("SC-039")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert "只根据病历文本本身判断危急值记录是否完整合规" in prompt
    assert "不依赖危急值数据表、阈值表、LIS" in prompt
    assert "结构化标记" in prompt
    assert "接电脑危急值" in prompt
    assert "接到危急值后未查看患者情况" in prompt
    assert "confidence_requirement" not in prompt


def test_sc_039_should_prefer_daily_course_candidate_with_low_potassium_context():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-039")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    routing = route_rule_to_domain(rule)
    rule_input = service._build_rule_execution_input_from_bundle(
        rule=rule,
        routing=routing,
        domain_bundle={
            "execution_domain": "course",
            "timeline_facts": [],
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "display_time": "2025-09-06 21:58:58",
                    "content": "查房内容：患者病情平稳，继续给予患者对症支持治疗，观察患者病情变化。",
                },
                {
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "display_time": "2025-09-21 09:54:42",
                    "content": (
                        "查房内容：患者心慌不适。辅助检查：2025-09-18 电解质:Ca 1.65mmol/l,"
                        "Mg 0.59mmol/l,K 2.12mmol/l。诊疗计划：注意动态复查电解质，静脉补钾。"
                    ),
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "上级查房记录",
                    "display_time": "2025-09-18 10:27:00",
                    "content": "上级医师提示患者严重低钾血症，予以加强静脉补钾。",
                },
            ],
        },
    )

    assert "K 2.12mmol/l" in rule_input.primary_medical_text
    assert "静脉补钾" in rule_input.primary_medical_text


def test_sc_039_should_fallback_to_non_compliant_when_llm_returns_empty_on_low_potassium_text():
    service = SichuanQCService()
    normalized = service._apply_sc039_text_only_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-039",
            document_type="日常病程记录",
            execution_domain="course",
            primary_medical_text=(
                "辅助检查：K 2.12mmol/l。诊疗计划：注意动态复查电解质，静脉补钾。"
            ),
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-039",
            "status": "uncertain",
            "is_compliant": True,
            "findings": "LLM 未返回任何内容。",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.7,
            "metadata": {
                "executor_type": "llm",
                "llm_fallback": False,
            },
        },
    )

    assert normalized["status"] == "non_compliant"
    assert normalized["is_compliant"] is False
    assert "危急值/电解质异常处置语境" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc039_text_only"


def test_sc_069_should_fallback_to_non_compliant_when_signature_is_missing():
    service = SichuanQCService()
    normalized = service._apply_sc069_text_only_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-069",
            document_type="会诊记录",
            execution_domain="consult_discussion",
            primary_medical_text=(
                "肿瘤科,患者贫血原因待查,故请贵科会诊协助诊治,李庆梅医生:2026-04-06,"
                "建议进一步完善贫血三项。 医生签名:"
            ),
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-069",
            "status": "uncertain",
            "is_compliant": True,
            "findings": "LLM 未返回任何内容。",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.7,
            "metadata": {
                "executor_type": "llm",
                "llm_fallback": False,
            },
        },
    )

    assert normalized["status"] == "non_compliant"
    assert normalized["is_compliant"] is False
    assert "缺少会诊医师签名" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc069_text_only"


def test_sc_146_should_prefer_senior_course_note_over_discharge_daily_note():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-146")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    routing = route_rule_to_domain(rule)
    rule_input = service._build_rule_execution_input_from_bundle(
        rule=rule,
        routing=routing,
        domain_bundle={
            "execution_domain": "course",
            "timeline_facts": [],
            "source_documents": [
                {
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "display_time": "2026-02-07 08:27:00",
                    "content": "出院情况：患者病情平稳。出院医嘱：门诊复查。",
                    "source_table": "daily_course_record",
                    "document_id": "daily-1",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "partial",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "上级查房记录",
                    "display_time": "2026-02-05 08:20:35",
                    "content": "诊疗计划：完善相关辅查，明日行左眼下睑睑内翻矫正术。",
                    "source_table": "senior_course_record",
                    "document_id": "senior-1",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "inpat_nondrug_order",
                    "document_title": "临时医嘱",
                    "display_time": "2026-02-06 13:29:25",
                    "content": "order_type: 手术\norder_name: 睑内翻矫正术",
                    "source_table": "inpat_nondrug_order",
                    "document_id": "order-1",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
            ],
        },
    )

    assert "明日行左眼下睑睑内翻矫正术" in rule_input.primary_medical_text
    assert any(item.get("source_table") == "inpat_nondrug_order" for item in rule_input.supporting_evidence)


def test_sc_146_should_fallback_to_uncertain_when_visible_order_time_is_after_preop_note():
    service = SichuanQCService()
    normalized = service._apply_sc146_temporal_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-146",
            document_type="上级查房记录",
            execution_domain="course",
            primary_medical_text="出院情况：患者病情平稳。出院医嘱：门诊复查。",
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[
                {
                    "source_table": "inpat_nondrug_order",
                    "document_title": "睑内翻矫正术",
                    "display_time": "2026-02-06 13:29:25",
                    "content": "order_type: 手术\norder_name: 睑内翻矫正术",
                }
            ],
        ),
        engine_result={
            "rule_id": "SC-146",
            "status": "uncertain",
            "is_compliant": True,
            "findings": "LLM 未返回任何内容。",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.7,
            "metadata": {
                "executor_type": "llm",
                "llm_fallback": False,
            },
        },
        surgery_bundle={
            "source_documents": [
                {
                    "source_table": "presurg_discussion",
                    "document_title": "术前讨论记录",
                    "display_time": "2026-02-05 18:14:15",
                    "content": "讨论时间: 2026-02-05 18:14:15",
                }
            ]
        },
    )

    assert normalized["status"] == "uncertain"
    assert "晚于术前文书" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc146_temporal_order_after_preop"


def test_sc_146_should_fallback_to_non_compliant_when_order_is_before_preop_note():
    service = SichuanQCService()
    normalized = service._apply_sc146_temporal_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-146",
            document_type="上级查房记录",
            execution_domain="course",
            primary_medical_text="诊疗计划：明日行手术。",
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[
                {
                    "source_table": "inpat_nondrug_order",
                    "document_title": "睑内翻矫正术",
                    "display_time": "2026-02-05 08:00:00",
                    "content": "order_type: 手术\norder_name: 睑内翻矫正术",
                }
            ],
        ),
        engine_result={
            "rule_id": "SC-146",
            "status": "uncertain",
            "is_compliant": True,
            "findings": "LLM 未返回任何内容。",
            "evidence": "",
            "suggestion": "",
            "confidence": 0.7,
            "metadata": {
                "executor_type": "llm",
                "llm_fallback": False,
            },
        },
        surgery_bundle={
            "source_documents": [
                {
                    "source_table": "presurg_summary",
                    "document_title": "术前小结",
                    "display_time": "2026-02-05 18:43:34",
                    "content": "术前小结正文",
                }
            ]
        },
    )

    assert normalized["status"] == "non_compliant"
    assert normalized["is_compliant"] is False
    assert "手术相关医嘱时间早于术前文书" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc146_temporal_order_before_preop"


def test_rule_set_list_should_expose_new_launch_rule_sets():
    items = list_sichuan_rule_sets()
    keys = {item["rule_set_key"] for item in items}

    assert "sc_content_launch_a_v1" in keys
    assert "sc_content_launch_b_v1" in keys
    assert "sc_content_launch_c_v1" in keys
    assert "sc_content_fast_v1" in keys
    assert "sc_content_full_v1" in keys
    assert "sc_content_hard_v1" in keys
    assert "sc_content_review_v1" in keys
    assert "sc_content_v1" in keys


def test_sc_content_fast_v1_should_use_fast_screen_strategy():
    rule_set = get_sichuan_rule_set("sc_content_fast_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控快速初筛 v1"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert list(rule_set.rule_ids) == list(SC_CONTENT_V1_RULE_IDS)


def test_sc_content_full_v1_should_cover_all_intrinsic_rules_with_fast_screen():
    rule_set = get_sichuan_rule_set("sc_content_full_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控全量 v1"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert list(rule_set.rule_ids) == list(SC_CONTENT_FULL_V1_RULE_IDS)
    assert len(rule_set.rule_ids) == 84


def test_sc_content_launch_a_v1_should_cover_default_enabled_rules():
    rule_set = get_sichuan_rule_set("sc_content_launch_a_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控默认启用首发 v1"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert list(rule_set.rule_ids) == list(SC_CONTENT_LAUNCH_A_V1_RULE_IDS)
    assert len(rule_set.rule_ids) == 37


def test_sc_content_launch_b_v1_should_cover_gray_release_rules():
    rule_set = get_sichuan_rule_set("sc_content_launch_b_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控灰度观察 v1"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert list(rule_set.rule_ids) == list(SC_CONTENT_LAUNCH_B_V1_RULE_IDS)
    assert len(rule_set.rule_ids) == 38


def test_sc_content_launch_c_v1_should_cover_observation_rules():
    rule_set = get_sichuan_rule_set("sc_content_launch_c_v1")

    assert rule_set is not None
    assert rule_set.name == "内涵质控重点观察 v1"
    assert rule_set.execution_strategy == "fast_screen"
    assert rule_set.scope == "final"
    assert rule_set.quality_profile == "throughput_v1"
    assert rule_set.bucket_strategy == "fixed_packs"
    assert rule_set.enable_selective_refine is False
    assert rule_set.max_refine_candidates == 0
    assert list(rule_set.rule_ids) == list(SC_CONTENT_LAUNCH_C_V1_RULE_IDS)
    assert len(rule_set.rule_ids) == 9
