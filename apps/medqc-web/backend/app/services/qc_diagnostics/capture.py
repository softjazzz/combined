"""显式授权范围内的内存模型录制，默认关闭，禁止直接对外导出。

只旁路消费实际调用，不查库、不发请求、不写文件。作用域退出即释放原件；
read_internal 供范围内的本地脱敏使用，返回值仍含原始内容，调用方不得落盘。
本模块尚未绑定正式最终结果，不能把内存录制称作完整质控证据。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import re
import threading
import time
from types import MappingProxyType
from uuid import UUID

from .contracts import DiagnosticPackageError
from .typed_values import decode_value, encode_value

_CURRENT: ContextVar[_Capture | None] = ContextVar("qc_diagnostic_capture", default=None)
_CREDENTIAL_FIELDS = {"authorization", "api_key", "apikey", "access_token", "password", "headers", "api_endpoint", "token", "secret"}
_SAFE_ERRORS = {"timeout", "cancelled", "canceled", "transport_error", "http_error", "http_4xx", "http_5xx", "unknown_error"}


def _snapshot(value: object) -> bytes:
    encoded = encode_value(value)  # 限制类型、深度、节点数，拒绝执行自定义序列化。
    stack = [value]
    while stack:
        item = stack.pop()
        if type(item) in (dict, MappingProxyType):
            if any(key.lower() in _CREDENTIAL_FIELDS for key in item):
                raise DiagnosticPackageError("credential_field")
            stack.extend(item.values())
        elif type(item) in (list, tuple):
            stack.extend(item)
    payload = json.dumps(encoded, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > 4 * 1024 * 1024:
        raise DiagnosticPackageError("capture_payload_limit")
    return payload


@dataclass(frozen=True, repr=False)
class _Handle:
    owner: _Capture
    key: tuple[str, int]


class _Capture:
    def __init__(self, max_bytes: int, ttl_seconds: int):
        if type(max_bytes) is not int or not 1 <= max_bytes <= 20 * 1024 * 1024:
            raise DiagnosticPackageError("invalid_capture_limit")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise DiagnosticPackageError("invalid_capture_limit")
        self._limit = max_bytes
        self._expires = time.monotonic() + ttl_seconds
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, int], dict] = {}
        self._inputs: bytes | None = None
        self._bytes = 0
        self._closed = False
        self._errors: set[str] = set()
        self._identity: tuple[str | None, str | None] | None = None

    def __repr__(self):
        return "DiagnosticCapture(raw_contents_hidden=True)"

    def _ready(self) -> bool:
        if time.monotonic() >= self._expires:
            self._errors.add("expired")
            self._release()
        return not self._closed

    def _release(self):
        if any(not row["finished"] for row in self._rows.values()):
            self._errors.add("unfinished_attempts")
        self._rows.clear()
        self._inputs = None
        self._identity = None
        self._bytes = 0
        self._closed = True

    def close(self):
        with self._lock:
            self._release()

    def _failed(self):
        with self._lock:
            self._errors.add("capture_failed")

    def _context_matches(self, context) -> bool:
        identity = (context.root_job_id, context.record_key_hash)
        if self._identity is not None and self._identity != identity:
            self._errors.add("case_context_mismatch")
            return False
        if not all(identity):
            self._errors.add("case_context_unavailable")
        self._identity = identity
        return True

    def _capture_inputs(self, session, parameters):
        from ..llm_observability import current_llm_observation_context
        from .execution_inputs import freeze_execution_inputs
        with self._lock:
            if not self._ready() or not self._context_matches(current_llm_observation_context()):
                return
            if self._inputs is not None:
                self._errors.add("duplicate_execution_inputs")
                return
            inputs = freeze_execution_inputs(session, **parameters)
            frozen = _snapshot(inputs)
            if not self._ready():
                return
            if self._bytes + len(frozen) > self._limit:
                self._errors.add("capacity_exceeded")
                return
            self._inputs = frozen
            self._bytes += len(frozen)
            if any(item["completeness"] != "complete" for item in inputs["snapshot"]["observations"]):
                self._errors.add("execution_sources_incomplete")

    def _begin(self, logical_call_id: str, attempt_no: int, payload: object) -> _Handle | None:
        with self._lock:
            if not self._ready():
                return None
            if type(logical_call_id) is not str or str(UUID(logical_call_id)) != logical_call_id or type(attempt_no) is not int or not 1 <= attempt_no <= 256:
                raise DiagnosticPackageError("invalid_capture_call")
            key = (logical_call_id, attempt_no)
            if key in self._rows:
                self._errors.add("duplicate_attempt")
                return None
            if len(self._rows) >= 256:
                self._errors.add("capacity_exceeded")
                return None
            from ..llm_observability import current_llm_observation_context
            context = current_llm_observation_context()
            if not self._context_matches(context):
                return None
            executor = context.executor_key
            if type(executor) is not str or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", executor) is None:
                executor = None
                self._errors.add("executor_context_unavailable")
            frozen = _snapshot(payload)
            if self._bytes + len(frozen) > self._limit:
                self._errors.add("capacity_exceeded")
                return None
            self._rows[key] = {"request": frozen, "response": None, "error_kind": None, "finished": False, "executor_key": executor}
            self._bytes += len(frozen)
            return _Handle(self, key)

    def _finish(self, handle: _Handle, result: object, error_kind: str | None):
        with self._lock:
            if not self._ready():
                return
            row = self._rows.get(handle.key)
            if row is None or row["finished"]:
                self._errors.add("unmatched_attempt")
                return
            if error_kind is not None:
                row["error_kind"] = error_kind if type(error_kind) is str and error_kind in _SAFE_ERRORS else "unknown_error"
            else:
                frozen = _snapshot(result)
                if self._bytes + len(frozen) > self._limit:
                    self._errors.add("capacity_exceeded")
                    return
                row["response"] = frozen
                self._bytes += len(frozen)
            row["finished"] = True

    def summary(self) -> dict:
        with self._lock:
            self._ready()
            return {"capture_completeness": "partial", "closed": self._closed,
                    "retained_bytes": self._bytes, "attempt_count": len(self._rows),
                    "pending_attempt_count": sum(not row["finished"] for row in self._rows.values()),
                    "missing_reasons": sorted(self._errors | {"final_result_not_captured"}
                                              | ({"execution_inputs_not_captured"} if self._inputs is None else set()))}

    def read_internal(self) -> dict:
        """返回独立副本，仅供本地脱敏；不向 API 暴露此方法或返回值。"""
        with self._lock:
            if not self._ready():
                raise DiagnosticPackageError("capture_unavailable")
            return {"execution_inputs": decode_value(json.loads(self._inputs)) if self._inputs is not None else None,
                    "calls": [{"logical_call_id": key[0], "attempt_no": key[1],
                               "executor_key": row["executor_key"],
                               "request": decode_value(json.loads(row["request"])),
                               "response": decode_value(json.loads(row["response"])) if row["response"] is not None else None,
                               "error_kind": row["error_kind"], "finished": row["finished"]}
                              for key, row in self._rows.items()]}


@contextmanager
def capture_scope(*, max_bytes: int = 20 * 1024 * 1024, ttl_seconds: int = 1800):
    """调用方必须在已授权的单病例执行范围使用；不能包围整个并发病例批次。"""
    capture = _Capture(max_bytes, ttl_seconds)
    token = _CURRENT.set(capture)
    try:
        yield capture
    finally:
        _CURRENT.reset(token)
        capture.close()


def begin_attempt(*, logical_call_id: str, attempt_no: int, payload: object) -> _Handle | None:
    capture = _CURRENT.get()
    if capture is None:
        return None
    try:
        return capture._begin(logical_call_id, attempt_no, payload)
    except Exception:
        capture._failed()
        return None


def finish_attempt(handle: _Handle | None, *, result: object = None, error_kind: str | None = None) -> None:
    if handle is None:
        return
    try:
        handle.owner._finish(handle, result, error_kind)
    except Exception:
        handle.owner._failed()


def capture_execution_inputs(session, *, selected_rule_ids: tuple[str, ...],
                             evaluation_as_of_date: str | None,
                             evaluation_horizon_policy: str | None,
                             horizon_unavailable_reason: str | None) -> None:
    """已授权单病例作用域内旁路接收实际 session；默认关闭且错误不影响质控。"""
    capture = _CURRENT.get()
    if capture is None:
        return
    try:
        capture._capture_inputs(session, {
            "selected_rule_ids": selected_rule_ids, "evaluation_as_of_date": evaluation_as_of_date,
            "evaluation_horizon_policy": evaluation_horizon_policy,
            "horizon_unavailable_reason": horizon_unavailable_reason,
        })
    except Exception:
        capture._failed()
