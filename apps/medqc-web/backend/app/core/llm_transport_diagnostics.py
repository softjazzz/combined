"""模型传输安全日志：仅记录白名单阶段，禁止异常原文和请求内容。"""

from contextlib import contextmanager
from contextvars import ContextVar
import errno
import logging
import math
import socket
import ssl
from uuid import UUID

import httpx


logger = logging.getLogger(__name__)
_EVENT_ID = ContextVar("llm_transport_diagnostic_event_id", default="unbound")
_ERRORS = (
    (httpx.ConnectTimeout, "connect", "connect_timeout"),
    (httpx.ReadTimeout, "read", "read_timeout"),
    (httpx.WriteTimeout, "write", "write_timeout"),
    (httpx.PoolTimeout, "pool", "pool_timeout"),
    (httpx.TimeoutException, "unknown", "timeout"),
    (httpx.ProxyError, "proxy", "proxy_error"),
    (httpx.ConnectError, "connect", "connect_error"),
    (httpx.ReadError, "read", "read_error"),
    (httpx.WriteError, "write", "write_error"),
    (httpx.RemoteProtocolError, "protocol", "remote_protocol_error"),
    (httpx.LocalProtocolError, "protocol", "local_protocol_error"),
    (httpx.TransportError, "unknown", "transport_error"),
)
_OS_ERRORS = {
    errno.ECONNREFUSED: "connection_refused", errno.ECONNRESET: "connection_reset",
    errno.ETIMEDOUT: "timed_out", errno.ENETUNREACH: "network_unreachable",
    errno.EHOSTUNREACH: "host_unreachable",
    10061: "connection_refused", 10054: "connection_reset", 10060: "timed_out",
    10051: "network_unreachable", 10065: "host_unreachable",
}


@contextmanager
def transport_diagnostic_scope(event_id):
    # 只接受本次调用的随机事件UUID，不接受病例、规则或任意自由文本作为关联键。
    try:
        safe_id = str(UUID(event_id)) if isinstance(event_id, str) else "unbound"
    except ValueError:
        safe_id = "unbound"
    token = _EVENT_ID.set(safe_id)
    try:
        yield
    finally:
        _EVENT_ID.reset(token)


def log_transport_failure(error, *, timeout_seconds, transport_attempt):
    """在代理脱敏包装前记录；不改变原异常、重试或调用结果。"""
    phase, kind = next(((phase, kind) for cls, phase, kind in _ERRORS
                        if isinstance(error, cls)), ("unknown", "request_error"))
    os_error = "unknown"
    current, seen = error, set()
    for _ in range(8):
        if not isinstance(current, BaseException) or id(current) in seen:
            break
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            phase, kind = "tls", "tls_certificate_error"
            break
        if isinstance(current, ssl.SSLError):
            phase, kind = "tls", "tls_error"
            break
        if isinstance(current, socket.gaierror):
            phase = "dns"
            os_error = {socket.EAI_AGAIN: "dns_temporary_failure",
                        socket.EAI_NONAME: "dns_name_not_found"}.get(current.errno, "unknown")
        elif isinstance(current, OSError):
            os_error = _OS_ERRORS.get(current.errno, "unknown")
        current = current.__cause__ or current.__context__
    safe_timeout = (timeout_seconds if type(timeout_seconds) in (int, float)
                    and 0 < timeout_seconds <= 86400 and math.isfinite(timeout_seconds) else "unknown")
    safe_attempt = transport_attempt if type(transport_attempt) is int and 1 <= transport_attempt <= 2 else "unknown"
    try:
        logger.warning(
            "LLM_TRANSPORT_FAILURE event_id=%s phase=%s error_kind=%s os_error=%s "
            "effective_timeout_seconds=%s transport_attempt=%s",
            _EVENT_ID.get(), phase, kind, os_error, safe_timeout, safe_attempt,
        )
    except Exception:
        # 日志处理器故障不得覆盖原始传输异常或触发额外请求。
        pass
