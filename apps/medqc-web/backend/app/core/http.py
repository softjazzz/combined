import asyncio
import ipaddress
import os
import socket
import threading
from contextvars import copy_context
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, TypeVar
from urllib.parse import urlsplit

import httpx

from .settings import get_settings
from .llm_http_proxy import LLMHTTPProxyPolicy
from .execution_timing import measure_stage, record_stage_duration, track_http_future
from .http_attempt_observation import current_http_attempt_observation
from .llm_transport_diagnostics import log_transport_failure


T = TypeVar("T")


class _SharedHttpResources:
    def __init__(self, max_concurrency: int, *,
                 proxy_policy: LLMHTTPProxyPolicy | None = None,
                 transport: httpx.BaseTransport | None = None,
                 proxy_transport: httpx.BaseTransport | None = None) -> None:
        settings = get_settings() if proxy_policy is None else None
        self.proxy_policy = proxy_policy if proxy_policy is not None else LLMHTTPProxyPolicy.load(
            getattr(settings, "LLM_HTTP_PROXY", ""), getattr(settings, "LLM_HTTP_PROXY_HOSTS", ""))
        physical_capacity = 64
        self.client = httpx.Client(
            limits=httpx.Limits(
                max_connections=physical_capacity,
                max_keepalive_connections=physical_capacity,
            ),
            trust_env=False,
            follow_redirects=False,
            **({"transport": transport} if transport is not None else {}),
        )
        self.proxy_client = None
        try:
            if self.proxy_policy.url:
                options = self.proxy_policy.client_options(
                    "https://" + sorted(self.proxy_policy.hosts)[0],
                    transport=transport, proxy_transport=proxy_transport)
                self.proxy_client = httpx.Client(
                    limits=httpx.Limits(max_connections=physical_capacity,
                                       max_keepalive_connections=physical_capacity),
                    trust_env=False, follow_redirects=False, **options)
        except Exception:
            self.client.close()
            raise
        self.executor = ThreadPoolExecutor(
            max_workers=physical_capacity,
            thread_name_prefix="medqc-llm-http",
        )
        self._condition = threading.Condition()
        self._active_count = 0
        self._max_concurrency = max_concurrency
        self._local = threading.local()

    def post_json(self, url: str, headers: Dict[str, str], payload: Dict[str, Any],
                  timeout_seconds: int, *, allow_disconnect_retry: bool = True) -> Dict[str, Any]:
        proxied = self.proxy_policy.matches(url)
        client = self.proxy_client if proxied else self.client
        try:
            result = _post_json(client, url, headers, payload, timeout_seconds,
                                allow_disconnect_retry=allow_disconnect_retry, reject_redirects=proxied)
        except httpx.HTTPError as error:
            if not proxied:
                raise
            # 不回显代理 URL、凭据或底层异常，不切换直连客户端。
            error_type = httpx.TimeoutException if isinstance(error, httpx.TimeoutException) else httpx.TransportError
            raise error_type("llm_http_proxy_transport_error") from None
        if proxied and isinstance(result, dict) and result.get("__status__") == 407:
            return {"__status__": 407, "__error__": True,
                    "body": {"error": "llm_http_proxy_authentication_failed"}}
        return result

    @property
    def max_concurrency(self) -> int:
        with self._condition:
            return self._max_concurrency

    def configure_max_concurrency(self, max_concurrency: int) -> None:
        with self._condition:
            self._max_concurrency = max_concurrency
            self._condition.notify_all()

    def _acquire_budget(self) -> None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._active_count < self._max_concurrency
            )
            self._active_count += 1

    def _release_budget(self) -> None:
        with self._condition:
            self._active_count -= 1
            self._condition.notify_all()

    def run_with_budget(self, operation: Callable[[], T]) -> T:
        depth = int(getattr(self._local, "budget_depth", 0))
        if depth > 0:
            return operation()
        self._acquire_budget()
        self._local.budget_depth = depth + 1
        try:
            return operation()
        finally:
            self._local.budget_depth = depth
            self._release_budget()


_shared_resources: Optional[_SharedHttpResources] = None
_shared_resources_lock = threading.Lock()
_shared_http_max_concurrency: Optional[int] = None


