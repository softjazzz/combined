import asyncio
import ipaddress
import socket
import threading
from contextvars import copy_context
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, TypeVar

import httpx

from .settings import get_settings
from .execution_timing import measure_stage, record_stage_duration, track_http_future


T = TypeVar("T")


class _SharedHttpResources:
    def __init__(self, max_concurrency: int) -> None:
        physical_capacity = 64
        self.client = httpx.Client(
            limits=httpx.Limits(
                max_connections=physical_capacity,
                max_keepalive_connections=physical_capacity,
            ),
            trust_env=False,
        )
        self.executor = ThreadPoolExecutor(
            max_workers=physical_capacity,
            thread_name_prefix="medqc-llm-http",
        )
        self._condition = threading.Condition()
        self._active_count = 0
        self._max_concurrency = max_concurrency
        self._local = threading.local()

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

    def observed_operation():
        # 包含线程池和共享槽位等待；请求计时从真正取得槽位后开始。
        record_stage_duration("http_wait", perf_counter() - submitted)
        with measure_stage("http_request"):
            return operation()

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
    resources.client.close()


def _is_private_address(host: str) -> bool:
    try:
        # Resolve host to IPs and check each
        infos = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in infos:
            ip = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return True
        return False
    except Exception:
        # If resolution fails, treat as unsafe
        return True


def _is_allowed_host(host: str) -> bool:
    settings = get_settings()
    allow = [h.strip().lower() for h in (settings.OUTBOUND_ALLOWLIST or [])]
    host = host.lower()
    return any(host == a or host.endswith("." + a) for a in allow)


def _is_disconnected_without_response(error: httpx.RemoteProtocolError) -> bool:
    return "without sending a response" in str(error)


def _post_json(
    client: httpx.Client,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
    try:
        resp = client.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
    except httpx.RemoteProtocolError as error:
        # 只对“服务端未返回任何响应即断开”重试一次：多为连接池复用了已被对端关闭的
        # 空闲连接，或并发突增时上游直接断开，请求未得到处理。收到部分响应后断开、
        # 超时、连接失败等其他异常仍原样抛出，不重试。
        if not _is_disconnected_without_response(error):
            raise
        resp = client.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
    # 不直接 raise，尽量返回上游的 JSON 错误体，供调用方包装。
    try:
        body = resp.json() if resp.text else {}
    except Exception:
        body = {"text": resp.text}
    if resp.status_code >= 400:
        return {"__status__": resp.status_code, "__error__": True, "body": body}
    return body


async def safe_post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
    # Basic safety checks
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("Invalid URL scheme")
    # Extract host (strip port if present)
    host = url.split("//", 1)[1].split("/", 1)[0].split(":")[0]
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
        lambda: _post_json(
            resources.client,
            url,
            headers,
            payload,
            timeout_seconds,
        ),
        resources=resources,
    )
