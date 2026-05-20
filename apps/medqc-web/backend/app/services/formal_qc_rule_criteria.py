from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


RULE_CRITERIA_VERSION = "formal_high_false_positive_rule_criteria_v1"


def _criteria(
    *,
    required_document: str,
    required_section: str,
    required_fields: list[str],
    confirmed_conditions: list[str],
    not_confirmed_conditions: list[str],
    data_quality_gap_conditions: list[str],
    rejected_conditions: list[str] | None = None,
    policy_pending_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rule_criteria_version": RULE_CRITERIA_VERSION,
        "required_document": required_document,
        "required_section": required_section,
        "required_fields": required_fields,
        "confirmed_conditions": confirmed_conditions,
        "not_confirmed_conditions": not_confirmed_conditions,
        "data_quality_gap_conditions": data_quality_gap_conditions,
        "rejected_conditions": rejected_conditions or [],
        "policy_pending_flags": policy_pending_flags or [],
    }


RULE_SPECIFIC_CRITERIA: dict[str, dict[str, Any]] = {
    "SC-012": _criteria(
        required_document="admission_record/入院记录",
        required_section="现病史/发病后到入院前",
        required_fields=[
            "onset_course",
            "preadmission_visit",
            "preadmission_exam",
            "preadmission_treatment",
            "treatment_effect",
        ],
        confirmed_conditions=[
            "证据明确来自入院记录现病史。",
            "现病史提示入院前曾在院外、门诊、急诊或其他机构检查/治疗。",
            "现病史未记录检查项目、治疗措施/用药或治疗效果中的关键内容。",
            "supporting_quote 能直接引用“外院治疗具体不详/输液治疗具体不详”等缺项原文。",
        ],
        not_confirmed_conditions=[
            "证据不是入院记录现病史。",
            "患者入院前明确未诊治，且无院前检查治疗触发。",
            "已记录主要检查、治疗和效果，只是语言简略。",
            "只看到孤立短句，无法确认所在段落。",
        ],
        data_quality_gap_conditions=[
            "缺完整现病史上下文。",
            "只看到截断片段，无法判断后文是否补充。",
            "无法确认患者是否存在入院前检查或治疗。",
        ],
    ),
    "SC-013": _criteria(
        required_document="admission_record/入院记录",
        required_section="既往史",
        required_fields=[
            "prior_disease_history",
            "infectious_disease_history",
            "surgery_trauma_history",
            "transfusion_history",
            "allergy_history",
            "vaccination_history",
        ],
        confirmed_conditions=[
            "基于完整或足够完整的入院记录既往史段落/结构化字段矩阵。",
            "能明确指出规定字段缺失、空白、未记录或前后矛盾。",
            "missing_fields 非空且 supporting_quote 支撑具体缺项。",
        ],
        not_confirmed_conditions=[
            "只看到既往史片段，无法确认其他字段是否已记录。",
            "主要字段已覆盖，仅部分表达简略。",
            "仅凭“不详预防接种史”不得直接 confirmed。",
        ],
        data_quality_gap_conditions=[
            "缺完整既往史段落。",
            "预防接种史“不详”且客户未确认必须明确记录。",
            "只能看到片段，不能判断字段完整性。",
        ],
        policy_pending_flags=["policy_pending_vaccination_unknown"],
    ),
    "SC-034": _criteria(
        required_document="daily_course_record/病程记录 + 医嘱/治疗变化来源",
        required_section="病情变化、医嘱变化、治疗措施调整相关病程",
        required_fields=[
            "trigger_event_present",
            "trigger_event_quote",
            "order_or_treatment_change_present",
            "order_or_treatment_change_quote",
            "course_analysis_present",
            "course_analysis_quote",
            "treatment_effect_or_followup_present",
        ],
        confirmed_conditions=[
            "同时具备病情变化/异常指标/疗效不佳等触发事件。",
            "同时具备明确医嘱、药物或治疗措施变化，如新开、停用、调整剂量或改变方案。",
            "对应病程缺少变化原因、依据、效果评估或后续计划。",
            "必须提供医嘱变化 quote 和病程上下文 quote。",
        ],
        not_confirmed_conditions=[
            "只有症状 + 对症处理，例如“术后呕吐，予胃复安止吐”。",
            "只有治疗措施存在，但没有证明发生医嘱/治疗变化。",
            "病程已记录处理措施和观察计划。",
        ],
        data_quality_gap_conditions=[
            "缺医嘱变化来源。",
            "缺病程上下文。",
            "无法形成触发事件、变化、缺分析三段链路。",
        ],
    ),
    "SC-118": _criteria(
        required_document="discharge_record/出院记录",
        required_section="完整出院记录字段矩阵",
        required_fields=[
            "admission_date",
            "discharge_date",
            "admission_condition",
            "admission_diagnosis",
            "treatment_course",
            "discharge_condition",
            "discharge_advice",
            "doctor_signature",
        ],
        confirmed_conditions=[
            "必须看到完整出院记录或结构化字段矩阵。",
            "必须明确列出具体 missing_fields。",
            "supporting_quote 能支撑对应字段缺失或内容错误。",
        ],
        not_confirmed_conditions=[
            "只有患者姓名、性别、年龄、主诉、记录时间等文书头片段。",
            "只笼统说关键要素缺失但没有字段矩阵。",
            "字段存在但表述简略。",
        ],
        data_quality_gap_conditions=[
            "只看到出院记录片段。",
            "缺完整出院记录上下文。",
            "无法判断具体字段是否在后文补充。",
        ],
    ),
    "SC-121": _criteria(
        required_document="discharge_record/出院记录",
        required_section="诊疗经过",
        required_fields=[
            "main_treatment_measures",
            "main_drug_names_or_treatment_plan",
            "important_auxiliary_exam_results_related_to_diagnosis",
            "treatment_response_or_outcome",
            "cross_document_contrast_present_when_claiming_missing_drug",
        ],
        confirmed_conditions=[
            "必须看到完整诊疗经过段。",
            "能证明主要治疗、主要药品、重要辅助检查结果或治疗转归确实缺失。",
            "若声称主要药品缺失，必须有医嘱、会诊建议或治疗方案对照。",
        ],
        not_confirmed_conditions=[
            "仅凭“护胃、补液”等短句 confirmed。",
            "仅凭主观“不详细”判断 confirmed。",
            "缺跨文书对照却声称主要药品遗漏。",
        ],
        data_quality_gap_conditions=[
            "缺完整诊疗经过段。",
            "只有短片段或截断文本。",
            "需要跨文书对照但缺医嘱/会诊/治疗方案来源。",
        ],
    ),
    "SC-122": _criteria(
        required_document="discharge_record/出院记录",
        required_section="出院医嘱",
        required_fields=[
            "discharge_advice_section_present",
            "source_is_full_discharge_advice_section",
            "medication_advice_present",
            "followup_advice_present",
            "diet_or_activity_advice_present",
            "warning_signs_or_return_visit_present",
        ],
        confirmed_conditions=[
            "必须看到完整出院医嘱段。",
            "能证明该段医嘱缺失或明显不全。",
            "missing_fields 能指出缺少用药、复诊、饮食活动、注意事项或返院提示中的核心内容。",
        ],
        not_confirmed_conditions=[
            "只有随访方式、随访周期、随访日期等局部片段。",
            "只看到出院带药段，未看到完整出院医嘱段。",
            "出院医嘱包含合理复查、饮食、活动、用药或注意事项。",
        ],
        data_quality_gap_conditions=[
            "缺完整出院医嘱段。",
            "只有随访/复查/局部建议片段。",
            "无法确认该片段是否为完整出院医嘱。",
        ],
    ),
    "SC-123": _criteria(
        required_document="discharge_record/出院记录",
        required_section="出院带药/出院用药",
        required_fields=[
            "discharge_medication_section_present",
            "drug_name",
            "dose",
            "dose_unit",
            "route",
            "frequency",
            "duration_or_quantity",
        ],
        confirmed_conditions=[
            "必须先确认存在出院带药/出院用药段或药品条目。",
            "逐药品确认药名、剂量、途径、频率、疗程/数量等核心字段确实缺失。",
            "supporting_quote 必须来自完整或足够完整的出院带药段。",
        ],
        not_confirmed_conditions=[
            "没有出院带药证据。",
            "出院医嘱只是饮食、休养、复查、换药、支具固定等非药品事项。",
            "药名、剂量、用法/途径、频率等核心字段基本完整。",
            "不确定是住院期间用药还是出院带药。",
        ],
        data_quality_gap_conditions=[
            "证据不是完整出院带药段。",
            "药品条目被截断，无法判断字段。",
            "无法确认是否存在出院带药。",
        ],
        rejected_conditions=[
            "无出院带药且仅有非药品出院医嘱时 rejected_by_system。",
            "出院带药核心字段基本完整时 rejected_by_system/defect_absent。",
        ],
    ),
}


