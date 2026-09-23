from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlalchemy import text as sql_text


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_ready_sample_candidates.json"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-formal-ready样本候选.md"

FORMAL_READY_QC_POINTS = {"LX0609-12-01-02", "LX0609-03-01-02", "LX0609-04-03-01"}


def normalize(value: Any) -> str:
    return str(value or "").strip()


def compact_text(value: Any) -> str:
    text = normalize(value)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。；;:：、（）()\[\]【】,.!?！？\"'“”‘’]", "", text)
    return text


def safe_snippet(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", normalize(value))
    return text[:limit]


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = normalize(value)
    if not text:
        return None
    text = text.replace("T", " ").replace("+08", "")
    text = re.sub(r"\.\d+", "", text)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def load_catalog() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        normalize(item.get("qc_point_id")): item
        for item in data
        if isinstance(item, dict) and normalize(item.get("qc_point_id")) in FORMAL_READY_QC_POINTS
    }


def load_sample_visit_ids(pool_id: str, *, page_size: int = 500) -> list[dict[str, Any]]:
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService

    service = CustomQCSamplePoolService()
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        result = service.list_pool_items(
            pool_id=pool_id,
            coverage_type=None,
            match_status="matched",
            include_in_batch_1=None,
            page=page,
            page_size=page_size,
        )
        rows.extend([item for item in result.items if isinstance(item, dict)])
        if page * result.page_size >= result.total:
            break
        page += 1
    seen: set[str] = set()
    visits: list[dict[str, Any]] = []
    for row in rows:
        visit_id = normalize(row.get("matched_visit_id") or row.get("visit_id") or row.get("record_id"))
        if not visit_id or visit_id in seen:
            continue
        seen.add(visit_id)
        visits.append(
            {
                "visit_id": visit_id,
                "sample_item_id": normalize(row.get("id") or row.get("sample_item_id")),
                "patient_name": normalize(row.get("patient_name") or row.get("name")),
                "department": normalize(row.get("department") or row.get("dept_name")),
                "manual_issue_text": normalize(row.get("manual_issue_text")),
            }
        )
    return visits


def load_frontpage(visit_id: str) -> dict[str, Any]:
    from app.database.connection import SessionLocal
    from app.database.models.cdm import MedicalRecordFrontpage

    if SessionLocal is None:
        return {}
    with SessionLocal() as session:
        row = session.query(MedicalRecordFrontpage).filter_by(visit_id=visit_id).first()
        if not row:
            return {}
        return {
            "patient_id": normalize(getattr(row, "patient_id", "")),
            "patient_name": normalize(getattr(row, "patient_name", "")),
            "department": normalize(getattr(row, "dept_name", "") or getattr(row, "department", "")),
            "admission_datetime": normalize(getattr(row, "admission_datetime", "")),
            "discharge_datetime": normalize(getattr(row, "discharge_datetime", "")),
        }


