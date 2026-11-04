"""已审查P9-C交付的离线装配与现场身份核对；不实现第二套Tokenizer。"""
import asyncio
import atexit
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from types import ModuleType
from urllib.parse import urlsplit

import httpx

from .llm_counter_installation import CounterInstaller, TokenVector
from .llm_token_budget import BudgetCapability, BudgetError, BudgetVerdict, CounterIdentity
from .strata_protocol import P9_MODEL, StrataModelIdentity, endpoint_identity

APPROVAL_PATH = Path(__file__).resolve().parents[2] / 'config' / 'strata-qwen36-p9c-approved.json'
_LOCK = threading.RLock()
_RUNTIMES = {}


def configured_root():
    from ..core.settings import get_settings
    return os.getenv('STRATA_HANDOFF_DIR') or get_settings().STRATA_HANDOFF_DIR or None


def _fail(reason, model=P9_MODEL):
    from .llm_token_budget import note_budget_failure
    error = BudgetError(BudgetVerdict('CAPABILITY_UNVERIFIED', reason, 'strata_handoff', model))
    note_budget_failure(error)
    return error


class Handoff:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        approval = json.loads(APPROVAL_PATH.read_text(encoding='utf-8'))
        self.hashes = approval['files']
        for name, digest in self.hashes.items():
            path = (self.root / name).resolve(strict=True)
            if self.root not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise _fail('handoff_resource_hash_mismatch')
        self.raw = json.loads((self.root / 'provider-capability.json').read_text(encoding='utf-8'))
        self.identity = json.loads((self.root / 'model-identity.json').read_text(encoding='utf-8'))
        c, i = self.raw, self.identity
        if (c['provider'] != 'strata' or c['model'] != P9_MODEL or c['verified'] is not True
                or c['context_limit'] != approval['context_tokens'] or c['safety_margin'] < 64
                or c['model_revision'] != 'sha256:' + i['model']['sha256']
                or c['chat_template_revision'] != 'sha256:' + i['chat_template']['sha256']
                or c['tokenizer_sha256'] != i['tokenizer']['files']
                or i['api']['model_id_reported'] != P9_MODEL or i['api']['context_limit'] != c['context_limit']
                or i['model']['served_context'] != c['context_limit']):
            raise _fail('handoff_identity_mismatch')
        for name, digest in c['tokenizer_sha256'].items():
            if self.hashes.get('tokenizer/' + name) != digest:
                raise _fail('handoff_tokenizer_mismatch')
        if self.hashes['tokenizer/chat_template.jinja'] != i['chat_template']['sha256']:
            raise _fail('handoff_template_mismatch')
        self.vectors = json.loads((self.root / 'validation/test_vectors.json').read_text(encoding='utf-8'))
        self.corpus = json.loads((self.root / 'validation/corpus.json').read_text(encoding='utf-8'))

    def capability(self, profile):
        c = self.raw
        return BudgetCapability(profile=profile, provider='strata', model=c['model'],
            model_revision=c['model_revision'], context_tokens=c['context_limit'], safety_margin=c['safety_margin'],
            tokenizer_id=c['tokenizer_id'], tokenizer_revision=c['tokenizer_revision'],
            chat_template_id=c['chat_template_id'], chat_template_revision=c['chat_template_revision'],
            counter_id=c['counter_id'], counter_revision=c['counter_revision'],
            verified_message_shapes=tuple('|'.join(s) for s in c['verified_message_shapes']),
            verified=c['verified'], thinking_semantics=c['thinking_semantics'])

    def model_identity(self, endpoint):
        # 这是DSH服务器侧文件证明与部署端点绑定；实时GET核对由Runtime单独执行。
        return StrataModelIdentity(model=P9_MODEL, model_revision=self.raw['model_revision'],
            endpoint_sha256=endpoint_identity(endpoint),
            evidence_sha256=self.hashes['model-identity.json'], verified=True)


@lru_cache(maxsize=4)
def load_handoff(root):
    try:
        return Handoff(root)
    except BudgetError:
        raise
    except Exception:
        raise _fail('handoff_unavailable_or_invalid') from None


