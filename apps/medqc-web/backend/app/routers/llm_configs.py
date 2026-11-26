from typing import Dict, Any, List, Optional
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone

from ..storage.memory import llm_configs
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id, StatusCode
from ..core.security import is_global_system_admin_principal, require_global_system_admin
from ..services.llm_config_loader import (
    SUPPORTED_PROVIDER_CODES,
    LLMConfigLoader,
    build_provider_runtime_config,
    build_adjudicator_runtime_config,
    build_local_model_runtime_config,
    get_default_provider_code,
    get_enabled_provider_codes,
    QC_USE_SELECTED_MODEL_KEY,
)
from ..services.qc_llm_client import SichuanQCLLMClient
from ..services.llm_task_roles import TASK_ROLES_KEY, normalize_task_roles, build_task_role_runtimes
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


def _resolve_model(model_code: str, provider_code: str = "") -> Dict[str, Any]:
    if provider_code in {"strata", "ollama"}:
        # 本地API的模型ID区分大小写，不套用云端别名目录。
        name = str(model_code or "").strip()
        return {"id": name, "model_code": name, "model_name": name, "description": ""}
    code = (model_code or "").lower()
    if code == "qwen3.6-35b-a3b":
        return {
            "id": code, "model_code": code, "model_name": "Qwen3.6-35B-A3B",
            "description": "Qwen3.6 35B A3B 模型",
        }
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
    try:
        enabled_provider_codes = set(get_enabled_provider_codes())
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail="llm_provider_not_enabled") from exc
    explicit_provider = str(payload.get("provider_code") or payload.get("provider_id") or "").strip().lower()
    if explicit_provider:
        provider_code = explicit_provider
    else:
        try:
            provider_code = get_default_provider_code()
        except ProviderConfigurationError as exc:
            raise HTTPException(status_code=422, detail="llm_provider_not_enabled") from exc
    if provider_code not in SUPPORTED_PROVIDER_CODES or provider_code not in enabled_provider_codes:
        raise HTTPException(status_code=422, detail="llm_provider_not_enabled")
    model_code = str(payload.get("model_code") or payload.get("model_id") or "").strip()
    return provider_code, model_code


def _validate_local_selection(provider_code: str, model_code: str, custom_parameters=None) -> Dict[str, Any]:
    """目录、保存和测试共用本地运行校验，不用页面状态代替后端约束。"""
    try:
        return build_local_model_runtime_config(provider_code, model_code, custom_parameters)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail=f"{provider_code}_configuration_unavailable") from exc


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
    row["model"] = _resolve_model(model_code, provider_code)
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
    custom_parameters = dict(payload.get("custom_parameters") or {})
    if provider_code == "alibaba":
        # 新保存的后台选型同时控制正式质控；旧配置不补写，保留原环境裁决覆盖。
        custom_parameters[QC_USE_SELECTED_MODEL_KEY] = True
    if provider_code in {"strata", "ollama"}:
        runtime = _validate_local_selection(provider_code, model_code, custom_parameters)
        model_code = model_code or str(runtime["model"])
    else:
        try:
            runtime = build_provider_runtime_config(provider_code, model_code=model_code or None,
                                                     custom_parameters=custom_parameters)
            build_adjudicator_runtime_config(runtime)
            model_code = model_code or str(runtime["model"])
        except ProviderConfigurationError as exc:
            raise HTTPException(status_code=422, detail="llm_configuration_unavailable") from exc
    try:
        if TASK_ROLES_KEY in custom_parameters:
            custom_parameters[TASK_ROLES_KEY] = normalize_task_roles(custom_parameters[TASK_ROLES_KEY])
        build_task_role_runtimes(runtime)
        build_task_role_runtimes(build_adjudicator_runtime_config(runtime))
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail="llm_task_role_configuration_unavailable") from exc
    supabase = get_supabase()
    cfg_name = payload.get("config_name") or "custom"

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
    model = _resolve_model(model_code, provider_code)
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


def _assert_allowed_target_user_id(target_user_id: Optional[str], current_user: dict) -> None:
    if target_user_id is None or not str(target_user_id).strip():
        return
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if str(target_user_id).strip() == actor_id:
        return
    if not is_global_system_admin_principal(
        _extract_roles(current_user),
        current_user.get("institute_id"),
    ):
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="禁止非全局管理员访问或修改其他用户的模型配置",
        )


@router.get("/configs")
async def list_configs(
    request: Request,
    user_id: Optional[str] = Query(default=None),
    system_config_user: dict = Depends(require_global_system_admin),
):
    _assert_allowed_target_user_id(user_id, system_config_user)
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
    system_config_user: dict = Depends(require_global_system_admin),
):
    _assert_allowed_target_user_id(user_id, system_config_user)
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
    admin_user: dict = Depends(require_global_system_admin),
):
    _assert_allowed_target_user_id(payload.get("user_id"), admin_user)
    result = await _save_config_internal(payload, request)
    return success_response(data=_project_config_row(result), trace_id=get_trace_id(request))


