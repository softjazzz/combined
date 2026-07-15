import json
from pathlib import Path

import pytest

import app.services.sichuan_qc_service as sichuan_qc_service_module
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


def test_luxian_0609_rule_set_should_persist_exact_customer_ids():
    rule_set = get_sichuan_rule_set("luxian_0609_qc_v1")

    assert rule_set is not None
    assert tuple(rule_set.rule_ids) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 50)
    )
    assert all(rule_id.startswith("LX0609-") for rule_id in rule_set.rule_ids)


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


def test_sc_032_should_use_stricter_daily_course_change_prompt():
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id("SC-032")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert "病程记录无具体内容" in prompt
    assert "病程过于简单/过于简略" in prompt
    assert "症状、体征、病情演变" in prompt
    assert "{medical_text}" in prompt
    assert "只返回单个 JSON 对象" in prompt


@pytest.mark.parametrize(
    ("rule_id", "expected_phrase"),
    [
        ("SC-011", "阴性/阳性症状"),
        ("SC-012", "诊治经过记录不全"),
        ("SC-019", "辅助检查记录不完善"),
    ],
)
def test_sc_011_sc_012_sc_019_should_use_runtime_override_prompts(rule_id: str, expected_phrase: str):
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id(rule_id)

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert expected_phrase in prompt
    assert "{medical_text}" in prompt
    assert "只返回单个 JSON 对象" in prompt


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


def test_sc_081_should_use_stricter_presurg_summary_prompt():
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id("SC-081")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert "术前小结记录不完整或内容不当" in prompt
    assert "{medical_text}" in prompt
    assert "手术要点" in prompt
    assert "空泛表述" in prompt


def test_sc_105_should_use_stricter_postsurg_firstcourse_prompt():
    service = SichuanQCService()

    raw_rule = service.get_rule_by_id("SC-105")

    assert raw_rule is not None
    rule = service._ensure_rule_execution_meta(raw_rule)
    prompt = str(rule.get("custom_prompt") or "")
    assert "术后首次病程记录书写不完整或不规范" in prompt
    assert "{medical_text}" in prompt
    assert "术后处理措施" in prompt
    assert "向家属告知手术情况" in prompt


def test_sc_084_sc_085_should_align_with_presurg_discussion():
    service = SichuanQCService()

    for rule_id in ("SC-084", "SC-085"):
        raw_rule = service.get_rule_by_id(rule_id)
        assert raw_rule is not None
        rule = service._ensure_rule_execution_meta(raw_rule)
        prompt = str(rule.get("custom_prompt") or "")
        assert "术前讨论" in prompt
        assert "适用文书: ['operation_record']" not in prompt


def test_sc_039_should_prefer_strongest_low_potassium_context_candidate():
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

    assert "严重低钾血症" in rule_input.primary_medical_text
    assert "加强静脉补钾" in rule_input.primary_medical_text
    assert "患者病情平稳" not in rule_input.primary_medical_text


def test_sc_039_should_fallback_to_senior_course_candidate_when_daily_note_lacks_crisis_context():
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
                    "content": "查房内容：患者病情平稳，继续观察病情变化。",
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "上级查房记录",
                    "display_time": "2025-09-18 10:27:00",
                    "content": "上级医师提示患者严重低钾血症，予以加强静脉补钾，动态复查电解质。",
                },
            ],
        },
    )

    assert "严重低钾血症" in rule_input.primary_medical_text
    assert "继续观察病情变化" not in rule_input.primary_medical_text


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


def test_sc_036_should_use_stricter_runtime_prompt_with_supporting_evidence_guard():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-036")

    assert raw_rule is not None
    normalized = service._ensure_rule_execution_meta(raw_rule)

    assert normalized["prompt_version"] == "runtime-override-sc036-v3"
    prompt = str(normalized.get("custom_prompt") or "")
    assert "同域辅助证据" in prompt
    assert "默认判 non_compliant" in prompt


def test_sc_036_should_fallback_to_non_compliant_when_supporting_evidence_is_abnormal_but_primary_only_has_generic_summary():
    service = SichuanQCService()
    normalized = service._apply_sc036_supporting_evidence_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-036",
            document_type="日常病程记录",
            execution_domain="course",
            primary_medical_text=(
                "查房内容：今日查房，患者诉左脚疼痛，余未诉特殊不适。"
                "处置：患者目前炎症指标较前明显好转，拟明日手术，完善术前准备。"
            ),
            supporting_evidence=[
                {
                    "document_type": "主治医师查房记录",
                    "evidence_text": "2026-04-05 ESR 42mm/h, PCT 0.82ng/ml, CRP 22.4mg/L，提示感染指标仍异常。",
                }
            ],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-036",
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
    assert "辅助证据已提示明确异常结果" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc036_supporting_abnormal_without_analysis"


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


