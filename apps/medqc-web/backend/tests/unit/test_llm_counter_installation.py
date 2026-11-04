"""精确Counter装配接口；资源、计数及向量全部是合成夹具，不能用于部署。"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import threading

import pytest

from app.services.llm_counter_installation import CounterInstaller, TokenVector
from app.services.llm_token_budget import assess_payload
from tests.unit.test_context_token_budget import capability, identity, payload


def fixture(tmp_path):
    root = tmp_path / 'synthetic-counter'
    root.mkdir()
    resource = b'synthetic-reviewed-resource-not-a-real-tokenizer'
    (root / 'fixture.txt').write_bytes(resource)
    return root, {'fixture.txt': hashlib.sha256(resource).hexdigest()}


def test_registration_validates_all_vectors_without_changing_them_and_closes(tmp_path):
    cap = capability()
    root, hashes = fixture(tmp_path)
    vectors = [TokenVector(payload(), 100), TokenVector({**payload(), 'max_tokens': 12}, 100)]
    before = deepcopy(vectors)
    loads = []
    def load(path):
        loads.append(path)
        return identity(cap), lambda _: 100
    installer = CounterInstaller()
    try:
        result = installer.install(capability=cap, resource_root=root, file_hashes=hashes,
                                   factory=load, vectors=vectors)
        assert result.validated_vectors == 2 and loads == [root.resolve()]
        assert vectors == before
        assert assess_payload('strata', cap.profile, payload(), cap, enabled=True).status == 'ACCEPT'
    finally:
        installer.close()
    assert assess_payload('strata', cap.profile, payload(), cap, enabled=True).status == 'COUNT_UNAVAILABLE'


@pytest.mark.parametrize('failure', ['hash', 'missing', 'outside', 'model', 'template', 'vector', 'mutation', 'unverified'])
def test_failed_installation_never_registers_a_fake_counter(tmp_path, failure):
    cap = capability()
    root, hashes = fixture(tmp_path)
    counter_identity = identity(cap)
    if failure == 'hash':
        hashes['fixture.txt'] = '0'*64
    elif failure == 'missing':
        hashes = {'absent.txt': '0'*64}
    elif failure == 'outside':
        hashes = {'../outside.txt': '0'*64}
    elif failure in {'model', 'template'}:
        from dataclasses import replace
        counter_identity = replace(counter_identity, **({'model': 'other'} if failure == 'model'
                                                       else {'chat_template_revision': 'other'}))
    elif failure == 'unverified':
        cap = cap.model_copy(update={'verified': False})
    def count(value):
        if failure == 'mutation':
            value['messages'].clear()
        return 99 if failure == 'vector' else 100
    installer = CounterInstaller()
    try:
        with pytest.raises(ValueError):
            installer.install(capability=cap, resource_root=root, file_hashes=hashes,
                factory=lambda _: (counter_identity, count), vectors=[TokenVector(payload(), 100)])
        assert assess_payload('strata', cap.profile, payload(), capability(), enabled=True).status == 'COUNT_UNAVAILABLE'
    finally:
        installer.close()


def test_concurrent_initialization_loads_once_and_serializes_counter(tmp_path):
    cap = capability()
    root, hashes = fixture(tmp_path)
    installer = CounterInstaller()
    loads, active, peak = [], 0, 0
    def count(_):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        # Event.wait只让出线程，不连接任何模型或服务。
        threading.Event().wait(.001)
        active -= 1
        return 100
    def factory(_):
        loads.append(1)
        return identity(cap), count
    def install(_):
        return installer.install(capability=cap, resource_root=root, file_hashes=hashes,
                                 factory=factory, vectors=[TokenVector(payload(), 100)])
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            installed = list(pool.map(install, range(16)))
            verdicts = list(pool.map(lambda _: assess_payload('strata', cap.profile, payload(), cap, enabled=True), range(32)))
        assert len(loads) == 1 and all(item is installed[0] for item in installed)
        assert all(item.status == 'ACCEPT' for item in verdicts) and peak == 1
    finally:
        installer.close()
