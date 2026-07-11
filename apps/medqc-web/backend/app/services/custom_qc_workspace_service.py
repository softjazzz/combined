from __future__ import annotations

import html
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    MetaData,
    Table,
    and_,
    asc,
    desc,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.orm import Session

from .document_domain_alignment import (
    align_document_domain_fields,
    normalize_document_label,
)
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage


DEFAULT_DOCUMENT_TYPE = "日常病程记录"
DEFAULT_COMPLEXITY = "中复杂度"
DEFAULT_DEFECT_LEVEL = "一般缺陷"
DEFAULT_BATCH_JOB_PAGE_SIZE = 10

SEVERITY_TO_DEFECT_LEVEL = {
    "critical": "严重缺陷",
    "major": "一般缺陷",
    "minor": "提示性缺陷",
}

DEFECT_LEVEL_TO_SEVERITY = {
    "严重缺陷": "critical",
    "一般缺陷": "major",
    "提示性缺陷": "minor",
}


def _now_utc() -> datetime:
    return datetime.utcnow()


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        parsed = json.loads(text)
        return parsed
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _as_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _to_iso_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _to_iso_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value).strip()


def _draft_schema() -> Optional[str]:
    return "qc" if DB_SCHEMA_MODE == "split" else None


def _value_for_column(column: Any, value: Any) -> Any:
    if value is None:
        return None
    col_type_name = column.type.__class__.__name__.lower()
    if isinstance(value, (dict, list)):
        if "json" in col_type_name:
            return value
        return _safe_json_dumps(value)
    return value


def _map_severity_to_defect_level(severity: Optional[str]) -> str:
    return SEVERITY_TO_DEFECT_LEVEL.get(_safe_text(severity).lower(), DEFAULT_DEFECT_LEVEL)


def _map_defect_level_to_severity(defect_level: Optional[str]) -> str:
    return DEFECT_LEVEL_TO_SEVERITY.get(_safe_text(defect_level), "major")


def _normalize_scope(scope: Optional[str]) -> str:
    normalized = _safe_text(scope, "all").lower()
    if normalized not in {"all", "running", "final"}:
        return "all"
    return normalized


def _normalize_date_field(date_field: Optional[str]) -> str:
    normalized = _safe_text(date_field, "admission").lower()
    if normalized not in {"admission", "discharge"}:
        return "admission"
    return normalized


def _normalize_execution_mode(execution_mode: Optional[str]) -> str:
    value = _safe_text(execution_mode, "single").lower()
    return "multi" if value == "multi" else "single"


def _normalize_run_mode(run_mode: Optional[str]) -> str:
    value = _safe_text(run_mode, "serial").lower()
    return "serial" if value != "parallel" else "parallel"


def _normalize_string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    normalized: List[str] = []
    for item in values:
        text = _safe_text(item)
        if text:
            normalized.append(text)
    return normalized


@lru_cache(maxsize=1)
def _drafts_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    schema = _draft_schema()
    table = Table(
        "custom_qc_rule_drafts",
        metadata,
        # 主键与核心字段
        # schema 在 split 模式下写入 qc
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_code", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_requirement", sa.Text, nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("applicable_documents", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, default="major"),
        sa.Column("defect_level", sa.String(32), nullable=False, default=DEFAULT_DEFECT_LEVEL),
        sa.Column("complexity", sa.String(32), nullable=False, default=DEFAULT_COMPLEXITY),
        sa.Column("scene", sa.String(20), nullable=False, default="running"),
        sa.Column("generation_mode", sa.String(32), nullable=False, default="fallback_template"),
        sa.Column("examples", sa.Text, nullable=False, default="[]"),
        sa.Column("check_logic", sa.Text, nullable=False, default="{}"),
        sa.Column("last_test_summary", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, default="draft"),
        sa.Column("published_rule_id", sa.String(64)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _batch_jobs_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    schema = _draft_schema()
    table = Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False, index=True),
        sa.Column("rule_code", sa.String(32), nullable=False, index=True),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False, default="final"),
        sa.Column("scope", sa.String(20), nullable=False, default="final"),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("filters_json", sa.Text, nullable=False, default="{}"),
        sa.Column("record_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("job_kind", sa.String(20), nullable=False, default="leaf"),
        sa.Column("parent_job_id", sa.String(36), index=True),
        sa.Column("child_job_ids_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
        sa.Column("family_key", sa.String(64)),
        sa.Column("family_name", sa.String(64)),
        schema=schema,
    )
    metadata.create_all(bind=engine, checkfirst=True)
    _sync_batch_job_parent_columns(schema=schema)
    return table


def _sync_batch_job_parent_columns(*, schema: Optional[str]) -> None:
    if engine is None:
        return
    table_prefix = f"{schema}." if schema else ""
    column_sql = {
        "job_kind": "VARCHAR(20) DEFAULT 'leaf'",
        "parent_job_id": "VARCHAR(36)",
        "child_job_ids_json": "TEXT",
        "child_summary_json": "TEXT",
        "family_key": "VARCHAR(64)",
        "family_name": "VARCHAR(64)",
    }
    with engine.begin() as conn:
        for column_name, column_type in column_sql.items():
            conn.execute(
                text(
                    f"ALTER TABLE {table_prefix}custom_qc_batch_jobs "
                    f"ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                )
            )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_custom_qc_batch_jobs_parent_job_id "
                f"ON {table_prefix}custom_qc_batch_jobs(parent_job_id)"
            )
        )


@lru_cache(maxsize=8)
def _autoload_table(table_name: str, schemas: tuple[Optional[str], ...]) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    metadata = MetaData()
    last_error: Exception | None = None
    for schema in schemas:
        try:
            return Table(table_name, metadata, schema=schema, autoload_with=engine)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"unable to load table {table_name}")


def _qc_rules_table() -> Table:
    schema_candidates: tuple[Optional[str], ...]
    if DB_SCHEMA_MODE == "split":
        schema_candidates = ("qc", None)
    else:
        schema_candidates = (None, "qc")
    return _autoload_table("qc_rules", schema_candidates)