def normalize_rule_id(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("－", "-").replace("—", "-").replace("–", "-").replace("_", "-")
    text = re.sub(r"\s+", "", text)
    match = re.search(r"(SC)-?0*([0-9]{1,3})", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):03d}"
    return text


def get_rule_specific_criteria(rule_id: Any) -> dict[str, Any]:
    criteria = RULE_SPECIFIC_CRITERIA.get(normalize_rule_id(rule_id))
    return deepcopy(criteria) if criteria else {}


def rule_criteria_metadata(rule_id: Any) -> dict[str, Any]:
    criteria = get_rule_specific_criteria(rule_id)
    if not criteria:
        return {}
    return {
        "rule_criteria_version": criteria["rule_criteria_version"],
        "required_document": criteria["required_document"],
        "required_section": criteria["required_section"],
        "required_fields": list(criteria["required_fields"]),
        "field_matrix_evidence": {field: "required" for field in criteria["required_fields"]},
        "policy_pending_flags": list(criteria.get("policy_pending_flags") or []),
    }


def rule_criteria_prompt_block(rule_id: Any, *, compact: bool = False) -> str:
    normalized = normalize_rule_id(rule_id)
    criteria = get_rule_specific_criteria(normalized)
    if not criteria:
        return ""

    def _join(items: list[str]) -> str:
        if compact:
            return "；".join(items)
        return "\n".join(f"- {item}" for item in items)

    if compact:
        return (
            f"【规则专属判定标准 {RULE_CRITERIA_VERSION}】"
            f" required_document={criteria['required_document']}；"
            f" required_section={criteria['required_section']}；"
            f" required_fields={','.join(criteria['required_fields'])}；"
            f" confirmed_conditions={_join(criteria['confirmed_conditions'])}；"
            f" not_confirmed_conditions={_join(criteria['not_confirmed_conditions'])}；"
            f" data_quality_gap_conditions={_join(criteria['data_quality_gap_conditions'])}"
        )
    return (
        f"【规则专属判定标准 {RULE_CRITERIA_VERSION}】\n"
        f"规则：{normalized}\n"
        f"required_document：{criteria['required_document']}\n"
        f"required_section：{criteria['required_section']}\n"
        f"required_fields：{', '.join(criteria['required_fields'])}\n"
        "confirmed_conditions：\n"
        f"{_join(criteria['confirmed_conditions'])}\n"
        "not_confirmed_conditions：\n"
        f"{_join(criteria['not_confirmed_conditions'])}\n"
        "data_quality_gap_conditions：\n"
        f"{_join(criteria['data_quality_gap_conditions'])}\n"
        f"policy_pending_flags：{', '.join(criteria.get('policy_pending_flags') or []) or '无'}\n"
        "请按上述文书、段落和字段矩阵裁决；证据不足时输出 data_quality_gap，不得凭规则名称自由扩展。"
    )


def enrich_rule_with_specific_criteria(rule: dict[str, Any]) -> dict[str, Any]:
    next_rule = dict(rule)
    rule_id = normalize_rule_id(next_rule.get("rule_id") or next_rule.get("rule_code"))
    criteria = get_rule_specific_criteria(rule_id)
    if not criteria:
        return next_rule

    criteria_block = rule_criteria_prompt_block(rule_id, compact=True)
    original_prompt = str(next_rule.get("custom_prompt") or next_rule.get("prompt_template") or "").strip()
    if criteria_block not in original_prompt:
        next_rule["custom_prompt"] = f"{criteria_block}\n{original_prompt}".strip()
    next_rule["rule_specific_criteria"] = criteria
    next_rule["rule_criteria_version"] = RULE_CRITERIA_VERSION
    version = str(next_rule.get("prompt_version") or "").strip()
    if RULE_CRITERIA_VERSION not in version:
        next_rule["prompt_version"] = f"{version}+{RULE_CRITERIA_VERSION}" if version else RULE_CRITERIA_VERSION
    return next_rule
