"""仅在显式指定隔离本机 PG 时验证 LX0609 跨进程领取与提交事务。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace_module


_CLAIM_PROCESS = r"""
import json
import sys
import time
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from app.services import custom_qc_workspace_service as storage

database_url, schema, job_id, ready_path, release_path = sys.argv[1:]
database = sa.create_engine(database_url)
storage.engine = database
storage._draft_schema = lambda: schema
storage._sync_batch_job_parent_columns = lambda **_kwargs: None
storage._batch_jobs_table.cache_clear()
storage._drafts_table.cache_clear()
storage._record_result_envelopes_table.cache_clear()
storage._session = sessionmaker(bind=database)
service = storage.CustomQCWorkspaceService()
Path(ready_path).write_text('ready', encoding='ascii')
deadline = time.monotonic() + 20
while not Path(release_path).exists():
    if time.monotonic() > deadline:
        raise TimeoutError('claim release was not signaled')
    time.sleep(0.01)
attempt = service.mark_batch_job_running(job_id=job_id)
print(json.dumps({'claimed': isinstance(attempt, str),
                  'attempt': attempt if isinstance(attempt, str) else ''}), flush=True)
"""


def _isolated_database_url() -> str:
    database_url = os.environ.get("MEDQC_LX0609_ISOLATED_PG_URL", "")
    if not database_url:
        pytest.skip("需显式提供独立本机 PostgreSQL 18 测试实例")
    parsed = sa.engine.make_url(database_url)
    if parsed.get_backend_name() != "postgresql" or parsed.host != "127.0.0.1" or parsed.port != 15432:
        pytest.fail("只允许连接隔离的 127.0.0.1:15432 PostgreSQL 测试实例")
    return database_url


def _wait_until_ready(processes: list[subprocess.Popen[str]], paths: list[Path]) -> None:
    deadline = time.monotonic() + 25
    while not all(path.exists() for path in paths):
        if any(process.poll() is not None for process in processes):
            raise AssertionError("领取进程在开始信号前退出")
        if time.monotonic() > deadline:
            raise TimeoutError("领取进程未进入准备状态")
        time.sleep(0.02)


@pytest.mark.parametrize("round_index", range(3))
def test_two_postgres_processes_claim_once_and_only_current_attempt_publishes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, round_index: int,
) -> None:
    database_url = _isolated_database_url()
    schema = f"lx0609_audit_{round_index}_" + uuid.uuid4().hex[:12]
    database = sa.create_engine(database_url)
    with database.begin() as connection:
        connection.execute(sa.text(f"CREATE SCHEMA {schema}"))

    processes: list[subprocess.Popen[str]] = []
    try:
        monkeypatch.setattr(workspace_module, "engine", database)
        monkeypatch.setattr(workspace_module, "_draft_schema", lambda: schema)
        monkeypatch.setattr(workspace_module, "_session", sessionmaker(bind=database))
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()
        service = workspace_module.CustomQCWorkspaceService()
        service._record_result_envelope_table.metadata.create_all(database)
        table = service._batch_job_table
        envelopes = service._record_result_envelope_table
        job_id = "pg-attempt-" + uuid.uuid4().hex[:20]
        with database.begin() as connection:
            connection.execute(table.insert().values(
                id=job_id, draft_id="synthetic-draft", created_by="synthetic-tester",
                rule_code="LX0609", rule_name="合成领取测试", scene="final", scope="final",
                status="queued", total_records=1, record_ids_json='["visit-1"]',
                filters_json=json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": workspace_module.RULE_SET_VERSION,
                    "rule_ids": ["LX0609-01-01-01"],
                    "record_refs": [{"institute_id": "inst-1", "patient_id": "patient-1",
                                     "visit_id": "visit-1"}],
                }),
                created_at=datetime(2026, 9, 25), updated_at=datetime(2026, 9, 25),
            ))

        release_path = tmp_path / "release"
        ready_paths = [tmp_path / f"ready-{index}" for index in range(2)]
        for ready_path in ready_paths:
            processes.append(subprocess.Popen(
                [sys.executable, "-c", _CLAIM_PROCESS, database_url, schema, job_id,
                 str(ready_path), str(release_path)],
                cwd=Path(__file__).resolve().parents[2],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            ))
        _wait_until_ready(processes, ready_paths)
        release_path.write_text("go", encoding="ascii")
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            results.append(json.loads(stdout.splitlines()[-1]))
        winners = [result for result in results if result["claimed"]]
        assert len(winners) == 1, results
        old_attempt = winners[0]["attempt"]
        running = service.get_batch_job_for_processing(job_id=job_id)
        assert running is not None and running["status"] == "running"
        assert running["_claim_filters_json"] == old_attempt

        canceled = service.cancel_batch_job(job_id=job_id, created_by="synthetic-tester")
        assert canceled is not None and canceled["status"] == "canceled"
        retried = service.retry_batch_job(job_id=job_id, created_by="synthetic-tester")
        assert retried is not None and retried["status"] == "queued"
        new_attempt = service.mark_batch_job_running(job_id=job_id)
        assert isinstance(new_attempt, str) and new_attempt != old_attempt
        payload = {
            "job_id": job_id,
            "summary": {"execution_status": "completed", "total_records": 1},
            "items": [{
                "institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1",
                "rule_id": "LX0609-01-01-01", "status": "compliant",
                "result_status": "compliant", "display_status": "compliant",
                "is_compliant": True, "reason_code": "requirement_within_threshold",
                "customer_display_facts": {
                    "failure_kind": "timeliness_requirement_satisfied",
                    "target_document": "admission_record", "source_label": "入院记录",
                    "timeliness_state": "within", "threshold_hours": 24,
                    "anchor_time": "2026-09-20 08:00:00",
                    "observed_time": "2026-09-20 09:00:00",
                    "elapsed_hours": 1.0, "remaining_hours": 23.0,
                },
            }],
            "failed_records": [],
        }
        assert service.complete_batch_job(**payload, attempt_filters_json=old_attempt) is False
        with database.connect() as connection:
            assert connection.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar_one() == 0
        assert service.complete_batch_job(**payload, attempt_filters_json=new_attempt) is True
        with database.connect() as connection:
            assert connection.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar_one() == 1
        with workspace_module._session() as session:
            result = service._load_record_result_envelope_items(
                session, root_job_id=job_id, institute_id="inst-1", patient_id="patient-1",
                visit_id="visit-1", rule_set_key="luxian_0609_qc_v1",
                rule_set_version=workspace_module.RULE_SET_VERSION,
            )
        assert [(item["rule_id"], item["status"]) for item in result["items"]] == [
            ("LX0609-01-01-01", "compliant"),
        ]
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        with database.begin() as connection:
            connection.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))
        database.dispose()
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()
