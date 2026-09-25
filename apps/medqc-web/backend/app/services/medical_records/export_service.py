"""medical_records 域 - 导出服务。"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from ...database.connection import Base, engine
from ...database.models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
from .errors import (
    MedicalRecordsConflictError,
    MedicalRecordsNotFoundError,
    MedicalRecordsSourceUnavailableError,
    MedicalRecordsValidationError,
)


DEFAULT_HOSPITAL_NAME = "泸县人民医院"

logger = logging.getLogger(__name__)


def _session_factory() -> Session:
    return Session(engine)


@contextmanager
def _source_session(session_factory: Callable[[], Any]) -> Any:
    """打开取数会话；数据库连接/读取异常按“取数不可用”收口。

    只转换 ``SQLAlchemyError``（连接失败、语句失败等），域错误（404/409/400/取数不可用）
    原样穿透，且不把 SQL、连接细节或患者标识带进对外文案。
    """

    try:
        with session_factory() as session:
            yield session
    except SQLAlchemyError as exc:
        logger.warning("病案首页取数失败: %s", type(exc).__name__)
        raise MedicalRecordsSourceUnavailableError("病案首页取数失败，请稍后重试") from exc


# 病案首页身份与三张明细表的权威 schema。
# 连接 search_path 以 public 打头（见 core/supabase_client），public 同名影子表会被优先命中；
# 首页四表必须显式限定 cdm，只有这一条主链。
CDM_SCHEMA = "cdm"

_cdm_tables: dict[str, Table] = {}
_cdm_sources: dict[str, Any] = {}


def _cdm_table(model: Any) -> Table:
    """``model`` 在 ``CDM_SCHEMA`` 下的等价表；列定义与 ORM 完全一致，按表名缓存。"""

    table_name = model.__table__.name
    table = _cdm_tables.get(table_name)
    if table is None:
        table = model.__table__.to_metadata(MetaData(), schema=CDM_SCHEMA)
        _cdm_tables[table_name] = table
    return table


def _frontpage_source(model: Any) -> Any:
    """首页四表的 ORM 取数源：始终钉到 ``cdm.<table>``，不回落裸表名。"""

    table_name = model.__table__.name
    source = _cdm_sources.get(table_name)
    if source is None:
        source = aliased(model, _cdm_table(model), adapt_on_names=True)
        _cdm_sources[table_name] = source
    return source


def get_schema(metadata: MetaData | None = None) -> dict[str, Any]:
    metadata = metadata or Base.metadata
    TABLE_LABELS = {
        "patient_information": "患者信息",
        "inpat_registration": "入院登记",
        "mr": "病案首页",
        "mr_surgery": "手术明细",
        "mr_cost": "费用明细",
        "diagnosis": "诊断表",
        "admission_record": "入院记录",
        "discharge_record": "出院记录",
        "qc_result": "质控结果",
    }

    tables = []
    for table_name, table_obj in metadata.tables.items():
        col_list = []
        for col in table_obj.columns:
            col_list.append({
                "name": col.name,
                "type": str(col.type),
                "comment": col.comment or "",
                "nullable": col.nullable,
                "primary_key": col.primary_key,
            })
        tables.append({
            "name": table_name,
            "label": TABLE_LABELS.get(table_name, table_name),
            "column_count": len(col_list),
            "columns": col_list,
        })

    return {"tables": tables, "total_tables": len(tables)}


def get_table_data(
    table_name: str,
    page: int = 1,
    page_size: int = 20,
    metadata: MetaData | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or Base.metadata
    allowed = set(metadata.tables.keys())
    if table_name not in allowed:
        raise MedicalRecordsNotFoundError(f"表不存在: {table_name}")

    session_factory = session_factory or _session_factory
    table_obj = metadata.tables[table_name]

    with session_factory() as session:
        total = session.execute(select(func.count()).select_from(table_obj)).scalar() or 0
        offset = (page - 1) * page_size
        rows = session.execute(select(table_obj).limit(page_size).offset(offset)).fetchall()
        columns = [col.name for col in table_obj.columns]

        items = []
        for row in rows:
            item = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                item[col_name] = val
            items.append(item)

    return {
        "table_name": table_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": columns,
        "items": items,
    }


def _sheet_basic_value(obj: Any, col_name: str) -> Any:
    val = getattr(obj, col_name, None)
    return str(val) if val is not None else None


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _is_main_diagnosis(row: Any) -> bool:
    diagnosis_type = str(_row_value(row, "diagnosis_type") or "").strip()
    diagnosis_no = str(_row_value(row, "diagnosis_no") or "").strip()
    diagnosis_main = str(_row_value(row, "diagnosis_main") or "").strip()
    return diagnosis_main == "是" or "主要" in diagnosis_type or diagnosis_no == "1"


def _build_sheet_diagnosis_item(row: Any, *, main_diag_seen: bool) -> tuple[dict[str, Any] | None, bool]:
    diagnosis_name = str(_row_value(row, "diagnosis_name") or "").strip()
    if not diagnosis_name:
        return None, main_diag_seen

    diagnosis_type = str(_row_value(row, "diagnosis_type") or "").strip()
    if _is_main_diagnosis(row) and not main_diag_seen:
        display_type = "主要诊断"
        main_diag_seen = True
    else:
        display_type = "其他诊断"

    item = {
        "diagnosis_type": display_type,
        "diagnosis_no": _row_value(row, "diagnosis_no"),
        "diagnosis_name": diagnosis_name,
        "diagnosis_code": _row_value(row, "diagnosis_code"),
        "admission_condition": _row_value(row, "admission_condition"),
        "discharge_condition": _row_value(row, "discharge_condition"),
        "source_diagnosis_type": diagnosis_type,
    }
    return item, main_diag_seen


def _build_pathology_info(row: Any | None) -> dict[str, Any]:
    if not row:
        return {}
    diagnosis_name = str(_row_value(row, "diagnosis_name") or "").strip()
    diagnosis_code = str(_row_value(row, "diagnosis_code") or "").strip()
    pathology_id = str(_row_value(row, "pathology_id") or "").strip()
    if not diagnosis_name and not diagnosis_code and not pathology_id:
        return {}
    return {
        "pathology_text": diagnosis_name,
        "pathology_icd": diagnosis_code,
        "pathology_no": pathology_id,
        "source_diagnosis_type": _row_value(row, "diagnosis_type"),
        "source_table": _row_value(row, "source_table"),
    }


def _resolve_frontpage_row(
    session: Any,
    *,
    patient_id: str,
    visit_id: str,
    institute_id: str | None,
) -> Any:
    """在病案首页上锁定唯一三坐标。

    - 首页表始终显式读 ``cdm.mr``，不经连接 search_path 猜测 public 同名影子表。
    - 显式机构：按 ``institute_id + patient_id + visit_id`` 精确匹配，只接受唯一一行。
    - 省略机构：仅在 patient+visit 唯一时可读；命中多行（含跨机构同号）按定位不唯一拒绝，
      不使用 ``.first()`` 猜首行。
    - 未解析到唯一机构坐标的行一律拒绝。
    """

    filters: dict[str, Any] = {"patient_id": patient_id, "visit_id": visit_id}
    if institute_id:
        filters["institute_id"] = institute_id
    rows = session.query(_frontpage_source(MedicalRecordFrontpage)).filter_by(**filters).all()
    if not rows:
        raise MedicalRecordsNotFoundError("未找到病案首页数据")
    if len(rows) > 1:
        raise MedicalRecordsConflictError("病案首页定位不唯一，请指定机构号后重试")
    row = rows[0]
    if not str(_row_value(row, "institute_id") or "").strip():
        raise MedicalRecordsConflictError("病案首页缺少机构坐标，无法安全读取")
    return row


def _query_institute_scoped_source(
    session: Any,
    statement: Any,
    coordinates: dict[str, Any],
    *,
    source: str,
) -> Any:
    """执行机构限定的原生兜底查询，读取失败时停止本次首页取数。

    兜底语句显式限定 ``cdm.`` 且三坐标之一必有 ``institute_id``（已按库核实两张兜底表结构），
    因此不存在“机构未限定却读到数据”的路径；来源不可读时不能把未知事实当成空值。
    对外不回显 SQL、连接细节或患者标识。
    """

    try:
        return session.execute(statement, coordinates)
    except SQLAlchemyError as exc:
        logger.warning("病案首页兜底来源读取失败: %s", source)
        raise MedicalRecordsSourceUnavailableError(
            "病案首页兜底来源读取失败，请稍后重试"
        ) from exc


def get_frontpage_sheet(
    patient_id: str,
    visit_id: str,
    institute_id: str | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """按 ``institute_id + patient_id + visit_id`` 三坐标读取病案首页。

    - 首页身份只认权威表 ``cdm.mr``（显式限定 schema，不经连接 search_path 解析）上的唯一三坐标；
      机构可显式给出，也可在 patient+visit 唯一时推断。
    - 省略机构而命中多机构/多行时按定位不唯一拒绝，不用 ``.first()`` 猜首行；显式空机构直接拒绝。
    - 关联的诊断/手术/费用同样显式限定 ``cdm``，与原生的 ``mr_diagnosis`` / ``discharge_record_diagnosis``
      兜底（原生语句显式限定 ``cdm.``）一并钉在解析出的同一机构上，禁止跨机构混读。
    """

    session_factory = session_factory or _session_factory
    if institute_id is not None and not str(institute_id).strip():
        raise MedicalRecordsValidationError("institute_id 不能为空")
    institute_key = str(institute_id).strip() if institute_id is not None else ""

    with _source_session(session_factory) as session:
        fp = _resolve_frontpage_row(
            session,
            patient_id=patient_id,
            visit_id=visit_id,
            institute_id=institute_key or None,
        )
        resolved_institute_id = str(getattr(fp, "institute_id", "") or "").strip()
        coordinates = {
            "institute_id": resolved_institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            basic[col.name] = _sheet_basic_value(fp, col.name)
        if not str(basic.get("institute_county_desc") or "").strip():
            basic["institute_county_desc"] = DEFAULT_HOSPITAL_NAME

        diag_source = _frontpage_source(Diagnosis)
        diag_rows = session.query(diag_source).filter_by(**coordinates).order_by(
            diag_source.diagnosis_type, diag_source.diagnosis_no
        ).all()
        diagnoses = []
        main_diag_seen = False
        for diag in diag_rows:
            item, main_diag_seen = _build_sheet_diagnosis_item(diag, main_diag_seen=main_diag_seen)
            if item:
                diagnoses.append(item)

        if not diagnoses:
            mr_diag_result = _query_institute_scoped_source(
                session,
                text(
                    "SELECT * FROM cdm.mr_diagnosis "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id AND visit_id = :visit_id "
                    "AND diagnosis_type LIKE '%出院诊断%' "
                    "ORDER BY CASE WHEN diagnosis_main = '是' THEN 0 ELSE 1 END, "
                    "CASE "
                    "WHEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '') ~ '^[0-9]+$' "
                    "THEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '')::int "
                    "ELSE 999 END, diagnosis_id"
                ),
                coordinates,
                source="mr_diagnosis",
            )
            mr_diag_rows = mr_diag_result.mappings().all()
            main_diag_seen = False
            for row in mr_diag_rows:
                item, main_diag_seen = _build_sheet_diagnosis_item(dict(row), main_diag_seen=main_diag_seen)
                if item:
                    item["source_table"] = "mr_diagnosis"
                    diagnoses.append(item)

        if not diagnoses:
            record_diag_result = _query_institute_scoped_source(
                session,
                text(
                    "SELECT * FROM cdm.discharge_record_diagnosis "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id AND visit_id = :visit_id "
                    "AND diagnosis_type LIKE '%出院诊断%' "
                    "AND COALESCE(is_deleted, '0') <> '1' "
                    "ORDER BY CASE WHEN diagnosis_main = '是' THEN 0 ELSE 1 END, "
                    "CASE "
                    "WHEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '') ~ '^[0-9]+$' "
                    "THEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '')::int "
                    "ELSE 999 END, diagnosis_id"
                ),
                coordinates,
                source="discharge_record_diagnosis",
            )
            record_diag_rows = record_diag_result.mappings().all()
            main_diag_seen = False
            for row in record_diag_rows:
                item, main_diag_seen = _build_sheet_diagnosis_item(dict(row), main_diag_seen=main_diag_seen)
                if item:
                    diagnoses.append(item)

        pathology_info: dict[str, Any] = {}
        pathology_row = next(
            (
                diag
                for diag in diag_rows
                if "病理" in str(_row_value(diag, "diagnosis_type") or "")
                or str(_row_value(diag, "diagnosis_code") or "").strip().upper().startswith("M")
            ),
            None,
        )
        if pathology_row:
            pathology_info = _build_pathology_info(pathology_row)
        else:
            mr_pathology_result = _query_institute_scoped_source(
                session,
                text(
                    "SELECT * FROM cdm.mr_diagnosis "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id AND visit_id = :visit_id "
                    "AND COALESCE(is_deleted, '0') <> '1' "
                    "AND (diagnosis_type LIKE '%病理%' OR diagnosis_code LIKE 'M%') "
                    "ORDER BY CASE WHEN diagnosis_type LIKE '%病理%' THEN 0 ELSE 1 END, diagnosis_id "
                    "LIMIT 1"
                ),
                coordinates,
                source="mr_diagnosis",
            )
            mr_pathology_row = mr_pathology_result.mappings().first()
            if mr_pathology_row:
                row = dict(mr_pathology_row)
                row["source_table"] = "mr_diagnosis"
                pathology_info = _build_pathology_info(row)

        surg_source = _frontpage_source(MrSurgery)
        surg_rows = session.query(surg_source).filter_by(**coordinates).all()
        surgeries = []
        for surg in surg_rows:
            surgeries.append({
                "surgery_name": surg.surgery_name,
                "surgery_code": surg.surgery_code,
                "surgical_level": surg.surgical_level,
                "surgery_begin_datetime": str(surg.surgery_begin_datetime) if surg.surgery_begin_datetime else None,
                "surgeon": surg.surgeon,
                "first_assistant": surg.first_assistant,
                "second_assistant": surg.second_assistant,
                "anesthesia_method": surg.anesthesia_method,
                "anesthesiologist": surg.anesthesiologist,
                "surgial_incision_level": surg.surgial_incision_level,
                "surgical_incisionheal_level": surg.surgical_incisionheal_level,
                "main_surgery_sign": surg.main_surgery_sign,
            })

        cost_source = _frontpage_source(MrCost)
        cost_rows = session.query(cost_source).filter_by(**coordinates).all()
        if len(cost_rows) > 1:
            raise MedicalRecordsConflictError("病案首页费用记录不唯一，无法安全读取")
        cost_row = cost_rows[0] if cost_rows else None
        cost_data = None
        if cost_row:
            cost_data = {}
            for col in MrCost.__table__.columns:
                val = getattr(cost_row, col.name, None)
                cost_data[col.name] = str(val) if val is not None else None

        return {
            "basic": basic,
            "diagnoses": diagnoses,
            "surgeries": surgeries,
            "cost": cost_data,
            "other_medical_info": pathology_info,
        }
