"""V3.6 质控员工作分析接口。"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from ..core.data_scope import resolve_workstation_data_scope
from ..core.response import get_trace_id, success_response
from ..core.security import require_roles
from ..services import staff_work_analysis_service as analysis_service


router = APIRouter(prefix="/api/v1/quality-reports", tags=["quality-reports"])
logger = logging.getLogger(__name__)
_UNAVAILABLE_DETAIL = "质控员工作分析暂不可用，请稍后重试"


@router.get("/staff-work")
async def get_staff_work_analysis(
    request: Request,
    period: Literal["this_week", "last_week", "this_month"] = Query("this_week"),
    scene: Literal["all", "running", "final"] = Query("all"),
    current_user: dict = Depends(require_roles("admin", "qc_manager")),
):
    scope = resolve_workstation_data_scope(current_user, None)
    if scope.hospital_scope != "all":
        raise HTTPException(status_code=403, detail="无权查看全院质控员工作分析")
    try:
        data = await run_in_threadpool(
            analysis_service.get_staff_work_analysis, period=period, scene=scene,
        )
    except analysis_service.StaffWorkAnalysisInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("staff_work_analysis_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None
    return success_response(data=data, trace_id=get_trace_id(request))
