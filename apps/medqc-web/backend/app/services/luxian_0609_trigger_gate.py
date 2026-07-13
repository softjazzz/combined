from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


TRIGGER_PRESENT = "present"
TRIGGER_ABSENT = "absent"
TRIGGER_DATA_GAP = "data_gap"
TRIGGER_UNKNOWN = "unknown"

_KNOWN_STATUSES = {TRIGGER_PRESENT, TRIGGER_ABSENT, TRIGGER_DATA_GAP, TRIGGER_UNKNOWN}
_LX0609_033_LIVE_SOURCE_STATES = {
    "consent_document_present",
    "exact_performed",
    "zero_rows",
    "nonexact_rows",
    "unavailable",
    "error",
}


@dataclass(frozen=True)
class Luxian0609GateDecision:
    rule_id: str
    status: str
    reason: str
    data_gap_fields: tuple[str, ...] = field(default_factory=tuple)
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    source: str = "deterministic"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        metadata = {
            "trigger_gate_status": self.status,
            "trigger_gate_reason": self.reason,
            "data_gap_fields": list(self.data_gap_fields),
            "trigger_gate_matched_keywords": list(self.matched_keywords),
            "trigger_gate_source": self.source,
        }
        if self.extra:
            metadata.update(dict(self.extra))
        return metadata


def build_luxian_0609_033_live_source_decision(
    *, source_state: str, source_status: str, source_row_count: int
) -> Luxian0609GateDecision:
    """033 的受控读侧安全 gate；不读取或保留原始时间、坐标、SQL。"""
    normalized_state = str(source_state or "").strip()
    normalized_status = str(source_status or "").strip()
    if normalized_state not in _LX0609_033_LIVE_SOURCE_STATES:
        raise ValueError("invalid lx0609-033 live source state")
    if normalized_status not in {"available", "unavailable", "error"}:
        raise ValueError("invalid lx0609-033 live source status")
    if not isinstance(source_row_count, int) or source_row_count < 0:
        raise ValueError("invalid lx0609-033 live source count")

    extra = {
        "live_source_status": normalized_status,
        "live_source_row_count": source_row_count,
        "live_source_state": normalized_state,
        "live_source_policy_version": "lx0609-033-live-source-v1",
    }
    if normalized_state == "consent_document_present":
        if normalized_status != "available" or source_row_count < 1:
            raise ValueError("invalid lx0609-033 consent document source")
        return Luxian0609GateDecision(
            rule_id="LX0609-033",
            status=TRIGGER_PRESENT,
            reason="已匹配到非空手术知情同意书文书，保留现有语义核查分派",
            source="bundle_document_guard",
            extra=extra,
        )
    if normalized_state == "zero_rows":
        return Luxian0609GateDecision(
            rule_id="LX0609-033",
            status=TRIGGER_ABSENT,
            reason="受控手术记录查询成功且未发现本次手术记录",
            source="live_source_guard",
            extra=extra,
        )
    if normalized_state == "exact_performed":
        return Luxian0609GateDecision(
            rule_id="LX0609-033",
            status=TRIGGER_DATA_GAP,
            reason="已确认本次严格已实施手术，但手术知情同意书来源完整性未获证明",
            data_gap_fields=("手术知情同意书来源完整性",),
            source="live_source_guard",
            extra=extra,
        )
    return Luxian0609GateDecision(
        rule_id="LX0609-033",
        status=TRIGGER_DATA_GAP,
        reason="无法由受控手术记录安全确认本次严格已实施手术",
        data_gap_fields=("手术记录已实施时间",),
        source="live_source_guard",
        extra=extra,
    )


_FAMILY_KEYWORDS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "surgery",
        ("手术", "术前", "术后", "安全核查", "麻醉", "切口", "术者", "手术操作"),
        ("手术记录", "手术名称", "术前讨论", "术前小结", "麻醉记录", "安全核查", "切口", "术后"),
    ),
    (
        "transfusion",
        ("输血", "血制品", "红细胞", "血浆", "血小板"),
        (
            "输血申请",
            "输血记录",
            "输血医嘱",
            "输血知情同意",
            "交叉配血",
            "血制品",
            "红细胞",
            "悬浮红细胞",
            "血浆",
            "血小板",
            "输注去白",
            "输注红细胞",
            "输注血浆",
            "输注血小板",
        ),
    ),
    (
        "consultation",
        ("会诊",),
        ("会诊记录", "会诊申请", "会诊意见", "会诊目的"),
    ),
    (
        "rescue",
        ("抢救",),
        ("抢救", "抢救记录", "抢救结束"),
    ),
    (
        "critical",
        ("病危", "病重", "危重"),
        ("病危", "病重", "危重", "病危医嘱", "病重医嘱"),
    ),
    (
        "imaging",
        ("CT", "MRI", "影像", "检查结果", "阳性结果"),
        ("CT", "MRI", "磁共振", "影像", "检查报告", "报告时间"),
    ),
    (
        "culture",
        ("细菌培养", "培养", "药敏", "阳性菌"),
        ("培养", "药敏", "阳性菌", "细菌"),
    ),
    (
        "pathology_tumor",
        ("病理", "恶性肿瘤", "肿瘤", "化疗", "癌"),
        ("病理报告", "病理检查", "病理诊断", "病理结果", "恶性肿瘤", "肿瘤", "癌", "化疗", "放疗", "靶向治疗", "免疫治疗"),
    ),
)

_LUXIAN_RULE_FAMILY_BY_ID: dict[str, str] = {
    **{f"LX0609-{index:03d}": "critical" for index in (7, 8, 9)},
    **{f"LX0609-{index:03d}": "imaging" for index in (10, 11, 12)},
    **{f"LX0609-{index:03d}": "culture" for index in (14, 15)},
    **{f"LX0609-{index:03d}": "consultation" for index in (20, 21, 22, 23)},
    **{f"LX0609-{index:03d}": "surgery" for index in (3, 24, 25, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40)},
    **{f"LX0609-{index:03d}": "transfusion" for index in (41, 42, 43, 44, 45, 46, 47, 48, 49)},
    **{f"LX0609-{index:03d}": "pathology_tumor" for index in (13, 19, 26, 27)},
}

