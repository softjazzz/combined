"""LX0609 任务跨 Python 进程读取持久化快照与执行代次的边界。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import asyncio
from pathlib import Path

import pytest


_PROBE = r"""
import asyncio
import json
import os
import sys

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.services import custom_qc_workspace_service as storage
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import rule_decision_settings as identity
from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from app.services.case_identity import CaseRef
from app.services.sichuan_qc_service import SichuanQCService

mode, database_path, build_id, *rest = sys.argv[1:]
database = sa.create_engine('sqlite:///' + database_path)
storage.engine = database
storage._draft_schema = lambda: None
storage._sync_batch_job_parent_columns = lambda **_kwargs: None
storage._session = sessionmaker(bind=database)
workspace = storage.CustomQCWorkspaceService()
identity._PROCESS_RUNTIME_BUILD = {
    'available': True,
    'build_id': build_id,
    'git_commit': os.environ.get('LX0609_PROBE_GIT_COMMIT', 'a' * 40),
}
config = {
    'provider_code': 'alibaba',
    'api_endpoint': os.environ.get('LX0609_PROBE_API_ENDPOINT', 'https://example.invalid/llm'),
    'api_key': 'synthetic-test-secret',
    'model': os.environ.get('LX0609_PROBE_MODEL', 'model-a'),
    'source': 'test',
}

if mode in ('create', 'create-full'):
    service = SichuanQCService(config)
    filters = {
        'rule_set_key': 'luxian_0609_qc_v1',
        'rule_ids': ['LX0609-01-01-01'],
        identity.LX0609_TASK_SETTINGS_FILTER_KEY:
            identity.capture_luxian_0609_task_settings(
                identity.resolve_mainline_rule_decision_settings(get_settings())
            ),
        identity.LX0609_TASK_RUNTIME_FILTER_KEY:
            identity.capture_luxian_0609_task_runtime(service),
    }
    if mode == 'create-full':
        record_ref = CaseRef('HOSP-001', 'PAT-001', 'synthetic-visit')
        filters.update({
            'rule_set_version': '2026-06-09',
            'record_refs': [record_ref.as_dict()],
            'selected_rule_ids': ['LX0609-01-01-01'],
            'scoped_customer_rule_ids': ['LX0609-01-01-01'],
            'active_customer_rule_ids': ['LX0609-01-01-01'],
            'pending_customer_rule_ids': [],
            'paused_customer_rule_ids': [],
            'record_rule_map': {record_ref.as_key(): ['LX0609-01-01-01']},
            'validation_mode': 'programmatic',
            'customer_rule_count': 1,
            'execution_rule_count': 1,
            'pending_rule_count': 0,
        })
    job = workspace.create_batch_job(
        draft={'id': 'synthetic-draft', 'rule_code': 'LX0609-01-01-01',
               'name': '合成规则', 'scene': 'final'},
        created_by='synthetic-tester', scope='final',
        filters=filters,
        record_ids=['synthetic-visit'], total_records=1,
        **({'record_refs': [record_ref]} if mode == 'create-full' else {}),
    )
    print(json.dumps({'job_id': job['id']}))
