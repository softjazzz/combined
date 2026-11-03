"""DSH专用入口：固定虚构材料→原正式执行链→独立SQLite；不接受患者输入。"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime
import html
import json
import logging
import os
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def synthetic_sources():
    """唯一可导入材料，固定为虚构病例；不是患者脱敏副本。"""
    return {
        'inpat_registration': ({'id': 'reg-synthetic', 'admission_datetime': '2026-01-01 08:00:00',
                                'discharge_datetime': '2026-01-04 12:00:00'},),
        'inpat_registration.discharge_horizon': ({'discharge_datetime': '2026-01-04 12:00:00'},),
        'evaluation_context.horizon': ({'horizon_datetime': '2026-01-04 12:00:00', 'horizon_date': '2026-01-04'},),
        'admission_record': ({'id': 'admission-synthetic', 'record_time': '2026-01-01 10:00:00',
            'record_content': '虚构验收患者。因咳嗽入院，拟完善胸部CT检查。无手术及输血。'},),
        'first_course_record': ({'id': 'first-synthetic', 'record_time': '2026-01-01 11:00:00',
            'record_content': '虚构验收患者首次病程。诊断考虑肺部感染。诊疗计划：完善胸部CT并对症治疗。'},),
        'exam_master': ({'id': 'exam-synthetic', 'exam_id': 'exam-synthetic', 'exam_name': '胸部CT',
            'exam_datetime': '2026-01-02 09:00:00', 'report_datetime': '2026-01-02 10:00:00',
            'report_time': '2026-01-02 10:00:00', 'exam_result': '右肺下叶少许炎性渗出。',
            'report_content': '右肺下叶少许炎性渗出。'},),
        'daily_course_record': ({'id': 'course-synthetic', 'record_time': '2026-01-02 12:00:00',
            'record_content': '胸部CT已回报，右肺下叶少许炎性渗出。结合咳嗽考虑肺部感染，继续对症治疗。'},),
        'discharge_record': ({'id': 'discharge-synthetic', 'record_time': '2026-01-04 13:00:00',
            'record_content': '虚构病例，症状改善出院，嘱门诊复诊。出院诊断：肺部感染。'},),
    }


def configure(root, state, endpoint):
    """不读.env，不启动Worker/定时器；只在新建独立状态目录内写入。"""
    host = urlsplit(endpoint).hostname
    if host not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('isolated_smoke_requires_loopback_ssh_tunnel')
    os.environ.update(STRATA_HANDOFF_DIR=str(root), LLM_DISPATCH_MODE='direct',
        LLM_LOCAL_TOKEN_BUDGET_ENABLED='true', LX0609_TOKEN_SPLIT_ENABLED='true', OUTBOUND_ALLOWLIST=json.dumps([host]),
        DATABASE_URL='', REMOTE_DB_URL='', JWT_SECRET='p9d-fictional-isolated-not-production',
        LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR=str(state / 'freeze-exam'),
        LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR=str(state / 'freeze-antimicrobial'),
        LUXIAN_0609_OPINION_FREEZE_DIR=str(state / 'freeze-opinion'),
        LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR=str(state / 'freeze-consultation'),
        LLM_GATEWAY_PROFILES_JSON=json.dumps({'p9d_qwen36': {'provider_code': 'strata',
            'resource_id': 'p9d_local', 'model': 'qwen3.6-35b-a3b',
            'api_endpoint': endpoint.rstrip('/') + '/chat/completions'}}))
    from app.core.settings import Settings, get_settings
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    # 所有已注册的冻结目录都定向到本次新目录，拒绝继承现场业务冻结。
    for field in type(settings).model_fields:
        if 'FREEZE' in field and field.endswith('_DIR'):
            setattr(settings, field, str(state / 'freezes' / field.lower()))
            os.environ[field] = str(state / 'freezes' / field.lower())
    get_settings.cache_clear()
    return settings


def write_json(path, value):
    temp = path.with_suffix('.new')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    temp.replace(path)


class AuditStore:
    """只记录原观测器产生的安全元数据，不保存Prompt或应答正文。"""
    def __init__(self, state):
        self.path = state / 'requests.jsonl'
        self.lock = threading.RLock()

    def append(self, value):
        with self.lock, self.path.open('a', encoding='utf-8') as target:
            target.write(json.dumps(value, ensure_ascii=False, default=str) + '\n')

    async def start_attempt(self, event):
        self.append(dict(event, audit_phase='start'))

    async def finish_attempt(self, event_id, changes):
        self.append(dict(changes, event_id=event_id, audit_phase='finish'))

    def start_attempt_sync(self, event):
        self.append(dict(event, audit_phase='start'))

    def finish_attempt_sync(self, event_id, changes):
        self.append(dict(changes, event_id=event_id, audit_phase='finish'))


def save_results(state, results, *, in_memory=False):
    """使用原Canonical保存器，不将技术失败伪装成可交付医学结果。"""
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine('sqlite://' if in_memory else 'sqlite:///' + (state / 'results.sqlite').as_posix())
    table.metadata.create_all(engine)
    saved, failures = [], []
    ref = dict(institute_id='p9d-fictional', patient_id='p9d-fictional', visit_id='p9d-fictional')
    try:
        for index, result in enumerate(results):
            if result.get('status') in {'technical_error', 'uncertain'}:
                failures.append({'rule_id': result['rule_id'], 'reason': 'technical_result_not_deliverable'})
                continue
            job = 'p9d-' + str(index)
            with Session(engine) as session:
                try:
                    CanonicalResultStore(table).replace_for_job(session,
                        job_row={'id': job, 'created_by': 'p9d-isolated', 'filters_json': json.dumps({
                            'rule_set_key': 'luxian_0609_qc_v1', 'rule_set_version': '2026-06-09',
                            'scoped_customer_rule_ids': [result['rule_id']], 'record_refs': [ref]})},
                        items=[{**result, **ref, 'record_id': ref['visit_id']}], now=datetime.now(),
                        projector=lambda row: envelope_item_from_rule_result(row, hmac_key='p9d-fictional-ref-key'),
                        projection_key='p9d-fictional-ref-key')
                    session.commit()
                    loaded = CanonicalResultStore(table).load_selected(session, root_job_id=job, **ref,
                        rule_set_key='luxian_0609_qc_v1', rule_set_version='2026-06-09')['items']
                    assert len(loaded) == 1
                    restored = loaded[0]
                    assert restored['rule_id'] == result['rule_id'] and restored['status'] == result['status']
                    assert restored['reason_code'] == result.get('reason_code')
                    assert restored.get('customer_display_facts') == result.get('customer_display_facts')
                    saved.extend(loaded)
                except Exception as error:
                    session.rollback()
                    failures.append({'rule_id': result['rule_id'], 'reason': 'canonical_save_or_read_failed',
                                     'error_type': type(error).__name__})
    finally:
        engine.dispose()
    return saved, failures


async def run_formal(client, settings, state, *, in_memory=False):
    """仅替换虚构材料的数据读取边界，不替换Executor、绑定、聚合和保存。"""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from app.services.luxian_0609 import execution, evidence_snapshot_provider as provider
    from app.services.luxian_0609 import preproduction_runner
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
    from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
    rows, raw_results = synthetic_sources(), []
    selected = tuple(c.rule_id for c in load_luxian_0609_rule_contracts())
    def row_reader(*, source_key, **_):
        data = tuple(rows.get(source_key, ()))
        return SnapshotSourceRows(source_key, data, False, 500)
    def session(**kwargs):
        return provider.build_luxian_0609_evidence_read_session(**kwargs, row_reader=row_reader)
    original = preproduction_runner.aggregate_luxian_0609_orchestrated_results
    def aggregate(**kwargs):
        value = original(**kwargs)
        raw_results.extend(kwargs['orchestrated']['results'])
        return value
    def prohibit_external_database(conn, record, args, kwargs):
        if conn.name != 'sqlite':
            raise RuntimeError('isolated_smoke_forbids_external_database')
    event.listen(Engine, 'do_connect', prohibit_external_database)
    try:
        with ExitStack() as patches:
            patches.enter_context(patch.object(execution, 'build_luxian_0609_evidence_read_session', session))
            patches.enter_context(patch.object(execution, 'build_luxian_0609_evidence_snapshot',
                lambda **kwargs: session(**kwargs).snapshot))
            patches.enter_context(patch.object(preproduction_runner, 'aggregate_luxian_0609_orchestrated_results', aggregate))
            from app.services import sample_programmatic_evidence as fallback
            patches.enter_context(patch.object(fallback, '_fetch_source_table_fallback_items', lambda *_a, **_k: ([], {})))
            patches.enter_context(patch.object(fallback, '_fetch_detail_service_fallback_items', lambda *_a, **_k: []))
            bundle = {'scene': 'final', 'institute_id': 'p9d-fictional', 'patient_id': 'p9d-fictional',
                'visit_id': 'p9d-fictional', 'medical_text': '\n'.join(str(r.get('record_content', ''))
                    for source in rows.values() for r in source),
                'structured_context': {'documents': rows}, 'source_doc_priority': list(rows)}
            report = await preproduction_runner.run_luxian_0609_preproduction(bundle=bundle,
                selected_customer_rule_ids=selected, evaluation_as_of_date='2026-01-04',
                llm_client=client, base_settings=settings, model_name='qwen3.6-35b-a3b')
        assert len(report['results']) == len(selected)
        assert {r['rule_id'] for r in report['results']} == set(selected)
        saved, failures = save_results(state, raw_results, in_memory=in_memory)
        report.update(synthetic_only=True, saved_results=saved, persistence_failures=failures,
                      selected_rule_ids=list(selected), raw_result_count=len(raw_results),
                      production_database_used=False)
        write_json(state / 'report.json', report)
        text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        (state / 'report.html').write_text('<!doctype html><meta charset="utf-8"><title>P9-D隔离验收</title>'
            '<h1>P9-D 虚构病例正式链报告</h1><p>技术未完成不代表医学合规；固定应答不证明模型质量。</p><pre>'
            + html.escape(text) + '</pre>', encoding='utf-8')
        return report
    finally:
        event.remove(Engine, 'do_connect', prohibit_external_database)


async def main_async(args):
    root = Path(args.handoff).resolve(strict=True)
    state = Path(args.state).resolve() / ('p9d-' + uuid.uuid4().hex)
    state.mkdir(parents=True, exist_ok=False)
    settings = configure(root, state, args.endpoint)
    handler = logging.FileHandler(state / 'safe-model-metrics.log', encoding='utf-8')
    # 这些owner只写低基数参数/预算/耗时/usage；不打开HTTP wire或医学Prompt调试日志。
    for name in ('app.services.llm_observability', 'app.services.llm_token_budget'):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    from app.services.strata_handoff import runtime_for, close_runtimes
    from app.services.strata_protocol import P9_MODEL, fixed_probe_result
    runtime = runtime_for(str(root))
    runtime.ensure_counter()
    verified = {'component_files': len(runtime.handoff.hashes), 'text_vectors': len(runtime.handoff.corpus),
        'message_vectors': runtime._counter.validated_vectors, 'live_api_verified': False}
    write_json(state / 'counter-validation.json', verified)
    if args.mode == 'verify':
        print(json.dumps(verified))
        close_runtimes()
        return
    if not args.live or not os.environ.get('P9D_STRATA_API_KEY'):
        raise ValueError('live_requires_explicit_flag_and_key')
    from app.services.qc_llm_client import SichuanQCLLMClient
    from app.services.llm_observability import LLMObservabilityRecorder
    client = SichuanQCLLMClient(dict(provider_code='strata', model=P9_MODEL, api_endpoint=args.endpoint,
        api_key=os.environ['P9D_STRATA_API_KEY'], dispatch_mode='direct', custom_parameters={}),
        observability_recorder=LLMObservabilityRecorder(store=AuditStore(state)))
    try:
        if args.mode == 'probe':
            answer = await client.generate('请仅输出JSON：{"probe":"p9b"}', max_tokens=64)
            write_json(state / 'probe.json', fixed_probe_result(answer, P9_MODEL))
        else:
            report = await run_formal(client, settings, state)
            print(json.dumps({'rules': len(report['results']), 'saved': len(report['saved_results']),
                              'metrics': report['metrics']}, ensure_ascii=False))
        print('Output: ' + str(state))
    finally:
        close_runtimes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['verify', 'probe', 'run'])
    parser.add_argument('--handoff', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:18084/v1')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    # 当前进程不继承现场.env。禁止外部业务DB连接，真实请求仅由显式live入口产生。
    import dotenv
    from pydantic_settings import DotEnvSettingsSource
    with patch.object(dotenv, 'load_dotenv', return_value=False), patch.object(DotEnvSettingsSource, '__call__', return_value={}):
        asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