def _row_to_draft(row: Dict[str, Any]) -> Dict[str, Any]:
    check_logic = _safe_json_loads(row.get("check_logic"), {})
    examples = _safe_json_loads(row.get("examples"), [])
    applicable_documents = _safe_json_loads(row.get("applicable_documents"), [])
    document_type = normalize_document_label(row.get("document_type"), DEFAULT_DOCUMENT_TYPE)
    last_test_summary = _safe_json_loads(row.get("last_test_summary"), None)
    return {
        "id": _safe_text(row.get("id")),
        "rule_code": _safe_text(row.get("rule_code")),
        "name": _safe_text(row.get("name")),
        "description": _safe_text(row.get("description")),
        "source_requirement": _safe_text(row.get("source_requirement")),
        "prompt_template": _safe_text(row.get("prompt_template")),
        "document_type": document_type,
        "applicable_documents": applicable_documents if isinstance(applicable_documents, list) else [],
        "severity": _safe_text(row.get("severity"), "major"),
        "defect_level": _safe_text(row.get("defect_level"), DEFAULT_DEFECT_LEVEL),
        "complexity": _safe_text(row.get("complexity"), DEFAULT_COMPLEXITY),
        "scene": _safe_text(row.get("scene"), "running"),
        "generation_mode": _safe_text(row.get("generation_mode"), "fallback_template"),
        "examples": examples if isinstance(examples, list) else [],
        "check_logic": check_logic if isinstance(check_logic, dict) else {},
        "last_test_summary": last_test_summary,
        "status": _safe_text(row.get("status"), "draft"),
        "published_rule_id": _safe_text(row.get("published_rule_id")),
        "created_by": _safe_text(row.get("created_by")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _row_to_batch_job(row: Dict[str, Any], *, include_items: bool = True) -> Dict[str, Any]:
    filters = _safe_json_loads(row.get("filters_json"), {})
    record_ids = _safe_json_loads(row.get("record_ids_json"), [])
    summary = _safe_json_loads(row.get("summary_json"), None)
    items = _safe_json_loads(row.get("items_json"), []) if include_items else []
    failed_records = _safe_json_loads(row.get("failed_records_json"), []) if include_items else []
    child_job_ids = _safe_json_loads(row.get("child_job_ids_json"), [])
    child_summary = _safe_json_loads(row.get("child_summary_json"), {})
    filters_dict = filters if isinstance(filters, dict) else {}
    summary_dict = summary if isinstance(summary, dict) else None
    draft_ids = _normalize_string_list(filters_dict.get("draft_ids"))
    if not draft_ids:
        draft_id = _safe_text(row.get("draft_id"))
        if draft_id:
            draft_ids = [draft_id]
    execution_mode = _normalize_execution_mode(filters_dict.get("execution_mode"))
    if execution_mode == "single" and len(draft_ids) > 1:
        execution_mode = "multi"
    run_mode = _normalize_run_mode(filters_dict.get("run_mode"))
    progress = {}
    if summary_dict is not None:
        progress_candidate = summary_dict.get("progress")
        if isinstance(progress_candidate, dict):
            progress = progress_candidate
    rule_count = int((summary_dict or {}).get("rule_count") or 0)
    if rule_count <= 0:
        rule_count = max(1, len(draft_ids))
    normalized_items: List[Dict[str, Any]] = []
    if isinstance(items, list):
        for raw_item in items:
            if isinstance(raw_item, dict):
                normalized_items.append(
                    {
                        **raw_item,
                        "rule_code": _safe_text(raw_item.get("rule_code")) or _safe_text(row.get("rule_code")),
                        "rule_name": _safe_text(raw_item.get("rule_name")) or _safe_text(row.get("rule_name")),
                    }
                )
    rule_results: List[Dict[str, Any]] = []
    if summary_dict is not None:
        candidate = summary_dict.get("rule_results")
        if isinstance(candidate, list):
            rule_results = candidate
    status_value = _safe_text(row.get("status"), "queued")
    return {
        "id": _safe_text(row.get("id")),
        "draft_id": _safe_text(row.get("draft_id")),
        "draft_ids": draft_ids,
        "rule_code": _safe_text(row.get("rule_code")),
        "rule_name": _safe_text(row.get("rule_name")),
        "scene": _safe_text(row.get("scene"), "final"),
        "scope": _safe_text(row.get("scope"), "final"),
        "status": status_value,
        "execution_mode": execution_mode,
        "rule_count": int(rule_count),
        "run_mode": run_mode,
        "filters": filters_dict,
        "record_ids": record_ids if isinstance(record_ids, list) else [],
        "summary": summary_dict,
        "progress": progress,
        "items": normalized_items,
        "failed_records": failed_records if isinstance(failed_records, list) else [],
        "rule_results": rule_results,
        "cancellable": status_value in {"queued", "running"},
        "error_message": _safe_text(row.get("error_message")),
        "created_by": _safe_text(row.get("created_by")),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
        "total_records": int(row.get("total_records") or 0),
        "success_count": int(row.get("success_count") or 0),
        "failed_count": int(row.get("failed_count") or 0),
        "issue_records": int(row.get("issue_records") or 0),
        "compliant_records": int(row.get("compliant_records") or 0),
        "total_tokens": int(row.get("total_tokens") or 0),
        "total_processing_time": float(row.get("total_processing_time") or 0.0),
        "job_kind": _safe_text(row.get("job_kind"), "leaf") or "leaf",
        "parent_job_id": _safe_text(row.get("parent_job_id")),
        "child_job_ids": child_job_ids if isinstance(child_job_ids, list) else [],
        "child_summary": child_summary if isinstance(child_summary, dict) else {},
        "family_key": _safe_text(row.get("family_key")),
        "family_name": _safe_text(row.get("family_name")),
    }


def _extract_rule_code_number(rule_code: str) -> int:
    match = re.match(r"^LXE-(\d{1,})$", rule_code.strip().upper())
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def _session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
    return SessionLocal()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_export_performance_profile(summary: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    raw_profile = summary.get("performance_profile") if isinstance(summary.get("performance_profile"), dict) else {}
    tokens_total = _to_int(
        raw_profile.get("tokens_total"),
        _to_int(summary.get("total_tokens"), _to_int(job.get("total_tokens"))),
    )
    prompt_tokens = _to_int(raw_profile.get("prompt_tokens"))
    completion_tokens = _to_int(raw_profile.get("completion_tokens"))
    unattributed_tokens = _to_int(raw_profile.get("unattributed_tokens"))
    if unattributed_tokens <= 0 and tokens_total > 0:
        unattributed_tokens = max(0, tokens_total - prompt_tokens - completion_tokens)
    token_breakdown_complete = raw_profile.get("token_breakdown_complete")
    if token_breakdown_complete is None:
        token_breakdown_complete = unattributed_tokens == 0
    return {
        "tokens_total": tokens_total,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "unattributed_tokens": unattributed_tokens,
        "token_breakdown_complete": bool(token_breakdown_complete),
        "wall_clock_time_seconds": _to_float(raw_profile.get("wall_clock_time_seconds")),
        "total_processing_time_seconds": _to_float(
            raw_profile.get("total_processing_time_seconds"),
            _to_float(summary.get("total_processing_time"), _to_float(job.get("total_processing_time"))),
        ),
        "llm_call_count": _to_int(raw_profile.get("llm_call_count")),
        "actual_llm_pack_call_count": _to_int(raw_profile.get("actual_llm_pack_call_count")),
    }


def _format_export_integer(value: Any) -> str:
    return f"{_to_int(value):,}"


def _map_scene_label(scene: Any) -> str:
    mapping = {
        "running": "运行病历",
        "final": "终末病历",
        "all": "全病历",
    }
    key = _safe_text(scene).lower()
    return mapping.get(key, _safe_text(scene, "-"))


def _map_scope_label(scope: Any) -> str:
    return _map_scene_label(scope)


def _map_job_status_label(status: Any) -> str:
    mapping = {
        "queued": "排队中",
        "running": "执行中",
        "completed": "已完成",
        "failed": "执行失败",
        "canceled": "已取消",
    }
    key = _safe_text(status).lower()
    return mapping.get(key, _safe_text(status, "-"))


def _map_item_status_label(status: Any, is_compliant: Any) -> str:
    key = _safe_text(status).lower()
    if key == "non_compliant":
        return "不合规"
    if key == "ai_suggested_non_compliant":
        return "AI判断：疑似问题"
    if key == "ai_suggested_compliant":
        return "AI判断：未见问题"
    if key == "data_gap":
        return "数据不足"
    if key == "not_applicable":
        return "不适用"
    if key == "not_executed":
        return "未执行"
    if key == "technical_error":
        return "技术异常"
    if key == "uncertain":
        return "AI判断"
    if key == "compliant":
        return "合规"
    if key == "failed":
        return "失败"
    if is_compliant is True:
        return "合规"
    if is_compliant is False:
        return "不合规"
    return _safe_text(status, "未判定")


def _build_filter_text(filters: Dict[str, Any]) -> str:
    if not isinstance(filters, dict):
        return "未设置筛选条件"
    parts: List[str] = []
    department = _safe_text(filters.get("department"))
    doctor = _safe_text(filters.get("doctor"))
    keyword = _safe_text(filters.get("keyword"))
    start_date = _safe_text(filters.get("start_date"))
    end_date = _safe_text(filters.get("end_date"))
    date_field = _safe_text(filters.get("date_field"))

    if department:
        parts.append(f"科室：{department}")
    if doctor:
        parts.append(f"医生：{doctor}")
    if keyword:
        parts.append(f"关键字：{keyword}")
    if start_date or end_date:
        date_field_zh = "出院日期" if date_field == "discharge" else "入院日期"
        parts.append(f"{date_field_zh}：{start_date or '-'} ~ {end_date or '-'}")
    if not parts:
        return "未设置筛选条件"
    return "；".join(parts)


_HTML_EXPORT_SENSITIVE_TOKENS = {
    "prompt",
    "raw_response",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "llm_raw_output",
}

_HTML_EXPORT_INTERNAL_LABELS = (
    "LLM 语义规则",
    "LLM语义规则",
    "证据模板",
    "映射执行规则",
    "来源未标注",
    "raw_response",
    "prompt",
    "embedding",
    "medical_text",
    "record_content",
    "documents",
    "bundle",
    "llm_raw_output",
)


def _html_escape(value: Any) -> str:
    return html.escape(_safe_text(value), quote=True)


def _truncate_export_text(value: Any, limit: int = 360) -> str:
    text_value = re.sub(r"\s+", " ", _safe_text(value)).strip()
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit].rstrip() + "..."


def _sanitize_export_text(value: Any, limit: int = 420) -> str:
    text_value = _safe_text(value)
    if not text_value:
        return ""
    # 旧证据字符串经常把内部模板、规则映射和可读证据拼在一起；导出时只保留客户可理解的证据段。
    for marker in ("执行证据：", "关键证据：", "证据："):
        if marker in text_value:
            text_value = text_value.split(marker, 1)[1]
            break
    text_value = text_value.replace("来源未标注 · evidence：", "")
    parts = re.split(r"[；;\n]+", text_value)
    kept: List[str] = []
    for part in parts:
        normalized = _safe_text(part)
        if not normalized:
            continue
        if any(label in normalized for label in _HTML_EXPORT_INTERNAL_LABELS):
            continue
        kept.append(normalized)
    if kept:
        text_value = "；".join(kept)
    for token in _HTML_EXPORT_SENSITIVE_TOKENS:
        text_value = re.sub(re.escape(token), "", text_value, flags=re.IGNORECASE)
    review_replacements = (
        ("待人工复核", "AI判断后建议确认"),
        ("待人工核对", "AI判断后建议确认"),
        ("建议人工复核", "建议结合原文确认"),
        ("建议人工核对", "建议结合原文确认"),
        ("需人工复核", "需结合原文确认"),
        ("需人工核对", "需结合原文确认"),
        ("需要人工复核", "需要结合原文确认"),
        ("需要人工核对", "需要结合原文确认"),
        ("人工复核", "结合原文确认"),
        ("人工核对", "结合原文确认"),
    )
    for source, target in review_replacements:
        text_value = text_value.replace(source, target)
    return _truncate_export_text(text_value, limit=limit)


def _extract_export_customer_evidence_text(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return ""
    for marker in ("执行证据：", "关键证据：", "证据："):
        if marker in raw:
            raw = raw.split(marker, 1)[1]
            break
    return _sanitize_export_text(raw, limit=720)


def _normalize_export_evidence_label(value: str) -> str:
    label = _safe_text(value)
    label_map = {
        "authored_at": "记录时间",
        "record_time": "记录时间",
        "submit_time": "提交时间",
        "submitted_at": "提交时间",
        "admission_time": "入院时间",
        "discharge_time": "出院时间",
        "deadline": "截止时间",
        "elapsed": "间隔",
        "delta": "差值",
    }
    return label_map.get(label, label)


def _parse_export_evidence_parts(value: Any, *, limit: int = 8) -> List[Dict[str, str]]:
    text_value = _extract_export_customer_evidence_text(value)
    if not text_value:
        return []
    parts: List[Dict[str, str]] = []
    for raw_part in re.split(r"[；;\n]+", text_value):
        raw_part = _safe_text(raw_part)
        if len(raw_part) < 4 or "：" not in raw_part:
            continue
        segments = [segment.strip() for segment in raw_part.split("：") if segment.strip()]
        if len(segments) < 2:
            continue
        first = _normalize_export_evidence_label(segments[0])
        second_is_field = len(segments) >= 3 and re.match(r"^[a-z_]+$", segments[1] or "", flags=re.IGNORECASE)
        label = f"{first} · {_normalize_export_evidence_label(segments[1])}" if second_is_field else first
        value_text = "：".join(segments[2:] if second_is_field else segments[1:]).strip()
        if not label or not value_text:
            continue
        if any(internal in label for internal in _HTML_EXPORT_INTERNAL_LABELS):
            continue
        parts.append({"label": label, "value": _truncate_export_text(value_text, 180)})
        if len(parts) >= limit:
            break
    return parts


def _export_item_status_key(item: Dict[str, Any]) -> str:
    status_key = _safe_text((item or {}).get("status")).lower()
    is_compliant = (item or {}).get("is_compliant")
    if status_key:
        if status_key == "failed":
            return "technical_error"
        return status_key
    if is_compliant is True:
        return "compliant"
    if is_compliant is False:
        return "non_compliant"
    return "uncertain"


def _status_tone_class(status_key: str) -> str:
    if status_key == "non_compliant":
        return "danger"
    if status_key in {
        "ai_suggested_non_compliant",
        "data_gap",
        "uncertain",
        "technical_error",
        "not_executed",
    }:
        return "warning"
    if status_key in {"compliant", "ai_suggested_compliant"}:
        return "success"
    if status_key == "not_applicable":
        return "neutral"
    return "muted"


def _extract_structured_evidence(item: Dict[str, Any]) -> List[Dict[str, str]]:
    evidence_candidates: List[Any] = []
    for key in ("evidence_items", "evidence_chain", "evidence_chains", "evidences", "evidence_details"):
        raw = item.get(key)
        if isinstance(raw, list):
            evidence_candidates.extend(raw)
    rows: List[Dict[str, str]] = []
    for raw in evidence_candidates:
        if not isinstance(raw, dict):
            continue
        quote = _sanitize_export_text(raw.get("quote") or raw.get("text") or raw.get("snippet") or raw.get("value"), 220)
        source = _safe_text(
            raw.get("source_document")
            or raw.get("source_table")
            or raw.get("document_type")
            or raw.get("source")
            or raw.get("source_field")
        )
        field = _safe_text(raw.get("source_field") or raw.get("field"))
        threshold = _safe_text(raw.get("threshold"))
        actual = _safe_text(raw.get("actual_value") or raw.get("actual"))
        delta = _safe_text(raw.get("delta") or raw.get("difference"))
        if not any([quote, source, field, threshold, actual, delta]):
            continue
        rows.append(
            {
                "source": source,
                "field": field,
                "quote": quote,
                "threshold": threshold,
                "actual": actual,
                "delta": delta,
            }
        )
    return rows[:4]


def _format_rule_code_list(values: Any, limit: int = 8) -> str:
    if not isinstance(values, list):
        return "-"
    cleaned = [_safe_text(item) for item in values if _safe_text(item)]
    if not cleaned:
        return "-"
    preview = "、".join(cleaned[:limit])
    if len(cleaned) > limit:
        preview += f" +{len(cleaned) - limit}"
    return preview


@dataclass
class WorkspaceListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


@dataclass
class WorkspaceBatchJobListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CustomQCWorkspaceService:
    def __init__(self) -> None:
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured; custom qc workspace unavailable")
        self._draft_table = _drafts_table()
        self._batch_job_table = _batch_jobs_table()

    @staticmethod
    def _aggregate_child_input_profiles(child_profiles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        input_profiles = [
            dict(profile.get("input_profile") or {})
            for profile in child_profiles
            if isinstance(profile.get("input_profile"), dict) and profile.get("input_profile")
        ]
        if not input_profiles:
            return {}

        source_table_counts: Dict[str, int] = {}
        source_table_text_lengths: Dict[str, int] = {}
        available_family_contexts = set()
        family_profiles: Dict[str, Dict[str, Any]] = {}
        for profile in input_profiles:
            for key, value in dict(profile.get("source_table_counts") or {}).items():
                source_table_counts[str(key)] = source_table_counts.get(str(key), 0) + _safe_int(value)
            for key, value in dict(profile.get("source_table_text_lengths") or {}).items():
                source_table_text_lengths[str(key)] = source_table_text_lengths.get(str(key), 0) + _safe_int(value)
            for family in list(profile.get("available_family_contexts") or []):
                if str(family or "").strip():
                    available_family_contexts.add(str(family).strip())
            for family, family_profile in dict(profile.get("family_profiles") or {}).items():
                family_key = str(family or "").strip()
                if not family_key or not isinstance(family_profile, dict):
                    continue
                target = family_profiles.setdefault(
                    family_key,
                    {
                        "family": family_key,
                        "ready_record_count": 0,
                        "document_count": 0,
                        "text_char_count": 0,
                        "present_source_table_count": 0,
                        "missing_source_table_count": 0,
                    },
                )
                for numeric_key in (
                    "ready_record_count",
                    "document_count",
                    "text_char_count",
                    "present_source_table_count",
                    "missing_source_table_count",
                ):
                    target[numeric_key] = _safe_int(target.get(numeric_key)) + _safe_int(
                        family_profile.get(numeric_key)
                    )

        return {
            "schema_version": "luxian_0609_parent_input_perf_summary_v1",
            "basis": "child_job_input_profile_summary",
            "child_input_profile_count": len(input_profiles),
            "record_count_sum": sum(_safe_int(profile.get("record_count")) for profile in input_profiles),
            "document_count_sum": sum(_safe_int(profile.get("document_count")) for profile in input_profiles),
            "primary_text_char_count_sum": sum(
                _safe_int(profile.get("primary_text_char_count")) for profile in input_profiles
            ),
            "medical_text_char_count_sum": sum(
                _safe_int(profile.get("medical_text_char_count")) for profile in input_profiles
            ),
            "source_table_counts": dict(sorted(source_table_counts.items())),
            "source_table_text_lengths": dict(sorted(source_table_text_lengths.items())),
            "available_family_contexts": sorted(available_family_contexts),
            "family_profiles": dict(sorted(family_profiles.items())),
        }

    @staticmethod
    def _aggregate_child_performance_profiles(child_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        child_profiles = [
            dict((child.get("summary") or {}).get("performance_profile") or {})
            for child in child_jobs
            if isinstance((child.get("summary") or {}).get("performance_profile"), dict)
        ]
        child_profiles = [profile for profile in child_profiles if profile]
        if not child_profiles:
            return {}

        status_breakdown: Dict[str, int] = {}
        for child in child_jobs:
            for key, value in dict((child.get("summary") or {}).get("status_breakdown") or {}).items():
                status_breakdown[str(key)] = status_breakdown.get(str(key), 0) + _safe_int(value)

        profile = {
            "schema_version": "luxian_0609_parent_job_perf_v1",
            "basis": "child_job_performance_profiles",
            "child_job_count": len(child_jobs),
            "profiled_child_job_count": len(child_profiles),
            "total_records": sum(_safe_int(profile.get("total_records")) for profile in child_profiles),
            "customer_rule_count": sum(_safe_int(profile.get("customer_rule_count")) for profile in child_profiles),
            "execution_rule_count": sum(_safe_int(profile.get("execution_rule_count")) for profile in child_profiles),
            "result_count": sum(_safe_int(profile.get("result_count")) for profile in child_profiles),
            "wall_clock_time_seconds": sum(
                _safe_float(profile.get("wall_clock_time_seconds")) for profile in child_profiles
            ),
            "sum_rule_duration_seconds": sum(
                _safe_float(profile.get("sum_rule_duration_seconds")) for profile in child_profiles
            ),
            "llm_call_count": sum(_safe_int(profile.get("llm_call_count")) for profile in child_profiles),
            "program_call_count": sum(_safe_int(profile.get("program_call_count")) for profile in child_profiles),
            "actual_llm_pack_call_count": sum(
                _safe_int(profile.get("actual_llm_pack_call_count")) for profile in child_profiles
            ),
            "retry_count": sum(_safe_int(profile.get("retry_count")) for profile in child_profiles),
            "provider_error_count": sum(_safe_int(profile.get("provider_error_count")) for profile in child_profiles),
            "timeout_count": sum(_safe_int(profile.get("timeout_count")) for profile in child_profiles),
            "rate_limit_count": sum(_safe_int(profile.get("rate_limit_count")) for profile in child_profiles),
            "pack_retry_attempts": sum(_safe_int(profile.get("pack_retry_attempts")) for profile in child_profiles),
            "tokens_total": sum(_safe_int(profile.get("tokens_total")) for profile in child_profiles),
            "prompt_tokens": sum(_safe_int(profile.get("prompt_tokens")) for profile in child_profiles),
            "completion_tokens": sum(_safe_int(profile.get("completion_tokens")) for profile in child_profiles),
            "unattributed_tokens": sum(
                _safe_int(
                    profile.get("unattributed_tokens"),
                    max(
                        0,
                        _safe_int(profile.get("tokens_total"))
                        - _safe_int(profile.get("prompt_tokens"))
                        - _safe_int(profile.get("completion_tokens")),
                    ),
                )
                for profile in child_profiles
            ),
            "context_tokens_estimate": sum(
                _safe_int(profile.get("context_tokens_estimate")) for profile in child_profiles
            ),
            "status_breakdown": dict(sorted(status_breakdown.items())),
            "children": [
                {
                    "job_id": str(child.get("id") or ""),
                    "status": str(child.get("status") or ""),
                    "rule_family": str((child.get("filters") or {}).get("luxian_rule_family") or ""),
                    "performance_profile": dict((child.get("summary") or {}).get("performance_profile") or {}),
                }
                for child in child_jobs
            ],
            "input_profile": CustomQCWorkspaceService._aggregate_child_input_profiles(child_profiles),
        }
        profile["token_breakdown_complete"] = _safe_int(profile.get("unattributed_tokens")) == 0
        return profile

    def _aggregate_parent_job(
        self,
        session: Session,
        parent_job: Dict[str, Any],
        *,
        include_items: bool = True,
    ) -> Dict[str, Any]:
        if str(parent_job.get("job_kind") or "").strip().lower() != "parent":
            return parent_job
        child_job_ids = [
            str(item or "").strip()
            for item in list(parent_job.get("child_job_ids") or [])
            if str(item or "").strip()
        ]
        if child_job_ids:
            child_rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(self._batch_job_table.c.id.in_(child_job_ids))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
        else:
            child_rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(self._batch_job_table.c.parent_job_id == parent_job.get("id"))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
        child_jobs = [_row_to_batch_job(dict(row), include_items=include_items) for row in child_rows]
        if not child_jobs:
            return parent_job

        statuses = [str(item.get("status") or "queued").strip().lower() for item in child_jobs]
        completed = sum(1 for item in statuses if item == "completed")
        failed = sum(1 for item in statuses if item == "failed")
        canceled = sum(1 for item in statuses if item == "canceled")
        running = sum(1 for item in statuses if item == "running")
        queued = sum(1 for item in statuses if item == "queued")
        if running or queued:
            aggregate_status = "running" if running else "queued"
        elif failed:
            aggregate_status = "failed"
        elif canceled == len(child_jobs):
            aggregate_status = "canceled"
        else:
            aggregate_status = "completed"

        status_breakdown: Dict[str, int] = {}
        total_tokens = 0
        total_processing_time = 0.0
        issue_records = 0
        compliant_records = 0
        failed_count = 0
        success_count = 0
        for child in child_jobs:
            child_summary = child.get("summary") or {}
            for key, value in dict(child_summary.get("status_breakdown") or {}).items():
                status_breakdown[str(key)] = status_breakdown.get(str(key), 0) + int(value or 0)
            total_tokens += int(child.get("total_tokens") or child_summary.get("total_tokens") or 0)
            total_processing_time += float(child.get("total_processing_time") or child_summary.get("total_processing_time") or 0.0)
            issue_records += int(child.get("issue_records") or child_summary.get("issue_records") or 0)
            compliant_records += int(child.get("compliant_records") or child_summary.get("compliant_records") or 0)
            failed_count += int(child.get("failed_count") or child_summary.get("failed_count") or 0)
            success_count += int(child.get("success_count") or child_summary.get("success_count") or 0)

        parent_summary = dict(parent_job.get("summary") or {})
        parent_performance_profile = self._aggregate_child_performance_profiles(child_jobs)
        parent_summary.update(
            {
                "child_job_count": len(child_jobs),
                "completed_child_count": completed,
                "failed_child_count": failed,
                "canceled_child_count": canceled,
                "running_child_count": running,
                "queued_child_count": queued,
                "status_breakdown": status_breakdown,
                "progress": {
                    **(parent_summary.get("progress") if isinstance(parent_summary.get("progress"), dict) else {}),
                    "step_key": aggregate_status,
                    "processed_records": completed + failed + canceled,
                    "total_records": len(child_jobs),
                    "completed_children": completed,
                    "total_children": len(child_jobs),
                },
            }
        )
        if parent_performance_profile:
            parent_summary["performance_profile"] = parent_performance_profile
        return {
            **parent_job,
            "status": aggregate_status,
            "summary": parent_summary,
            "progress": parent_summary.get("progress") or {},
            "children": child_jobs,
            "child_jobs": child_jobs,
            "cancellable": any(status in {"queued", "running"} for status in statuses),
            "success_count": success_count,
            "failed_count": failed_count,
            "issue_records": issue_records,
            "compliant_records": compliant_records,
            "total_tokens": total_tokens,
            "total_processing_time": total_processing_time,
        }

    def _next_rule_code(self, session: Session) -> str:
        max_num = 0
        draft_codes = session.execute(select(self._draft_table.c.rule_code)).scalars().all()
        for code in draft_codes:
            max_num = max(max_num, _extract_rule_code_number(_safe_text(code)))

        try:
            qc_rules_table = _qc_rules_table()
            qc_codes = session.execute(select(qc_rules_table.c.rule_code)).scalars().all()
            for code in qc_codes:
                max_num = max(max_num, _extract_rule_code_number(_safe_text(code)))
        except Exception:
            pass
        return f"LXE-{str(max_num + 1).zfill(4)}"

    def _build_records_query(
        self,
        session: Session,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
    ):
        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_datetime,
            DischargeRecord.discharge_date,
            DischargeRecord.update_time,
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            AdmissionRecord.update_time,
        )
        query = (
            session.query(
                MedicalRecordFrontpage,
                discharge_dt_expr.label("effective_discharge_datetime"),
                admission_dt_expr.label("effective_admission_datetime"),
            )
            .outerjoin(
                DischargeRecord,
                and_(
                    DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                AdmissionRecord,
                and_(
                    AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
        )

        if scope_value == "final":
            query = query.filter(discharge_dt_expr.is_not(None))
        elif scope_value == "running":
            query = query.filter(discharge_dt_expr.is_(None))

        if department:
            query = query.filter(dept_expr == department)
        if doctor:
            query = query.filter(MedicalRecordFrontpage.attending_physician_sign == doctor)

        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MedicalRecordFrontpage.visit_id.ilike(kw),
                    MedicalRecordFrontpage.name.ilike(kw),
                    MedicalRecordFrontpage.mr_no.ilike(kw),
                    MedicalRecordFrontpage.inpat_no.ilike(kw),
                )
            )

        if record_ids:
            normalized_ids = [_safe_text(item) for item in record_ids if _safe_text(item)]
            if normalized_ids:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))

        date_col = (
            admission_dt_expr
            if date_field_value == "admission"
            else discharge_dt_expr
        )
        if start:
            query = query.filter(func.date(date_col) >= start)
        if end:
            query = query.filter(func.date(date_col) <= end)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        source_row = row
        effective_discharge_datetime = None
        effective_admission_datetime = None
        if isinstance(row, tuple):
            source_row = row[0]
            if len(row) > 1:
                effective_discharge_datetime = row[1]
            if len(row) > 2:
                effective_admission_datetime = row[2]
        effective_discharge_datetime = effective_discharge_datetime or source_row.discharge_datetime
        effective_admission_datetime = effective_admission_datetime or source_row.admission_datetime
        item_scope = "final" if effective_discharge_datetime else "running"
        item_department = _safe_text(source_row.discharge_dept_name or source_row.admission_dept_name)
        return {
            "record_id": _safe_text(source_row.visit_id),
            "visit_id": _safe_text(source_row.visit_id),
            "patient_name": _safe_text(source_row.name),
            "mr_no": _safe_text(source_row.mr_no),
            "inpat_no": _safe_text(source_row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(source_row.attending_physician_sign),
            "admission_date": _to_iso_date(effective_admission_datetime),
            "discharge_date": _to_iso_date(effective_discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text_length": len(_safe_text(source_row.record_content)),
        }

    def list_drafts(
        self,
        *,
        created_by: str,
        status: Optional[str],
        query: Optional[str],
        page: int,
        page_size: int,
    ) -> WorkspaceListResult:
        session = _session()
        try:
            clauses = [self._draft_table.c.created_by == created_by]
            if status and status in {"draft", "published"}:
                clauses.append(self._draft_table.c.status == status)
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._draft_table.c.rule_code.ilike(keyword),
                        self._draft_table.c.name.ilike(keyword),
                        self._draft_table.c.description.ilike(keyword),
                    )
                )

            where_clause = and_(*clauses)
            total_stmt = select(func.count()).select_from(self._draft_table).where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)

            stmt = (
                select(self._draft_table)
                .where(where_clause)
                .order_by(desc(self._draft_table.c.updated_at), desc(self._draft_table.c.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            items = [_row_to_draft(dict(row)) for row in rows]
            return WorkspaceListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def get_draft(self, *, draft_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            row = session.execute(stmt).mappings().first()
            if not row:
                return None
            return _row_to_draft(dict(row))
        finally:
            session.close()

    def create_draft(self, *, created_by: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        session = _session()
        try:
            now = _now_utc()
            severity = _safe_text(payload.get("severity"), "major").lower()
            document_type, applicable_documents, check_logic = align_document_domain_fields(
                document_type=payload.get("document_type"),
                applicable_documents=payload.get("applicable_documents"),
                check_logic=payload.get("check_logic") or {},
            )
            draft_id = str(uuid.uuid4())
            row_payload = {
                "id": draft_id,
                "rule_code": self._next_rule_code(session),
                "name": _safe_text(payload.get("name"), "未命名规则"),
                "description": _safe_text(payload.get("description"), ""),
                "source_requirement": _safe_text(
                    payload.get("source_requirement") or payload.get("description"), ""
                ),
                "prompt_template": _safe_text(payload.get("prompt_template"), ""),
                "document_type": document_type,
                "applicable_documents": _safe_json_dumps(applicable_documents),
                "severity": severity if severity in {"critical", "major", "minor"} else "major",
                "defect_level": _safe_text(
                    payload.get("defect_level"), _map_severity_to_defect_level(severity)
                ),
                "complexity": _safe_text(payload.get("complexity"), DEFAULT_COMPLEXITY),
                "scene": _safe_text(payload.get("scene"), "running"),
                "generation_mode": _safe_text(payload.get("generation_mode"), "fallback_template"),
                "examples": _safe_json_dumps(payload.get("examples") or []),
                "check_logic": _safe_json_dumps(check_logic),
                "last_test_summary": _safe_json_dumps(payload.get("last_test_summary") or None),
                "status": "draft",
                "published_rule_id": None,
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            }
            session.execute(self._draft_table.insert().values(**row_payload))
            session.commit()
            return self.get_draft(draft_id=draft_id, created_by=created_by) or _row_to_draft(row_payload)
        finally:
            session.close()

    def update_draft(self, *, draft_id: str, created_by: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            existing_stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            existing = session.execute(existing_stmt).mappings().first()
            if not existing:
                return None

            patch: Dict[str, Any] = {"updated_at": _now_utc()}
            editable_fields = {
                "name",
                "description",
                "source_requirement",
                "prompt_template",
                "document_type",
                "severity",
                "defect_level",
                "complexity",
                "scene",
                "generation_mode",
                "published_rule_id",
                "status",
            }
            for key in editable_fields:
                if key in payload and payload[key] is not None:
                    patch[key] = payload[key]

            existing_check_logic = _safe_json_loads(existing.get("check_logic"), {})
            aligned_document_type, aligned_applicable_documents, aligned_check_logic = align_document_domain_fields(
                document_type=patch.get("document_type", existing.get("document_type")),
                applicable_documents=(
                    payload.get("applicable_documents")
                    if "applicable_documents" in payload
                    else _safe_json_loads(existing.get("applicable_documents"), [])
                ),
                check_logic=(
                    payload.get("check_logic")
                    if "check_logic" in payload
                    else existing_check_logic
                ),
            )
            patch["document_type"] = aligned_document_type
            patch["applicable_documents"] = _safe_json_dumps(aligned_applicable_documents)
            patch["check_logic"] = _safe_json_dumps(aligned_check_logic)

            if "examples" in payload:
                patch["examples"] = _safe_json_dumps(payload.get("examples") or [])
            if "last_test_summary" in payload:
                patch["last_test_summary"] = _safe_json_dumps(payload.get("last_test_summary"))

            if "severity" in patch and "defect_level" not in patch:
                patch["defect_level"] = _map_severity_to_defect_level(_safe_text(patch.get("severity")))

            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(**patch)
            )
            session.commit()
            return self.get_draft(draft_id=draft_id, created_by=created_by)
        finally:
            session.close()

    def delete_draft(self, *, draft_id: str, created_by: str) -> bool:
        session = _session()
        try:
            result = session.execute(
                self._draft_table.delete().where(
                    and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
                )
            )
            session.commit()
            return bool(result.rowcount and result.rowcount > 0)
        finally:
            session.close()

    def _build_records_query(
        self,
        session: Session,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
    ):
        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_datetime,
            DischargeRecord.discharge_date,
            DischargeRecord.update_time,
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            AdmissionRecord.update_time,
        )
        query = (
            session.query(MedicalRecordFrontpage)
            .outerjoin(
                DischargeRecord,
                and_(
                    DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                AdmissionRecord,
                and_(
                    AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
        )

        if scope_value == "final":
            query = query.filter(discharge_dt_expr.is_not(None))
        elif scope_value == "running":
            query = query.filter(discharge_dt_expr.is_(None))

        if department:
            query = query.filter(dept_expr == department)
        if doctor:
            query = query.filter(MedicalRecordFrontpage.attending_physician_sign == doctor)

        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MedicalRecordFrontpage.visit_id.ilike(kw),
                    MedicalRecordFrontpage.name.ilike(kw),
                    MedicalRecordFrontpage.mr_no.ilike(kw),
                    MedicalRecordFrontpage.inpat_no.ilike(kw),
                )
            )

        if record_ids:
            normalized_ids = [_safe_text(item) for item in record_ids if _safe_text(item)]
            if normalized_ids:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))

        date_col = (
            admission_dt_expr
            if date_field_value == "admission"
            else discharge_dt_expr
        )
        if start:
            query = query.filter(func.date(date_col) >= start)
        if end:
            query = query.filter(func.date(date_col) <= end)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        effective_discharge_datetime = row.discharge_datetime or getattr(row, "update_time", None)
        item_scope = "final" if effective_discharge_datetime else "running"
        item_department = _safe_text(row.discharge_dept_name or row.admission_dept_name)
        return {
            "institute_id": _safe_text(getattr(row, "institute_id", "")),
            "patient_id": _safe_text(getattr(row, "patient_id", "")),
            "record_id": _safe_text(row.visit_id),
            "visit_id": _safe_text(row.visit_id),
            "patient_name": _safe_text(row.name),
            "mr_no": _safe_text(row.mr_no),
            "inpat_no": _safe_text(row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(row.attending_physician_sign),
            "admission_date": _to_iso_date(row.admission_datetime),
            "discharge_date": _to_iso_date(effective_discharge_datetime),
            "admission_datetime": _to_iso_datetime(row.admission_datetime),
            "discharge_datetime": _to_iso_datetime(effective_discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text": _safe_text(row.record_content),
            "medical_text_length": len(_safe_text(row.record_content)),
        }

    def list_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> WorkspaceListResult:
        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
            )
            total = int(query.count())
            rows = (
                query.order_by(
                    desc(MedicalRecordFrontpage.discharge_datetime),
                    desc(MedicalRecordFrontpage.admission_datetime),
                )
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
                .all()
            )
            items = [self._serialize_record_row(row) for row in rows]
            return WorkspaceListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def get_record_filters(
        self,
        *,
        scope: str,
        department: Optional[str],
    ) -> Dict[str, Any]:
        session = _session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
            )
            base_query = self._build_records_query(
                session,
                scope=scope,
                department=None,
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
            )

            dept_query = base_query.with_entities(dept_expr.label("department")).filter(
                dept_expr.is_not(None), dept_expr != ""
            )
            departments = [row.department for row in dept_query.distinct().order_by(asc("department")).all()]

            doctor_query = base_query.with_entities(
                MedicalRecordFrontpage.attending_physician_sign.label("doctor")
            ).filter(
                MedicalRecordFrontpage.attending_physician_sign.is_not(None),
                MedicalRecordFrontpage.attending_physician_sign != "",
            )
            if department:
                doctor_query = doctor_query.filter(dept_expr == department)
            doctors = [row.doctor for row in doctor_query.distinct().order_by(asc("doctor")).all()]

            date_bounds = base_query.with_entities(
                func.min(MedicalRecordFrontpage.admission_datetime).label("min_admission"),
                func.max(MedicalRecordFrontpage.admission_datetime).label("max_admission"),
                func.min(MedicalRecordFrontpage.discharge_datetime).label("min_discharge"),
                func.max(MedicalRecordFrontpage.discharge_datetime).label("max_discharge"),
            ).first()

            return {
                "departments": [d for d in departments if _safe_text(d)],
                "doctors": [d for d in doctors if _safe_text(d)],
                "date_bounds": {
                    "admission": {
                        "min": _to_iso_date(getattr(date_bounds, "min_admission", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_admission", None)),
                    },
                    "discharge": {
                        "min": _to_iso_date(getattr(date_bounds, "min_discharge", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_discharge", None)),
                    },
                },
            }
        finally:
            session.close()

    def collect_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
            )
            rows = query.order_by(
                desc(MedicalRecordFrontpage.discharge_datetime),
                desc(MedicalRecordFrontpage.admission_datetime),
            ).all()
            return [self._serialize_record_row(row) for row in rows]
        finally:
            session.close()

    def count_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
    ) -> int:
        session = _session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
            )
            return int(query.with_entities(func.count(func.distinct(MedicalRecordFrontpage.visit_id))).scalar() or 0)
        finally:
            session.close()

    def hydrate_records_with_medical_text(
        self,
        records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        visit_ids = {
            _safe_text(item.get("visit_id") or item.get("record_id"))
            for item in records
            if _safe_text(item.get("visit_id") or item.get("record_id"))
        }
        if not visit_ids:
            return []

        session = _session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
            )
            rows = (
                session.query(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                    MedicalRecordFrontpage.name,
                    dept_expr.label("department"),
                    MedicalRecordFrontpage.attending_physician_sign,
                    MedicalRecordFrontpage.record_content,
                )
                .filter(MedicalRecordFrontpage.visit_id.in_(visit_ids))
                .all()
            )
            row_map: Dict[str, Any] = {str(row.visit_id): row for row in rows}
        finally:
            session.close()

        hydrated: List[Dict[str, Any]] = []
        for item in records:
            visit_id = _safe_text(item.get("visit_id") or item.get("record_id"))
            source = row_map.get(visit_id)
            medical_text = _safe_text(item.get("medical_text"))
            if not medical_text and source is not None:
                medical_text = _safe_text(source.record_content)
            hydrated_item = dict(item)
            hydrated_item.update(
                {
                    "institute_id": _safe_text(item.get("institute_id") or (source.institute_id if source else "")),
                    "patient_id": _safe_text(item.get("patient_id") or (source.patient_id if source else "")),
                    "record_id": _safe_text(item.get("record_id") or visit_id),
                    "visit_id": visit_id,
                    "patient_name": _safe_text(item.get("patient_name") or (source.name if source else "")),
                    "department": _safe_text(item.get("department") or (source.department if source else "")),
                    "doctor": _safe_text(item.get("doctor") or (source.attending_physician_sign if source else "")),
                    "medical_text": medical_text,
                }
            )
            hydrated.append(hydrated_item)
        return hydrated

    def save_last_test_summary(
        self,
        *,
        draft_id: str,
        created_by: str,
        summary: Dict[str, Any],
    ) -> None:
        session = _session()
        try:
            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(
                    last_test_summary=_safe_json_dumps(summary),
                    updated_at=_now_utc(),
                )
            )
            session.commit()
        finally:
            session.close()

    def create_batch_job(
        self,
        *,
        draft: Dict[str, Any],
        created_by: str,
        scope: str,
        filters: Dict[str, Any],
        record_ids: Sequence[str],
        total_records: int,
        draft_ids: Optional[Sequence[str]] = None,
        execution_mode: str = "single",
        run_mode: str = "serial",
        rule_count: int = 1,
        job_kind: str = "leaf",
        parent_job_id: Optional[str] = None,
        child_job_ids: Optional[Sequence[str]] = None,
        child_summary: Optional[Dict[str, Any]] = None,
        family_key: Optional[str] = None,
        family_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            now = _now_utc()
            job_id = str(uuid.uuid4())
            normalized_draft_ids = [item for item in _normalize_string_list(list(draft_ids or [])) if item]
            if not normalized_draft_ids:
                current_draft_id = _safe_text(draft.get("id"))
                if current_draft_id:
                    normalized_draft_ids = [current_draft_id]
            normalized_execution_mode = _normalize_execution_mode(execution_mode)
            if normalized_execution_mode == "single" and len(normalized_draft_ids) > 1:
                normalized_execution_mode = "multi"
            normalized_run_mode = _normalize_run_mode(run_mode)
            filters_payload = {
                **(filters or {}),
                "draft_ids": normalized_draft_ids,
                "execution_mode": normalized_execution_mode,
                "run_mode": normalized_run_mode,
            }
            summary_payload = {
                "rule_count": max(1, int(rule_count or len(normalized_draft_ids) or 1)),
                "progress": {
                    "step_key": "queued",
                    "rule_index": 0,
                    "rule_count": max(1, int(rule_count or len(normalized_draft_ids) or 1)),
                    "processed_records": 0,
                    "total_records": int(total_records or 0),
                },
                "updated_at": now.isoformat(),
            }
            row_payload = {
                "id": job_id,
                "draft_id": _safe_text(draft.get("id")),
                "rule_code": _safe_text(draft.get("rule_code")),
                "rule_name": _safe_text(draft.get("name"), "未命名规则"),
                "scene": _safe_text(draft.get("scene"), "final"),
                "scope": _normalize_scope(scope),
                "status": "queued",
                "filters_json": _safe_json_dumps(filters_payload),
                "record_ids_json": _safe_json_dumps(list(record_ids)),
                "summary_json": _safe_json_dumps(summary_payload),
                "items_json": None,
                "failed_records_json": None,
                "error_message": None,
                "created_by": created_by,
                "created_at": now,
                "started_at": None,
                "finished_at": None,
                "updated_at": now,
                "total_records": int(total_records or 0),
                "success_count": 0,
                "failed_count": 0,
                "issue_records": 0,
                "compliant_records": 0,
                "total_tokens": 0,
                "total_processing_time": 0.0,
                "job_kind": _safe_text(job_kind, "leaf") or "leaf",
                "parent_job_id": _safe_text(parent_job_id) or None,
                "child_job_ids_json": _safe_json_dumps(list(child_job_ids or [])),
                "child_summary_json": _safe_json_dumps(child_summary or {}),
                "family_key": _safe_text(family_key) or None,
                "family_name": _safe_text(family_name) or None,
            }
            session.execute(self._batch_job_table.insert().values(**row_payload))
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by) or _row_to_batch_job(row_payload)
        finally:
            session.close()

    def update_parent_child_jobs(
        self,
        *,
        parent_job_id: str,
        created_by: str,
        child_job_ids: Sequence[str],
        child_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(
                        self._batch_job_table.c.id == parent_job_id,
                        self._batch_job_table.c.created_by == created_by,
                    )
                )
                .values(
                    child_job_ids_json=_safe_json_dumps(list(child_job_ids or [])),
                    child_summary_json=_safe_json_dumps(child_summary or {}),
                    updated_at=now,
                )
            )
            session.commit()
            return self.get_batch_job(job_id=parent_job_id, created_by=created_by)
        finally:
            session.close()

    def get_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            return self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
        finally:
            session.close()

    def update_batch_job_review_report(
        self,
        *,
        job_id: str,
        created_by: str,
        review_report: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            next_summary = {
                **current_summary,
                "review_report": review_report,
                "reviewed_at": review_report.get("reviewed_at") or now.isoformat(),
                "updated_at": now.isoformat(),
            }
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by))
                .values(summary_json=_safe_json_dumps(next_summary), updated_at=now)
            )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return None
            return self._aggregate_parent_job(session, _row_to_batch_job(dict(row)))
        finally:
            session.close()

    def list_batch_jobs(
        self,
        *,
        created_by: str,
        draft_id: Optional[str] = None,
        status: Optional[str] = None,
        scope: Optional[str] = None,
        query: Optional[str] = None,
        executor_type: Optional[str] = None,
        cache_hit: Optional[bool] = None,
        created_start_date: Optional[str] = None,
        created_end_date: Optional[str] = None,
        include_children: bool = False,
        page: int = 1,
        page_size: int = DEFAULT_BATCH_JOB_PAGE_SIZE,
    ) -> WorkspaceBatchJobListResult:
        session = _session()
        try:
            clauses = [self._batch_job_table.c.created_by == created_by]
            if not include_children:
                clauses.append(
                    or_(
                        self._batch_job_table.c.parent_job_id.is_(None),
                        self._batch_job_table.c.parent_job_id == "",
                    )
                )
            if draft_id:
                clauses.append(self._batch_job_table.c.draft_id == draft_id)
            status_value = _safe_text(status).lower()
            if status_value:
                clauses.append(self._batch_job_table.c.status == status_value)
            scope_value = _safe_text(scope).lower()
            if scope_value:
                clauses.append(self._batch_job_table.c.scope == _normalize_scope(scope_value))
            query_value = _safe_text(query)
            if query_value:
                clauses.append(
                    or_(
                        self._batch_job_table.c.rule_code.ilike(f"%{query_value}%"),
                        self._batch_job_table.c.rule_name.ilike(f"%{query_value}%"),
                    )
                )
            start = _as_date(created_start_date)
            end = _as_date(created_end_date)
            if start:
                clauses.append(func.date(self._batch_job_table.c.created_at) >= start)
            if end:
                clauses.append(func.date(self._batch_job_table.c.created_at) <= end)
            where_clause = and_(*clauses)
            executor_value = _safe_text(executor_type).lower()
            enable_runtime_filter = executor_value in {"program", "llm"} or cache_hit is not None

            if not enable_runtime_filter:
                total = int(
                    session.execute(
                        select(func.count()).select_from(self._batch_job_table).where(where_clause)
                    ).scalar()
                    or 0
                )
                rows = (
                    session.execute(
                        select(self._batch_job_table)
                        .where(where_clause)
                        .order_by(desc(self._batch_job_table.c.created_at))
                        .offset(max(page - 1, 0) * page_size)
                        .limit(page_size)
                    )
                    .mappings()
                    .all()
                )
                items = [
                    self._aggregate_parent_job(
                        session,
                        _row_to_batch_job(dict(row), include_items=False),
                        include_items=False,
                    )
                    for row in rows
                ]
                return WorkspaceBatchJobListResult(items=items, total=total, page=page, page_size=page_size)

            rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(where_clause)
                    .order_by(desc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
            all_items = [
                self._aggregate_parent_job(
                    session,
                    _row_to_batch_job(dict(row), include_items=False),
                    include_items=False,
                )
                for row in rows
            ]

            filtered_items = all_items
            if executor_value in {"program", "llm"}:
                filtered_items = [
                    item
                    for item in filtered_items
                    if int(
                        (((item.get("summary") or {}).get("executor_breakdown") or {}).get(executor_value) or 0)
                    )
                    > 0
                ]
            if cache_hit is not None:
                expected = bool(cache_hit)
                filtered_items = [
                    item
                    for item in filtered_items
                    if (
                        (int((((item.get("summary") or {}).get("cache_breakdown") or {}).get("hit") or 0) or 0) > 0)
                        == expected
                    )
                ]

            total = len(filtered_items)
            offset = max(page - 1, 0) * page_size
            items = filtered_items[offset : offset + page_size]
            return WorkspaceBatchJobListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def cancel_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            if current.get("status") in {"completed", "failed", "canceled"}:
                return current
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            cancelled_progress = (
                current_summary.get("progress")
                if isinstance(current_summary.get("progress"), dict)
                else {}
            )
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
                .values(
                    status="canceled",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **cancelled_progress,
                                "step_key": "canceled",
                                "step_label": "已停止",
                            },
                            "user_cancelled": True,
                            "cancelled_by": created_by,
                            "cancelled_at": now.isoformat(),
                            "updated_at": now.isoformat(),
                        }
                    ),
                    error_message="user_cancelled: 任务已取消",
                    finished_at=now,
                    updated_at=now,
                )
            )
            if str(current.get("job_kind") or "").strip().lower() == "parent":
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                session.execute(
                    update(self._batch_job_table)
                    .where(
                        and_(
                            child_where,
                            self._batch_job_table.c.created_by == created_by,
                            self._batch_job_table.c.status.in_(["queued", "running"]),
                        )
                    )
                    .values(
                        status="canceled",
                        error_message="parent_cancelled: 总任务已取消",
                        finished_at=now,
                        updated_at=now,
                    )
                )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def retry_batch_job(self, *, job_id: str, created_by: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            rule_count = int(current.get("rule_count") or 1)
            total_records = int(current.get("total_records") or 0)
            now = _now_utc()
            reset_values = dict(
                status="queued",
                summary_json=_safe_json_dumps(
                    {
                        "rule_count": max(1, rule_count),
                        "progress": {
                            "step_key": "queued",
                            "rule_index": 0,
                            "rule_count": max(1, rule_count),
                            "processed_records": 0,
                            "total_records": total_records,
                        },
                        "updated_at": now.isoformat(),
                    }
                ),
                items_json=None,
                failed_records_json=None,
                error_message=None,
                started_at=None,
                finished_at=None,
                updated_at=now,
                success_count=0,
                failed_count=0,
                issue_records=0,
                compliant_records=0,
                total_tokens=0,
                total_processing_time=0.0,
            )
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
                .values(**reset_values)
            )
            if str(current.get("job_kind") or "").strip().lower() == "parent":
                child_ids = [
                    str(item or "").strip()
                    for item in list(current.get("child_job_ids") or [])
                    if str(item or "").strip()
                ]
                child_where = self._batch_job_table.c.parent_job_id == job_id
                if child_ids:
                    child_where = or_(child_where, self._batch_job_table.c.id.in_(child_ids))
                session.execute(
                    update(self._batch_job_table)
                    .where(
                        and_(
                            child_where,
                            self._batch_job_table.c.created_by == created_by,
                        )
                    )
                    .values(**reset_values)
                )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
        finally:
            session.close()

    def get_child_batch_jobs(self, *, parent_job_id: str, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        session = _session()
        try:
            clauses = [self._batch_job_table.c.parent_job_id == parent_job_id]
            if created_by:
                clauses.append(self._batch_job_table.c.created_by == created_by)
            rows = (
                session.execute(
                    select(self._batch_job_table)
                    .where(and_(*clauses))
                    .order_by(asc(self._batch_job_table.c.created_at))
                )
                .mappings()
                .all()
            )
            return [_row_to_batch_job(dict(row)) for row in rows]
        finally:
            session.close()

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return False
            current = _row_to_batch_job(dict(row))
            if current.get("status") in {"canceled", "completed", "failed"}:
                return False
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            progress_value = current_summary.get("progress")
            if not isinstance(progress_value, dict):
                progress_value = {}
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(self._batch_job_table.c.id == job_id)
                .values(
                    status="running",
                    started_at=now,
                    updated_at=now,
                    error_message=None,
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **progress_value,
                                "step_key": "prepare",
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def update_batch_job_progress(
        self,
        *,
        job_id: str,
        step_key: str,
        rule_index: int,
        rule_count: int,
        processed_records: int,
        total_records: int,
        summary_patch: Optional[Dict[str, Any]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        failed_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return None
            current = _row_to_batch_job(dict(row))
            if current.get("status") == "canceled":
                return current

            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            merged_summary = {**current_summary, **(summary_patch or {})}
            merged_summary["rule_count"] = max(1, int(merged_summary.get("rule_count") or rule_count or 1))
            merged_summary["progress"] = {
                "step_key": _safe_text(step_key) or "run",
                "rule_index": max(0, int(rule_index or 0)),
                "rule_count": max(1, int(rule_count or merged_summary.get("rule_count") or 1)),
                "processed_records": max(0, int(processed_records or 0)),
                "total_records": max(0, int(total_records or 0)),
            }
            now = _now_utc()
            merged_summary["updated_at"] = now.isoformat()

            values: Dict[str, Any] = {
                "summary_json": _safe_json_dumps(merged_summary),
                "updated_at": now,
                "total_records": int(merged_summary.get("total_records") or total_records or 0),
                "success_count": int(merged_summary.get("success_count") or 0),
                "failed_count": int(merged_summary.get("failed_count") or 0),
                "issue_records": int(merged_summary.get("issue_records") or 0),
                "compliant_records": int(merged_summary.get("compliant_records") or 0),
                "total_tokens": int(merged_summary.get("total_tokens") or 0),
                "total_processing_time": float(merged_summary.get("total_processing_time") or 0.0),
            }
            if items is not None:
                values["items_json"] = _safe_json_dumps(items)
            if failed_records is not None:
                values["failed_records_json"] = _safe_json_dumps(failed_records)

            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(**values)
            )
            session.commit()
            return self.get_batch_job_for_processing(job_id=job_id)
        finally:
            session.close()

    def complete_batch_job(
        self,
        *,
        job_id: str,
        summary: Dict[str, Any],
        items: List[Dict[str, Any]],
        failed_records: List[Dict[str, Any]],
    ) -> None:
        session = _session()
        try:
            now = _now_utc()
            merged_summary = {
                **(summary or {}),
                "progress": {
                    **(
                        summary.get("progress")
                        if isinstance(summary.get("progress"), dict)
                        else {}
                    ),
                    "step_key": "completed",
                    "processed_records": int((summary or {}).get("total_records") or 0),
                    "total_records": int((summary or {}).get("total_records") or 0),
                },
                "updated_at": now.isoformat(),
            }
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(
                    status="completed",
                    summary_json=_safe_json_dumps(merged_summary),
                    items_json=_safe_json_dumps(items),
                    failed_records_json=_safe_json_dumps(failed_records),
                    total_records=int(summary.get("total_records") or 0),
                    success_count=int(summary.get("success_count") or 0),
                    failed_count=int(summary.get("failed_count") or 0),
                    issue_records=int(summary.get("issue_records") or 0),
                    compliant_records=int(summary.get("compliant_records") or 0),
                    total_tokens=int(summary.get("total_tokens") or 0),
                    total_processing_time=float(summary.get("total_processing_time") or 0.0),
                    finished_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            if not row:
                return
            current_summary = _safe_json_loads(row.get("summary_json"), {})
            if not isinstance(current_summary, dict):
                current_summary = {}
            now = _now_utc()
            session.execute(
                update(self._batch_job_table)
                .where(and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.status != "canceled"))
                .values(
                    status="failed",
                    summary_json=_safe_json_dumps(
                        {
                            **current_summary,
                            "progress": {
                                **(
                                    current_summary.get("progress")
                                    if isinstance(current_summary.get("progress"), dict)
                                    else {}
                                ),
                                "step_key": "failed",
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                    error_message=_safe_text(error_message),
                    finished_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

    def export_batch_job_workbook(self, *, job: Dict[str, Any]) -> BytesIO:
        from openpyxl import Workbook

        output = BytesIO()
        workbook = Workbook()
        summary = job.get("summary") or {}
        items = job.get("items") or []
        failed_records = job.get("failed_records") or []
        status_breakdown = summary.get("status_breakdown") or {}
        rule_name_map: Dict[str, str] = {}
        for rr in summary.get("rule_results") or []:
            if not isinstance(rr, dict):
                continue
            rule_code = _safe_text(rr.get("rule_code"))
            rule_name = _safe_text(rr.get("rule_name"))
            if rule_code and rule_name:
                rule_name_map[rule_code] = rule_name

        issue_items: List[Dict[str, Any]] = []
        for item in items:
            status_key = _safe_text((item or {}).get("status")).lower()
            is_compliant = (item or {}).get("is_compliant")
            if status_key in {"non_compliant", "ai_suggested_non_compliant", "uncertain"} or is_compliant is False:
                issue_items.append(item or {})

        # 1) 管理摘要（面向行政管理）
        ws_summary = workbook.active
        ws_summary.title = "管理摘要"
        ws_summary.append(["报告项", "内容"])
        summary_rows = [
            ("任务编号", _safe_text(job.get("id"), "-")),
            ("任务名称", _safe_text(job.get("rule_name"), "终末病历批量质控任务")),
            ("规则集", _safe_text(summary.get("rule_set_name") or (job.get("filters") or {}).get("rule_set_name"), "手工选择规则")),
            ("执行策略", _safe_text(summary.get("quality_profile") or (job.get("filters") or {}).get("quality_profile"), "-")),
            ("分桶策略", _safe_text(summary.get("bucket_strategy") or (job.get("filters") or {}).get("bucket_strategy"), "-")),
            ("精审规则数", _to_int(summary.get("refined_rule_count"))),
            ("适用场景", _map_scene_label(job.get("scene"))),
            ("覆盖范围", _map_scope_label(job.get("scope"))),
            ("当前状态", _map_job_status_label(job.get("status"))),
            ("发起时间", str(job.get("created_at") or "-")),
            ("开始执行时间", str(job.get("started_at") or "-")),
            ("完成时间", str(job.get("finished_at") or "-")),
            ("筛选范围说明", _build_filter_text(job.get("filters") or {})),
            ("纳入病历数", _to_int(summary.get("total_records"), _to_int(job.get("total_records")))),
            ("完成病历数", _to_int(summary.get("success_count"), _to_int(job.get("success_count")))),
            ("执行失败病历数", _to_int(summary.get("failed_record_count"), _to_int(job.get("failed_count")))),
            ("发现问题病历数", _to_int(summary.get("issue_records"), _to_int(job.get("issue_records")))),
            ("AI判断病历数", _to_int(summary.get("uncertain_records"), _to_int(status_breakdown.get("uncertain")))),
            ("合规病历数", _to_int(summary.get("compliant_records"), _to_int(job.get("compliant_records")))),
            ("执行规则数", _to_int(summary.get("rule_count"), 1)),
        ]
        for label, value in summary_rows:
            ws_summary.append([label, value])
        ws_summary.column_dimensions["A"].width = 24
        ws_summary.column_dimensions["B"].width = 80

        # 2) 问题明细（业务重点）
        ws_items = workbook.create_sheet("问题明细")
        ws_items.append(
            [
                "病历号",
                "患者姓名",
                "科室",
                "质控点编码",
                "质控点名称",
                "文书域",
                "规则族",
                "判定结果",
                "问题结论",
                "整改建议",
                "证据摘要",
                "置信度",
                "是否精审",
            ]
        )
        for item in issue_items:
            ws_items.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("rule_code") or "",
                    item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                    item.get("document_type") or "",
                    item.get("rule_family") or "",
                    _map_item_status_label(item.get("status"), item.get("is_compliant")),
                    item.get("findings") or "",
                    item.get("suggestion") or "",
                    item.get("evidence") or "",
                    _to_float(item.get("confidence"), 0.0),
                    "是" if item.get("refined") is True else "否",
                ]
            )
        ws_items.freeze_panes = "A2"
        ws_items.column_dimensions["A"].width = 16
        ws_items.column_dimensions["B"].width = 14
        ws_items.column_dimensions["C"].width = 14
        ws_items.column_dimensions["D"].width = 12
        ws_items.column_dimensions["E"].width = 32
        ws_items.column_dimensions["F"].width = 16
        ws_items.column_dimensions["G"].width = 20
        ws_items.column_dimensions["H"].width = 10
        ws_items.column_dimensions["I"].width = 42
        ws_items.column_dimensions["J"].width = 38
        ws_items.column_dimensions["K"].width = 38
        ws_items.column_dimensions["L"].width = 10
        ws_items.column_dimensions["M"].width = 10

        # 3) 全部明细（含合规、AI判断、不合规）
        ws_all = workbook.create_sheet("全部明细")
        ws_all.append(
            [
                "病历号",
                "患者姓名",
                "科室",
                "质控点编码",
                "质控点名称",
                "文书域",
                "规则族",
                "判定结果",
                "是否合规",
                "问题结论",
                "整改建议",
                "证据摘要",
                "置信度",
                "是否精审",
            ]
        )
        for item in items:
            ws_all.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("rule_code") or "",
                    item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                    item.get("document_type") or "",
                    item.get("rule_family") or "",
                    _map_item_status_label(item.get("status"), item.get("is_compliant")),
                    "是" if item.get("is_compliant") is True else "否",
                    item.get("findings") or "",
                    item.get("suggestion") or "",
                    item.get("evidence") or "",
                    _to_float(item.get("confidence"), 0.0),
                    "是" if item.get("refined") is True else "否",
                ]
            )
        ws_all.freeze_panes = "A2"

        # 4) 失败明细
        ws_failed = workbook.create_sheet("失败明细")
        ws_failed.append(["病历号", "患者姓名", "科室", "失败原因"])
        for item in failed_records:
            ws_failed.append(
                [
                    item.get("record_id") or "",
                    item.get("patient_name") or "",
                    item.get("department") or "",
                    item.get("error") or "",
                ]
            )
        ws_failed.freeze_panes = "A2"
        ws_failed.column_dimensions["A"].width = 16
        ws_failed.column_dimensions["B"].width = 14
        ws_failed.column_dimensions["C"].width = 14
        ws_failed.column_dimensions["D"].width = 64

        # 5) 技术信息（默认不看，给研发定位问题）
        ws_tech = workbook.create_sheet("技术信息")
        ws_tech.append(["技术字段", "值"])
        performance_profile = _normalize_export_performance_profile(summary, job)
        tech_rows = [
            ("任务ID", _safe_text(job.get("id"), "-")),
            ("规则编码", _safe_text(job.get("rule_code"), "-")),
            ("规则集(raw)", _safe_text(summary.get("rule_set_key") or (job.get("filters") or {}).get("rule_set_key"), "-")),
            ("精审摘要(raw)", _safe_json_dumps(summary.get("refine_summary") or {})),
            ("场景(raw)", _safe_text(job.get("scene"), "-")),
            ("范围(raw)", _safe_text(job.get("scope"), "-")),
            ("状态(raw)", _safe_text(job.get("status"), "-")),
            ("总 token", performance_profile["tokens_total"]),
            ("输入 token", performance_profile["prompt_tokens"]),
            ("输出 token", performance_profile["completion_tokens"]),
            ("未归因 token", performance_profile["unattributed_tokens"]),
            ("token 拆分完整", "是" if performance_profile["token_breakdown_complete"] else "否"),
            ("总耗时(秒)", round(_to_float(summary.get("total_processing_time"), _to_float(job.get("total_processing_time"))), 4)),
            ("筛选条件(raw)", _safe_json_dumps(job.get("filters") or {})),
            ("summary(raw)", _safe_json_dumps(summary)),
        ]
        for label, value in tech_rows:
            ws_tech.append([label, value])
        ws_tech.column_dimensions["A"].width = 24
        ws_tech.column_dimensions["B"].width = 96

        workbook.save(output)
        output.seek(0)
        return output

    def export_batch_job_csv(self, *, job: Dict[str, Any]) -> StringIO:
        import csv

        output = StringIO()
        writer = csv.writer(output)
        summary = job.get("summary") or {}
        items = job.get("items") or []
        rule_name_map: Dict[str, str] = {}
        for rr in summary.get("rule_results") or []:
            if not isinstance(rr, dict):
                continue
            rule_code = _safe_text(rr.get("rule_code"))
            rule_name = _safe_text(rr.get("rule_name"))
            if rule_code and rule_name:
                rule_name_map[rule_code] = rule_name
        issue_items: List[Dict[str, Any]] = []
        for item in items:
            status_key = _safe_text((item or {}).get("status")).lower()
            is_compliant = (item or {}).get("is_compliant")
            if status_key in {"non_compliant", "ai_suggested_non_compliant", "uncertain"} or is_compliant is False:
                issue_items.append(item or {})

        writer.writerow(["管理摘要"])
        writer.writerow(["任务编号", _safe_text(job.get("id"), "-")])
        writer.writerow(["任务名称", _safe_text(job.get("rule_name"), "终末病历批量质控任务")])
        writer.writerow(["规则集", _safe_text(summary.get("rule_set_name") or (job.get("filters") or {}).get("rule_set_name"), "手工选择规则")])
        writer.writerow(["执行策略", _safe_text(summary.get("quality_profile") or (job.get("filters") or {}).get("quality_profile"), "-")])
        writer.writerow(["分桶策略", _safe_text(summary.get("bucket_strategy") or (job.get("filters") or {}).get("bucket_strategy"), "-")])
        writer.writerow(["精审规则数", _to_int(summary.get("refined_rule_count"))])
        writer.writerow(["适用场景", _map_scene_label(job.get("scene"))])
        writer.writerow(["覆盖范围", _map_scope_label(job.get("scope"))])
        writer.writerow(["当前状态", _map_job_status_label(job.get("status"))])
        writer.writerow(["纳入病历数", _to_int(summary.get("total_records"), _to_int(job.get("total_records")))])
        writer.writerow(["发现问题病历数", _to_int(summary.get("issue_records"), _to_int(job.get("issue_records")))])
        writer.writerow(["AI判断病历数", _to_int(summary.get("uncertain_records"))])
        writer.writerow(["合规病历数", _to_int(summary.get("compliant_records"), _to_int(job.get("compliant_records")))])
        writer.writerow(["执行规则数", _to_int(summary.get("rule_count"), 1)])
        writer.writerow([])
        writer.writerow(["问题明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "质控点编码", "质控点名称", "文书域", "规则族", "判定结果", "问题结论", "整改建议", "证据摘要", "置信度", "是否精审"])
        for item in issue_items:
            writer.writerow([
                item.get("record_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("rule_code") or "",
                item.get("rule_name") or rule_name_map.get(_safe_text(item.get("rule_code")), ""),
                item.get("document_type") or "",
                item.get("rule_family") or "",
                _map_item_status_label(item.get("status"), item.get("is_compliant")),
                item.get("findings") or "",
                item.get("suggestion") or "",
                item.get("evidence") or "",
                _to_float(item.get("confidence"), 0.0),
                "是" if item.get("refined") is True else "否",
            ])
        writer.writerow([])
        writer.writerow(["失败明细"])
        writer.writerow(["病历号", "患者姓名", "科室", "失败原因"])
        for item in job.get("failed_records") or []:
            writer.writerow([
                item.get("record_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("error") or "",
            ])
        output.seek(0)
        return output

    def export_batch_job_html(self, *, job: Dict[str, Any]) -> str:
        summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
        filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
        child_jobs = job.get("child_jobs") or job.get("children") or []
        export_jobs = [child for child in child_jobs if isinstance(child, dict)] or [job]

        all_items: List[Dict[str, Any]] = []
        failed_records: List[Dict[str, Any]] = []
        for source_job in export_jobs:
            for item in source_job.get("items") or []:
                if isinstance(item, dict):
                    all_items.append(item)
            for item in source_job.get("failed_records") or []:
                if isinstance(item, dict):
                    failed_records.append(item)

        status_counts: Dict[str, int] = {}
        for source in (
            summary.get("display_status_counts"),
            summary.get("status_breakdown"),
        ):
            if isinstance(source, dict):
                for key, value in source.items():
                    status_counts[_safe_text(key).lower()] = status_counts.get(_safe_text(key).lower(), 0) + _to_int(value)
        if not status_counts:
            for item in all_items:
                key = _export_item_status_key(item)
                status_counts[key] = status_counts.get(key, 0) + 1

        record_groups: Dict[str, Dict[str, Any]] = {}
        for item in all_items:
            record_id = _safe_text(item.get("record_id") or item.get("visit_id") or item.get("mr_no") or "未返回病历号")
            group = record_groups.setdefault(
                record_id,
                {
                    "record_id": record_id,
                    "patient_name": _safe_text(item.get("patient_name"), "-"),
                    "department": _safe_text(item.get("department"), "-"),
                    "items": [],
                    "status_counts": {},
                },
            )
            if group.get("patient_name") in {"", "-"} and _safe_text(item.get("patient_name")):
                group["patient_name"] = _safe_text(item.get("patient_name"))
            if group.get("department") in {"", "-"} and _safe_text(item.get("department")):
                group["department"] = _safe_text(item.get("department"))
            group["items"].append(item)
            status_key = _export_item_status_key(item)
            group["status_counts"][status_key] = group["status_counts"].get(status_key, 0) + 1

        status_order = [
            "non_compliant",
            "ai_suggested_non_compliant",
            "data_gap",
            "uncertain",
            "not_executed",
            "technical_error",
            "not_applicable",
            "ai_suggested_compliant",
            "compliant",
        ]
        status_cards = []
        for key in status_order:
            value = _to_int(status_counts.get(key))
            status_cards.append(
                f'<div class="metric metric-{_status_tone_class(key)}"><span>{_html_escape(_map_item_status_label(key, None))}</span><strong>{value}</strong></div>'
            )

        selected_rule_ids = (
            filters.get("selected_rule_ids")
            or filters.get("scoped_customer_rule_ids")
            or summary.get("selected_rule_ids")
            or summary.get("scoped_customer_rule_ids")
            or []
        )
        customer_rule_count = _to_int(
            job.get("customer_rule_count"),
            _to_int(summary.get("customer_rule_count"), _to_int(summary.get("rule_count"), _to_int(job.get("rule_count")))),
        )
        execution_rule_count = _to_int(
            job.get("execution_rule_count"),
            _to_int(summary.get("execution_rule_count"), _to_int(summary.get("rule_count"), _to_int(job.get("rule_count")))),
        )
        total_records = _to_int(summary.get("total_records"), _to_int(job.get("total_records"), len(record_groups)))
        rule_set_name = _safe_text(
            summary.get("rule_set_name") or filters.get("rule_set_name") or job.get("rule_set_name") or job.get("rule_name"),
            "质控任务",
        )
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        performance_profile = _normalize_export_performance_profile(summary, job)
        performance_block = (
            '<div class="performance-metrics">'
            f'<div class="performance-metric"><span>总 Token</span><strong>{_format_export_integer(performance_profile["tokens_total"])}</strong></div>'
            f'<div class="performance-metric"><span>输入 Token</span><strong>{_format_export_integer(performance_profile["prompt_tokens"])}</strong></div>'
            f'<div class="performance-metric"><span>输出 Token</span><strong>{_format_export_integer(performance_profile["completion_tokens"])}</strong></div>'
            f'<div class="performance-metric performance-metric-warn"><span>未归因 Token</span><strong>{_format_export_integer(performance_profile["unattributed_tokens"])}</strong></div>'
            f'<div class="performance-metric"><span>Token 拆分</span><strong>{"完整" if performance_profile["token_breakdown_complete"] else "有未归因"}</strong></div>'
            "</div>"
            '<p class="performance-note">未归因 Token 表示模型服务返回了总量，但未能拆分到输入或输出的部分；用于性能剖析和成本排查。</p>'
        )

        toc_rows = []
        record_sections = []
        for index, group in enumerate(record_groups.values(), start=1):
            anchor = f"record-{index}"
            issue_count = sum(
                _to_int(group["status_counts"].get(key))
                for key in (
                    "non_compliant",
                    "ai_suggested_non_compliant",
                    "data_gap",
                    "uncertain",
                    "not_executed",
                    "technical_error",
                )
            )
            toc_rows.append(
                "<tr>"
                f'<td><a href="#{anchor}">{_html_escape(group.get("record_id"))}</a></td>'
                f"<td>{_html_escape(group.get('patient_name'))}</td>"
                f"<td>{_html_escape(group.get('department'))}</td>"
                f"<td>{len(group.get('items') or [])}</td>"
                f"<td>{issue_count}</td>"
                "</tr>"
            )

            item_cards = []
            sorted_items = sorted(
                group.get("items") or [],
                key=lambda item: (
                    0
                    if _export_item_status_key(item)
                    in {
                        "non_compliant",
                        "ai_suggested_non_compliant",
                        "data_gap",
                        "uncertain",
                        "technical_error",
                        "not_executed",
                    }
                    else 1,
                    _safe_text(item.get("rule_code")),
                ),
            )
            for item in sorted_items:
                status_key = _export_item_status_key(item)
                status_label = _map_item_status_label(status_key, item.get("is_compliant"))
                conclusion = _sanitize_export_text(item.get("findings") or item.get("conclusion") or item.get("summary"), 520)
                suggestion = _sanitize_export_text(item.get("suggestion") or item.get("recommendation"), 360)
                evidence_part_rows = []
                for part in _parse_export_evidence_parts(item.get("evidence")):
                    evidence_part_rows.append(
                        '<div class="evidence-fact">'
                        f"<span>{_html_escape(part.get('label') or '-')}</span>"
                        f"<strong>{_html_escape(part.get('value') or '-')}</strong>"
                        "</div>"
                    )
                evidence_rows = []
                for evidence in _extract_structured_evidence(item):
                    evidence_rows.append(
                        "<div class=\"evidence-row\">"
                        f"<div><span>来源</span><strong>{_html_escape(evidence.get('source') or '-')}</strong></div>"
                        f"<div><span>字段</span><strong>{_html_escape(evidence.get('field') or '-')}</strong></div>"
                        f"<div class=\"evidence-quote\"><span>片段</span><strong>{_html_escape(evidence.get('quote') or '-')}</strong></div>"
                        f"<div><span>阈值</span><strong>{_html_escape(evidence.get('threshold') or '-')}</strong></div>"
                        f"<div><span>实际</span><strong>{_html_escape(evidence.get('actual') or '-')}</strong></div>"
                        f"<div><span>差值</span><strong>{_html_escape(evidence.get('delta') or '-')}</strong></div>"
                        "</div>"
                    )
                if not evidence_rows and not evidence_part_rows:
                    legacy_evidence = _sanitize_export_text(
                        item.get("evidence")
                        or item.get("evidence_text")
                        or item.get("evidence_summary")
                        or item.get("quote"),
                        520,
                    )
                    if legacy_evidence:
                        evidence_rows.append(f'<p class="legacy-evidence">{_html_escape(legacy_evidence)}</p>')
                    else:
                        evidence_rows.append('<p class="legacy-evidence muted">未返回可导出的证据摘要。</p>')
                missing_sources = item.get("missing_sources") or item.get("missing_fields") or item.get("data_gap")
                missing_text = ""
                if isinstance(missing_sources, list):
                    missing_text = "、".join(_safe_text(value) for value in missing_sources if _safe_text(value))
                elif missing_sources:
                    missing_text = _safe_text(missing_sources)
                missing_block = (
                    f'<div class="missing-block">缺失字段/来源：{_html_escape(_truncate_export_text(missing_text, 220))}</div>'
                    if missing_text
                    else ""
                )
                item_cards.append(
                    f'<article class="issue-card issue-{_status_tone_class(status_key)}">'
                    '<div class="issue-head">'
                    f"<h4>{_html_escape(item.get('rule_code'))} · {_html_escape(item.get('rule_name'))}</h4>"
                    f'<span class="status-pill status-{_status_tone_class(status_key)}">{_html_escape(status_label)}</span>'
                    "</div>"
                    '<div class="issue-meta">'
                    f"<span>{_html_escape(item.get('document_type') or '文书未标注')}</span>"
                    f"<span>{_html_escape(item.get('defect_level') or '缺陷等级未标注')}</span>"
                    f"<span>复核状态：{_html_escape(item.get('review_status') or '未处理')}</span>"
                    "</div>"
                    '<div class="issue-grid">'
                    f'<section><label>质控结论</label><p>{_html_escape(conclusion or "-")}</p></section>'
                    f'<section><label>关键证据</label>{"".join(evidence_part_rows)}{"".join(evidence_rows)}{missing_block}</section>'
                    f'<section><label>处理建议</label><p>{_html_escape(suggestion or "请结合病历原文确认。")}</p></section>'
                    "</div>"
                    "</article>"
                )

            record_sections.append(
                f'<section id="{anchor}" class="record-section">'
                '<div class="record-head">'
                "<div>"
                f"<h3>{_html_escape(group.get('record_id'))} · {_html_escape(group.get('patient_name'))}</h3>"
                f"<p>{_html_escape(group.get('department'))} · {len(group.get('items') or [])} 条质控结果</p>"
                "</div>"
                f'<span class="record-issue-count">需关注 {issue_count}</span>'
                "</div>"
                f"{''.join(item_cards)}"
                "</section>"
            )

        if not record_sections:
            record_sections.append('<section class="empty-state">当前任务暂无可导出的质控明细。</section>')

        review_block = ""
        review_report = summary.get("review_report") if isinstance(summary.get("review_report"), dict) else {}
        if review_report:
            review_summary = review_report.get("summary") if isinstance(review_report.get("summary"), dict) else {}
            review_findings = review_report.get("findings") if isinstance(review_report.get("findings"), list) else []
            review_rows = []
            for finding in review_findings[:12]:
                if not isinstance(finding, dict):
                    continue
                review_rows.append(
                    "<tr>"
                    f"<td>{_html_escape(finding.get('severity') or '-')}</td>"
                    f"<td>{_html_escape(finding.get('record_id') or '-')}</td>"
                    f"<td>{_html_escape(finding.get('rule_id') or '-')}</td>"
                    f"<td>{_html_escape(_sanitize_export_text(finding.get('customer_message') or finding.get('reason'), 220))}</td>"
                    f"<td>{_html_escape(_map_item_status_label(finding.get('suggested_status'), None))}</td>"
                    "</tr>"
                )
            review_table_html = (
                '<table class="review-table"><thead><tr><th>级别</th><th>病历</th><th>质控点</th><th>复核建议</th><th>建议口径</th></tr></thead>'
                f"<tbody>{''.join(review_rows)}</tbody></table>"
                if review_rows
                else '<p class="muted">已完成复核，暂无高风险复核建议。</p>'
            )
            review_block = (
                '<section class="panel review-section"><h2>结果复核建议</h2>'
                '<div class="review-summary">'
                f"<span>建议总数 <strong>{_to_int(review_summary.get('total_findings'))}</strong></span>"
                f"<span>P0 <strong>{_to_int(review_summary.get('p0'))}</strong></span>"
                f"<span>P1 <strong>{_to_int(review_summary.get('p1'))}</strong></span>"
                f"<span>P2 <strong>{_to_int(review_summary.get('p2'))}</strong></span>"
                "</div>"
                f"{review_table_html}</section>"
            )

        failed_block = ""
        if failed_records:
            failed_rows = []
            for item in failed_records:
                failed_rows.append(
                    "<tr>"
                    f"<td>{_html_escape(item.get('record_id') or item.get('visit_id'))}</td>"
                    f"<td>{_html_escape(item.get('patient_name'))}</td>"
                    f"<td>{_html_escape(item.get('department'))}</td>"
                    f"<td>{_html_escape(_sanitize_export_text(item.get('error'), 240))}</td>"
                    "</tr>"
                )
            failed_block = (
                '<section class="failed-section"><h2>执行失败病历</h2>'
                '<table><thead><tr><th>病历号</th><th>患者</th><th>科室</th><th>失败原因</th></tr></thead>'
                f"<tbody>{''.join(failed_rows)}</tbody></table></section>"
            )

        html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_html_escape(rule_set_name)} - 质控明细</title>
  <style>
    body {{ margin: 0; background: #f5f5f7; color: #1d1d1f; font-family: "Source Han Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", system-ui, sans-serif; }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    .hero, .panel, .record-section, .failed-section {{ border: 1px solid rgba(0,0,0,.08); border-radius: 18px; background: rgba(255,255,255,.94); box-shadow: 0 10px 30px rgba(15,23,42,.06); }}
    .hero {{ padding: 24px; }}
    .eyebrow {{ margin: 0 0 8px; color: rgba(29,29,31,.58); font-size: 13px; }}
    h1 {{ margin: 0; font-size: 26px; line-height: 34px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    h3 {{ margin: 0; font-size: 17px; }}
    h4 {{ margin: 0; font-size: 15px; line-height: 22px; }}
    .hero-meta, .issue-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; color: rgba(29,29,31,.62); font-size: 13px; }}
    .hero-meta span, .issue-meta span {{ border-radius: 999px; background: #f3f6fb; padding: 5px 10px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }}
    .metric {{ border-radius: 14px; border: 1px solid rgba(0,0,0,.08); padding: 12px; background: #fff; }}
    .metric span {{ display: block; color: rgba(29,29,31,.56); font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    .metric-danger strong {{ color: #dc2626; }} .metric-warning strong {{ color: #b45309; }} .metric-success strong {{ color: #0066cc; }}
    .performance-metrics {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .performance-metric {{ border-radius: 14px; border: 1px solid #dbe5f3; background: #f8fafc; padding: 10px 12px; }}
    .performance-metric span {{ display: block; color: rgba(29,29,31,.56); font-size: 12px; }}
    .performance-metric strong {{ display: block; margin-top: 5px; font-size: 18px; }}
    .performance-metric-warn strong {{ color: #b45309; }}
    .performance-note {{ margin: 8px 0 0; color: rgba(29,29,31,.56); font-size: 12px; line-height: 20px; }}
    .panel, .failed-section {{ margin-top: 18px; padding: 18px; }}
    .review-section {{ border-color: #bfdbfe; background: #f8fbff; }}
    .review-summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .review-summary span {{ border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 6px 10px; font-size: 13px; }}
    .review-summary strong {{ margin-left: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid rgba(0,0,0,.08); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: rgba(29,29,31,.58); font-weight: 700; }}
    a {{ color: #0066cc; text-decoration: none; }}
    .record-section {{ margin-top: 18px; padding: 18px; scroll-margin-top: 18px; }}
    .record-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 14px; }}
    .record-head p {{ margin: 6px 0 0; color: rgba(29,29,31,.58); }}
    .record-issue-count {{ border-radius: 999px; background: #fff7ed; color: #b45309; padding: 6px 10px; font-size: 13px; font-weight: 700; }}
    .issue-card {{ border: 1px solid rgba(0,0,0,.08); border-left-width: 5px; border-radius: 14px; background: #fff; padding: 14px; margin-top: 12px; }}
    .issue-danger {{ border-left-color: #ef4444; }} .issue-warning {{ border-left-color: #f59e0b; }} .issue-success {{ border-left-color: #0066cc; }} .issue-neutral, .issue-muted {{ border-left-color: #94a3b8; }}
    .issue-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .status-pill {{ flex: 0 0 auto; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }}
    .status-danger {{ background: #fef2f2; color: #dc2626; }} .status-warning {{ background: #fff7ed; color: #b45309; }} .status-success {{ background: #eaf2ff; color: #0066cc; }} .status-neutral, .status-muted {{ background: #f1f5f9; color: #475569; }}
    .issue-grid {{ display: grid; grid-template-columns: 1fr 1.25fr 1fr; gap: 12px; margin-top: 12px; }}
    section label {{ display: block; margin-bottom: 6px; color: rgba(29,29,31,.58); font-size: 12px; font-weight: 700; }}
    section p {{ margin: 0; font-size: 13px; line-height: 21px; }}
    .evidence-fact {{ display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 10px; align-items: center; border: 1px solid #d7e7ff; border-radius: 10px; background: #f3f8ff; padding: 8px 10px; font-size: 12px; }}
    .evidence-fact + .evidence-fact, .evidence-fact + .evidence-row, .evidence-fact + .legacy-evidence {{ margin-top: 8px; }}
    .evidence-fact span {{ color: #375f8f; font-weight: 600; }}
    .evidence-fact strong {{ color: #111827; font-weight: 700; line-height: 18px; }}
    .evidence-row {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; border-radius: 12px; background: #f8fafc; padding: 10px; font-size: 12px; }}
    .evidence-row + .evidence-row {{ margin-top: 8px; }}
    .evidence-row span {{ display: block; color: rgba(29,29,31,.52); }}
    .evidence-row strong {{ display: block; margin-top: 3px; font-weight: 600; line-height: 18px; }}
    .evidence-quote {{ grid-column: span 3; }}
    .legacy-evidence {{ border-radius: 12px; background: #f8fafc; padding: 10px; }}
    .missing-block {{ margin-top: 8px; border-radius: 10px; background: #fff7ed; color: #9a3412; padding: 8px 10px; font-size: 12px; }}
    .notice {{ margin-top: 18px; color: rgba(29,29,31,.58); font-size: 12px; line-height: 20px; }}
    .empty-state {{ margin-top: 18px; border-radius: 16px; background: #fff; padding: 28px; color: rgba(29,29,31,.58); text-align: center; }}
    @media print {{ .page {{ padding: 0; }} .hero, .panel, .record-section, .failed-section {{ box-shadow: none; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">质控明细导出 · 生成时间 {generated_at}</p>
      <h1>{_html_escape(rule_set_name)}</h1>
      <div class="hero-meta">
        <span>任务ID：{_html_escape(job.get("id"))}</span>
        <span>状态：{_html_escape(_map_job_status_label(job.get("status")))}</span>
        <span>病历数：{total_records}</span>
        <span>客户质控点数：{customer_rule_count}</span>
        <span>底层执行规则数：{execution_rule_count}</span>
        <span>选择质控点：{_html_escape(_format_rule_code_list(selected_rule_ids))}</span>
      </div>
      <div class="metrics">{"".join(status_cards)}</div>
      {performance_block}
      <p class="notice">本文件仅用于质控明细查看和质控确认，不作为病历归档、医保结算、绩效扣分或正式质控结论依据。文件不包含完整病历全文、模型原始输出或向量数据。</p>
    </section>

    <section class="panel">
      <h2>病历目录</h2>
      <table>
        <thead><tr><th>病历号</th><th>患者</th><th>科室</th><th>结果数</th><th>需关注</th></tr></thead>
        <tbody>{"".join(toc_rows) or '<tr><td colspan="5">暂无病历结果</td></tr>'}</tbody>
      </table>
    </section>

    {review_block}
    {"".join(record_sections)}
    {failed_block}
  </main>
</body>
</html>
"""
        return "\ufeff" + html_text

    def publish_draft(self, *, draft_id: str, created_by: str) -> Dict[str, Any]:
        session = _session()
        try:
            stmt = select(self._draft_table).where(
                and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by)
            )
            row = session.execute(stmt).mappings().first()
            if not row:
                raise ValueError("草稿不存在或无权限")

            draft = _row_to_draft(dict(row))
            last_test_summary = draft.get("last_test_summary") or {}
            success_count = 0
            if isinstance(last_test_summary, dict):
                success_count = int(last_test_summary.get("success_count") or 0)
            if success_count <= 0:
                raise ValueError("请至少完成一次成功测试后再发布")

            qc_rules_table = _qc_rules_table()
            now = _now_utc()
            draft_check_logic = dict(draft.get("check_logic") or {})
            aligned_document_type, aligned_applicable_documents, aligned_check_logic = align_document_domain_fields(
                document_type=draft.get("document_type"),
                applicable_documents=draft.get("applicable_documents"),
                check_logic=draft_check_logic,
            )
            check_logic = {
                **aligned_check_logic,
                "source": "custom_rule_workspace",
                "workspace_draft_id": draft["id"],
                "applicable_documents": aligned_applicable_documents,
                "generation_mode": draft.get("generation_mode") or "fallback_template",
                "examples": draft.get("examples") or [],
                "last_test_summary": draft.get("last_test_summary"),
                "document_type": aligned_document_type,
                "scene": draft.get("scene"),
            }
            values: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "rule_code": draft["rule_code"],
                "name": draft["name"],
                "description": draft["description"],
                "category": "consistency",
                "severity": draft.get("severity") or _map_defect_level_to_severity(draft.get("defect_level")),
                "rule_type": "semantic",
                "scope": "global",
                "status": "published",
                "version": "1.0",
                "priority": 0,
                "is_active": True,
                "prompt_template": draft.get("prompt_template"),
                "check_logic": check_logic,
                "applicable_documents": aligned_applicable_documents,
                "metadata": {
                    "source": "custom_rule_workspace",
                    "workspace_draft_id": draft["id"],
                },
                "created_by": created_by,
                "updated_by": created_by,
                "created_at": now,
                "updated_at": now,
            }

            existing_stmt = select(qc_rules_table).where(qc_rules_table.c.rule_code == draft["rule_code"]).limit(1)
            existing = session.execute(existing_stmt).mappings().first()
            filtered_values = {
                key: _value_for_column(qc_rules_table.c[key], value)
                for key, value in values.items()
                if key in qc_rules_table.c
            }
            if existing:
                session.execute(
                    update(qc_rules_table)
                    .where(qc_rules_table.c.rule_code == draft["rule_code"])
                    .values(**{k: v for k, v in filtered_values.items() if k != "id"})
                )
                published_rule_id = _safe_text(existing.get("id")) or draft["rule_code"]
            else:
                session.execute(qc_rules_table.insert().values(**filtered_values))
                inserted = session.execute(existing_stmt).mappings().first()
                published_rule_id = _safe_text((inserted or {}).get("id")) or draft["rule_code"]

            session.execute(
                update(self._draft_table)
                .where(and_(self._draft_table.c.id == draft_id, self._draft_table.c.created_by == created_by))
                .values(
                    status="published",
                    published_rule_id=published_rule_id,
                    updated_at=now,
                )
            )
            session.commit()
            return {
                "draft_id": draft_id,
                "rule_code": draft["rule_code"],
                "published_rule_id": published_rule_id,
                "status": "published",
            }
        finally:
            session.close()


# SQLAlchemy is imported lazily here to avoid polluting top-level namespace usage above.
