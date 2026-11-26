"""首页质控 V2：从 CDM 只读加载一份正式首页的原始行。

只用可移植 SQL（不依赖 PostgreSQL 专有函数）。split 模式下表名显式带 cdm schema，
不依赖 search_path 顺序：未配置 DB_SEARCH_PATH 时默认 public 在前，public 下的旧 mr 表会遮住 cdm.mr。
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError

from ..case_identity import CaseRef


@dataclass(frozen=True)
class FrontpageRef:
    institute_id: str
    patient_id: str
    visit_id: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> FrontpageRef:
        return cls(
            str(record.get("institute_id") or ""),
            str(record.get("patient_id") or ""),
            str(record.get("visit_id") or record.get("record_id") or ""),
        )

    def as_case_ref(self) -> CaseRef:
        return CaseRef(self.institute_id, self.patient_id, self.visit_id)

    def legacy_key(self) -> str:
        return f"{self.institute_id}|{self.patient_id}|{self.visit_id}"

    def as_key(self) -> str:
        legacy_key = self.legacy_key()
        if legacy_key.count("|") == 2:
            return legacy_key
        # 旧键至少含两个 |，无 | 的新键不会与任何旧键冲突。
        digest = hashlib.sha256(self.as_case_ref().as_key().encode("utf-8")).hexdigest()
        return f"frontpage-ref-v2:{digest}"


@dataclass
class RawFrontpage:
    ref: FrontpageRef
    mr: Dict[str, Any]
    # 首页诊断：优先 mr_diagnosis（病案首页诊断），没有出院诊断时退回 diagnosis 表
    diagnosis_rows: List[Dict[str, Any]]
    diagnosis_source: str
    surgery_rows: List[Dict[str, Any]]
    cost_row: Optional[Dict[str, Any]]
    notes: List[str] = field(default_factory=list)


def default_cdm_schema() -> Optional[str]:
    from app.database import clinical_connection
    from app.database.connection import DB_SCHEMA_MODE

    if clinical_connection.configured():
        return "cdm"
    return "cdm" if str(DB_SCHEMA_MODE or "").strip().lower() == "split" else None


def _table(name: str, schema: Optional[str]) -> str:
    return f'"{schema}"."{name}"' if schema else f'"{name}"'


_WHERE = "institute_id = :institute_id AND patient_id = :patient_id AND visit_id = :visit_id"


def _rows(session: Any, sql: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def _is_missing_or_unreadable_table(exc: Exception) -> bool:
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    if pgcode is not None:
        return str(pgcode) in {"42P01", "42501"}
    if orig is not None and type(orig).__name__ in {"UndefinedTable", "InsufficientPrivilege"}:
        return True
    msg = str(orig or exc).lower()
    if "no such table" in msg:
        return True
    if "relation " in msg and "does not exist" in msg:
        return True
    if "permission denied for " in msg:
        return True
    return False


def _optional_rows(
    session: Any,
    table_name: str,
    schema: Optional[str],
    params: Dict[str, str],
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """使用 SAVEPOINT 查询可选表，捕获缺表/无权限并仅回滚子事务，绝不污染外层事务。"""
    sql = f"SELECT * FROM {_table(table_name, schema)} WHERE {_WHERE}"
    begin_nested = getattr(session, "begin_nested", None)
    try:
        if callable(begin_nested):
            with begin_nested():
                return _rows(session, sql, params), None
        return _rows(session, sql, params), None
    except (ProgrammingError, OperationalError, DBAPIError) as exc:
        if _is_missing_or_unreadable_table(exc):
            orig = getattr(exc, "orig", None)
            pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
            if str(pgcode or "") == "42501" or "permission denied" in str(orig or exc).lower():
                return [], "permission_denied"
            return [], "missing_table"
        raise


def _not_deleted(row: Dict[str, Any]) -> bool:
    return str(row.get("is_deleted") or "0").strip() != "1"


def is_discharge_diagnosis_type(diagnosis_type: object) -> bool:
    value = str(diagnosis_type or "")
    if "出院" in value:
        return True
    # 部分来源只写“主要诊断/其他诊断”，没有“出院”字样
    return value.strip() in {"主要诊断", "其他诊断"}


_DEFAULT = object()


def load_frontpage_raw(session: Any, ref: FrontpageRef, schema: Any = _DEFAULT) -> Optional[RawFrontpage]:
    """schema 不传时按 clinical_connection / DB_SCHEMA_MODE 推断；传 None 表示不带 schema（SQLite 测试）。"""
    schema = default_cdm_schema() if schema is _DEFAULT else schema
    params = {"institute_id": ref.institute_id, "patient_id": ref.patient_id, "visit_id": ref.visit_id}
    mr_rows = _rows(session, f"SELECT * FROM {_table('mr', schema)} WHERE {_WHERE}", params)
    if not mr_rows:
        return None
    notes: List[str] = []
    if len(mr_rows) > 1:
        notes.append(f"同一就诊存在 {len(mr_rows)} 份首页，取第一份")

    mr_diag_raw, mr_diag_unavailable = _optional_rows(session, "mr_diagnosis", schema, params)
    diagnosis_rows = [row for row in mr_diag_raw if _not_deleted(row)]
    diagnosis_source = "mr_diagnosis"
    if mr_diag_unavailable:
        fallback_raw, diag_unavailable = _optional_rows(session, "diagnosis", schema, params)
        diagnosis_rows = [row for row in fallback_raw if _not_deleted(row)]
        diagnosis_source = "diagnosis"
        if diag_unavailable:
            notes.append("病案首页诊断表（mr_diagnosis）与诊断表（diagnosis）均不可用，已跳过诊断读取")
        else:
            notes.append("病案首页诊断表（mr_diagnosis）不可用，已回退诊断表（diagnosis）")
    elif not any(is_discharge_diagnosis_type(row.get("diagnosis_type")) for row in diagnosis_rows):
        fallback_raw, diag_unavailable = _optional_rows(session, "diagnosis", schema, params)
        if diag_unavailable:
            notes.append("诊断表（diagnosis）不可用，无法补充出院诊断")
        else:
            fallback = [row for row in fallback_raw if _not_deleted(row)]
            if any(is_discharge_diagnosis_type(row.get("diagnosis_type")) for row in fallback):
                # 门诊、病理诊断仍以 mr_diagnosis 为准，只替换出院诊断
                diagnosis_rows = [
                    row for row in diagnosis_rows if not is_discharge_diagnosis_type(row.get("diagnosis_type"))
                ] + [row for row in fallback if is_discharge_diagnosis_type(row.get("diagnosis_type"))]
                diagnosis_source = "diagnosis"
                notes.append("出院诊断取自诊断表（病案首页诊断表无出院诊断）")

    surgery_rows, surgery_unavailable = _optional_rows(session, "mr_surgery", schema, params)
    if surgery_unavailable:
        notes.append("病案首页手术表（mr_surgery）不可用，已跳过手术明细读取")
    cost_rows, cost_unavailable = _optional_rows(session, "mr_cost", schema, params)
    if cost_unavailable:
        notes.append("病案首页费用表（mr_cost）不可用，已跳过费用明细读取")
    return RawFrontpage(
        ref=ref,
        mr=mr_rows[0],
        diagnosis_rows=diagnosis_rows,
        diagnosis_source=diagnosis_source,
        surgery_rows=surgery_rows,
        cost_row=cost_rows[0] if cost_rows else None,
        notes=notes,
    )
