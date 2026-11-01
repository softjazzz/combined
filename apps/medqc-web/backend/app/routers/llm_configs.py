from typing import Dict, Any, List, Optional
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone

from ..storage.memory import llm_configs
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id, StatusCode
from ..core.security import get_optional_user, require_roles
from ..services.llm_config_loader import (
    SUPPORTED_PROVIDER_CODES,
    LLMConfigLoader,
    build_provider_runtime_config,
    build_adjudicator_runtime_config,
    get_default_provider_code,
    get_enabled_provider_codes,
)
from ..services.qc_llm_client import SichuanQCLLMClient
from ..services.llm_dispatch.provider_profiles import ProviderConfigurationError
from ..services.llm_observability import llm_observation_context
from ..services.llm_execution_concurrency import (
    EXECUTION_CONCURRENCY_KEY,
    concurrency_from_custom_parameters,
    default_llm_execution_concurrency,
    resolve_llm_execution_concurrency,
)


router = APIRouter(prefix="/api/v1/llm", tags=["llm-configs"])

_SYSTEM_CONFIG_ROLES = ("admin", "sync_admin", "super_admin")
_LLM_CONFIG_TABLE = "public.user_llm_configs"


def _is_production_env() -> bool:
    return str(os.getenv("ENV") or "").strip().lower() in {"prod", "production"}


def _persistence_unavailable() -> HTTPException:
    return HTTPException(
        status_code=StatusCode.SERVICE_UNAVAILABLE,
        detail="llm_config_persistence_unavailable",
    )


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
    if code in ("deepseek",):
        return {
            "id": "deepseek",
            "provider_code": "deepseek",
            "provider_name": "DeepSeek 官方 API",
            "base_endpoint": "https://api.deepseek.com",
            "request_format": "openai",
        }
    if code in ("siliconflow",):
        return {
            "id": "siliconflow",
            "provider_code": "siliconflow",
            "provider_name": "SiliconFlow",
            "base_endpoint": "https://api.siliconflow.cn/v1",
            "request_format": "openai",
        }
    if code in ("ollama", "local"):
        return {
            "id": "ollama",
            "provider_code": "ollama",
            "provider_name": "内部 Ollama",
            "base_endpoint": "http://127.0.0.1:11434/v1",
            "request_format": "openai",
        }
    if code == "strata":
        return {"id": "strata", "provider_code": "strata", "provider_name": "本地 Strata",
                "base_endpoint": "", "request_format": "openai"}
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
    if code in ("qwen3.8-flash",):
        return {
            "id": "qwen3.8-flash",
            "model_code": "qwen3.8-flash",
            "model_name": "Qwen3.8 Flash",
            "description": "Qwen3.8 Flash 模型",
        }
    if code in ("qwen3.7-flash",):
        return {
            "id": "qwen3.7-flash",
            "model_code": "qwen3.7-flash",
            "model_name": "Qwen3.7 Flash",
            "description": "Qwen3.7 Flash 模型",
        }
    if code in ("qwen3.5-35b-a3b",):
        return {
            "id": "qwen3.5-35b-a3b",
            "model_code": "qwen3.5-35b-a3b",
            "model_name": "Qwen3.5-35B-A3B",
            "description": "Qwen3.5 35B A3B 模型",
        }
    if code in ("qwen2.5-14b-instruct", "qwen2.5-14b", "qwen2.5-14b-instruct".lower()):
        return {
            "id": "qwen2.5-14b-instruct",
            "model_code": "qwen2.5-14b-instruct",
            "model_name": "Qwen2.5-14B-Instruct",
            "description": "14B参数指令优化模型",
        }
    if code in ("qwen/qwen3.5-27b",):
        return {
            "id": "Qwen/Qwen3.5-27B",
            "model_code": "Qwen/Qwen3.5-27B",
            "model_name": "Qwen/Qwen3.5-27B",
            "description": "Qwen3.5 27B 模型",
        }
    if code in ("qwen/qwen3.5-9b",):
        return {
            "id": "Qwen/Qwen3.5-9B",
            "model_code": "Qwen/Qwen3.5-9B",
            "model_name": "Qwen/Qwen3.5-9B",
            "description": "Qwen3.5 9B 模型",
        }
    if code in ("qwen/qwen3.5-4b",):
        return {
            "id": "Qwen/Qwen3.5-4B",
            "model_code": "Qwen/Qwen3.5-4B",
            "model_name": "Qwen/Qwen3.5-4B",
            "description": "Qwen3.5 4B 模型",
        }
    if code in ("deepseek-chat",):
        return {
            "id": "deepseek-chat",
            "model_code": "deepseek-chat",
            "model_name": "DeepSeek Chat",
            "description": "DeepSeek 通用对话模型",
        }
    if code in ("deepseek-reasoner",):
        return {
            "id": "deepseek-reasoner",
            "model_code": "deepseek-reasoner",
            "model_name": "DeepSeek Reasoner",
            "description": "DeepSeek 推理模型",
        }
    if code in ("deepseek-v4-flash",):
        return {
            "id": "deepseek-v4-flash",
            "model_code": "deepseek-v4-flash",
            "model_name": "DeepSeek V4 Flash",
            "description": "DeepSeek V4 Flash 模型",
        }
    if code in ("deepseek-v4-pro",):
        return {
            "id": "deepseek-v4-pro",
            "model_code": "deepseek-v4-pro",
            "model_name": "DeepSeek V4 Pro",
            "description": "DeepSeek V4 Pro 模型",
        }
    return {
        "id": (model_code or "").strip() or "unknown",
        "model_code": (model_code or "").strip() or "unknown",
        "model_name": model_code or "Unknown",
        "description": "",
    }


