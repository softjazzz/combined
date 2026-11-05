"""部署级模型出口策略；不读取系统代理，不改变 Provider 或请求内容。"""

from dataclasses import dataclass, field
import re
from urllib.parse import urlsplit


class LLMProxyConfigurationError(ValueError):
    """固定错误码，禁止回显配置（可能含误填的凭据）。"""


def _hostname(value: str) -> str:
    try:
        name = value.rstrip('.').encode('idna').decode('ascii').lower()
    except (UnicodeError, AttributeError):
        raise LLMProxyConfigurationError('llm_http_proxy_invalid_host') from None
    if len(name) > 253 or not all(
        re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
        for part in name.split('.')
    ):
        raise LLMProxyConfigurationError('llm_http_proxy_invalid_host')
    return name


@dataclass(frozen=True)
class LLMHTTPProxyPolicy:
    # 首期仅支持现场 HTTP CONNECT 代理，不接受内嵌凭据。
    url: str = field(default='', repr=False)
    hosts: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def parse(cls, url: str | None = None, hosts: str | None = None):
        url, hosts = (url or '').strip(), (hosts or '').strip()
        if not url and not hosts:
            return cls()
        if not url or not hosts:
            raise LLMProxyConfigurationError('llm_http_proxy_incomplete')
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == 'http' and parsed.hostname and parsed.port
                and not parsed.username and not parsed.password
                and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                and not any(c.isspace() or ord(c) < 32 for c in url)
                and '\\' not in url
            )
            if not valid:
                raise ValueError()
            _hostname(parsed.hostname)
        except ValueError:
            raise LLMProxyConfigurationError('llm_http_proxy_invalid_url') from None
        parts = hosts.split(',')
        normalized = frozenset(_hostname(part.strip()) for part in parts)
        return cls(url=url, hosts=normalized)

    def matches(self, url: str) -> bool:
        if not self.url:
            return False
        try:
            parsed = urlsplit(url)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username or parsed.password or '\\' in url
                    or any(c.isspace() or ord(c) < 32 for c in url)):
                raise ValueError()
            # 用与实际 HTTP 客户端一致的 URL 规范化，拒绝无法解释的端口。
            _ = parsed.port
            host = parsed.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        except (ValueError, UnicodeError):
            raise LLMProxyConfigurationError('llm_http_proxy_invalid_target') from None
        return host in self.hosts

    def client_options(self, url: str, *, transport=None, proxy_transport=None) -> dict:
        """显式测试 transport 优先；不能让 HTTPX 代理 mount 绕过隔离 transport。"""
        if not self.matches(url):
            return {'transport': transport} if transport is not None else {}
        if proxy_transport is not None:
            return {'transport': proxy_transport}
        if transport is not None:
            raise LLMProxyConfigurationError('llm_http_proxy_transport_required')
        return {'proxies': self.url}
