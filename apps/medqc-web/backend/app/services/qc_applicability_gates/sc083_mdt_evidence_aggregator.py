from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


STRONG_CODE_MATCH_TYPES = {"code_exact", "code_normalized"}
MDT_KEYWORD_PATTERN = re.compile(r"MDT|多学科|多专业|多科会诊|联合会诊|联合讨论", re.IGNORECASE)
MULTIDISCIPLINARY_KEYWORD_PATTERN = re.compile(r"多学科|多专业|多科|联合会诊|联合讨论|相关科室")
HOST_PATTERN = re.compile(r"主持(?:人)?[:：]?|主持医师[:：]?|主持者[:：]?|主持[:：]?")
REASON_PATTERN = re.compile(r"讨论(?:目的|原因|理由)|会诊(?:目的|原因)|病情摘要|术前讨论|手术风险|拟行|因患者")
CONCLUSION_PATTERN = re.compile(r"讨论(?:意见|结论)|会诊(?:意见|结论)|处理意见|一致认为|建议|决定|拟行|预案|风险")
PREOP_PATTERN = re.compile(r"术前|拟行|术前讨论|术前会诊|术前评估")
PARTICIPANT_PATTERN = re.compile(r"(?:参加人员|参与人员|讨论人员|会诊医师|医师|主任医师|副主任医师|主治医师|护士长)")

DEPARTMENT_TERMS = (
    "麻醉科",
    "心血管内科",
    "心内科",
    "呼吸内科",
    "肿瘤科",
    "病理科",
    "输血科",
    "康复科",
    "胸外科",
    "骨科",
    "普外科",
    "神经外科",
    "泌尿外科",
    "妇科",
    "产科",
    "耳鼻咽喉科",
    "眼科",
    "ICU",
    "重症医学科",
    "感染科",
    "内分泌科",
    "消化内科",
    "肾内科",
    "血液科",
    "放射科",
    "影像科",
    "超声科",
    "检验科",
)


@dataclass(frozen=True)
class MdtEvidenceDocument:
    visit_id: str
    source_table: str
    document_id: str = ""
    document_title: str = ""
    record_time: str = ""
    record_content: str = ""
    submitter: str = ""
    host_name: str = ""
    discuss_staff: str = ""
    v2_schema: str = ""


@dataclass(frozen=True)
class SurgeryCodeGateContext:
    visit_id: str
    patient_name: str = ""
    department: str = ""
    visit_max_level: str = ""
    visit_level4_evidence_code: str = ""
    visit_level4_evidence_name: str = ""
    visit_level4_evidence_source_table: str = ""
    strong_match_type: str = ""
    sc083_applicability: str = ""


@dataclass(frozen=True)
class MdtEvidenceAggregation:
    visit_id: str
    patient_name: str
    department: str
    visit_max_level: str
    visit_level4_evidence_code: str
    visit_level4_evidence_name: str
    visit_level4_evidence_source_table: str
    code_gate_passed: bool
    mdt_evidence_status: str
    suggested_gate_decision: str
    has_mdt_keyword: bool
    has_multidisciplinary_keyword: bool
    has_multi_department_participants: bool
    departments_detected: list[str] = field(default_factory=list)
    participant_count: int = 0
    has_host_or_moderator: bool = False
    has_discussion_reason: bool = False
    has_discussion_conclusion: bool = False
    has_preoperative_timing: bool = False
    evidence_source_tables: list[str] = field(default_factory=list)
    strongest_quote: str = ""
    contrast_quote: str = ""
    evidence_quality_flags: list[str] = field(default_factory=list)
    ordinary_consultation_substitute_mdt: str = ""
    document_count: int = 0
    consultation_record_count: int = 0
    presurg_discussion_count: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _safe_text(value))


def _contains(pattern: re.Pattern[str], text: str) -> bool:
    return bool(pattern.search(text))


