"""医生病历读取范围：持久账号机构、科室、姓名与首页主治医师精确匹配。"""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import func, or_, tuple_

from ..database.connection import SessionLocal
from ..database.models.cdm import MedicalRecordFrontpage
from ..database.models.v36_reports import SysUser
from .clinical_read import clinical_query
from .defect_rectification_service import RectificationError, _person, _effective_persistent_roles
from .user_scope_owner import user_owner_options


_MANAGEMENT_ROLES = {"admin", "qc_manager", "qc_staff", "sync_admin", "super_admin"}


@dataclass(frozen=True)
class DoctorCaseScope:
    institute_id: str
    department: str
    doctor_name: str
    case_refs: tuple[tuple[str, str, str], ...]

    def predicate(self, model):
        return tuple_(model.institute_id, model.patient_id, model.visit_id).in_(self.case_refs)

    def require_case(self, institute_id, patient_id, visit_id):
        identity = tuple(str(v or "") for v in (institute_id, patient_id, visit_id))
        if any(not v or v != v.strip() for v in identity) or identity not in self.case_refs:
            raise HTTPException(403, "仅可查看本人名下病历")
        return dict(zip(("institute_id", "patient_id", "visit_id"), identity))

    def require_filters(self, department=None, doctor=None):
        if department and department.strip() != self.department:
            raise HTTPException(403, "无权查看其他科室病历")
        if doctor and doctor.strip() != self.doctor_name:
            raise HTTPException(403, "无权查看其他医生病历")


def resolve_doctor_case_scope(actor_id: str, *, session_factory=None) -> DoctorCaseScope | None:
    factory = session_factory or SessionLocal
    if factory is None:
        raise HTTPException(503, "账号授权来源暂不可用")
    try:
        with factory() as session:
            person = _person(session, actor_id)
            if "doctor" not in person["roles"] or person["roles"] & _MANAGEMENT_ROLES:
                return None
            institute, department, name = (
                str(person[key] or "").strip() for key in ("institute_id", "department", "name")
            )
            if not all((institute, department, name)):
                raise HTTPException(403, "请联系管理员核定医生姓名、机构和科室")
            # 同机构同科室的同名医生无法凭姓名区分，必须由管理员消除歧义。
            candidates = session.execute(
                SysUser.__table__.select().where(
                    SysUser.is_active.is_(True), SysUser.institute_id == institute,
                    SysUser.department == department, func.trim(SysUser.display_name) == name,
                ), execution_options=user_owner_options(session),
            ).mappings().all()
            doctors = [row for row in candidates if "doctor" in _effective_persistent_roles(row["role"], row["roles_json"])]
            if len(doctors) != 1:
                raise HTTPException(403, "存在同名医生账号，暂不能确定本人病历范围，请联系管理员")
            from ..database import clinical_connection
            if clinical_connection.configured():
                from .clinical_case_catalog import catalog, KEYS
                from sqlalchemy import select
                source = catalog(clinical_connection.get_engine())
                with clinical_connection.get_engine().connect() as connection:
                    rows = connection.execute(select(*[source.c[k] for k in KEYS]).where(
                        source.c.institute_id == institute, func.trim(source.c.department) == department,
                        func.trim(source.c.doctor) == name)).all()
                return DoctorCaseScope(institute, department, name, tuple(sorted(tuple(str(v) for v in row) for row in rows)))
            mr = MedicalRecordFrontpage
            from .medical_records.query_service import (
                _workstation_department_expr, _workstation_discharge_join_condition,
                _workstation_discharge_summary_subquery,
            )
            discharge = _workstation_discharge_summary_subquery(session)
            query = clinical_query(session, mr.institute_id, mr.patient_id, mr.visit_id)
            if discharge is not None:
                query = query.outerjoin(discharge, _workstation_discharge_join_condition(discharge))
            rows = query.filter(
                mr.institute_id == institute, func.trim(_workstation_department_expr(discharge)) == department,
                func.trim(mr.attending_physician_sign) == name,
            ).distinct().all()
            refs = tuple(sorted(
                tuple(str(v) for v in row) for row in rows
                if all(v is not None and str(v) and str(v) == str(v).strip() for v in row)
            ))
            return DoctorCaseScope(institute, department, name, refs)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "医生病历授权来源暂不可用，未开放其他病历") from exc


