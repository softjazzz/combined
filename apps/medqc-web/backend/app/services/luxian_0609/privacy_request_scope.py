"""病例调用范围内的发送闸门；不在共享客户端保存患者身份。"""

from __future__ import annotations

from contextlib import contextmanager
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
    require_collected_identity: bool = field(default=False, repr=False)
    identity_context_invalid: bool = field(default=False, repr=False)


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
        with _case_scope(_case_coordinates(arguments)):
            return await function(*args, **kwargs)

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
        with _case_scope(_case_coordinates(arguments)):
            return await function(*args, **kwargs)

    return guarded


@contextmanager
def _case_scope(coordinates: tuple[str, str, str] | None, *, require_collected_identity: bool = False):
    current = _SCOPE.get()
    inherits_case = (
        current is not None and current.lease.active and coordinates is not None
        and current.case_coordinates == coordinates
    )
    requires_source = require_collected_identity or bool(current and current.require_collected_identity)
    invalid_source = (
        current.identity_context_invalid if inherits_case else
        bool(current and current.require_collected_identity and not require_collected_identity)
    )
    scope = (
        _Scope(
            provider=current.provider, case_coordinates=coordinates,
            lease=current.lease, preserve_existing_provider=True,
            require_collected_identity=requires_source, identity_context_invalid=invalid_source,
        )
        if inherits_case else _Scope(
            case_coordinates=coordinates, require_collected_identity=requires_source,
            identity_context_invalid=invalid_source,
        )
    )
    token = _SCOPE.set(scope)
    try:
        yield
    finally:
        if not inherits_case:
            scope.lease.active = False
        _SCOPE.reset(token)


@contextmanager
def luxian_0609_case_identity_scope(*, case_coordinates: tuple[str, str, str], identity_provider: Callable[[], Iterable[str]]):
    """worker单病例私有作用域；完整归属贯通现有正式入口及每次attempt。"""
    coordinates = _case_coordinates(dict(zip(("institute_id", "patient_id", "visit_id"), case_coordinates)))
    if coordinates is None or len(case_coordinates) != 3:
        raise PrivacyIdentityContextError("Patient identity context unavailable")
    with _case_scope(coordinates, require_collected_identity=True):
        bind_luxian_0609_identity_provider(identity_provider, case_coordinates=coordinates)
        yield


def is_luxian_0609_privacy_scope_active() -> bool:
    """只公开是否位于病例发送边界，不返回身份或 provider。"""
    return _SCOPE.get() is not None


def bind_luxian_0609_identity_provider(provider: Callable[[], Iterable[str]], *, case_coordinates: tuple[str, str, str] | None = None) -> Callable[[], Iterable[str]]:
    scope = _SCOPE.get()
    if scope is not None:
        coordinates = _case_coordinates(dict(zip(("institute_id", "patient_id", "visit_id"), case_coordinates))) if case_coordinates is not None and len(case_coordinates) == 3 else None
        invalid_context = scope.identity_context_invalid or (
            scope.require_collected_identity and coordinates != scope.case_coordinates
        )
        if invalid_context:
            def unavailable() -> tuple[str, ...]:
                raise PrivacyIdentityContextError("Patient identity context unavailable")
            provider = unavailable
        previous = scope.provider
        if not invalid_context and scope.preserve_existing_provider and previous is not None and previous is not provider:
            incoming = provider

            def combined() -> tuple[str, ...]:
                # 不缓存身份：每次发送重读双方，任一失败仍由最终闸门固定拒发。
                return (*previous(), *incoming())

            provider = combined
        _SCOPE.set(_Scope(
            provider=provider, case_coordinates=scope.case_coordinates,
            lease=scope.lease, preserve_existing_provider=scope.preserve_existing_provider,
            require_collected_identity=scope.require_collected_identity, identity_context_invalid=invalid_context,
        ))
    return provider


def current_luxian_0609_redaction_identities() -> Iterable[str]:
    """让事实准备和发送边界使用同一病例身份；不缓存、不补查来源。"""
    scope = _SCOPE.get()
    if scope is None or scope.provider is None:
        return ()
    if not scope.lease.active or scope.identity_context_invalid:
        raise PrivacyIdentityContextError("Patient identity context unavailable")
    try:
        return tuple(scope.provider())
    except Exception:
        raise PrivacyIdentityContextError("Patient identity context unavailable") from None


def _redact_strings(value: Any, identity_values: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        return redact_luxian_0609_patient_privacy(value, identity_values=identity_values)
    if isinstance(value, dict):
        return {key: _redact_strings(item, identity_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_strings(item, identity_values) for item in value]
    return value


def protect_current_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """每次 HTTP 尝试前调用，包含重试；先脱敏再检测完整组包，不记录原值。"""
    scope = _SCOPE.get()
    if scope is None:
        return payload
    if not scope.lease.active or scope.identity_context_invalid or scope.provider is None:
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
            safe[key] = _redact_strings(safe[key], values)
    assert_no_known_identity_in_model_request(safe, values)
    return safe