else:
    job_id = rest[0]

    class Activation:
        def enforce(self):
            return None

    def stop_after_runtime_gate(*_args, **_kwargs):
        raise RuntimeError('passed-runtime-gate')

    worker.get_product_activation_service = lambda: Activation()
    if mode not in ('finish', 'recover-full'):
        worker.assert_luxian_0609_customer_native_delivery_ready = stop_after_runtime_gate

    def block_record_read(**_kwargs):
        raise AssertionError('record-read-before-runtime-gate')

    if mode in ('finish', 'recover-full'):
        storage._record_result_envelopes_table().metadata.create_all(database)
        workspace.collect_records = lambda **_kwargs: [{
            'institute_id': 'HOSP-001', 'patient_id': 'PAT-001',
            'record_id': 'synthetic-visit', 'visit_id': 'synthetic-visit',
            'patient_name': 'synthetic', 'department': 'test', 'scope': 'final',
        }]
        workspace.hydrate_records_with_medical_text = lambda records: [
            {**record, 'medical_text': 'synthetic record'} for record in records
        ]
        worker.load_running_final_bundle = lambda **kwargs: {
            'scene': 'final', 'visit_id': kwargs['visit_id'],
            'institute_id': 'HOSP-001', 'patient_id': 'PAT-001',
            'source_schema': 'cdm', 'medical_text': 'synthetic record',
            'structured_context': {}, 'document_hits': {}, 'text_available': True,
        }
        original_evidence = execution_module.build_luxian_0609_evidence_read_session
        execution_module.build_luxian_0609_evidence_read_session = lambda **kwargs: original_evidence(
            **kwargs, row_reader=lambda **query: SnapshotSourceRows.create(
                source_key=query['source_key'], rows=[], truncated=False, limit_rows=50,
            ),
        )
        programmatic_evidence._fetch_source_table_fallback_items = lambda *_a, **_k: ([], {})
        programmatic_evidence._fetch_detail_service_fallback_items = lambda *_a, **_k: []
    else:
        workspace.collect_records = block_record_read

    renew_count = 0
    if mode == 'heartbeat':
        worker.LX0609_LEASE_HEARTBEAT_SECONDS = 0.01
        original_renew = workspace.renew_luxian_0609_batch_job_lease

        def counted_renew(**kwargs):
            global renew_count
            renewed = original_renew(**kwargs)
            renew_count += int(renewed)
            return renewed

        workspace.renew_luxian_0609_batch_job_lease = counted_renew

    async def provide():
        if mode == 'heartbeat':
            await asyncio.sleep(0.08)
        service = SichuanQCService(config)
        if mode in ('finish', 'recover-full'):
            async def forbid_model(*_args, **_kwargs):
                raise AssertionError('synthetic finish probe must not call the model')
            service.client.generate = forbid_model
        return service

    resumed_count = None
    if mode in ('recover', 'recover-full'):
        from app.routers import qc_sichuan as route

        async def run_recovered(recovered_job_id):
            await worker.run_sichuan_workspace_batch_job(
                recovered_job_id, workspace=workspace, qc_service_provider=provide,
            )

        def submit_synchronously(_name, func, *args, **kwargs):
            asyncio.run(func(*args, **kwargs))

        route._sichuan_workspace_service = lambda: workspace
        route._run_sichuan_workspace_batch_job = run_recovered
        route.submit_detached_task = submit_synchronously
        resumed_count = route.resume_queued_luxian_0609_workspace_jobs()
    else:
        asyncio.run(worker.run_sichuan_workspace_batch_job(
            job_id, workspace=workspace, qc_service_provider=provide,
        ))
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    persisted_filters = json.loads(job['_claim_filters_json'])
    canonical_statuses = []
    if mode in ('finish', 'recover-full'):
        with storage._session() as db:
            loaded = CanonicalResultStore(workspace._record_result_envelope_table).load_selected(
                db, root_job_id=job_id, institute_id='HOSP-001', patient_id='PAT-001',
                visit_id='synthetic-visit', rule_set_key='luxian_0609_qc_v1',
                rule_set_version='2026-06-09',
            )
        canonical_statuses = [item['status'] for item in loaded['items']]
    print(json.dumps({
        'status': job['status'],
        'error_message': job['error_message'],
        'attempt_id': persisted_filters.get(storage.LX0609_ATTEMPT_FILTER_KEY),
        'resumed_count': resumed_count,
        'renew_count': renew_count,
        'result_statuses': [item.get('status') for item in job.get('items', [])],
        'canonical_statuses': canonical_statuses,
        'total_tokens': job.get('total_tokens'),
    }, ensure_ascii=False))
