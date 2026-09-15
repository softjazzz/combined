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
import re
import time
from typing import Any, Awaitable, Callable, Iterator, Mapping, Optional, Protocol, TypeVar
from uuid import uuid4

from sqlalchemy import text

from app.core.settings import get_settings
from app.database import connection as database_connection


logger = logging.getLogger(__name__)

_SAFE_METADATA_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


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

    def start_attempt_sync(self, event: Mapping[str, Any]) -> None:
        self._start_attempt_sync(dict(event))

    def finish_attempt_sync(
        self,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> None:
        self._finish_attempt_sync(event_id, dict(changes))

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
                        cached_input_tokens = :cached_input_tokens,
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

    def start_attempt_sync(self, event: Mapping[str, Any]) -> None:
        return None

    def finish_attempt_sync(
        self,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> None:
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
            "business_scene": _safe_metadata_label(
                context.business_scene,
                max_length=80,
                fallback="unclassified",
            ),
            "root_job_id": _safe_metadata_label(
                context.root_job_id,
                max_length=128,
                fallback=None,
            ),
            "record_key_hash": context.record_key_hash,
            "rule_set_key": _safe_metadata_label(
                context.rule_set_key,
                max_length=128,
                fallback=None,
            ),
            "rule_set_version": _safe_metadata_label(
                context.rule_set_version,
                max_length=64,
                fallback=None,
            ),
            "executor_key": _safe_metadata_label(
                context.executor_key,
                max_length=128,
                fallback=None,
            ),
            "provider_code": _safe_metadata_label(
                provider_code,
                max_length=64,
                fallback="unknown",
            ),
            "model": _safe_metadata_label(
                model,
                max_length=128,
                fallback="unknown",
            ),
            "model_role": _safe_metadata_label(
                model_role,
                max_length=64,
                fallback="unknown",
            ),
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
            "cached_input_tokens": (
                int(usage["cached_input_tokens"])
                if usage is not None and usage.get("cached_input_tokens") is not None
                else None
            ),
            "output_tokens": int(usage["output_tokens"]) if usage is not None else None,
            "total_tokens": int(usage["total_tokens"]) if usage is not None else None,
            "latency_ms": max(0, round((time.perf_counter() - started_timestamp) * 1000)),
        }
        await self._safe_store_call(
            "finish_attempt",
            self._store.finish_attempt(event_id, changes),
        )

    def start_attempt_sync(
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
            "business_scene": _safe_metadata_label(
                context.business_scene,
                max_length=80,
                fallback="unclassified",
            ),
            "root_job_id": _safe_metadata_label(
                context.root_job_id,
                max_length=128,
                fallback=None,
            ),
            "record_key_hash": context.record_key_hash,
            "rule_set_key": _safe_metadata_label(
                context.rule_set_key,
                max_length=128,
                fallback=None,
            ),
            "rule_set_version": _safe_metadata_label(
                context.rule_set_version,
                max_length=64,
                fallback=None,
            ),
            "executor_key": _safe_metadata_label(
                context.executor_key,
                max_length=128,
                fallback=None,
            ),
            "provider_code": _safe_metadata_label(
                provider_code,
                max_length=64,
                fallback="unknown",
            ),
            "model": _safe_metadata_label(
                model,
                max_length=128,
                fallback="unknown",
            ),
            "model_role": _safe_metadata_label(
                model_role,
                max_length=64,
                fallback="unknown",
            ),
            "status": "running",
            "usage_state": "unknown",
            "worker_id": _worker_id(),
            "created_at": started_at,
        }
        self._safe_store_call_sync("start_attempt", event)
        return event_id, time.perf_counter()

    def finish_attempt_sync(
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
            "cached_input_tokens": (
                int(usage["cached_input_tokens"])
                if usage is not None and usage.get("cached_input_tokens") is not None
                else None
            ),
            "output_tokens": int(usage["output_tokens"]) if usage is not None else None,
            "total_tokens": int(usage["total_tokens"]) if usage is not None else None,
            "latency_ms": max(
                0,
                round((time.perf_counter() - started_timestamp) * 1000),
            ),
        }
        self._safe_store_call_sync("finish_attempt", changes, event_id=event_id)

    def _safe_store_call_sync(
        self,
        operation: str,
        payload: Mapping[str, Any],
        *,
        event_id: Optional[str] = None,
    ) -> None:
        method = getattr(self._store, f"{operation}_sync", None)
        if not callable(method):
            logger.warning(
                "llm_observability_write_failed operation=%s error_type=%s",
                operation,
                "SyncStoreUnavailable",
            )
            return
        try:
            if event_id is None:
                method(payload)
            else:
                method(event_id, payload)
        except Exception as error:
            logger.warning(
                "llm_observability_write_failed operation=%s error_type=%s",
                operation,
                type(error).__name__,
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


_LLM_HTTP_RESULT = TypeVar("_LLM_HTTP_RESULT", bound=Mapping[str, Any])


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


def opaque_observation_id(namespace: str, value: Optional[str]) -> Optional[str]:
    """把不受信任的外部标识转换为固定长度、不可逆的观测关联键。"""

    normalized_namespace = str(namespace or "").strip()
    normalized_value = str(value or "").strip()
    if not normalized_namespace or not normalized_value:
        return None
    secret = str(get_settings().JWT_SECRET).encode("utf-8")
    material = f"{normalized_namespace}\x1f{normalized_value}".encode("utf-8")
    return hmac.new(secret, material, hashlib.sha256).hexdigest()


def _safe_metadata_label(
    value: Any,
    *,
    max_length: int,
    fallback: Optional[str],
) -> Optional[str]:
    normalized = str(value or "").strip()
    lowered = normalized.lower()
    if (
        not normalized
        or len(normalized) > max_length
        or not _SAFE_METADATA_PATTERN.fullmatch(normalized)
        or "://" in normalized
        or lowered.startswith(("sk-", "bearer"))
        or "api_key" in lowered
    ):
        return fallback
    return normalized


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
    if not any(key in usage for key in ("prompt_tokens", "input_tokens")):
        return None
    if not any(key in usage for key in ("completion_tokens", "output_tokens")):
        return None
    for key in recognized_keys:
        if key not in usage:
            continue
        value = usage[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None

    input_tokens = int(
        usage["prompt_tokens"]
        if "prompt_tokens" in usage
        else usage.get("input_tokens", 0)
    )
    output_tokens = int(
        usage["completion_tokens"]
        if "completion_tokens" in usage
        else usage.get("output_tokens", 0)
    )
    total_tokens = int(
        usage["total_tokens"]
        if "total_tokens" in usage
        else usage.get("total", input_tokens + output_tokens)
    )
    prompt_details = usage.get("prompt_tokens_details")
    cached_input_tokens = 0
    if isinstance(prompt_details, Mapping) and "cached_tokens" in prompt_details:
        cached_value = prompt_details["cached_tokens"]
        if (
            isinstance(cached_value, bool)
            or not isinstance(cached_value, int)
            or cached_value < 0
        ):
            return None
        cached_input_tokens = int(cached_value)
    elif "cached_tokens" in usage:
        cached_value = usage["cached_tokens"]
        if (
            isinstance(cached_value, bool)
            or not isinstance(cached_value, int)
            or cached_value < 0
        ):
            return None
        cached_input_tokens = int(cached_value)

    if cached_input_tokens is not None and cached_input_tokens > input_tokens:
        return None
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
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
    import requests

    if isinstance(error, asyncio.CancelledError):
        return "cancelled", "cancelled"
    if isinstance(error, httpx.TimeoutException):
        return "timeout", "timeout"
    if isinstance(error, httpx.TransportError):
        return "transport_error", "http_transport"
    if isinstance(error, requests.Timeout):
        return "timeout", "timeout"
    if isinstance(error, requests.ConnectionError):
        return "transport_error", "http_transport"
    if isinstance(error, requests.HTTPError):
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code == 429:
            return "upstream_429", "upstream_429"
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            return "upstream_5xx", "upstream_5xx"
        if isinstance(status_code, int) and 400 <= status_code <= 499:
            return "configuration_error", "upstream_4xx"
    error_module = type(error).__module__.split(".", 1)[0]
    error_name = type(error).__name__
    if error_module == "openai":
        status_code = getattr(error, "status_code", None)
        if error_name == "APITimeoutError":
            return "timeout", "timeout"
        if error_name == "APIConnectionError":
            return "transport_error", "http_transport"
        if error_name == "RateLimitError" or status_code == 429:
            return "upstream_429", "upstream_429"
        if isinstance(status_code, int) and 500 <= status_code <= 599:
            return "upstream_5xx", "upstream_5xx"
        if isinstance(status_code, int) and 400 <= status_code <= 499:
            return "configuration_error", "upstream_4xx"
    if isinstance(error, (ValueError, RuntimeError)):
        return "configuration_error", "configuration"
    return "unclassified", "unclassified"


@contextmanager
def _llm_http_attempt_context(
    *,
    business_scene: str,
    executor_key: str,
) -> Iterator[None]:
    """为独立模型出口补齐安全分类，同时保留外层任务/病例上下文。"""

    current = _OBSERVATION_CONTEXT.get()
    token = _OBSERVATION_CONTEXT.set(
        LLMObservationContext(
            business_scene=(
                current.business_scene
                if current.business_scene != "unclassified"
                else str(business_scene or "unclassified")
            ),
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


async def observe_llm_http_attempt(
    request: Callable[[], Awaitable[_LLM_HTTP_RESULT]],
    *,
    provider_code: str,
    model: str,
    business_scene: str,
    executor_key: str,
    model_role: str = "first_pass",
    recorder: Optional[LLMObservabilityRecorder] = None,
    logical_call_id: Optional[str] = None,
    attempt_no: int = 1,
) -> _LLM_HTTP_RESULT:
    """记录一次真实模型 HTTP 尝试，并原样返回上游结果。

    ``request`` 闭包可持有请求所需的敏感参数，但本边界只接收和持久化脱敏
    元数据，不读取或记录提示词、响应正文、端点、密钥与异常正文。
    """

    active_recorder = recorder or get_llm_observability_recorder()
    with _llm_http_attempt_context(
        business_scene=business_scene,
        executor_key=executor_key,
    ):
        event_id, started_timestamp = await active_recorder.start_attempt(
            logical_call_id=logical_call_id or str(uuid4()),
            attempt_no=max(1, int(attempt_no)),
            provider_code=provider_code,
            model=model,
            model_role=model_role,
        )
        try:
            result = await request()
        except BaseException as error:
            status, safe_error_kind = safe_status_for_exception(error)
            await active_recorder.finish_attempt(
                event_id=event_id,
                started_timestamp=started_timestamp,
                status=status,
                safe_error_kind=safe_error_kind,
                usage=None,
            )
            raise

        status, safe_error_kind = safe_status_for_http_result(result)
        await active_recorder.finish_attempt(
            event_id=event_id,
            started_timestamp=started_timestamp,
            status=status,
            safe_error_kind=safe_error_kind,
            usage=observed_usage(result),
        )
        return result


def observe_llm_sync_http_attempt(
    request: Callable[[], _LLM_HTTP_RESULT],
    *,
    provider_code: str,
    model: str,
    business_scene: str,
    executor_key: str,
    model_role: str = "first_pass",
    recorder: Optional[LLMObservabilityRecorder] = None,
) -> _LLM_HTTP_RESULT:
    """记录同步模型 HTTP 出口；观测失败不改变调用结果或异常语义。"""

    active_recorder = recorder or get_llm_observability_recorder()
    with _llm_http_attempt_context(
        business_scene=business_scene,
        executor_key=executor_key,
    ):
        event_id, started_timestamp = active_recorder.start_attempt_sync(
            logical_call_id=str(uuid4()),
            attempt_no=1,
            provider_code=provider_code,
            model=model,
            model_role=model_role,
        )
        try:
            result = request()
        except BaseException as error:
            status, safe_error_kind = safe_status_for_exception(error)
            active_recorder.finish_attempt_sync(
                event_id=event_id,
                started_timestamp=started_timestamp,
                status=status,
                safe_error_kind=safe_error_kind,
                usage=None,
            )
            raise

        status, safe_error_kind = safe_status_for_http_result(result)
        active_recorder.finish_attempt_sync(
            event_id=event_id,
            started_timestamp=started_timestamp,
            status=status,
            safe_error_kind=safe_error_kind,
            usage=observed_usage(result),
        )
        return result