_STRUCTURED_DEPENDENCY_MARKERS = (
    "医嘱",
    "费用",
    "收费",
    "报告时间",
    "检查时间",
    "培养结果",
    "手术时间",
    "麻醉记录",
    "输血记录",
)

_RULE_METADATA_KEYS = {
    "rule",
    "rules",
    "rule_id",
    "rule_code",
    "rule_name",
    "qc_point_id",
    "customer_rule_id",
    "customer_rule_name",
    "name",
    "description",
    "trigger_condition",
    "non_trigger_condition",
    "dependency_type",
    "data_status",
    "applicable_documents",
    "applicable_document_labels",
    "data_dependencies",
    "missing_sources",
    "missing_source",
    "missing_fields",
    "missing_field",
    "missing_documents",
    "missing_document",
    "required_sources",
    "required_fields",
    "required_documents",
    "evidence_requirements",
    "document_hits",
    "mapped_rule_ids",
    "selected_rule_ids",
    "scoped_customer_rule_ids",
    "record_rule_map",
    "summary",
    "diagnostic_summary",
    "result_summary",
}


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_norm_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.append(_norm_text(item))
        return "\n".join(parts)
    return str(value)


def _record_payload_text(value: Any) -> str:
    """Extract patient-record text from mixed evidence payloads.

    The trigger gate must not treat rule metadata such as "LX0609-045 输血记录"
    as a patient trigger fact. Keep actual source document values, but skip
    rule/catalog keys that can contain the target defect wording.
    """

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_record_payload_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            key_text = str(key).strip()
            if key_text in _RULE_METADATA_KEYS:
                continue
            parts.append(_record_payload_text(item))
        return "\n".join(part for part in parts if part.strip())
    return str(value)


def _rule_text(rule: dict[str, Any]) -> str:
    fields = [
        rule.get("rule_id"),
        rule.get("rule_name"),
        rule.get("name"),
        rule.get("description"),
        rule.get("trigger_condition"),
        rule.get("non_trigger_condition"),
        rule.get("dependency_type"),
        rule.get("data_status"),
        rule.get("applicable_documents"),
        rule.get("applicable_document_labels"),
        rule.get("data_dependencies"),
    ]
    return "\n".join(_norm_text(item) for item in fields if item is not None)


