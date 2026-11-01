"""0609 按调用点（role）选择裁决模型。

LLM_ROLE_MODELS="exam_finding_analysis=deepseek/deepseek-flash"：只有列出的调用点换用
指定 provider/model，其余调用沿用裁决模型。已知 role 的显式 Provider 身份、凭据或本地
端点错配均失败关闭；只有未配置 role 才沿用裁决模型。隐私脱敏由调用方包装保持不变。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 已评估可切换模型的调用点；新增前须先做同一标注集的判对率评估。
KNOWN_ROLES = frozenset({"exam_finding_analysis"})


def parse_role_models(raw: str | None) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        role, assignment_separator, spec = item.partition("=")
        provider, model_separator, model = spec.strip().partition("/")
        role, provider, model = role.strip(), provider.strip().lower(), model.strip()
        if role in KNOWN_ROLES and (
            not assignment_separator
            or not model_separator
            or not provider
            or not model
        ):
            from ..llm_dispatch.provider_profiles import ProviderConfigurationError

            raise ProviderConfigurationError("role model override is malformed")
        if role not in KNOWN_ROLES or not provider or not model:
            logger.warning("LLM_ROLE_MODELS 忽略无效项: role=%s", role or "-")
            continue
        result[role] = (provider, model)
    return result


def build_role_delegate(role: str) -> Any | None:
    """返回该调用点配置的裁决模型客户端；未配置或不可用时返回 None。"""
    from ...core.settings import get_settings
    from ..llm_config_loader import build_adjudicator_runtime_config, build_provider_runtime_config
    from ..llm_dispatch.provider_profiles import ProviderConfigurationError
    from ..qc_llm_client import SichuanQCLLMClient

    spec = parse_role_models(get_settings().LLM_ROLE_MODELS).get(role)
    if spec is None:
        return None
    provider, model = spec
    adjudicator = build_adjudicator_runtime_config()
    params = dict(adjudicator.get("custom_parameters") or {})
    if provider == "deepseek":
        # 评估（2026-10-19）按关闭 thinking 运行；DeepSeek 不走 DashScope 的 thinking 参数。
        params["enable_thinking"] = False
    runtime = build_provider_runtime_config(
        provider_code=provider,
        model_code=model,
        custom_parameters=params,
        dispatch_mode=adjudicator.get("dispatch_mode"),
        gateway_profile=(adjudicator.get("gateway_profile")
                         if provider == adjudicator.get("provider_code") and model == adjudicator.get("model")
                         else None),
    )
    if runtime.get("provider_code") != provider:
        raise ProviderConfigurationError("role provider override mismatch")
    if (
        runtime.get("dispatch_mode") == "direct"
        and not runtime.get("api_key")
        and provider not in {"ollama", "strata"}
    ):
        # 医院内网 OpenAI-compatible 服务允许不设 Provider key；endpoint/model
        # 已由各自 adapter 显式校验，不能因此回退到云端。
        raise ProviderConfigurationError("role provider credential is unavailable")
    runtime.update({"source": "env_role_model", "config_name": f"role:{role}", "model_role": "adjudicator"})
    return SichuanQCLLMClient(runtime)


def client_for_role(llm_client: Any, role: str) -> Any:
    """调用点取模型：客户端支持按 role 切换时使用切换结果，否则原样返回。"""
    selector = getattr(llm_client, "for_role", None)
    if not callable(selector):
        return llm_client
    try:
        return selector(role)
    except Exception as exc:  # noqa: BLE001 - 非身份类旧调用错误保持兼容
        from ..llm_dispatch.provider_profiles import ProviderConfigurationError

        if isinstance(exc, ProviderConfigurationError):
            raise
        logger.warning("LLM_ROLE_MODELS 切换失败，沿用裁决模型: role=%s", role)
        return llm_client
