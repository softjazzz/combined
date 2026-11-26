"""诊断及手术操作完整性校验 API。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..database.connection import engine
from ..database.models.cdm import MedicalRecordFrontpage
from ..services.clinical_read import clinical_query, clinical_table_sql
from ..services.clinical_timeline_service import ClinicalTimelineService
from ..services.doctor_case_scope import get_doctor_case_scope, resolve_doctor_case_scope
from ..services.medical_records.detail_service import (
    _GLOBAL_INSTITUTE_ROLES,
    _normalize_user_roles,
    enforce_institute_access,
    resolve_non_global_institute_scope,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clinical-completeness", tags=["clinical-completeness"])

_CLINICAL_COMPLETENESS_READ_ROLES = frozenset({
    "admin",
    "super_admin",
    "sync_admin",
    "qc_manager",
    "qc_staff",
    "coder",
    "reviewer",
    "doctor",
})
_CLINICAL_COMPLETENESS_REFRESH_ROLES = frozenset({
    "admin",
    "super_admin",
    "sync_admin",
    "qc_manager",
    "qc_staff",
    "coder",
})
_MANAGEMENT_ROLES = frozenset({"admin", "super_admin", "sync_admin", "qc_manager", "qc_staff"})


def _resolve_authorized_tri_key(
    request: Request,
    current_user: Dict[str, Any],
    *,
    visit_id: str,
    patient_id: str = "",
    institute_id: str = "",
    allowed_roles: frozenset[str] = _CLINICAL_COMPLETENESS_READ_ROLES,
) -> tuple[str, str, str]:
    """校验角色、院区、医生作用域，并强制解析完整非空三坐标 (institute_id, patient_id, visit_id)。"""
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Authentication required")

    roles = _normalize_user_roles(current_user)
    if not (roles & allowed_roles):
        raise HTTPException(status_code=403, detail="当前角色无权访问诊断及手术完整性校验")

    vid = str(visit_id or "").strip()
    pid = str(patient_id or "").strip()
    iid = str(institute_id or "").strip()
    if not vid:
        raise HTTPException(status_code=400, detail="visit_id 不能为空")

    is_global = bool(roles & _GLOBAL_INSTITUTE_ROLES)
    inst_scope: Optional[str] = None
    if not is_global:
        inst_scope = resolve_non_global_institute_scope(current_user)
        if not inst_scope:
            raise HTTPException(status_code=403, detail="账号缺少可信机构范围")
        if iid:
            enforce_institute_access(inst_scope, iid)
        else:
            iid = inst_scope

    # 若缺 institute_id 或 patient_id，按授权院区范围唯一解析三坐标，多院/多患者重号 fail-closed 409
    if not (iid and pid):
        if engine is None:
            raise HTTPException(
                status_code=400,
                detail="缺少完整病例三坐标 (institute_id, patient_id, visit_id)",
            )
        with Session(engine) as session:
            q = clinical_query(
                session,
                MedicalRecordFrontpage.institute_id,
                MedicalRecordFrontpage.patient_id,
                MedicalRecordFrontpage.visit_id,
            ).filter(MedicalRecordFrontpage.visit_id == vid)
            if iid:
                q = q.filter(MedicalRecordFrontpage.institute_id == iid)
            if pid:
                q = q.filter(MedicalRecordFrontpage.patient_id == pid)
            rows = q.distinct().limit(2).all()
            if len(rows) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="同一 visit_id 存在多院区或多患者重号，请显式传入 institute_id 和 patient_id",
                )
            if len(rows) == 1:
                iid = str(rows[0][0] or "").strip()
                pid = str(rows[0][1] or "").strip()
            else:
                clauses = ["visit_id = :vid"]
                params: Dict[str, Any] = {"vid": vid}
                if iid:
                    clauses.append("institute_id = :iid")
                    params["iid"] = iid
                if pid:
                    clauses.append("patient_id = :pid")
                    params["pid"] = pid
                try:
                    reg_rows = (
                        session.execute(
                            sql_text(
                                f"SELECT DISTINCT institute_id, patient_id, visit_id "
                                f"FROM {clinical_table_sql('inpat_registration')} "
                                f"WHERE {' AND '.join(clauses)} LIMIT 2"
                            ),
                            params,
                        )
                        .mappings()
                        .all()
                    )
                except Exception:
                    reg_rows = []
                if len(reg_rows) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail="同一 visit_id 存在多院区或多患者重号，请显式传入 institute_id 和 patient_id",
                    )
                if len(reg_rows) == 1:
                    iid = str(reg_rows[0].get("institute_id") or "").strip()
                    pid = str(reg_rows[0].get("patient_id") or "").strip()

    if not (iid and pid and vid):
        raise HTTPException(
            status_code=400,
            detail="无法唯一确定完整病例三坐标 (institute_id, patient_id, visit_id)，拒绝读写空坐标缓存",
        )

    if not is_global:
        enforce_institute_access(inst_scope, iid)

    # 医生角色强制校验本人名下病例范围
    doctor_scope = get_doctor_case_scope(request)
    if doctor_scope is None and "doctor" in roles and not (roles & _MANAGEMENT_ROLES):
        actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
        if not actor_id:
            raise HTTPException(status_code=403, detail="缺少可信医生账号身份")
        doctor_scope = resolve_doctor_case_scope(actor_id)
    if doctor_scope is not None:
        doctor_scope.require_case(iid, pid, vid)

    return iid, pid, vid


def _load_clinical_bundle(
    *,
    visit_id: str,
    patient_id: str = "",
    institute_id: str = "",
    force_refresh: bool = False,
    read_only: bool = True,
) -> dict[str, Any]:
    """加载用于诊断/手术完整性校验的病历 bundle。

    - 强制非空三坐标，禁止写入 ('', '', visit_id) 脏缓存；
    - read_only=True 时使用纯只读装配 assemble_final_record_bundle，绝不写缓存表；
    - 仅显式 POST 刷新入口允许 read_only=False 写缓存。
    """
    iid = str(institute_id or "").strip()
    pid = str(patient_id or "").strip()
    vid = str(visit_id or "").strip()
    if not (iid and pid and vid):
        raise ValueError("必须提供完整非空三坐标 (institute_id, patient_id, visit_id)")

    if read_only:
        if force_refresh:
            raise ValueError("只读加载模式禁止 force_refresh 写库")
        from ..services.bundles.assembly import assemble_final_record_bundle

        return assemble_final_record_bundle(
            institute_id=iid,
            patient_id=pid,
            visit_id=vid,
        )

    from ..services.bundles.assembly import load_or_assemble_scene_bundle

    return load_or_assemble_scene_bundle(
        scene="final",
        institute_id=iid,
        patient_id=pid,
        visit_id=vid,
        force_refresh=force_refresh,
    )


@router.get("/{visit_id}")
async def get_clinical_completeness(
    request: Request,
    visit_id: str,
    patient_id: str = Query("", description="患者 ID；有值时可更精确定位 bundle"),
    institute_id: str = Query("", description="机构 ID"),
    force_refresh: bool = Query(False, description="只读 GET 禁止传 true 写库；请使用 POST /{visit_id}/refresh"),
    current_user: dict = Depends(get_current_user),
):
    """返回诊断发生发展时间轴和手术操作执行验证。

    该接口严格只读，不写正式病案首页、医保结算清单、正式质控结果或 bundle 缓存表。
    """
    if force_refresh:
        raise HTTPException(
            status_code=405,
            detail="GET 接口严格只读，禁止通过 force_refresh=true 写库；请使用 POST /api/v1/clinical-completeness/{visit_id}/refresh",
        )

    resolved_iid, resolved_pid, resolved_vid = _resolve_authorized_tri_key(
        request,
        current_user,
        visit_id=visit_id,
        patient_id=patient_id,
        institute_id=institute_id,
        allowed_roles=_CLINICAL_COMPLETENESS_READ_ROLES,
    )

    try:
        bundle = _load_clinical_bundle(
            visit_id=resolved_vid,
            patient_id=resolved_pid,
            institute_id=resolved_iid,
            force_refresh=False,
            read_only=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("加载临床完整性 bundle 失败 visit_id=%s error=%s", resolved_vid, type(exc).__name__)
        raise HTTPException(status_code=503, detail=f"病历文书 bundle 暂不可用：{exc}") from exc

    timeline = ClinicalTimelineService().build_from_bundle(bundle)
    data = timeline.to_dict()
    data["safety"] = {
        "mode": "read_only_analysis",
        "writes_formal_frontpage": False,
        "writes_settlement": False,
        "writes_formal_qc_result": False,
        "writes_bundle_cache": False,
    }
    return success_response(
        data=data,
        message="诊断及手术操作完整性分析完成",
        trace_id=get_trace_id(request),
    )


@router.post("/{visit_id}/refresh")
async def refresh_clinical_completeness(
    request: Request,
    visit_id: str,
    patient_id: str = Query(..., min_length=1, description="患者 ID（必填三坐标）"),
    institute_id: str = Query(..., min_length=1, description="机构 ID（必填三坐标）"),
    current_user: dict = Depends(get_current_user),
):
    """显式 POST 刷新指定完整三坐标病例的 bundle 缓存并返回诊断/手术完整性分析。"""
    resolved_iid, resolved_pid, resolved_vid = _resolve_authorized_tri_key(
        request,
        current_user,
        visit_id=visit_id,
        patient_id=patient_id,
        institute_id=institute_id,
        allowed_roles=_CLINICAL_COMPLETENESS_REFRESH_ROLES,
    )

    try:
        bundle = _load_clinical_bundle(
            visit_id=resolved_vid,
            patient_id=resolved_pid,
            institute_id=resolved_iid,
            force_refresh=True,
            read_only=False,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("刷新临床完整性 bundle 失败 visit_id=%s error=%s", resolved_vid, type(exc).__name__)
        raise HTTPException(status_code=503, detail=f"病历文书 bundle 刷新失败：{exc}") from exc

    timeline = ClinicalTimelineService().build_from_bundle(bundle)
    data = timeline.to_dict()
    data["safety"] = {
        "mode": "explicit_cache_refresh",
        "writes_formal_frontpage": False,
        "writes_settlement": False,
        "writes_formal_qc_result": False,
        "writes_bundle_cache": True,
    }
    return success_response(
        data=data,
        message="诊断及手术操作完整性缓存已刷新",
        trace_id=get_trace_id(request),
    )
