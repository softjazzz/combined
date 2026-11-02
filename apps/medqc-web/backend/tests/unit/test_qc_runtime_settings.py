"""临时目录、Mock HTTP和合成身份验收；不写业务库，不连接外部服务。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

from fastapi import FastAPI
import httpx
import pytest

from app.core.security import get_current_user
from app.routers import qc_runtime_settings as api
from app.services.qc_dispatch import control, readiness, status
from app.services.qc_dispatch.dispatcher import (
    QCDispatchEntrypointError, assert_new_qc_task_dispatch_ready, should_submit_detached_qc_task,
)


@pytest.fixture
def cfg(tmp_path):
    return SimpleNamespace(QC_DISPATCH_STATE_DIR=str(tmp_path), QC_TASK_DISPATCH_MODE='legacy',
        QC_RABBITMQ_URL='amqp://test:test@fake-broker/test', QC_RABBITMQ_EXCHANGE='test.exchange',
        QC_RABBITMQ_QUEUE='test.queue', QC_RABBITMQ_DEAD_QUEUE='test.dead',
        DATABASE_URL='sqlite://', DB_SCHEMA_MODE='legacy', LLM_DISPATCH_MODE='gateway',
        LLM_GATEWAY_URL='http://fake-gateway', LLM_GATEWAY_TOKEN='synthetic-' + 'a' * 32,
        LLM_GATEWAY_PROFILE='alibaba_first_pass')


def test_default_legacy_and_environment_compatibility(cfg):
    assert control.effective_dispatch_mode(cfg) == 'legacy'
    cfg.QC_TASK_DISPATCH_MODE = 'rabbitmq'
    assert control.effective_dispatch_mode(cfg) == 'rabbitmq'
    assert not (control.state_directory(cfg) / 'settings.json').exists()


def test_revision_atomic_save_and_persisted_jobs_unchanged(cfg):
    old_mq = {'filters': {'qc_dispatch': {'schema_version': 1, 'mode': 'rabbitmq'}}}
    old_legacy = {'filters': {}}
    control.save_control(enabled=True, expected_revision=0, actor='test-admin', settings=cfg)
    assert control.effective_dispatch_mode(cfg) == 'rabbitmq'
    with pytest.raises(control.DispatchControlConflict):
        control.save_control(enabled=False, expected_revision=0, actor='other', settings=cfg)
    assert control.effective_dispatch_mode(cfg) == 'rabbitmq'
    control.save_control(enabled=False, expected_revision=1, actor='test-admin', settings=cfg)
    assert control.effective_dispatch_mode(cfg) == 'legacy'
    assert not should_submit_detached_qc_task(old_mq)
    assert should_submit_detached_qc_task(old_legacy)


@pytest.mark.parametrize('raw', ['{', '{"rabbitmq_enabled":"false"}', '{"rabbitmq_enabled":false,"unknown":1}'])
def test_corrupt_configuration_fails_closed(cfg, raw):
    (control.state_directory(cfg) / 'settings.json').write_text(raw, encoding='utf-8')
    with pytest.raises(control.DispatchControlError):
        control.effective_dispatch_mode(cfg)
    with pytest.raises(QCDispatchEntrypointError):
        assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=True, settings=cfg)
    assert assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=False, settings=cfg) == 'legacy'


def test_failed_replace_preserves_old_setting(cfg, monkeypatch):
    control.save_control(enabled=False, expected_revision=0, actor='test', settings=cfg)
    def deny(*_args):
        raise PermissionError('synthetic')
    monkeypatch.setattr(control.os, 'replace', deny)
    with pytest.raises(control.DispatchControlError):
        control.save_control(enabled=True, expected_revision=1, actor='test', settings=cfg)
    assert control.load_control(cfg)[0].revision == 1
    assert control.effective_dispatch_mode(cfg) == 'legacy'
    assert list(control.state_directory(cfg).glob('*.tmp')) == []


def test_mode_owner_is_shared_with_preflight_and_validates_actual_runtime(cfg):
    control.save_control(enabled=True, expected_revision=0, actor='test', settings=cfg)
    with pytest.raises(QCDispatchEntrypointError, match='模型运行身份'):
        assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=True, settings=cfg)
    identity = {'dispatch_mode': 'gateway', 'gateway_profile': 'alibaba_first_pass', 'gateway_endpoint_sha256': 'a' * 64}
    assert assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=True, settings=cfg,
        task_runtime_snapshot={'first_pass': identity, 'adjudicator': identity}) == 'rabbitmq'
    with pytest.raises(QCDispatchEntrypointError, match='父子任务'):
        assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=True, family_parent=True, settings=cfg)


def test_second_writer_cannot_bypass_lock(cfg):
    with control._write_lock(control.state_directory(cfg)):
        with pytest.raises(control.DispatchControlError):
            control.save_control(enabled=True, expected_revision=0, actor='test', settings=cfg)
    assert not (control.state_directory(cfg) / 'settings.json').exists()


def put_heartbeat(cfg, role, *, age=0, ready=True, identity=None):
    data = status.Heartbeat(role=role, deployment=identity or control.deployment_identity(cfg),
        ready=ready, observed_at=datetime.now(timezone.utc) - timedelta(seconds=age))
    control.atomic_write(control.state_directory(cfg) / 'services' / f'{role}.json', data.model_dump(mode='json'))


@pytest.mark.parametrize('age,ready,identity,expected', [
    (0, True, None, True), (31, True, None, False), (-5, True, None, False),
    (0, False, None, False), (0, True, 'other-deployment', False),
])
def test_heartbeat_never_guesses_readiness(cfg, age, ready, identity, expected):
    put_heartbeat(cfg, 'worker', age=age, ready=ready, identity=identity)
    assert status.service_status(cfg) == {'publisher': False, 'worker': expected}


@pytest.mark.asyncio
async def test_heartbeat_shutdown_removes_only_own_file(cfg):
    put_heartbeat(cfg, 'worker')
    task = asyncio.create_task(status.report_service_status(cfg, role='publisher', is_ready=lambda: True))
    await asyncio.sleep(0)
    assert status.service_status(cfg) == {'publisher': True, 'worker': True}
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert status.service_status(cfg) == {'publisher': False, 'worker': True}


@pytest.mark.asyncio
@pytest.mark.parametrize('healthy,authorized,capacity,expected', [
    (True, True, 2, True), (False, True, 2, False), (True, False, 2, False), (True, True, 0, False),
])
async def test_readiness_only_uses_mock_readonly_gateway(cfg, monkeypatch, healthy, authorized, capacity, expected):
    put_heartbeat(cfg, 'publisher')
    put_heartbeat(cfg, 'worker')
    paths = []
    real_client = httpx.AsyncClient
    def handle(request):
        paths.append(request.url.path)
        assert request.method == 'GET'
        if request.url.path == '/health':
            return httpx.Response(200 if healthy else 503, json={'status': 'ok'})
        assert request.headers['authorization'] == 'Bearer ' + cfg.LLM_GATEWAY_TOKEN
        return httpx.Response(200 if authorized else 401, json={'resources': [{'effective_max_inflight': capacity}]})
    monkeypatch.setattr(readiness.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    result = await readiness.check_readiness(cfg)
    assert result['ready'] is expected
    assert paths == ['/health', '/v1/llm/resources']
    assert cfg.LLM_GATEWAY_TOKEN not in json.dumps(result)
    assert cfg.QC_RABBITMQ_URL not in json.dumps(result)


@pytest.fixture
def api_app(cfg, monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    monkeypatch.setattr(api, 'get_settings', lambda: cfg)
    app.dependency_overrides[get_current_user] = lambda: {'id': 'test-admin', 'roles': ['sync_admin']}
    return app


@pytest.mark.asyncio
async def test_read_get_does_not_probe_and_blocked_enable_does_not_save(api_app, cfg):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.get('/api/v1/system/qc-runtime')
        assert response.status_code == 200
        assert response.json()['effective_mode'] == 'legacy'
        cfg.LLM_DISPATCH_MODE = 'direct'  # 配置不完整不应尝试任何HTTP连接。
        response = await client.put('/api/v1/system/qc-runtime', json={'rabbitmq_enabled': True, 'expected_revision': 0})
        assert response.status_code == 409
        assert not (control.state_directory(cfg) / 'settings.json').exists()


@pytest.mark.asyncio
async def test_enable_mock_ready_and_disable_without_services(api_app, cfg, monkeypatch):
    async def ready(_settings):
        return {'ready': True, 'gateway_checked': True, 'checks': {}}
    monkeypatch.setattr(api, 'check_readiness', ready)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        response = await client.put('/api/v1/system/qc-runtime', json={'rabbitmq_enabled': True, 'expected_revision': 0})
        assert response.status_code == 200
        assert control.effective_dispatch_mode(cfg) == 'rabbitmq'
        cfg.QC_RABBITMQ_URL = None
        cfg.LLM_DISPATCH_MODE = 'direct'
        async def must_not_probe(_settings):
            raise AssertionError('关闭开关不依赖服务可用')
        monkeypatch.setattr(api, 'check_readiness', must_not_probe)
        stale = await client.put('/api/v1/system/qc-runtime', json={'rabbitmq_enabled': False, 'expected_revision': 0})
        assert stale.status_code == 409
        response = await client.put('/api/v1/system/qc-runtime', json={'rabbitmq_enabled': False, 'expected_revision': 1})
        assert response.status_code == 200
        assert control.effective_dispatch_mode(cfg) == 'legacy'


@pytest.mark.asyncio
@pytest.mark.parametrize('user', [
    {'roles': ['doctor']}, {'roles': ['qc_manager']},
    {'roles': ['admin'], 'is_demo_account': True},
])
async def test_permissions_cannot_be_bypassed_by_direct_url(api_app, user, cfg):
    api_app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        for method, path in [('GET', ''), ('POST', '/check'), ('PUT', '')]:
            response = await client.request(method, '/api/v1/system/qc-runtime' + path,
                json={'rabbitmq_enabled': False, 'expected_revision': 0} if method == 'PUT' else None)
            assert response.status_code == 403
    assert not (control.state_directory(cfg) / 'settings.json').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    {'rabbitmq_enabled': 'false', 'expected_revision': 0},
    {'rabbitmq_enabled': False, 'expected_revision': 0, 'url': 'http://injected'},
    {'rabbitmq_enabled': False, 'expected_revision': -1},
])
async def test_update_contract_strict(api_app, payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url='http://test') as client:
        assert (await client.put('/api/v1/system/qc-runtime', json=payload)).status_code == 422
