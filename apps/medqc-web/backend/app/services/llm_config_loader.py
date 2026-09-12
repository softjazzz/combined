"""
LLM 配置加载服务
数据库仅保存 provider/model/custom_parameters；
敏感信息（endpoint / key）统一由 backend/.env 注入。
"""
from typing import Dict, Any, Optional
import logging
import os

from ..core.supabase_client import get_supabase
from ..core.settings import get_settings
from ..storage.memory import llm_configs

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDER_CODES = ("alibaba", "deepseek", "siliconflow", "ollama")
_USER_LLM_CONFIGS_TABLE_UNAVAILABLE = False


def get_enabled_provider_codes() -> tuple[str, ...]:
    """返回当前环境允许暴露和使用的 provider 列表。"""
    settings = get_settings()
    visible = tuple(code for code in settings.LLM_VISIBLE_PROVIDERS if code in SUPPORTED_PROVIDER_CODES)
    if visible:
        return visible

    env_name = str(settings.ENV or os.getenv("ENV") or "development").strip().lower()
    if env_name == "production":
        return ("alibaba", "deepseek", "ollama")
    return SUPPORTED_PROVIDER_CODES


def get_default_provider_code() -> str:
    """返回当前环境默认 provider。"""
    settings = get_settings()
    enabled = get_enabled_provider_codes()
    default_code = str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower()
    if default_code in enabled:
        return default_code
    env_name = str(settings.ENV or os.getenv("ENV") or "development").strip().lower()
    if env_name == "production" and "ollama" in enabled:
        return "ollama"
    if "alibaba" in enabled:
        return "alibaba"
    if "deepseek" in enabled:
        return "deepseek"
    return enabled[0]


