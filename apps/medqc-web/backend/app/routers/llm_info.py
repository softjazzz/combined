from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import require_roles
from ..services.llm_config_loader import get_enabled_provider_codes, SUPPORTED_PROVIDER_CODES
from ..core.settings import get_settings

router = APIRouter(prefix="/api/v1/llm", tags=["llm-info"])

_SYSTEM_CONFIG_ROLES = ("admin", "sync_admin", "super_admin")
SUPPORTED_PROVIDERS = SUPPORTED_PROVIDER_CODES
CUSTOM_MODELS_FILE = Path(__file__).resolve().parents[2] / "data" / "llm_custom_models.json"


class CustomModelPayload(BaseModel):
    provider_code: str = Field(..., description="服务商编码：alibaba/deepseek/siliconflow/ollama/strata")
    model_code: str = Field(..., description="模型编码（也是模型名称）")
    model_name: str | None = Field(default=None, description="模型展示名，默认同 model_code")


def _normalize_provider_code(provider_code: str | None) -> str:
    return str(provider_code or "").strip().lower()


def _base_models() -> list[dict[str, Any]]:
    models = [
        {"provider": "alibaba", "id": "qwen-plus", "model_code": "qwen-plus", "model_name": "Qwen-Plus", "is_custom": False},
        {"provider": "alibaba", "id": "qwen3.7-flash", "model_code": "qwen3.7-flash", "model_name": "Qwen3.7 Flash", "is_custom": False},
        {"provider": "alibaba", "id": "qwen3.8-flash", "model_code": "qwen3.8-flash", "model_name": "Qwen3.8 Flash", "is_custom": False},
        {"provider": "alibaba", "id": "qwen3.5-35b-a3b", "model_code": "qwen3.5-35b-a3b", "model_name": "Qwen3.5-35B-A3B", "is_custom": False},
        {"provider": "deepseek", "id": "deepseek-chat", "model_code": "deepseek-chat", "model_name": "DeepSeek Chat", "is_custom": False},
        {"provider": "deepseek", "id": "deepseek-reasoner", "model_code": "deepseek-reasoner", "model_name": "DeepSeek Reasoner", "is_custom": False},
        {"provider": "deepseek", "id": "deepseek-v4-flash", "model_code": "deepseek-v4-flash", "model_name": "DeepSeek V4 Flash", "is_custom": False},
        {"provider": "deepseek", "id": "deepseek-v4-pro", "model_code": "deepseek-v4-pro", "model_name": "DeepSeek V4 Pro", "is_custom": False},
        {"provider": "siliconflow", "id": "Qwen/Qwen3.5-27B", "model_code": "Qwen/Qwen3.5-27B", "model_name": "Qwen/Qwen3.5-27B", "is_custom": False},
        {"provider": "siliconflow", "id": "Qwen/Qwen3.5-9B", "model_code": "Qwen/Qwen3.5-9B", "model_name": "Qwen/Qwen3.5-9B", "is_custom": False},
        {"provider": "siliconflow", "id": "Qwen/Qwen3.5-4B", "model_code": "Qwen/Qwen3.5-4B", "model_name": "Qwen/Qwen3.5-4B", "is_custom": False},
        {"provider": "ollama", "id": "qwen2.5:7b-instruct", "model_code": "qwen2.5:7b-instruct", "model_name": "qwen2.5:7b-instruct", "is_custom": False},
    ]
    # 本地模型ID取部署真实值，不猜测量化模型的API名称。
    model = str(get_settings().STRATA_MODEL or "").strip()
    if model:
        models.append({"provider": "strata", "id": model, "model_code": model,
                       "model_name": model, "is_custom": False})
    # 多模型Gateway部署可显式登记每个模型自己的profile，模型名称原样展示。
    existing = {(row["provider"], row["model_code"]) for row in models}
    for provider, profiles in get_settings().LLM_GATEWAY_PROFILES.items():
        if isinstance(profiles, dict):
            for name in profiles:
                if (provider, name) not in existing:
                    models.append({"provider": provider, "id": name, "model_code": name,
                                   "model_name": name, "is_custom": False})
    return models


def _load_custom_models() -> dict[str, list[dict[str, Any]]]:
    if not CUSTOM_MODELS_FILE.exists():
        return {}
    try:
        raw = json.loads(CUSTOM_MODELS_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[dict[str, Any]]] = {}
        for provider_code, items in raw.items():
            p = _normalize_provider_code(provider_code)
            if p not in SUPPORTED_PROVIDERS or not isinstance(items, list):
                continue
            normalized: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                model_code = str(item.get("model_code") or "").strip()
                if not model_code:
                    continue
                normalized.append(
                    {
                        "provider": p,
                        "id": model_code,
                        "model_code": model_code,
                        "model_name": str(item.get("model_name") or model_code).strip() or model_code,
                        "is_custom": True,
                    }
                )
            if normalized:
                result[p] = normalized
        return result
    except Exception:
        return {}


