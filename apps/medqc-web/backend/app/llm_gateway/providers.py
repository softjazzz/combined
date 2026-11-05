"""受控 Provider payload 适配与单次 HTTP 发送。"""

from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any, Protocol

import httpx

from app.core.llm_http_proxy import LLMHTTPProxyPolicy, LLMProxyConfigurationError

from app.services.llm_dispatch.contracts import GatewayErrorCode
from app.services.llm_token_budget import BudgetError

from .config import ProfileConfig
from app.services.strata_protocol import prepare_request as prepare_strata_request, validate_result, upstream_error, StrataProtocolError, p9_enabled


NETWORK_RETRY_COUNT = 0
MAX_PROVIDER_RESPONSE_BYTES = 16 * 1024 * 1024
_ALLOWED_PAYLOAD_FIELDS = frozenset(
    {
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "stream",
        "stop",
        "seed",
        "frequency_penalty",
        "presence_penalty",
        "response_format",
        "enable_thinking",
        "thinking_budget",
        "thinking",
        "reasoning_effort",
        "chat_template_kwargs",
        "n",
    }
)


class ProviderError(RuntimeError):
    code = GatewayErrorCode.PROVIDER_UNAVAILABLE.value
    status_code = 502
    retryable = False


class ProviderProxyConfigurationError(ProviderError):
    code = GatewayErrorCode.PROXY_CONFIGURATION_INVALID.value
    status_code = 503
    retryable = False


class InvalidPayloadError(ProviderError):
    code = GatewayErrorCode.INVALID_PROVIDER_PAYLOAD.value
    status_code = 400


class ProviderHTTPError(ProviderError):
    code = GatewayErrorCode.PROVIDER_REJECTED.value

    def __init__(self, upstream_status: int) -> None:
        super().__init__(self.code)
        self.upstream_status = upstream_status
        self.retryable = upstream_status == 429 or upstream_status >= 500
        self.status_code = 503 if self.retryable else 502


class ProviderTimeoutError(ProviderError):
    code = GatewayErrorCode.PROVIDER_TIMEOUT.value
    status_code = 504
    retryable = True


class ProviderTransportError(ProviderError):
    code = GatewayErrorCode.PROVIDER_UNAVAILABLE.value
    status_code = 503
    retryable = True


class InvalidProviderResponseError(ProviderError):
    code = GatewayErrorCode.INVALID_PROVIDER_RESPONSE.value
    status_code = 502


class ProviderSender(Protocol):
    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


def prepare_provider_payload(profile: ProfileConfig, raw_payload: dict[str, Any], *, allow_strata_prefix=False) -> dict[str, Any]:
    """只转发业务需要的 OpenAI 兼容字段，路由和凭据不在 payload 中。"""

    allowed = _ALLOWED_PAYLOAD_FIELDS | ({'top_k', 'repetition_penalty'} if profile.provider_code == 'strata' and p9_enabled(profile.model, profile.strata_protocol) else set()) | ({"strata_prefix"} if allow_strata_prefix and profile.provider_code == "strata" else set())
    if not isinstance(raw_payload, dict) or set(raw_payload) - allowed:
        raise InvalidPayloadError()
    payload = deepcopy(raw_payload)
    if "strata_prefix" in payload:
        prefix = payload["strata_prefix"]
        if (not isinstance(prefix, dict) or set(prefix) != {"tokens"}
                or type(prefix["tokens"]) is not int or not 1 <= prefix["tokens"] <= 32768):
            raise InvalidPayloadError()
    if payload.get("model") != profile.model:
        raise InvalidPayloadError()
    if payload.get("stream", False) is not False:
        raise InvalidPayloadError()
    payload["stream"] = False
    if payload.get("n", 1) != 1:
        raise InvalidPayloadError()

    _validate_messages(payload.get("messages"))
    _validate_optional_numbers(payload)
    _validate_response_format(payload.get("response_format"))
    _validate_thinking(payload)

    if profile.provider_code == "local_openai" and any(
        key in payload for key in ("strata_prefix", "chat_template_kwargs", "enable_thinking",
                                   "thinking_budget", "thinking", "reasoning_effort")
    ):
        # 首期只接纳通用OpenAI字段，不能猜测本地服务的Thinking扩展。
        raise InvalidPayloadError()

    if profile.provider_code == "strata":
        _map_strata_thinking(payload)
        if p9_enabled(profile.model, profile.strata_protocol):
            return _prepare_p9_numbers(payload)
    elif "chat_template_kwargs" in payload:
        raise InvalidPayloadError()
    return payload


