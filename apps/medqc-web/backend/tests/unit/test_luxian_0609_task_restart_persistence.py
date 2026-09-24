"""LX0609 任务跨 Python 进程读取持久化快照与执行代次的边界。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_PROBE = r"""
import asyncio
import json
import sys

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.services import custom_qc_workspace_service as storage
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import rule_decision_settings as identity
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
    'git_commit': 'a' * 40,
}
config = {
    'provider_code': 'alibaba', 'api_endpoint': 'https://example.invalid/llm',
    'api_key': 'synthetic-test-secret', 'model': 'model-a', 'source': 'test',
}

if mode == 'create':
    service = SichuanQCService(config)
    job = workspace.create_batch_job(
        draft={'id': 'synthetic-draft', 'rule_code': 'LX0609-01-01-01',
               'name': '合成规则', 'scene': 'final'},
        created_by='synthetic-tester', scope='final',
        filters={
            'rule_set_key': 'luxian_0609_qc_v1',
            'rule_ids': ['LX0609-01-01-01'],
            identity.LX0609_TASK_SETTINGS_FILTER_KEY:
                identity.capture_luxian_0609_task_settings(
                    identity.resolve_mainline_rule_decision_settings(get_settings())
                ),
            identity.LX0609_TASK_RUNTIME_FILTER_KEY:
                identity.capture_luxian_0609_task_runtime(service),
        },
        record_ids=['synthetic-visit'], total_records=1,
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
    worker.assert_luxian_0609_customer_native_delivery_ready = stop_after_runtime_gate

    def block_record_read(**_kwargs):
        raise AssertionError('record-read-before-runtime-gate')

    workspace.collect_records = block_record_read

    async def provide():
        return SichuanQCService(config)

    asyncio.run(worker.run_sichuan_workspace_batch_job(
        job_id, workspace=workspace, qc_service_provider=provide,
    ))
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    persisted_filters = json.loads(job['_claim_filters_json'])
    print(json.dumps({
        'status': job['status'],
        'error_message': job['error_message'],
        'attempt_id': persisted_filters.get(storage.LX0609_ATTEMPT_FILTER_KEY),
    }, ensure_ascii=False))
"""


def _run_probe(*args: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment.update({
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/test",
        "JWT_SECRET": "isolated-test-secret-not-for-production-0609",
        "DB_SCHEMA_MODE": "single",
        "PYTHONIOENCODING": "utf-8",
    })
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