def _save_custom_models(data: dict[str, list[dict[str, Any]]]) -> None:
    CUSTOM_MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_MODELS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/providers")
async def providers(request: Request):
    """获取 LLM 提供商列表"""
    enabled_provider_codes = set(get_enabled_provider_codes())
    provider_items = [
        {"id": "alibaba", "provider_name": "阿里云百炼", "provider_code": "alibaba"},
        {"id": "deepseek", "provider_name": "DeepSeek 官方 API", "provider_code": "deepseek"},
        {"id": "siliconflow", "provider_name": "SiliconFlow", "provider_code": "siliconflow"},
        {"id": "ollama", "provider_name": "内部 Ollama", "provider_code": "ollama"},
        {"id": "strata", "provider_name": "本地 Strata", "provider_code": "strata"},
    ]
    provider_items = [
        item
        for item in provider_items
        if str(item.get("provider_code") or "").strip().lower() in enabled_provider_codes
    ]
    return success_response(
        data=provider_items,
        message="获取提供商列表成功",
        trace_id=get_trace_id(request),
    )


@router.get("/models")
async def models(request: Request, provider_id: str | None = Query(default=None)):
    """获取 LLM 模型列表"""
    enabled_provider_codes = set(get_enabled_provider_codes())
    model_items = [
        item
        for item in _base_models()
        if str(item.get("provider") or "").strip().lower() in enabled_provider_codes
    ]

    custom_models = _load_custom_models()
    for provider_code, items in custom_models.items():
        if provider_code not in enabled_provider_codes:
            continue
        existing_codes = {
            str(item.get("model_code") or "").strip()
            for item in model_items
            if _normalize_provider_code(item.get("provider")) == provider_code
        }
        for item in items:
            model_code = str(item.get("model_code") or "").strip()
            if not model_code or model_code in existing_codes:
                continue
            model_items.append(item)
            existing_codes.add(model_code)

    # provider_id 同时兼容 provider code / provider id（前端历史参数）
    if provider_id:
        provider_code = _normalize_provider_code(provider_id)
        model_items = [
            item
            for item in model_items
            if _normalize_provider_code(item.get("provider")) == provider_code
        ]

    return success_response(
        data=model_items,
        message="获取模型列表成功",
        trace_id=get_trace_id(request),
    )


@router.post("/models/custom")
async def add_custom_model(
    request: Request,
    payload: CustomModelPayload,
    admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del admin_user
    provider_code = _normalize_provider_code(payload.provider_code)
    if provider_code not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 provider_code: {provider_code}")
    if provider_code not in set(get_enabled_provider_codes()):
        raise HTTPException(status_code=400, detail=f"当前环境未启用 provider: {provider_code}")

    model_code = str(payload.model_code or "").strip()
    model_name = str(payload.model_name or model_code).strip() or model_code
    if not model_code:
        raise HTTPException(status_code=400, detail="model_code 不能为空")

    builtin = [
        item
        for item in _base_models()
        if _normalize_provider_code(item.get("provider")) == provider_code
    ]
    if any(str(item.get("model_code") or "").strip() == model_code for item in builtin):
        raise HTTPException(status_code=409, detail=f"模型已存在: {model_code}")

    raw = _load_custom_models()
    provider_items = list(raw.get(provider_code) or [])
    if any(str(item.get("model_code") or "").strip() == model_code for item in provider_items):
        raise HTTPException(status_code=409, detail=f"模型已存在: {model_code}")

    provider_items.append(
        {
            "provider": provider_code,
            "id": model_code,
            "model_code": model_code,
            "model_name": model_name,
            "is_custom": True,
        }
    )
    raw[provider_code] = provider_items
    _save_custom_models(raw)

    return success_response(
        data={"provider_code": provider_code, "model_code": model_code, "model_name": model_name},
        message="添加自定义模型成功",
        trace_id=get_trace_id(request),
    )


@router.delete("/models/custom")
async def delete_custom_model(
    request: Request,
    provider_code: str = Query(...),
    model_code: str = Query(...),
    admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del admin_user
    p = _normalize_provider_code(provider_code)
    m = str(model_code or "").strip()
    if p not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"不支持的 provider_code: {p}")
    if not m:
        raise HTTPException(status_code=400, detail="model_code 不能为空")

    raw = _load_custom_models()
    provider_items = list(raw.get(p) or [])
    original_size = len(provider_items)
    provider_items = [
        item
        for item in provider_items
        if str(item.get("model_code") or "").strip() != m
    ]
    if len(provider_items) == original_size:
        raise HTTPException(status_code=404, detail=f"未找到自定义模型: {m}")

    if provider_items:
        raw[p] = provider_items
    else:
        raw.pop(p, None)
    _save_custom_models(raw)

    return success_response(
        data={"provider_code": p, "model_code": m},
        message="删除自定义模型成功",
        trace_id=get_trace_id(request),
    )
