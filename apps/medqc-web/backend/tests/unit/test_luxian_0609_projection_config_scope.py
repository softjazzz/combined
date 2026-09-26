"""保存操作内复用安全引用密钥，同时保留跨操作配置更新。"""

import json
from datetime import datetime
from functools import lru_cache
from types import SimpleNamespace

import pytest

import app.core.settings as settings_module
import app.services.custom_qc_workspace_service as workspace
import app.services.luxian_0609.customer_text_publication as publication
import app.services.qc_workspace.canonical_result_store as canonical
from tests.luxian_0609_published_result_support import published_lx0609_items


@lru_cache(maxsize=1)
def _published_templates():
    """正式执行链发布的合法结果：001 合规、004 合规、暂停 03-01-01 not_executed。"""

    return tuple(published_lx0609_items(include_paused_consultation=True).values())


class CaptureSession:
    def __init__(self):
        self.envelopes = []

    def execute(self, statement):
        params = statement.compile().params
        if 'envelope_json' in params:
            self.envelopes.append(json.loads(params['envelope_json']))


def item(visit=0, rule=1):
    # 病例坐标不在文案签章内；按就诊替换坐标即可复用同一已发布结果。
    return {
        **_published_templates()[rule - 1],
        'record_id': f'visit-{visit}', 'visit_id': f'visit-{visit}',
        'institute_id': 'synthetic-inst', 'patient_id': f'patient-{visit}',
    }


def write(monkeypatch, items):
    monkeypatch.setattr(workspace, 'diagnostic_capture_enabled', lambda: False)
    service = workspace.CustomQCWorkspaceService.__new__(workspace.CustomQCWorkspaceService)
    service._record_result_envelope_table = workspace._record_result_envelopes_table()
    session = CaptureSession()
    service._write_record_result_envelopes(
        session, job_row={'id': 'synthetic-job', 'created_by': 'synthetic-user',
                          'filters_json': '{}'},
        items=items, now=datetime(2026, 9, 10),
    )
    return session.envelopes


def test_2160_items_read_projection_settings_once(monkeypatch):
    calls = []
    def settings():
        calls.append(1)
        return SimpleNamespace(JWT_SECRET='synthetic-key')
    monkeypatch.setattr(canonical, 'get_settings', settings)
    # 签章按发布时的真实配置生成；先完成发布，只计数保存阶段且不替换密钥。
    _published_templates()
    publication_calls = []
    real_settings = settings_module.get_settings
    def publication_settings():
        publication_calls.append(1)
        return real_settings()
    monkeypatch.setattr(publication, 'get_settings', publication_settings)
    rules = len(_published_templates())
    visits = 2160 // rules
    saved = write(monkeypatch, [item(v, r) for v in range(visits) for r in range(1, rules + 1)])
    assert len(saved) == visits
    assert sum(len(e['items']) for e in saved) == 2160
    assert len(calls) == 1
    # 2160 条均带发布签章并逐条校验，但一次保存只读取一次签章密钥。
    assert all('customer_text_seal' in entry for e in saved for entry in e['items'])
    assert len(publication_calls) == 1


def test_publication_key_is_reused_within_save_and_reread_after_rotation(monkeypatch):
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='synthetic-key'))
    real_settings = settings_module.get_settings
    _published_templates()
    reads = []
    rotated = SimpleNamespace(JWT_SECRET='rotated-publication-key')
    def publication_settings():
        reads.append(1)
        return real_settings() if len(reads) == 1 else rotated
    monkeypatch.setattr(publication, 'get_settings', publication_settings)

    first = write(monkeypatch, [item(v, r) for v in range(3) for r in (1, 2, 3)])
    assert len(first) == 3 and len(reads) == 1
    # 下一次保存必须重新读取配置；密钥已轮换，旧签章不再成立而被拒绝，不重新签章。
    with pytest.raises(ValueError, match='客户结果解释合同不完整'):
        write(monkeypatch, [item()])
    assert len(reads) == 2


def test_save_rejects_tampered_published_text_within_reused_key_batch(monkeypatch):
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='synthetic-key'))
    batch = [item(v, r) for v in range(3) for r in (1, 2, 3)]
    tampered = next(entry for entry in batch if entry.get('findings'))
    tampered['findings'] = tampered['findings'] + '（改写）'
    with pytest.raises(ValueError, match='客户结果解释合同不完整'):
        write(monkeypatch, batch)


def test_operation_publication_key_reads_config_lazily_once(monkeypatch):
    reads = []
    def publication_settings():
        reads.append(1)
        return SimpleNamespace(JWT_SECRET='lazy-key')
    monkeypatch.setattr(publication, 'get_settings', publication_settings)
    provider = publication.operation_publication_key()
    assert reads == []
    assert provider() == provider() == b'lazy-key'
    assert len(reads) == 1
    assert publication.operation_publication_key()() == b'lazy-key'
    assert len(reads) == 2


def test_save_rejects_published_result_missing_rule_facts(monkeypatch):
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='synthetic-key'))
    broken = item()
    assert broken['customer_display_facts']
    broken['customer_display_facts'] = None
    with pytest.raises(ValueError, match='客户结果解释合同不完整'):
        write(monkeypatch, [broken])


def test_next_save_sees_new_key_and_same_operation_keeps_one_key(monkeypatch):
    keys = iter(['first-synthetic-key', 'second-synthetic-key'])
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET=next(keys)))
    first = write(monkeypatch, [item()])[0]
    second = write(monkeypatch, [item()])[0]
    for envelope, key in [(first, 'first-synthetic-key'), (second, 'second-synthetic-key')]:
        projected = canonical.envelope_item_from_rule_result(item(), hmac_key=key)
        # Store 以三坐标 Envelope 身份统一覆盖规则项 record_ref，其余字段与投影一致。
        assert envelope['items'] == [{**projected, 'record_ref': envelope['record_ref']}]
        ref = workspace.CaseRef.from_mapping(item())
        assert envelope['record_ref'] == canonical.keyed_ref('rec', ref.as_key(), hmac_key=key)
    assert first['record_ref'] != second['record_ref']
    assert first['items'][0]['evidence'] != second['items'][0]['evidence']


def test_explicit_key_preserves_projection_and_does_not_read_config(monkeypatch):
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='same-synthetic-key'))
    before = canonical.envelope_item_from_rule_result(item())
    def forbidden():
        raise AssertionError('显式操作密钥不应再次读取配置')
    monkeypatch.setattr(canonical, 'get_settings', forbidden)
    after = canonical.envelope_item_from_rule_result(item(), hmac_key='same-synthetic-key')
    assert after == before
    assert after['evidence']