def _resolve_masked_key_configured(provider_code: str, row_has_key: bool = False) -> bool:
    """只返回脱敏后的密钥配置状态（布尔值），绝不解密或回显密钥原文。"""
    if row_has_key:
        return True
    code = str(provider_code or "").strip().lower()
    if not code:
        return False
    try:
        from ..core.settings import get_settings
        from ..services import llm_endpoint_settings as endpoint_settings

        settings = get_settings()
        if code in endpoint_settings.PROVIDERS:
            try:
                state = endpoint_settings.snapshot()
                saved = state.get("providers", {}).get(code)
                if saved is not None:
                    return bool(saved.get("key_ciphertext"))
            except Exception:
                pass
            _, dep_key = endpoint_settings.deployment_values(code, settings)
            return bool(dep_key)
        if code == "strata":
            return bool(getattr(settings, "STRATA_API_KEY", None))
    except Exception:
        return False
    return False


async def _load_fallback_default_row() -> Dict[str, Any]:
    """当默认推理服务被禁用或配置不可用时，只读提取存储或部署中的原始摘要供后台恢复切换。"""
    supabase = get_supabase()
    if supabase is not None:
        try:
            q = (
                supabase.table(_LLM_CONFIG_TABLE)
                .select("*")
                .eq("config_name", "default")
                .eq("is_active", True)
                .is_("user_id", None)  # type: ignore[attr-defined]
                .order("updated_at", desc=True)
                .limit(1)
            )
            resp = await async_execute(q)
            if resp.data:
                row = dict(resp.data[0])
                provider_code = str(row.get("provider_code") or row.get("provider_id") or "").strip().lower()
                model_code = str(row.get("model_code") or row.get("model_id") or "").strip()
                row_has_key = bool(row.get("api_key_encrypted") or row.get("api_key"))
                return {
                    "provider_code": provider_code,
                    "model_code": model_code,
                    "custom_parameters": dict(row.get("custom_parameters") or {}),
                    "api_key_configured": _resolve_masked_key_configured(provider_code, row_has_key),
                    "source": "database+env",
                }
        except Exception:
            logging.getLogger(__name__).warning("llm_default_fallback_db_read_failed")

    matched: List[Dict[str, Any]] = [
        item
        for item in llm_configs.values()
        if str(item.get("config_name") or "").strip() == "default" and item.get("user_id") is None
    ]
    if matched:
        matched.sort(
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )
        row = matched[0]
        provider_code = str(
            row.get("provider_code")
            or row.get("provider_id")
            or (
                row.get("provider", {}).get("provider_code")
                if isinstance(row.get("provider"), dict)
                else row.get("provider")
            )
            or ""
        ).strip().lower()
        model_code = str(
            row.get("model_code")
            or row.get("model_id")
            or (
                row.get("model", {}).get("model_code")
                if isinstance(row.get("model"), dict)
                else row.get("model")
            )
            or ""
        ).strip()
        row_has_key = bool(row.get("api_key_encrypted") or row.get("api_key"))
        return {
            "provider_code": provider_code,
            "model_code": model_code,
            "custom_parameters": dict(row.get("custom_parameters") or {}),
            "api_key_configured": _resolve_masked_key_configured(provider_code, row_has_key),
            "source": "memory+env",
        }

    from ..core.settings import get_settings

    settings = get_settings()
    provider_code = str(getattr(settings, "LLM_DEFAULT_PROVIDER", None) or "").strip().lower()
    if provider_code == "ollama":
        model_code = str(getattr(settings, "OLLAMA_MODEL", None) or "qwen2.5:7b-instruct").strip()
    elif provider_code == "strata":
        model_code = str(getattr(settings, "STRATA_MODEL", None) or "").strip()
    elif provider_code == "deepseek":
        model_code = str(getattr(settings, "LLM_MODEL", None) or "deepseek-v4-flash").strip()
    elif provider_code == "siliconflow":
        model_code = str(getattr(settings, "LLM_MODEL", None) or "Qwen/Qwen3.5-27B").strip()
    else:
        model_code = str(getattr(settings, "LLM_MODEL", None) or "qwen3.5-35b-a3b").strip()

    custom_params: Dict[str, Any] = {
        "enable_thinking": bool(getattr(settings, "LLM_ENABLE_THINKING", False)),
    }
    if custom_params["enable_thinking"] and getattr(settings, "LLM_THINKING_BUDGET", None) is not None:
        custom_params["thinking_budget"] = getattr(settings, "LLM_THINKING_BUDGET")

    return {
        "provider_code": provider_code,
        "model_code": model_code,
        "custom_parameters": custom_params,
        "api_key_configured": _resolve_masked_key_configured(provider_code),
        "source": "env",
    }


