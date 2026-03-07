"""
文书类型常量定义

统一管理英文标识 ↔ 中文名称的映射，消除多处维护风险。
供 sichuan_qc_service.py / unified_rule_engine.py / rule_router.py 等共用。
"""

# ---- 精确映射（与 CDM 表名一致） ----
DOC_TYPE_MAP: dict[str, str] = {
    "admission_record":             "入院记录",
    "first_course_record":          "首次病程记录",
    "daily_course_record":          "日常病程记录",
    "senior_course_record":         "上级查房记录",
    "rescue_record":                "抢救记录",
    "diffcase_discussion_record":   "疑难病例讨论记录",
    "death_discussion":             "死亡病例讨论记录",
    "death_record":                 "死亡记录",
    "handoff_record":               "交接班记录",
    "handover_record":              "交接班记录",
    "summary_record":               "阶段小结",
    "consultation_record":          "会诊记录",
    "surgery_record":               "手术记录",
    "presurg_summary":              "术前小结",
    "presurg_discussion":           "术前讨论",
    "postsurg_firstcourse_record":  "术后首次病程记录",
    "surgery_safecheck_record":     "手术安全核查",
    "surgery_risk_assessment":      "手术风险评估",
    "anesthesia_record":            "麻醉记录",
    "newborn_record":               "新生儿记录",
    "bloodtrans_record":            "输血记录",
    "nursing_record":               "护理记录",
    "discharge_record":             "出院记录",
    "consent_form":                 "知情同意书",
    "exam_item_report":             "检查检验报告",
    "labtest_item_report":          "检验报告",
    "medical_order":                "医嘱",
    "transfer_in_record":           "转科记录",
    "transfer_out_record":          "转科记录",
}

# ---- 旧的粗粒度/同义编码（向后兼容） ----
DOC_TYPE_COMPAT_MAP: dict[str, str] = {
    "progress_note":        "病程记录",
    "operation_record":     "手术记录",
    "examination_report":   "检查检验报告",
    "course_record":        "病程记录",
    "case_discussion":      "病例讨论",
    "discharge_summary":    "出院记录",
    "lab_report":           "检验报告",
    "informed_consent":     "知情同意书",
    "transfusion_record":   "输血记录",
}

# 完整映射（精确 + 兼容）
DOC_TYPE_FULL_MAP: dict[str, str] = {**DOC_TYPE_MAP, **DOC_TYPE_COMPAT_MAP}

# 反向映射：中文 → 英文（取精确映射中的首个英文标识）
DOC_TYPE_CN_TO_EN: dict[str, str] = {}
for _en, _cn in DOC_TYPE_MAP.items():
    if _cn not in DOC_TYPE_CN_TO_EN:
        DOC_TYPE_CN_TO_EN[_cn] = _en
