"""Workstation V4 aggregated worklist and snapshot APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.doctor_case_scope import get_doctor_case_scope
from ..services.medical_records.detail_service import (
    InstituteCaseScope,
    enforce_institute_access,
    resolve_non_global_institute_scope,
)
from ..services.workstation.worklist_service import default_workstation_aggregation_service
from ..services.workstation.luxian_0609_result_analysis_service import (
    default_luxian_0609_result_analysis_service,
)

router = APIRouter(prefix="/api/v1/workstation", tags=["workstation"])
logger = logging.getLogger(__name__)


def _current_user_id(current_user: dict | None) -> Optional[str]:
    if not current_user:
        return None
    return current_user.get("id") or current_user.get("user_id")


def _effective_case_scope(request: Request, current_user: dict | None):
    doctor_scope = get_doctor_case_scope(request)
    if doctor_scope is not None:
        return doctor_scope
    inst_scope = resolve_non_global_institute_scope(current_user)
    if inst_scope is not None:
        return InstituteCaseScope(inst_scope)
    return None


def _filter_items_by_institute(items: object, inst_scope: Optional[str]) -> list:
    if not isinstance(items, list):
        return []
    if inst_scope is None:
        return items
    return [
        item for item in items
        if isinstance(item, dict) and str(item.get("institute_id") or "") == inst_scope
    ]


def _has_other_institute_records(inst_scope: str) -> bool:
    from ..database import clinical_connection, connection as db_connection
    from ..database.models.cdm import MedicalRecordFrontpage
    from ..services.clinical_read import clinical_query

    if clinical_connection.configured():
        from sqlalchemy import select
        from ..services.clinical_case_catalog import catalog

        eng = clinical_connection.get_engine()
        source = catalog(eng, include_frontpage=False)
        with eng.connect() as conn:
            other = conn.execute(
                select(source.c.institute_id)
                .where(source.c.institute_id != inst_scope)
                .limit(1)
            ).first()
        return other is not None

    session_factory = getattr(db_connection, "SessionLocal", None)
    if session_factory is None:
        return False
    try:
        with session_factory() as session:
            other = (
                clinical_query(session, MedicalRecordFrontpage.institute_id)
                .filter(MedicalRecordFrontpage.institute_id != inst_scope)
                .limit(1)
                .first()
            )
            return other is not None
    except Exception:
        return False


def _filter_worklist_payload(data: dict, inst_scope: Optional[str]) -> dict:
    if inst_scope is None or not isinstance(data, dict):
        return data
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        return data
    filtered = _filter_items_by_institute(raw_items, inst_scope)
    if len(filtered) == len(raw_items):
        return data
    updated = dict(data)
    updated["items"] = filtered
    updated["total"] = len(filtered)
    return updated


def _filter_home_payload(data: dict, inst_scope: Optional[str]) -> dict:
    if inst_scope is None or not isinstance(data, dict):
        return data
    updated = dict(data)
    for key in ("hotspots", "my_todo_items", "items"):
        if isinstance(updated.get(key), list):
            filtered = _filter_items_by_institute(updated[key], inst_scope)
            updated[key] = filtered
            if key == "items" and "total" in updated:
                updated["total"] = len(filtered)
    clinical_qc = updated.get("clinical_qc")
    if isinstance(clinical_qc, dict) and isinstance(clinical_qc.get("priority_records"), list):
        updated["clinical_qc"] = {
            **clinical_qc,
            "priority_records": _filter_items_by_institute(
                clinical_qc["priority_records"], inst_scope
            ),
        }
    return updated


def _validate_snapshot_scope(
    *,
    visit_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    current_user: dict | None,
) -> tuple[Optional[str], Optional[str]]:
    from ..database import clinical_connection, connection as db_connection
    from ..database.models.cdm import MedicalRecordFrontpage
    from ..services.clinical_read import clinical_query

    inst_scope = resolve_non_global_institute_scope(current_user)
    if inst_scope is not None and institute_id:
        enforce_institute_access(inst_scope, institute_id)
    effective_inst = inst_scope or (str(institute_id).strip() if institute_id else None)
    effective_pat = str(patient_id).strip() if patient_id else None

    if clinical_connection.configured():
        from sqlalchemy import select
        from ..services.clinical_case_catalog import KEYS, catalog

        eng = clinical_connection.get_engine()
        source = catalog(eng, include_frontpage=False)
        cond = source.c.visit_id == visit_id
        if effective_inst:
            cond &= source.c.institute_id == effective_inst
        if effective_pat:
            cond &= source.c.patient_id == effective_pat
        with eng.connect() as conn:
            rows = conn.execute(select(*[source.c[k] for k in KEYS]).where(cond).limit(2)).all()
            if len(rows) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="就诊号命中多份跨院或重复病历，请提供完整三坐标",
                )
            if not rows and inst_scope is not None:
                any_other = conn.execute(
                    select(source.c.institute_id).where(source.c.visit_id == visit_id).limit(1)
                ).first()
                if any_other is not None:
                    raise HTTPException(status_code=403, detail="无权访问其他机构病历快照")
        return effective_inst, effective_pat

    session_factory = getattr(db_connection, "SessionLocal", None)
    if session_factory is not None:
        try:
            with session_factory() as session:
                query = clinical_query(
                    session,
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                ).filter(MedicalRecordFrontpage.visit_id == visit_id)
                if effective_inst:
                    query = query.filter(MedicalRecordFrontpage.institute_id == effective_inst)
                if effective_pat:
                    query = query.filter(MedicalRecordFrontpage.patient_id == effective_pat)
                rows = query.distinct().limit(2).all()
                if len(rows) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail="就诊号命中多份跨院或重复病历，请提供完整三坐标",
                    )
                if not rows and inst_scope is not None:
                    any_other = (
                        clinical_query(session, MedicalRecordFrontpage.institute_id)
                        .filter(MedicalRecordFrontpage.visit_id == visit_id)
                        .limit(1)
                        .first()
                    )
                    if any_other is not None:
                        raise HTTPException(status_code=403, detail="无权访问其他机构病历快照")
        except HTTPException:
            raise
        except Exception:
            pass
    return effective_inst, effective_pat


def _verify_snapshot_result(
    data: dict,
    *,
    effective_inst: Optional[str],
    effective_pat: Optional[str],
) -> dict:
    if not isinstance(data, dict):
        return data
    actual_inst = data.get("institute_id")
    if effective_inst is not None and actual_inst is not None and str(actual_inst) != effective_inst:
        raise HTTPException(status_code=403, detail="无权访问其他机构病历快照")
    actual_pat = data.get("patient_id")
    if effective_pat is not None and actual_pat is not None and str(actual_pat) != effective_pat:
        raise HTTPException(status_code=404, detail="病历患者身份不匹配")
    return data


def _raise_workstation_http_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, HTTPException):
        raise exc
    logger.error("工作台聚合接口异常: %s", exc)
    raise HTTPException(status_code=500, detail=f"工作台聚合失败: {str(exc)}")


@router.get("/home")
async def get_workstation_home(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期 YYYY-MM-DD"),
    department: Optional[str] = Query(None, description="科室筛选"),
    severity: Optional[str] = Query(None, description="严重度筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    hotspot_limit: int = Query(50, ge=1, le=200),
    todo_limit: int = Query(12, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_home(
            target_date=date,
            department=department,
            severity=severity,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            hotspot_limit=hotspot_limit,
            todo_limit=todo_limit,
        )
        data = _filter_home_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/qc-home")
async def get_luxian_0609_home(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    priority_limit: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """当前全病历质控首页的轻量读取入口。"""

    try:
        effective_scope = _effective_case_scope(request, current_user)
        data = default_workstation_aggregation_service.get_luxian_0609_home(
            department=department,
            keyword=keyword,
            priority_limit=priority_limit,
            **({"case_scope": effective_scope} if effective_scope is not None else {}),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/analytics/luxian-0609")
async def get_luxian_0609_analytics(
    request: Request,
    completed_from: Optional[datetime] = Query(None, description="质控完成时间起点（闭区间）"),
    completed_to: Optional[datetime] = Query(None, description="质控完成时间终点（闭区间）"),
    department: Optional[str] = Query(None, description="科室筛选"),
    job_id: Optional[UUID] = Query(None, description="已完成根任务 ID"),
    current_user: dict = Depends(get_current_user),
):
    """全院临时范围内的泸县 Canonical 终末质控统计。"""

    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        kwargs = dict(
            completed_from=completed_from,
            completed_to=completed_to,
            department=department,
            job_id=str(job_id) if job_id else None,
        )
        if inst_scope is not None:
            try:
                data = default_workstation_aggregation_service.get_luxian_0609_analytics(
                    **kwargs,
                    institute_id=inst_scope,
                )
            except TypeError:
                if _has_other_institute_records(inst_scope):
                    raise HTTPException(
                        status_code=403,
                        detail="多院区环境下当前统计接口未开启分院隔离，无权跨院读取",
                    )
                data = default_workstation_aggregation_service.get_luxian_0609_analytics(**kwargs)
        else:
            data = default_workstation_aggregation_service.get_luxian_0609_analytics(**kwargs)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/qc-result-analysis/luxian-0609")
async def get_luxian_0609_result_analysis(
    request: Request,
    care_phase: Literal["inpatient", "discharged"] = Query(..., description="病历范围：在院/已出院"),
    department: Optional[str] = Query(None, description="科室筛选"),
    doctor: Optional[str] = Query(None, description="主管医师筛选"),
    rule_id: Optional[str] = Query(None, description="LX0609 质控点编码"),
    result_status: Optional[
        Literal[
            "non_compliant",
            "data_gap",
            "uncertain",
            "compliant",
            "not_applicable",
            "not_executed",
        ]
    ] = Query(None, description="客户可见的质控结果状态"),
    completed_from: Optional[datetime] = Query(None, description="质控完成时间起点（闭区间）"),
    completed_to: Optional[datetime] = Query(None, description="质控完成时间终点（闭区间）"),
    page: int = Query(1, ge=1, description="病历下钻页码"),
    page_size: int = Query(20, ge=1, le=100, description="病历下钻每页条数"),
    current_user: dict = Depends(get_current_user),
):
    """读取当前范围中每份病历最新 Canonical 结果的规则下钻统计。"""

    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        kwargs = dict(
            care_phase=care_phase,
            department=department,
            doctor=doctor,
            rule_id=rule_id,
            result_status=result_status,
            completed_from=completed_from,
            completed_to=completed_to,
            page=page,
            page_size=page_size,
        )
        if inst_scope is not None:
            try:
                data = default_luxian_0609_result_analysis_service.get_analysis(
                    **kwargs,
                    institute_id=inst_scope,
                )
            except TypeError:
                if _has_other_institute_records(inst_scope):
                    raise HTTPException(
                        status_code=403,
                        detail="多院区环境下当前统计下钻接口未开启分院隔离，无权跨院读取",
                    )
                data = default_luxian_0609_result_analysis_service.get_analysis(**kwargs)
                if isinstance(data, dict) and isinstance(data.get("record_page"), dict):
                    rp = data["record_page"]
                    if isinstance(rp.get("items"), list):
                        filtered_rp_items = _filter_items_by_institute(rp["items"], inst_scope)
                        data = {
                            **data,
                            "record_page": {
                                **rp,
                                "items": filtered_rp_items,
                                **({"total": len(filtered_rp_items)} if "total" in rp else {}),
                            },
                        }
        else:
            data = default_luxian_0609_result_analysis_service.get_analysis(**kwargs)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/home/hotspots")
async def get_workstation_home_hotspots(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期 YYYY-MM-DD"),
    department: Optional[str] = Query(None, description="科室筛选"),
    severity: Optional[str] = Query(None, description="严重度筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_home_hotspots(
            target_date=date,
            department=department,
            severity=severity,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
        data = _filter_home_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/home/todos")
async def get_workstation_home_todos(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    workflow_type: Optional[str] = Query(None, description="workflow 类型筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_home_todos(
            department=department,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
        data = _filter_home_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/frontpage-qc/worklist")
async def get_frontpage_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_frontpage_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        data = _filter_worklist_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/coding-qc/worklist")
async def get_coding_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_coding_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        data = _filter_worklist_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/settlement-qc/worklist")
async def get_settlement_worklist(
    request: Request,
    department: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号/住院号/visit 搜索"),
    queue_status: Optional[str] = Query(None, description="队列状态筛选"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query(None, description="排序方向 asc/desc"),
    current_user: dict = Depends(get_current_user),
):
    try:
        inst_scope = resolve_non_global_institute_scope(current_user)
        data = default_workstation_aggregation_service.get_settlement_worklist(
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=_current_user_id(current_user),
        )
        data = _filter_worklist_payload(data, inst_scope)
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/frontpage-qc/{visit_id}/snapshot")
async def get_frontpage_snapshot(
    request: Request,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构标识"),
    patient_id: Optional[str] = Query(None, description="患者标识"),
    current_user: dict = Depends(get_current_user),
):
    try:
        effective_inst, effective_pat = _validate_snapshot_scope(
            visit_id=visit_id,
            institute_id=institute_id,
            patient_id=patient_id,
            current_user=current_user,
        )
        data = default_workstation_aggregation_service.get_frontpage_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        data = _verify_snapshot_result(
            data, effective_inst=effective_inst, effective_pat=effective_pat
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/coding-qc/{visit_id}/snapshot")
async def get_coding_snapshot(
    request: Request,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构标识"),
    patient_id: Optional[str] = Query(None, description="患者标识"),
    current_user: dict = Depends(get_current_user),
):
    try:
        effective_inst, effective_pat = _validate_snapshot_scope(
            visit_id=visit_id,
            institute_id=institute_id,
            patient_id=patient_id,
            current_user=current_user,
        )
        data = default_workstation_aggregation_service.get_coding_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        data = _verify_snapshot_result(
            data, effective_inst=effective_inst, effective_pat=effective_pat
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/settlement-qc/{visit_id}/snapshot")
async def get_settlement_snapshot(
    request: Request,
    visit_id: str,
    institute_id: Optional[str] = Query(None, description="机构标识"),
    patient_id: Optional[str] = Query(None, description="患者标识"),
    current_user: dict = Depends(get_current_user),
):
    try:
        effective_inst, effective_pat = _validate_snapshot_scope(
            visit_id=visit_id,
            institute_id=institute_id,
            patient_id=patient_id,
            current_user=current_user,
        )
        data = default_workstation_aggregation_service.get_settlement_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        data = _verify_snapshot_result(
            data, effective_inst=effective_inst, effective_pat=effective_pat
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)
