"""Worker 与独立 LLM Gateway 之间的线上合同。

本模块只依赖 Pydantic 和标准库，不得导入主应用、Settings 或数据库。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    INVALID_PROVIDER_RESPONSE = "gateway_invalid_provider_response"
    INTERNAL_ERROR = "gateway_internal_error"


class GatewayCompletionRequest(BaseModel):
    """一次受截止时间约束的 Provider 调用。"""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    profile: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    deadline_at: datetime
    timeout_seconds: float = Field(gt=0, le=3600)
    payload: dict[str, Any]

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
]