def _extract_provider_and_model_codes(payload: Dict[str, Any]) -> tuple[str, str]:
    default_provider_code = get_default_provider_code()
    enabled_provider_codes = set(get_enabled_provider_codes())
    provider_code = str(payload.get("provider_code") or payload.get("provider_id") or default_provider_code).strip().lower()
    if provider_code not in SUPPORTED_PROVIDER_CODES or provider_code not in enabled_provider_codes:
        raise HTTPException(status_code=422, detail="llm_provider_not_enabled")
    model_code = str(payload.get("model_code") or payload.get("model_id") or "").strip()
    return provider_code, model_code


def _validate_strata_selection(model_code: str, custom_parameters=None) -> Dict[str, Any]:
    """后台本地选项必须使用统一准入，不把40个HTTP槽当成本地容量。"""
    try:
        runtime = build_provider_runtime_config("strata", model_code=model_code or None,
                                                custom_parameters=custom_parameters)
        if runtime.get("dispatch_mode") != "gateway":
            raise ProviderConfigurationError("strata_requires_gateway")
        build_adjudicator_runtime_config(runtime)
        return runtime
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail="strata_configuration_unavailable") from exc


def _extract_roles(current_user: Optional[Dict[str, Any]]) -> set[str]:
    if not current_user:
        return set()
    roles = current_user.get("roles")
    if isinstance(roles, list):
        return {str(role).strip().lower() for role in roles if str(role).strip()}
    role = current_user.get("role")
    if role:
        return {str(role).strip().lower()}
    return set()


def _normalize_config_row(row: Dict[str, Any]) -> Dict[str, Any]:
    provider_code = str(row.get("provider_code") or row.get("provider_id") or "").strip().lower()
    model_code = str(row.get("model_code") or row.get("model_id") or "").strip()
    row["provider"] = _resolve_provider(provider_code)
    row["model"] = _resolve_model(model_code)
    row["provider_code"] = row["provider"]["provider_code"]
    row["model_code"] = row["model"]["model_code"]
    return row


def _project_config_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """只返回配置工作台需要的字段，密钥及未知数据库列永不出接口。"""
    normalized = _normalize_config_row(dict(row))
    allowed_fields = (
        "id",
        "user_id",
        "config_name",
        "provider_id",
        "model_id",
        "provider_code",
        "model_code",
        "provider",
        "model",
        "custom_endpoint",
        "custom_parameters",
        "is_active",
        "created_at",
        "updated_at",
    )
    projected = {
        field: normalized.get(field)
        for field in allowed_fields
        if field in normalized
    }
    projected["api_key_configured"] = bool(
        normalized.get("api_key_encrypted") or normalized.get("api_key")
    )
    return projected


