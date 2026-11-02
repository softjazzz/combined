"""首页质控 V2：从 CDM 只读加载一份正式首页的原始行。

只用可移植 SQL（不依赖 PostgreSQL 专有函数）。split 模式下表名显式带 cdm schema，
不依赖 search_path 顺序：未配置 DB_SEARCH_PATH 时默认 public 在前，public 下的旧 mr 表会遮住 cdm.mr。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text


@dataclass(frozen=True)
class FrontpageRef:
    institute_id: str
    patient_id: str
    visit_id: str

    def as_key(self) -> str:
        return f"{self.institute_id}|{self.patient_id}|{self.visit_id}"


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
    from app.database.connection import DB_SCHEMA_MODE

    return "cdm" if str(DB_SCHEMA_MODE or "").strip().lower() == "split" else None


def _table(name: str, schema: Optional[str]) -> str:
    return f'"{schema}"."{name}"' if schema else f'"{name}"'


_WHERE = "institute_id = :institute_id AND patient_id = :patient_id AND visit_id = :visit_id"


def _rows(session: Any, sql: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


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
    """schema 不传时按 DB_SCHEMA_MODE 推断；传 None 表示不带 schema（SQLite 测试）。"""
    schema = default_cdm_schema() if schema is _DEFAULT else schema
    params = {"institute_id": ref.institute_id, "patient_id": ref.patient_id, "visit_id": ref.visit_id}
    mr_rows = _rows(session, f"SELECT * FROM {_table('mr', schema)} WHERE {_WHERE}", params)
    if not mr_rows:
        return None
    notes: List[str] = []
    if len(mr_rows) > 1:
        notes.append(f"同一就诊存在 {len(mr_rows)} 份首页，取第一份")

    diagnosis_rows = [row for row in _rows(session, f"SELECT * FROM {_table('mr_diagnosis', schema)} WHERE {_WHERE}", params) if _not_deleted(row)]
    diagnosis_source = "mr_diagnosis"
    if not any(is_discharge_diagnosis_type(row.get("diagnosis_type")) for row in diagnosis_rows):
        fallback = [row for row in _rows(session, f"SELECT * FROM {_table('diagnosis', schema)} WHERE {_WHERE}", params) if _not_deleted(row)]
        if any(is_discharge_diagnosis_type(row.get("diagnosis_type")) for row in fallback):
            # 门诊、病理诊断仍以 mr_diagnosis 为准，只替换出院诊断
            diagnosis_rows = [
                row for row in diagnosis_rows if not is_discharge_diagnosis_type(row.get("diagnosis_type"))
            ] + [row for row in fallback if is_discharge_diagnosis_type(row.get("diagnosis_type"))]
            diagnosis_source = "diagnosis"
            notes.append("出院诊断取自诊断表（病案首页诊断表无出院诊断）")

    surgery_rows = _rows(session, f"SELECT * FROM {_table('mr_surgery', schema)} WHERE {_WHERE}", params)
    cost_rows = _rows(session, f"SELECT * FROM {_table('mr_cost', schema)} WHERE {_WHERE}", params)
    return RawFrontpage(
        ref=ref,
        mr=mr_rows[0],
        diagnosis_rows=diagnosis_rows,
        diagnosis_source=diagnosis_source,
        surgery_rows=surgery_rows,
        cost_row=cost_rows[0] if cost_rows else None,
        notes=notes,
    )