def test_sc_008_should_fallback_to_non_compliant_when_chief_complaint_only_mentions_trauma_event():
    service = SichuanQCService()
    normalized = service._apply_sc008_text_only_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-008",
            document_type="入院记录",
            execution_domain="admission",
            primary_medical_text=(
                "车祸致头面部、胸部等多处受伤40+分钟。\n"
                "患者于40+分钟前走路时被一辆三轮车撞伤起病。"
            ),
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-008",
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
    assert "未突出主要症状或体征" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc008_text_only"


def test_sc_033_should_fallback_to_non_compliant_when_note_only_says_observe_and_handle_if_needed():
    service = SichuanQCService()
    normalized = service._apply_sc033_text_only_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-033",
            document_type="日常病程记录",
            execution_domain="course",
            primary_medical_text=(
                "查房内容：患者昨日C13呼气试验检查时因方法错误，导致无检查结果，"
                "耗材已使用，今日再次行C13呼气试验检查。密观患者病情变化，如有不适，及时处理。"
            ),
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-033",
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
    assert "笼统观察性表述" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc033_text_only"


def test_sc_026_should_fallback_to_non_compliant_when_differential_is_missing_or_too_thin():
    service = SichuanQCService()
    normalized = service._apply_sc026_text_only_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-026",
            document_type="首次病程记录",
            execution_domain="course",
            primary_medical_text=(
                "患者14岁青少年，主要表现为腹痛腹泻4天。"
                "目前诊断：1、感染性腹泻；2、急性胃黏膜病变。"
                "鉴别诊断：细菌性痢疾：表现为腹痛、腹泻，为粘液脓血便、里急后重等，完善大便培养排除。"
            ),
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[],
        ),
        engine_result={
            "rule_id": "SC-026",
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
    assert "鉴别诊断推理" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc026_text_only"


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


def test_sc_033_should_prefer_medication_change_daily_note_over_discharge_like_note():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-033")

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
                    "display_time": "2025-07-10 10:00:00",
                    "content": (
                        "患者未诉腹泻,腹痛不适,精神饮食夜休可,大小便外观无异常。"
                        "患者拒绝完善胃肠镜检查,于今日办理出院。出院医嘱:门诊随访。"
                    ),
                    "source_table": "daily_course_record",
                    "document_id": "daily-discharge",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "partial",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "daily_course_record",
                    "document_title": "日常病程记录",
                    "display_time": "2025-07-07 09:00:00",
                    "content": (
                        "查房内容：患者输注左氧氟沙星过程中出现左前壁皮肤麻木、瘙痒、肿痛，"
                        "输注结束后症状缓解。"
                    ),
                    "source_table": "daily_course_record",
                    "document_id": "daily-medication",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
            ],
        },
    )

    assert "左氧氟沙星" in rule_input.primary_medical_text
    assert "办理出院" not in rule_input.primary_medical_text


def test_sc_026_should_fallback_to_senior_note_when_first_course_is_empty():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-026")

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
                    "document_type": "first_course_record",
                    "document_title": "首次病程记录",
                    "display_time": "2025-10-16 21:40:00",
                    "content": "",
                    "source_table": "first_course_record",
                    "document_id": "first-empty",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "empty_document",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "主治医师查房记录",
                    "display_time": "2025-10-17 08:08:44",
                    "content": "患者腹痛原因待诊，右侧附件区脂肪密度影，畸胎瘤不除外，建议结合专科检查。",
                    "source_table": "senior_course_record",
                    "document_id": "senior-fallback",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
            ],
        },
    )

    assert "畸胎瘤不除外" in rule_input.primary_medical_text
    assert rule_input.document_type == "首次病程记录"


def test_sc_025_should_fallback_to_reasoning_note_when_first_course_is_empty():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-025")

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
                    "document_type": "first_course_record",
                    "document_title": "首次病程记录",
                    "display_time": "2025-10-16 21:40:00",
                    "content": "",
                    "source_table": "first_course_record",
                    "document_id": "first-empty",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "empty_document",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "主治医师查房记录",
                    "display_time": "2025-10-17 08:08:44",
                    "content": "目前诊断：急性阑尾炎。诊断依据：右下腹压痛、反跳痛。鉴别诊断：附件区包块待排。诊疗计划：完善检查后评估手术。",
                    "source_table": "senior_course_record",
                    "document_id": "senior-fallback",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
            ],
        },
    )

    assert "诊疗计划" in rule_input.primary_medical_text
    assert rule_input.document_type == "首次病程记录"


