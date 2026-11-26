from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect, text

from .models import ApplicabilityGateResult, GateApplicability, GateCoverage, GateDecision


STRONG_CODE_MATCH_TYPES = {"code_exact", "code_normalized"}
GATE_NAME = "sc083_mdt_equivalent_gate"
RULE_ID = "SC-083"
MDT_KEYWORD_PATTERN = re.compile(
    r"MDT|多学科会诊|多学科讨论|多学科|多专业|多科会诊|多科室会诊|多科联合会诊|联合会诊|联合讨论",
    re.IGNORECASE,
)
MULTIDISCIPLINARY_KEYWORD_PATTERN = re.compile(
    r"多学科|多专业|多科会诊|多科室会诊|多科联合会诊|多科|联合会诊|联合讨论|相关科室"
)
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
    mdt_equivalent_by_customer_policy: bool = False
    evidence_time_relation_to_surgery: str = "unknown"
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


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


def _evidence_time_relation(has_preop: bool, documents: list[MdtEvidenceDocument]) -> str:
    if has_preop:
        return "preoperative_or_presurg_documented"
    if documents:
        return "unknown_from_available_documents"
    return "missing_evidence"


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
        flags.append("ordinary_multidept_consult_accepted_by_customer_policy")
    if has_mdt_keyword and not has_conclusion:
        flags.append("mdt_keyword_without_conclusion")
    if has_mdt_keyword and not has_host:
        flags.append("mdt_keyword_without_host")
    if has_mdt_keyword and not has_reason:
        flags.append("mdt_keyword_without_reason")
    if compact and len(compact) < 120:
        flags.append("evidence_fragment_too_short")

    mdt_equivalent = bool(has_mdt_keyword or has_multidisciplinary_keyword or has_multi_department)

    if _not_applicable_by_code(code_gate):
        status = "level4_not_applicable_by_code"
        decision = "rejected_by_system"
        reason = "手术编码精确/规范化匹配显示最高等级为三级或以下，SC-083 四级手术 MDT 规则不适用。"
    elif not _strong_code_gate_passed(code_gate):
        status = "level4_applicability_data_gap"
        decision = "data_quality_gap"
        reason = "未取得 code_exact/code_normalized 四级手术编码证据，不能进入 SC-083 缺陷裁决。"
    elif mdt_equivalent:
        status = "level4_applicable_mdt_equivalent_evidence_accepted"
        decision = "rejected_by_system"
        reason = "已取得四级手术编码证据，并聚合到客户认可的 MDT/多学科会诊/多科会诊等价证据，SC-083 暂不构成未 MDT 缺陷。"
    elif not documents:
        status = "level4_applicable_discussion_evidence_incomplete"
        decision = "data_quality_gap"
        reason = "已取得四级手术编码证据，但未取得术前讨论、会诊或病程相关源文书，无法判断是否存在 MDT/多科会诊证据。"
    elif presurg_count:
        status = "level4_applicable_discussion_evidence_incomplete"
        decision = "data_quality_gap"
        reason = "已取得四级手术编码证据，也有术前讨论类文书，但未聚合到 MDT/多科会诊等价证据，需补充讨论正文或会诊对照。"
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
        mdt_equivalent_by_customer_policy=mdt_equivalent and _strong_code_gate_passed(code_gate),
        evidence_time_relation_to_surgery=_evidence_time_relation(has_preop, documents),
        evidence_source_tables=source_tables,
        strongest_quote=strongest_quote,
        contrast_quote=contrast_quote,
        evidence_quality_flags=flags,
        ordinary_consultation_substitute_mdt=(
            "accepted_by_customer_policy" if has_multi_department and not has_mdt_keyword else ""
        ),
        document_count=len(documents),
        consultation_record_count=consultation_count,
        presurg_discussion_count=presurg_count,
        reason=reason,
    )


def _normalize_code(value: Any) -> str:
    return re.sub(r"[\s　]+", "", _safe_text(value)).upper()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


@lru_cache(maxsize=1)
def _catalog_by_code() -> dict[str, dict[str, str]]:
    path = _repo_root() / "apps" / "medqc-web" / "docs" / "0508" / "surgery_level_catalog" / "surgery_level_catalog.csv"
    if not path.exists():
        return {}
    catalog: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = _normalize_code(row.get("surgery_code"))
            if code and code not in catalog:
                catalog[code] = {key: _safe_text(value) for key, value in row.items()}
    return catalog


