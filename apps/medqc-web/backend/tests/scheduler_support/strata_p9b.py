"""仅测试使用的显式合成部署合同；不能打包或用于真实计量。"""
from dataclasses import replace
import hashlib
import json
import os

from app.services import llm_token_budget as budget
from app.services.strata_protocol import StrataModelIdentity, endpoint_identity
from tests.unit.test_context_token_budget import capability, identity


def install_mock_profile(monkeypatch, profile):
    if profile.provider_code != 'strata':
        return profile
    key = hashlib.sha256((profile.name + profile.model).encode()).hexdigest()[:16]
    cap = profile.context_budget or capability(profile=profile.name, model=profile.model,
        context_tokens=131072, counter_id='p9b-mock-' + key,
        verified_message_shapes=('user', 'user|user'))
    attestation = profile.model_identity or StrataModelIdentity(model=profile.model,
        model_revision=cap.model_revision, endpoint_sha256=endpoint_identity(profile.api_endpoint),
        evidence_sha256='f'*64, verified=True)
    counters = dict(budget._COUNTERS)
    counters[cap.counter_id, cap.counter_revision] = (identity(cap), lambda _: 100)
    monkeypatch.setattr(budget, '_COUNTERS', counters)
    records = json.loads(os.getenv('LLM_GATEWAY_PROFILES_JSON', '[]'))
    records = [item for item in records if item['profile'] != profile.name]
    records.append(dict(profile=profile.name, provider_code='strata', model=profile.model,
        api_endpoint=profile.api_endpoint, context_budget=cap.model_dump(mode='json'), model_identity=attestation.model_dump()))
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps(records))
    return replace(profile, context_budget=cap, model_identity=attestation)


def configure_mock_profile_factory(monkeypatch, module, *, model='synthetic-model',
                                   profile='strata_first_pass', endpoint='http://strata.test/v1/chat/completions'):
    from app.llm_gateway.config import ProfileConfig
    original = getattr(module, "ProfileConfig", ProfileConfig)
    def configured(*args, **kwargs):
        return install_mock_profile(monkeypatch, original(*args, **kwargs))
    monkeypatch.setattr(module, 'ProfileConfig', configured, raising=False)
    install_mock_profile(monkeypatch, original(profile, 'gpu', 'strata', model, endpoint))
