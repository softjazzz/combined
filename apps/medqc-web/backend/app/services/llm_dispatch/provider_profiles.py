"""Provider 与受控 Gateway profile 的本地路由约束。"""

from __future__ import annotations

import re
from typing import Any


LEGACY_CLOUD_PROVIDER_CODES = frozenset({"alibaba", "deepseek", "siliconflow"})
LOCAL_PROVIDER_CODES = frozenset({"ollama", "strata", "local_openai"})
SUPPORTED_PROVIDER_CODES = tuple(
    sorted(LEGACY_CLOUD_PROVIDER_CODES | LOCAL_PROVIDER_CODES)
)
_PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class ProviderConfigurationError(ValueError):
    """不得通过切换到其他 Provider 恢复的配置错误。"""

    fail_closed = True


def normalize_dispatch_mode(value: Any) -> str:
    mode = str(value or "direct").strip().lower()
    if mode not in {"direct", "gateway"}:
        raise ProviderConfigurationError("unsupported LLM dispatch mode")
    return mode


def validate_provider_code(provider_code: Any) -> str:
    code = str(provider_code or "").strip().lower()
    if code not in SUPPORTED_PROVIDER_CODES:
        raise ProviderConfigurationError("unsupported LLM provider")
    return code


def strata_is_explicitly_configured(settings: Any) -> bool:
    return bool(
        str(getattr(settings, "STRATA_API_ENDPOINT", "") or "").strip()
        and str(getattr(settings, "STRATA_MODEL", "") or "").strip()
    )


def validate_gateway_profile(*, profile: Any, provider_code: Any) -> str:
    """校验 profile 名称及其 Provider 前缀，拒绝静默发往另一资源。

    Gateway 的真实 profile 注册表属于服务端；客户端只允许
    ``provider`` 或 ``provider_<name>``/``provider-<name>``/``provider.<name>``
    形式，从而在不传 provider 字段的线上合同中仍能本地发现明显错配。
    """

    code = validate_provider_code(provider_code)
    normalized = str(profile or "").strip()
    if not normalized or not _PROFILE_PATTERN.fullmatch(normalized):
        raise ProviderConfigurationError("invalid or missing LLM gateway profile")
    lowered = normalized.lower()
    if lowered != code and not any(
        lowered.startswith(f"{code}{separator}") for separator in ("_", "-", ".")
    ):
        raise ProviderConfigurationError("LLM gateway profile/provider mismatch")
    return normalized


def dispatch_runtime_fields(
    settings: Any,
    *,
    provider_code: Any,
    dispatch_mode: Any = None,
    gateway_profile: Any = None,
    model_code: Any = None,
) -> dict[str, str | None]:
    mode = normalize_dispatch_mode(
        dispatch_mode
        if dispatch_mode is not None
        else getattr(settings, "LLM_DISPATCH_MODE", "direct")
    )
    if mode == "direct":
        return {"dispatch_mode": "direct", "gateway_profile": None}
    profile = validate_gateway_profile(
        profile=(
            gateway_profile
            if gateway_profile is not None
            else configured_gateway_profile(settings, provider_code, model_code)
        ),
        provider_code=provider_code,
    )
    return {"dispatch_mode": "gateway", "gateway_profile": profile}


def configured_gateway_profile(settings: Any, provider_code: Any, model_code: Any = None) -> str | None:
    """同一Gateway内各Provider各用自己的profile，不猜测或跨Provider回退。"""
    code = validate_provider_code(provider_code)
    profiles = getattr(settings, "LLM_GATEWAY_PROFILES", {}) or {}
    if not isinstance(profiles, dict):
        raise ProviderConfigurationError("LLM gateway profile map is invalid")
    profile = profiles.get(code)
    if isinstance(profile, dict):
        profile = profile.get(str(model_code or ""))
        if not profile:
            raise ProviderConfigurationError("LLM model has no configured Gateway profile")
    return profile or getattr(settings, "LLM_GATEWAY_PROFILE", None)


__all__ = [
    "LEGACY_CLOUD_PROVIDER_CODES",
    "LOCAL_PROVIDER_CODES",
    "ProviderConfigurationError",
    "SUPPORTED_PROVIDER_CODES",
    "dispatch_runtime_fields",
    "configured_gateway_profile",
    "normalize_dispatch_mode",
    "strata_is_explicitly_configured",
    "validate_gateway_profile",
    "validate_provider_code",
]