def test_sc_026_should_prefer_reasoning_note_over_discharge_like_senior_note():
    service = SichuanQCService()
    raw_rule = service.get_rule_by_id("SC-026")

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
                    "document_type": "senior_course_record",
                    "document_title": "主治医师查房记录",
                    "display_time": "2025-10-20 08:07:02",
                    "content": "患者症状缓解，今日予以办理出院。出院医嘱：门诊随访。",
                    "source_table": "senior_course_record",
                    "document_id": "senior-discharge",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
                {
                    "document_type": "senior_course_record",
                    "document_title": "主治医师查房记录",
                    "display_time": "2025-10-17 08:08:44",
                    "content": "目前诊断：阑尾炎待排。诊断依据：右下腹压痛、反跳痛。鉴别诊断：右侧附件区脂肪密度影，畸胎瘤不除外。",
                    "source_table": "senior_course_record",
                    "document_id": "senior-reasoning",
                    "sections": [],
                    "source_fields": [],
                    "assembly_status": "assembled",
                    "data_quality_flags": [],
                },
            ],
        },
    )

    assert "鉴别诊断" in rule_input.primary_medical_text
    assert "办理出院" not in rule_input.primary_medical_text


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


def test_sc_146_should_fallback_to_non_compliant_when_preop_round_is_after_presurg_summary():
    service = SichuanQCService()
    normalized = service._apply_sc146_temporal_fallback(
        rule_input=RuleExecutionInput(
            rule_id="SC-146",
            document_type="日常病程记录",
            execution_domain="course",
            primary_medical_text="患者要求手术治疗，继续完善术前准备。",
            supporting_evidence=[],
            timeline_facts=[],
            source_documents=[
                {
                    "source_table": "daily_course_record",
                    "document_title": "日常病程记录",
                    "display_time": "2025-12-17 17:35:00",
                    "content": "现术者术前查看患者，向其交代术中及术后可能发生的意外、并发症及后遗症。",
                },
                {
                    "source_table": "inpat_nondrug_order",
                    "document_title": "手术申请",
                    "display_time": "2025-12-17 15:30:00",
                    "content": "order_type: 手术\norder_name: 腹腔镜经腹全子宫切除术",
                },
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
                    "display_time": "2025-12-17 15:21:59",
                    "content": "术前小结正文",
                }
            ]
        },
    )

    assert normalized["status"] == "non_compliant"
    assert "术前主刀医生查房记录时间晚于术前小结" in str(normalized["findings"])
    assert str((normalized.get("metadata") or {}).get("decision_fallback")) == "sc146_preop_round_after_summary"


@pytest.mark.asyncio
async def test_evaluate_rule_for_visit_sc070_should_include_consultation_supporting_evidence(monkeypatch):
    service = SichuanQCService()

    def _fake_load_bundle(*, execution_domain: str, **_: object) -> dict:
        if execution_domain == "course":
            return {
                "execution_domain": "course",
                "timeline_facts": [],
                "document_hits": {"daily_course_record": True},
                "data_quality_flags": [],
                "source_documents": [
                    {
                        "document_type": "daily_course_record",
                        "source_table": "daily_course_record",
                        "document_id": "daily-001",
                        "document_title": "日常病程记录",
                        "display_time": "2026-03-09 09:00:00",
                        "content": "今日病程记录仅记录患者病情变化，未明确写会诊意见执行情况。",
                    }
                ],
            }
        if execution_domain == "consult_discussion":
            return {
                "execution_domain": "consult_discussion",
                "timeline_facts": [{"source_table": "consultation_record", "field": "request_at", "value": "2026-03-09 08:00:00"}],
                "source_documents": [
                    {
                        "document_type": "consultation_record",
                        "source_table": "consultation_record",
                        "document_id": "consult-001",
                        "document_title": "会诊记录",
                        "display_time": "2026-03-09 10:00:00",
                        "content": "会诊意见：建议加用利伐沙班，并动态复查血栓弹力图。",
                    }
                ],
            }
        raise AssertionError(f"unexpected domain: {execution_domain}")

    async def _fake_orchestrated(**kwargs):
        return {
            "results": [
                {
                    "rule_id": "SC-070",
                    "rule_name": "申请会诊医师未在病程记录中记录会诊意见及执行情况",
                    "status": "uncertain",
                    "is_compliant": True,
                    "findings": "待判断",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.7,
                    "metadata": {"tokens_used": 0, "api_time": 0.0},
                }
            ],
            "executor_breakdown": {"llm": 1},
        }

    monkeypatch.setattr(sichuan_qc_service_module, "load_or_assemble_domain_bundle", _fake_load_bundle)
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _fake_orchestrated)

    result = await service.evaluate_rule_for_visit(
        rule_id="SC-070",
        institute_id="HOSP-001",
        patient_id="PAT-001",
        visit_id="VISIT-001",
    )

    supporting = list((result.get("rule_execution_input") or {}).get("supporting_evidence") or [])
    source_tables = {str(item.get("source_table") or "") for item in supporting}
    assert "consultation_record" in source_tables
    assert any("利伐沙班" in str(item.get("evidence_text") or "") for item in supporting)


