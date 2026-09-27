"""Workstation V4 aggregated worklist and snapshot APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from ..core.data_scope import resolve_workstation_data_scope
from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..core.permissions import PermissionAction, ResourceType, require_permission
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.modern_case_qc_result_service import (
    CaseIdentityAmbiguous,
    CaseNotFound,
    SchemaUnavailable,
    SourceUnavailable,
    default_modern_case_qc_result_service,
)
from ..services.qc_persistence_service import VerifiedQCIdentity
from ..services.workstation.worklist_service import (
    WorklistIdentityAmbiguousError,
    default_workstation_aggregation_service,
)
from ..services.workstation.luxian_0609_result_analysis_service import (
    default_luxian_0609_result_analysis_service,
)

router = APIRouter(prefix="/api/v1/workstation", tags=["workstation"])
logger = logging.getLogger(__name__)

# 全院任意机构病例读取，暂时收窄到两个管理角色；机构对象级授权尚未完成。
# 该常量只是本批临时限制，不改变已落地的 QC_RESULTS:READ 资源门。
_MODERN_CASE_SNAPSHOT_ROLES = ("admin", "qc_manager")


def _current_user_id(current_user: dict | None) -> Optional[str]:
    if not current_user:
        return None
    return current_user.get("id") or current_user.get("user_id")


def _raise_workstation_http_error(exc: Exception) -> None:
    if isinstance(exc, WorklistIdentityAmbiguousError):
        raise HTTPException(status_code=409, detail="case_identity_ambiguous")
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

    scope = resolve_workstation_data_scope(current_user, department)
    try:
        data = default_workstation_aggregation_service.get_luxian_0609_home(
            department=scope.department,
            keyword=keyword,
            priority_limit=priority_limit,
            hospital_scope=scope.hospital_scope,
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

    scope = resolve_workstation_data_scope(current_user, department)
    try:
        data = default_workstation_aggregation_service.get_luxian_0609_analytics(
            completed_from=completed_from,
            completed_to=completed_to,
            department=scope.department,
            job_id=str(job_id) if job_id else None,
            hospital_scope=scope.hospital_scope,
        )
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

    scope = resolve_workstation_data_scope(current_user, department)
    try:
        data = default_luxian_0609_result_analysis_service.get_analysis(
            care_phase=care_phase,
            department=scope.department,
            doctor=doctor,
            rule_id=rule_id,
            result_status=result_status,
            completed_from=completed_from,
            completed_to=completed_to,
            page=page,
            page_size=page_size,
        )
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
        data = default_workstation_aggregation_service.get_home_hotspots(
            target_date=date,
            department=department,
            severity=severity,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
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
        data = default_workstation_aggregation_service.get_home_todos(
            department=department,
            workflow_type=workflow_type,
            keyword=keyword,
            recipient_id=_current_user_id(current_user),
            limit=limit,
        )
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
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/frontpage-qc/{visit_id}/snapshot")
async def get_frontpage_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_frontpage_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/coding-qc/{visit_id}/snapshot")
async def get_coding_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_coding_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/settlement-qc/{visit_id}/snapshot")
async def get_settlement_snapshot(
    request: Request,
    visit_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = default_workstation_aggregation_service.get_settlement_snapshot(
            visit_id,
            recipient_id=_current_user_id(current_user),
        )
        return success_response(data=data, trace_id=get_trace_id(request))
    except Exception as exc:
        _raise_workstation_http_error(exc)


@router.get("/case-qc/snapshot")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_modern_case_qc_snapshot(
    request: Request,
    institute_id: str = Query(..., description="机构标识"),
    patient_id: str = Query(..., description="患者标识"),
    visit_id: str = Query(..., description="就诊标识"),
    source_key: Literal[
        "frontpage_formal_qc",
        "coding_qc",
        "settlement_qc",
        "settlement_generate_qc",
    ] = Query(..., description="现代质控结果来源"),
    active_defects_offset: int = Query(0, ge=0, description="未关闭缺陷分页偏移"),
    current_result_defects_offset: int = Query(0, ge=0, description="本次结果缺陷分页偏移"),
    defects_limit: int = Query(20, ge=1, le=50, description="缺陷分页条数上限"),
    current_user: dict = Depends(require_roles(*_MODERN_CASE_SNAPSHOT_ROLES)),
):
    """按三坐标身份读取现代落库的质控快照。

    只接受完整的 institute/patient/visit + source_key 身份，不做 record_id 兼容回退；
    所有失败细节回传固定文案，避免把底层连接串或病例原文带出接口。
    两组缺陷各自分页：返回至多 ``defects_limit`` 条并给出 ``has_more``/``next_offset``。

    调用方按三坐标自填机构，因此本批临时限定 admin/qc_manager 两角色
    （``QC_RESULTS:READ`` 资源门同时保留），机构对象级授权仍待后续补足。
    服务读取是同步 SQLAlchemy，必须放到线程池执行，避免阻塞事件循环。
    """

    try:
        identity = VerifiedQCIdentity(institute_id, patient_id, visit_id, source_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="病例身份参数不合法") from exc

    try:
        snapshot = await run_in_threadpool(
            default_modern_case_qc_result_service.get_snapshot,
            identity,
            recipient_id=_current_user_id(current_user),
            active_defects_offset=active_defects_offset,
            current_result_defects_offset=current_result_defects_offset,
            defects_limit=defects_limit,
        )
    except HTTPException:
        raise
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="质控结果不存在") from exc
    except CaseIdentityAmbiguous as exc:
        raise HTTPException(status_code=409, detail="病例身份不唯一，无法读取质控结果") from exc
    except (SchemaUnavailable, SourceUnavailable) as exc:
        logger.warning("现代质控快照来源不可用: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="质控结果暂时不可用") from exc
    except Exception as exc:
        # 不复用会回显 str(exc) 的 _raise_workstation_http_error：该接口的异常可能带有连接串。
        logger.error("现代质控快照读取失败: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="质控结果暂时不可用") from exc

    return success_response(data=snapshot, trace_id=get_trace_id(request))
