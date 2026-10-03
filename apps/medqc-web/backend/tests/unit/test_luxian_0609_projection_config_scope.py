"""保存操作内复用安全引用密钥，同时保留跨操作配置更新。"""

import json
from datetime import datetime
from types import SimpleNamespace

import app.services.custom_qc_workspace_service as workspace
import app.services.qc_workspace.canonical_result_store as canonical


class CaptureSession:
    def __init__(self):
        self.envelopes = []

    def get_bind(self):
        # 非 PostgreSQL 方言：Canonical 写入跳过 advisory lock。
        return SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))

    def execute(self, statement):
        params = statement.compile().params
        if 'envelope_json' in params:
            self.envelopes.append(json.loads(params['envelope_json']))


def item(visit=0, rule=1):
    return {
        'record_id': f'visit-{visit}', 'visit_id': f'visit-{visit}',
        'institute_id': 'synthetic-inst', 'patient_id': f'patient-{visit}',
        'rule_id': f'LX0609-{rule:03d}', 'status': 'compliant',
        'result_status': 'compliant', 'display_status': 'compliant',
        'is_compliant': True, 'reason_code': 'requirement_satisfied',
        'customer_evidence': [{
            'source_type': 'daily_course_record',
            'source_document_id': f'doc-{visit}',
            'field_path': 'record_content', 'evidence_excerpt': '合成病程依据',
        }],
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
    saved = write(monkeypatch, [item(v, r) for v in range(30) for r in range(1, 73)])
    assert len(saved) == 30
    assert sum(len(e['items']) for e in saved) == 2160
    assert len(calls) == 1


def test_next_save_sees_new_key_and_same_operation_keeps_one_key(monkeypatch):
    keys = iter(['first-synthetic-key', 'second-synthetic-key'])
    monkeypatch.setattr(canonical, 'get_settings', lambda: SimpleNamespace(JWT_SECRET=next(keys)))
    first = write(monkeypatch, [item()])[0]
    second = write(monkeypatch, [item()])[0]
    for envelope, key in [(first, 'first-synthetic-key'), (second, 'second-synthetic-key')]:
        projected = canonical.envelope_item_from_rule_result(item(), hmac_key=key)
        assert envelope['items'] == [projected]
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
