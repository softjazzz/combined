"""Worker 与独立 LLM Gateway 之间的线上合同。

本模块只依赖 Pydantic 和标准库，不得导入主应用、Settings 或数据库。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..llm_request_observation import GatewayRequestObservation
from ..llm_context_contract import CONTEXT_REASON_CODES


GATEWAY_COMPLETIONS_PATH = "/v1/llm/completions"
GATEWAY_RESOURCES_PATH = "/v1/llm/resources"


class GatewayErrorCode(str, Enum):
    """Worker 和 Gateway 共享的可公开、低基数错误码。"""

    INVALID_AUTH = "gateway_invalid_auth"
    INVALID_REQUEST = "gateway_invalid_request"
    INVALID_PROFILE = "gateway_invalid_profile"
    INVALID_PROVIDER_PAYLOAD = "gateway_invalid_provider_payload"
    QUEUE_FULL = "gateway_queue_full"
    DEADLINE_EXCEEDED = "gateway_deadline_exceeded"
    SHUTTING_DOWN = "gateway_shutting_down"
    RESOURCE_QUARANTINED = "gateway_resource_quarantined"
    PROVIDER_REJECTED = "gateway_provider_rejected"
    PROVIDER_TIMEOUT = "gateway_provider_timeout"
    PROVIDER_UNAVAILABLE = "gateway_provider_unavailable"
    PROXY_CONFIGURATION_INVALID = "gateway_proxy_configuration_invalid"
    INVALID_PROVIDER_RESPONSE = "gateway_invalid_provider_response"
    STRATA_STRUCTURED_FAILED = 'strata_structured_output_failed'
    INTERNAL_ERROR = "gateway_internal_error"
    CONTEXT_OVER_BUDGET = CONTEXT_REASON_CODES["OVER_BUDGET"]
    CONTEXT_COUNT_UNAVAILABLE = CONTEXT_REASON_CODES["COUNT_UNAVAILABLE"]
    CONTEXT_CAPABILITY_UNVERIFIED = CONTEXT_REASON_CODES["CAPABILITY_UNVERIFIED"]
    CONTEXT_BUDGET_EXHAUSTED = CONTEXT_REASON_CODES["BUDGET_EXHAUSTED"]


class GatewayCasePrefix(BaseModel):
    """最终脱敏单消息的非重复分段描述，不允许指定路由。"""
    model_config = ConfigDict(extra="forbid")
    case_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    context_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    prefix_start: int = Field(gt=0, le=262144, strict=True)
    expected_requests: int = Field(ge=1, le=16, strict=True)


class GatewayPrimeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nominal_input_tokens: int | None = Field(default=None, ge=0, strict=True)
    cached_tokens: int | None = Field(default=None, ge=0, strict=True)
    prefill_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    prefill_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    decode_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    queue_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    transport_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    wall_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)


class GatewayCacheTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["disabled", "cold", "primed", "reused", "prime_failed", "capacity_bypass"]
    prime_requests_started: int | None = Field(ge=0, le=1, strict=True)
    rule_requests_started: int | None = Field(ge=0, le=1, strict=True)
    prime_metrics: GatewayPrimeMetrics | None = None
    prime_error_code: str | None = Field(default=None, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")

    @model_validator(mode="after")
    def require_consistent_counts(self):
        if self.strategy == "primed" and self.prime_requests_started != 1:
            raise ValueError("primed trace requires one Prime")
        if self.strategy in {"disabled", "cold", "reused", "capacity_bypass"} and self.prime_requests_started != 0:
            raise ValueError("trace strategy cannot conceal a Prime")
        return self


class GatewayCompletionRequest(BaseModel):
    """一次受截止时间约束的 Provider 调用。"""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    profile: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    deadline_at: datetime
    timeout_seconds: float = Field(gt=0, le=3600)
    payload: dict[str, Any]
    case_prefix: GatewayCasePrefix | None = None
    observe_request: bool = Field(default=False, strict=True)
    context_budget_required: bool = Field(default=False, strict=True)
    case_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    package_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def require_package_case(self):
        if self.package_key is not None and self.case_key is None:
            raise ValueError("package identity requires case identity")
        return self

    @field_validator("deadline_at")
    @classmethod
    def require_aware_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deadline_at must include a timezone")
        return value


class GatewayTiming(BaseModel):
    """Gateway 只记录的传输阶段耗时。"""

    model_config = ConfigDict(extra="forbid")

    queue_seconds: float = Field(ge=0)
    http_seconds: float = Field(ge=0)


class GatewayErrorDetail(BaseModel):
    """可以对 Worker 公开的固定错误形状。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    retryable: bool
    cache_trace: GatewayCacheTrace | None = None
    request_observation: GatewayRequestObservation | None = None


class GatewayErrorResponse(BaseModel):
    """Gateway HTTP 4xx/5xx 响应。"""

    model_config = ConfigDict(extra="forbid")

    detail: GatewayErrorDetail


class GatewayContractError(ValueError):
    """本地构造 Gateway 请求时的合同错误。"""


__all__ = [
    "GATEWAY_COMPLETIONS_PATH",
    "GATEWAY_RESOURCES_PATH",
    "GatewayCompletionRequest",
    "GatewayContractError",
    "GatewayErrorCode",
    "GatewayErrorDetail",
    "GatewayErrorResponse",
    "GatewayTiming",
    "GatewayCasePrefix",
    "GatewayCacheTrace",
    "GatewayPrimeMetrics",
]
