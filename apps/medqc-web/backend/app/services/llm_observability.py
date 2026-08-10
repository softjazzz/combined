"""脱敏的模型调用观测边界。

该模块只记录模型 HTTP 尝试的运行元数据，不保存提示词、响应正文、接口地址、
API Key 或患者三坐标原文。观测写入失败不得影响临床质控主流程。
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import logging
import os
import time
from typing import Any, Awaitable, Iterator, Mapping, Optional, Protocol
from uuid import uuid4

from sqlalchemy import text

from app.core.settings import get_settings
from app.database import connection as database_connection


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMObservationContext:
    business_scene: str = "unclassified"
    root_job_id: Optional[str] = None
    record_key_hash: Optional[str] = None
    rule_set_key: Optional[str] = None
    rule_set_version: Optional[str] = None
    executor_key: Optional[str] = None


_OBSERVATION_CONTEXT: ContextVar[LLMObservationContext] = ContextVar(
    "llm_observation_context",
    default=LLMObservationContext(),
)


class LLMCallEventStore(Protocol):
    async def start_attempt(self, event: Mapping[str, Any]) -> None: ...

    async def finish_attempt(self, event_id: str, changes: Mapping[str, Any]) -> None: ...


class PostgresLLMCallEventStore:
    """显式写入 ``sys.llm_call_events`` 的生产存储。"""

    async def start_attempt(self, event: Mapping[str, Any]) -> None:
        await asyncio.to_thread(self._start_attempt_sync, dict(event))

    async def finish_attempt(self, event_id: str, changes: Mapping[str, Any]) -> None:
        await asyncio.to_thread(self._finish_attempt_sync, event_id, dict(changes))

    @staticmethod
    def _start_attempt_sync(event: dict[str, Any]) -> None:
        engine = database_connection.engine
        if engine is None:
            raise RuntimeError("database_unavailable")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO sys.llm_call_events (
                        event_id, logical_call_id, attempt_no, started_at,
                        business_scene, root_job_id, record_key_hash,
                        rule_set_key, rule_set_version, executor_key,
                        provider_code, model, model_role, status,
                        usage_state, worker_id, created_at
                    ) VALUES (
                        :event_id, :logical_call_id, :attempt_no, :started_at,
                        :business_scene, :root_job_id, :record_key_hash,
                        :rule_set_key, :rule_set_version, :executor_key,
                        :provider_code, :model, :model_role, :status,
                        :usage_state, :worker_id, :created_at
                    )
                    ON CONFLICT (logical_call_id, attempt_no) DO NOTHING
                    """
                ),
                event,
            )

    @staticmethod
    def _finish_attempt_sync(event_id: str, changes: dict[str, Any]) -> None:
        engine = database_connection.engine
        if engine is None:
            raise RuntimeError("database_unavailable")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE sys.llm_call_events
                    SET finished_at = :finished_at,
                        status = :status,
                        safe_error_kind = :safe_error_kind,
                        usage_state = :usage_state,
                        input_tokens = :input_tokens,
                        output_tokens = :output_tokens,
                        total_tokens = :total_tokens,
                        latency_ms = :latency_ms
                    WHERE event_id = :event_id
                    """
                ),
                {"event_id": event_id, **changes},
            )


class NullLLMCallEventStore:
    """单元测试默认存储，避免测试进程写入开发数据库。"""

    async def start_attempt(self, event: Mapping[str, Any]) -> None:
        return None

    async def finish_attempt(self, event_id: str, changes: Mapping[str, Any]) -> None:
        return None


class LLMObservabilityRecorder:
    def __init__(self, *, store: Optional[LLMCallEventStore] = None) -> None:
        self._store = store or PostgresLLMCallEventStore()

    async def start_attempt(
        self,
        *,
        logical_call_id: str,
        attempt_no: int,
        provider_code: str,
        model: str,
        model_role: str,
    ) -> tuple[str, float]:
        event_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        context = _OBSERVATION_CONTEXT.get()
        event = {
            "event_id": event_id,
            "logical_call_id": logical_call_id,
            "attempt_no": attempt_no,
            "started_at": started_at,
            "business_scene": context.business_scene,
            "root_job_id": context.root_job_id,
            "record_key_hash": context.record_key_hash,
            "rule_set_key": context.rule_set_key,
            "rule_set_version": context.rule_set_version,
            "executor_key": context.executor_key,
            "provider_code": provider_code or "unknown",
            "model": model or "unknown",
            "model_role": model_role or "unknown",
            "status": "running",
            "usage_state": "unknown",
            "worker_id": _worker_id(),
            "created_at": started_at,
        }
        await self._safe_store_call("start_attempt", self._store.start_attempt(event))
        return event_id, time.perf_counter()

    async def finish_attempt(
        self,
        *,
        event_id: str,
        started_timestamp: float,
        status: str,
        safe_error_kind: Optional[str],
        usage: Optional[Mapping[str, int]],
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        usage_state = "known" if usage is not None else "unknown"
        changes = {
            "finished_at": finished_at,
            "status": status,
            "safe_error_kind": safe_error_kind,
            "usage_state": usage_state,
            "input_tokens": int(usage["input_tokens"]) if usage is not None else None,
            "output_tokens": int(usage["output_tokens"]) if usage is not None else None,
            "total_tokens": int(usage["total_tokens"]) if usage is not None else None,
            "latency_ms": max(0, round((time.perf_counter() - started_timestamp) * 1000)),
        }
        await self._safe_store_call(
            "finish_attempt",
            self._store.finish_attempt(event_id, changes),
        )

    @staticmethod
    async def _safe_store_call(operation: str, call: Awaitable[Any]) -> None:
        try:
            await call
        except Exception as error:
            logger.warning(
                "llm_observability_write_failed operation=%s error_type=%s",
                operation,
                type(error).__name__,
            )


_DEFAULT_RECORDER = LLMObservabilityRecorder()
_TEST_RECORDER = LLMObservabilityRecorder(store=NullLLMCallEventStore())


def get_llm_observability_recorder() -> LLMObservabilityRecorder:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return _TEST_RECORDER
    return _DEFAULT_RECORDER


def current_llm_observation_context() -> LLMObservationContext:
    """返回当前任务的脱敏观测上下文，供其它模型客户端复用。"""

    return _OBSERVATION_CONTEXT.get()


def _record_identity_hash(record_identity: Optional[tuple[str, str, str]]) -> Optional[str]:
    if not record_identity:
        return None
    normalized_parts = tuple(str(value).strip() for value in record_identity)
    if len(normalized_parts) != 3 or not all(normalized_parts):
        return None
    normalized = "\x1f".join(normalized_parts)
    secret = str(get_settings().JWT_SECRET).encode("utf-8")
    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def _worker_id() -> str:
    host = os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME") or "local"
    return f"{host}:{os.getpid()}"


@contextmanager
def llm_observation_context(
    *,
    business_scene: str,
    root_job_id: Optional[str] = None,
    record_identity: Optional[tuple[str, str, str]] = None,
    rule_set_key: Optional[str] = None,
    rule_set_version: Optional[str] = None,
    executor_key: Optional[str] = None,
) -> Iterator[None]:
    token = _OBSERVATION_CONTEXT.set(
        LLMObservationContext(
            business_scene=str(business_scene or "unclassified"),
            root_job_id=str(root_job_id) if root_job_id else None,
            record_key_hash=_record_identity_hash(record_identity),
            rule_set_key=str(rule_set_key) if rule_set_key else None,
            rule_set_version=str(rule_set_version) if rule_set_version else None,
            executor_key=str(executor_key) if executor_key else None,
        )
    )
    try:
        yield
    finally:
        _OBSERVATION_CONTEXT.reset(token)


@contextmanager
def llm_executor_observation_context(executor_key: str) -> Iterator[None]:
    """在保留病例/任务上下文的同时细化当前原生执行器。"""

    current = _OBSERVATION_CONTEXT.get()
    token = _OBSERVATION_CONTEXT.set(
        LLMObservationContext(
            business_scene=current.business_scene,
            root_job_id=current.root_job_id,
            record_key_hash=current.record_key_hash,
            rule_set_key=current.rule_set_key,
            rule_set_version=current.rule_set_version,
            executor_key=str(executor_key or "unclassified"),
        )
    )
    try:
        yield
    finally:
        _OBSERVATION_CONTEXT.reset(token)


def observed_usage(result: Mapping[str, Any]) -> Optional[dict[str, int]]:
    usage = result.get("usage")
    if not isinstance(usage, Mapping):
        return None
    recognized_keys = {
        "prompt_tokens",
        "input_tokens",
        "completion_tokens",
        "output_tokens",
        "total_tokens",
        "total",
    }
    if not any(key in usage for key in recognized_keys):
        return None
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or usage.get("total") or (input_tokens + output_tokens))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def safe_status_for_http_result(result: Mapping[str, Any]) -> tuple[str, Optional[str]]:
    if result.get("__error__") is not True:
        return "success", None
    try:
        status_code = int(result.get("__status__") or 0)
    except (TypeError, ValueError):
        status_code = 0
    if status_code == 429:
        return "upstream_429", "upstream_429"
    if 500 <= status_code <= 599:
        return "upstream_5xx", "upstream_5xx"
    return "configuration_error", "upstream_4xx"


def safe_status_for_exception(error: BaseException) -> tuple[str, str]:
    import httpx

    if isinstance(error, asyncio.CancelledError):
        return "cancelled", "cancelled"
    if isinstance(error, httpx.TimeoutException):
        return "timeout", "timeout"
    if isinstance(error, httpx.TransportError):
        return "transport_error", "http_transport"
    if isinstance(error, (ValueError, RuntimeError)):
        return "configuration_error", "configuration"
    return "unclassified", "unclassified"
