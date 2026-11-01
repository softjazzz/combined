from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias


DISPATCH_FILTER_KEY = "qc_dispatch"
DISPATCH_SCHEMA_VERSION = 1
MAX_ENVELOPE_BYTES = 4096

DispatchMode: TypeAlias = Literal["legacy", "rabbitmq"]
DispatchTarget: TypeAlias = Literal["main", "dead"]

PUBLISH_FAILURE_CODES = frozenset(
    {
        "dependency_missing",
        "connection_failed",
        "topology_failed",
        "channel_closed",
        "unroutable",
        "publish_nack",
        "confirm_missing",
        "publish_timeout",
        "invalid_envelope",
        "record_mismatch",
        "unexpected_publish_error",
    }
)
TERMINAL_FAILURE_CODES = frozenset(
    {
        "canceled",
        "worker_failed",
        "worker_lease_expired",
        "retry_budget_exhausted",
        "manual_scope_required",
    }
)
RECOVERY_KINDS = frozenset(
    {"delivery", "failed_scope", "manual_scope_required", "unstarted"}
)


def dispatch_filter_payload(mode: DispatchMode) -> dict[str, object]:
    """返回可持久化的调度身份；legacy 不应写入这个字段。"""

    if mode != "rabbitmq":
        raise ValueError("only rabbitmq dispatch identity is persisted")
    return {"schema_version": DISPATCH_SCHEMA_VERSION, "mode": mode}


def qc_dispatch_mode_from_filters(filters: Mapping[str, Any] | None) -> DispatchMode:
    """解析任务冻结的调度模式，损坏的新身份不得回退旧执行链。"""

    if filters is None or DISPATCH_FILTER_KEY not in filters:
        return "legacy"
    raw = filters[DISPATCH_FILTER_KEY]
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "mode"}:
        raise ValueError("invalid persisted qc dispatch identity")
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ValueError("unsupported persisted qc dispatch schema")
    if raw.get("mode") != "rabbitmq":
        raise ValueError("unsupported persisted qc dispatch mode")
    return "rabbitmq"


def _canonical_uuid(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a UUID string") from exc
    canonical = str(parsed)
    if value.lower() != canonical:
        raise ValueError(f"{field} must use canonical UUID form")
    return canonical


@dataclass(frozen=True, slots=True)
class BatchDispatchEnvelope:
    """RabbitMQ 中唯一允许的整批任务引用，不包含患者或模型数据。"""

    schema_version: int
    message_id: str
    job_id: str
    generation: int

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != DISPATCH_SCHEMA_VERSION:
            raise ValueError("unsupported batch dispatch envelope schema")
        _canonical_uuid(self.message_id, field="message_id")
        _canonical_uuid(self.job_id, field="job_id")
        if type(self.generation) is not int or self.generation <= 0:
            raise ValueError("generation must be a positive integer")

    @classmethod
    def new(
        cls,
        *,
        job_id: str,
        generation: int,
        message_id: str | None = None,
    ) -> "BatchDispatchEnvelope":
        return cls(
            schema_version=DISPATCH_SCHEMA_VERSION,
            message_id=message_id or str(uuid.uuid4()),
            job_id=job_id,
            generation=generation,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "message_id": self.message_id,
            "job_id": self.job_id,
            "generation": self.generation,
        }

    def to_bytes(self) -> bytes:
        encoded = json.dumps(
            self.as_dict(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        if len(encoded) > MAX_ENVELOPE_BYTES:
            raise ValueError("batch dispatch envelope exceeds 4096 bytes")
        return encoded

    @classmethod
    def from_bytes(cls, payload: bytes) -> "BatchDispatchEnvelope":
        if not isinstance(payload, bytes) or not payload or len(payload) > MAX_ENVELOPE_BYTES:
            raise ValueError("invalid batch dispatch envelope size")
        try:
            raw = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid batch dispatch envelope JSON") from exc
        expected = {"schema_version", "message_id", "job_id", "generation"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("batch dispatch envelope fields do not match schema")
        return cls(
            schema_version=raw["schema_version"],
            message_id=raw["message_id"],
            job_id=raw["job_id"],
            generation=raw["generation"],
        )