def _document_text(document: MdtEvidenceDocument) -> str:
    parts = [
        document.document_title,
        document.record_content,
        document.submitter,
        document.host_name,
        document.discuss_staff,
        document.v2_schema,
    ]
    return "\n".join(part for part in parts if _safe_text(part))


def detect_departments(text: str) -> list[str]:
    detected = [term for term in DEPARTMENT_TERMS if term in text]
    generic = re.findall(r"([\u4e00-\u9fff]{2,8}科)(?:医师|主任|会诊|意见|：|:)", text)
    for item in generic:
        item = re.sub(r"^(?:故请|请|邀|邀请|请予|建议请)", "", item)
        if re.search(rf"{re.escape(item)}主任讨论地点", text):
            continue
        if item not in detected and len(item) <= 8:
            detected.append(item)
    normalized: list[str] = []
    for item in detected:
        item = re.sub(r"^(?:再次)?(?:故请|请|邀|邀请|请予|建议请)", "", item)
        if item and item not in normalized:
            normalized.append(item)
    return sorted(set(normalized))


def estimate_participant_count(text: str) -> int:
    if not _contains(PARTICIPANT_PATTERN, text):
        return 0
    names = re.findall(r"[\u4e00-\u9fff]{2,4}(?:主任医师|副主任医师|主治医师|医师|护士长)", text)
    return max(len(set(names)), len(detect_departments(text)))


