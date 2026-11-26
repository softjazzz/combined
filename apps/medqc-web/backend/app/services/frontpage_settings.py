"""
首页抽取配置服务

配置以 JSON 文件持久化，支持默认值回退，并提供运行时策略判断函数。
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..core.settings import get_settings

logger = logging.getLogger(__name__)

_SETTINGS_LOCK = threading.RLock()
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
    auto_hide_demo_when_real_data: bool = False
    demo_hide_threshold: int = Field(default=1, ge=0, le=100000)

    # 运行体验策略
    stream_progress_enabled: bool = True
    default_preview_tab: str = Field(default="preview", pattern="^(fields|preview)$")


def load_frontpage_settings() -> tuple[FrontpageExtractionSettings, str]:
    """加载首页抽取设置：优先文件，其次默认。"""
    with _SETTINGS_LOCK:
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                return FrontpageExtractionSettings(**data), "file"
            except Exception as exc:
                logger.warning("加载首页抽取配置失败，回退默认: %s", exc)
    return FrontpageExtractionSettings(), "default"


def save_frontpage_settings(settings: FrontpageExtractionSettings) -> None:
    """使用线程锁 + 同目录临时文件 + os.replace() 原子保存首页抽取设置。"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(settings.model_dump(), ensure_ascii=False, indent=2)
    tmp_path: Optional[str] = None
    with _SETTINGS_LOCK:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(CONFIG_PATH.parent),
                prefix=f".{CONFIG_PATH.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(payload)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, CONFIG_PATH)
            tmp_path = None
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    logger.info("首页抽取配置已保存: %s", CONFIG_PATH)


def reset_frontpage_settings() -> tuple[FrontpageExtractionSettings, str]:
    """移除覆盖文件并恢复系统默认设置，确保重置响应与后续读取的 source 一致。"""
    with _SETTINGS_LOCK:
        try:
            CONFIG_PATH.unlink()
            logger.info("首页抽取配置覆盖文件已移除，恢复默认: %s", CONFIG_PATH)
        except FileNotFoundError:
            pass
        return FrontpageExtractionSettings(), "default"


def update_frontpage_settings(update_data: dict[str, Any]) -> FrontpageExtractionSettings:
    """按字段更新并原子保存设置。"""
    with _SETTINGS_LOCK:
        current, _ = load_frontpage_settings()
        merged = current.model_dump()
        merged.update(update_data)
        updated = FrontpageExtractionSettings(**merged)
        save_frontpage_settings(updated)
        return updated


def should_include_demo_records(settings: FrontpageExtractionSettings, real_record_count: int) -> bool:
    """根据策略和真实数据量判断是否展示 demo 病历。"""
    # 生产环境只展示真实病历；文件配置不能覆盖该安全边界。
    if _is_production_env():
        return False
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