def _prepare_p9_numbers(payload):
    for key in ('top_k', 'repetition_penalty'):
        if key in payload and (isinstance(payload[key], bool) or not isinstance(payload[key], (int, float))
                               or not math.isfinite(payload[key]) or payload[key] <= 0):
            raise InvalidPayloadError()
    if 'top_k' in payload and type(payload['top_k']) is not int:
        raise InvalidPayloadError()
    return prepare_strata_request(payload)


def _validate_messages(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise InvalidPayloadError()
    for message in value:
        if not isinstance(message, dict) or set(message) - {"role", "content", "name"}:
            raise InvalidPayloadError()
        if message.get("role") not in {"system", "developer", "user", "assistant"}:
            raise InvalidPayloadError()
        if not isinstance(message.get("content"), str):
            # 首期禁止 image_url/file 等使 Provider 主动取回外部资源的形状。
            raise InvalidPayloadError()
        if "name" in message and not isinstance(message["name"], str):
            raise InvalidPayloadError()


def _validate_optional_numbers(payload: dict[str, Any]) -> None:
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty"):
        if key in payload and (
            isinstance(payload[key], bool) or not isinstance(payload[key], (int, float))
            or not math.isfinite(payload[key])
        ):
            raise InvalidPayloadError()
    for key in ("max_tokens", "max_completion_tokens"):
        if key in payload and (
            isinstance(payload[key], bool)
            or not isinstance(payload[key], int)
            or not 1 <= payload[key] <= 131072
        ):
            raise InvalidPayloadError()
    if "seed" in payload and (
        isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int)
    ):
        raise InvalidPayloadError()


