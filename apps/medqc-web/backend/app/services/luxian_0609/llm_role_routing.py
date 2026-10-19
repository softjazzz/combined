"""0609 按调用点（role）选择裁决模型。

LLM_ROLE_MODELS="exam_finding_analysis=deepseek/deepseek-flash"：只有列出的调用点换用
指定 provider/model，其余调用沿用裁决模型。provider 未启用、格式不合法或 role 未登记时
记录告警并沿用裁决模型，不因配置错误中断质控。隐私脱敏由调用方的隐私包装保持不变。
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
        role, _, spec = item.partition("=")
        provider, _, model = spec.strip().partition("/")
        role, provider, model = role.strip(), provider.strip().lower(), model.strip()
        if role not in KNOWN_ROLES or not provider or not model:
            logger.warning("LLM_ROLE_MODELS 忽略无效项: role=%s", role or "-")
            continue
        result[role] = (provider, model)
    return result


def build_role_delegate(role: str) -> Any | None:
    """返回该调用点配置的裁决模型客户端；未配置或不可用时返回 None。"""
    from ...core.settings import get_settings
    from ..llm_config_loader import build_adjudicator_runtime_config, build_provider_runtime_config
    from ..qc_llm_client import SichuanQCLLMClient

    spec = parse_role_models(get_settings().LLM_ROLE_MODELS).get(role)
    if spec is None:
        return None
    provider, model = spec
    params = dict(build_adjudicator_runtime_config().get("custom_parameters") or {})
    if provider == "deepseek":
        # 评估（2026-10-19）按关闭 thinking 运行；DeepSeek 不走 DashScope 的 thinking 参数。
        params["enable_thinking"] = False
    runtime = build_provider_runtime_config(provider_code=provider, model_code=model, custom_parameters=params)
    if runtime.get("provider_code") != provider or not runtime.get("api_key"):
        logger.warning("LLM_ROLE_MODELS 调用点模型不可用，沿用裁决模型: role=%s provider=%s", role, provider)
        return None
    runtime.update({"source": "env_role_model", "config_name": f"role:{role}", "model_role": "adjudicator"})
    return SichuanQCLLMClient(runtime)


def client_for_role(llm_client: Any, role: str) -> Any:
    """调用点取模型：客户端支持按 role 切换时使用切换结果，否则原样返回。"""
    selector = getattr(llm_client, "for_role", None)
    if not callable(selector):
        return llm_client
    try:
        return selector(role)
    except Exception:  # noqa: BLE001 - 配置异常不应中断质控
        logger.warning("LLM_ROLE_MODELS 切换失败，沿用裁决模型: role=%s", role)
        return llm_client