def _find_family(rule: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
    explicit_family = _LUXIAN_RULE_FAMILY_BY_ID.get(rule_id)
    if explicit_family:
        for family, rule_markers, record_markers in _FAMILY_KEYWORDS:
            if family == explicit_family:
                return family, rule_markers, record_markers

    text = _rule_text(rule)
    for family, rule_markers, record_markers in _FAMILY_KEYWORDS:
        if any(marker in text for marker in rule_markers):
            return family, rule_markers, record_markers
    return None


def _find_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(keyword for keyword in keywords if keyword and keyword in text)


_NEGATED_TRIGGER_PHRASES: dict[str, tuple[str, ...]] = {
    "surgery": ("未行手术", "未做手术", "无手术", "未手术", "无需手术", "未予手术治疗"),
    "transfusion": (
        "输血史",
        "否认输血史",
        "无输血史",
        "未输血",
        "无输血",
        "未行输血",
        "未予输血",
        "未输注血",
        "无需输血",
    ),
    "consultation": ("未请会诊", "无会诊", "未会诊", "无需会诊", "未申请会诊"),
    "rescue": ("未抢救", "无抢救", "未行抢救", "无需抢救"),
    "critical": ("未下达病危医嘱", "无病危医嘱", "未下达病重医嘱", "无病重医嘱", "未下达病危", "未下达病重"),
    "imaging": ("未行CT", "未做CT", "无CT检查", "未行MRI", "未做MRI", "无MRI检查", "未行磁共振", "未做磁共振"),
    "culture": ("未送培养", "未做培养", "无培养", "未行细菌培养", "未见培养报告"),
    "pathology_tumor": ("未做病理", "无病理", "未行病理", "未化疗", "无化疗", "未行化疗"),
}

_TRANSFUSION_DOCUMENT_MARKERS = (
    "输血申请",
    "输血记录",
    "输血医嘱",
    "输血知情同意",
)

_TRANSFUSION_CONTEXT_NEGATIVE_MARKERS = (
    "质控点",
    "规则",
    "触发关键词",
    "匹配关键词",
    "数据缺口",
    "缺少",
    "缺失",
    "未见",
    "未发现",
    "无",
    "不完整",
    "应包含",
    "映射执行规则",
)

_TRANSFUSION_CLINICAL_CONTEXT_MARKERS = (
    "血制品",
    "红细胞",
    "悬浮红细胞",
    "血浆",
    "血小板",
    "输注去白",
    "输注红细胞",
    "输注血浆",
    "输注血小板",
    "交叉配血",
    "配血",
    "血型",
    "ABO",
    "Rh",
    "血红蛋白",
    "HGB",
    "Hb",
    "用血",
    "备血",
    "血袋",
)

_TRANSFUSION_BLOOD_PRODUCT_MARKERS = (
    "血制品",
    "去白悬浮红细胞",
    "悬浮红细胞",
    "红细胞悬液",
    "洗涤红细胞",
    "冰冻血浆",
    "新鲜冰冻血浆",
    "血浆",
    "血小板",
    "冷沉淀",
)

_TRANSFUSION_STRONG_ACTION_MARKERS = (
    "输血",
    "输注",
    "医嘱",
    "申请",
    "记录",
    "收费",
    "费用",
    "血费",
    "用血",
    "备血",
)

_INTRAOPERATIVE_TRANSFUSION_PATTERNS = (
    re.compile(r"(术中|手术中|麻醉记录|手术记录).{0,40}(输血|输注.{0,12}(红细胞|血浆|血小板|血制品))"),
    re.compile(r"(输血|输注.{0,12}(红细胞|血浆|血小板|血制品)).{0,40}(术中|手术中|麻醉记录|手术记录)"),
)

_IMAGING_REPORT_PATTERNS = (
    re.compile(r"(CT|MRI|磁共振).{0,24}(检查报告|报告时间|报告结果|报告结论|阳性报告|检查时间)"),
    re.compile(r"(检查报告|报告时间|报告结果|报告结论|检查时间).{0,24}(CT|MRI|磁共振)"),
)

_IMAGING_ORDER_WITH_REPORT_TIME_PATTERN = re.compile(r"(CT|MRI|磁共振).{0,40}(医嘱|申请|检查).{0,40}(报告时间|报告结果|检查时间)")

_CULTURE_REPORT_PATTERNS = (
    re.compile(r"(细菌培养|尿培养|血培养|痰培养|培养).{0,24}(报告|报告时间|培养结果|药敏结果|阳性结果)"),
    re.compile(r"(培养报告|培养结果|药敏报告|药敏结果|阳性菌|报告时间).{0,24}(细菌|培养|药敏|大肠埃希菌|金黄色葡萄球菌|铜绿假单胞菌)"),
)

_CULTURE_ORDER_WITH_REPORT_TIME_PATTERN = re.compile(r"(培养|药敏).{0,40}(医嘱|申请|送检).{0,40}(报告时间|培养结果|药敏结果)")

_SURGERY_FACT_LABELS = (
    "手术名称",
    "手术项目",
    "手术开始时间",
    "手术结束时间",
    "麻醉方式",
    "术者",
    "手术医师",
    "术中诊断",
    "术后诊断",
)

_SURGERY_EMPTY_LABEL_VALUES = (
    "手术编码",
    "手术医生签名",
    "术前小结",
    "术中诊断",
    "术后诊断",
    "切口",
    "麻醉",
    "科室",
    "病房",
    "记录者",
)

_SURGERY_NEGATIVE_CONTEXT = ("既往", "既往史", "曾行", "手术史", "痔疮手术")
_SURGERY_CONTEXT_REQUIRED_MARKERS = (
    "手术名称",
    "术前诊断",
    "术后诊断",
    "术中所见",
    "手术经过",
    "手术记录",
)
_SURGERY_HISTORY_MARKERS = (
    "既往史",
    "个人史",
    "家族史",
    "病史",
    "既往",
    "曾行",
    "术后复查",
)

_PATHOLOGY_TUMOR_STRONG_PATTERNS = (
    re.compile(r"病理(报告|检查|诊断|结果)"),
    re.compile(r"(腺癌|鳞癌|癌|恶性肿瘤|化疗|放疗|靶向治疗|免疫治疗|淋巴结转移)"),
    re.compile(r"(胃癌|肺癌|乳腺癌|结直肠癌|肝癌|肠癌|宫颈癌|卵巢癌|淋巴瘤)"),
)

_LX0609_019_PATHOLOGY_SPECIMEN_PATTERNS = (
    re.compile(r"病理(报告|检查|诊断|结果)"),
    re.compile(r"(活检|穿刺活检|取材|送检|送病理|送病检|标本|冰冻病理|术中冰冻)"),
    re.compile(r"(手术记录|术中|手术).{0,50}(取材|标本|送检|送病理|送病检|病理)"),
    re.compile(r"(取材|标本|送检|送病理|送病检|病理).{0,50}(手术记录|术中|手术)"),
)

_CHEMO_STRONG_PATTERNS = (
    re.compile(r"(化疗医嘱|化疗记录|化学治疗记录|辅助化疗|新辅助化疗|化疗方案)"),
    re.compile(r"(奥沙利铂|卡培他滨|顺铂|紫杉醇|多西他赛|吉西他滨|替吉奥|氟尿嘧啶|伊立替康|依托泊苷)"),
    re.compile(r"\b(XELOX|FOLFOX|FOLFIRI|TP|GP|TC)\b", re.IGNORECASE),
)

_ANTIBIOTIC_ORDER_STRONG_PATTERNS = (
    re.compile(r"(抗菌药物|抗生素|预防用药|预防使用抗菌药物|预防使用抗生素).{0,50}(医嘱|用药|开始|停止|术前|术后)"),
    re.compile(r"(医嘱|用药|开始|停止|术前|术后).{0,50}(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)"),
    re.compile(r"(头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南).{0,50}(医嘱|静滴|静脉|口服|预防|术前|术后)"),
)

_ANTIBIOTIC_NEGATIVE_MARKERS = (
    "未见",
    "未查见",
    "未发现",
    "无",
    "未予",
    "未使用",
    "未用",
    "未开立",
    "未下达",
    "未记录",
    "否认",
)

_INCISION_I_II_EXPLICIT_PATTERNS = (
    re.compile(r"(Ⅰ|I|一|1)\s*类切口|清洁切口"),
    re.compile(r"(Ⅱ|II|二|2)\s*类切口|清洁[-－—]污染切口"),
)

_INCISION_I_II_SURGERY_PATTERNS = (
    re.compile(r"(甲状腺|乳腺良性肿物|腹股沟疝|脂肪瘤).{0,30}(手术|切除|修补)"),
    re.compile(r"(闭合骨折内固定|关节置换|白内障|择期颅脑肿瘤).{0,30}(手术|切除|置换|内固定)"),
    re.compile(r"(胆囊切除|胃大部切除|胃切除|结肠切除|直肠切除|结直肠).{0,30}(手术|切除|吻合)"),
    re.compile(r"(剖宫产|子宫|输卵管).{0,30}(手术|切除|修补|成形)"),
    re.compile(r"(耳鼻喉|口腔|经尿道前列腺电切|前列腺电切|输尿管结石).{0,30}(手术|治疗|碎石|取石)"),
)

_INCISION_CONTAMINATED_EXCLUSION_MARKERS = (
    "脓液",
    "化脓",
    "穿孔",
    "破裂",
    "坏疽",
    "污染切口",
    "感染切口",
    "急性炎症",
)

_ANTIBIOTIC_START_TIME_PATTERNS = (
    re.compile(r"(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南).{0,80}(\d{4}[-/年]\d{1,2}|\d{1,2}:\d{2}|术前\s*\d+\s*分钟|开始|起始|下达|开立)"),
    re.compile(r"(\d{4}[-/年]\d{1,2}|\d{1,2}:\d{2}|术前\s*\d+\s*分钟|开始|起始|下达|开立).{0,80}(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)"),
)

_ANTIBIOTIC_STOP_TIME_PATTERNS = (
    re.compile(r"(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南).{0,100}(停止|停用|结束|术后\s*\d+\s*(小时|天)|连用\s*\d+\s*天|使用\s*\d+\s*天|持续\s*\d+\s*天)"),
    re.compile(r"(停止|停用|结束|术后\s*\d+\s*(小时|天)|连用\s*\d+\s*天|使用\s*\d+\s*天|持续\s*\d+\s*天).{0,100}(抗菌药物|抗生素|头孢|青霉素|左氧氟沙星|甲硝唑|阿莫西林|克林霉素|哌拉西林|亚胺培南|美罗培南)"),
)

_LEVEL_4_SURGERY_PATTERNS = (
    re.compile(r"(四级|4级|Ⅳ级|IV级).{0,18}(手术|操作)"),
    re.compile(r"(手术级别|手术等级|手术分级)[:：]?\s*(四级|4级|Ⅳ级|IV级)"),
    re.compile(r"(重大手术|疑难复杂手术|高风险手术)"),
)

_LX0609_024_MALIGNANT_TUMOR_PATTERNS = (
    re.compile(r"(恶性肿瘤|腺癌|鳞癌|未分化癌|低分化癌|中分化癌|高分化癌|淋巴瘤|肉瘤|黑色素瘤)"),
    re.compile(r"(癌组织|癌细胞|癌栓|癌转移|癌性|癌根治)"),
    re.compile(r"(胃癌|肺癌|乳腺癌|结直肠癌|结肠癌|直肠癌|肝癌|胰腺癌|胆管癌|胆囊癌|食管癌|宫颈癌|卵巢癌|甲状腺癌|前列腺癌|膀胱癌|肾癌)"),
    re.compile(r"\bC\d{2}(?:\.\d+)?\b", re.IGNORECASE),
)

_LX0609_024_TUMOR_SURGERY_PATTERNS = (
    re.compile(r"(癌|恶性肿瘤).{0,30}(根治术|切除术|清扫术|淋巴结清扫)"),
    re.compile(r"(根治术|癌根治|肿瘤切除|淋巴结清扫|D[23]淋巴结清扫|区域淋巴结清扫)"),
    re.compile(r"(胃癌|肺癌|乳腺癌|结直肠癌|结肠癌|直肠癌|肝癌|胰腺癌|胆管癌|胆囊癌|食管癌|宫颈癌|卵巢癌|甲状腺癌|前列腺癌|膀胱癌|肾癌).{0,30}(根治术|切除术|清扫术|淋巴结清扫)"),
)

_LX0609_024_SPECIMEN_PATHOLOGY_PATTERNS = (
    re.compile(r"(送检|送病理|送病检|标本|取材|活检|冰冻病理|术中冰冻).{0,80}(恶性|腺癌|鳞癌|癌|癌转移)"),
    re.compile(r"(恶性|腺癌|鳞癌|癌|癌转移).{0,80}(送检|送病理|送病检|标本|取材|活检|冰冻病理|术中冰冻)"),
)

_LX0609_024_SURGERY_CONTEXT_MARKERS = (
    "手术记录",
    "手术名称",
    "术中所见",
    "手术经过",
    "术前诊断",
    "术后诊断",
)

_CRITICAL_ORDER_RULE_CONFIG: dict[str, tuple[str, tuple[str, ...]]] = {
    "LX0609-008": ("病重医嘱", ("病重医嘱起止时间",)),
    "LX0609-009": ("病危医嘱", ("病危医嘱起止时间",)),
}


def _keyword_has_positive_context(text: str, keyword: str, negated_phrases: tuple[str, ...]) -> bool:
    if not keyword:
        return False
    start = 0
    while True:
        position = text.find(keyword, start)
        if position < 0:
            return False
        window = text[max(0, position - 10): position + len(keyword) + 10]
        if not any(phrase in window for phrase in negated_phrases):
            return True
        start = position + len(keyword)


def _find_positive_keywords(text: str, keywords: tuple[str, ...], family_name: str) -> tuple[str, ...]:
    negated_phrases = _NEGATED_TRIGGER_PHRASES.get(family_name, ())
    if not negated_phrases:
        return _find_keywords(text, keywords)
    if family_name == "imaging" and not _has_imaging_report_context(text):
        return ()
    if family_name == "culture" and not _has_culture_report_context(text):
        return ()
    if family_name == "transfusion" and not _has_transfusion_strong_trigger(text):
        return ()
    matched: list[str] = []
    for keyword in keywords:
        if not _keyword_has_positive_context(text, keyword, negated_phrases):
            continue
        if family_name == "surgery" and not _has_surgery_clinical_context(text, keyword):
            continue
        if family_name == "pathology_tumor" and not _has_pathology_tumor_clinical_context(text):
            continue
        if family_name == "transfusion" and keyword in _TRANSFUSION_DOCUMENT_MARKERS:
            start = 0
            has_patient_context = False
            while True:
                position = text.find(keyword, start)
                if position < 0:
                    break
                line_start = text.rfind("\n", 0, position) + 1
                line_end = text.find("\n", position)
                if line_end < 0:
                    line_end = len(text)
                line = text[line_start:line_end]
                context = text[max(0, position - 80): position + len(keyword) + 120]
                if (
                    not any(marker in line for marker in _TRANSFUSION_CONTEXT_NEGATIVE_MARKERS)
                    and any(marker in context for marker in _TRANSFUSION_CLINICAL_CONTEXT_MARKERS)
                ):
                    has_patient_context = True
                    break
                start = position + len(keyword)
            if not has_patient_context:
                continue
        matched.append(keyword)
    return tuple(matched)


def _has_imaging_report_context(text: str) -> bool:
    if any(pattern.search(text) for pattern in _IMAGING_REPORT_PATTERNS):
        return True
    return bool(_IMAGING_ORDER_WITH_REPORT_TIME_PATTERN.search(text))


def _has_culture_report_context(text: str) -> bool:
    if any(pattern.search(text) for pattern in _CULTURE_REPORT_PATTERNS):
        return True
    return bool(_CULTURE_ORDER_WITH_REPORT_TIME_PATTERN.search(text))


def _has_transfusion_strong_trigger(text: str) -> bool:
    for marker in _TRANSFUSION_DOCUMENT_MARKERS:
        start = 0
        while True:
            position = text.find(marker, start)
            if position < 0:
                break
            line_start = text.rfind("\n", 0, position) + 1
            line_end = text.find("\n", position)
            if line_end < 0:
                line_end = len(text)
            line = text[line_start:line_end]
            context = text[max(0, position - 80): position + len(marker) + 120]
            if (
                not any(negative in line for negative in _TRANSFUSION_CONTEXT_NEGATIVE_MARKERS)
                and any(clinical_marker in context for clinical_marker in _TRANSFUSION_CLINICAL_CONTEXT_MARKERS)
            ):
                return True
            start = position + len(marker)

    for product in _TRANSFUSION_BLOOD_PRODUCT_MARKERS:
        start = 0
        while True:
            position = text.find(product, start)
            if position < 0:
                break
            context = text[max(0, position - 60): position + len(product) + 80]
            if (
                any(marker in context for marker in _TRANSFUSION_STRONG_ACTION_MARKERS)
                and not any(negative in context for negative in ("否认输血史", "无输血史", "未输血", "未予输血"))
            ):
                return True
            start = position + len(product)
    return False


def _label_value_has_content(text: str, labels: tuple[str, ...]) -> bool:
    for line in text.splitlines():
        for label in labels:
            marker_options = (f"{label}：", f"{label}:")
            marker = next((item for item in marker_options if item in line), "")
            if not marker:
                continue
            value = line.split(marker, 1)[1].strip()
            if not value:
                continue
            value = re.split(r"[；;。]", value, maxsplit=1)[0].strip()
            if not value or any(empty_marker in value for empty_marker in _SURGERY_EMPTY_LABEL_VALUES):
                continue
            if len(value) >= 2:
                return True
    return False


def _has_surgery_clinical_context(text: str, keyword: str) -> bool:
    if _label_value_has_content(text, _SURGERY_FACT_LABELS):
        return True

    start = 0
    while True:
        position = text.find(keyword, start)
        if position < 0:
            break
        context = text[max(0, position - 40): position + len(keyword) + 80]
        if any(marker in context for marker in _SURGERY_NEGATIVE_CONTEXT):
            start = position + len(keyword)
            continue
        if re.search(r"(行|拟行|完成|实施).{0,24}(手术|切除|修补|固定|清创|探查)", context):
            return True
        if "术中见" in context or "切口" in context and "缝合" in context:
            return True
        start = position + len(keyword)
    return False


def _has_pathology_tumor_clinical_context(text: str) -> bool:
    if any(pattern.search(text) for pattern in _PATHOLOGY_TUMOR_STRONG_PATTERNS):
        return True
    return False


def _has_lx0609_019_pathology_specimen_context(text: str) -> tuple[bool, tuple[str, ...]]:
    matches = _find_regex_matches(text, _LX0609_019_PATHOLOGY_SPECIMEN_PATTERNS)
    return bool(matches), matches[:8]


def _has_pathology_report_context(text: str) -> tuple[bool, tuple[str, ...]]:
    patterns = (
        re.compile(r"(病理报告|病理检查报告|病理诊断|病理结果|活检报告).{0,80}(报告时间|记录时间|诊断|结果|提示|出具)"),
        re.compile(r"(报告时间|记录时间|诊断|结果|提示|出具).{0,80}(病理报告|病理检查报告|病理诊断|病理结果|活检报告)"),
        re.compile(r"【[^】]*(病理|活检)[^】]*】.{0,120}(诊断|结果|报告|提示|标本|取材)"),
    )
    matches = _find_regex_matches(text, patterns)
    if matches and "病理报告" in text and "病理报告" not in matches:
        matches = ("病理报告", *matches)
    return bool(matches), matches[:8]


def _has_pathology_report_time_context(text: str) -> bool:
    patterns = (
        re.compile(r"(病理报告|病理检查报告|病理诊断|病理结果|活检报告).{0,80}(报告时间|记录时间|提交时间|出具时间|报告出具|出具).{0,30}\d{4}[-/年]\d{1,2}"),
        re.compile(r"(报告时间|记录时间|提交时间|出具时间|报告出具|出具).{0,30}\d{4}[-/年]\d{1,2}.{0,80}(病理报告|病理检查报告|病理诊断|病理结果|活检报告)"),
        re.compile(r"【[^】]*(病理|活检)[^】]*】.{0,80}(报告时间|记录时间|提交时间|出具时间|报告出具|出具).{0,30}\d{4}[-/年]\d{1,2}"),
    )
    return any(pattern.search(text) for pattern in patterns)


def _rule_requires_pathology_report_time(rule: dict[str, Any]) -> bool:
    dependency_text = _norm_text(rule.get("data_dependencies"))
    return "病理报告时间" in dependency_text or "病理检查报告时间" in dependency_text


def _has_chemo_clinical_context(text: str) -> tuple[bool, tuple[str, ...]]:
    matches = _find_regex_matches(text, _CHEMO_STRONG_PATTERNS)
    return bool(matches), matches[:8]


def _has_antibiotic_order_context(text: str) -> tuple[bool, tuple[str, ...]]:
    matches: list[str] = []
    for pattern in _ANTIBIOTIC_ORDER_STRONG_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            if not value:
                continue
            context = text[max(0, match.start() - 12): min(len(text), match.end() + 12)]
            if any(marker in context for marker in _ANTIBIOTIC_NEGATIVE_MARKERS):
                continue
            if value not in matches:
                matches.append(value)
    return bool(matches), matches[:8]


def _has_lx0609_028_class_i_ii_incision_context(text: str) -> tuple[bool, tuple[str, ...]]:
    if not text.strip():
        return False, ()

    explicit_matches = _find_regex_matches(text, _INCISION_I_II_EXPLICIT_PATTERNS)
    surgery_matches = _find_regex_matches(text, _INCISION_I_II_SURGERY_PATTERNS)
    matches = tuple(dict.fromkeys((*explicit_matches, *surgery_matches)))[:8]
    if not matches:
        return False, ()

    # If the same chart clearly describes contaminated/infected surgery, do not
    # infer I/II incision only from a generic surgery name.
    if not explicit_matches and any(marker in text for marker in _INCISION_CONTAMINATED_EXCLUSION_MARKERS):
        return False, ()
    return True, matches


def _missing_lx0609_028_antibiotic_time_fields(text: str) -> tuple[str, ...]:
    missing: list[str] = []
    if not any(pattern.search(text) for pattern in _ANTIBIOTIC_START_TIME_PATTERNS):
        missing.append("抗菌药物医嘱开始时间")
    if not any(pattern.search(text) for pattern in _ANTIBIOTIC_STOP_TIME_PATTERNS):
        missing.append("抗菌药物医嘱停止时间")
    return tuple(missing)


def _has_level_4_surgery_context(text: str) -> tuple[bool, tuple[str, ...]]:
    matches = _find_regex_matches(text, _LEVEL_4_SURGERY_PATTERNS)
    return bool(matches), matches[:8]


def _has_intraoperative_transfusion_context(text: str) -> tuple[bool, tuple[str, ...]]:
    matches = _find_regex_matches(text, _INTRAOPERATIVE_TRANSFUSION_PATTERNS)
    return bool(matches), matches[:8]


def _find_regex_matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(0).strip()
            if value and value not in matches:
                matches.append(value)
    return tuple(matches)


def _surgery_context_windows(text: str, *, radius: int = 520) -> list[str]:
    windows: list[str] = []
    for marker in _LX0609_024_SURGERY_CONTEXT_MARKERS:
        start = 0
        while True:
            position = text.find(marker, start)
            if position < 0:
                break
            window = text[position: min(len(text), position + radius)]
            if window and window not in windows:
                windows.append(window)
            start = position + len(marker)
    return windows


def _window_has_current_surgery_anchor(window: str) -> bool:
    return any(marker in window for marker in _SURGERY_CONTEXT_REQUIRED_MARKERS)


def _window_looks_like_history_only(window: str) -> bool:
    head = window[:160]
    if not any(marker in head for marker in _SURGERY_HISTORY_MARKERS):
        return False
    return not _window_has_current_surgery_anchor(window)


def _window_is_current_malignant_tumor_surgery(window: str) -> tuple[bool, tuple[str, ...]]:
    if not window.strip():
        return False, ()
    if _window_looks_like_history_only(window):
        return False, ()

    malignant_markers = _find_regex_matches(window, _LX0609_024_MALIGNANT_TUMOR_PATTERNS)
    tumor_surgery_markers = _find_regex_matches(window, _LX0609_024_TUMOR_SURGERY_PATTERNS)
    specimen_pathology_markers = _find_regex_matches(window, _LX0609_024_SPECIMEN_PATHOLOGY_PATTERNS)
    if tumor_surgery_markers and malignant_markers and _window_has_current_surgery_anchor(window):
        return True, tuple(dict.fromkeys((*malignant_markers, *tumor_surgery_markers)))[:8]
    if specimen_pathology_markers and _window_has_current_surgery_anchor(window):
        return True, tuple(dict.fromkeys((*malignant_markers, *specimen_pathology_markers)))[:8]
    if tumor_surgery_markers and any(marker in window for marker in ("手术名称", "术前诊断", "术后诊断", "术中所见")):
        return True, tuple(dict.fromkeys((*malignant_markers, *tumor_surgery_markers)))[:8]
    if malignant_markers and _window_has_current_surgery_anchor(window) and re.search(
        r"(手术名称|拟行|实施|完成).{0,100}"
        r"(根治|癌根治|淋巴结清扫|区域淋巴结清扫|肿瘤切除|胃切除|肺叶切除|乳腺切除|结肠切除|直肠切除|肝切除|胰十二指肠|甲状腺切除)",
        window,
    ):
        return True, tuple(dict.fromkeys((*malignant_markers, *tumor_surgery_markers)))[:8]
    return False, ()


def _has_lx0609_024_malignant_tumor_surgery_context(text: str) -> tuple[bool, tuple[str, ...]]:
    if not text.strip():
        return False, ()

    matched_markers: list[str] = []
    for window in _surgery_context_windows(text):
        applicable, markers = _window_is_current_malignant_tumor_surgery(window)
        if applicable:
            matched_markers.extend(markers)
    if matched_markers:
        return True, tuple(dict.fromkeys(matched_markers))[:8]

    # Fall back only for compact texts that directly describe a malignant tumor
    # operation without a formal "手术记录/手术名称" section. Do not let a remote
    # history diagnosis such as "既往肺癌" trigger the current-surgery rule.
    tumor_surgery_markers = _find_regex_matches(text, _LX0609_024_TUMOR_SURGERY_PATTERNS)
    malignant_markers = _find_regex_matches(text, _LX0609_024_MALIGNANT_TUMOR_PATTERNS)
    if (
        tumor_surgery_markers
        and malignant_markers
        and _window_has_current_surgery_anchor(text)
        and not any(marker in text[:160] for marker in ("既往史", "手术史"))
    ):
        return True, tuple(dict.fromkeys((*malignant_markers, *tumor_surgery_markers)))[:8]
    return False, ()


def _has_positive_critical_order(text: str, order_keyword: str) -> bool:
    if not text.strip() or not order_keyword:
        return False
    return _keyword_has_positive_context(
        text,
        order_keyword,
        _NEGATED_TRIGGER_PHRASES.get("critical", ()),
    )


def _critical_order_has_timing_context(text: str, order_keyword: str) -> bool:
    if not text.strip() or not order_keyword:
        return False
    start = 0
    timing_markers = ("起始时间", "开始时间", "下达时间", "停止时间", "未停止", "持续执行", "仍在执行")
    while True:
        position = text.find(order_keyword, start)
        if position < 0:
            return False
        context = text[max(0, position - 80): position + len(order_keyword) + 160]
        if _keyword_has_positive_context(context, order_keyword, _NEGATED_TRIGGER_PHRASES.get("critical", ())) and any(
            marker in context for marker in timing_markers
        ):
            return True
        start = position + len(order_keyword)


def _payload_first_course_has_content(value: Any) -> bool | None:
    if not isinstance(value, dict):
        return None
    timeline = value.get("programmatic_timeline")
    if not isinstance(timeline, dict):
        return None
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return None
    first_courses = [item for item in list(docs.get("first_course_record") or []) if isinstance(item, dict)]
    if not first_courses:
        return False
    for item in first_courses:
        text = "\n".join(
            str(item.get(key) or "").strip()
            for key in ("content", "raw_text", "content_preview")
            if str(item.get(key) or "").strip()
        )
        normalized = "".join(text.split())
        if normalized and normalized not in {"首次病程记录", "首次病程"} and len(normalized) >= 20:
            return True
    return False


def _record_text_has_first_course_content(text: str) -> bool:
    for marker in ("首次病程记录", "首次病程"):
        start = 0
        while True:
            position = text.find(marker, start)
            if position < 0:
                break
            window = text[position: position + 600]
            cleaned = re.sub(r"(首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|[:：\s\dT-]+)", "", window)
            if len(cleaned.strip()) >= 30:
                return True
            start = position + len(marker)
    return False


def evaluate_luxian_0609_trigger_gates(
    *,
    rules: list[dict[str, Any]],
    visit_id: str = "",
    medical_text: str = "",
    evidence_payload: dict[str, Any] | None = None,
) -> dict[str, Luxian0609GateDecision]:
    """Return conservative trigger-gate decisions for Luxian 0609 customer rules.

    The gate is intentionally conservative: if a trigger cannot be ruled out from
    available text/bundle evidence, it returns ``unknown`` and lets the normal
    execution path decide. Only clear absence of a trigger produces
    ``absent``/``not_applicable``.
    """

    del visit_id  # reserved for future structured loaders; do not special-case visits.
    record_text = "\n".join(
        part for part in (_norm_text(medical_text), _record_payload_text(evidence_payload or {})) if part.strip()
    )
    decisions: dict[str, Luxian0609GateDecision] = {}

    for rule in rules:
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        if not rule_id:
            continue
        first_course_has_content = _payload_first_course_has_content(evidence_payload or {})
        if rule_id == "LX0609-016" and (
            first_course_has_content is False
            or (first_course_has_content is None and not _record_text_has_first_course_content(record_text))
        ):
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_DATA_GAP,
                reason="首次病程记录缺失或正文为空，无法安全执行复制病历比对",
                data_gap_fields=("首次病程记录正文",),
            )
            continue
        if rule_id == "LX0609-013":
            has_pathology_report, matched_markers = _has_pathology_report_context(record_text)
            if not has_pathology_report:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现病理报告或病理检查结果强触发事实，本次不进入病理结果回看规则",
                )
                continue
            if _rule_requires_pathology_report_time(rule) and not _has_pathology_report_time_context(record_text):
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_DATA_GAP,
                    reason="已发现病理报告或病理检查结果事实，但缺少病理报告时间，无法完成自动判定",
                    data_gap_fields=("病理报告时间",),
                    matched_keywords=matched_markers,
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现病理报告或病理检查结果事实，进入病理结果记录复核",
                matched_keywords=matched_markers,
            )
            continue
        if rule_id == "LX0609-019":
            has_pathology_specimen, matched_markers = _has_lx0609_019_pathology_specimen_context(record_text)
            if not has_pathology_specimen:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现病理检查、活检取材或手术送检等适用事实，本次不进入取材记录规则",
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现病理检查或取材送检事实，进入取材记录复核",
                matched_keywords=matched_markers,
            )
            continue
        if rule_id == "LX0609-028":
            has_class_i_ii_incision, incision_markers = _has_lx0609_028_class_i_ii_incision_context(record_text)
            if not has_class_i_ii_incision:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现I类/II类切口或常见清洁、清洁-污染切口手术事实，本次不进入抗菌药物预防用药时限规则",
                )
                continue
            has_antibiotic_order, antibiotic_markers = _has_antibiotic_order_context(record_text)
            if not has_antibiotic_order:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="已发现I类/II类切口相关手术，但未发现抗菌药物医嘱或预防使用抗生素事实，本次不进入抗菌药物预防用药时限规则",
                    matched_keywords=incision_markers,
                )
                continue
            missing_time_fields = _missing_lx0609_028_antibiotic_time_fields(record_text)
            if missing_time_fields:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_DATA_GAP,
                    reason="已发现I类/II类切口相关手术及预防抗菌药物医嘱，但缺少完成时限判定所需的起止时间字段",
                    data_gap_fields=missing_time_fields,
                    matched_keywords=tuple(dict.fromkeys((*incision_markers, *antibiotic_markers)))[:8],
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现I类/II类切口相关手术及预防抗菌药物起止时间，进入抗菌药物使用时限复核",
                matched_keywords=tuple(dict.fromkeys((*incision_markers, *antibiotic_markers)))[:8],
            )
            continue
        if rule_id == "LX0609-024":
            is_applicable, matched_markers = _has_lx0609_024_malignant_tumor_surgery_context(record_text)
            if not is_applicable:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现恶性肿瘤相关手术或淋巴结清扫适用场景",
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现恶性肿瘤相关手术场景，进入淋巴结清扫记录复核",
                matched_keywords=matched_markers,
            )
            continue
        if rule_id == "LX0609-026":
            has_chemo, matched_markers = _has_chemo_clinical_context(record_text)
            if not has_chemo:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现明确化疗医嘱或化疗记录，本次不进入化疗记录一致性规则",
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现化疗医嘱或化疗记录，进入化疗记录一致性复核",
                matched_keywords=matched_markers,
            )
            continue
        if rule_id == "LX0609-040":
            has_level_4, matched_markers = _has_level_4_surgery_context(record_text)
            if not has_level_4:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现四级手术或重大手术适用证据，本次不进入MDT讨论规则",
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现四级手术或重大手术线索，进入MDT讨论记录复核",
                matched_keywords=matched_markers,
            )
            continue
        if rule_id == "LX0609-048":
            has_intraop_transfusion, matched_markers = _has_intraoperative_transfusion_context(record_text)
            if not has_intraop_transfusion:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason="未发现术中输血或麻醉/手术记录中的输血事实，本次不进入术中输血规则",
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason="已发现术中输血事实，进入术中输血记录复核",
                matched_keywords=matched_markers,
            )
            continue
        critical_config = _CRITICAL_ORDER_RULE_CONFIG.get(rule_id)
        if critical_config is not None:
            order_keyword, default_gap_fields = critical_config
            if not _has_positive_critical_order(record_text, order_keyword):
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_ABSENT,
                    reason=f"未发现明确的{order_keyword}触发事实，本次不进入查房频次规则",
                )
                continue

            data_dependencies = tuple(
                str(item).strip()
                for item in list(rule.get("data_dependencies") or [])
                if str(item).strip()
            )
            gap_fields = ()
            if not _critical_order_has_timing_context(record_text, order_keyword):
                gap_fields = tuple(
                    dep
                    for dep in data_dependencies
                    if any(marker in dep for marker in default_gap_fields)
                ) or default_gap_fields
            if gap_fields:
                decisions[rule_id] = Luxian0609GateDecision(
                    rule_id=rule_id,
                    status=TRIGGER_DATA_GAP,
                    reason=f"已发现{order_keyword}，但缺少完成频次判定所需的起止时间字段",
                    data_gap_fields=gap_fields,
                    matched_keywords=(order_keyword,),
                )
                continue
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_PRESENT,
                reason=f"已发现{order_keyword}，进入查房频次复核",
                matched_keywords=(order_keyword,),
            )
            continue
        family = _find_family(rule)
        data_dependencies = tuple(
            str(item).strip()
            for item in list(rule.get("data_dependencies") or [])
            if str(item).strip()
        )
        if family is None:
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_UNKNOWN,
                reason="未识别到可安全门控的触发族，进入常规执行",
            )
            continue

        family_name, _rule_markers, record_markers = family
        matched = _find_positive_keywords(record_text, record_markers, family_name)
        if not matched:
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_ABSENT,
                reason=f"病历文本和证据中未发现{family_name}相关触发事实",
            )
            continue

        gap_fields = tuple(
            dep
            for dep in data_dependencies
            if any(marker in dep for marker in _STRUCTURED_DEPENDENCY_MARKERS)
            and dep not in record_text
        )
        if gap_fields and any(marker in _rule_text(rule) for marker in ("跨表联查", "医嘱", "费用", "报告时间")):
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_DATA_GAP,
                reason="已发现触发事实，但缺少完成判定所需的结构化字段",
                data_gap_fields=gap_fields,
                matched_keywords=matched,
            )
            continue

        decisions[rule_id] = Luxian0609GateDecision(
            rule_id=rule_id,
            status=TRIGGER_PRESENT,
            reason="已发现相关触发事实，进入常规执行",
            matched_keywords=matched,
        )
    return decisions


