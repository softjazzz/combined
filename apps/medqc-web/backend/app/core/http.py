import asyncio
import ipaddress
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, TypeVar

import httpx

from .settings import get_settings


T = TypeVar("T")


class _SharedHttpResources:
    def __init__(self, max_concurrency: int) -> None:
        self.client = httpx.Client(
            limits=httpx.Limits(
                max_connections=max_concurrency,
                max_keepalive_connections=max_concurrency,
            ),
            trust_env=False,
        )
        self.executor = ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="medqc-llm-http",
        )
        self.budget = threading.BoundedSemaphore(max_concurrency)
        self._local = threading.local()

    def run_with_budget(self, operation: Callable[[], T]) -> T:
        depth = int(getattr(self._local, "budget_depth", 0))
        if depth > 0:
            return operation()
        with self.budget:
            self._local.budget_depth = depth + 1
            try:
                return operation()
            finally:
                self._local.budget_depth = depth


_shared_resources: Optional[_SharedHttpResources] = None
_shared_resources_lock = threading.Lock()


def _get_or_create_shared_resources() -> _SharedHttpResources:
    global _shared_resources
    with _shared_resources_lock:
        if _shared_resources is None:
            budget = int(get_settings().LLM_HTTP_MAX_CONCURRENCY)
            _shared_resources = _SharedHttpResources(budget)
        return _shared_resources


async def run_shared_http_call(operation: Callable[[], T]) -> T:
    """在线程池执行阻塞 HTTP 操作，并与同步旁路共享全进程并发预算。"""

    resources = _get_or_create_shared_resources()
    future = resources.executor.submit(resources.run_with_budget, operation)
    return await asyncio.wrap_future(future)


def run_shared_http_call_sync(operation: Callable[[], T]) -> T:
    """执行同步 HTTP 操作，并与异步质控主链共享全进程并发预算。"""

    return _get_or_create_shared_resources().run_with_budget(operation)


def close_shared_http_resources() -> None:
    """幂等关闭共享 HTTP 连接池；后续调用会按当前配置重新创建。"""

    global _shared_resources
    with _shared_resources_lock:
        resources = _shared_resources
        _shared_resources = None
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


def _post_json(
    client: httpx.Client,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
) -> Dict[str, Any]:
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
        )
    )