def load_admission_record_times(visit_id: str) -> dict[str, str]:
    from app.database.connection import SessionLocal

    if SessionLocal is None:
        return {}
    desired = ["admission_datetime", "submit_datetime", "last_modified_datetime", "record_time", "record_content"]
    with SessionLocal() as session:
        columns = set(
            session.execute(
                sql_text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'admission_record'
                      AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    """
                )
            ).scalars().all()
        )
        select_columns = [column for column in desired if column in columns]
        if not select_columns:
            return {}
        order_column = "submit_datetime" if "submit_datetime" in columns else ("record_time" if "record_time" in columns else "")
        order_by = f" ORDER BY {order_column} NULLS LAST" if order_column else ""
        row = session.execute(
            sql_text(
                f"SELECT {', '.join(select_columns)} FROM admission_record "
                "WHERE visit_id = :visit_id"
                f"{order_by} LIMIT 1"
            ),
            {"visit_id": visit_id},
        ).mappings().first()
        if not row:
            return {}
        return {column: normalize(row.get(column)) for column in desired}


def load_documents_by_type(visit_id: str) -> dict[str, list[dict[str, Any]]]:
    from app.services.medical_records.detail_service import get_documents

    result = get_documents(visit_id)
    docs = result.get("documents") if isinstance(result, dict) else []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not isinstance(docs, list):
        return {}
    for doc in docs:
        if not isinstance(doc, dict) or not doc.get("has_content"):
            continue
        source_table = normalize(doc.get("source_table") or doc.get("type"))
        if source_table:
            grouped[source_table].append(doc)
    if not grouped.get("first_course_record"):
        table_docs = load_cdm_documents(visit_id, "first_course_record")
        if table_docs:
            grouped["first_course_record"].extend(table_docs)
    return dict(grouped)


def load_cdm_documents(visit_id: str, table_name: str, *, limit: int = 3) -> list[dict[str, Any]]:
    from app.database.connection import SessionLocal

    if SessionLocal is None:
        return []
    try:
        with SessionLocal() as session:
            exists = session.execute(
                sql_text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                      AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    LIMIT 1
                    """
                ),
                {"table_name": table_name},
            ).first()
            if not exists:
                return []
            rows = session.execute(
                sql_text(
                    f"""
                    SELECT document_title, record_content, submit_datetime, last_modified_datetime, record_time
                    FROM {table_name}
                    WHERE visit_id = :visit_id
                    ORDER BY COALESCE(submit_datetime, record_time, last_modified_datetime) NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"visit_id": visit_id, "limit": limit},
            ).mappings().all()
    except Exception:
        return []

    result: list[dict[str, Any]] = []
    for row in rows:
        content = normalize(row.get("record_content"))
        result.append(
            {
                "source_table": table_name,
                "type": table_name,
                "label": normalize(row.get("document_title")) or table_name,
                "document_title": normalize(row.get("document_title")) or table_name,
                "content": content,
                "has_content": bool(content),
                "submit_time": normalize(row.get("submit_datetime")),
                "last_modified_time": normalize(row.get("last_modified_datetime")),
                "record_time": normalize(row.get("record_time")),
            }
        )
    return result


def table_row_count(visit_id: str, table_name: str) -> int | None:
    from app.database.connection import SessionLocal

    if SessionLocal is None:
        return None
    try:
        with SessionLocal() as session:
            exists = session.execute(
                sql_text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                      AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    LIMIT 1
                    """
                ),
                {"table_name": table_name},
            ).first()
            if not exists:
                return None
            value = session.execute(
                sql_text(f"SELECT COUNT(*) FROM {table_name} WHERE visit_id = :visit_id"),
                {"visit_id": visit_id},
            ).scalar()
            return int(value or 0)
    except Exception:
        return None