def _build_summary_payload(
    *,
    provider_code: str,
    model_code: str,
    custom_params: Dict[str, Any],
    source: str,
    readonly: bool,
    api_key_configured: bool = False,
    provider_unavailable: bool = False,
    provider_unavailable_reason: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        execution_concurrency = concurrency_from_custom_parameters(custom_params)
    except Exception:
        execution_concurrency = default_llm_execution_concurrency()
    try:
        task_roles = normalize_task_roles(custom_params.get(TASK_ROLES_KEY))
    except Exception:
        task_roles = normalize_task_roles(None)
    try:
        temperature = float(custom_params.get("temperature", 0.2))
    except (TypeError, ValueError):
        temperature = 0.2
    try:
        top_p = float(custom_params.get("top_p", 0.9))
    except (TypeError, ValueError):
        top_p = 0.9
    try:
        max_tokens = int(custom_params.get("max_tokens", 4000))
    except (TypeError, ValueError):
        max_tokens = 4000

    return {
        "provider_code": provider_code,
        "model_code": model_code,
        "api_key_configured": bool(api_key_configured),
        "custom_parameters": {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "enable_thinking": bool(custom_params.get("enable_thinking", False)),
            "thinking_budget": custom_params.get("thinking_budget"),
            "reasoning_effort": str(custom_params.get("reasoning_effort") or ""),
            TASK_ROLES_KEY: task_roles,
        },
        "execution_concurrency": execution_concurrency.as_dict(),
        "source": source,
        "readonly": readonly,
        "provider_unavailable": provider_unavailable,
        "provider_unavailable_reason": provider_unavailable_reason,
    }


@router.get("/configs/default/summary")
async def get_default_summary(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_global_system_admin),
):
    readonly = not is_global_system_admin_principal(
        _extract_roles(current_user),
        current_user.get("institute_id"),
    )
    try:
        runtime = await LLMConfigLoader.load_config(config_name="default", user_id=None)
        runtime = runtime or {}
        custom_params = runtime.get("custom_parameters") or {}
        provider_code = str(runtime.get("provider_code") or get_default_provider_code())
        model_code = str(runtime.get("model") or "")
        source = str(runtime.get("source") or "env")
        data = _build_summary_payload(
            provider_code=provider_code,
            model_code=model_code,
            custom_params=custom_params,
            source=source,
            readonly=readonly,
            api_key_configured=bool(runtime.get("api_key")),
            provider_unavailable=False,
            provider_unavailable_reason=None,
        )
    except ProviderConfigurationError as exc:
        logging.getLogger(__name__).warning("llm_default_summary_provider_unavailable")
        fallback = await _load_fallback_default_row()
        reason = str(exc).strip() or "provider_unavailable"
        data = _build_summary_payload(
            provider_code=fallback["provider_code"],
            model_code=fallback["model_code"],
            custom_params=fallback["custom_parameters"],
            source=fallback["source"],
            readonly=readonly,
            api_key_configured=fallback["api_key_configured"],
            provider_unavailable=True,
            provider_unavailable_reason=reason,
        )
    return success_response(
        data=data,
        trace_id=get_trace_id(request),
    )


@router.post("/configs/default/reset")
async def reset_default_config(
    request: Request,
    admin_user: dict = Depends(require_global_system_admin),
):
    del admin_user
    try:
        default_provider = get_default_provider_code()
        runtime = build_provider_runtime_config(default_provider)
    except ProviderConfigurationError as exc:
        logging.getLogger(__name__).warning("llm_default_reset_provider_unavailable")
        fallback = await _load_fallback_default_row()
        reason = str(exc).strip() or "provider_unavailable"
        data = _build_summary_payload(
            provider_code=fallback["provider_code"],
            model_code=fallback["model_code"],
            custom_params=fallback["custom_parameters"],
            source=fallback["source"],
            readonly=False,
            api_key_configured=fallback["api_key_configured"],
            provider_unavailable=True,
            provider_unavailable_reason=reason,
        )
        return success_response(
            data=data,
            message="默认推理服务当前不可用，请先重新启用或切换到其他已启用的推理服务",
            trace_id=get_trace_id(request),
        )
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
            "api_key_configured": bool(runtime.get("api_key")),
            "custom_parameters": {
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 4000,
            },
            "execution_concurrency": execution_concurrency.as_dict(),
            "source": "database+env",
            "readonly": False,
            "provider_unavailable": False,
            "provider_unavailable_reason": None,
        },
        message="已恢复默认配置",
        trace_id=get_trace_id(request),
    )


@router.post("/test")
async def test_config(
    request: Request,
    payload: Dict[str, Any],
    system_config_user: dict = Depends(require_global_system_admin),
):
    del system_config_user
    try:
        provider_code, model_code = _extract_provider_and_model_codes(payload)
        if provider_code in {"strata", "ollama"}:
            runtime = _validate_local_selection(provider_code, model_code, payload.get("custom_parameters"))
        else:
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
