from typing import Dict, Any, List, Optional
import logging
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime, timezone
import base64

from ..storage.memory import llm_configs
from ..core.supabase_client import get_supabase, async_execute
from ..core.settings import get_settings
from ..core.response import success_response, paginated_response, get_trace_id, StatusCode


router = APIRouter(prefix="/api/v1/llm", tags=["llm-configs"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_provider(provider_code: str) -> Dict[str, Any]:
    code = (provider_code or "").lower()
    if code in ("alibaba", "aliyun"):
        return {
            "id": "alibaba",
            "provider_code": "alibaba",
            "provider_name": "Aliyun DashScope",
            "base_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "request_format": "openai",
        }
    if code in ("openai",):
        return {
            "id": "openai",
            "provider_code": "openai",
            "provider_name": "OpenAI",
            "base_endpoint": "https://api.openai.com/v1",
            "request_format": "openai",
        }
    # fallback custom
    return {
        "id": code or "custom",
        "provider_code": code or "custom",
        "provider_name": code or "Custom",
        "base_endpoint": "",
        "request_format": "openai",
    }


def _resolve_model(model_code: str) -> Dict[str, Any]:
    code = (model_code or "").lower()
    if code in ("qwen2.5-14b-instruct", "qwen2.5-14b", "qwen2.5-14b-instruct".lower()):
        return {
            "id": "qwen2.5-14b-instruct",
            "model_code": "qwen2.5-14b-instruct",
            "model_name": "Qwen2.5-14B-Instruct",
            "description": "14B参数指令优化模型",
        }
    return {
        "id": code or "unknown",
        "model_code": code or "unknown",
        "model_name": model_code or "Unknown",
        "description": "",
    }


def _lookup_provider_and_model_ids(supabase, provider_code: str, model_code: str) -> Dict[str, Any]:
    """Resolve provider_id and model_id UUIDs from codes using Supabase tables.

    Falls back to None if not found so that insert/update will still succeed where columns are nullable.
    """
    provider_id = None
    model_id = None
    try:
        # llm_api_providers(id) by provider_code
        r = supabase.table("llm_api_providers").select("id").eq("provider_code", provider_code).limit(1).execute()
        if r and getattr(r, "data", None):
            provider_id = r.data[0].get("id")
            # llm_models(id) by model_code and provider_id
            try:
                rm = (
                    supabase
                    .table("llm_models")
                    .select("id")
                    .eq("model_code", model_code)
                    .eq("provider_id", provider_id)
                    .limit(1)
                    .execute()
                )
                if rm and getattr(rm, "data", None):
                    model_id = rm.data[0].get("id")
            except Exception:
                model_id = None
    except Exception:
        provider_id = None
        model_id = None
    return {"provider_id": provider_id, "model_id": model_id}


@router.get("/configs")
async def list_configs(request: Request, user_id: Optional[str] = Query(default=None)):
    supabase = get_supabase()

    def _fallback() -> Dict[str, Any]:
        items: List[Dict[str, Any]] = list(llm_configs.values())
        if user_id is not None:
            items = [c for c in items if c.get("user_id") == user_id]
        return success_response(
            data={"items": items, "total": len(items)},
            trace_id=get_trace_id(request)
        )

    if supabase is None:
        return _fallback()

    try:
        q = supabase.table("user_llm_configs").select("*, provider:llm_api_providers(*), model:llm_models(*)").eq("is_active", True)
        if user_id:
            q = q.eq("user_id", user_id)
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]
        resp = await async_execute(q)
        data = resp.data or []
        return success_response(
            data={"items": data, "total": len(data)},
            trace_id=get_trace_id(request)
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("Supabase list_configs 失败，回退内存配置: %s", exc)
        return _fallback()


@router.get("/configs/{config_name}")
async def get_config_by_name(request: Request, config_name: str, user_id: Optional[str] = Query(default=None)):
    supabase = get_supabase()

    def _fallback() -> Dict[str, Any]:
        for cfg in llm_configs.values():
            if cfg.get("config_name") == config_name and (user_id is None or cfg.get("user_id") == user_id):
                return success_response(data=cfg, trace_id=get_trace_id(request))
        return success_response(data=None, trace_id=get_trace_id(request))

    if supabase is None:
        return _fallback()

    try:
        q = supabase.table("user_llm_configs").select("*, provider:llm_api_providers(*), model:llm_models(*)").eq("config_name", config_name).eq("is_active", True)
        if user_id:
            q = q.eq("user_id", user_id)
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]
        resp = await async_execute(q.order("updated_at", {"ascending": False}).order("created_at", {"ascending": False}).limit(1))
        if resp.data:
            return success_response(data=resp.data[0], trace_id=get_trace_id(request))
        return success_response(data=None, trace_id=get_trace_id(request))
    except Exception as exc:
        logging.getLogger(__name__).warning("Supabase get_config_by_name 失败，回退内存配置: %s", exc)
        return _fallback()


@router.post("/configs")
async def save_config(request: Request, payload: Dict[str, Any]):
    supabase = get_supabase()
    provider_code = payload.get("provider_code") or payload.get("provider_id") or "alibaba"
    model_code = payload.get("model_code") or payload.get("model_id") or "qwen2.5-14b-instruct"
    cfg_name = payload.get("config_name") or "custom"

    provider = _resolve_provider(provider_code)
    model = _resolve_model(model_code)

    api_key_plain = payload.get("api_key") or ""
    api_key_encrypted = base64.b64encode(api_key_plain.encode("utf-8")).decode("utf-8") if api_key_plain else None

    now = _now_iso()

    def _save_in_memory() -> Dict[str, Any]:
        existing_id: Optional[str] = None
        for cid, cfg in llm_configs.items():
            if cfg.get("config_name") == cfg_name and cfg.get("user_id") == payload.get("user_id"):
                existing_id = cid
                break
        data = {
            "id": existing_id or (payload.get("id") or f"cfg-{len(llm_configs)+1:03d}"),
            "user_id": payload.get("user_id"),
            "config_name": cfg_name,
            "provider_code": provider["provider_code"],
            "model_code": model["model_code"],
            "provider": provider,
            "model": model,
            "api_key_encrypted": api_key_encrypted,
            "custom_endpoint": payload.get("custom_endpoint") or provider.get("base_endpoint", ""),
            "custom_parameters": payload.get("custom_parameters") or {},
            "is_active": True if payload.get("is_active") is None else bool(payload.get("is_active")),
            "updated_at": now,
        }
        if existing_id is None:
            data["created_at"] = now
        else:
            data["created_at"] = llm_configs[existing_id].get("created_at", now)
        llm_configs[data["id"]] = data
        return success_response(data=data, trace_id=get_trace_id(request))

    if supabase is None:
        return _save_in_memory()

    # Supabase 分支：按 config_name + user_id upsert
    # Resolve UUID foreign keys when Supabase is available
    resolved_ids = {"provider_id": None, "model_id": None}
    if supabase is not None:
        resolved_ids = _lookup_provider_and_model_ids(supabase, provider["provider_code"], model["model_code"])  # type: ignore[index]

    row = {
        "user_id": payload.get("user_id"),
        "config_name": cfg_name,
        # Only include UUID foreign keys when resolved; leave None otherwise
        "provider_id": resolved_ids.get("provider_id"),
        "model_id": resolved_ids.get("model_id"),
        "api_key_encrypted": api_key_encrypted,
        "custom_endpoint": payload.get("custom_endpoint") or provider.get("base_endpoint", ""),
        "custom_parameters": payload.get("custom_parameters") or {},
        "is_active": True if payload.get("is_active") is None else bool(payload.get("is_active")),
        "updated_at": now,
    }

    # 尝试查找现有
    try:
        q = supabase.table("user_llm_configs").select("id").eq("config_name", cfg_name)
        if row["user_id"]:
            q = q.eq("user_id", row["user_id"])
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]

        # 查询现有配置（404 不抛出异常）
        existing_data = None
        try:
            existing = await async_execute(q.limit(1))
            existing_data = existing.data if existing.data else None
        except Exception as e:
            # 404 是正常的，表示配置不存在
            if "404" not in str(e):
                raise
            existing_data = None

        if existing_data:
            cfg_id = existing_data[0]["id"]
            await async_execute(supabase.table("user_llm_configs").update(row).eq("id", cfg_id))
        else:
            row["created_at"] = now
            await async_execute(supabase.table("user_llm_configs").insert(row))

        # 读取完整行返回（不使用关联查询，避免 400 错误）
        q2 = supabase.table("user_llm_configs").select("*").eq("config_name", cfg_name)
        if row["user_id"]:
            q2 = q2.eq("user_id", row["user_id"])
        else:
            q2 = q2.is_("user_id", None)  # type: ignore[attr-defined]
        full = await async_execute(q2.order("updated_at", desc=True).limit(1))

        # 构建返回数据（包含 provider 和 model 信息）
        result_data = full.data[0] if full.data else None
        if result_data:
            result_data["provider"] = provider
            result_data["model"] = model
            result_data["provider_code"] = provider["provider_code"]
            result_data["model_code"] = model["model_code"]

        return success_response(
            data=result_data,
            trace_id=get_trace_id(request)
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("Supabase save_config 失败，回退内存配置: %s", exc)
        return _save_in_memory()
