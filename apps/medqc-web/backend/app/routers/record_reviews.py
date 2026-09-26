"""病历初审/复审接口（任务受领范围）。

路由对象不带 prefix，各路径自带完整前缀：
- GET/POST /api/v1/tasks/{task_id}/records/{task_record_id}/review
- GET      /api/v1/record-reviews/todo
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal, NoReturn, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.permissions import PermissionAction, ResourceType, require_permission
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services import record_review_service as service
from ..services.record_review_service import (
    RecordReviewConflict,
    RecordReviewForbidden,
    RecordReviewInvalid,
    RecordReviewNotFound,
    RecordReviewUnavailable,
)
from .qc_sichuan import _sichuan_workspace_service
from .tasks import _get_task_scope_user_id

router = APIRouter(tags=["record-reviews"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "病历审核服务暂不可用，请稍后重试"
DashboardScene = Literal["all", "outpatient_emergency", "running", "final"]


class RecordReviewDecisionRequest(BaseModel):
    """提交审核决定；stage 由服务端计算，客户端不得指定。"""

    model_config = ConfigDict(extra="forbid")

    run_number: int = Field(..., strict=True, gt=0)
    decision: Literal["approved", "doubtful"]
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]] = None
    request_id: UUID
    envelope_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36)]

    @model_validator(mode="after")
    def _doubtful_requires_reason(self) -> "RecordReviewDecisionRequest":
        if self.decision == "doubtful" and not (self.reason or "").strip():
            raise ValueError("存疑必须填写原因")
        return self


def _raise_http(exc: Exception, *, log_message: str) -> NoReturn:
    if isinstance(exc, RecordReviewNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RecordReviewForbidden):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, RecordReviewInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, RecordReviewConflict):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    if not isinstance(exc, RecordReviewUnavailable):
        logger.exception(log_message)
    # 数据库/数据源故障一律固定脱敏，不回显 SQL 或内部信息。
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from exc


@router.get("/api/v1/tasks/{task_id}/records/{task_record_id}/review")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_record_review(
    request: Request,
    task_id: str,
    task_record_id: str,
    run_number: int = Query(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    """读取受领病历在指定运行结果上的审核状态与历史。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            service.get_record_review,
            task_id=task_id, task_record_id=task_record_id,
            run_number=run_number, actor_id=actor_id,
            workspace_factory=_sichuan_workspace_service,
        )
    except Exception as exc:  # noqa: BLE001 - 统一映射
        _raise_http(exc, log_message=f"读取病历审核失败 task_id={task_id}")
    return success_response(data=data, trace_id=get_trace_id(request))


@router.post("/api/v1/tasks/{task_id}/records/{task_record_id}/review")
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
async def submit_task_record_review(
    request: Request,
    task_id: str,
    task_record_id: str,
    body: RecordReviewDecisionRequest,
    current_user: dict = Depends(get_current_user),
):
    """受领人对当前结果对象提交初审/复审决定；决定不可修改。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            service.submit_record_review,
            task_id=task_id, task_record_id=task_record_id,
            run_number=body.run_number, decision=body.decision,
            reason=body.reason, request_id=str(body.request_id),
            envelope_id=body.envelope_id, actor_id=actor_id,
            workspace_factory=_sichuan_workspace_service,
        )
    except Exception as exc:  # noqa: BLE001 - 统一映射
        _raise_http(exc, log_message=f"提交病历审核失败 task_id={task_id}")
    audit_event(
        request,
        action="tasks.records.review.submit",
        resource="qc_record_review",
        outcome="success",
        details={
            "task_id": task_id, "task_record_id": task_record_id,
            "run_number": body.run_number, "review_id": data["id"],
            "stage": data["stage"], "decision": data["decision"],
            "idempotent": data["idempotent"],
        },
        current_user=current_user,
    )
    return success_response(data=data, message="审核决定已保存", trace_id=get_trace_id(request))


@router.get("/api/v1/record-reviews/todo")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def list_record_review_todos(
    request: Request,
    stage: Optional[Literal["initial", "recheck"]] = Query(None),
    scene: DashboardScene = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """本人待初审/待复审病例；与首页计数共用同一谓词。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            service.list_my_record_review_todos,
            actor_id=actor_id, stage=stage, scene=scene,
            page=page, page_size=page_size,
            workspace_factory=_sichuan_workspace_service,
        )
    except Exception as exc:  # noqa: BLE001 - 统一映射
        _raise_http(exc, log_message="读取病历审核待办失败")
    return success_response(data=data, trace_id=get_trace_id(request))


def count_my_record_review_todos(actor_id: str, scene: Optional[str] = None) -> dict[str, Any]:
    """供 dashboard 接线：返回 {"initial": int, "recheck": int}；失败抛异常由调用方映射 503。"""
    return service.count_my_record_review_todos(
        actor_id, scene=scene, workspace_factory=_sichuan_workspace_service,
    )