def resolve_record_identity(scope: DoctorCaseScope, record_id: str, *, session_factory=None):
    """旧单号入口必须唯一解析三坐标；同院/跨院同号也不能取第一条放行。"""
    from ..database import clinical_connection
    if clinical_connection.configured():
        from .clinical_case_catalog import resolve_identity
        return scope.require_case(**resolve_identity(record_id))
    factory = session_factory or SessionLocal
    try:
        if factory is None:
            raise RuntimeError("missing_case_source")
        with factory() as session:
            mr = MedicalRecordFrontpage
            rows = clinical_query(session, mr.institute_id, mr.patient_id, mr.visit_id).filter(
                or_(mr.visit_id == record_id, mr.mr_no == record_id, mr.inpat_no == record_id)
            ).distinct().limit(2).all()
    except Exception as exc:
        raise HTTPException(503, "病历身份来源暂不可用") from exc
    if len(rows) != 1:
        raise HTTPException(403, "病历身份不明确或不在本人名下")
    return scope.require_case(*rows[0])


def get_doctor_case_scope(request: Request) -> DoctorCaseScope | None:
    return getattr(request.state, "doctor_case_scope", None)


async def enforce_doctor_case_access(request: Request, user: dict[str, Any]) -> None:
    """普通医生只开放已接入范围或已有持久对象授权的入口，旧全院入口失败关闭。"""
    from starlette.concurrency import run_in_threadpool

    # user由默认认证从持久账号重建，不读取请求体、查询参数或JWT中的角色声明。
    if "doctor" not in (user.get("roles") or []):
        return
    path = request.url.path.rstrip("/")
    # 这些 owner 自行以持久收件人/申请人/任务责任人授权；不改其写入和CAS口径。
    owned_prefixes = (
        "/api/v1/auth/", "/api/v1/notifications", "/api/v1/record-reviews",
        "/api/v1/modern-appeals", "/api/v1/defect-rectifications", "/api/v1/case-communications",
    )
    if path.startswith(owned_prefixes) or path in {"/api/v1/runtime-build", "/api/v1/health", "/api/v1/clinical-sources/options"}:
        return
    scope = await run_in_threadpool(resolve_doctor_case_scope, str(user.get("id") or ""))
    request.state.doctor_case_scope = scope
    if scope is None:
        return
    query_paths = {"/api/medical-records/workstation", "/api/medical-records/list", "/api/medical-records/stats", "/api/medical-records/departments"}
    if path in query_paths and request.method == "GET":
        scope.require_filters(request.query_params.get("dept"), request.query_params.get("doctor"))
        return
    if path in {"/api/v1/workstation/qc-home", "/api/v1/records", "/api/v1/records/final"} and request.method == "GET":
        scope.require_filters(request.query_params.get("department"))
        return
    if path.startswith("/api/v1/records/") and path.endswith("/qc-detail") and request.method == "GET":
        request.state.doctor_case_identity = await run_in_threadpool(
            resolve_record_identity, scope, str(request.path_params.get("record_id") or ""),
        )
        return
    if path.startswith("/api/medical-records/") and request.method == "GET":
        parameters = request.path_params
        if all(parameters.get(k) for k in ("institute_id", "patient_id", "visit_id")):
            request.state.doctor_case_identity = scope.require_case(**{
                k: parameters[k] for k in ("institute_id", "patient_id", "visit_id")
            })
            return
        if path.startswith(("/api/medical-records/documents/", "/api/medical-records/frontpage-by-mr/", "/api/medical-records/frontpage-sheet/")):
            key = parameters.get("mr_no") or parameters.get("visit_id")
            identity = await run_in_threadpool(resolve_record_identity, scope, str(key or ""))
            if parameters.get("patient_id") and parameters["patient_id"] != identity["patient_id"]:
                raise HTTPException(403, "仅可查看本人名下病历")
            request.state.doctor_case_identity = identity
            return
    if path.startswith("/api/v1/emr/") and request.method == "GET":
        record_id = str(request.path_params.get("record_id") or "")
        provided = {k: request.query_params.get(k) for k in ("institute_id", "patient_id", "visit_id")}
        if all(provided.values()):
            identity = scope.require_case(**provided)
            if record_id != identity["visit_id"]:
                raise HTTPException(403, "病历路径与三坐标不符")
        else:
            identity = await run_in_threadpool(resolve_record_identity, scope, record_id)
        for key, value in identity.items():
            if request.query_params.get(key) and request.query_params[key] != value:
                raise HTTPException(403, "病历三坐标与本人授权范围不符")
        request.state.doctor_case_identity = identity
        return
    # 未接入逐病历授权的全院统计、旧缓存、客户样本和通用表导出不向医生放行。
    raise HTTPException(403, "当前入口未开放医生个人病历范围，请从病历池或本人待办进入")