def decision_to_result(rule: dict[str, Any], decision: Luxian0609GateDecision) -> dict[str, Any] | None:
    status = decision.status if decision.status in _KNOWN_STATUSES else TRIGGER_UNKNOWN
    if status not in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
        return None

    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or decision.rule_id).strip().upper()
    rule_name = str(rule.get("name") or rule.get("rule_name") or rule_id)
    if status == TRIGGER_ABSENT:
        result_status = "not_applicable"
        findings = decision.reason if rule_id == "LX0609-028" and decision.reason else "未发现该质控点所需触发事件，本次判定为不适用。"
        suggestion = "无需整改；如病历存在相关事件，请补充结构化文书或医嘱后重新质控。"
        confidence = 0.88
    else:
        result_status = "data_gap"
        fields = "、".join(decision.data_gap_fields) or "必要结构化字段"
        findings = f"已发现触发事件，但缺少 {fields}，无法完成自动判定。"
        suggestion = f"请补齐 {fields} 后重新执行质控，或由质控员结合原文确认。"
        confidence = 0.72

    if status == TRIGGER_ABSENT:
        evidence_lines = [
            f"适用性：{decision.reason}"
            if rule_id == "LX0609-028" and decision.reason
            else "适用性：未发现与本质控点直接相关的触发事实。"
        ]
    else:
        evidence_lines = ["数据不足：已发现相关事件，但缺少自动判定所需字段。"]
    if decision.data_gap_fields:
        evidence_lines.append(f"缺失字段：{'、'.join(decision.data_gap_fields)}")
    evidence = "\n".join(evidence_lines)
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "rule_name": rule_name,
        "status": result_status,
        "is_compliant": result_status == "not_applicable",
        "findings": findings,
        "evidence": evidence,
        "suggestion": suggestion,
        "confidence": confidence,
        "metadata": {
            **decision.to_metadata(),
            "executor_type": "program",
            "aggregation_source": "trigger_gate",
        },
    }


