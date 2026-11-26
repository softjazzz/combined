"""系统配置中的模型性能观测只读接口。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from ..core.response import get_trace_id, success_response
from ..core.security import require_global_system_admin
from ..services.llm_observability_read import (
    LLMObservabilityFilters,
    LLMObservabilityReadService,
    LLMObservabilityUnavailableError,
)
from ..storage.memory import DEFAULT_DEMO_USER_EMAILS


router = APIRouter(
    prefix="/api/v1/system/llm-observability",
    tags=["llm-observability"],
)

_SYSTEM_OBSERVABILITY_ROLES = ("admin", "sync_admin", "super_admin")


def get_llm_observability_read_service() -> LLMObservabilityReadService:
    return LLMObservabilityReadService()


def _normalize_query_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_filters(
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    business_scene: str | None,
    provider_code: str | None,
    model: str | None,
    root_job_id: str | None,
) -> LLMObservabilityFilters:
    normalized_start = _normalize_query_datetime(start_at)
    normalized_end = _normalize_query_datetime(end_at)
    if normalized_start is not None and normalized_end is not None and normalized_start > normalized_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_at 不能晚于 end_at",
        )
    return LLMObservabilityFilters(
        start_at=normalized_start,
        end_at=normalized_end,
        business_scene=business_scene,
        provider_code=provider_code,
        model=model,
        root_job_id=root_job_id,
    )


async def require_llm_observability_user(
    current_user: dict = Depends(require_global_system_admin),
) -> dict:
    normalized_email = str(current_user.get("email") or "").strip().lower()
    role_names = {
        str(role or "").strip().lower()
        for role in (current_user.get("roles") or [])
        if str(role or "").strip()
    }
    is_operational_admin = bool({"sync_admin", "super_admin"}.intersection(role_names))
    if normalized_email in DEFAULT_DEMO_USER_EMAILS and not is_operational_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="演示账号不可访问模型性能观测数据",
        )
    return current_user


@router.get("/overview")
async def get_llm_observability_overview(
    request: Request,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    business_scene: str | None = Query(default=None, max_length=100),
    provider_code: str | None = Query(default=None, max_length=100),
    model: str | None = Query(default=None, max_length=200),
    root_job_id: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _current_user: dict = Depends(require_llm_observability_user),
    service: LLMObservabilityReadService = Depends(get_llm_observability_read_service),
):
    try:
        payload = await service.build_overview(
            filters=_build_filters(
                start_at=start_at,
                end_at=end_at,
                business_scene=business_scene,
                provider_code=provider_code,
                model=model,
                root_job_id=root_job_id,
            ),
            page=page,
            page_size=page_size,
        )
    except LLMObservabilityUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="模型性能观测数据暂不可用",
        )
    return success_response(
        data=payload,
        message="模型性能观测数据获取成功",
        trace_id=get_trace_id(request),
    )


@router.get("/records/{record_key_hash}/calls")
async def get_llm_observability_record_calls(
    request: Request,
    record_key_hash: str = Path(min_length=1, max_length=128),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    business_scene: str | None = Query(default=None, max_length=100),
    provider_code: str | None = Query(default=None, max_length=100),
    model: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _current_user: dict = Depends(require_llm_observability_user),
    service: LLMObservabilityReadService = Depends(get_llm_observability_read_service),
):
    try:
        payload = await service.build_record_calls(
            record_key_hash=record_key_hash,
            filters=_build_filters(
                start_at=start_at,
                end_at=end_at,
                business_scene=business_scene,
                provider_code=provider_code,
                model=model,
                root_job_id=None,
            ),
            page=page,
            page_size=page_size,
        )
    except LLMObservabilityUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="模型性能观测数据暂不可用",
        )
    return success_response(
        data=payload,
        message="单病历模型调用明细获取成功",
        trace_id=get_trace_id(request),
    )


@router.get("/records")
async def get_llm_observability_records(
    request: Request,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    business_scene: str | None = Query(default=None, max_length=100),
    provider_code: str | None = Query(default=None, max_length=100),
    model: str | None = Query(default=None, max_length=200),
    root_job_id: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _current_user: dict = Depends(require_llm_observability_user),
    service: LLMObservabilityReadService = Depends(get_llm_observability_read_service),
):
    try:
        payload = await service.build_records(
            filters=_build_filters(
                start_at=start_at,
                end_at=end_at,
                business_scene=business_scene,
                provider_code=provider_code,
                model=model,
                root_job_id=root_job_id,
            ),
            page=page,
            page_size=page_size,
        )
    except LLMObservabilityUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="模型性能观测数据暂不可用",
        )
    return success_response(
        data=payload,
        message="单病历模型调用统计获取成功",
        trace_id=get_trace_id(request),
    )
