"""病历级操作记录路由（V3.6 病历操作记录时间线合同第 2 节）。

- GET /api/v1/record-operations/case  按三坐标只读装配该病例的操作时间线
需要 QC_RESULTS.REVIEW 权限；三坐标或 limit 非法返回 422；数据库异常固定脱敏为 503。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from ..core.permissions import PermissionAction, ResourceType, has_permission
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.case_operation_timeline_service import (
    DEFAULT_LIMIT,
    MAX_IDENTITY_LENGTH,
    MAX_LIMIT,
    CaseOperationTimelineInvalid,
    CaseOperationTimelineForbidden,
    list_case_operations,
)

router = APIRouter(prefix="/api/v1/record-operations", tags=["record-operations"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "病例操作记录服务暂不可用，请稍后重试"


class CaseOperationItem(BaseModel):
    """时间线事件字段白名单；summary 由服务按事件类型给出固定字段。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal[
        "qc_run_completed",
        "record_review",
        "manual_defect_created",
        "manual_defect_reviewed",
        "task_record_completed",
        "rectification_assigned",
        "rectification_submitted",
        "rectification_approved",
        "rectification_rejected",
        "rectification_urged",
        "rectification_urge_withdrawn",
    ]
    occurred_at: datetime
    actor_id: Optional[str]
    actor_name: Optional[str]
    summary: dict[str, Any]


def _require_review(current_user: dict) -> None:
    """与抽屉审核面板一致：真实认证字段 id 优先，兼容历史 user_id；需 QC_RESULTS.REVIEW。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    if not has_permission(current_user, ResourceType.QC_RESULTS, PermissionAction.REVIEW):
        raise HTTPException(status_code=403, detail="没有查看病例操作记录的权限")


@router.get("/case")
async def get_case_operations(
    request: Request,
    institute_id: str = Query(..., min_length=1, max_length=MAX_IDENTITY_LENGTH),
    patient_id: str = Query(..., min_length=1, max_length=MAX_IDENTITY_LENGTH),
    visit_id: str = Query(..., min_length=1, max_length=MAX_IDENTITY_LENGTH),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_user: dict = Depends(get_current_user),
):
    """按三坐标读取病例操作时间线（倒序，最近 limit 条 + 精确 total）。"""
    _require_review(current_user)
    try:
        data = await run_in_threadpool(
            list_case_operations,
            actor_id=str(current_user.get("id") or current_user.get("user_id")),
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id, limit=limit,
        )
        result = {
            # 回显三坐标供前端校验响应与当前病例一致。
            "institute_id": data["institute_id"],
            "patient_id": data["patient_id"],
            "visit_id": data["visit_id"],
            "items": [
                CaseOperationItem.model_validate(item).model_dump(mode="json")
                for item in data["items"]
            ],
            "total": data["total"],
            "limit": data["limit"],
        }
    except CaseOperationTimelineInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CaseOperationTimelineForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        # CaseOperationTimelineUnavailable 与未知异常一律脱敏为 503，只记录异常类型。
        logger.error("case_operation_timeline_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None
    return success_response(data=result, trace_id=get_trace_id(request))
