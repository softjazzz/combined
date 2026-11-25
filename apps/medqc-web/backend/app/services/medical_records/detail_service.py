"""medical_records 域 - 详情服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect, select, text as sql_text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..clinical_read import clinical_query, clinical_read_schema, clinical_table_sql
from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import (
    MedicalRecordFrontpage,
    Diagnosis,
    MrSurgery,
    MrCost,
)
from ..document_assembly import assemble_document, build_document_select_columns
from .errors import MedicalRecordsNotFoundError, MedicalRecordsStorageError
from .shared import DOC_TYPES, build_concat_text

from ...core.roles import effective_roles

_GLOBAL_INSTITUTE_ROLES = frozenset({"admin", "super_admin", "sync_admin"})


def _normalize_user_roles(current_user: Optional[dict[str, Any]]) -> set[str]:
    if not isinstance(current_user, dict):
        return set()
    roles: set[str] = set()
    raw_roles = current_user.get("roles")
    if isinstance(raw_roles, (list, tuple, set)):
        roles.update(str(r).strip().lower() for r in raw_roles if str(r).strip())
    elif isinstance(raw_roles, str) and raw_roles.strip():
        roles.add(raw_roles.strip().lower())
    single_role = str(current_user.get("role") or "").strip().lower()
    if single_role:
        roles.add(single_role)
    return set(effective_roles(list(roles)))


def _resolve_scope_from_roles_and_institute(
    roles: set[str],
    raw_inst: Any,
) -> ResolvedInstituteScope:
    """统一全局视角条件：仅 sync_admin 或未绑定院区的 admin/super_admin 具备全局视角。"""
    if isinstance(raw_inst, str) and raw_inst and not raw_inst.strip():
        if "sync_admin" in roles:
            return ResolvedInstituteScope(kind="global", institute_id=None)
        return ResolvedInstituteScope(kind="missing", institute_id=None)

    actor_institute_id = raw_inst.strip() if isinstance(raw_inst, str) else ""
    if ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not actor_institute_id
    ):
        return ResolvedInstituteScope(kind="global", institute_id=None)

    if isinstance(raw_inst, str) and raw_inst.strip() and raw_inst == raw_inst.strip():
        return ResolvedInstituteScope(kind="institute", institute_id=raw_inst)
    return ResolvedInstituteScope(kind="missing", institute_id=None)


@dataclass(frozen=True)
class ResolvedInstituteScope:
    """显式区分三类账号机构范围：global（全局权限）、institute（仅本机构）、missing（机构缺失）。"""

    kind: Literal["global", "institute", "missing"]
    institute_id: Optional[str] = None


def inspect_institute_scope(current_user: Optional[dict[str, Any]]) -> ResolvedInstituteScope:
    """解析账号机构范围，严禁把未绑定机构的非全局账号或绑定院区的 admin 混同为全局权限。"""
    from ...database import connection as db_connection
    from ..defect_rectification_service import RectificationError, _person

    actor_id = str(
        (current_user or {}).get("id") or (current_user or {}).get("user_id") or ""
    ).strip()
    session_factory = getattr(db_connection, "SessionLocal", None)
    if session_factory is not None and actor_id:
        try:
            with session_factory() as session:
                person = _person(session, actor_id)
            return _resolve_scope_from_roles_and_institute(
                set(person["roles"]),
                person.get("institute_id"),
            )
        except RectificationError:
            # 单元测试未写入 sys_users 时的兼容回退：继续检查调用方主体。
            pass
        except OperationalError as exc:
            msg = str(exc).lower()
            if "no such table" not in msg and "no such column" not in msg:
                raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None

    roles = _normalize_user_roles(current_user)
    fallback_inst = (current_user or {}).get("institute_id")
    return _resolve_scope_from_roles_and_institute(roles, fallback_inst)


def resolve_non_global_institute_scope(current_user: Optional[dict[str, Any]]) -> Optional[str]:
    """为非全局角色解析持久 institute_id；仅全局角色返回 None，非全局机构缺失直接 fail-closed 403。"""
    resolved = inspect_institute_scope(current_user)
    if resolved.kind == "global":
        return None
    if resolved.kind == "institute" and resolved.institute_id:
        return resolved.institute_id
    raise HTTPException(status_code=403, detail="账号缺少可信机构范围")


def enforce_institute_access(
    institute_scope: Optional[str],
    target_institute_id: Optional[str],
) -> None:
    if institute_scope is None:
        return
    if (
        not isinstance(target_institute_id, str)
        or not target_institute_id.strip()
        or target_institute_id != institute_scope
    ):
        raise HTTPException(status_code=403, detail="无权访问其他机构病历数据")


@dataclass(frozen=True)
class InstituteCaseScope:
    """面向非全局管理/质控角色的机构范围适配器，复用现有 case_scope SQL 下推通道。"""

    institute_id: str

    def predicate(self, model: Any):
        return model.institute_id == self.institute_id

    def require_filters(self, department: Optional[str] = None, doctor: Optional[str] = None) -> None:
        return None

    @property
    def case_refs(self) -> tuple[tuple[str, str, str], ...]:
        from ...database import clinical_connection

        if clinical_connection.configured():
            from ..clinical_case_catalog import KEYS, catalog

            engine_obj = clinical_connection.get_engine()
            source = catalog(engine_obj, include_frontpage=False)
            with engine_obj.connect() as conn:
                rows = conn.execute(
                    select(*[source.c[k] for k in KEYS]).where(
                        source.c.institute_id == self.institute_id
                    )
                ).all()
            return tuple(sorted(tuple(str(v) for v in row) for row in rows))
        with _session_factory() as session:
            rows = (
                clinical_query(
                    session,
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                )
                .filter(MedicalRecordFrontpage.institute_id == self.institute_id)
                .distinct()
                .all()
            )
            return tuple(sorted(tuple(str(v) for v in row) for row in rows))


def list_departments_for_institute(institute_id: str) -> list[str]:
    from ...database import clinical_connection

    if clinical_connection.configured():
        from ..clinical_case_catalog import catalog

        engine_obj = clinical_connection.get_engine()
        source = catalog(engine_obj, include_frontpage=False)
        with engine_obj.connect() as conn:
            rows = conn.execute(
                select(source.c.department)
                .where(source.c.institute_id == institute_id, source.c.department.is_not(None))
                .distinct()
            ).scalars().all()
        return sorted({str(val).strip() for val in rows if str(val or "").strip()})

    with _session_factory() as session:
        rows = (
            clinical_query(
                session,
                MedicalRecordFrontpage.discharge_dept_name,
                MedicalRecordFrontpage.admission_dept_name,
            )
            .filter(MedicalRecordFrontpage.institute_id == institute_id)
            .all()
        )
        depts = {
            str(d_dept or a_dept or "").strip()
            for d_dept, a_dept in rows
            if str(d_dept or a_dept or "").strip()
        }
        return sorted(depts)

TIME_COLUMNS = (
    "record_datetime",
    "record_time",
    "round_datetime",
    "submit_datetime",
    "submit_time",
    "last_modified_time",
    "last_modified_datetime",
    "update_time",
)


def _get_table_columns(session: Session, table_name: str) -> set[str]:
    try:
        bind = session.get_bind() if hasattr(session, "get_bind") else None
        if bind is not None and bind.dialect.name == "sqlite":
            inspector = sa_inspect(bind)
            schema = clinical_read_schema()
            if not inspector.has_table(table_name, schema=schema):
                return set()
            return {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
        rows = session.execute(
            sql_text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND table_schema = :source_schema
                """
            ),
            {"table_name": table_name, "source_schema": clinical_read_schema() or "public"},
        ).mappings().all()
    except Exception:
        return {"record_content"}
    columns = {str(row.get("column_name")) for row in rows if row.get("column_name")}
    return columns