def _validate_response_format(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or value.get("type") not in {"json_object", "json_schema"}:
        raise InvalidPayloadError()


def _validate_thinking(payload: dict[str, Any]) -> None:
    if "enable_thinking" in payload and not isinstance(payload["enable_thinking"], bool):
        raise InvalidPayloadError()
    if "thinking_budget" in payload and (
        isinstance(payload["thinking_budget"], bool)
        or not isinstance(payload["thinking_budget"], int)
        or payload["thinking_budget"] <= 0
    ):
        raise InvalidPayloadError()
    if "thinking" in payload:
        thinking = payload["thinking"]
        if not isinstance(thinking, dict) or thinking.get("type") not in {"enabled", "disabled"}:
            raise InvalidPayloadError()
    if "reasoning_effort" in payload and payload["reasoning_effort"] not in {
        "low",
        "medium",
        "high",
        "max",
    }:
        raise InvalidPayloadError()
    if "chat_template_kwargs" in payload:
        nested = payload["chat_template_kwargs"]
        if not isinstance(nested, dict) or set(nested) - {"enable_thinking", "thinking_budget"}:
            raise InvalidPayloadError()
        nested_probe = dict(nested)
        _validate_thinking(nested_probe)


def _map_strata_thinking(payload: dict[str, Any]) -> None:
    nested = dict(payload.get("chat_template_kwargs") or {})
    for key in ("enable_thinking", "thinking_budget"):
        if key not in payload:
            continue
        if key in nested and nested[key] != payload[key]:
            raise InvalidPayloadError()
        nested[key] = payload.pop(key)
    if nested:
        payload["chat_template_kwargs"] = nested


class HttpxProviderSender:
    """不跟随重定向、不读取系统代理、首期不自动重试。"""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None,
                 proxy_policy: LLMHTTPProxyPolicy | None = None,
                 proxy_transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport
        self._proxy_policy = proxy_policy or LLMHTTPProxyPolicy()
        self._proxy_transport = proxy_transport

    def prepare(self, profile: ProfileConfig, payload: dict[str, Any]) -> dict[str, Any]:
        from app.services.llm_token_budget import BudgetError, guard_payload, strict_enabled
        try:
            # 配置拒绝发生在排队和HTTP之前，不记为远端未知在途或隔离整资源。
            self._proxy_policy.matches(profile.api_endpoint)
        except LLMProxyConfigurationError:
            raise ProviderProxyConfigurationError() from None
        try:
            if profile.provider_code == 'strata' and p9_enabled(profile.model, profile.strata_protocol):
                from app.services.strata_protocol import require_deployment_identity
                require_deployment_identity(profile.model, profile.api_endpoint, profile.context_budget, profile.model_identity)
                payload = prepare_provider_payload(profile, payload, allow_strata_prefix=True)
            guard_payload(profile.provider_code, profile.name, payload, profile.context_budget,
                          enabled=strict_enabled() or (profile.provider_code == "strata" and p9_enabled(profile.model, profile.strata_protocol)), phase="provider_http_boundary")
        except (BudgetError, StrataProtocolError) as error:
            # 直接使用sender时也不绕过；通常排队前已经完成同一准入。
            rejected = InvalidPayloadError()
            rejected.code = error.code
            raise rejected from None
        return payload

    async def ensure_counter(self, profile):
        if profile.provider_code == 'strata' and profile.model == 'qwen3.6-35b-a3b':
            from app.services.strata_handoff import ensure_counter, _fail
            try:
                if not profile.handoff_dir:
                    raise _fail('handoff_not_configured')
                await ensure_counter(profile.handoff_dir)
            except BudgetError as error:
                rejected = InvalidPayloadError()
                rejected.code = error.code
                raise rejected from None

    async def ensure_identity(self, profile):
        if profile.provider_code == 'strata' and profile.model == 'qwen3.6-35b-a3b':
            from app.services.strata_handoff import ensure_endpoint
            try:
                await ensure_endpoint(profile.handoff_dir, profile.api_endpoint, profile.api_key,
                                      transport=self._transport)
            except BudgetError as error:
                rejected = InvalidPayloadError()
                rejected.code = error.code
                raise rejected from None

    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        await self.ensure_counter(profile)
        payload = self.prepare(profile, payload)
        await self.ensure_identity(profile)
        payload = self.prepare(profile, payload)
        headers = {"Content-Type": "application/json"}
        if profile.api_key:
            headers["Authorization"] = f"Bearer {profile.api_key}"
        try:
            async with httpx.AsyncClient(
                **self._proxy_policy.client_options(profile.api_endpoint,
                    transport=self._transport, proxy_transport=self._proxy_transport),
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(timeout_seconds),
            ) as client:
                response = await client.post(profile.api_endpoint, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ProviderTimeoutError() from None
        except httpx.HTTPError:
            raise ProviderTransportError() from None

        if not 200 <= response.status_code < 300:
            if profile.provider_code == 'strata' and p9_enabled(profile.model, profile.strata_protocol):
                try:
                    body = response.json()
                except (ValueError, UnicodeDecodeError):
                    body = None
                error = upstream_error(response.status_code, body)
                if error is not None:
                    rejected = ProviderError(error.code)
                    rejected.code = error.code
                    raise rejected from None
            raise ProviderHTTPError(response.status_code)
        if len(response.content) > MAX_PROVIDER_RESPONSE_BYTES:
            raise InvalidProviderResponseError()
        try:
            decoded = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            raise InvalidProviderResponseError() from None
        if not isinstance(decoded, dict):
            raise InvalidProviderResponseError()
        if profile.provider_code == 'strata' and p9_enabled(profile.model, profile.strata_protocol):
            try:
                validate_result(decoded, profile.model)
            except StrataProtocolError as error:
                rejected = ProviderError(error.code)
                rejected.code = error.code
                raise rejected from None
        return decoded


__all__ = [
    "HttpxProviderSender",
    "InvalidPayloadError",
    "InvalidProviderResponseError",
    "NETWORK_RETRY_COUNT",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderSender",
    "ProviderTimeoutError",
    "ProviderTransportError",
    "prepare_provider_payload",
]