def _code_context_from_mapping(payload: dict[str, Any], visit_id: str) -> SurgeryCodeGateContext | None:
    raw = payload.get("sc083_code_gate_context") or payload.get("surgery_code_gate_context") or payload
    if not isinstance(raw, dict):
        return None
    if not any(
        raw.get(key)
        for key in (
            "visit_max_level",
            "visit_level4_evidence_code",
            "strong_match_type",
            "sc083_applicability",
        )
    ):
        return None
    return SurgeryCodeGateContext(
        visit_id=_safe_text(raw.get("visit_id")) or visit_id,
        patient_name=_safe_text(raw.get("patient_name") or payload.get("patient_name")),
        department=_safe_text(raw.get("department") or payload.get("department")),
        visit_max_level=_safe_text(raw.get("visit_max_level")),
        visit_level4_evidence_code=_safe_text(raw.get("visit_level4_evidence_code")),
        visit_level4_evidence_name=_safe_text(raw.get("visit_level4_evidence_name")),
        visit_level4_evidence_source_table=_safe_text(raw.get("visit_level4_evidence_source_table")),
        strong_match_type=_safe_text(raw.get("strong_match_type")),
        sc083_applicability=_safe_text(raw.get("sc083_applicability")),
    )


def _source_table_from_doc(doc: Any) -> str:
    if not isinstance(doc, dict):
        return ""
    return _safe_text(doc.get("source_table") or doc.get("table_name") or doc.get("document_type")).split(".")[-1]


def _source_text_from_doc(doc: Any) -> str:
    if not isinstance(doc, dict):
        return ""
    return "\n".join(
        text
        for text in (
            _safe_text(doc.get("document_title")),
            _safe_text(doc.get("title")),
            _safe_text(doc.get("text")),
            _safe_text(doc.get("content")),
            _safe_text(doc.get("record_content")),
            _safe_text(doc.get("medical_text")),
            _safe_text(doc.get("assembled_text")),
            _safe_text(doc.get("raw_text")),
            _safe_text(doc.get("summary")),
        )
        if text
    )


def _documents_from_payload(payload: dict[str, Any], visit_id: str) -> list[MdtEvidenceDocument]:
    documents: list[MdtEvidenceDocument] = []
    doc_values: list[Any] = []
    for key in ("sc083_mdt_documents", "source_documents", "documents"):
        value = payload.get(key)
        if isinstance(value, list):
            doc_values.extend(value)
    inventory = payload.get("document_inventory")
    if isinstance(inventory, list):
        doc_values.extend(inventory)
    elif isinstance(inventory, dict):
        for value in inventory.values():
            if isinstance(value, list):
                doc_values.extend(value)
            elif isinstance(value, dict):
                doc_values.append(value)

    for doc in doc_values:
        if not isinstance(doc, dict):
            continue
        table = _source_table_from_doc(doc)
        if table not in {"consultation_record", "presurg_discussion", "daily_course_record", "senior_course_record"}:
            continue
        documents.append(
            MdtEvidenceDocument(
                visit_id=_safe_text(doc.get("visit_id")) or visit_id,
                source_table=table,
                document_id=_safe_text(doc.get("document_id") or doc.get("id")),
                document_title=_safe_text(doc.get("document_title") or doc.get("title")),
                record_time=_safe_text(
                    doc.get("record_time")
                    or doc.get("record_datetime")
                    or doc.get("submit_datetime")
                    or doc.get("update_time")
                ),
                record_content=_source_text_from_doc(doc),
                submitter=_safe_text(doc.get("submitter")),
                host_name=_safe_text(doc.get("host_name")),
                discuss_staff=_safe_text(doc.get("discuss_staff")),
                v2_schema=_safe_text(doc.get("v2_schema")),
            )
        )
    return documents


