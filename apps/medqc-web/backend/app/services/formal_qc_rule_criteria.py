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
    first_pass_guidance: list[str] | None = None,
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
        "first_pass_guidance": first_pass_guidance or [],
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
        first_pass_guidance=[
            "一审以候选召回为主：证据来自入院记录现病史且存在入院前诊疗线索时，不要因最终缺项尚需二审确认而直接消除候选。",
            "只有明确不是入院记录现病史、仅文书头/记录时间或完全无院前诊疗触发时才不输出候选。",
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
        first_pass_guidance=[
            "一审以候选召回为主：入院记录既往史字段疑似缺项或前后矛盾时保留候选。",
            "仅“不详预防接种史”属于客户口径敏感项，一审可保留为复核候选，但二审不得直接 confirmed。",
        ],
    ),
    "SC-015": _criteria(
        required_document="admission_record/入院记录",
        required_section="个人史/婚育史/月经史/家族史",
        required_fields=[
            "sex",
            "age",
            "personal_history_present",
            "family_history_present",
            "marital_childbearing_applicable",
            "marital_childbearing_present",
            "menstrual_history_applicable",
            "menstrual_history_present",
            "supporting_quote_by_field",
        ],
        confirmed_conditions=[
            "必须基于完整或近完整入院记录上下文，且能定位个人史/婚育史/月经史/家族史段落。",
            "必须明确患者性别和年龄，并按性别/年龄判断婚育史、月经史是否适用。",
            "confirmed 仅限必填段落整段缺失、适用字段明确缺失，或与其他源文书存在明确强矛盾。",
            "supporting_quote 必须定位到对应段落和具体缺项字段，不能只引用“具体不详”。",
        ],
        not_confirmed_conditions=[
            "男性病历仅缺月经史不得 confirmed。",
            "儿童或未达适用年龄病历仅缺婚育史/月经史不得 confirmed。",
            "“具体不详/不详”单独出现不得 confirmed，除非客户已确认该口径必须扣分。",
            "字段矩阵显示个人史、婚育史、月经史、家族史已按适用性记录。",
        ],
        data_quality_gap_conditions=[
            "缺性别或年龄，无法判断适用性。",
            "缺完整入院记录上下文或只能看到局部片段。",
            "只有“具体不详/不详”等口径敏感表述，缺客户确认口径。",
            "无法判断婚育史/月经史是否按年龄适用。",
        ],
        rejected_conditions=[
            "非入院记录来源。",
            "男性仅声称缺月经史。",
            "适用性不成立或字段矩阵已覆盖主要规定字段。",
        ],
        policy_pending_flags=["policy_pending_unspecified_history_detail"],
        first_pass_guidance=[
            "一审只做候选召回：入院记录个人史/婚育史/月经史/家族史疑似缺项或矛盾时保留 qc_review_candidate。",
            "男性仅缺月经史、儿童仅缺婚育史/月经史、仅文书头/记录时间时不应输出 confirmed 候选。",
            "“具体不详/不详”可以作为复核候选，但二审不得直接 confirmed。",
        ],
    ),
    "SC-018": _criteria(
        required_document="admission_record/入院记录",
        required_section="体格检查/专科检查/局部查体",
        required_fields=[
            "chief_complaint_present",
            "diagnosis_present",
            "body_site_or_system_present",
            "general_physical_exam_present",
            "specialty_or_local_exam_present",
            "specialty_exam_context_available",
            "recorded_findings",
            "missing_findings",
        ],
        confirmed_conditions=[
            "必须拿到主诉或诊断、疾病/损伤部位或系统定位、一般体格检查、专科/局部查体上下文。",
            "必须证明相关部位存在明确疾病/损伤，且一般查体和专科/局部查体均缺主要阳性体征或关键阴性体征。",
            "supporting_quote 不得只有“详见专科检查”，必须能引用到可审计的查体上下文和缺项字段。",
        ],
        not_confirmed_conditions=[
            "只看到“详见专科检查”不得 confirmed。",
            "专科/局部查体全文存在且已记录相关体征。",
            "缺主诉、诊断或部位定位，不能证明该查体要件适用。",
            "只是主观认为查体不够详细。",
        ],
        data_quality_gap_conditions=[
            "缺专科/局部查体全文。",
            "缺主诉、诊断或部位定位上下文。",
            "只有一般查体片段，无法确认完整入院记录是否已有局部查体。",
            "quote 过短或无法回连源文书。",
        ],
        first_pass_guidance=[
            "一审只做候选召回：入院记录主诉/诊断/部位提示需要相关查体且疑似缺体征时保留候选。",
            "仅“详见专科检查”不得作为 confirmed 依据；缺专科全文时应交二审转 data_quality_gap。",
        ],
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
        first_pass_guidance=[
            "一审以候选召回为主：出现病情变化、治疗措施或医嘱调整线索时可以保留候选，由二审核对三段链路。",
            "仅有症状加普通对症处理且无医嘱/治疗变化线索时，不应作为 confirmed 候选。",
        ],
    ),
    "SC-036": _criteria(
        required_document="exam/lab/pathology report + daily_course_record/检查检验病理报告 + 病程记录",
        required_section="异常辅助检查结果、后续病程分析及处理意见",
        required_fields=[
            "abnormal_result_present",
            "abnormal_result_quote",
            "abnormal_result_time",
            "course_record_after_result_present",
            "course_record_quote",
            "analysis_present",
            "treatment_or_followup_present",
            "timeline_valid",
        ],
        confirmed_conditions=[
            "必须有明确重要异常检查/检验/病理结果 quote，并可判断异常程度或标志。",
            "必须有异常结果后续病程 quote 和时间线，证明医生应当分析处理。",
            "后续病程缺少针对该异常的分析、处理意见、复查、会诊、治疗调整或观察计划。",
        ],
        not_confirmed_conditions=[
            "仅有“辅助检查同前”不得 confirmed。",
            "缺原始异常检查/检验/病理报告来源不得 confirmed。",
            "病程已有处理意见、复查、会诊、治疗调整或观察计划不得 confirmed。",
            "异常结果与本次病情无关或非重要异常不得 confirmed。",
        ],
        data_quality_gap_conditions=[
            "有异常结果但缺后续病程。",
            "有病程但缺检查/检验原报告或异常标志来源。",
            "缺时间戳，无法判断异常结果与病程先后。",
            "只有短片段，无法排除后文已有分析处理。",
        ],
        first_pass_guidance=[
            "一审只召回候选：重要异常结果和后续病程疑似未分析处理时保留 qc_review_candidate。",
            "“辅助检查同前”只能作为弱病程片段，必须绑定异常结果和时间线。",
        ],
    ),
    "SC-047": _criteria(
        required_document="daily_course_record/病程记录 + diagnosis matrix/诊断矩阵",
        required_section="修正诊断/补充诊断/诊断调整动作及理由依据",
        required_fields=[
            "diagnosis_revision_action_present",
            "diagnosis_revision_action_quote",
            "before_diagnosis_quote",
            "after_diagnosis_quote",
            "revision_time",
            "reason_present",
            "diagnostic_basis_present",
            "adjacent_course_checked",
        ],
        confirmed_conditions=[
            "必须先证明发生修正诊断、补充诊断、诊断调整或目前诊断改为等诊断变更动作。",
            "必须有变更时间、变更前后诊断或等价对照。",
            "同次或邻近病程完全缺少修改理由和诊断依据，且无病理/检查/会诊等明确支撑 quote。",
        ],
        not_confirmed_conditions=[
            "单纯病理结果、检查结果、检验异常或诊断名称变化不得视为诊断修正动作。",
            "未发生诊断修正/补充/调整动作时不得 confirmed。",
            "病程已记录修改理由或诊断依据时不得 confirmed。",
            "只是鉴别诊断/考虑诊断表述时不得 confirmed。",
        ],
        data_quality_gap_conditions=[
            "只有诊断列表，缺连续病程，无法判断是否发生修正/补充。",
            "有诊断动作但缺变更时间、变更前后诊断或相邻病程。",
            "缺相邻病程，无法确认理由/依据是否在其他记录补充。",
        ],
        rejected_conditions=[
            "无诊断修正/补充/调整动作。",
            "已有修改理由和诊断依据。",
        ],
        first_pass_guidance=[
            "一审只召回明确诊断动作候选：修正诊断、补充诊断、诊断调整为、诊断改为、新增诊断等。",
            "单纯病理或检查结果不构成 trigger。",
        ],
    ),
    "SC-050": _criteria(
        required_document="senior_course_record/上级查房记录",
        required_section="上级医师查房时间、医师级别、病情分析、诊疗意见",
        required_fields=[
            "senior_round_records_present",
            "round_time_present",
            "doctor_role_present",
            "condition_analysis_present",
            "treatment_opinion_present",
            "weekly_round_coverage_present",
        ],
        confirmed_conditions=[
            "内容缺陷必须基于完整或近完整上级查房正文，证明病情分析缺失且诊疗意见缺失或仅模板化。",
            "频次缺陷必须有完整住院时间轴和全部查房事件，能证明某 7 天窗口缺副主任以上或医疗组长查房。",
            "医师级别/时间缺陷必须有可核查记录时间、标题、签名或角色来源。",
        ],
        not_confirmed_conditions=[
            "不得仅因查房记录短 confirmed。",
            "查房已包含病情分析和诊疗意见时不得 confirmed。",
            "只是“继续治疗/观察”但上下文已有判断或计划时不得 confirmed。",
        ],
        data_quality_gap_conditions=[
            "缺完整查房正文。",
            "缺住院时间轴、全部查房事件、医师级别或医疗组长身份来源。",
            "只能证明某条记录短，不能证明全文无分析/无意见。",
        ],
        first_pass_guidance=[
            "一审只召回候选：命中上级查房记录且疑似无病情分析、无诊疗意见、频次或级别异常时保留。",
            "不要仅凭查房记录短直接 confirmed。",
        ],
    ),
    "SC-105": _criteria(
        required_document="postsurg_firstcourse_record/术后首次病程记录 + surgery/anesthesia record/手术麻醉记录",
        required_section="术后首次病程字段矩阵",
        required_fields=[
            "surgery_trigger_present",
            "postsurg_firstcourse_full_text",
            "record_time",
            "surgery_time",
            "procedure_name",
            "anesthesia_method",
            "intraoperative_condition",
            "postoperative_treatment",
            "postoperative_precautions",
            "doctor_signature",
        ],
        confirmed_conditions=[
            "必须先证明存在手术/有创操作触发和术后首次病程记录。",
            "必须基于完整或近完整术后首次病程字段矩阵，明确缺术后诊断、手术名称、术中情况、术后处理、注意事项、医师签名等核心字段。",
            "如主张时间/术式不一致，必须有手术记录或麻醉记录对照 quote。",
        ],
        not_confirmed_conditions=[
            "无手术/有创操作触发不得 confirmed。",
            "只见“术后安返病房”等短片段不得 confirmed。",
            "完整字段矩阵已覆盖核心字段不得 confirmed。",
        ],
        data_quality_gap_conditions=[
            "缺术后首次病程全文。",
            "缺手术记录/麻醉记录导致无法核对时间、术式、麻醉方式。",
            "无法确认该记录是否为术后首次病程。",
        ],
        first_pass_guidance=[
            "一审只召回候选：存在手术触发且术后首次病程疑似缺核心字段时保留。",
            "短片段只能召回或转 data_quality_gap，不能 confirmed。",
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
            "必须看到结构化字段矩阵，且 missing_fields 来自出院记录 source_fields/sections 的显式空值。",
            "不得把完整/近完整正文中没有出现某个字段标题，直接当作该字段缺失。",
            "supporting_quote 必须回连到字段矩阵中的具体缺失字段；仅引用正文片段不足以 confirmed。",
        ],
        not_confirmed_conditions=[
            "只有患者姓名、性别、年龄、主诉、记录时间等文书头片段。",
            "只笼统说关键要素缺失但没有字段矩阵。",
            "只根据文本片段或正文未出现字段标题推断缺项。",
            "字段存在但表述简略。",
        ],
        data_quality_gap_conditions=[
            "只看到出院记录片段。",
            "缺完整出院记录上下文。",
            "缺出院记录结构化 source_fields/sections，无法判断日期、诊断、签名等字段是否为空。",
            "无法判断具体字段是否在后文补充。",
        ],
        first_pass_guidance=[
            "一审以候选召回为主：命中出院记录且疑似缺入院日期、出院日期、诊疗经过、出院情况、出院医嘱或签名等字段时，应保留 qc_review_candidate。",
            "不要把 confirmed 条件当作一审硬过滤；完整/近完整上下文是否足以 confirmed 交由二审字段矩阵裁决。",
            "只有证据仅为文书头、记录时间、患者基本信息，或无法确认来自出院记录时，才不输出 confirmed 候选。",
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
            "cross_document_contrast_present",
            "missing_from_discharge_candidates",
            "matrix_source_tables",
        ],
        confirmed_conditions=[
            "本规则质控对象是出院记录的诊疗经过段，不是住院医嘱本身。",
            "必须看到完整或近完整诊疗经过段。",
            "必须用住院医嘱、检查检验、病程变化或会诊建议等住院事实对照，证明出院记录漏写关键诊疗内容。",
            "能指出具体漏写项，例如关键治疗类别、主要药品、重要异常检查结果或治疗转归。",
            "若声称主要药品缺失，必须有关键药品类别或医嘱对照。",
            "若声称重要辅助检查结果缺失，必须有明确异常或重要检查检验对照。",
            "若缺陷主张不是主要药品名称缺失，has_discharge_medication_text=false 不能一票否决 confirmed。",
            "supporting_quote 可以较短，但必须能回连到完整/近完整诊疗经过上下文。",
        ],
        not_confirmed_conditions=[
            "仅凭“护胃、补液、对症支持治疗、抗感染治疗、继续治疗”等泛化短句 confirmed。",
            "仅凭主观“不详细”判断 confirmed。",
            "缺跨文书对照却确认诊疗经过漏写关键诊疗内容。",
            "住院事实只证明医嘱存在，但不能证明出院记录应写而未写。",
        ],
        data_quality_gap_conditions=[
            "缺完整诊疗经过段。",
            "只有短片段或截断文本。",
            "需要跨文书对照但缺医嘱/检查检验/病程变化/会诊建议来源。",
            "Python evidence matrix 无法证明 cross_document_contrast_present。",
            "只能抽到泛化短句，未抽到 key_drug_categories、important_abnormal_exam_or_lab_results 或 course_change_or_treatment_adjustment_quotes。",
        ],
        first_pass_guidance=[
            "一审以候选召回为主：命中出院记录诊疗经过且疑似缺主要治疗、重要检查结果、治疗转归或必要治疗方案时，应保留 qc_review_candidate。",
            "不要因为 supporting_quote 本身较短或 has_discharge_medication_text=false 直接消除候选；二审需结合 targeted_evidence_context.discharge_record_evidence 的完整/近完整上下文裁决。",
            "一审不得把住院医嘱本身当成 SC-121 缺陷；必须提示二审用住院事实对照出院记录诊疗经过是否漏写关键内容。",
            "泛化治疗短句只能作为候选线索；缺对照来源时二审应转 data_quality_gap。",
            "只有证据仅为文书头、记录时间、孤立短句且无法回连诊疗经过上下文时，才不输出 confirmed 候选。",
        ],
    ),
    "SC-125": _criteria(
        required_document="discharge_record/出院记录 + diagnosis matrix/诊断矩阵",
        required_section="入院诊断、出院/死亡诊断、主次顺序与对照证据",
        required_fields=[
            "admission_diagnosis_list",
            "discharge_diagnosis_list",
            "death_diagnosis_list_if_applicable",
            "diagnosis_no_or_main_secondary_flag",
            "source_quote_for_each_diagnosis_source",
            "clinical_support_or_contradiction_quote",
            "counterevidence_checked",
        ],
        confirmed_conditions=[
            "必须有入院诊断、出院/死亡诊断、诊断序号或主次标识的诊断矩阵。",
            "漏填 confirmed 需要证明某诊断住院期间已明确成立并影响治疗/出院判断，且完整出院/死亡诊断列表中缺失。",
            "错填 confirmed 需要客观反证，如诊断表、病理/检查、死亡记录或明确临床事实冲突。",
            "顺序错误 confirmed 只能基于结构化主次字段或权威来源冲突，不得凭模型主观排序。",
        ],
        not_confirmed_conditions=[
            "仅凭模型主观认为诊断顺序应调整不得 confirmed。",
            "只有单个诊断名、短 quote 或诊断来源不明不得 confirmed。",
            "同义词、诊断粒度差异、疑似诊断被明确诊断替代且有病程依据时不得 confirmed。",
        ],
        data_quality_gap_conditions=[
            "缺完整出院诊断/死亡诊断列表、入院诊断列表或结构化诊断表。",
            "缺主次/序号字段，无法判断顺序错误。",
            "诊断演变可能合理但缺病程、检查、诊疗经过或诊断依据。",
            "顺序问题依赖客户编码口径但当前无明确标准。",
        ],
        first_pass_guidance=[
            "一审只召回候选：出院/死亡诊断疑似错填、漏填、顺序错误且有诊断矩阵线索时保留。",
            "不得凭主观诊断排序或孤立诊断名输出 confirmed 候选。",
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
        first_pass_guidance=[
            "一审以候选召回为主：命中出院医嘱段且疑似缺核心出院指导内容时保留候选。",
            "只有随访方式/周期等局部片段时不应直接 confirmed，交由二审或 postprocess 转 data_quality_gap。",
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
        first_pass_guidance=[
            "一审以候选召回为主：仅在确认存在出院带药/出院用药药品条目且字段疑似缺失时保留候选。",
            "无出院带药、非药品出院医嘱或字段完整时不应输出 confirmed 候选。",
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
            " 一审用于候选召回，不得把 confirmed 条件当作提前消灭候选的硬过滤；"
            f" required_document={criteria['required_document']}；"
            f" required_section={criteria['required_section']}；"
            f" required_fields={','.join(criteria['required_fields'])}；"
            f" first_pass_guidance={_join(criteria.get('first_pass_guidance') or [])}；"
            "若命中对应文书/段落且存在疑似缺项，请输出 qc_review_candidate 供二审字段矩阵裁决；"
            f" hard_not_candidate={_join(criteria['not_confirmed_conditions'])}"
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
