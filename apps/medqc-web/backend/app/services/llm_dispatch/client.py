"""受控 LLM Gateway HTTP 客户端。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import ValidationError

from ...core.settings import get_settings
from .contracts import (
    GATEWAY_COMPLETIONS_PATH,
    GatewayCompletionRequest,
    GatewayErrorCode,
    GatewayErrorResponse,
    GatewayTiming,
)
from .provider_profiles import validate_gateway_profile


_SAFE_GATEWAY_ERROR_CODES = frozenset(code.value for code in GatewayErrorCode) | {
    # 以下只由客户端本地传输层产生，不接受服务端任意文本。
    "gateway_error",
    "gateway_invalid_response",
    "gateway_request_timeout",
    "gateway_transport_error",
}


class GatewayDispatchError(RuntimeError):
    """只公开安全错误码，并声明传输重试已由 Gateway 管理。"""

    transport_retry_managed = True

    def __init__(self, code: str, *, retryable: bool) -> None:
        safe_code = code if code in _SAFE_GATEWAY_ERROR_CODES else "gateway_error"
        self.code = safe_code
        self.retryable = bool(retryable)
        super().__init__(safe_code)


class GatewayDispatchClient:
    """每次调用使用独立 AsyncClient，不继承代理且不跟随重定向。"""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    @staticmethod
    def _connection_settings(
        *, expected_profile: str, expected_endpoint_sha256: str
    ) -> tuple[str, str]:
        settings = get_settings()
        if str(getattr(settings, "LLM_DISPATCH_MODE", "direct")) != "gateway":
            raise GatewayDispatchError("gateway_invalid_request", retryable=False)
        configured_profile = str(
            getattr(settings, "LLM_GATEWAY_PROFILE", "") or ""
        ).strip()
        if configured_profile != expected_profile:
            raise GatewayDispatchError("gateway_invalid_request", retryable=False)
        root = str(getattr(settings, "LLM_GATEWAY_URL", "") or "").strip().rstrip("/")
        token = str(getattr(settings, "LLM_GATEWAY_TOKEN", "") or "").strip()
        try:
            parsed = urlparse(root)
        except Exception as exc:
            raise GatewayDispatchError(
                "gateway_invalid_request", retryable=False
            ) from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or len(token) < 32
        ):
            raise GatewayDispatchError("gateway_invalid_request", retryable=False)
        current_endpoint_sha256 = hashlib.sha256(root.encode("utf-8")).hexdigest()
        if current_endpoint_sha256 != expected_endpoint_sha256:
            raise GatewayDispatchError("gateway_invalid_request", retryable=False)
        return f"{root}{GATEWAY_COMPLETIONS_PATH}", token

    async def complete(
        self,
        *,
        provider_code: str,
        profile: str,
        expected_endpoint_sha256: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        normalized_profile = validate_gateway_profile(
            profile=profile, provider_code=provider_code
        )
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise GatewayDispatchError("gateway_deadline_exceeded", retryable=False)
        remaining = min(float(timeout_seconds), 3600.0)
        loop = asyncio.get_running_loop()
        budget_started = loop.time()
        deadline_at = datetime.now(timezone.utc) + timedelta(seconds=remaining)
        url, token = self._connection_settings(
            expected_profile=normalized_profile,
            expected_endpoint_sha256=expected_endpoint_sha256,
        )
        request_remaining = remaining - (loop.time() - budget_started)
        if request_remaining <= 0:
            raise GatewayDispatchError("gateway_deadline_exceeded", retryable=False)
        try:
            request = GatewayCompletionRequest(
                request_id=uuid4(),
                profile=normalized_profile,
                deadline_at=deadline_at,
                timeout_seconds=request_remaining,
                payload=payload,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise GatewayDispatchError(
                "gateway_invalid_request", retryable=False
            ) from exc

        try:
            timeout = httpx.Timeout(request_remaining)
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=timeout,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await asyncio.wait_for(
                    client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json=request.model_dump(mode="json"),
                    ),
                    timeout=request_remaining,
                )
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise GatewayDispatchError(
                "gateway_request_timeout", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise GatewayDispatchError(
                "gateway_transport_error", retryable=True
            ) from exc

        try:
            body = response.json()
        except (ValueError, TypeError) as exc:
            raise GatewayDispatchError(
                "gateway_invalid_response", retryable=response.status_code >= 500
            ) from exc
        if response.status_code < 200 or response.status_code >= 300:
            try:
                error = GatewayErrorResponse.model_validate(body).detail
            except (ValidationError, TypeError, ValueError):
                raise GatewayDispatchError(
                    "gateway_error", retryable=response.status_code >= 500
                ) from None
            raise GatewayDispatchError(error.code, retryable=error.retryable)
        if not isinstance(body, dict):
            raise GatewayDispatchError("gateway_invalid_response", retryable=False)
        try:
            GatewayTiming.model_validate(body.get("_gateway_timing"))
        except (ValidationError, TypeError, ValueError) as exc:
            raise GatewayDispatchError(
                "gateway_invalid_response", retryable=False
            ) from exc
        return body


__all__ = ["GatewayDispatchClient", "GatewayDispatchError"]
