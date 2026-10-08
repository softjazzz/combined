"""病例调用范围内的发送闸门；不在共享客户端保存患者身份。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from inspect import signature
from typing import Any, Callable, Iterable

from .llm_prompt_privacy import (
    PrivacyIdentityContextError,
    assert_no_known_identity_in_model_request,
    redact_luxian_0609_patient_privacy,
)


@dataclass(frozen=True)
class _Scope:
    provider: Callable[[], Iterable[str]] | None = field(default=None, repr=False)


_SCOPE: ContextVar[_Scope | None] = ContextVar(
    "luxian0609_request_privacy", default=None
)


def luxian_0609_privacy_scope(function):
    """正式病例入口建立隔离范围；内部清空规则集名称的兼容调用仍继承。"""
    sig = signature(function)

    @wraps(function)
    async def guarded(*args, **kwargs):
        arguments = sig.bind_partial(*args, **kwargs).arguments
        if str(arguments.get("rule_set_key") or "").strip() != "luxian_0609_qc_v1":
            return await function(*args, **kwargs)
        token = _SCOPE.set(_Scope())
        try:
            return await function(*args, **kwargs)
        finally:
            _SCOPE.reset(token)

    return guarded


def bind_luxian_0609_identity_provider(provider: Callable[[], Iterable[str]]) -> None:
    if _SCOPE.get() is not None:
        _SCOPE.set(_Scope(provider=provider))


def _redact_strings(value: Any) -> Any:
    if isinstance(value, str):
        return redact_luxian_0609_patient_privacy(value)
    if isinstance(value, dict):
        return {key: _redact_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_strings(item) for item in value]
    return value


def protect_current_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """每次 HTTP 尝试前调用，包含重试；先脱敏再检测完整组包，不记录原值。"""
    scope = _SCOPE.get()
    if scope is None:
        return payload
    if scope.provider is None:
        raise PrivacyIdentityContextError("Patient identity context unavailable")
    try:
        values = tuple(scope.provider())
        if not values:
            raise PrivacyIdentityContextError("Patient identity context unavailable")
    except Exception:
        raise PrivacyIdentityContextError(
            "Patient identity context unavailable"
        ) from None
    safe = dict(payload)
    for key in ("messages", "response_format"):
        if key in safe:
            safe[key] = _redact_strings(safe[key])
    assert_no_known_identity_in_model_request(safe, values)
    return safe
