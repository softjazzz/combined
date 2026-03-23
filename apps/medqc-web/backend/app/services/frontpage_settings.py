"""
首页抽取配置服务

配置以 JSON 文件持久化，支持默认值回退，并提供运行时策略判断函数。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..core.settings import get_settings

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "frontpage_settings.json"


def _is_production_env() -> bool:
    env = (get_settings().ENV or "").strip().lower()
    return env in {"prod", "production"}


class FrontpageExtractionSettings(BaseModel):
    # 抽取策略
    sql_prefill_enabled: bool = True
    llm_backfill_enabled: bool = True
    allow_force_llm_regenerate: bool = True

    # 演示数据策略
    include_demo_records: bool = Field(default_factory=lambda: not _is_production_env())
    auto_hide_demo_when_real_data: bool = True
    demo_hide_threshold: int = Field(default=1, ge=0, le=100000)

    # 运行体验策略
    stream_progress_enabled: bool = True
    default_preview_tab: str = Field(default="fields", pattern="^(fields|preview)$")


def load_frontpage_settings() -> tuple[FrontpageExtractionSettings, str]:
    """加载首页抽取设置：优先文件，其次默认。"""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return FrontpageExtractionSettings(**data), "file"
        except Exception as exc:
            logger.warning("加载首页抽取配置失败，回退默认: %s", exc)
    return FrontpageExtractionSettings(), "default"


def save_frontpage_settings(settings: FrontpageExtractionSettings) -> None:
    """保存首页抽取设置到本地 JSON 文件。"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(settings.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("首页抽取配置已保存: %s", CONFIG_PATH)


def reset_frontpage_settings() -> FrontpageExtractionSettings:
    """重置并保存默认设置。"""
    settings = FrontpageExtractionSettings()
    save_frontpage_settings(settings)
    return settings


def update_frontpage_settings(update_data: dict[str, Any]) -> FrontpageExtractionSettings:
    """按字段更新并保存设置。"""
    current, _ = load_frontpage_settings()
    merged = current.model_dump()
    merged.update(update_data)
    updated = FrontpageExtractionSettings(**merged)
    save_frontpage_settings(updated)
    return updated


def should_include_demo_records(settings: FrontpageExtractionSettings, real_record_count: int) -> bool:
    """根据策略和真实数据量判断是否展示 demo 病历。"""
    if not settings.include_demo_records:
        return False
    if not settings.auto_hide_demo_when_real_data:
        return True
    return real_record_count < settings.demo_hide_threshold


def resolve_force_llm(requested_force_llm: bool, settings: FrontpageExtractionSettings) -> bool:
    """根据配置计算本次请求是否允许强制 LLM 重抽。"""
    if not requested_force_llm:
        return False
    if not settings.llm_backfill_enabled:
        return False
    if not settings.allow_force_llm_regenerate:
        return False
    return True

