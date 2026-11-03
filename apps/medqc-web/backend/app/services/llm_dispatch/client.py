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
    GatewayCasePrefix,
    GatewayCacheTrace,
)
from .provider_profiles import configured_gateway_profile, validate_gateway_profile


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

    def __init__(self, code: str, *, retryable: bool, cache_trace: GatewayCacheTrace | None = None,
                 cache_trace_invalid: bool = False, request_observation=None,
                 request_observation_invalid: bool = False) -> None:
        safe_code = code if code in _SAFE_GATEWAY_ERROR_CODES else "gateway_error"
        self.code = safe_code
        self.retryable = bool(retryable)
        self.cache_trace = cache_trace.model_dump(mode="json") if cache_trace is not None else None
        self.cache_trace_invalid = cache_trace_invalid
        self.request_observation = request_observation
        self.request_observation_invalid = request_observation_invalid
        super().__init__(safe_code)


class GatewayDispatchClient:
    """每次调用使用独立 AsyncClient，不继承代理且不跟随重定向。"""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    @staticmethod
    def _connection_settings(
        *, expected_profile: str, expected_endpoint_sha256: str, provider_code: str, model_code: str
    ) -> tuple[str, str]:
        settings = get_settings()
        if str(getattr(settings, "LLM_DISPATCH_MODE", "direct")) != "gateway":
            raise GatewayDispatchError("gateway_invalid_request", retryable=False)
        configured_profile = str(
            configured_gateway_profile(settings, provider_code, model_code) or ""
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
        case_prefix: GatewayCasePrefix | None = None,
        case_key: str | None = None,
        package_key: str | None = None,
        observe_request: bool = False,
        context_budget_required: bool = False,
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
            provider_code=provider_code,
            model_code=payload.get("model"),
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
                case_prefix=case_prefix,
                case_key=case_key,
                package_key=package_key,
                observe_request=observe_request,
                context_budget_required=context_budget_required,
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
                        json=self._request_body(request),
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
            trace, trace_invalid = self._validated_cache_trace(
                body.get("detail", {}).get("cache_trace")
                if isinstance(body, dict) and isinstance(body.get("detail"), dict) else None,
            )
            receipt, receipt_invalid = self._validated_request_observation(
                body.get("detail", {}).get("request_observation")
                if observe_request and isinstance(body, dict) and isinstance(body.get("detail"), dict) else None,
                request.request_id,
            )
            try:
                # 纯观测坏字段不覆盖原始安全错误码，也不能伪造失败的Prime费用。
                safe_body = dict(body) if isinstance(body, dict) else body
                if isinstance(safe_body, dict) and isinstance(safe_body.get("detail"), dict):
                    safe_body["detail"] = {**safe_body["detail"], "cache_trace": trace}
                    safe_body["detail"].pop("request_observation", None)
                error = GatewayErrorResponse.model_validate(safe_body).detail
            except (ValidationError, TypeError, ValueError):
                raise GatewayDispatchError(
                    "gateway_error", retryable=response.status_code >= 500
                ) from None
            raise GatewayDispatchError(error.code, retryable=error.retryable,
                                       cache_trace=trace, cache_trace_invalid=trace_invalid,
                                       request_observation=receipt, request_observation_invalid=receipt_invalid)
        if not isinstance(body, dict):
            raise GatewayDispatchError("gateway_invalid_response", retryable=False)
        try:
            GatewayTiming.model_validate(body.get("_gateway_timing"))
        except (ValidationError, TypeError, ValueError) as exc:
            raise GatewayDispatchError(
                "gateway_invalid_response", retryable=False
            ) from exc
        # 收据必须来自当前Gateway请求；坏观测不改变已成功的医学响应。
        receipt = body.pop("_gateway_request_observation", None)
        parsed, invalid = self._validated_request_observation(receipt if observe_request else None, request.request_id)
        if invalid:
            body["_gateway_request_observation_invalid"] = True
        elif parsed is not None:
            body["_gateway_request_observation"] = parsed
        if "_strata_cache" in body:
            trace, invalid = self._validated_cache_trace(body["_strata_cache"])
            if invalid:
                body.pop("_strata_cache", None)
                body["_strata_cache_invalid"] = True
            elif trace is not None:
                body["_strata_cache"] = trace.model_dump(mode="json")
        if case_prefix is not None:
            body["_strata_cache_expected"] = True
        return body

    @staticmethod
    def _validated_request_observation(value, request_id):
        if value is None:
            return None, False
        from ..llm_request_observation import GatewayRequestObservation
        try:
            parsed = GatewayRequestObservation.model_validate(value)
            if parsed.request_id != request_id:
                raise ValueError("request observation mismatch")
        except (ValidationError, ValueError, TypeError):
            return None, True
        return parsed.model_dump(mode="json"), False

    @staticmethod
    def _request_body(request: GatewayCompletionRequest) -> dict[str, Any]:
        body = request.model_dump(mode="json")
        if not body.get("context_budget_required"):
            body.pop("context_budget_required", None)
        if not body.get("observe_request"):
            body.pop("observe_request", None)
        if body.get("case_prefix") is None:
            body.pop("case_prefix", None)
        if body.get("case_key") is None:
            body.pop("case_key", None)
        if body.get("package_key") is None:
            body.pop("package_key", None)
        return body

    @staticmethod
    def _validated_cache_trace(value) -> tuple[GatewayCacheTrace | None, bool]:
        if value is None:
            return None, False
        try:
            return GatewayCacheTrace.model_validate(value), False
        except (ValidationError, TypeError, ValueError):
            return None, True


__all__ = ["GatewayDispatchClient", "GatewayDispatchError"]
