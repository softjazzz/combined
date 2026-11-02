"""MQ启用检查：配置、实际独立服务心跳及Gateway只读接口。"""
from __future__ import annotations

import httpx

from .control import rabbitmq_settings
from .status import service_status
from .config import RabbitMQConfigurationError
from ..llm_dispatch.contracts import GATEWAY_RESOURCES_PATH


def readiness_snapshot(settings) -> dict:
    checks = {'broker_config': False, 'gateway_config': False, 'publisher': False,
              'worker': False, 'gateway': False}
    try:
        rabbitmq_settings(settings)
        checks['broker_config'] = True
        checks.update(service_status(settings))
    except (RabbitMQConfigurationError, ValueError, OSError):
        pass
    checks['gateway_config'] = (
        getattr(settings, 'LLM_DISPATCH_MODE', 'direct') == 'gateway'
        and bool(getattr(settings, 'LLM_GATEWAY_URL', None))
        and bool(getattr(settings, 'LLM_GATEWAY_TOKEN', None))
        and bool(getattr(settings, 'LLM_GATEWAY_PROFILE', None)
                 or getattr(settings, 'LLM_GATEWAY_PROFILES', None)))
    return {'checks': checks, 'ready': False, 'gateway_checked': False}


async def check_readiness(settings) -> dict:
    result = readiness_snapshot(settings)
    if result['checks']['gateway_config']:
        try:
            # 仅访问部署配置中的Gateway；拒绝重定向，不读取环境代理，不调用模型。
            base = str(settings.LLM_GATEWAY_URL).rstrip('/')
            async with httpx.AsyncClient(timeout=2.0, trust_env=False, follow_redirects=False) as client:
                health = await client.get(base + '/health')
                resources = await client.get(base + GATEWAY_RESOURCES_PATH,
                    headers={'Authorization': f'Bearer {settings.LLM_GATEWAY_TOKEN}'})
            items = resources.json().get('resources') if resources.status_code == 200 else None
            result['checks']['gateway'] = (
                health.status_code == 200 and isinstance(items, list) and bool(items)
                and all(isinstance(item, dict) and type(item.get('effective_max_inflight')) is int
                        and item['effective_max_inflight'] > 0 for item in items))
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            result['checks']['gateway'] = False
        result['gateway_checked'] = True
    result['ready'] = all(result['checks'].values())
    return result
