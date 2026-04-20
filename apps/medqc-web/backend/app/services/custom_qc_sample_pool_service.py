from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence
import psycopg2
import psycopg2.extras

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, desc, func, or_, select, update
from sqlalchemy.orm import Session

from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import MedicalRecordFrontpage
from .bundles.assembly import refresh_scene_bundles_for_rows
from .etl_sync import (
    expand_table_groups,
    fetch_remote_rows_by_visit_keys,
    get_remote_db_url,
    list_sync_tables,
    load_db_config,
    upsert_to_local,
)
from .visit_index_service import ingest_sync_rows


def _now_utc() -> datetime:
    return datetime.utcnow()


def _schema() -> Optional[str]:
    return "qc" if DB_SCHEMA_MODE == "split" else None


def _session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    return SessionLocal()


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
        return json.loads(text)
    except Exception:
        return default


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            serial = float(value)
            if serial > 20000:
                excel_epoch = datetime(1899, 12, 30)
                return (excel_epoch + timedelta(days=serial)).date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(normalized).date()
    except Exception:
        return None


def _to_iso_date(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _normalize_issue_text(text: Any) -> str:
    normalized = _safe_text(text)
    normalized = normalized.replace("\u3000", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_manual_issue_text(text: Any) -> Dict[str, Any]:
    normalized = _normalize_issue_text(text)
    lowered = normalized.lower()

    # 纯程序/时效问题先挡掉，避免误入首批内涵样本。
    if _contains_any(
        normalized,
        (
            "未及时",
            "超时",
            "24小时",
            "48小时",
            "72小时",
            "三天未",
            "两天未",
            "每日未",
            "签名",
            "签字",
            "无术前小结",
            "无术前讨论",
            "无手术记录",
            "无会诊记录",
            "无主刀医生",
            "未进行术前讨论",
        ),
    ):
        return {
            "coverage_type": "programmatic",
            "issue_category": "timeliness_or_presence",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "纯时效/缺文书/签名类问题，首批不纳入 LLM 内涵验证",
        }

    if _contains_any(normalized, ("鉴别诊断", "诊断依据", "诊疗计划", "病例特点", "首次病程")):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "first_course_reasoning",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-023", "SC-024", "SC-025", "SC-026", "SC-027"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "现病史",
            "主诉",
            "既往史",
            "前后矛盾",
            "体格检查",
            "专科检查",
            "院外检查",
            "阴性症状",
            "入院记录",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "admission_consistency",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "病情变化",
            "分析",
            "处理意见",
            "异常检查",
            "辅助检查",
            "未记录",
            "病程记录",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-032", "SC-033", "SC-036"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(normalized, ("会诊", "遵会诊意见", "执行", "落实")):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_execution",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-070"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(normalized, ("查房", "上级医师", "主任查房", "副主任查房")):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "senior_round_content",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-050"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if "llm" in lowered:
        # 避免纯字符串测试时被误判成 unsupported
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "manual_override",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "",
        }

    return {
        "coverage_type": "unsupported",
        "issue_category": "unclassified",
        "expected_scene": "running",
        "candidate_rule_ids": [],
        "include_in_batch_1": False,
        "exclude_reason": "当前未归入首批内涵问题分类，请人工确认",
    }


def load_manual_case_rows_from_excel(*, file_path: str, sheet_name: str = "Sheet2") -> List[Dict[str, Any]]:
    import pandas as pd

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    if df.empty or len(df.index) < 3:
        return []
    header_row = [str(item).strip() for item in df.iloc[1].tolist()]
    data = df.iloc[2:].copy()
    data.columns = header_row
    rows: List[Dict[str, Any]] = []
    for index, raw in enumerate(data.to_dict(orient="records"), start=3):
        mr_no = _safe_text(raw.get("住院号"))
        issue_text = _safe_text(raw.get("存在问题"))
        patient_name = _safe_text(raw.get("患者姓名"))
        if not mr_no and not issue_text and not patient_name:
            continue
        rows.append(
            {
                "row_no": index,
                "department": _safe_text(raw.get("科室")),
                "patient_name": patient_name,
                "mr_no": mr_no,
                "manual_issue_text": issue_text,
                "doctor_name": _safe_text(raw.get("责任医生")),
                "qc_date": raw.get("质控日期"),
                "qc_user": _safe_text(raw.get("质控人员")),
            }
        )
    return rows


def _score_candidate(
    *,
    row: Any,
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(getattr(row, "name", ""))
    row_department = _safe_text(getattr(row, "admission_dept_name", "") or getattr(row, "discharge_dept_name", ""))
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    admission_dt = getattr(row, "admission_datetime", None)
    discharge_dt = getattr(row, "discharge_datetime", None)
    if qc_date_value:
        admission_date = _parse_date(admission_dt)
        discharge_date = _parse_date(discharge_dt)
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


def _score_remote_candidate(
    *,
    candidate: Dict[str, Any],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(candidate.get("name"))
    row_department = _safe_text(
        candidate.get("admission_dept_name") or candidate.get("discharge_dept_name") or candidate.get("dept_name")
    )
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    if qc_date_value:
        admission_date = _parse_date(candidate.get("admission_datetime"))
        discharge_date = _parse_date(candidate.get("discharge_datetime"))
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


@lru_cache(maxsize=1)
def _sample_pools_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pools",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("source_sheet", sa.String(100), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False, default="running"),
        sa.Column("description", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_items", sa.Integer, nullable=False, default=0),
        sa.Column("llm_intrinsic_items", sa.Integer, nullable=False, default=0),
        sa.Column("programmatic_items", sa.Integer, nullable=False, default=0),
        sa.Column("unsupported_items", sa.Integer, nullable=False, default=0),
        sa.Column("matched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ambiguous_items", sa.Integer, nullable=False, default=0),
        sa.Column("unmatched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ready_items", sa.Integer, nullable=False, default=0),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_job_status", sa.String(20)),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _sample_pool_items_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pool_items",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False, index=True),
        sa.Column("row_no", sa.Integer, nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("patient_name", sa.String(100)),
        sa.Column("mr_no", sa.String(100), index=True),
        sa.Column("manual_issue_text", sa.Text, nullable=False),
        sa.Column("normalized_issue_text", sa.Text, nullable=False),
        sa.Column("doctor_name", sa.String(100)),
        sa.Column("qc_date", sa.Date),
        sa.Column("qc_user", sa.String(100)),
        sa.Column("coverage_type", sa.String(30), nullable=False, default="unsupported"),
        sa.Column("issue_category", sa.String(100), nullable=False, default="unclassified"),
        sa.Column("expected_scene", sa.String(20), nullable=False, default="running"),
        sa.Column("candidate_rule_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("include_in_batch_1", sa.Boolean, nullable=False, default=False),
        sa.Column("exclude_reason", sa.Text),
        sa.Column("matched_institute_id", sa.String(100)),
        sa.Column("matched_patient_id", sa.String(100)),
        sa.Column("matched_visit_id", sa.String(100), index=True),
        sa.Column("match_status", sa.String(20), nullable=False, default="unmatched"),
        sa.Column("sync_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("bundle_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_match_status", sa.String(20)),
        sa.Column("raw_payload_json", sa.Text, nullable=False, default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@dataclass
class SamplePoolListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CustomQCSamplePoolService:
    def __init__(self) -> None:
        self._pool_table = _sample_pools_table()
        self._item_table = _sample_pool_items_table()

    @staticmethod
    def resolve_sync_table_names(group_ids: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
        default_group_ids = [
            "core_8",
            "document_extended",
            "diagnosis_extended",
            "orders_prescriptions",
            "exam_lab_pathology",
        ]
        selected_groups = [str(item).strip() for item in (group_ids or default_group_ids) if str(item).strip()]
        table_names, missing = expand_table_groups(selected_groups)
        if not table_names:
            raise ValueError("未解析到可执行同步表，请检查 table_groups 配置")
        return {
            "group_ids": selected_groups,
            "table_names": table_names,
            "missing_group_ids": missing,
        }

    def _row_to_pool(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": _safe_text(row.get("id")),
            "name": _safe_text(row.get("name")),
            "source_file": _safe_text(row.get("source_file")),
            "source_sheet": _safe_text(row.get("source_sheet")),
            "scene": _safe_text(row.get("scene"), "running"),
            "description": _safe_text(row.get("description")),
            "created_by": _safe_text(row.get("created_by")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "total_items": int(row.get("total_items") or 0),
            "llm_intrinsic_items": int(row.get("llm_intrinsic_items") or 0),
            "programmatic_items": int(row.get("programmatic_items") or 0),
            "unsupported_items": int(row.get("unsupported_items") or 0),
            "matched_items": int(row.get("matched_items") or 0),
            "ambiguous_items": int(row.get("ambiguous_items") or 0),
            "unmatched_items": int(row.get("unmatched_items") or 0),
            "ready_items": int(row.get("ready_items") or 0),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "latest_job_status": _safe_text(row.get("latest_job_status")),
        }

    def _row_to_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": _safe_text(row.get("id")),
            "pool_id": _safe_text(row.get("pool_id")),
            "row_no": int(row.get("row_no") or 0),
            "department": _safe_text(row.get("department")),
            "patient_name": _safe_text(row.get("patient_name")),
            "mr_no": _safe_text(row.get("mr_no")),
            "manual_issue_text": _safe_text(row.get("manual_issue_text")),
            "normalized_issue_text": _safe_text(row.get("normalized_issue_text")),
            "doctor_name": _safe_text(row.get("doctor_name")),
            "qc_date": _to_iso_date(row.get("qc_date")),
            "qc_user": _safe_text(row.get("qc_user")),
            "coverage_type": _safe_text(row.get("coverage_type"), "unsupported"),
            "issue_category": _safe_text(row.get("issue_category"), "unclassified"),
            "expected_scene": _safe_text(row.get("expected_scene"), "running"),
            "candidate_rule_ids": _safe_json_loads(row.get("candidate_rule_ids_json"), []),
            "include_in_batch_1": bool(row.get("include_in_batch_1")),
            "exclude_reason": _safe_text(row.get("exclude_reason")),
            "matched_institute_id": _safe_text(row.get("matched_institute_id")),
            "matched_patient_id": _safe_text(row.get("matched_patient_id")),
            "matched_visit_id": _safe_text(row.get("matched_visit_id")),
            "match_status": _safe_text(row.get("match_status"), "unmatched"),
            "sync_status": _safe_text(row.get("sync_status"), "pending"),
            "bundle_status": _safe_text(row.get("bundle_status"), "pending"),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "latest_match_status": _safe_text(row.get("latest_match_status")),
            "raw_payload": _safe_json_loads(row.get("raw_payload_json"), {}),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _update_pool_counters(self, session: Session, pool_id: str) -> None:
        item_table = self._item_table
        stats_stmt = select(
            func.count().label("total_items"),
            func.sum(sa.case((item_table.c.coverage_type == "llm_intrinsic", 1), else_=0)).label("llm_intrinsic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "programmatic", 1), else_=0)).label("programmatic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "unsupported", 1), else_=0)).label("unsupported_items"),
            func.sum(sa.case((item_table.c.match_status == "matched", 1), else_=0)).label("matched_items"),
            func.sum(sa.case((item_table.c.match_status == "ambiguous", 1), else_=0)).label("ambiguous_items"),
            func.sum(sa.case((item_table.c.match_status == "unmatched", 1), else_=0)).label("unmatched_items"),
            func.sum(sa.case((item_table.c.bundle_status == "ready", 1), else_=0)).label("ready_items"),
        ).where(item_table.c.pool_id == pool_id)
        stats = session.execute(stats_stmt).mappings().first() or {}
        session.execute(
            update(self._pool_table)
            .where(self._pool_table.c.id == pool_id)
            .values(
                updated_at=_now_utc(),
                total_items=int(stats.get("total_items") or 0),
                llm_intrinsic_items=int(stats.get("llm_intrinsic_items") or 0),
                programmatic_items=int(stats.get("programmatic_items") or 0),
                unsupported_items=int(stats.get("unsupported_items") or 0),
                matched_items=int(stats.get("matched_items") or 0),
                ambiguous_items=int(stats.get("ambiguous_items") or 0),
                unmatched_items=int(stats.get("unmatched_items") or 0),
                ready_items=int(stats.get("ready_items") or 0),
            )
        )

    def list_pools(self, *, page: int = 1, page_size: int = 20, query: Optional[str] = None) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = []
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._pool_table.c.name.ilike(keyword),
                        self._pool_table.c.source_file.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses) if clauses else None
            total_stmt = select(func.count()).select_from(self._pool_table)
            if where_clause is not None:
                total_stmt = total_stmt.where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = select(self._pool_table)
            if where_clause is not None:
                stmt = stmt.where(where_clause)
            stmt = (
                stmt.order_by(desc(self._pool_table.c.updated_at), desc(self._pool_table.c.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            return SamplePoolListResult(
                items=[self._row_to_pool(dict(row)) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def get_pool(self, *, pool_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._pool_table).where(self._pool_table.c.id == pool_id)
            row = session.execute(stmt).mappings().first()
            return self._row_to_pool(dict(row)) if row else None
        finally:
            session.close()

    def create_pool_with_items(
        self,
        *,
        name: str,
        source_file: str,
        source_sheet: str,
        created_by: str,
        rows: Iterable[Dict[str, Any]],
        description: Optional[str] = None,
        scene: str = "running",
    ) -> Dict[str, Any]:
        session = _session()
        try:
            pool_id = str(uuid.uuid4())
            now = _now_utc()
            session.execute(
                self._pool_table.insert().values(
                    id=pool_id,
                    name=_safe_text(name, "客户样本池"),
                    source_file=_safe_text(source_file),
                    source_sheet=_safe_text(source_sheet, "Sheet2"),
                    scene=_safe_text(scene, "running"),
                    description=_safe_text(description),
                    created_by=_safe_text(created_by, "system"),
                    created_at=now,
                    updated_at=now,
                    total_items=0,
                    llm_intrinsic_items=0,
                    programmatic_items=0,
                    unsupported_items=0,
                    matched_items=0,
                    ambiguous_items=0,
                    unmatched_items=0,
                    ready_items=0,
                )
            )
            payload_rows = []
            for index, raw in enumerate(rows, start=1):
                classification = classify_manual_issue_text(raw.get("manual_issue_text"))
                payload_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "pool_id": pool_id,
                        "row_no": int(raw.get("row_no") or index),
                        "department": _safe_text(raw.get("department")),
                        "patient_name": _safe_text(raw.get("patient_name")),
                        "mr_no": _safe_text(raw.get("mr_no")),
                        "manual_issue_text": _safe_text(raw.get("manual_issue_text")),
                        "normalized_issue_text": _normalize_issue_text(raw.get("manual_issue_text")),
                        "doctor_name": _safe_text(raw.get("doctor_name")),
                        "qc_date": _parse_date(raw.get("qc_date")),
                        "qc_user": _safe_text(raw.get("qc_user")),
                        "coverage_type": classification["coverage_type"],
                        "issue_category": classification["issue_category"],
                        "expected_scene": classification["expected_scene"],
                        "candidate_rule_ids_json": _safe_json_dumps(classification["candidate_rule_ids"]),
                        "include_in_batch_1": bool(classification["include_in_batch_1"]),
                        "exclude_reason": _safe_text(classification["exclude_reason"]),
                        "matched_institute_id": "",
                        "matched_patient_id": "",
                        "matched_visit_id": "",
                        "match_status": "unmatched",
                        "sync_status": "pending",
                        "bundle_status": "pending",
                        "latest_job_id": "",
                        "latest_match_status": "",
                        "raw_payload_json": _safe_json_dumps(raw),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            if payload_rows:
                session.execute(self._item_table.insert(), payload_rows)
            self._update_pool_counters(session, pool_id)
            session.commit()
            return self.get_pool(pool_id=pool_id) or {"id": pool_id}
        finally:
            session.close()

    def list_pool_items(
        self,
        *,
        pool_id: str,
        coverage_type: Optional[str] = None,
        match_status: Optional[str] = None,
        include_in_batch_1: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if coverage_type:
                clauses.append(self._item_table.c.coverage_type == coverage_type)
            if match_status:
                clauses.append(self._item_table.c.match_status == match_status)
            if include_in_batch_1 is not None:
                clauses.append(self._item_table.c.include_in_batch_1.is_(include_in_batch_1))
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._item_table.c.patient_name.ilike(keyword),
                        self._item_table.c.mr_no.ilike(keyword),
                        self._item_table.c.manual_issue_text.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses)
            total_stmt = select(func.count()).select_from(self._item_table).where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = (
                select(self._item_table)
                .where(where_clause)
                .order_by(self._item_table.c.row_no.asc())
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            return SamplePoolListResult(
                items=[self._row_to_item(dict(row)) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def _check_running_bundle_status(self, *, institute_id: str, patient_id: str, visit_id: str) -> str:
        if engine is None:
            return "pending"
        sql = sa.text(
            """
            SELECT 1
            FROM public.running_record_bundle
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sql,
                    {
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": visit_id,
                    },
                ).first()
            return "ready" if row else "missing"
        except Exception:
            return "pending"

    def match_pool_items(self, *, pool_id: str) -> Dict[str, Any]:
        session = _session()
        try:
            stmt = (
                select(self._item_table)
                .where(self._item_table.c.pool_id == pool_id)
                .order_by(self._item_table.c.row_no.asc())
            )
            rows = session.execute(stmt).mappings().all()
            matched = 0
            ambiguous = 0
            unmatched = 0
            for row in rows:
                mr_no = _safe_text(row.get("mr_no"))
                patient_name = _safe_text(row.get("patient_name"))
                department = _safe_text(row.get("department"))
                qc_date_value = _parse_date(row.get("qc_date"))
                match_status = "unmatched"
                institute_id = ""
                patient_id = ""
                visit_id = ""
                sync_status = "missing"
                bundle_status = "pending"
                if mr_no:
                    candidates = (
                        session.query(MedicalRecordFrontpage)
                        .filter(
                            or_(
                                MedicalRecordFrontpage.mr_no == mr_no,
                                MedicalRecordFrontpage.inpat_no == mr_no,
                                MedicalRecordFrontpage.visit_id == mr_no,
                            )
                        )
                        .all()
                    )
                    if len(candidates) == 1:
                        candidate = candidates[0]
                        match_status = "matched"
                    elif len(candidates) > 1:
                        scored = sorted(
                            (
                                (
                                    _score_candidate(
                                        row=item,
                                        patient_name=patient_name,
                                        department=department,
                                        qc_date_value=qc_date_value,
                                    ),
                                    item,
                                )
                                for item in candidates
                            ),
                            key=lambda item: item[0],
                            reverse=True,
                        )
                        top_score = scored[0][0]
                        if top_score > 0 and (len(scored) == 1 or top_score > scored[1][0]):
                            candidate = scored[0][1]
                            match_status = "matched"
                        else:
                            candidate = None
                            match_status = "ambiguous"
                    else:
                        candidate = None
                    if candidate is not None:
                        institute_id = _safe_text(candidate.institute_id)
                        patient_id = _safe_text(candidate.patient_id)
                        visit_id = _safe_text(candidate.visit_id)
                        sync_status = "synced"
                        bundle_status = self._check_running_bundle_status(
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                        )
                if match_status == "matched":
                    matched += 1
                elif match_status == "ambiguous":
                    ambiguous += 1
                else:
                    unmatched += 1
                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row["id"])
                    .values(
                        matched_institute_id=institute_id,
                        matched_patient_id=patient_id,
                        matched_visit_id=visit_id,
                        match_status=match_status,
                        sync_status=sync_status,
                        bundle_status=bundle_status,
                        updated_at=_now_utc(),
                    )
                )
            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def get_runnable_items(
        self,
        *,
        pool_id: str,
        coverage_type: str = "llm_intrinsic",
        include_in_batch_1: bool = True,
        item_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            stmt = (
                select(self._item_table)
                .where(
                    and_(
                        self._item_table.c.pool_id == pool_id,
                        self._item_table.c.coverage_type == coverage_type,
                        self._item_table.c.match_status == "matched",
                        self._item_table.c.sync_status == "synced",
                    )
                )
                .order_by(self._item_table.c.row_no.asc())
            )
            if include_in_batch_1:
                stmt = stmt.where(self._item_table.c.include_in_batch_1.is_(True))
            if item_ids:
                normalized_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
                if normalized_ids:
                    stmt = stmt.where(self._item_table.c.id.in_(normalized_ids))
            rows = session.execute(stmt).mappings().all()
            return [self._row_to_item(dict(row)) for row in rows]
        finally:
            session.close()

    def _list_sync_candidate_items(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if only_intrinsic:
                clauses.append(self._item_table.c.coverage_type == "llm_intrinsic")
            if include_in_batch_1:
                clauses.append(self._item_table.c.include_in_batch_1.is_(True))
            stmt = select(self._item_table).where(and_(*clauses)).order_by(self._item_table.c.row_no.asc())
            rows = session.execute(stmt).mappings().all()
            return [self._row_to_item(dict(row)) for row in rows]
        finally:
            session.close()

    def _resolve_remote_visit_keys(self, *, items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        remote_url = get_remote_db_url()
        if not remote_url:
            raise RuntimeError("远端 PG 未配置，无法执行样本定向同步")
        cfg = load_db_config()
        remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")

        mr_nos = sorted({str(item.get("mr_no") or "").strip() for item in items if str(item.get("mr_no") or "").strip()})
        if not mr_nos:
            return {
                "matched": 0,
                "ambiguous": 0,
                "unmatched": 0,
                "visit_keys": [],
            }

        lookup_map: Dict[str, List[Dict[str, Any]]] = {}
        conn = psycopg2.connect(remote_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            chunk_size = 200
            for start in range(0, len(mr_nos), chunk_size):
                chunk = mr_nos[start : start + chunk_size]
                placeholders = ", ".join(["%s"] * len(chunk))
                sql = f"""
                    SELECT
                        institute_id::text AS institute_id,
                        patient_id::text AS patient_id,
                        visit_id::text AS visit_id,
                        COALESCE(inpat_no::text, '') AS inpat_no,
                        COALESCE(mr_no::text, '') AS mr_no,
                        COALESCE(name::text, '') AS name,
                        COALESCE(admission_dept_name::text, '') AS admission_dept_name,
                        COALESCE(discharge_dept_name::text, '') AS discharge_dept_name,
                        admission_datetime,
                        discharge_datetime
                    FROM {schema_ident}.mr
                    WHERE COALESCE(mr_no::text, '') IN ({placeholders})
                       OR COALESCE(inpat_no::text, '') IN ({placeholders})
                       OR COALESCE(visit_id::text, '') IN ({placeholders})
                """
                params = chunk + chunk + chunk
                cursor.execute(sql, params)
                for row in cursor.fetchall() or []:
                    candidate = dict(row)
                    for key in (candidate.get("mr_no"), candidate.get("inpat_no"), candidate.get("visit_id")):
                        lookup_key = str(key or "").strip()
                        if not lookup_key:
                            continue
                        lookup_map.setdefault(lookup_key, []).append(candidate)
        finally:
            cursor.close()
            conn.close()

        visit_key_set: set[tuple[str, str]] = set()
        matched = 0
        ambiguous = 0
        unmatched = 0
        for item in items:
            mr_no = str(item.get("mr_no") or "").strip()
            candidates = lookup_map.get(mr_no, [])
            patient_name = _safe_text(item.get("patient_name"))
            department = _safe_text(item.get("department"))
            qc_date_value = _parse_date(item.get("qc_date"))
            chosen: Optional[Dict[str, Any]]
            if len(candidates) == 1:
                chosen = candidates[0]
            elif len(candidates) > 1:
                scored = sorted(
                    (
                        (
                            _score_remote_candidate(
                                candidate=candidate,
                                patient_name=patient_name,
                                department=department,
                                qc_date_value=qc_date_value,
                            ),
                            candidate,
                        )
                        for candidate in candidates
                    ),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                top_score = scored[0][0]
                chosen = scored[0][1] if top_score > 0 and (len(scored) == 1 or top_score > scored[1][0]) else None
            else:
                chosen = None

            if chosen is None:
                if candidates:
                    ambiguous += 1
                else:
                    unmatched += 1
                continue

            patient_id = _safe_text(chosen.get("patient_id"))
            visit_id = _safe_text(chosen.get("visit_id"))
            if not patient_id or not visit_id:
                unmatched += 1
                continue
            matched += 1
            visit_key_set.add((patient_id, visit_id))

        return {
            "matched": matched,
            "ambiguous": ambiguous,
            "unmatched": unmatched,
            "visit_keys": sorted(visit_key_set),
        }

    def sync_pool_records(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
        table_groups: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        items = self._list_sync_candidate_items(
            pool_id=pool_id,
            only_intrinsic=only_intrinsic,
            include_in_batch_1=include_in_batch_1,
        )
        if not items:
            raise ValueError("当前样本池没有可同步的样本")

        sync_plan = self.resolve_sync_table_names(group_ids=table_groups)
        resolved = self._resolve_remote_visit_keys(items=items)
        visit_keys: List[tuple[str, str]] = resolved["visit_keys"]
        if not visit_keys:
            return {
                "pool_id": pool_id,
                "matched": resolved["matched"],
                "ambiguous": resolved["ambiguous"],
                "unmatched": resolved["unmatched"],
                "eligible_visits": 0,
                "synced_tables": [],
                "total_rows_pulled": 0,
                "total_rows_upserted": 0,
                "sync_group_ids": sync_plan["group_ids"],
                "missing_group_ids": sync_plan["missing_group_ids"],
                "pool": self.get_pool(pool_id=pool_id),
            }

        table_map = {str(item.get("name") or "").strip(): item for item in list_sync_tables()}
        remote_url = get_remote_db_url()
        cfg = load_db_config()
        remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
        anchor_tables = {"mr", "admission_record"}
        results: List[Dict[str, Any]] = []
        total_rows_pulled = 0
        total_rows_upserted = 0

        for table_name in sync_plan["table_names"]:
            table_config = table_map.get(table_name)
            if not table_config:
                continue
            source_table = str(table_config.get("source_table") or table_name)
            rows = fetch_remote_rows_by_visit_keys(
                remote_url=remote_url,
                remote_schema=remote_schema,
                source_table=source_table,
                visit_keys=visit_keys,
            )
            upserted = upsert_to_local(
                table_name=table_name,
                records=rows,
                primary_keys=[str(key) for key in (table_config.get("key_fields") or []) if str(key).strip()],
            )
            total_rows_pulled += len(rows)
            total_rows_upserted += upserted

            if table_name in anchor_tables and rows:
                ingest_sync_rows(
                    table_name=table_name,
                    rows=rows,
                    policy_version="sample_pool_sync",
                    sync_scene="running",
                    allow_frontpage_only=False,
                    latest_mirror_success_time=datetime.now(),
                    mirror_delay_base_minutes=30,
                    sync_interval_minutes=30,
                )
                refresh_scene_bundles_for_rows(
                    scene="running",
                    rows=rows,
                    policy_version="sample_pool_sync",
                )

            results.append(
                {
                    "table_name": table_name,
                    "source_table": source_table,
                    "rows_pulled": len(rows),
                    "rows_upserted": upserted,
                }
            )

        match_result = self.match_pool_items(pool_id=pool_id)
        return {
            "pool_id": pool_id,
            "matched": resolved["matched"],
            "ambiguous": resolved["ambiguous"],
            "unmatched": resolved["unmatched"],
            "eligible_visits": len(visit_keys),
            "synced_tables": results,
            "total_rows_pulled": total_rows_pulled,
            "total_rows_upserted": total_rows_upserted,
            "sync_group_ids": sync_plan["group_ids"],
            "missing_group_ids": sync_plan["missing_group_ids"],
            "pool": match_result.get("pool") or self.get_pool(pool_id=pool_id),
            "post_match": match_result,
        }

    def update_pool_latest_job(self, *, pool_id: str, job_id: str, job_status: str = "queued") -> None:
        session = _session()
        try:
            session.execute(
                update(self._pool_table)
                .where(self._pool_table.c.id == pool_id)
                .values(
                    latest_job_id=_safe_text(job_id),
                    latest_job_status=_safe_text(job_status),
                    updated_at=_now_utc(),
                )
            )
            session.commit()
        finally:
            session.close()