async def _save_config_internal(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    provider_code, model_code = _extract_provider_and_model_codes(payload)
    if provider_code == "strata":
        runtime = _validate_strata_selection(model_code, payload.get("custom_parameters"))
        model_code = model_code or str(runtime["model"])
    else:
        try:
            runtime = build_provider_runtime_config(provider_code, model_code=model_code or None,
                                                     custom_parameters=payload.get("custom_parameters"))
            build_adjudicator_runtime_config(runtime)
            model_code = model_code or str(runtime["model"])
        except ProviderConfigurationError as exc:
            raise HTTPException(status_code=422, detail="llm_configuration_unavailable") from exc
    supabase = get_supabase()
    cfg_name = payload.get("config_name") or "custom"

    custom_parameters = dict(payload.get("custom_parameters") or {})
    requested_concurrency = payload.get("execution_concurrency")
    if requested_concurrency is None:
        requested_concurrency = custom_parameters.get(EXECUTION_CONCURRENCY_KEY)
    try:
        execution_concurrency = resolve_llm_execution_concurrency(
            requested_concurrency
            if isinstance(requested_concurrency, dict)
            else None
        )
        if requested_concurrency is not None and not isinstance(requested_concurrency, dict):
            raise ValueError("execution_concurrency 必须是对象")
    except ValueError as exc:
        raise HTTPException(
            status_code=StatusCode.UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    custom_parameters[EXECUTION_CONCURRENCY_KEY] = execution_concurrency.as_dict()

    provider = _resolve_provider(provider_code)
    model = _resolve_model(model_code)
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
            "api_key_encrypted": None,
            "custom_endpoint": None,
            "custom_parameters": custom_parameters,
            "is_active": True if payload.get("is_active") is None else bool(payload.get("is_active")),
            "updated_at": now,
        }
        if existing_id is None:
            data["created_at"] = now
        else:
            data["created_at"] = llm_configs[existing_id].get("created_at", now)
        llm_configs[data["id"]] = data
        return data

    if supabase is None:
        if _is_production_env():
            raise _persistence_unavailable()
        return _save_in_memory()

    row = {
        "user_id": payload.get("user_id"),
        "config_name": cfg_name,
        "provider_code": provider["provider_code"],
        "model_code": model["model_code"],
        "api_key_encrypted": None,
        "custom_endpoint": None,
        "custom_parameters": custom_parameters,
        "is_active": True if payload.get("is_active") is None else bool(payload.get("is_active")),
        "updated_at": now,
    }

    try:
        q = supabase.table(_LLM_CONFIG_TABLE).select("id").eq("config_name", cfg_name)
        if row["user_id"]:
            q = q.eq("user_id", row["user_id"])
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]

        existing_data = None
        try:
            existing = await async_execute(q.limit(1))
            existing_data = existing.data if existing.data else None
        except Exception as e:
            if "404" not in str(e):
                raise
            existing_data = None

        if existing_data:
            cfg_id = existing_data[0]["id"]
            await async_execute(supabase.table(_LLM_CONFIG_TABLE).update(row).eq("id", cfg_id))
        else:
            row["created_at"] = now
            await async_execute(supabase.table(_LLM_CONFIG_TABLE).insert(row))

        q2 = supabase.table(_LLM_CONFIG_TABLE).select("*").eq("config_name", cfg_name)
        if row["user_id"]:
            q2 = q2.eq("user_id", row["user_id"])
        else:
            q2 = q2.is_("user_id", None)  # type: ignore[attr-defined]
        full = await async_execute(q2.order("updated_at", desc=True).limit(1))
        result_data = full.data[0] if full.data else None
        if result_data:
            result_data["provider"] = provider
            result_data["model"] = model
            result_data["provider_code"] = provider["provider_code"]
            result_data["model_code"] = model["model_code"]
        if result_data is None:
            if _is_production_env():
                raise RuntimeError("llm_config_readback_empty")
            return _save_in_memory()
        return result_data
    except Exception as exc:
        if _is_production_env():
            logging.getLogger(__name__).warning("llm_config_persistence_failed")
            raise _persistence_unavailable() from exc
        logging.getLogger(__name__).warning(
            "LLM config persistence failed; using development memory fallback"
        )
        return _save_in_memory()


@router.get("/configs")
async def list_configs(
    request: Request,
    user_id: Optional[str] = Query(default=None),
    system_config_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del system_config_user
    supabase = get_supabase()

    def _fallback() -> Dict[str, Any]:
        items: List[Dict[str, Any]] = list(llm_configs.values())
        if user_id is not None:
            items = [c for c in items if c.get("user_id") == user_id]
        items = [_project_config_row(item) for item in items]
        return success_response(
            data={"items": items, "total": len(items)},
            trace_id=get_trace_id(request)
        )

    if supabase is None:
        return _fallback()

    try:
        q = supabase.table(_LLM_CONFIG_TABLE).select("*").eq("is_active", True)
        if user_id:
            q = q.eq("user_id", user_id)
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]
        resp = await async_execute(q)
        data = []
        for item in (resp.data or []):
            data.append(_project_config_row(dict(item)))
        return success_response(
            data={"items": data, "total": len(data)},
            trace_id=get_trace_id(request)
        )
    except Exception:
        logging.getLogger(__name__).warning("llm_config_list_failed")
        return _fallback()


