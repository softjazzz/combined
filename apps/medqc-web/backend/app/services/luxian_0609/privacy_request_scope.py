"""病例调用范围内的发送闸门；不在共享客户端保存患者身份。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from inspect import signature
from typing import Any, Callable, Iterable, Mapping

from .llm_prompt_privacy import (
    PrivacyIdentityContextError,
    assert_no_known_identity_in_model_request,
    redact_luxian_0609_patient_privacy,
)


class _ScopeLease:
    """范围退出后让继承ContextVar的延迟任务失效；不保存身份。"""
    __slots__ = ("active",)

    def __init__(self) -> None:
        self.active = True


@dataclass(frozen=True)
class _Scope:
    provider: Callable[[], Iterable[str]] | None = field(default=None, repr=False)
    case_coordinates: tuple[str, str, str] | None = field(default=None, repr=False)
    lease: _ScopeLease = field(default_factory=_ScopeLease, repr=False, compare=False)
    preserve_existing_provider: bool = field(default=False, repr=False)


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
        scope = _Scope(case_coordinates=_case_coordinates(arguments))
        token = _SCOPE.set(scope)
        try:
            return await function(*args, **kwargs)
        finally:
            scope.lease.active = False
            _SCOPE.reset(token)

    return guarded


def _case_coordinates(arguments: Mapping[str, Any]) -> tuple[str, str, str] | None:
    bundle = arguments.get("bundle")
    source = bundle if isinstance(bundle, Mapping) else arguments
    values = tuple(source.get(key) for key in ("institute_id", "patient_id", "visit_id"))
    if any(isinstance(value, bool) or not isinstance(value, (str, int)) for value in values):
        return None
    coordinates = tuple(str(value).strip() for value in values)
    return coordinates if all(coordinates) else None


def luxian_0609_case_privacy_scope(function):
    """显式0609入口；只在完整病例归属一致时继承已有 provider。"""
    sig = signature(function)

    @wraps(function)
    async def guarded(*args, **kwargs):
        arguments = sig.bind_partial(*args, **kwargs).arguments
        coordinates = _case_coordinates(arguments)
        current = _SCOPE.get()
        inherits_case = (
            current is not None and current.lease.active and coordinates is not None
            and current.case_coordinates == coordinates
        )
        scope = (
            _Scope(
                provider=current.provider, case_coordinates=coordinates,
                lease=current.lease, preserve_existing_provider=True,
            )
            if inherits_case else _Scope(case_coordinates=coordinates)
        )
        owns_lease = not inherits_case
        token = _SCOPE.set(scope)
        try:
            return await function(*args, **kwargs)
        finally:
            if owns_lease:
                scope.lease.active = False
            _SCOPE.reset(token)

    return guarded


def is_luxian_0609_privacy_scope_active() -> bool:
    """只公开是否位于病例发送边界，不返回身份或 provider。"""
    return _SCOPE.get() is not None


def bind_luxian_0609_identity_provider(provider: Callable[[], Iterable[str]]) -> None:
    scope = _SCOPE.get()
    if scope is not None:
        previous = scope.provider
        if scope.preserve_existing_provider and previous is not None and previous is not provider:
            incoming = provider

            def combined() -> tuple[str, ...]:
                # 不缓存身份：每次发送重读双方，任一失败仍由最终闸门固定拒发。
                return (*previous(), *incoming())

            provider = combined
        _SCOPE.set(_Scope(
            provider=provider, case_coordinates=scope.case_coordinates,
            lease=scope.lease, preserve_existing_provider=scope.preserve_existing_provider,
        ))


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
    if not scope.lease.active or scope.provider is None:
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
