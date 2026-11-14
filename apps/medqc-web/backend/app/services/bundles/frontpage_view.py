"""当前病历的首页只读投影；不参与质控 Bundle、事实抽取或持久化。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from .. import case_material_snapshot as case_material

from ...database.connection import engine
from ...database.models.cdm import MedicalRecordFrontpage, MrCost, MrSurgery
from ..clinical_read import clinical_table_sql
from ..validation_material_source import is_material_copy, material_source_schema


_HIDDEN = frozenset({
    "institute_id", "patient_id", "visit_id", "visit_type", "document_id",
    "update_time", "created_at", "updated_at", "local_sync_completed_at", "is_deleted", "v2_schema",
})
_DIAGNOSIS_COLUMNS = (
    ("diagnosis_no", "序号"), ("diagnosis_type", "诊断类型"),
    ("diagnosis_name", "诊断名称"), ("diagnosis_code", "诊断编码"),
    ("diagnosis_main", "主诊断标记"), ("admission_condition", "入院病情"),
    ("discharge_condition", "出院情况"),
)
_SURGERY_COLUMNS = tuple(
    (col.name, col.comment or col.name) for col in MrSurgery.__table__.columns
    if col.name not in _HIDDEN | {"inpat_no", "mr_no"}
)


def _value(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    # 0 和 False 也是源端已返回的值；不猜测代码值的临床含义。
    return str(value)


def _fields(model: Any, row: dict[str, Any], names: set[str] | None = None) -> list[dict[str, Any]]:
    return [
        {"key": col.name, "label": col.comment or col.name, "value": _value(row.get(col.name))}
        for col in model.__table__.columns
        if col.name not in _HIDDEN and (names is None or col.name in names)
    ]


def _table(columns: tuple[tuple[str, str], ...], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "columns": [{"key": key, "label": label} for key, label in columns],
        "rows": [{key: _value(row.get(key)) for key, _ in columns} for row in rows],
    }


def _confirmed_source_gap(schema: str, source_table: str) -> str | None:
    """只接受本轮已记录且一致的缺供给，不把未知或读取故障推断为空表。"""
    from ..automatic_material_scope import PROTOCOL

    state = case_material.context()
    automatic = (state or {}).get("automatic_material")
    if automatic is None:
        return None  # 无自动来源合同的旧路径保持原有查询与失败语义。
    if schema != state["schema"]:
        raise case_material.MaterialSnapshotError("material_schema_mismatch")
    if source_table not in state.get("columns", {}):
        raise case_material.MaterialSnapshotError("uncaptured_material_columns")
    if source_table not in state.get("tables", {}):
        raise case_material.MaterialSnapshotError("uncaptured_material_table")
    scope = automatic.get("sources", {}).get(source_table, {})
    status = scope.get("status")
    if automatic.get("protocol") != PROTOCOL or status not in {
        "table_missing", "columns_missing", "available", "empty_unconfirmed", "body_empty",
    }:
        raise case_material.MaterialSnapshotError("material_source_contract_incomplete")
    columns = state["columns"][source_table]
    rows = state["tables"][source_table]
    if scope.get("protocol") != PROTOCOL or scope.get("row_count") != len(rows):
        raise case_material.MaterialSnapshotError("material_source_contract_incomplete")
    if status == "table_missing":
        if columns or rows:
            raise case_material.MaterialSnapshotError("material_source_contract_incomplete")
        return status
    if not {"institute_id", "patient_id", "visit_id"}.issubset(columns):
        raise case_material.MaterialSnapshotError("material_identity_or_source_mismatch")
    if status == "columns_missing":
        if rows:
            raise case_material.MaterialSnapshotError("material_source_contract_incomplete")
        return status
    return None


@case_material.material_query
def load_frontpage_document(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, Any] | None:
    identity = {"institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id}
    if not all(str(v).strip() for v in identity.values()):
        raise ValueError("missing_frontpage_identity")
    tables: dict[str, list[dict[str, Any]]] = {}
    source_gaps: dict[str, str] = {}
    copy_schema = None
    if is_material_copy(patient_id, visit_id):
        from .assembly import _default_source_schema
        copy_schema = material_source_schema(default_schema=_default_source_schema(), **identity)
    # 全字段仅用于只读展示，不能扩大公共组装器的规则输入白名单。
    from .assembly import _default_source_schema, _source_engine
    from ...database.clinical_connection import configured
    read_engine = _source_engine("cdm") if configured() and not copy_schema else engine
    with case_material.source_connection(read_engine) as connection:
        for table in ("mr", "mr_diagnosis", "mr_surgery", "mr_cost"):
            source_table = "diagnosis" if table == "mr_diagnosis" and configured() and not copy_schema else table
            gap = _confirmed_source_gap(copy_schema or _default_source_schema(), source_table)
            if gap is not None:
                source_gaps[source_table] = gap
                records = []
            else:
                records = connection.execute(text(
                    f"SELECT * FROM {f'{copy_schema}.{table}' if copy_schema else clinical_table_sql(source_table)} "
                    "WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id "
                    "LIMIT 1001"
                ), identity).mappings().all()
            if len(records) > 1000 or (table in {"mr", "mr_cost"} and len(records) > 1):
                raise ValueError("frontpage_source_ambiguous_or_incomplete")
            tables[table] = [dict(row) for row in records]
            if table == "mr" and not records:
                return None

    main = tables["mr"][0]
    stay_names = {col.name for col in MedicalRecordFrontpage.__table__.columns if
                  col.name.startswith(("admission_", "discharge_", "transfer_")) or
                  col.name in {"hospital_duration", "diagnosis_date", "leaving_hospital_way",
                               "planned_transder_to", "rehospital_with_month", "rehospital_with_month_purpose"}}
    signature_names = {col.name for col in MedicalRecordFrontpage.__table__.columns if
                       "sign" in col.name and col.name not in {"allergy_sign", "death_autopsy_sign", "archive_sign"}}
    signature_names |= {"QC_date", "medicalrecord_quality", "archive_sign", "mr_datetime"}
    all_names = {col.name for col in MedicalRecordFrontpage.__table__.columns}
    groups = [
        {"key": "basic", "label": "首页基本信息", "fields": _fields(MedicalRecordFrontpage, main, all_names - stay_names - signature_names)},
        {"key": "stay", "label": "住院与出院信息", "fields": _fields(MedicalRecordFrontpage, main, stay_names)},
        {"key": "signatures", "label": "首页签署与归档", "fields": _fields(MedicalRecordFrontpage, main, signature_names)},
        {"key": "cost", "label": "费用信息", "fields": _fields(MrCost, tables["mr_cost"][0] if tables["mr_cost"] else {})},
    ]
    diagnoses = sorted(tables["mr_diagnosis"], key=lambda row: (
        str(row.get("diagnosis_type") or ""), str(row.get("diagnosis_no") or ""),
        str(row.get("diagnosis_id") or ""), str(row.get("diagnosis_name") or ""),
    ))
    surgeries = sorted(tables["mr_surgery"], key=lambda row: str(row.get("surgery_id") or ""))
    display = {"groups": groups, "diagnoses": _table(_DIAGNOSIS_COLUMNS, diagnoses),
               "surgeries": _table(_SURGERY_COLUMNS, surgeries)}
    sections = [
        {"section_key": group["key"], "section_label": group["label"],
         "text": "\n".join(f"{field['label']}：{field['value'] if field['value'] is not None else '未返回'}" for field in group["fields"]),
         "order_index": index}
        for index, group in enumerate(groups)
    ]
    for key, label in (("diagnoses", "首页诊断"), ("surgeries", "手术及操作")):
        table = display[key]
        lines = ["；".join(f"{col['label']}：{row[col['key']] if row[col['key']] is not None else '未返回'}" for col in table["columns"])
                 for row in table["rows"]]
        sections.append({"section_key": key, "section_label": label, "text": "\n".join(lines) or "未返回", "order_index": len(sections)})
    if source_gaps:
        display["source_gaps"] = source_gaps
        section_sources = {"cost": "mr_cost", "surgeries": "mr_surgery",
                           "diagnoses": "diagnosis" if configured() and not copy_schema else "mr_diagnosis"}
        for section in sections:
            status = source_gaps.get(section_sources.get(section["section_key"], ""))
            if status:
                section["text"] = "来源表缺失，相关信息暂不可用。" if status == "table_missing" else "来源字段不完整，相关信息暂不可用。"
    content = "\n\n".join(f"{section['section_label']}\n{section['text']}" for section in sections)
    document_id = str(main.get("document_id") or "")
    return {
        "id": document_id or f"mr::{visit_id}", "doc_key": f"mr::{document_id or visit_id}",
        "document_id": document_id, "doc_type": "mr", "document_title": "病案首页",
        "label": "病案首页", "group_key": "frontpage", "execution_domain": "index_coding_settlement",
        "record_time": "", "submit_time": "", "content": content, "length": len(content),
        "has_content": True, "sections": sections, "frontpage_display": display,
    }
