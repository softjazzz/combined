from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.settings import get_settings


router = APIRouter(prefix="/api/v1/sqlbot", tags=["sqlbot"])


class SQLBotConfigResponse(BaseModel):
    enabled: bool
    base_url: Optional[str] = None
    embed_url: Optional[str] = None
    app_id: Optional[str] = None
    display_mode: Literal["iframe", "disabled"] = "disabled"
    message: str


@router.get("/config", response_model=SQLBotConfigResponse)
def get_sqlbot_config() -> SQLBotConfigResponse:
    settings = get_settings()
    base_url = (settings.SQLBOT_BASE_URL or "").strip().rstrip("/")
    embed_url = (settings.SQLBOT_EMBED_URL or "").strip()
    app_id = (settings.SQLBOT_APP_ID or "").strip()

    if not settings.SQLBOT_ENABLED:
        return SQLBotConfigResponse(
            enabled=False,
            display_mode="disabled",
            message="SQLBot 未启用。请配置 SQLBOT_ENABLED=true 和 SQLBOT_EMBED_URL 后再使用问数能力。",
        )

    if not embed_url:
        return SQLBotConfigResponse(
            enabled=False,
            base_url=base_url or None,
            app_id=app_id or None,
            display_mode="disabled",
            message="SQLBot 已启用，但未配置嵌入地址 SQLBOT_EMBED_URL。",
        )

    return SQLBotConfigResponse(
        enabled=True,
        base_url=base_url or None,
        embed_url=embed_url,
        app_id=app_id or None,
        display_mode="iframe",
        message="SQLBot 已配置。问数能力将以独立嵌入面板打开。",
    )
