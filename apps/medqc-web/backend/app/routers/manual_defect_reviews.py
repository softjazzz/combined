"""人工缺陷审核路由（V3.6 合同第 3 节）。

- GET  /api/v1/manual-defects                   按审核状态分页列出任务受领人工缺陷
- POST /api/v1/manual-defects/{defect_id}/review  通过/驳回（行锁 + CAS）
两个接口都需要 QC_RESULTS.REVIEW 权限；数据库异常固定脱敏为 503。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from ..core.audit import audit_event
from ..core.permissions import PermissionAction, ResourceType, has_permission
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.manual_defect_review_service import (
    MAX_PAGE_SIZE,
    ManualDefectReviewConflict,
    ManualDefectReviewForbidden,
    ManualDefectReviewInvalid,
    ManualDefectReviewNotFound,
    ManualDefectReviewUnavailable,
    count_pending_manual_defects,
    list_case_manual_defects,
    list_manual_defects,
    review_manual_defect,
)

router = APIRouter(prefix="/api/v1/manual-defects", tags=["manual-defect-reviews"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "人工缺陷审核服务暂不可用，请稍后重试"

__all__ = ["router", "count_pending_manual_defects"]


class ManualDefectReviewRequest(BaseModel):
    """审核请求体；expected_status 只允许 pending。"""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    reason: Optional[str] = None
    expected_status: Literal["pending"]


class ManualDefectListItem(BaseModel):
    """列表字段白名单。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    institute_id: Optional[str]
    patient_id: Optional[str]
    visit_id: Optional[str]
    task_id: Optional[str]
    task_record_id: Optional[str]
    run_number: Optional[int]
    rule_code: Optional[str]
    rule_name: Optional[str]
    description: Optional[str]
    severity: Optional[str]
    location: Optional[str]
    suggestion: Optional[str]
    manual_review_status: Literal["pending", "approved", "rejected"]
    manual_created_by: Optional[str]
    created_at: Optional[datetime]


class ManualDefectReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    manual_review_status: Literal["approved", "rejected"]
    previous_status: Literal["pending"]
    reason: Optional[str]
    reviewer_id: str
    reviewed_at: datetime
    history_id: str


def _reviewer_id(current_user: dict) -> str:
    """与任务路由一致：真实认证字段 id 优先，兼容历史 user_id。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(user_id)


def _require_review(current_user: dict) -> str:
    user_id = _reviewer_id(current_user)
    if not has_permission(current_user, ResourceType.QC_RESULTS, PermissionAction.REVIEW):
        raise HTTPException(status_code=403, detail="没有人工缺陷审核权限")
    return user_id


@router.get("")
async def get_manual_defects(
    request: Request,
    review_status: Literal["pending", "approved", "rejected"] = Query("pending"),
    scene: Literal["all", "running", "final", "outpatient_emergency"] = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    current_user: dict = Depends(get_current_user),
):
    """按审核状态分页读取人工缺陷（精确 total）。"""
    _require_review(current_user)
    try:
        data = await run_in_threadpool(
            list_manual_defects,
            review_status=review_status, page=page, page_size=page_size, scene=scene,
        )
        result = {
            "items": [
                ManualDefectListItem.model_validate(item).model_dump(mode="json")
                for item in data["items"]
            ],
            "total": data["total"],
            "page": data["page"],
            "page_size": data["page_size"],
            "scene": data["scene"],
        }
    except ManualDefectReviewInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # 只记录异常类型，不回显 SQL 或异常原文。
        logger.error("manual_defect_list_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None
    return success_response(data=result, trace_id=get_trace_id(request))


@router.get("/case")
async def get_case_manual_defects(
    request: Request,
    institute_id: str = Query(..., min_length=1, max_length=128),
    patient_id: str = Query(..., min_length=1, max_length=128),
    visit_id: str = Query(..., min_length=1, max_length=128),
    scene: Literal["all", "running", "final", "outpatient_emergency"] = Query("all"),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """按三坐标分页读取该病例任务人工缺陷，默认第一页 200 条。"""
    _require_review(current_user)
    try:
        data = await run_in_threadpool(
            list_case_manual_defects,
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id, scene=scene,
            offset=offset, limit=limit,
        )
        result = {
            "items": [
                ManualDefectListItem.model_validate(item).model_dump(mode="json")
                for item in data["items"]
            ],
            "total": data["total"],
            "limit": data["limit"],
            "offset": data.get("offset", 0),
        }
    except ManualDefectReviewInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("manual_defect_case_list_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None
    return success_response(data=result, trace_id=get_trace_id(request))


@router.post("/{defect_id}/review")
async def post_manual_defect_review(
    request: Request,
    defect_id: str,
    body: ManualDefectReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """审核人工缺陷：仅 pending 可审，禁止自审，驳回必须填写原因。"""
    reviewer_id = _require_review(current_user)
    try:
        data = await run_in_threadpool(
            review_manual_defect,
            defect_id=defect_id, reviewer_id=reviewer_id,
            decision=body.decision, reason=body.reason,
            expected_status=body.expected_status,
        )
        result = ManualDefectReviewResult.model_validate(data).model_dump(mode="json")
    except ManualDefectReviewInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ManualDefectReviewNotFound as exc:
        raise HTTPException(status_code=404, detail="人工缺陷不存在") from exc
    except ManualDefectReviewForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ManualDefectReviewConflict as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except Exception as exc:
        # ManualDefectReviewUnavailable 与未知异常一律脱敏为 503。
        logger.error(
            "manual_defect_review_failed error_type=%s unavailable=%s",
            type(exc).__name__, isinstance(exc, ManualDefectReviewUnavailable),
        )
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None

    audit_event(
        request,
        action="manual_defects.review",
        resource="qc_defect",
        outcome="success",
        details={"defect_id": result["id"], "decision": result["manual_review_status"]},
        current_user=current_user,
    )
    return success_response(data=result, message="人工缺陷审核已保存", trace_id=get_trace_id(request))