"""


def _run_probe(
    *args: str, runtime_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    environment = os.environ.copy()
    for key in (
        "LX0609_PROBE_GIT_COMMIT", "LX0609_PROBE_MODEL", "LX0609_PROBE_API_ENDPOINT",
    ):
        environment.pop(key, None)
    environment.update({
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/test",
        "JWT_SECRET": "isolated-test-secret-not-for-production-0609",
        "DB_SCHEMA_MODE": "single",
        "PYTHONIOENCODING": "utf-8",
        "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": "true",
    })
    environment.update(runtime_overrides or {})
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, *args],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("same_release", [True, False])
def test_persisted_formal_task_is_checked_by_a_new_worker_process(tmp_path, same_release):
    """新进程从任务表领取任务，同版通过门禁、异版在取病历前受控失败。"""

    database_path = str(tmp_path / "formal-jobs.sqlite")
    first_build = "medqc-web-customer-20260925-100000"
    next_build = first_build if same_release else "medqc-web-customer-20260925-110000"
    created = _run_probe("create", database_path, first_build)
    resumed = _run_probe("run", database_path, next_build, str(created["job_id"]))

    assert resumed["status"] == "failed"
    assert isinstance(resumed["attempt_id"], str) and resumed["attempt_id"], resumed
    if same_release:
        assert resumed["error_message"] == "passed-runtime-gate"
    else:
        assert "模型或实现版本已变化" in str(resumed["error_message"])


@pytest.mark.parametrize("resume_mode", ["finish", "recover-full"])
def test_new_process_can_complete_frozen_original_rule_and_read_canonical_result(tmp_path, resume_mode):
    database_path = str(tmp_path / "completed-jobs.sqlite")
    build_id = "medqc-web-customer-20260925-100000"
    created = _run_probe("create-full", database_path, build_id)
    completed = _run_probe(resume_mode, database_path, build_id, str(created["job_id"]))

    assert completed["status"] == "completed", completed
    assert completed["error_message"] in (None, ""), completed
    assert completed["result_statuses"] == ["data_gap"]
    assert completed["canonical_statuses"] == completed["result_statuses"]
    assert completed["total_tokens"] == 0
    if resume_mode == "recover-full":
        assert completed["resumed_count"] == 1


@pytest.mark.parametrize("same_release", [True, False])
def test_queued_formal_task_is_resubmitted_after_process_restart(tmp_path, same_release):
    """重启扫描应重投已保存队列，同版或异版均经正式 Worker 门禁。"""

    database_path = str(tmp_path / "queued-jobs.sqlite")
    first_build = "medqc-web-customer-20260925-100000"
    next_build = first_build if same_release else "medqc-web-customer-20260925-110000"
    created = _run_probe("create", database_path, first_build)
    recovered = _run_probe("recover", database_path, next_build, str(created["job_id"]))

    assert recovered["resumed_count"] == 1
    assert recovered["status"] == "failed"
    assert isinstance(recovered["attempt_id"], str) and recovered["attempt_id"]
    if same_release:
        assert recovered["error_message"] == "passed-runtime-gate"
    else:
        assert "模型或实现版本已变化" in str(recovered["error_message"])
    assert _run_probe("recover", database_path, next_build, str(created["job_id"]))["resumed_count"] == 0


@pytest.mark.parametrize("resume_mode", ["run", "recover"])
@pytest.mark.parametrize(
    ("runtime_overrides", "expected_error"),
    [
        ({"LX0609_PROBE_GIT_COMMIT": "b" * 40}, "模型或实现版本已变化"),
        ({"LX0609_PROBE_MODEL": "model-b"}, "模型或实现版本已变化"),
        ({"LX0609_PROBE_API_ENDPOINT": "https://changed.example.invalid/llm"}, "模型或实现版本已变化"),
        ({"LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": "false"}, "执行配置已变化"),
    ],
    ids=["commit-drift", "model-drift", "endpoint-drift", "rule-setting-drift"],
)
def test_persisted_task_rejects_runtime_drift_before_record_read(
    tmp_path, resume_mode: str, runtime_overrides: dict[str, str], expected_error: str,
):
    """同一构建号也必须检查持久化模型身份；恢复不能偷换模型。"""

    database_path = str(tmp_path / "runtime-drift-jobs.sqlite")
    build_id = "medqc-web-customer-20260925-100000"
    created = _run_probe("create", database_path, build_id)
    resumed = _run_probe(
        resume_mode, database_path, build_id, str(created["job_id"]),
        runtime_overrides=runtime_overrides,
    )

    assert resumed["status"] == "failed"
    assert isinstance(resumed["attempt_id"], str) and resumed["attempt_id"]
    assert expected_error in str(resumed["error_message"])
    if resume_mode == "recover":
        assert resumed["resumed_count"] == 1


def test_restarted_worker_renews_persisted_attempt_during_wait(tmp_path):
    database_path = str(tmp_path / "heartbeat-jobs.sqlite")
    build_id = "medqc-web-customer-20260925-100000"
    created = _run_probe("create", database_path, build_id)
    observed = _run_probe("heartbeat", database_path, build_id, str(created["job_id"]))
    assert observed["status"] == "failed"
    assert observed["error_message"] == "passed-runtime-gate"
    assert observed["renew_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("resume_tasks", [None, "false"])
async def test_application_startup_invokes_queued_luxian_recovery(monkeypatch, resume_tasks):
    from app import main as main_module
    from app import database
    from app.database import repository
    from app.storage import memory
    from app.services import smart_upload_async_service
    from app.services.drg import batch_task_service
    from app.services import local_icd_service
    from app.services.llm_config_loader import LLMConfigLoader

    calls = []
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "normal")
    if resume_tasks is None:
        monkeypatch.delenv("MEDQC_RESUME_QC_TASKS", raising=False)
    else:
        monkeypatch.setenv("MEDQC_RESUME_QC_TASKS", resume_tasks)

    async def load_config(**_kwargs):
        return None

    monkeypatch.setattr(main_module.runtime_build_router, "initialize_runtime_build", lambda _app: None)
    monkeypatch.setattr(memory, "assert_no_default_demo_users_in_production", lambda _env: None)
    monkeypatch.setattr(repository, "validate_data_source", lambda: None)
    monkeypatch.setattr(database, "init_db", lambda: None)
    monkeypatch.setattr(smart_upload_async_service, "get_smart_upload_async_service", lambda: None)
    monkeypatch.setattr(batch_task_service, "get_batch_task_manager", lambda: None)
    monkeypatch.setattr(local_icd_service, "_get_icd_data", lambda: None)
    monkeypatch.setattr(LLMConfigLoader, "load_config", load_config)
    monkeypatch.setattr(main_module.qc_sichuan_router, "start_rule_source_monitor", lambda: None)
    monkeypatch.setattr(
        main_module.qc_sichuan_router, "start_luxian_0609_task_recovery_monitor",
        lambda: calls.append("monitor"),
    )
    monkeypatch.setattr(
        main_module.qc_sichuan_router, "resume_queued_luxian_0609_workspace_jobs",
        lambda: calls.append("recover"),
    )

    app = main_module.create_app()
    startup = next(callback for callback in app.router.on_startup if callback.__name__ == "startup_event")
    await startup()
    assert calls == (["recover", "monitor"] if resume_tasks is None else [])


@pytest.mark.asyncio
async def test_recovery_monitor_checks_expired_attempts(monkeypatch):
    from app.routers import qc_sichuan as route

    calls = []

    class Workspace:
        def fail_stale_luxian_0609_running_jobs(self, *, stale_before):
            calls.append(stale_before)
            return ()

    monkeypatch.setattr(route, "_sichuan_workspace_service", Workspace)
    monkeypatch.setattr(route, "_LX0609_RECOVERY_SCAN_SECONDS", 0.01)
    route.start_luxian_0609_task_recovery_monitor()
    try:
        for _ in range(50):
            if calls:
                break
            await asyncio.sleep(0.01)
        assert calls
    finally:
        await route.stop_luxian_0609_task_recovery_monitor()
