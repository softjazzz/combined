"""Strata P9-B机械传输协议；不改变Prompt、证据或临床状态。"""
from copy import deepcopy
import hashlib
import json
import os

from pydantic import BaseModel, ConfigDict, Field

from .llm_dispatch.provider_profiles import ProviderConfigurationError

PROTOCOL_VERSION = 'strata-p9b-v1'
GREEDY = {'temperature': 0, 'top_k': 1, 'top_p': 1, 'presence_penalty': 0,
          'frequency_penalty': 0, 'repetition_penalty': 1}
SAFE_ERROR_CODES = frozenset({'llm_context_over_budget', 'strata_output_truncated',
    'strata_structured_output_failed', 'strata_model_identity_mismatch',
    'strata_model_identity_missing', 'strata_model_not_registered', 'strata_output_budget_insufficient',
    'strata_invalid_response'})


class StrataProtocolError(ProviderConfigurationError):
    retryable = False
    request_started = False

    def __init__(self, code, *, terminal=False):
        self.reason = code if code in SAFE_ERROR_CODES else 'strata_model_identity_missing'
        self.code = {
            'strata_output_truncated': 'llm_context_budget_exhausted',
            'strata_invalid_response': 'llm_context_budget_exhausted',
            'strata_output_budget_insufficient': 'llm_context_over_budget',
            'strata_model_identity_mismatch': 'llm_context_capability_unverified',
            'strata_model_identity_missing': 'llm_context_capability_unverified',
            'strata_model_not_registered': 'llm_context_capability_unverified',
        }.get(self.reason, self.reason)
        if terminal and self.reason == 'strata_structured_output_failed':
            self.code = 'llm_context_budget_exhausted'
        super().__init__(self.reason)
        from .llm_token_budget import note_budget_failure
        note_budget_failure(self)


def validate_model_selection(model, allowed_models):
    if (not isinstance(model, str) or not model.strip() or model != model.strip()
            or len(model) > 256 or any(ord(c) < 32 for c in model)):
        raise StrataProtocolError('strata_model_not_registered')
    if allowed_models is not None and (not isinstance(allowed_models, (list, tuple, set, frozenset))
                                       or model not in allowed_models):
        raise StrataProtocolError('strata_model_not_registered')


def prepare_request(payload):
    """仅由Strata分支调用；显式覆盖采样和Thinking，不修改正文和输出上限。"""
    result = deepcopy(payload)
    validate_model_selection(result.get('model'), None)
    result.update(GREEDY)
    result.pop('enable_thinking', None)
    result.pop('thinking_budget', None)
    result.pop('thinking', None)
    result.pop('reasoning_effort', None)
    result['chat_template_kwargs'] = {'enable_thinking': False}
    return result


def upstream_error(status, body):
    """只识别固定错误码，不把上游正文或病历写入异常。"""
    if not isinstance(body, dict):
        return None
    nested = body.get('error')
    code = (nested.get('code') or nested.get('type')) if isinstance(nested, dict) else body.get('code')
    if code in {'context_length_exceeded', 'context_window_exceeded', 'context_limit_exceeded'}:
        return StrataProtocolError('llm_context_over_budget')
    if status == 502 and code == 'structured_output_failed':
        return StrataProtocolError('strata_structured_output_failed')
    return None


def validate_result(result, model):
    if isinstance(result, dict) and result.get('__error__') is True:
        error = upstream_error(result.get('__status__'), result.get('body'))
        if error is not None:
            error.request_started = True
            raise error
        return  # 未知HTTP错误仍由原客户端处理。
    if not isinstance(result, dict) or not isinstance(result.get('model'), str):
        error = StrataProtocolError('strata_model_identity_missing')
    elif result['model'] != model:
        error = StrataProtocolError('strata_model_identity_mismatch')
    else:
        choices = result.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            error = StrataProtocolError('strata_invalid_response')
        elif choices[0].get('finish_reason') == 'length':
            error = StrataProtocolError('strata_output_truncated')
        elif (len(choices) != 1 or choices[0].get('finish_reason') != 'stop'
                or not isinstance(choices[0].get('message'), dict)
                or not isinstance(choices[0]['message'].get('content'), str)
                or not choices[0]['message']['content'].strip()
                or choices[0]['message'].get('tool_calls')):
            error = StrataProtocolError('strata_invalid_response')
        else:
            return
    error.request_started = True
    raise error


def fixed_probe_result(result, expected_model, *, require_draft_activity=False):
    """仅固定探针可要求draft活动；业务观测中的0不是失败。"""
    validate_result(result, expected_model)
    timings = result.get('timings')
    value = timings.get('draft_n') if isinstance(timings, dict) else None
    valid = type(value) is int and value >= 0
    return {'response_model_matches': True, 'draft_n': value if valid else None,
            'draft_field_verified': valid, 'passed': valid and (value > 0 or not require_draft_activity),
            'protocol': PROTOCOL_VERSION}


class StrataModelIdentity(BaseModel):
    """DSH交付后由部署者核验填写；响应model回显不能替代此离线身份合同。"""
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    model: str = Field(min_length=1, max_length=256)
    model_revision: str = Field(min_length=1)
    endpoint_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    evidence_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    verified: bool = False


def endpoint_identity(endpoint):
    normalized = str(endpoint or '').rstrip('/').removesuffix('/chat/completions')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def require_deployment_identity(model, endpoint, capability, identity):
    if (not isinstance(identity, StrataModelIdentity) or identity.verified is not True
            or identity.model != model or identity.endpoint_sha256 != endpoint_identity(endpoint)
            or capability is None or capability.model_revision != identity.model_revision):
        raise StrataProtocolError('strata_model_identity_missing')


def deployed_identity(provider, model, profile, endpoint):
    # 复用已登记Profile目录，不进行网络发现，不接受客户端提供的身份。
    try:
        entries = json.loads(os.getenv('LLM_GATEWAY_PROFILES_JSON', '[]'))
        if isinstance(entries, dict):
            entries = [{'profile': key, **value} for key, value in entries.items()]
        matches = [item for item in entries if item.get('provider_code') == provider
                   and item.get('model') == model and item.get('profile') == profile
                   and (endpoint is None or endpoint_identity(item.get('api_endpoint')) == endpoint_identity(endpoint))]
        return StrataModelIdentity.model_validate(matches[0]['model_identity']) if len(matches) == 1 else None
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