class HandoffRuntime:
    def __init__(self, handoff):
        self.handoff = handoff
        self.installer = CounterInstaller()
        self._lock = threading.RLock()
        self._counter = None
        self._attestation = {}

    def ensure_counter(self):
        with self._lock:
            if self._counter is not None:
                return self._counter
            h = self.handoff
            cap = h.capability('strata_handoff')
            def factory(root):
                # 只执行已固定SHA256且人工审查过的纯标准库模块，不执行integration_example。
                source_path = root / 'token_counter.py'
                source = source_path.read_bytes()
                if hashlib.sha256(source).hexdigest() != h.hashes['token_counter.py']:
                    raise _fail('counter_source_hash_mismatch')
                module = ModuleType('medqc_approved_qwen36_counter')
                module.__file__ = str(source_path)
                # 不使用SourceFileLoader：现场__pycache__不在可信交付白名单，不能加载其中字节码。
                exec(compile(source, str(source_path), 'exec'), module.__dict__)
                counter = module.TokenCounter(str(root / 'tokenizer'))
                actual = counter.identity()
                if (actual['counter_id'] != cap.counter_id or actual['counter_revision'] != cap.counter_revision
                        or actual['assets'] != h.raw['tokenizer_sha256']
                        or set(actual['verified_shapes']) != set(cap.verified_message_shapes)):
                    raise _fail('counter_runtime_identity_mismatch')
                for row in h.corpus:
                    if counter.count_text(row['text']) != row['ref_tokens']:
                        raise _fail('counter_text_vector_mismatch')
                def count(payload):
                    # strict json_schema被交付明确列为未验证，不因纯文本消息已验证而顺带放行。
                    response_format = payload.get('response_format')
                    if isinstance(response_format, dict) and response_format.get('type') == 'json_schema':
                        raise ValueError('strict_json_schema_unverified')
                    return counter.count_prompt_tokens(payload)
                return CounterIdentity(**{f: getattr(cap, f) for f in CounterIdentity.__dataclass_fields__}), count
            vectors = [TokenVector({'model': P9_MODEL, 'messages': [
                {'role': 'user', 'content': row['test_text']}],
                'chat_template_kwargs': {'enable_thinking': False}}, row['expected_prompt_tokens']) for row in h.vectors]
            self._counter = self.installer.install(capability=cap, resource_root=h.root, file_hashes=h.hashes,
                                                  factory=factory, vectors=vectors)
            return self._counter

    def verify_endpoint(self, endpoint, api_key, *, transport=None, ttl_seconds=60):
        with self._lock:
            parts = urlsplit(endpoint)
            if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password
                    or parts.query or parts.fragment or not api_key):
                raise _fail('deployment_identity_connection_invalid')
            base = endpoint.rstrip('/').removesuffix('/chat/completions')
            key = (endpoint_identity(base), hashlib.sha256(api_key.encode()).hexdigest())
            if self._attestation.get(key, 0) > time.monotonic():
                return
            try:
                with httpx.Client(transport=transport, trust_env=False, follow_redirects=False, timeout=5) as client:
                    headers = {'Authorization': 'Bearer ' + api_key}
                    models_response = client.get(base + '/models', headers=headers)
                    health_response = client.get(f'{parts.scheme}://{parts.netloc}/health', headers=headers)
                    models_response.raise_for_status()
                    health_response.raise_for_status()
                    models, health = models_response.json(), health_response.json()
                selected = [row for row in models['data'] if row.get('id') == P9_MODEL]
                if (len(selected) != 1 or selected[0].get('status', {}).get('value') != 'loaded'
                        or type(selected[0].get('meta', {}).get('n_ctx')) is not int
                        or selected[0]['meta']['n_ctx'] != self.handoff.raw['context_limit']
                        or health.get('status') != 'ok' or health.get('loaded') is not True
                        or health.get('model') != P9_MODEL or health.get('service') != 'strata'
                        or type(health.get('max_context')) is not int
                        or health['max_context'] != self.handoff.raw['context_limit']):
                    raise _fail('deployment_identity_mismatch')
            except BudgetError:
                raise
            except Exception:
                raise _fail('deployment_identity_unavailable') from None
            self._attestation[key] = time.monotonic() + max(0, min(ttl_seconds, 300))


def runtime_for(root):
    with _LOCK:
        normalized = str(Path(root).resolve())
        if normalized not in _RUNTIMES:
            _RUNTIMES[normalized] = HandoffRuntime(load_handoff(normalized))
        return _RUNTIMES[normalized]


async def ensure_counter(root):
    if root:
        await asyncio.to_thread(runtime_for(root).ensure_counter)


async def ensure_endpoint(root, endpoint, api_key, *, transport=None):
    if root:
        await asyncio.to_thread(runtime_for(root).verify_endpoint, endpoint, api_key, transport=transport)


def close_runtimes():
    with _LOCK:
        for runtime in _RUNTIMES.values():
            runtime.installer.close()
        _RUNTIMES.clear()
        load_handoff.cache_clear()


atexit.register(close_runtimes)