@pytest.mark.asyncio
async def test_evaluate_rule_for_visit_sc146_should_include_surgery_bundle_supporting_evidence(monkeypatch):
    service = SichuanQCService()

    def _fake_load_bundle(*, execution_domain: str, **_: object) -> dict:
        if execution_domain == "course":
            return {
                "execution_domain": "course",
                "timeline_facts": [],
                "document_hits": {"senior_course_record": True},
                "data_quality_flags": [],
                "source_documents": [
                    {
                        "document_type": "senior_course_record",
                        "source_table": "senior_course_record",
                        "document_id": "senior-001",
                        "document_title": "上级查房记录",
                        "display_time": "2026-02-05 08:20:35",
                        "content": "诊疗计划：完善相关辅查，明日行左眼下睑睑内翻矫正术。",
                    },
                    {
                        "document_type": "inpat_nondrug_order",
                        "source_table": "inpat_nondrug_order",
                        "document_id": "order-001",
                        "document_title": "临时医嘱",
                        "display_time": "2026-02-06 13:29:25",
                        "content": "order_type: 手术\norder_name: 睑内翻矫正术",
                    },
                ],
            }
        if execution_domain == "surgery":
            return {
                "execution_domain": "surgery",
                "timeline_facts": [{"source_table": "presurg_summary", "field": "record_time", "value": "2026-02-05 18:43:34"}],
                "source_documents": [
                    {
                        "document_type": "presurg_summary",
                        "source_table": "presurg_summary",
                        "document_id": "preop-001",
                        "document_title": "术前小结",
                        "display_time": "2026-02-05 18:43:34",
                        "content": "术前小结：拟行左眼下睑睑内翻矫正术。",
                    }
                ],
            }
        raise AssertionError(f"unexpected domain: {execution_domain}")

    async def _fake_orchestrated(**kwargs):
        return {
            "results": [
                {
                    "rule_id": "SC-146",
                    "rule_name": "缺诊疗医嘱，或诊疗医嘱与病程记录不一致",
                    "status": "uncertain",
                    "is_compliant": True,
                    "findings": "待判断",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 0.7,
                    "metadata": {"tokens_used": 0, "api_time": 0.0},
                }
            ],
            "executor_breakdown": {"llm": 1},
        }

    monkeypatch.setattr(sichuan_qc_service_module, "load_or_assemble_domain_bundle", _fake_load_bundle)
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _fake_orchestrated)

    result = await service.evaluate_rule_for_visit(
        rule_id="SC-146",
        institute_id="HOSP-001",
        patient_id="PAT-001",
        visit_id="VISIT-001",
    )

    supporting = list((result.get("rule_execution_input") or {}).get("supporting_evidence") or [])
    source_tables = {str(item.get("source_table") or "") for item in supporting}
    assert "presurg_summary" in source_tables
    assert any("术前小结" in str(item.get("document_title") or "") for item in supporting)


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


def test_sc_cross_document_rules_should_align_with_pdf_mapping():
    expected = {
        "SC-065": [
            "summary_record",
            "handoff_record",
            "handover_record",
            "transfer_in_record",
            "transfer_out_record",
        ],
        "SC-086": [
            "presurg_summary",
            "senior_course_record",
            "anesthesia_record",
        ],
        "SC-104": [
            "postsurg_firstcourse_record",
            "anesthesia_record",
        ],
        "SC-107": [
            "daily_course_record",
            "senior_course_record",
        ],
        "SC-113": [
            "daily_course_record",
            "presurg_summary",
        ],
    }
    source_paths = [
        Path(__file__).resolve().parents[2] / "app" / "data" / "sichuan_rules_146.json",
        Path(__file__).resolve().parents[2] / "app" / "data" / "sichuan_rules_146_updated.json",
    ]

    for path in source_paths:
        rules = json.loads(path.read_text(encoding="utf-8"))
        for rule_id, applicable_documents in expected.items():
            rule = next(item for item in rules if item["rule_id"] == rule_id)
            assert list(rule["applicable_documents"]) == applicable_documents
