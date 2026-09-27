"""保存操作内复用安全引用密钥，同时保留跨操作配置更新。"""

import json
from datetime import datetime
from functools import lru_cache
from types import SimpleNamespace

import pytest

import app.services.custom_qc_workspace_service as workspace
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
    rules = len(_published_templates())
    visits = 2160 // rules
    saved = write(monkeypatch, [item(v, r) for v in range(visits) for r in range(1, rules + 1)])
    assert len(saved) == visits
    assert sum(len(e['items']) for e in saved) == 2160
    assert len(calls) == 1
    # 结果签章已取消：保存结果不含签章字段。
    assert all('customer_text_seal' not in entry for e in saved for entry in e['items'])


def test_save_ignores_deprecated_text_seal_field(monkeypatch):
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='synthetic-key'))
    plain = write(monkeypatch, [item()])[0]
    legacy = dict(item())
    legacy['customer_text_seal'] = 'lx0609-customer-text-v1:' + '0' * 64
    with_deprecated = write(monkeypatch, [legacy])[0]
    # 废弃签章不校验、不落库，也不改变其余业务结果。
    assert with_deprecated == plain


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


def _saved_under_key_a_then_rotated_to_b(monkeypatch):
    """密钥 A 下经正式保存入口写入合法结果，随后服务配置切换为密钥 B。"""

    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session

    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    monkeypatch.setattr(workspace, 'diagnostic_capture_enabled', lambda: False)
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='key-a'))
    service = workspace.CustomQCWorkspaceService.__new__(workspace.CustomQCWorkspaceService)
    service._record_result_envelope_table = table
    items = [item(0, rule) for rule in (1, 2, 3)]
    case = {'institute_id': 'synthetic-inst', 'patient_id': 'patient-0', 'visit_id': 'visit-0'}
    filters = {'rule_set_key': 'luxian_0609_qc_v1', 'rule_set_version': '2026-06-09',
               'record_refs': [case]}
    with Session(engine) as session:
        service._write_record_result_envelopes(
            session,
            job_row={'id': 'rotation-job', 'created_by': 'synthetic-user',
                     'filters_json': json.dumps(filters)},
            items=items, now=datetime(2026, 9, 26),
        )
        session.commit()
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET='key-b'))
    store = canonical.CanonicalResultStore(table)
    job = {'id': 'rotation-job', 'created_by': 'synthetic-user', 'status': 'completed',
           'total_records': 1, 'filters': filters}
    return engine, store, case, job, items


def test_legal_history_stays_readable_after_service_key_rotation(monkeypatch):
    from sqlalchemy.orm import Session

    engine, store, case, job, items = _saved_under_key_a_then_rotated_to_b(monkeypatch)
    with Session(engine) as session:
        latest = store.load_selected(
            session, root_job_id='rotation-job', rule_set_key='luxian_0609_qc_v1',
            rule_set_version='2026-06-09', **case,
        )
    batch = store.load_root_job_items(job=job, session_factory=lambda: Session(engine))
    assert [x['rule_id'] for x in latest['items']] == [x['rule_id'] for x in items]
    assert [x['rule_id'] for x in batch] == [x['rule_id'] for x in items]
    # 读取不重新生成历史病历引用，反馈等既有绑定保持原值。
    assert {x['record_ref'] for x in batch} == {latest['record_ref']}
    assert latest['record_ref'] == canonical.keyed_ref(
        'rec', canonical.CaseRef(**case).as_key(), hmac_key='key-a',
    )
    engine.dispose()