def _get_or_create_shared_resources() -> _SharedHttpResources:
    global _shared_resources
    with _shared_resources_lock:
        if _shared_resources is None:
            budget = int(
                _shared_http_max_concurrency
                if _shared_http_max_concurrency is not None
                else get_settings().LLM_HTTP_MAX_CONCURRENCY
            )
            _shared_resources = _SharedHttpResources(budget)
        return _shared_resources


def configure_shared_http_max_concurrency(
    max_concurrency: int,
) -> None:
    """热更新模型 HTTP 槽位；在途请求不取消，后续请求按新上限排队。"""

    global _shared_http_max_concurrency
    value = int(max_concurrency)
    if value < 1 or value > 64:
        raise ValueError("模型 HTTP 槽位必须在 1 到 64 之间")
    with _shared_resources_lock:
        _shared_http_max_concurrency = value
        resources = _shared_resources
    if resources is not None:
        resources.configure_max_concurrency(value)


async def run_shared_http_call(
    operation: Callable[[], T],
    *,
    resources: Optional[_SharedHttpResources] = None,
) -> T:
    """在线程池执行阻塞 HTTP 操作，并与同步旁路共享全进程并发预算。"""

    selected_resources = resources or _get_or_create_shared_resources()
    submitted = perf_counter()
    context = copy_context()
    observation = current_http_attempt_observation()
    if observation is not None:
        observation.submitted()

    def observed_operation():
        # 包含线程池和共享槽位等待；请求计时从真正取得槽位后开始。
        started = perf_counter()
        record_stage_duration("http_wait", started - submitted)
        if observation is not None:
            observation.started(started - submitted)
        try:
            with measure_stage("http_request"):
                return operation()
        finally:
            if observation is not None:
                observation.finished(perf_counter() - started)

    future = selected_resources.executor.submit(
        context.run,
        selected_resources.run_with_budget,
        observed_operation,
    )
    # 取消 await 不一定终止已经发出的阻塞 HTTP；终态观测必须明确仍有在途请求。
    track_http_future(future)
    return await asyncio.wrap_future(future)


def run_shared_http_call_sync(operation: Callable[[], T]) -> T:
    """执行同步 HTTP 操作，并与异步质控主链共享全进程并发预算。"""

    submitted = perf_counter()

    def observed_operation():
        record_stage_duration("http_wait", perf_counter() - submitted)
        with measure_stage("http_request"):
            return operation()

    return _get_or_create_shared_resources().run_with_budget(observed_operation)


def close_shared_http_resources() -> None:
    """幂等关闭共享 HTTP 连接池；后续调用按环境默认值重新创建。"""

    global _shared_resources, _shared_http_max_concurrency
    with _shared_resources_lock:
        resources = _shared_resources
        _shared_resources = None
        _shared_http_max_concurrency = None
    if resources is None:
        return
    resources.executor.shutdown(wait=True, cancel_futures=False)
    try:
        resources.client.close()
    finally:
        if resources.proxy_client is not None:
            resources.proxy_client.close()


_BLOCKED_METADATA_HOSTS = frozenset({
    "metadata.google.internal",
    "metadata.aliyun.internal",
    "metadata.internal",
})
_BLOCKED_LOOPBACK_HOSTS = frozenset({
    "localhost",
    "localhost.",
    "ip6-localhost",
    "ip6-loopback",
})
_ALIBABA_METADATA_IP = ipaddress.IPv4Address("100.100.100.200")


def _unwrap_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    mapped = getattr(ip_obj, "ipv4_mapped", None)
    return mapped if mapped is not None else ip_obj