def _quote_around(text: str, pattern: re.Pattern[str], limit: int = 260) -> str:
    match = pattern.search(text)
    if not match:
        return _safe_text(text)[:limit]
    start = max(match.start() - limit // 3, 0)
    end = min(match.end() + limit * 2 // 3, len(text))
    return _safe_text(text[start:end])[:limit]


def _strong_code_gate_passed(code_gate: SurgeryCodeGateContext) -> bool:
    return (
        code_gate.visit_max_level == "4"
        and code_gate.strong_match_type in STRONG_CODE_MATCH_TYPES
        and bool(code_gate.visit_level4_evidence_code)
    )


def _not_applicable_by_code(code_gate: SurgeryCodeGateContext) -> bool:
    return code_gate.visit_max_level in {"<=3", "3", "2", "1"} or code_gate.sc083_applicability == "not_applicable_level3_by_code"


def aggregate_sc083_mdt_evidence(
    code_gate: SurgeryCodeGateContext,
    documents: list[MdtEvidenceDocument],
) -> MdtEvidenceAggregation:
    texts = [_document_text(document) for document in documents]
    combined = "\n".join(text for text in texts if text)
    compact = _compact(combined)
    source_tables = sorted({document.source_table for document in documents if document.source_table})
    departments = detect_departments(combined)
    participant_count = max([estimate_participant_count(text) for text in texts] + [len(departments)])
    has_mdt_keyword = _contains(MDT_KEYWORD_PATTERN, combined)
    has_multidisciplinary_keyword = _contains(MULTIDISCIPLINARY_KEYWORD_PATTERN, combined)
    has_multi_department = len(departments) >= 2
    has_host = any(_contains(HOST_PATTERN, _document_text(document)) or bool(document.host_name) for document in documents)
    has_reason = _contains(REASON_PATTERN, combined)
    has_conclusion = _contains(CONCLUSION_PATTERN, combined)
    has_preop = any(document.source_table == "presurg_discussion" for document in documents) or _contains(PREOP_PATTERN, combined)
    consultation_count = sum(1 for document in documents if document.source_table == "consultation_record")
    presurg_count = sum(1 for document in documents if document.source_table == "presurg_discussion")

    flags: list[str] = []
    if not documents:
        flags.append("mdt_source_missing")
    if has_multi_department and not has_mdt_keyword:
        flags.append("ordinary_multidept_consult_policy_pending")
    if has_mdt_keyword and not has_conclusion:
        flags.append("mdt_keyword_without_conclusion")
    if has_mdt_keyword and not has_host:
        flags.append("mdt_keyword_without_host")
    if has_mdt_keyword and not has_reason:
        flags.append("mdt_keyword_without_reason")
    if compact and len(compact) < 120:
        flags.append("evidence_fragment_too_short")

    if _not_applicable_by_code(code_gate):
        status = "level4_not_applicable_by_code"
        decision = "rejected_by_system"
        reason = "手术编码精确/规范化匹配显示最高等级为三级或以下，SC-083 四级手术 MDT 规则不适用。"
    elif not _strong_code_gate_passed(code_gate):
        status = "level4_applicability_data_gap"
        decision = "data_quality_gap"
        reason = "未取得 code_exact/code_normalized 四级手术编码证据，不能进入 SC-083 缺陷裁决。"
    elif has_mdt_keyword and has_host and has_reason and has_conclusion:
        status = "level4_applicable_mdt_evidence_strong"
        decision = "rejected_by_system"
        reason = "已取得四级手术编码证据，并有 MDT/多学科讨论的主持、原因和结论证据，暂不构成未 MDT。"
    elif has_multi_department or (consultation_count >= 2 and len(departments) >= 2):
        status = "level4_applicable_multidept_consult_policy_pending"
        decision = "data_quality_gap"
        reason = "已取得四级手术编码证据，并有多科室普通会诊证据；客户尚未确认普通多科会诊可替代正式 MDT，暂按数据/口径缺口处理。"
    elif has_mdt_keyword or has_multidisciplinary_keyword or presurg_count:
        status = "level4_applicable_discussion_evidence_incomplete"
        decision = "data_quality_gap"
        reason = "已取得四级手术编码证据，但 MDT/术前讨论证据缺主持、原因或结论等完整要件。"
    else:
        status = "level4_applicable_mdt_evidence_missing"
        decision = "pass_to_second_gate"
        reason = "已取得四级手术编码证据，未聚合到可审计 MDT/多学科讨论证据；只能进入二轮候选，不得程序化 confirmed。"

    quote_pattern = MDT_KEYWORD_PATTERN if has_mdt_keyword else (MULTIDISCIPLINARY_KEYWORD_PATTERN if has_multidisciplinary_keyword else REASON_PATTERN)
    strongest_quote = _quote_around(combined, quote_pattern) if compact else ""
    contrast_quote = ""
    if has_multi_department and not has_mdt_keyword:
        contrast_quote = "；".join(departments[:8])

    return MdtEvidenceAggregation(
        visit_id=code_gate.visit_id,
        patient_name=code_gate.patient_name,
        department=code_gate.department,
        visit_max_level=code_gate.visit_max_level,
        visit_level4_evidence_code=code_gate.visit_level4_evidence_code,
        visit_level4_evidence_name=code_gate.visit_level4_evidence_name,
        visit_level4_evidence_source_table=code_gate.visit_level4_evidence_source_table,
        code_gate_passed=_strong_code_gate_passed(code_gate),
        mdt_evidence_status=status,
        suggested_gate_decision=decision,
        has_mdt_keyword=has_mdt_keyword,
        has_multidisciplinary_keyword=has_multidisciplinary_keyword,
        has_multi_department_participants=has_multi_department,
        departments_detected=departments,
        participant_count=participant_count,
        has_host_or_moderator=has_host,
        has_discussion_reason=has_reason,
        has_discussion_conclusion=has_conclusion,
        has_preoperative_timing=has_preop,
        evidence_source_tables=source_tables,
        strongest_quote=strongest_quote,
        contrast_quote=contrast_quote,
        evidence_quality_flags=flags,
        ordinary_consultation_substitute_mdt="policy_pending" if has_multi_department and not has_mdt_keyword else "",
        document_count=len(documents),
        consultation_record_count=consultation_count,
        presurg_discussion_count=presurg_count,
        reason=reason,
    )
