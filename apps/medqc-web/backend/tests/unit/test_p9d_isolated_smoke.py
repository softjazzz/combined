"""虚构病例全目录经过真实执行及保存；模型仅固定协议失败，不声称质量验收。"""
import json

import pytest

from scripts import p9d_isolated_smoke as smoke


@pytest.mark.asyncio
async def test_formal_synthetic_smoke_preserves_successes_and_reports_model_failures(tmp_path, monkeypatch):
    from app.core.settings import Settings
    from app.services import sample_programmatic_evidence as fallback
    class FixedClient:
        provider_code = 'alibaba'
        model = 'synthetic-fixed-response'
        model_role = 'adjudicator'
        custom_parameters = {}
        temperature = 0
        calls = 0
        async def generate(self, *args, **kwargs):
            self.calls += 1
            # 固定协议错误用于确认失败不会伪装合规；非模型医学答案。
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}}
    for name in ('_fetch_source_table_fallback_items', '_fetch_detail_service_fallback_items'):
        monkeypatch.setattr(fallback, name, lambda *_a, **_k: pytest.fail('不能读外部源'))
    client = FixedClient()
    report = await smoke.run_formal(client, Settings(_env_file=None, JWT_SECRET='synthetic'), tmp_path, in_memory=True)
    assert client.calls > 0
    assert len(report['selected_rule_ids']) == len(report['results'])
    assert len(report['results']) == len({r['rule_id'] for r in report['results']})
    assert report['saved_results'], '确定性成功不能被模型失败丢掉'
    assert report['persistence_failures'], '固定无效模型协议必须体现未完成'
    assert not [f for f in report['persistence_failures'] if f['reason'] == 'canonical_save_or_read_failed']
    assert not (tmp_path / 'results.sqlite').exists()
    assert json.loads((tmp_path / 'report.json').read_text(encoding='utf-8')) == report


def test_source_is_fixed_synthetic_and_does_not_accept_external_material():
    rows = smoke.synthetic_sources()
    assert rows['first_course_record'][0]['id'] == 'first-synthetic'
    assert rows['exam_master'][0]['exam_id'] == 'exam-synthetic'
    with pytest.raises(ValueError, match='loopback'):
        smoke.configure('unused', None, 'http://example.com/v1')