def _pick_time_columns(columns: set[str]) -> list[str]:
    return [column for column in TIME_COLUMNS if column in columns]


def _session_factory() -> Session:
    from ...database.clinical_connection import get_engine
    return Session(get_engine() or engine)


def _read_repository():
    from ...database.clinical_connection import configured
    if not configured():
        return get_repository()
    from ...database.repository import SqliteRepository
    repo = SqliteRepository()
    repo._session_factory = _session_factory
    return repo


def get_frontpage(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict[str, Any]]:
    repo = _read_repository()
    return repo.get_frontpage(institute_id, patient_id, visit_id)


def get_frontpage_by_mr_no(
    mr_no: str,
    *,
    institute_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    repo = _read_repository()
    from ...database.clinical_connection import configured
    if configured():
        from ..clinical_case_catalog import resolve_identity
        return repo.get_frontpage(
            **resolve_identity(mr_no, institute_id=institute_id, include_frontpage=True)
        )
    with _session_factory() as session:
        query = clinical_query(session, MedicalRecordFrontpage).filter(
            MedicalRecordFrontpage.mr_no == mr_no
        )
        if institute_id:
            query = query.filter(MedicalRecordFrontpage.institute_id == institute_id)
        rows = query.limit(2).all()
        if not rows:
            raise MedicalRecordsNotFoundError(f"病案号未找到: {mr_no}")
        if len(rows) > 1:
            raise HTTPException(
                status_code=409,
                detail="病案号对应多份跨院或重复病历，请提供完整三坐标",
            )
        row = rows[0]
        return repo.get_frontpage(row.institute_id, row.patient_id, row.visit_id)


def get_diagnoses(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = _read_repository()
    return repo.get_diagnoses(institute_id, patient_id, visit_id)


def get_surgeries(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = _read_repository()
    return repo.get_surgeries(institute_id, patient_id, visit_id)


def get_cost(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict]:
    repo = _read_repository()
    return repo.get_cost(institute_id, patient_id, visit_id)


def get_record_content(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    record_type: str = "admission",
) -> Optional[str]:
    repo = _read_repository()
    return repo.get_record_content(institute_id, patient_id, visit_id, record_type)


def _document_entry(table_name: str, label: str, row: dict, total_rows: int, index: int = 0) -> dict[str, Any]:
    assembled = assemble_document(table_name, row)
    content = assembled.assembled_text
    raw_title = assembled.document_title
    if raw_title:
        doc_label = raw_title
    elif total_rows <= 1:
        doc_label = label
    else:
        doc_label = f"{label} ({index + 1})"

    return {
        "type": table_name,
        "label": doc_label,
        "has_content": bool(content),
        "content": content if content else None,
        "length": len(content),
        "document_id": assembled.document_id or row.get("document_id"),
        "document_title": raw_title or None,
        "sort_time": assembled.display_time,
        "source_table": table_name,
        "record_time": assembled.record_time,
        "submit_time": assembled.submit_time,
        "last_modified_time": assembled.last_modified_time,
        "sections": [section.to_dict() for section in assembled.sections],
        "source_fields": [field.to_dict() for field in assembled.source_fields],
        "assembly_status": assembled.assembly_status,
        "data_quality_flags": list(assembled.data_quality_flags),
        **{key: row[key] for key in ("version_id", "source_record_identity", "source_namespace", "source_object", "daily_material", "daily_material_scope") if key in row},
    }


def _resolve_document_coordinates(
    session: Session,
    *,
    visit_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """当传入裸 visit_id 时，借助 mr 表校验是否存在跨院/跨患者重号，命中多条则 fail-closed 返回 409。"""
    if institute_id and patient_id:
        return institute_id, patient_id
    bind = session.get_bind() if hasattr(session, "get_bind") else None
    if bind is None:
        return institute_id, patient_id
    mr_cols = _get_table_columns(session, "mr")
    if not {"institute_id", "patient_id", "visit_id"}.issubset(mr_cols):
        return institute_id, patient_id
    query = clinical_query(
        session,
        MedicalRecordFrontpage.institute_id,
        MedicalRecordFrontpage.patient_id,
        MedicalRecordFrontpage.visit_id,
    ).filter(MedicalRecordFrontpage.visit_id == visit_id)
    if institute_id:
        query = query.filter(MedicalRecordFrontpage.institute_id == institute_id)
    if patient_id:
        query = query.filter(MedicalRecordFrontpage.patient_id == patient_id)
    matches = query.distinct().limit(2).all()
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="就诊号对应多份跨院或重复病历，请提供完整三坐标",
        )
    if len(matches) == 1:
        matched_inst, matched_pat, _ = matches[0]
        return (
            institute_id or (str(matched_inst).strip() if matched_inst else None),
            patient_id or (str(matched_pat).strip() if matched_pat else None),
        )
    return institute_id, patient_id


def get_documents(
    visit_id: str,
    mode: Optional[str] = None,
    session_factory: Callable[[], Any] | None = None,
    *,
    institute_id: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> dict[str, Any]:
    from ...database.clinical_connection import configured
    if configured() and session_factory is None:
        from ..clinical_case_catalog import resolve_identity
        from ..bundles.current_view import load_current_documents
        if institute_id and patient_id:
            resolved_identity = {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            }
        else:
            resolved_identity = resolve_identity(
                visit_id,
                patient_id=patient_id,
                institute_id=institute_id,
            )
        result = load_current_documents(**resolved_identity)
        if mode == "concat":
            content = "\n\n".join(doc.get("content") or "" for doc in result["documents"])
            return {"text": content, "visit_id": visit_id, "mode": "concat", "total_length": len(content),
                    "document_count": sum(bool(doc.get("has_content")) for doc in result["documents"])}
        return result
    session_factory = session_factory or _session_factory
    documents: list[dict[str, Any]] = []
    try:
        with session_factory() as session:
            resolved_inst, resolved_pat = _resolve_document_coordinates(
                session,
                visit_id=visit_id,
                institute_id=institute_id,
                patient_id=patient_id,
            )
            for table_name, label in DOC_TYPES:
                try:
                    columns = _get_table_columns(session, table_name)
                    if not columns:
                        documents.append(_document_entry(table_name, label, {}, 0))
                        continue

                    select_fields = build_document_select_columns(table_name, columns)
                    time_columns = _pick_time_columns(columns)

                    order_by = ""
                    if time_columns and "document_id" in columns:
                        order_by = f" ORDER BY COALESCE({', '.join(time_columns)}) NULLS LAST, document_id NULLS LAST"
                    elif time_columns:
                        order_by = f" ORDER BY COALESCE({', '.join(time_columns)}) NULLS LAST"
                    elif "document_id" in columns:
                        order_by = " ORDER BY document_id NULLS LAST"

                    where_clauses = ["visit_id = :vid"]
                    params: dict[str, Any] = {"vid": visit_id}
                    if resolved_inst and "institute_id" in columns:
                        where_clauses.append("institute_id = :inst_id")
                        params["inst_id"] = resolved_inst
                    if resolved_pat and "patient_id" in columns:
                        where_clauses.append("patient_id = :pid")
                        params["pid"] = resolved_pat

                    rows = session.execute(
                        sql_text(
                            f"SELECT {', '.join(select_fields)} FROM {clinical_table_sql(table_name)} "
                            f"WHERE {' AND '.join(where_clauses)}"
                            f"{order_by}"
                        ),
                        params,
                    ).mappings().all()
                    if rows:
                        for idx, row in enumerate(rows):
                            # SQLAlchemy 2.x 的 mappings() 返回 RowMapping；
                            # 在 Cython 严格类型场景下需显式转为 dict，避免类型检查失败后被误判为空文书。
                            documents.append(_document_entry(table_name, label, dict(row), len(rows), idx))
                    else:
                        documents.append(_document_entry(table_name, label, {}, 0))
                except Exception:
                    documents.append(_document_entry(table_name, label, {}, 0))
    except HTTPException:
        raise
    except Exception as exc:
        raise MedicalRecordsStorageError(f"查询文书失败: {exc}") from exc

    if mode == "concat":
        concat_text = build_concat_text(documents)
        return {
            "visit_id": visit_id,
            "mode": "concat",
            "text": concat_text,
            "total_length": len(concat_text),
            "document_count": len([d for d in documents if d["has_content"]]),
        }

    return {"documents": documents, "visit_id": visit_id}


def get_frontpage_sheet(
    patient_id: str,
    visit_id: str,
    session_factory: Callable[[], Any] | None = None,
    *,
    institute_id: Optional[str] = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    from ...database.clinical_connection import configured
    selection: dict[str, Any] = {}
    if institute_id:
        selection["institute_id"] = institute_id
    elif configured():
        from ..clinical_case_catalog import resolve_identity
        selection["institute_id"] = resolve_identity(visit_id, patient_id=patient_id)["institute_id"]
    with session_factory() as session:
        fps = clinical_query(session, MedicalRecordFrontpage).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
        ).limit(2).all()
        if not fps:
            raise MedicalRecordsNotFoundError("未找到病案首页数据")
        if len(fps) > 1:
            raise HTTPException(
                status_code=409,
                detail="病历命中多院区记录，请提供完整三坐标",
            )
        fp = fps[0]
        if getattr(fp, "institute_id", None):
            selection["institute_id"] = fp.institute_id

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            val = getattr(fp, col.name, None)
            basic[col.name] = str(val) if val is not None else None

        diag_rows = clinical_query(session, Diagnosis).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
        ).order_by(Diagnosis.diagnosis_type, Diagnosis.diagnosis_no).all()
        diagnoses = []
        main_diag_seen = False
        for diag in diag_rows:
            diagnosis_type = diag.diagnosis_type
            if diagnosis_type and "主要" in diagnosis_type:
                if main_diag_seen:
                    diagnosis_type = diagnosis_type.replace("主要诊断", "其他诊断")
                    if "主要" in diagnosis_type:
                        diagnosis_type = diagnosis_type.replace("主要", "其他")
                    if "主要" in diagnosis_type:
                        diagnosis_type = "出院诊断-其他诊断"
                else:
                    main_diag_seen = True
            diagnoses.append({
                "diagnosis_type": diagnosis_type,
                "diagnosis_no": diag.diagnosis_no,
                "diagnosis_name": diag.diagnosis_name,
                "diagnosis_code": diag.diagnosis_code,
                "admission_condition": diag.admission_condition,
                "discharge_condition": diag.discharge_condition,
            })

        surg_rows = clinical_query(session, MrSurgery).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
        ).all()
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

        cost_row = clinical_query(session, MrCost).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
        ).first()
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
        }