def table_quality_stats(visit_id: str, table_name: str) -> dict[str, int] | None:
    from app.database.connection import SessionLocal

    if SessionLocal is None:
        return None
    try:
        with SessionLocal() as session:
            exists = session.execute(
                sql_text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                      AND table_schema NOT IN ('information_schema', 'pg_catalog')
                    LIMIT 1
                    """
                ),
                {"table_name": table_name},
            ).first()
            if not exists:
                return None
            row = session.execute(
                sql_text(
                    f"""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (
                            WHERE record_content IS NOT NULL
                              AND LENGTH(record_content) >= 20
                        ) AS content_ready,
                        COUNT(*) FILTER (
                            WHERE submit_datetime IS NOT NULL
                               OR record_time IS NOT NULL
                               OR last_modified_datetime IS NOT NULL
                        ) AS time_ready
                    FROM {table_name}
                    WHERE visit_id = :visit_id
                    """
                ),
                {"visit_id": visit_id},
            ).mappings().first()
            if not row:
                return {"total": 0, "content_ready": 0, "time_ready": 0}
            return {
                "total": int(row.get("total") or 0),
                "content_ready": int(row.get("content_ready") or 0),
                "time_ready": int(row.get("time_ready") or 0),
            }
    except Exception:
        return None


def parse_admission_time_from_text(text: str) -> datetime | None:
    if not text:
        return None
    patterns = (
        r"于\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})[:：](\d{1,2})\s*入院",
        r"于\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})时(\d{1,2})分?\s*入院",
        r"入院时间[:：]?\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日\s]+(\d{1,2})[:：](\d{1,2})",
        r"入院日期[:：]?\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日\s]+(\d{1,2})[:：](\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month, day, hour, minute = [int(part) for part in match.groups()]
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            continue
    return None


def resolve_admission_time(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> tuple[datetime | None, str]:
    frontpage_time = parse_datetime(frontpage.get("admission_datetime"))
    if frontpage_time:
        return frontpage_time, f"首页入院时间 {frontpage.get('admission_datetime')}"
    record_times = load_admission_record_times(visit["visit_id"])
    table_time = parse_datetime(record_times.get("admission_datetime"))
    if table_time:
        return table_time, f"入院记录入院时间 {record_times.get('admission_datetime')}"
    text_time = parse_admission_time_from_text(record_times.get("record_content") or "")
    if text_time:
        return text_time, f"入院记录正文入院时间 {text_time:%Y-%m-%d %H:%M}"
    admission_docs = docs.get("admission_record") or []
    if admission_docs:
        doc_time = parse_admission_time_from_text(normalize(admission_docs[0].get("content")))
        if doc_time:
            return doc_time, f"入院记录装配文本入院时间 {doc_time:%Y-%m-%d %H:%M}"
    return None, "入院时间缺失"


def resolve_document_completion_time(doc: dict[str, Any]) -> tuple[datetime | None, str]:
    for field, label in (
        ("submit_time", "提交时间"),
        ("last_modified_time", "最后修改时间"),
        ("record_time", "记录时间"),
        ("sort_time", "排序时间"),
    ):
        value = doc.get(field)
        parsed = parse_datetime(value)
        if parsed:
            return parsed, f"{label} {value}"
    return None, "文书完成时间缺失"


def make_candidate(
    *,
    qc_point_id: str,
    case_type: str,
    visit: dict[str, Any],
    frontpage: dict[str, Any],
    evidence_summary: str,
    matched_text: str,
    confidence: float,
    status: str = "candidate",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "qc_point_id": qc_point_id,
        "suggested_case_type": case_type,
        "expected_hit": case_type == "positive",
        "status": status,
        "visit_id": visit["visit_id"],
        "sample_item_id": visit.get("sample_item_id") or "",
        "patient_name": visit.get("patient_name") or frontpage.get("patient_name") or "",
        "department": visit.get("department") or frontpage.get("department") or "",
        "evidence_summary": evidence_summary,
        "matched_text": safe_snippet(matched_text),
        "confidence": confidence,
        "review_status": "pending",
        "reviewer_note": "",
        **(extra or {}),
    }


def discover_lx0609_001(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    admission_time, admission_time_source = resolve_admission_time(visit, frontpage, docs)
    admission_docs = docs.get("admission_record") or []
    if not admission_docs:
        return None
    first_doc = admission_docs[0]
    if not admission_time:
        return make_candidate(
            qc_point_id="LX0609-01-01-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在入院记录，但缺少可判定入院后24小时完成情况的入院时间。应作为数据不足样本复核。",
            matched_text=f"{admission_time_source}；入院记录 {first_doc.get('label') or first_doc.get('document_title') or ''}",
            confidence=0.62,
            status="data_insufficient",
        )
    record_time, record_time_source = resolve_document_completion_time(first_doc)
    if not record_time:
        return make_candidate(
            qc_point_id="LX0609-01-01-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在入院记录和入院时间，但缺少入院记录完成时间，无法判定24小时规则。",
            matched_text=f"{admission_time_source}；入院记录完成时间缺失",
            confidence=0.62,
            status="data_insufficient",
        )
    hours = (record_time - admission_time).total_seconds() / 3600
    if hours > 24:
        return make_candidate(
            qc_point_id="LX0609-01-01-01",
            case_type="positive",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"入院记录完成时间距入院时间约 {hours:.1f} 小时，超过24小时。",
            matched_text=f"{admission_time_source}；入院记录{record_time_source}",
            confidence=0.92,
            extra={"hours_delta": round(hours, 2)},
        )
    if 22 <= hours <= 24:
        return make_candidate(
            qc_point_id="LX0609-01-01-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"入院记录完成时间距入院时间约 {hours:.1f} 小时，接近24小时阈值。",
            matched_text=f"{admission_time_source}；入院记录{record_time_source}",
            confidence=0.75,
            extra={"hours_delta": round(hours, 2)},
        )
    if 0 <= hours <= 8:
        return make_candidate(
            qc_point_id="LX0609-01-01-01",
            case_type="negative",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"入院记录在入院后约 {hours:.1f} 小时完成，未超过24小时。",
            matched_text=f"{admission_time_source}；入院记录{record_time_source}",
            confidence=0.86,
            extra={"hours_delta": round(hours, 2)},
        )
    return None


def discover_lx0609_002(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    admission_time, admission_time_source = resolve_admission_time(visit, frontpage, docs)
    course_docs = docs.get("first_course_record") or []
    if not admission_time:
        if course_docs:
            return make_candidate(
                qc_point_id="LX0609-01-02-01",
                case_type="boundary",
                visit=visit,
                frontpage=frontpage,
                evidence_summary="存在首次病程记录，但缺少可判定入院后8小时完成情况的入院时间。应作为数据不足样本复核。",
                matched_text=f"{admission_time_source}；首次病程记录 {course_docs[0].get('label') or course_docs[0].get('document_title') or ''}",
                confidence=0.62,
                status="data_insufficient",
            )
        return None
    if not course_docs:
        return make_candidate(
            qc_point_id="LX0609-01-02-01",
            case_type="positive",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="未查询到首次病程记录，需复核是否入院后8小时内缺失。",
            matched_text=f"{admission_time_source}；首次病程记录缺失",
            confidence=0.78,
            status="needs_review",
        )
    first_doc = course_docs[0]
    record_time, record_time_source = resolve_document_completion_time(first_doc)
    if not record_time:
        return make_candidate(
            qc_point_id="LX0609-01-02-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在首次病程记录行，但缺少可判定8小时规则的完成时间。应作为数据不足样本复核。",
            matched_text=f"{admission_time_source}；首次病程记录{record_time_source}；标题 {first_doc.get('label') or ''}",
            confidence=0.64,
            status="data_insufficient",
        )
    hours = (record_time - admission_time).total_seconds() / 3600
    if hours > 8:
        return make_candidate(
            qc_point_id="LX0609-01-02-01",
            case_type="positive",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"首次病程记录完成时间距入院时间约 {hours:.1f} 小时，超过8小时。",
            matched_text=f"{admission_time_source}；首次病程记录{record_time_source}",
            confidence=0.91,
            extra={"hours_delta": round(hours, 2)},
        )
    if 7 <= hours <= 8:
        return make_candidate(
            qc_point_id="LX0609-01-02-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"首次病程记录距入院时间约 {hours:.1f} 小时，接近8小时阈值。",
            matched_text=f"{admission_time_source}；首次病程记录{record_time_source}",
            confidence=0.76,
            extra={"hours_delta": round(hours, 2)},
        )
    if 0 <= hours <= 4:
        return make_candidate(
            qc_point_id="LX0609-01-02-01",
            case_type="negative",
            visit=visit,
            frontpage=frontpage,
            evidence_summary=f"首次病程记录在入院后约 {hours:.1f} 小时完成，未超过8小时。",
            matched_text=f"{admission_time_source}；首次病程记录{record_time_source}",
            confidence=0.86,
            extra={"hours_delta": round(hours, 2)},
        )
    return None


def discover_lx0609_016(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    admission_docs = docs.get("admission_record") or []
    course_docs = docs.get("first_course_record") or []
    if not admission_docs:
        return None
    if not course_docs:
        return make_candidate(
            qc_point_id="LX0609-12-01-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在入院记录，但当前样本装配文书缺少首次病程记录，无法判定首次病程与入院记录是否复制。",
            matched_text=f"入院记录 {admission_docs[0].get('label') or admission_docs[0].get('document_title') or ''}；首次病程记录缺失",
            confidence=0.6,
            status="data_insufficient",
        )
    admission_text = compact_text(admission_docs[0].get("content"))
    course_text = compact_text(course_docs[0].get("content"))
    if len(admission_text) < 120 or len(course_text) < 120:
        return make_candidate(
            qc_point_id="LX0609-12-01-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在入院记录和首次病程记录，但至少一份文书正文不足，无法可靠判定是否复制。",
            matched_text=f"入院记录长度 {len(admission_text)}；首次病程长度 {len(course_text)}",
            confidence=0.62,
            status="data_insufficient",
        )
    ratio = SequenceMatcher(None, admission_text[:1200], course_text[:1200]).ratio()
    if ratio >= 0.72:
        case_type = "positive"
        summary = f"入院记录与首次病程记录前1200字相似度 {ratio:.2f}，疑似复制。"
        confidence = 0.82
    elif 0.62 <= ratio < 0.72:
        case_type = "boundary"
        summary = f"入院记录与首次病程记录前1200字相似度 {ratio:.2f}，接近复制阈值。"
        confidence = 0.72
    elif ratio <= 0.42:
        case_type = "negative"
        summary = f"入院记录与首次病程记录前1200字相似度 {ratio:.2f}，差异较明显。"
        confidence = 0.78
    else:
        return None
    return make_candidate(
        qc_point_id="LX0609-12-01-01",
        case_type=case_type,
        visit=visit,
        frontpage=frontpage,
        evidence_summary=summary,
        matched_text=f"入院记录片段：{admission_docs[0].get('content', '')[:80]}；首次病程片段：{course_docs[0].get('content', '')[:80]}",
        confidence=confidence,
        extra={"similarity": round(ratio, 4)},
    )


def discover_lx0609_017(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    course_docs = (docs.get("daily_course_record") or []) + (docs.get("senior_course_record") or [])
    meaningful = [doc for doc in course_docs if len(compact_text(doc.get("content"))) >= 80]
    if len(meaningful) < 2:
        return None
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for idx, left in enumerate(meaningful):
        left_text = compact_text(left.get("content"))[:1000]
        for right in meaningful[idx + 1 :]:
            ratio = SequenceMatcher(None, left_text, compact_text(right.get("content"))[:1000]).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, left, right)
    if best is None:
        return None
    ratio, left, right = best
    if ratio >= 0.72:
        case_type = "positive"
        summary = f"两份病程记录相似度 {ratio:.2f}，疑似重复复制。"
        confidence = 0.82
    elif 0.62 <= ratio < 0.72:
        case_type = "boundary"
        summary = f"两份病程记录相似度 {ratio:.2f}，接近重复阈值。"
        confidence = 0.72
    elif ratio <= 0.35:
        case_type = "negative"
        summary = f"病程记录最高相似度 {ratio:.2f}，未见明显重复。"
        confidence = 0.75
    else:
        return None
    return make_candidate(
        qc_point_id="LX0609-12-01-02",
        case_type=case_type,
        visit=visit,
        frontpage=frontpage,
        evidence_summary=summary,
        matched_text=f"{left.get('label')} vs {right.get('label')}",
        confidence=confidence,
        extra={"similarity": round(ratio, 4)},
    )


def consultation_request_segment(content: str) -> str:
    if not content:
        return ""
    split_markers = ("会诊意见", "会诊示", "会诊查房", "会诊后意见", "医师:", "医生签名", "病史敬悉", "病史悉知")
    end = len(content)
    for marker in split_markers:
        index = content.find(marker)
        if index >= 0:
            end = min(end, index)
    return content[:end].strip(" ,，。；;：:")


def has_explicit_consultation_purpose(segment: str) -> bool:
    if not segment:
        return False
    purpose_patterns = (
        r"(因|因患者|由于|为|为了|拟|现|患者|诉|查|提示|诊断|入院诊断|术前|术后|产后|检查|评估|指导|完善|明确|排除|可否|是否|要求).{0,90}(请|特请|故请|邀|邀请|会诊|协助)",
        r"(请|特请|故请|邀|邀请).{0,20}(贵科|[\u4e00-\u9fff]{2,12}科).{0,80}(评估|指导|完善|明确|排除|处理|治疗|检查|诊治|会诊)",
        r"(评估|指导|完善|明确|排除|可否|是否).{0,50}(诊治|治疗|检查|手术|麻醉|转科|用药|风险)",
    )
    return any(re.search(pattern, segment) for pattern in purpose_patterns)


def is_generic_consultation_request(segment: str) -> bool:
    text = segment.strip(" ,，。；;：:")
    if not text:
        return False
    generic_patterns = (
        r"^[\u4e00-\u9fff]{2,12}科[,，、]?(协助诊治|请会诊|会诊)$",
        r"^(请|特请|故请)?贵科(会诊|协助诊治|指导诊治)[,，。；;！!]*$",
        r"^(协助诊治|请会诊|会诊|必要时进一步诊治)[,，。；;！!]*$",
    )
    return any(re.search(pattern, text) for pattern in generic_patterns)


def discover_lx0609_021(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    consultation_docs = docs.get("consultation_record") or []
    if not consultation_docs:
        return None
    content = normalize(consultation_docs[0].get("content"))
    request_segment = consultation_request_segment(content)
    has_purpose_label = any(keyword in content for keyword in ("会诊目的", "申请目的", "会诊理由", "申请会诊理由", "请会诊目的"))
    has_purpose = has_purpose_label or has_explicit_consultation_purpose(request_segment)
    has_generic = is_generic_consultation_request(request_segment)
    if has_generic or (len(request_segment) < 24 and "会诊" in request_segment and not has_purpose):
        return make_candidate(
            qc_point_id="LX0609-03-01-02",
            case_type="positive",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="会诊申请/记录存在泛化表述，未见明确会诊目的或理由。",
            matched_text=request_segment or content,
            confidence=0.73,
        )
    if has_purpose:
        return make_candidate(
            qc_point_id="LX0609-03-01-02",
            case_type="negative",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="会诊申请段可见明确目的、理由或需要协助解决的问题。",
            matched_text=request_segment or content,
            confidence=0.82,
        )
    return make_candidate(
        qc_point_id="LX0609-03-01-02",
        case_type="boundary",
        visit=visit,
        frontpage=frontpage,
        evidence_summary="会诊记录存在但目的字段不清晰，需要人工判断是否明确。",
        matched_text=request_segment or content,
        confidence=0.65,
    )


def discover_lx0609_032(visit: dict[str, Any], frontpage: dict[str, Any], docs: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    surgery_docs = docs.get("surgery_record") or []
    safecheck_stats = table_quality_stats(visit["visit_id"], "surgery_safecheck_record")
    if not surgery_docs:
        return None
    if safecheck_stats is None:
        return make_candidate(
            qc_point_id="LX0609-04-03-01",
            case_type="boundary",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在手术记录，但当前库未能确认手术安全核查表数据源。",
            matched_text=surgery_docs[0].get("label") or "手术记录",
            confidence=0.62,
            status="data_insufficient",
        )
    safecheck_count = safecheck_stats["total"]
    if safecheck_count <= 0:
        return make_candidate(
            qc_point_id="LX0609-04-03-01",
            case_type="positive",
            visit=visit,
            frontpage=frontpage,
            evidence_summary="存在手术记录，但未查询到手术安全核查表。",
            matched_text=surgery_docs[0].get("label") or "手术记录",
            confidence=0.86,
            extra={"safecheck_count": safecheck_count},
        )
    evidence_quality_note = ""
    confidence = 0.82
    if safecheck_stats["content_ready"] <= 0 or safecheck_stats["time_ready"] <= 0:
        evidence_quality_note = "；核查表结构化记录存在，但正文或记录时间不完整，复核时需以表记录存在性作为证据"
        confidence = 0.74
        return [
            make_candidate(
                qc_point_id="LX0609-04-03-01",
                case_type="negative",
                visit=visit,
                frontpage=frontpage,
                evidence_summary=f"存在手术记录，同时查询到 {safecheck_count} 条手术安全核查表{evidence_quality_note}。",
                matched_text=surgery_docs[0].get("label") or "手术记录",
                confidence=confidence,
                extra={"safecheck_count": safecheck_count, **safecheck_stats},
            ),
            make_candidate(
                qc_point_id="LX0609-04-03-01",
                case_type="boundary",
                visit=visit,
                frontpage=frontpage,
                evidence_summary="存在手术记录和手术安全核查表结构化记录，但核查表正文或记录时间不完整；作为边界样本复核证据质量。",
                matched_text=surgery_docs[0].get("label") or "手术记录",
                confidence=0.66,
                status="data_insufficient",
                extra={"safecheck_count": safecheck_count, **safecheck_stats},
            ),
        ]
    return make_candidate(
        qc_point_id="LX0609-04-03-01",
        case_type="negative",
        visit=visit,
        frontpage=frontpage,
        evidence_summary=f"存在手术记录，同时查询到 {safecheck_count} 条手术安全核查表{evidence_quality_note}。",
        matched_text=surgery_docs[0].get("label") or "手术记录",
        confidence=confidence,
        extra={"safecheck_count": safecheck_count, **safecheck_stats},
    )


DISCOVERERS = {
    "LX0609-01-01-01": discover_lx0609_001,
    "LX0609-01-02-01": discover_lx0609_002,
    "LX0609-12-01-01": discover_lx0609_016,
    "LX0609-12-01-02": discover_lx0609_017,
    "LX0609-03-01-02": discover_lx0609_021,
    "LX0609-04-03-01": discover_lx0609_032,
}


def discover_candidates(pool_id: str, *, max_visits: int | None = None, max_per_type: int = 10) -> dict[str, Any]:
    catalog = load_catalog()
    visits = load_sample_visit_ids(pool_id)
    if max_visits is not None:
        visits = visits[:max_visits]
    counters: Counter[tuple[str, str]] = Counter()
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for visit in visits:
        visit_id = visit["visit_id"]
        try:
            frontpage = load_frontpage(visit_id)
            docs = load_documents_by_type(visit_id)
        except Exception as exc:
            errors.append({"visit_id": visit_id, "error": str(exc)})
            continue
        for qc_point_id, discoverer in DISCOVERERS.items():
            if qc_point_id not in catalog:
                continue
            try:
                discovered = discoverer(visit, frontpage, docs)
            except Exception as exc:
                errors.append({"visit_id": visit_id, "qc_point_id": qc_point_id, "error": str(exc)})
                continue
            if not discovered:
                continue
            discovered_items = discovered if isinstance(discovered, list) else [discovered]
            for candidate in discovered_items:
                if not isinstance(candidate, dict):
                    continue
                key = (qc_point_id, candidate["suggested_case_type"])
                if counters[key] >= max_per_type:
                    continue
                counters[key] += 1
                candidate["candidate_id"] = f"{qc_point_id}-AUTO-{candidate['suggested_case_type'].upper()}-{counters[key]:03d}"
                candidate["customer_text"] = catalog.get(qc_point_id, {}).get("customer_text") or ""
                candidates.append(candidate)

    summary_by_rule: dict[str, dict[str, int]] = {}
    for qc_point_id in sorted(FORMAL_READY_QC_POINTS):
        summary_by_rule[qc_point_id] = {
            case_type: counters.get((qc_point_id, case_type), 0)
            for case_type in ("positive", "negative", "boundary")
        }
    return {
        "version": "2026-06-10",
        "pool_id": pool_id,
        "description": "formal_ready 质控点自动样本候选。只作为复核输入，不直接写入 golden cases。",
        "summary": {
            "visited": len(visits),
            "candidate_count": len(candidates),
            "covered_qc_points": len({item["qc_point_id"] for item in candidates}),
            "by_rule": summary_by_rule,
            "errors": len(errors),
        },
        "candidates": candidates,
        "errors": errors[:30],
    }


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    candidates = data.get("candidates") or []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(candidate.get("qc_point_id") or "")].append(candidate)

    lines = [
        "# 泸县0609 formal_ready 质控点样本候选",
        "",
        "## 说明",
        "",
        "本报告自动扫描客户样本池，为已具备执行基础的 `formal_ready` 质控点寻找 positive / negative / boundary 候选样本。候选样本必须人工复核后，才能导入正式 golden cases。",
        "",
        "## 汇总",
        "",
        f"- 样本池：{data.get('pool_id')}",
        f"- 扫描住院号：{summary.get('visited', 0)}",
        f"- 候选样本：{summary.get('candidate_count', 0)}",
        f"- 覆盖质控点：{summary.get('covered_qc_points', 0)}",
        f"- 错误数：{summary.get('errors', 0)}",
        "",
        "| 质控点 | Positive | Negative | Boundary |",
        "|---|---:|---:|---:|",
    ]
    for qc_point_id, counts in (summary.get("by_rule") or {}).items():
        lines.append(
            f"| {qc_point_id} | {counts.get('positive', 0)} | {counts.get('negative', 0)} | {counts.get('boundary', 0)} |"
        )

    lines.extend(["", "## 候选样本 Top 120", "", "| 候选ID | 类型 | 质控点 | 住院号 | 患者 | 科室 | 证据摘要 |", "|---|---|---|---|---|---|---|"])
    for candidate in candidates[:120]:
        lines.append(
            "| {candidate_id} | {case_type} | {qc_point_id} | {visit_id} | {patient_name} | {department} | {summary} |".format(
                candidate_id=candidate.get("candidate_id") or "",
                case_type=candidate.get("suggested_case_type") or "",
                qc_point_id=candidate.get("qc_point_id") or "",
                visit_id=candidate.get("visit_id") or "",
                patient_name=str(candidate.get("patient_name") or "").replace("|", "/"),
                department=str(candidate.get("department") or "").replace("|", "/"),
                summary=str(candidate.get("evidence_summary") or "").replace("|", "/")[:120],
            )
        )

    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            "1. 对候选样本逐条复核证据摘要和原始病历。",
            "2. 复核通过后，可转换为 `luxian_0609_golden_review_queue.csv` 的 accepted 行，或手工写入 golden cases。",
            "3. 对没有三类样本的质控点，继续扩大样本池或补充人工构造边界样本。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover golden case candidates for Luxian 0609 formal_ready rules.")
    parser.add_argument("--pool-id", required=True)
    parser.add_argument("--max-visits", type=int, default=None)
    parser.add_argument("--max-per-type", type=int, default=10)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = discover_candidates(args.pool_id, max_visits=args.max_visits, max_per_type=args.max_per_type)
    summary = data["summary"]
    print(f"visited={summary['visited']}")
    print(f"candidate_count={summary['candidate_count']}")
    print(f"covered_qc_points={summary['covered_qc_points']}")
    print(f"by_rule={summary['by_rule']}")
    print(f"errors={summary['errors']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