def parse_ip_literal(host: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """解析字面 IP（含方括号 IPv6、zone ID 及数字/十六进制/八进制 IPv4 变形）。"""
    candidate = str(host or "").strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    candidate = candidate.split("%", 1)[0].strip()
    if not candidate:
        return None
    try:
        return _unwrap_ip(ipaddress.ip_address(candidate))
    except ValueError:
        pass
    # 拦截十进制/十六进制/八进制 IPv4 变形（如 2130706433、0x7f000001、0177.0.0.1）
    if all(ch in "0123456789abcdefABCDEFxX." for ch in candidate):
        try:
            packed = socket.inet_aton(candidate)
            return ipaddress.IPv4Address(packed)
        except OSError:
            pass
    return None


def is_unsafe_ssrf_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判定 IP 是否落入回环、私网、link-local、云元数据、保留段、多播或未指定段。"""
    ip_obj = _unwrap_ip(ip_obj)
    if ip_obj == _ALIBABA_METADATA_IP:
        return True
    return bool(
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def _is_blocked_db_metadata_or_special_ip(
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """数据库目标主机永不允许探测云元数据、link-local、未指定、多播或保留段。"""
    ip_obj = _unwrap_ip(ip_obj)
    if ip_obj == _ALIBABA_METADATA_IP:
        return True
    return bool(
        ip_obj.is_link_local
        or ip_obj.is_unspecified
        or ip_obj.is_multicast
        or ip_obj.is_reserved
    )


def _match_host_allowlist(host: str, entries: list[str], resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address]) -> bool:
    normalized_host = host.strip().lower().rstrip(".")
    literal_ip = parse_ip_literal(normalized_host)
    candidate_ips = [literal_ip] if literal_ip is not None else list(resolved_ips)
    for raw_entry in entries:
        entry = raw_entry.strip().lower()
        if not entry:
            continue
        if entry.startswith("[") and entry.endswith("]"):
            entry = entry[1:-1]
        if "/" in entry:
            try:
                net = ipaddress.ip_network(entry, strict=False)
                if any(_unwrap_ip(ip) in net for ip in candidate_ips):
                    return True
            except ValueError:
                continue
            continue
        entry_ip = parse_ip_literal(entry)
        if entry_ip is not None:
            if any(_unwrap_ip(ip) == entry_ip for ip in candidate_ips):
                return True
            continue
        entry_host = entry.rstrip(".")
        if normalized_host == entry_host or normalized_host.endswith("." + entry_host):
            return True
    return False


def validate_db_target_host(host: str, *, allowlist_env: str = "") -> str:
    """校验数据库连接目标主机，防止 SSRF / 内网回环及云元数据探测。"""
    raw = str(host or "").strip()
    if not raw or any(ch.isspace() or ord(ch) < 32 for ch in raw):
        raise ValueError("无效的数据库目标主机")
    if any(token in raw for token in ("://", "/", "@", "?", "#")):
        raise ValueError("无效的数据库目标主机")

    normalized = raw[1:-1].strip().lower() if raw.startswith("[") and raw.endswith("]") else raw.lower()
    stripped_dot = normalized.rstrip(".")
    if not stripped_dot:
        raise ValueError("无效的数据库目标主机")

    if stripped_dot in _BLOCKED_METADATA_HOSTS:
        raise ValueError("禁止连接云元数据或保留地址")

    allow_entries: list[str] = []
    for env_name in (allowlist_env, "DB_TARGET_HOST_ALLOWLIST"):
        if not env_name:
            continue
        env_val = os.getenv(env_name, "").strip()
        if env_val:
            allow_entries.extend(item.strip() for item in env_val.split(",") if item.strip())

    literal_ip = parse_ip_literal(normalized)
    resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    if literal_ip is not None:
        resolved_ips = [literal_ip]
    else:
        try:
            infos = socket.getaddrinfo(stripped_dot, None)
            for _family, _, _, _, sockaddr in infos:
                parsed_ip = parse_ip_literal(sockaddr[0])
                if parsed_ip is not None:
                    resolved_ips.append(parsed_ip)
        except OSError:
            resolved_ips = []

    if any(_is_blocked_db_metadata_or_special_ip(ip) for ip in resolved_ips):
        raise ValueError("禁止连接云元数据、链路本地或保留地址")

    if allow_entries:
        if not _match_host_allowlist(normalized, allow_entries, resolved_ips):
            raise ValueError("目标数据库主机不在部署白名单中")
        return raw

    if stripped_dot in _BLOCKED_LOOPBACK_HOSTS or stripped_dot.endswith(".localhost"):
        raise ValueError("禁止探测本机回环地址，如需本机连接请配置白名单")
    if any(_unwrap_ip(ip).is_loopback for ip in resolved_ips):
        raise ValueError("禁止探测本机回环地址，如需本机连接请配置白名单")
    return raw


def _is_private_address(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    stripped_dot = normalized.rstrip(".")
    if not stripped_dot:
        return True
    if stripped_dot in _BLOCKED_LOOPBACK_HOSTS or stripped_dot.endswith(".localhost"):
        return True
    if stripped_dot in _BLOCKED_METADATA_HOSTS:
        return True
    literal_ip = parse_ip_literal(normalized)
    if literal_ip is not None:
        return is_unsafe_ssrf_ip(literal_ip)
    try:
        # Resolve host to IPs and check each
        infos = socket.getaddrinfo(stripped_dot, None)
        if not infos:
            return True
        for _family, _, _, _, sockaddr in infos:
            ip_obj = parse_ip_literal(sockaddr[0])
            if ip_obj is None or is_unsafe_ssrf_ip(ip_obj):
                return True
        return False
    except Exception:
        # If resolution fails, treat as unsafe
        return True


def _is_allowed_host(host: str) -> bool:
    settings = get_settings()
    allow = [h.strip().lower().rstrip(".") for h in (settings.OUTBOUND_ALLOWLIST or []) if str(h).strip()]
    normalized = str(host or "").strip().lower().rstrip(".")
    if not normalized:
        return False
    for entry in allow:
        if normalized == entry:
            return True
        if "." in entry and parse_ip_literal(entry) is None and normalized.endswith("." + entry):
            return True
    return False


def _is_disconnected_without_response(error: httpx.RemoteProtocolError) -> bool:
    return "without sending a response" in str(error)


def _post_json(
    client: httpx.Client,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
    *, allow_disconnect_retry: bool = True, reject_redirects: bool = False,
) -> Dict[str, Any]:
    observation = current_http_attempt_observation()
    transport_attempt = 0

    def send_once():
        nonlocal transport_attempt
        transport_attempt += 1
        if observation is not None:
            observation.sending()
        try:
            response = client.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
        except httpx.RequestError as error:
            log_transport_failure(error, timeout_seconds=timeout_seconds,
                                  transport_attempt=transport_attempt)
            raise
        if observation is not None:
            observation.received()
        return response

    try:
        resp = send_once()
    except httpx.RemoteProtocolError as error:
        # 只对“服务端未返回任何响应即断开”重试一次：多为连接池复用了已被对端关闭的
        # 空闲连接，或并发突增时上游直接断开，请求未得到处理。收到部分响应后断开、
        # 超时、连接失败等其他异常仍原样抛出，不重试。
        if not allow_disconnect_retry or not _is_disconnected_without_response(error):
            raise
        resp = send_once()
    # 不直接 raise，尽量返回上游的 JSON 错误体，供调用方包装。
    try:
        body = resp.json() if resp.text else {}
    except Exception:
        body = {"text": resp.text}
    if resp.status_code >= 400 or (reject_redirects and resp.status_code >= 300):
        return {"__status__": resp.status_code, "__error__": True, "body": body}
    return body


async def safe_post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
    *, allow_disconnect_retry: bool = True,
) -> Dict[str, Any]:
    # Basic safety checks
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid URL scheme")
    host = parsed.hostname
    # 先检查允许列表：允许列表中的域名跳过私有地址检查
    # （VPN/代理环境可能把合法域名 DNS 解析到 198.18.x.x 等私有 IP 段）
    if not _is_allowed_host(host):
        if _is_private_address(host):
            raise ValueError("Outbound host resolves to private/loopback address")
        raise ValueError(f"Outbound host not in allowlist: {host}")

    # 同步 Client 可在线程间安全复用；线程池同时承担全进程并发预算，且不会把
    # AsyncClient 绑定到某一个 detached task 的事件循环。
    resources = _get_or_create_shared_resources()
    return await run_shared_http_call(
        lambda: resources.post_json(
            url,
            headers,
            payload,
            timeout_seconds,
            allow_disconnect_retry=allow_disconnect_retry,
        ),
        resources=resources,
    )
