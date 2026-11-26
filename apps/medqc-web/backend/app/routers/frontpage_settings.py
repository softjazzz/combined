"""
首页抽取设置 API
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.security import require_global_system_admin, require_roles
from ..services.frontpage_settings import (
    FrontpageExtractionSettings,
    load_frontpage_settings,
    reset_frontpage_settings,
    update_frontpage_settings,
)

router = APIRouter(
    prefix="/api/v1/frontpage/settings",
    tags=["Frontpage Settings"],
    dependencies=[
        Depends(require_roles("admin", "qc_manager", "sync_admin", "super_admin"))
    ],
)


class FrontpageSettingsResponse(BaseModel):
    settings: FrontpageExtractionSettings
    source: str = "default"  # default / file


class FrontpageSettingsUpdateRequest(BaseModel):
    # 抽取策略
    sql_prefill_enabled: Optional[bool] = None
    llm_backfill_enabled: Optional[bool] = None
    allow_force_llm_regenerate: Optional[bool] = None

    # 演示数据策略
    include_demo_records: Optional[bool] = None
    auto_hide_demo_when_real_data: Optional[bool] = None
    demo_hide_threshold: Optional[int] = Field(default=None, ge=0, le=100000)

    # 运行体验策略
    stream_progress_enabled: Optional[bool] = None
    default_preview_tab: Optional[str] = Field(default=None, pattern="^(fields|preview)$")


@router.get("", response_model=FrontpageSettingsResponse)
async def get_frontpage_settings():
    settings, source = load_frontpage_settings()
    return FrontpageSettingsResponse(settings=settings, source=source)


@router.put("", response_model=FrontpageSettingsResponse)
async def put_frontpage_settings(
    payload: FrontpageSettingsUpdateRequest,
    _admin_user: dict = Depends(require_global_system_admin),
):
    del _admin_user
    updated = update_frontpage_settings(payload.model_dump(exclude_none=True))
    return FrontpageSettingsResponse(settings=updated, source="file")


@router.post("/reset", response_model=FrontpageSettingsResponse)
async def post_frontpage_settings_reset(
    _admin_user: dict = Depends(require_global_system_admin),
):
    del _admin_user
    settings, source = reset_frontpage_settings()
    return FrontpageSettingsResponse(settings=settings, source=source)
