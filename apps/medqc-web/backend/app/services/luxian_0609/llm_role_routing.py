"""0609 按调用点（role）选择裁决模型。

LLM_ROLE_MODELS="exam_finding_analysis=deepseek/deepseek-flash"：只有列出的调用点换用
指定 provider/model，其余调用沿用裁决模型。已知 role 的显式 Provider 身份、凭据或本地
端点错配均失败关闭；只有未配置 role 才沿用裁决模型。隐私脱敏由调用方包装保持不变。
"""

from __future__ import annotations

import logging
from copy import deepcopy
import hashlib
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


from ..llm_endpoint_settings import pinned_runtime


@pinned_runtime
def capture_legacy_role_runtimes(base: dict) -> dict:
    """接纳客户端时固定旧调用点配置，后续不再读取进程默认模型与参数。"""
    from ...core.settings import get_settings
    from ..llm_config_loader import build_provider_runtime_config
    from ..llm_dispatch.provider_profiles import ProviderConfigurationError
    settings = get_settings()
    result = {}
    for role, (provider, model) in parse_role_models(settings.LLM_ROLE_MODELS).items():
        if base.get("provider_code") in {"ollama", "strata", "local_openai"} and provider not in {"ollama", "strata", "local_openai"}:
            raise ProviderConfigurationError("local legacy roles cannot route to cloud")
        params = deepcopy(base.get("custom_parameters") or {})
        if provider == "deepseek":
            params["enable_thinking"] = False
        runtime = build_provider_runtime_config(provider_code=provider, model_code=model,
            custom_parameters=params, dispatch_mode=base.get("dispatch_mode"),
            gateway_profile=base.get("gateway_profile") if (provider, model) == (base.get("provider_code"), base.get("model")) else None)
        if runtime.get("provider_code") != provider:
            raise ProviderConfigurationError("role provider override mismatch")
        if runtime.get("dispatch_mode") == "direct" and not runtime.get("api_key") and provider not in {"ollama", "strata"}:
            raise ProviderConfigurationError("role provider credential is unavailable")
        if runtime.get("dispatch_mode") == "gateway":
            runtime["gateway_endpoint_sha256"] = hashlib.sha256(str(settings.LLM_GATEWAY_URL or "").strip().rstrip('/').encode()).hexdigest()
        runtime.update(source="frozen_legacy_role", model_role="adjudicator", allow_mock_when_unconfigured=False,
            legacy_role_runtimes={}, task_role_runtimes={}, task_role_identity=None)
        result[role] = runtime
    return result


def legacy_role_identity(runtimes):
    """任务与冻结仅登记旧路由有效身份；凭据和地址原文不入结果。"""
    fields = ("temperature", "top_p", "top_k", "presence_penalty", "frequency_penalty",
              "repetition_penalty", "max_tokens", "enable_thinking", "thinking_budget", "reasoning_effort")
    return {role: {**({"endpoint_config_revision": value["endpoint_config_revision"]} if value.get("endpoint_config_revision") else {}),
        "provider": value["provider_code"], "model": value["model"],
        "endpoint_sha256": hashlib.sha256(str(value.get("api_endpoint") or "").encode()).hexdigest(),
        "dispatch_mode": value.get("dispatch_mode", "direct"), "gateway_profile": value.get("gateway_profile"),
        "gateway_endpoint_sha256": value.get("gateway_endpoint_sha256"),
        "parameters": {key: (value.get("custom_parameters") or {}).get(key) for key in fields}}
        for role, value in sorted(runtimes.items())}


def build_role_delegate(role: str) -> Any | None:
    """无正式客户端的兼容调用仍检查本地到云端边界；正式任务使用已冻结路由。"""
    from ..llm_config_loader import build_adjudicator_runtime_config
    from ..qc_llm_client import SichuanQCLLMClient
    runtime = capture_legacy_role_runtimes(build_adjudicator_runtime_config()).get(role)
    return SichuanQCLLMClient(runtime) if runtime else None


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