@router.get("/configs/{config_name}")
async def get_config_by_name(
    request: Request,
    config_name: str,
    user_id: Optional[str] = Query(default=None),
    system_config_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del system_config_user
    supabase = get_supabase()

    def _fallback() -> Dict[str, Any]:
        for cfg in llm_configs.values():
            if cfg.get("config_name") == config_name and (user_id is None or cfg.get("user_id") == user_id):
                return success_response(
                    data=_project_config_row(cfg),
                    trace_id=get_trace_id(request),
                )
        return success_response(data=None, trace_id=get_trace_id(request))

    if supabase is None:
        return _fallback()

    try:
        q = supabase.table(_LLM_CONFIG_TABLE).select("*").eq("config_name", config_name).eq("is_active", True)
        if user_id:
            q = q.eq("user_id", user_id)
        else:
            q = q.is_("user_id", None)  # type: ignore[attr-defined]
        resp = await async_execute(q.order("updated_at", {"ascending": False}).order("created_at", {"ascending": False}).limit(1))
        if resp.data:
            row = _project_config_row(dict(resp.data[0]))
            return success_response(data=row, trace_id=get_trace_id(request))
        return success_response(data=None, trace_id=get_trace_id(request))
    except Exception:
        logging.getLogger(__name__).warning("llm_config_read_failed")
        return _fallback()


@router.post("/configs")
async def save_config(
    request: Request,
    payload: Dict[str, Any],
    admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del admin_user
    result = await _save_config_internal(payload, request)
    return success_response(data=result, trace_id=get_trace_id(request))


@router.get("/configs/default/summary")
async def get_default_summary(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    runtime = await LLMConfigLoader.load_config(config_name="default", user_id=None)
    runtime = runtime or {}
    custom_params = runtime.get("custom_parameters") or {}
    execution_concurrency = concurrency_from_custom_parameters(custom_params)
    source = str(runtime.get("source") or "env")
    readonly = not _extract_roles(current_user).intersection(_SYSTEM_CONFIG_ROLES)
    return success_response(
        data={
            "provider_code": str(runtime.get("provider_code") or get_default_provider_code()),
            "model_code": str(runtime.get("model") or ""),
            "custom_parameters": {
                "temperature": float(custom_params.get("temperature", 0.2)),
                "top_p": float(custom_params.get("top_p", 0.9)),
                "max_tokens": int(custom_params.get("max_tokens", 4000)),
                "enable_thinking": bool(custom_params.get("enable_thinking", False)),
                "thinking_budget": custom_params.get("thinking_budget"),
                "reasoning_effort": str(custom_params.get("reasoning_effort") or ""),
            },
            "execution_concurrency": execution_concurrency.as_dict(),
            "source": source,
            "readonly": readonly,
        },
        trace_id=get_trace_id(request),
    )


@router.post("/configs/default/reset")
async def reset_default_config(
    request: Request,
    admin_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del admin_user
    default_provider = get_default_provider_code()
    runtime = build_provider_runtime_config(default_provider)
    execution_concurrency = default_llm_execution_concurrency()
    payload = {
        "config_name": "default",
        "user_id": None,
        "provider_code": default_provider,
        "model_code": str(runtime.get("model") or ""),
        "custom_parameters": {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 4000,
            EXECUTION_CONCURRENCY_KEY: execution_concurrency.as_dict(),
        },
        "execution_concurrency": execution_concurrency.as_dict(),
        "is_active": True,
    }
    await _save_config_internal(payload, request)
    return success_response(
        data={
            "provider_code": payload["provider_code"],
            "model_code": payload["model_code"],
            "custom_parameters": {
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 4000,
            },
            "execution_concurrency": execution_concurrency.as_dict(),
            "source": "database+env",
            "readonly": False,
        },
        message="已恢复默认配置",
        trace_id=get_trace_id(request),
    )


@router.post("/test")
async def test_config(
    request: Request,
    payload: Dict[str, Any],
    system_config_user: dict = Depends(require_roles(*_SYSTEM_CONFIG_ROLES)),
):
    del system_config_user
    try:
        provider_code, model_code = _extract_provider_and_model_codes(payload)
        if provider_code == "strata":
            _validate_strata_selection(model_code, payload.get("custom_parameters"))
        runtime = build_provider_runtime_config(
            provider_code=provider_code,
            model_code=model_code or None,
            custom_parameters=payload.get("custom_parameters") or {},
        )
        client = SichuanQCLLMClient(
            {
                **runtime,
                "source": "test",
            }
        )

        if not client.api_endpoint:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="llm_connection_test_not_configured",
            )
        if client.dispatch_mode == "direct" and provider_code in ("alibaba", "deepseek", "siliconflow") and not client.api_key:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="llm_connection_test_not_configured",
            )

        with llm_observation_context(
            business_scene="llm_config_probe",
            root_job_id=get_trace_id(request),
            executor_key="llm_config_probe",
        ):
            result = await client.generate("请只返回“pong”，不要输出其他内容。")
        content = str(
            ((result.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
        return success_response(
            data={
                "provider_code": runtime.get("provider_code"),
                "model": client.model,
                "api_endpoint": client.api_endpoint,
                "content_preview": content[:120],
                "stats": client.stats(),
            },
            message="连接测试成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logging.getLogger(__name__).warning("llm_connection_test_failed")
        raise HTTPException(
            status_code=StatusCode.BAD_GATEWAY,
            detail="llm_connection_test_failed",
        ) from exc