def filter_executable_rules_by_gate(
    *,
    executable_rules: list[dict[str, Any]],
    wrapper_rules: list[dict[str, Any]],
    decisions: dict[str, Luxian0609GateDecision],
) -> list[dict[str, Any]]:
    """Skip executable rules only when every mapped customer rule is terminal."""

    rule_to_wrappers: dict[str, list[str]] = {}
    for wrapper in wrapper_rules:
        wrapper_id = str(wrapper.get("rule_id") or "").strip().upper()
        for mapped_rule_id in list(wrapper.get("mapped_rule_ids") or []):
            key = str(mapped_rule_id or "").strip().upper()
            if key and wrapper_id:
                rule_to_wrappers.setdefault(key, []).append(wrapper_id)

    filtered: list[dict[str, Any]] = []
    for rule in executable_rules:
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        wrapper_ids = list(rule_to_wrappers.get(rule_id) or [])
        if rule_id in decisions and rule_id not in wrapper_ids:
            wrapper_ids.append(rule_id)
        if not wrapper_ids:
            filtered.append(rule)
            continue
        terminal_count = 0
        for wrapper_id in wrapper_ids:
            decision = decisions.get(wrapper_id)
            if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
                terminal_count += 1
        if terminal_count == len(wrapper_ids):
            continue
        filtered.append(rule)
    return filtered