def build_provider_runtime_config(
    provider_code: str,
    model_code: Optional[str] = None,
    custom_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """根据 provider/model 组合生成实际运行时配置。"""
    settings = get_settings()
    enabled = get_enabled_provider_codes()
    code = (provider_code or get_default_provider_code()).strip().lower()
    params = custom_parameters or {}

    if code not in enabled:
        fallback = get_default_provider_code()
        logger.warning("provider_code=%s 当前环境未启用，回退 %s", code, fallback)
        code = fallback

    if code == "deepseek":
        endpoint = str(
            settings.DEEPSEEK_API_ENDPOINT
            or (
                settings.LLM_API_ENDPOINT
                if str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower() == "deepseek"
                else ""
            )
            or ""
        ).strip()
        api_key = str(
            settings.DEEPSEEK_API_KEY
            or (
                settings.LLM_API_KEY
                if str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower() == "deepseek"
                else None
            )
            or ""
        ).strip() or None
        default_model = (
            settings.LLM_MODEL
            if str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower() == "deepseek"
            else "deepseek-v4-flash"
        )
        model = str(model_code or default_model or "deepseek-v4-flash").strip()
        provider_name = "DeepSeek"
    elif code == "siliconflow":
        endpoint = str(settings.SILICONFLOW_API_ENDPOINT or "").strip()
        api_key = str(settings.SILICONFLOW_API_KEY or "").strip() or None
        model = str(model_code or settings.LLM_MODEL or "Qwen/Qwen3.5-27B").strip()
        provider_name = "SiliconFlow"
    elif code == "ollama":
        endpoint = str(settings.OLLAMA_API_ENDPOINT or "").strip()
        api_key = str(settings.OLLAMA_API_KEY or "").strip() or None
        model = str(model_code or settings.OLLAMA_MODEL or "qwen2.5:7b-instruct").strip()
        provider_name = "内部 Ollama"
    else:
        code = "alibaba"
        endpoint = str(
            settings.DASHSCOPE_BASE_URL
            or (
                settings.LLM_API_ENDPOINT
                if str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower() == "alibaba"
                else ""
            )
            or ""
        ).strip()
        api_key = str(
            settings.DASHSCOPE_API_KEY
            or (
                settings.LLM_API_KEY
                if str(settings.LLM_DEFAULT_PROVIDER or "").strip().lower() == "alibaba"
                else None
            )
            or ""
        ).strip() or None
        model = str(model_code or settings.LLM_MODEL or "qwen3.5-35b-a3b").strip()
        provider_name = "阿里云百炼"

    return {
        "api_endpoint": endpoint or None,
        "api_key": api_key,
        "model": model,
        "provider_code": code,
        "provider_name": provider_name,
        "timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
        "allow_mock_when_unconfigured": settings.LLM_ALLOW_MOCK_WHEN_UNCONFIGURED,
        "custom_parameters": params,
    }


def build_adjudicator_runtime_config(
    base_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成正式质控二审运行时配置。

    二审默认可通过 LLM_ADJUDICATOR_MODEL 指向更稳的裁决模型；未配置时回退一审模型，
    保持既有部署兼容。
    """
    settings = get_settings()
    base = dict(base_config or build_provider_runtime_config(get_default_provider_code()))
    provider_code = str(base.get("provider_code") or get_default_provider_code()).strip().lower()
    adjudicator_model = str(settings.LLM_ADJUDICATOR_MODEL or "").strip()
    model_code = adjudicator_model or str(base.get("model") or settings.LLM_MODEL or "qwen3.5-35b-a3b").strip()
    runtime = build_provider_runtime_config(
        provider_code=provider_code,
        model_code=model_code,
        custom_parameters=base.get("custom_parameters", {}) or {},
    )
    source = "env_adjudicator_model" if adjudicator_model else "fallback_first_pass_model"
    runtime.update(
        {
            "source": source,
            "config_name": "adjudicator",
            "model_role": "adjudicator",
            "adjudicator_model_source": source,
            "first_pass_model": str(base.get("model") or ""),
        }
    )
    return runtime


class LLMConfigLoader:
    """LLM 配置加载器，支持数据库配置 + env 注入敏感参数。"""

    @staticmethod
    async def load_config(
        config_name: str = "default",
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        加载 LLM 配置

        优先级：
        1. 数据库中的用户/全局配置（provider/model/custom_parameters）
        2. .env 文件默认配置（阿里云）
        """
        supabase = get_supabase()

        global _USER_LLM_CONFIGS_TABLE_UNAVAILABLE
        if supabase is not None and not _USER_LLM_CONFIGS_TABLE_UNAVAILABLE:
            try:
                config = await LLMConfigLoader._load_from_database(supabase, config_name, user_id)
                if config:
                    logger.info(
                        "✅ 从数据库加载 LLM 配置成功: config_name=%s user_id=%s provider=%s model=%s",
                        config_name,
                        user_id,
                        config.get("provider_code"),
                        config.get("model"),
                    )
                    return config
            except Exception as exc:
                message = str(exc)
                if (
                    "user_llm_configs" in message
                    and (
                        "UndefinedTable" in message
                        or "does not exist" in message
                        or "不存在" in message
                        or "关系" in message
                    )
                ):
                    _USER_LLM_CONFIGS_TABLE_UNAVAILABLE = True
                    logger.warning(
                        "user_llm_configs 表不可用，本进程后续跳过数据库 LLM 配置查询，直接回退 env"
                    )
                else:
                    logger.warning("llm_config_database_load_failed fallback=env")

        memory_config = LLMConfigLoader._load_from_memory(config_name=config_name, user_id=user_id)
        if memory_config:
            logger.info(
                "✅ 从内存配置加载 LLM 配置成功: config_name=%s user_id=%s provider=%s model=%s",
                config_name,
                user_id,
                memory_config.get("provider_code"),
                memory_config.get("model"),
            )
            return memory_config

        config = LLMConfigLoader._load_from_env()
        logger.info(
            "✅ 从 .env 文件加载 LLM 配置: provider=%s model=%s",
            config.get("provider_code"),
            config.get("model"),
        )
        return config

    @staticmethod
    async def _load_from_database(
        supabase,
        config_name: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """从数据库加载 provider/model/custom_parameters，再由 env 注入敏感参数。"""
        try:
            q = (
                supabase.table("public.user_llm_configs")
                .select("*")
                .eq("config_name", config_name)
                .eq("is_active", True)
            )

            if user_id:
                q = q.eq("user_id", user_id)
            else:
                q = q.is_("user_id", None)  # type: ignore[attr-defined]

            resp = q.order("updated_at", desc=True).limit(1).execute()
            if not resp.data:
                logger.debug("数据库中未找到配置: config_name=%s user_id=%s", config_name, user_id)
                return None

            db_config = resp.data[0]
            provider_code = str(
                db_config.get("provider_code")
                or db_config.get("provider_id")
                or "alibaba"
            ).strip().lower()
            if provider_code not in SUPPORTED_PROVIDER_CODES:
                fallback = get_default_provider_code()
                logger.warning("配置中的 provider_code=%s 不受支持，回退 %s", provider_code, fallback)
                provider_code = fallback

            runtime = build_provider_runtime_config(
                provider_code=provider_code,
                model_code=str(
                    db_config.get("model_code")
                    or db_config.get("model_id")
                    or ""
                ).strip() or None,
                custom_parameters=db_config.get("custom_parameters", {}) or {},
            )
            runtime.update(
                {
                    "source": "database+env",
                    "config_id": db_config.get("id"),
                    "config_name": config_name,
                }
            )
            return runtime
        except Exception:
            logger.error("llm_config_database_query_failed")
            raise

    @staticmethod
    def _load_from_memory(
        config_name: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """在无 Supabase 或保存回退内存时，从内存配置加载运行时配置。"""
        matched: list[Dict[str, Any]] = []
        for item in llm_configs.values():
            if str(item.get("config_name") or "").strip() != config_name:
                continue
            item_user_id = item.get("user_id")
            if user_id is not None:
                if item_user_id != user_id:
                    continue
            elif item_user_id is not None:
                continue
            matched.append(item)

        if not matched:
            return None

        matched.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
        memory_config = matched[0]
        provider_code = str(
            memory_config.get("provider_code")
            or memory_config.get("provider_id")
            or (
                memory_config.get("provider", {}).get("provider_code")
                if isinstance(memory_config.get("provider"), dict)
                else memory_config.get("provider")
            )
            or "alibaba"
        ).strip().lower()
        if provider_code not in SUPPORTED_PROVIDER_CODES:
            provider_code = get_default_provider_code()

        model_code = str(
            memory_config.get("model_code")
            or memory_config.get("model_id")
            or (
                memory_config.get("model", {}).get("model_code")
                if isinstance(memory_config.get("model"), dict)
                else memory_config.get("model")
            )
            or ""
        ).strip() or None

        runtime = build_provider_runtime_config(
            provider_code=provider_code,
            model_code=model_code,
            custom_parameters=memory_config.get("custom_parameters", {}) or {},
        )
        runtime.update(
            {
                "source": "memory+env",
                "config_id": memory_config.get("id"),
                "config_name": config_name,
            }
        )
        return runtime

    @staticmethod
    def _load_from_env() -> Dict[str, Any]:
        """从 .env 文件加载默认配置。"""
        runtime = build_provider_runtime_config(get_default_provider_code())
        runtime.update(
            {
                "source": "env",
                "config_name": "env_default",
            }
        )
        return runtime

    @staticmethod
    async def reload_config_for_service(
        service,
        config_name: str = "default",
        user_id: Optional[str] = None,
    ) -> bool:
        """为服务重新加载配置。"""
        try:
            config = await LLMConfigLoader.load_config(config_name, user_id)
            if not config:
                logger.warning("无法加载配置: config_name=%s user_id=%s", config_name, user_id)
                return False

            if hasattr(service, "client"):
                client = service.client
                client.api_endpoint = config.get("api_endpoint")
                client.api_key = config.get("api_key")
                client.model = config.get("model") or client.model
                client.timeout_seconds = int(config.get("timeout_seconds") or client.timeout_seconds)
                client.allow_mock_when_unconfigured = bool(
                    config.get("allow_mock_when_unconfigured", client.allow_mock_when_unconfigured)
                )
                client.config_source = str(config.get("source") or "unknown")
                if hasattr(client, "provider_code"):
                    client.provider_code = str(config.get("provider_code") or "").strip().lower()

                custom_params = config.get("custom_parameters", {}) or {}
                if hasattr(client, "temperature"):
                    client.temperature = float(custom_params.get("temperature", 0.2))
                if hasattr(client, "top_p"):
                    client.top_p = float(custom_params.get("top_p", 0.9))
                if hasattr(client, "max_tokens"):
                    client.max_tokens = int(custom_params.get("max_tokens", 16384))
                if hasattr(client, "enable_thinking"):
                    client.enable_thinking = bool(custom_params.get("enable_thinking", False))
                if hasattr(client, "thinking_budget"):
                    client.thinking_budget = custom_params.get("thinking_budget")
                if hasattr(client, "reasoning_effort"):
                    client.reasoning_effort = str(custom_params.get("reasoning_effort") or "").strip().lower()

                logger.info(
                    "✅ 成功为服务重新加载配置: provider=%s model=%s source=%s",
                    config.get("provider_code"),
                    client.model,
                    client.config_source,
                )
                return True

            return False
        except Exception:
            logger.error("llm_config_reload_failed")
            return False