def _visit_id(result: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    metadata = _safe_dict(result.get("metadata"))
    bundle_meta = _safe_dict(context.get("bundle_metadata"))
    return _safe_text(
        result.get("visit_id")
        or result.get("record_id")
        or result.get("visitId")
        or metadata.get("visit_id")
        or context.get("visit_id")
        or context.get("record_id")
        or bundle_meta.get("visit_id")
    )


def _tri_key(result: dict[str, Any], context: dict[str, Any] | None = None) -> tuple[str, str, str]:
    context = context or {}
    metadata = _safe_dict(result.get("metadata"))
    bundle_meta = _safe_dict(context.get("bundle_metadata"))
    institute_id = _safe_text(
        result.get("institute_id")
        or metadata.get("institute_id")
        or context.get("institute_id")
        or bundle_meta.get("institute_id")
    )
    patient_id = _safe_text(
        result.get("patient_id")
        or metadata.get("patient_id")
        or context.get("patient_id")
        or bundle_meta.get("patient_id")
    )
    visit_id = _visit_id(result, context)
    return institute_id, patient_id, visit_id


def _patient_name(result: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    return _safe_text(result.get("patient_name") or context.get("patient_name"))


def _department(result: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    return _safe_text(result.get("department") or context.get("department"))


_SC083_DB_MAX_ROWS = 200


def _db_table_schema(table_name: str) -> tuple[str, list[str]] | None:
    from app.database.connection import engine
    from app.services.clinical_read import clinical_read_schema

    if engine is None:
        raise RuntimeError("数据库连接未配置，无法读取 SC-083 临床证据")
    inspector = sa_inspect(engine)
    preferred = clinical_read_schema()
    schema_candidates: list[str | None] = []
    for candidate in (preferred, "cdm", "public", None):
        if candidate not in schema_candidates:
            schema_candidates.append(candidate)
    for schema in schema_candidates:
        if inspector.has_table(table_name, schema=schema):
            columns = [column["name"] for column in inspector.get_columns(table_name, schema=schema)]
            return schema or "", columns
    return None


def _qualified(schema: str, table_name: str) -> str:
    return f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'


def _db_rows(
    table_name: str,
    visit_id: str,
    wanted_fields: list[str],
    *,
    institute_id: str = "",
    patient_id: str = "",
    max_rows: int = _SC083_DB_MAX_ROWS,
) -> tuple[list[dict[str, Any]], bool]:
    """按三坐标 (institute_id, patient_id, visit_id) 读取证据行，使用 LIMIT N+1 探测截断且不静默吞 DB 错。"""
    from app.database.connection import engine

    iid = _safe_text(institute_id)
    pid = _safe_text(patient_id)
    vid = _safe_text(visit_id)
    if not (iid and pid and vid):
        raise ValueError("SC-083 数据库回源缺少完整三坐标 (institute_id, patient_id, visit_id)")
    if engine is None:
        raise RuntimeError("数据库连接未配置，无法读取 SC-083 临床证据")
    schema_info = _db_table_schema(table_name)
    if not schema_info:
        return [], False
    schema, columns = schema_info
    for required_col in ("institute_id", "patient_id", "visit_id"):
        if required_col not in columns:
            raise RuntimeError(f"SC-083 来源表 {table_name} 缺少三坐标列 {required_col}")
    fields = ["institute_id", "patient_id", "visit_id"] + [
        field for field in wanted_fields if field in columns
    ]
    fields = list(dict.fromkeys(fields))
    selected = ", ".join(f'"{field}"' for field in fields)
    limit_cap = max(1, int(max_rows))
    sql = (
        f'SELECT {selected} FROM {_qualified(schema, table_name)} '
        f'WHERE CAST("institute_id" AS TEXT) = :institute_id '
        f'AND CAST("patient_id" AS TEXT) = :patient_id '
        f'AND CAST("visit_id" AS TEXT) = :visit_id '
        f'LIMIT :limit_rows'
    )
    with engine.connect() as conn:
        fetched = [
            dict(row)
            for row in conn.execute(
                text(sql),
                {
                    "institute_id": iid,
                    "patient_id": pid,
                    "visit_id": vid,
                    "limit_rows": limit_cap + 1,
                },
            )
            .mappings()
            .all()
        ]
    truncated = len(fetched) > limit_cap
    if truncated:
        fetched = fetched[:limit_cap]
    return fetched, truncated


def _db_code_context(
    visit_id: str,
    patient_name: str = "",
    department: str = "",
    *,
    institute_id: str = "",
    patient_id: str = "",
) -> tuple[SurgeryCodeGateContext, bool]:
    if not visit_id:
        return SurgeryCodeGateContext(visit_id=visit_id, patient_name=patient_name, department=department), False
    catalog = _catalog_by_code()
    source_priority = (
        ("mr_surgery", "surgery_code", "surgery_name"),
        ("surgery_application", "surgery_code", "surgery_name"),
        ("surgery_record", "surgery_code", "surgery_name"),
        ("surgery_inform_consent", "planned_operation_code", "planned_operation_name"),
    )
    seen_codes = False
    matched_levels: list[int] = []
    best_level4: dict[str, str] | None = None
    unmatched = False
    any_truncated = False
    for table, code_field, name_field in source_priority:
        rows, truncated = _db_rows(
            table,
            visit_id,
            [code_field, name_field],
            institute_id=institute_id,
            patient_id=patient_id,
        )
        if truncated:
            any_truncated = True
        for row in rows:
            code = _normalize_code(row.get(code_field))
            if not code:
                continue
            seen_codes = True
            match = catalog.get(code)
            if not match:
                unmatched = True
                continue
            level_text = _safe_text(match.get("surgery_level"))
            try:
                level = int(level_text)
            except Exception:
                unmatched = True
                continue
            matched_levels.append(level)
            if level == 4 and best_level4 is None:
                best_level4 = {
                    "code": code,
                    "name": _safe_text(row.get(name_field) or match.get("surgery_name")),
                    "table": table,
                    "match_type": "code_exact",
                }
    if best_level4:
        return SurgeryCodeGateContext(
            visit_id=visit_id,
            patient_name=patient_name,
            department=department,
            visit_max_level="4",
            visit_level4_evidence_code=best_level4["code"],
            visit_level4_evidence_name=best_level4["name"],
            visit_level4_evidence_source_table=best_level4["table"],
            strong_match_type=best_level4["match_type"],
            sc083_applicability="applicable_level4_by_code",
        ), any_truncated
    if any_truncated:
        return SurgeryCodeGateContext(
            visit_id=visit_id,
            patient_name=patient_name,
            department=department,
            visit_max_level="unknown",
            sc083_applicability="data_gap_source_truncated",
        ), True
    if matched_levels and max(matched_levels) <= 3 and not unmatched:
        return SurgeryCodeGateContext(
            visit_id=visit_id,
            patient_name=patient_name,
            department=department,
            visit_max_level="<=3",
            strong_match_type="code_exact",
            sc083_applicability="not_applicable_level3_by_code",
        ), False
    reason = "data_gap_code_missing"
    if seen_codes and unmatched:
        reason = "data_gap_code_unmatched"
    return SurgeryCodeGateContext(
        visit_id=visit_id,
        patient_name=patient_name,
        department=department,
        visit_max_level="unknown",
        sc083_applicability=reason,
    ), False


def _db_mdt_documents(
    visit_id: str,
    *,
    institute_id: str = "",
    patient_id: str = "",
) -> tuple[list[MdtEvidenceDocument], bool]:
    documents: list[MdtEvidenceDocument] = []
    any_truncated = False
    table_names = ("consultation_record", "presurg_discussion", "daily_course_record", "senior_course_record")
    wanted = [
        "document_id",
        "document_title",
        "record_content",
        "submitter",
        "host_name",
        "discuss_staff",
        "v2_schema",
        "record_datetime",
        "record_time",
        "submit_datetime",
        "last_modified_datetime",
        "update_time",
    ]
    for table in table_names:
        rows, truncated = _db_rows(
            table,
            visit_id,
            wanted,
            institute_id=institute_id,
            patient_id=patient_id,
        )
        if truncated:
            any_truncated = True
        for row in rows:
            record_time = next(
                (
                    _safe_text(row.get(field))
                    for field in (
                        "record_datetime",
                        "record_time",
                        "submit_datetime",
                        "last_modified_datetime",
                        "update_time",
                    )
                    if _safe_text(row.get(field))
                ),
                "",
            )
            documents.append(
                MdtEvidenceDocument(
                    visit_id=visit_id,
                    source_table=table,
                    document_id=_safe_text(row.get("document_id")),
                    document_title=_safe_text(row.get("document_title")),
                    record_time=record_time,
                    record_content=_safe_text(row.get("record_content")),
                    submitter=_safe_text(row.get("submitter")),
                    host_name=_safe_text(row.get("host_name")),
                    discuss_staff=_safe_text(row.get("discuss_staff")),
                    v2_schema=_safe_text(row.get("v2_schema")),
                )
            )
    return documents, any_truncated


def _aggregation_to_gate(aggregation: MdtEvidenceAggregation) -> ApplicabilityGateResult:
    decision = GateDecision(aggregation.suggested_gate_decision)
    if decision == GateDecision.REJECTED_BY_SYSTEM:
        applicability = GateApplicability.NOT_APPLICABLE if aggregation.mdt_evidence_status == "level4_not_applicable_by_code" else GateApplicability.APPLICABLE
        coverage = GateCoverage.SUFFICIENT
    elif decision == GateDecision.PASS_TO_SECOND_GATE:
        applicability = GateApplicability.APPLICABLE
        coverage = GateCoverage.SUFFICIENT
    else:
        applicability = GateApplicability.UNKNOWN
        coverage = GateCoverage.INSUFFICIENT if "data_gap" in aggregation.mdt_evidence_status else GateCoverage.PARTIAL
    metadata = {
        "gate_id": GATE_NAME,
        "gate_decision": decision.value,
        "mdt_evidence_status": aggregation.mdt_evidence_status,
        "mdt_equivalent_by_customer_policy": aggregation.mdt_equivalent_by_customer_policy,
        "departments_detected": aggregation.departments_detected,
        "participant_count": aggregation.participant_count,
        "source_tables": aggregation.evidence_source_tables,
        "evidence_source_tables": aggregation.evidence_source_tables,
        "strongest_quote": aggregation.strongest_quote,
        "contrast_quote": aggregation.contrast_quote,
        "evidence_time_relation_to_surgery": aggregation.evidence_time_relation_to_surgery,
        "trigger_status": "present" if aggregation.mdt_equivalent_by_customer_policy else "absent",
        "trigger_strength": "mdt_equivalent" if aggregation.mdt_equivalent_by_customer_policy else "absent",
        "code_gate_passed": aggregation.code_gate_passed,
        "visit_max_level": aggregation.visit_max_level,
        "visit_level4_evidence_code": aggregation.visit_level4_evidence_code,
        "visit_level4_evidence_name": aggregation.visit_level4_evidence_name,
        "visit_level4_evidence_source_table": aggregation.visit_level4_evidence_source_table,
        "has_mdt_keyword": aggregation.has_mdt_keyword,
        "has_multidisciplinary_keyword": aggregation.has_multidisciplinary_keyword,
        "has_multi_department_participants": aggregation.has_multi_department_participants,
        "has_host_or_moderator": aggregation.has_host_or_moderator,
        "has_discussion_reason": aggregation.has_discussion_reason,
        "has_discussion_conclusion": aggregation.has_discussion_conclusion,
        "has_preoperative_timing": aggregation.has_preoperative_timing,
        "evidence_quality_flags": aggregation.evidence_quality_flags,
        "confirmed_allowed": False,
        "data_gap_reason": aggregation.mdt_evidence_status if decision == GateDecision.DATA_QUALITY_GAP else "",
    }
    return ApplicabilityGateResult(
        rule_id=RULE_ID,
        gate_name=GATE_NAME,
        applicability=applicability,
        coverage=coverage,
        gate_decision=decision,
        confirmed_allowed=False,
        needs_second_pass_gate=decision == GateDecision.PASS_TO_SECOND_GATE,
        metadata=metadata,
        evidence_quote=aggregation.strongest_quote,
        reason=aggregation.reason,
    )


def run_sc083_gate(result: dict[str, Any], context: dict[str, Any] | None = None) -> ApplicabilityGateResult:
    context = _safe_dict(context)
    metadata = _safe_dict(result.get("metadata"))
    institute_id, patient_id, visit_id = _tri_key(result, context)
    patient = _patient_name(result, context)
    department = _department(result, context)

    code_context = _code_context_from_mapping(context, visit_id) or _code_context_from_mapping(metadata, visit_id)
    code_truncated = False
    if code_context is None:
        code_context, code_truncated = _db_code_context(
            visit_id,
            patient,
            department,
            institute_id=institute_id,
            patient_id=patient_id,
        )

    documents = _documents_from_payload(context, visit_id) or _documents_from_payload(metadata, visit_id)
    docs_truncated = False
    if not documents:
        documents, docs_truncated = _db_mdt_documents(
            visit_id,
            institute_id=institute_id,
            patient_id=patient_id,
        )

    aggregation = aggregate_sc083_mdt_evidence(code_context, documents)
    gate_result = _aggregation_to_gate(aggregation)
    if code_truncated or docs_truncated:
        gate_result.metadata["source_rows_truncated"] = True
        if gate_result.gate_decision != GateDecision.REJECTED_BY_SYSTEM or code_truncated:
            gate_result.metadata["data_gap_reason"] = "sc083_source_rows_truncated"
            gate_result.metadata["gate_decision"] = GateDecision.DATA_QUALITY_GAP.value
            return ApplicabilityGateResult(
                rule_id=RULE_ID,
                gate_name=GATE_NAME,
                applicability=GateApplicability.UNKNOWN,
                coverage=GateCoverage.INSUFFICIENT,
                gate_decision=GateDecision.DATA_QUALITY_GAP,
                confirmed_allowed=False,
                needs_second_pass_gate=False,
                metadata=gate_result.metadata,
                evidence_quote=gate_result.evidence_quote,
                reason="SC-083 临床证据查询发生截断，无法安全断言缺失或排除适用，已降级为资料缺口。",
            )
    return gate_result
