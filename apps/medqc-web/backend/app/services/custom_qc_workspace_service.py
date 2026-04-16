from __future__ import annotations

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
    update,
)
from sqlalchemy.orm import Session

from .document_domain_alignment import (
    align_document_domain_fields,
    normalize_document_label,
)
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import MedicalRecordFrontpage


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
        schema=schema,
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


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


def _row_to_batch_job(row: Dict[str, Any]) -> Dict[str, Any]:
    filters = _safe_json_loads(row.get("filters_json"), {})
    record_ids = _safe_json_loads(row.get("record_ids_json"), [])
    summary = _safe_json_loads(row.get("summary_json"), None)
    items = _safe_json_loads(row.get("items_json"), [])
    failed_records = _safe_json_loads(row.get("failed_records_json"), [])
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
            MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
        )
        query = session.query(MedicalRecordFrontpage)

        if scope_value == "final":
            query = query.filter(MedicalRecordFrontpage.discharge_datetime.is_not(None))
        elif scope_value == "running":
            query = query.filter(MedicalRecordFrontpage.discharge_datetime.is_(None))

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
            MedicalRecordFrontpage.admission_datetime
            if date_field_value == "admission"
            else MedicalRecordFrontpage.discharge_datetime
        )
        if start:
            query = query.filter(func.date(date_col) >= start)
        if end:
            query = query.filter(func.date(date_col) <= end)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        item_scope = "final" if row.discharge_datetime else "running"
        item_department = _safe_text(row.discharge_dept_name or row.admission_dept_name)
        return {
            "record_id": _safe_text(row.visit_id),
            "visit_id": _safe_text(row.visit_id),
            "patient_name": _safe_text(row.name),
            "mr_no": _safe_text(row.mr_no),
            "inpat_no": _safe_text(row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(row.attending_physician_sign),
            "admission_date": _to_iso_date(row.admission_datetime),
            "discharge_date": _to_iso_date(row.discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text_length": len(_safe_text(row.record_content)),
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
            MedicalRecordFrontpage.discharge_dept_name, MedicalRecordFrontpage.admission_dept_name
        )
        query = session.query(MedicalRecordFrontpage)

        if scope_value == "final":
            query = query.filter(MedicalRecordFrontpage.discharge_datetime.is_not(None))
        elif scope_value == "running":
            query = query.filter(MedicalRecordFrontpage.discharge_datetime.is_(None))

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
            MedicalRecordFrontpage.admission_datetime
            if date_field_value == "admission"
            else MedicalRecordFrontpage.discharge_datetime
        )
        if start:
            query = query.filter(func.date(date_col) >= start)
        if end:
            query = query.filter(func.date(date_col) <= end)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        item_scope = "final" if row.discharge_datetime else "running"
        item_department = _safe_text(row.discharge_dept_name or row.admission_dept_name)
        return {
            "record_id": _safe_text(row.visit_id),
            "visit_id": _safe_text(row.visit_id),
            "patient_name": _safe_text(row.name),
            "mr_no": _safe_text(row.mr_no),
            "inpat_no": _safe_text(row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(row.attending_physician_sign),
            "admission_date": _to_iso_date(row.admission_datetime),
            "discharge_date": _to_iso_date(row.discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
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
            hydrated.append(
                {
                    "record_id": _safe_text(item.get("record_id") or visit_id),
                    "visit_id": visit_id,
                    "patient_name": _safe_text(item.get("patient_name") or (source.name if source else "")),
                    "department": _safe_text(item.get("department") or (source.department if source else "")),
                    "doctor": _safe_text(item.get("doctor") or (source.attending_physician_sign if source else "")),
                    "medical_text": medical_text,
                }
            )
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
            }
            session.execute(self._batch_job_table.insert().values(**row_payload))
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by) or _row_to_batch_job(row_payload)
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
            return _row_to_batch_job(dict(row)) if row else None
        finally:
            session.close()

    def get_batch_job_for_processing(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            row = session.execute(
                select(self._batch_job_table).where(self._batch_job_table.c.id == job_id)
            ).mappings().first()
            return _row_to_batch_job(dict(row)) if row else None
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
        page: int = 1,
        page_size: int = DEFAULT_BATCH_JOB_PAGE_SIZE,
    ) -> WorkspaceBatchJobListResult:
        session = _session()
        try:
            clauses = [self._batch_job_table.c.created_by == created_by]
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
                items = [_row_to_batch_job(dict(row)) for row in rows]
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
            all_items = [_row_to_batch_job(dict(row)) for row in rows]

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
                                **(
                                    current_summary.get("progress")
                                    if isinstance(current_summary.get("progress"), dict)
                                    else {}
                                ),
                                "step_key": "canceled",
                            },
                            "updated_at": now.isoformat(),
                        }
                    ),
                    error_message="任务已取消",
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
            session.execute(
                update(self._batch_job_table)
                .where(
                    and_(self._batch_job_table.c.id == job_id, self._batch_job_table.c.created_by == created_by)
                )
                .values(
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
            )
            session.commit()
            return self.get_batch_job(job_id=job_id, created_by=created_by)
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
        ws_summary = workbook.active
        ws_summary.title = "汇总"
        ws_summary.append(["任务ID", job.get("id")])
        ws_summary.append(["规则编码", job.get("rule_code")])
        ws_summary.append(["规则名称", job.get("rule_name")])
        ws_summary.append(["场景", job.get("scene")])
        ws_summary.append(["范围", job.get("scope")])
        ws_summary.append(["状态", job.get("status")])
        ws_summary.append(["创建时间", str(job.get("created_at") or "")])
        ws_summary.append(["开始时间", str(job.get("started_at") or "")])
        ws_summary.append(["结束时间", str(job.get("finished_at") or "")])
        ws_summary.append(["筛选条件", _safe_json_dumps(job.get("filters") or {})])
        summary = job.get("summary") or {}
        for label, key in [
            ("总病历数", "total_records"),
            ("成功数", "success_count"),
            ("失败数", "failed_count"),
            ("命中数", "issue_records"),
            ("合规数", "compliant_records"),
            ("总 token", "total_tokens"),
            ("总耗时", "total_processing_time"),
        ]:
            ws_summary.append([label, summary.get(key) or job.get(key) or 0])

        ws_items = workbook.create_sheet("命中明细")
        ws_items.append(["病历ID", "visit", "患者", "科室", "状态", "是否合规", "Findings", "Evidence", "Suggestion", "Confidence"])
        for item in job.get("items") or []:
            ws_items.append([
                item.get("record_id") or "",
                item.get("visit_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("status") or "",
                "是" if item.get("is_compliant") else "否",
                item.get("findings") or "",
                item.get("evidence") or "",
                item.get("suggestion") or "",
                item.get("confidence") or 0,
            ])

        ws_failed = workbook.create_sheet("失败明细")
        ws_failed.append(["病历ID", "visit", "患者", "科室", "失败原因"])
        for item in job.get("failed_records") or []:
            ws_failed.append([
                item.get("record_id") or "",
                item.get("visit_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("error") or "",
            ])

        workbook.save(output)
        output.seek(0)
        return output

    def export_batch_job_csv(self, *, job: Dict[str, Any]) -> StringIO:
        import csv

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["任务ID", job.get("id")])
        writer.writerow(["规则编码", job.get("rule_code")])
        writer.writerow(["规则名称", job.get("rule_name")])
        writer.writerow(["场景", job.get("scene")])
        writer.writerow(["范围", job.get("scope")])
        writer.writerow([])
        writer.writerow(["命中明细"])
        writer.writerow(["病历ID", "visit", "患者", "科室", "状态", "是否合规", "Findings", "Evidence", "Suggestion", "Confidence"])
        for item in job.get("items") or []:
            writer.writerow([
                item.get("record_id") or "",
                item.get("visit_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("status") or "",
                "是" if item.get("is_compliant") else "否",
                item.get("findings") or "",
                item.get("evidence") or "",
                item.get("suggestion") or "",
                item.get("confidence") or 0,
            ])
        writer.writerow([])
        writer.writerow(["失败明细"])
        writer.writerow(["病历ID", "visit", "患者", "科室", "失败原因"])
        for item in job.get("failed_records") or []:
            writer.writerow([
                item.get("record_id") or "",
                item.get("visit_id") or "",
                item.get("patient_name") or "",
                item.get("department") or "",
                item.get("error") or "",
            ])
        output.seek(0)
        return output

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
