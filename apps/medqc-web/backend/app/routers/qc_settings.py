"""
质控引擎配置 API

提供 GET/PUT 端点，让前端可以查看和修改质控引擎的高级配置。
配置持久化到本地 JSON 文件（无需数据库）。
"""
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.security import require_global_system_admin

logger = logging.getLogger(__name__)

_SYSTEM_CONFIG_ROLES = ("admin", "sync_admin", "super_admin")
_SETTINGS_LOCK = threading.RLock()

router = APIRouter(
    prefix="/api/v1/qc/settings",
    tags=["QC Settings"],
    dependencies=[Depends(require_global_system_admin)],
)

# 配置文件路径
CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "qc_settings.json"


class QCSettingsModel(BaseModel):
    """质控引擎配置"""

    # ── Prompt 策略 ──
    prompt_mode: str = Field(
        default="plan_a",
        description="Prompt 模式：current（精简）/ plan_a（标准，推荐）/ plan_c（详细）",
    )

    # ── 分段引擎 ──
    max_rules_per_batch: int = Field(
        default=15, ge=3, le=50,
        description="每批发给 LLM 的最大规则数（3-50）",
    )
    max_concurrency: int = Field(
        default=3, ge=1, le=10,
        description="LLM 最大并发调用数（1-10）",
    )

    # ── LLM 参数 ──
    temperature: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description="LLM 温度参数（0.0-1.0，越低越确定）",
    )
    max_tokens: int = Field(
        default=16384, ge=1024, le=65536,
        description="LLM 最大输出 token 数",
    )


class QCSettingsResponse(BaseModel):
    """配置响应"""
    settings: QCSettingsModel
    source: str = "default"  # default / file


def _load_settings() -> tuple[QCSettingsModel, str]:
    """加载配置：优先从文件，否则返回默认值"""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return QCSettingsModel(**data), "file"
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，使用默认值")
    return QCSettingsModel(), "default"


def _save_settings(settings: QCSettingsModel) -> None:
    """使用同目录临时文件 + os.replace() 原子保存配置，防止并发或崩溃写坏文件。"""
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
    logger.info(f"质控配置已保存: {CONFIG_PATH}")


@router.get("", response_model=QCSettingsResponse)
async def get_qc_settings(
    _admin_user: dict = Depends(require_global_system_admin),
):
    """获取当前质控引擎配置"""
    del _admin_user
    settings, source = _load_settings()
    return QCSettingsResponse(settings=settings, source=source)


class QCSettingsUpdateRequest(BaseModel):
    """更新请求（所有字段可选，只更新传入的字段）"""
    prompt_mode: Optional[str] = None
    max_rules_per_batch: Optional[int] = Field(default=None, ge=3, le=50)
    max_concurrency: Optional[int] = Field(default=None, ge=1, le=10)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1024, le=65536)


@router.put("", response_model=QCSettingsResponse)
async def update_qc_settings(
    req: QCSettingsUpdateRequest,
    _admin_user: dict = Depends(require_global_system_admin),
):
    """更新质控引擎配置（部分更新）"""
    del _admin_user
    with _SETTINGS_LOCK:
        # 加载当前配置
        current, _ = _load_settings()
        current_dict = current.model_dump()

        # 合并更新
        update_data = req.model_dump(exclude_none=True)
        current_dict.update(update_data)

        # 验证并原子保存
        updated = QCSettingsModel(**current_dict)
        _save_settings(updated)

    logger.info(f"质控配置已更新: {update_data}")
    return QCSettingsResponse(settings=updated, source="file")


@router.post("/reset", response_model=QCSettingsResponse)
async def reset_qc_settings(
    _admin_user: dict = Depends(require_global_system_admin),
):
    """重置质控引擎配置为默认值"""
    del _admin_user
    with _SETTINGS_LOCK:
        default = QCSettingsModel()
        _save_settings(default)
    logger.info("质控配置已重置为默认值")
    return QCSettingsResponse(settings=default, source="default")
