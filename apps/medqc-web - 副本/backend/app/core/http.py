import ipaddress
import socket
from typing import Dict, Any, Optional
import httpx

from .settings import get_settings


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


async def safe_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
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

    # 显式禁用环境代理，避免 SOCKS 代理导致的 socksio 包缺失问题
    async with httpx.AsyncClient(timeout=timeout_seconds, trust_env=False) as client:
        resp = await client.post(url, headers=headers, json=payload)
        # 不直接 raise，尽量返回上游的 JSON 错误体，供调用方包装
        try:
            body = resp.json() if resp.text else {}
        except Exception:
            body = {"text": resp.text}
        if resp.status_code >= 400:
            return {"__status__": resp.status_code, "__error__": True, "body": body}
        return body

