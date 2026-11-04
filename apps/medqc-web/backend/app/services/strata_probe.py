"""固定虚构探针，绝不由正式业务请求自动触发。"""
import json

from .llm_dispatch.provider_profiles import ProviderConfigurationError
from .strata_protocol import fixed_probe_result

PROBE_PROMPT = '这是无患者数据的传输探针。请只返回JSON：{"probe":"p9b"}。'


async def run_fixed_probe(client, *, require_draft_activity=True):
    if getattr(client, 'provider_code', None) != 'strata':
        raise ProviderConfigurationError('strata_probe_requires_registered_local_client')
    # 仍走同一个客户端的身份、最终计量、超时及请求预算，不开另一条HTTP通道。
    response = await client.generate(PROBE_PROMPT, max_completion_tokens=128,
                                     allow_length_retry=False, enable_thinking=False, temperature=0)
    report = fixed_probe_result(response, client.model, require_draft_activity=require_draft_activity)
    try:
        content_verified = json.loads(response['choices'][0]['message']['content']) == {'probe': 'p9b'}
    except (ValueError, KeyError, TypeError, IndexError):
        content_verified = False
    return {**report, 'fixed_content_verified': content_verified,
            'passed': report['passed'] and content_verified}
