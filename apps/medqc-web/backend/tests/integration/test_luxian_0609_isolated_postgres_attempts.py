"""仅在显式指定隔离本机 PG 时验证 LX0609 跨进程领取与提交事务。"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from html import unescape as html_unescape
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


_FORMAL_WORKER_PROCESS = r"""
import asyncio
import json
import sys

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as storage
from app.services import sichuan_workspace_batch_worker as worker
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609 import rule_decision_settings as identity
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from app.services.sichuan_qc_service import SichuanQCService

database_url, schema, job_id, build_id = sys.argv[1:]
database = sa.create_engine(database_url)
storage.engine = database
storage._draft_schema = lambda: schema
storage._sync_batch_job_parent_columns = lambda **_kwargs: None
storage._drafts_table.cache_clear()
storage._batch_jobs_table.cache_clear()
storage._record_result_envelopes_table.cache_clear()
storage._session = sessionmaker(bind=database)
workspace = storage.CustomQCWorkspaceService()
identity._PROCESS_RUNTIME_BUILD = {
    'available': True, 'build_id': build_id, 'git_commit': 'a' * 40,
}

class Activation:
    def enforce(self):
        return None

worker.get_product_activation_service = lambda: Activation()
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

config = {
    'provider_code': 'alibaba', 'api_endpoint': 'https://example.invalid/llm',
    'api_key': 'synthetic-test-secret', 'model': 'model-a', 'source': 'test',
}

async def provide():
    service = SichuanQCService(config)
    async def forbid_model(*_args, **_kwargs):
        raise AssertionError('isolated PG worker must not call the model')
    service.client.generate = forbid_model
    return service

asyncio.run(worker.run_sichuan_workspace_batch_job(
    job_id, workspace=workspace, qc_service_provider=provide,
))
job = workspace.get_batch_job_for_processing(job_id=job_id)
with storage._session() as session:
    loaded = CanonicalResultStore(workspace._record_result_envelope_table).load_selected(
        session, root_job_id=job_id, institute_id='HOSP-001', patient_id='PAT-001',
        visit_id='synthetic-visit', rule_set_key='luxian_0609_qc_v1',
        rule_set_version='2026-06-09',
    )
print(json.dumps({
    'status': job['status'],
    'result_statuses': [item.get('status') for item in job.get('items', [])],
    'canonical_statuses': [item['status'] for item in loaded['items']],
    'total_tokens': job.get('total_tokens'),
}, ensure_ascii=False))
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

        progress = service.update_batch_job_progress(
            job_id=job_id, step_key="run", rule_index=1, rule_count=1,
            processed_records=0, total_records=1,
            summary_patch={
                "total_tokens": 12,
                "luxian_0609_usage_observation_complete": True,
            },
            attempt_filters_json=old_attempt,
        )
        assert progress is not None and progress["summary"]["total_tokens"] == 12
        canceled = service.cancel_batch_job(job_id=job_id, created_by="synthetic-tester")
        assert canceled is not None and canceled["status"] == "canceled"
        assert canceled["summary"]["total_tokens"] == 12
        assert canceled["summary"]["luxian_0609_usage_observation_complete"] is False
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


def test_new_process_executes_original_rule_and_commits_canonical_on_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 PG 上由独立进程运行正式 Worker，而非手动调用完成事务。"""
    from app.core.settings import get_settings
    from app.services.case_identity import CaseRef
    from app.services.luxian_0609 import rule_decision_settings as identity
    from app.services.qc_workspace.export_service import CUSTOMER_EXPORT_HEADERS
    from app.services.sichuan_qc_service import SichuanQCService

    database_url = _isolated_database_url()
    schema = "lx0609_worker_" + uuid.uuid4().hex[:12]
    database = sa.create_engine(database_url)
    with database.begin() as connection:
        connection.execute(sa.text(f"CREATE SCHEMA {schema}"))

    try:
        monkeypatch.setattr(workspace_module, "engine", database)
        monkeypatch.setattr(workspace_module, "_draft_schema", lambda: schema)
        monkeypatch.setattr(workspace_module, "_session", sessionmaker(bind=database))
        monkeypatch.setattr(
            workspace_module, "_sync_batch_job_parent_columns", lambda **_kwargs: None,
        )
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()

        service = workspace_module.CustomQCWorkspaceService()
        service._record_result_envelope_table.metadata.create_all(database)

        build_id = "medqc-web-customer-20260925-100000"
        monkeypatch.setattr(identity, "_PROCESS_RUNTIME_BUILD", {
            "available": True, "build_id": build_id, "git_commit": "a" * 40,
        })
        config = {
            "provider_code": "alibaba",
            "api_endpoint": "https://example.invalid/llm",
            "api_key": "synthetic-test-secret",
            "model": "model-a", "source": "test",
        }
        qc_service = SichuanQCService(config)
        record_ref = CaseRef("HOSP-001", "PAT-001", "synthetic-visit")
        filters = {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "rule_ids": ["LX0609-01-01-01"],
            "record_refs": [record_ref.as_dict()],
            "selected_rule_ids": ["LX0609-01-01-01"],
            "scoped_customer_rule_ids": ["LX0609-01-01-01"],
            "active_customer_rule_ids": ["LX0609-01-01-01"],
            "pending_customer_rule_ids": [], "paused_customer_rule_ids": [],
            "record_rule_map": {record_ref.as_key(): ["LX0609-01-01-01"]},
            "validation_mode": "programmatic",
            "customer_rule_count": 1, "execution_rule_count": 1,
            "pending_rule_count": 0,
            identity.LX0609_TASK_SETTINGS_FILTER_KEY:
                identity.capture_luxian_0609_task_settings(
                    identity.resolve_mainline_rule_decision_settings(get_settings())
                ),
            identity.LX0609_TASK_RUNTIME_FILTER_KEY:
                identity.capture_luxian_0609_task_runtime(qc_service),
        }
        job = service.create_batch_job(
            draft={"id": "synthetic-draft", "rule_code": "LX0609-01-01-01",
                   "name": "合成规则", "scene": "final"},
            created_by="synthetic-tester", scope="final", filters=filters,
            record_ids=["synthetic-visit"], total_records=1,
            record_refs=[record_ref],
        )

        environment = os.environ.copy()
        environment.update({
            "DATABASE_URL": "postgresql://test:test@127.0.0.1:1/test",
            "JWT_SECRET": "isolated-test-secret-not-for-production-0609",
            "DB_SCHEMA_MODE": "single", "PYTHONIOENCODING": "utf-8",
            "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": "true",
        })
        completed = subprocess.run(
            [sys.executable, "-c", _FORMAL_WORKER_PROCESS,
             database_url, schema, str(job["id"]), build_id],
            cwd=Path(__file__).resolve().parents[2], env=environment,
            capture_output=True, text=True, encoding="utf-8", timeout=45,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout.splitlines()[-1])
        assert result == {
            "status": "completed",
            "result_statuses": ["data_gap"],
            "canonical_statuses": ["data_gap"],
            "total_tokens": 0,
        }
        with database.connect() as connection:
            count = connection.execute(
                sa.select(sa.func.count()).select_from(service._record_result_envelope_table)
            ).scalar_one()
        assert count == 1

        latest = service.build_latest_single_record_result_dto(
            institute_id="HOSP-001", patient_id="PAT-001",
            visit_id="synthetic-visit",
            expected_rule_ids=["LX0609-01-01-01"],
        )
        # 出口一：单病历结果页的唯一读取入口（Canonical Envelope 直读）。
        assert latest["state"] == "ready"
        assert latest["schema_version"] == "lx0609-single-record-result-v1"
        assert latest["data_origin"] == "canonical_result_envelope"
        assert latest["reason_code"] == ""
        assert latest["is_complete"] is True
        assert latest["expected_rule_count"] == latest["result_rule_count"] == 1
        assert latest["missing_rule_ids"] == []
        assert latest["conflicting_rule_ids"] == []
        assert re.fullmatch(r"rec_[0-9a-f]{24}", latest["record_ref"])
        assert len(latest["items"]) == 1
        latest_item = latest["items"][0]
        assert latest_item["rule_id"] == "LX0609-01-01-01"
        assert latest_item["record_ref"] == latest["record_ref"]
        # 冻结状态合同：status/result_status/display_status 同源，且 data_gap 不臆造合规性。
        assert {
            latest_item["status"], latest_item["result_status"], latest_item["display_status"],
        } == {"data_gap"}
        assert latest_item["is_compliant"] is None
        assert latest_item["reason_code"] == "authoritative_time_missing"
        assert latest_item["conclusion"] == latest_item["findings"] != ""
        assert latest_item["suggestion"] != ""
        assert latest_item["evidence"] == []

        saved_job = service.get_batch_job_for_processing(job_id=str(job["id"]))
        assert saved_job is not None and saved_job["status"] == "completed"

        # 出口二/三：CSV 与 XLSX 必须逐列同源，且与单病历出口的状态/原因码/结论/建议一致。
        csv_rows = list(csv.reader(io.StringIO(
            service.export_batch_job_csv(job=saved_job).getvalue()
        )))
        assert csv_rows[0] == ["管理摘要"]
        assert csv_rows[1][0] == "任务引用"
        assert csv_rows[2] == ["结果总数", "1"]
        assert csv_rows[3] == ["确定问题病历数", "0"]
        detail_index = csv_rows.index(["全部明细"])
        assert csv_rows[detail_index + 1] == CUSTOMER_EXPORT_HEADERS
        csv_data_rows = [row for row in csv_rows[detail_index + 2:] if row]
        assert len(csv_data_rows) == 1
        csv_item = dict(zip(CUSTOMER_EXPORT_HEADERS, csv_data_rows[0]))
        assert csv_item["病历引用"] == latest["record_ref"]
        assert csv_item["质控点编码"] == latest_item["rule_id"]
        assert csv_item["质控点名称"] == latest_item["rule_name"]
        assert csv_item["判定结果"] == "数据不足"
        assert csv_item["原因码"] == latest_item["reason_code"]
        assert csv_item["质控结论"] == latest_item["conclusion"]
        assert csv_item["处理建议"] == latest_item["suggestion"]
        assert csv_item["证据引用"] == ""

        from openpyxl import load_workbook
        workbook = load_workbook(service.export_batch_job_workbook(job=saved_job))
        assert workbook.sheetnames == ["管理摘要", "问题明细", "全部明细"]
        summary_cells = [list(row) for row in workbook["管理摘要"].iter_rows(values_only=True)]
        assert summary_cells[:4] == [
            ["报告项", "内容"],
            ["任务引用", csv_rows[1][1]],
            ["结果总数", 1],
            ["确定问题病历数", 0],
        ]
        assert summary_cells[4] == ["状态-data_gap", 1]
        # data_gap 不是确定问题，问题明细必须只有一个表头，不得由导出层臆造缺陷。
        assert [list(row) for row in workbook["问题明细"].iter_rows(values_only=True)] == [
            CUSTOMER_EXPORT_HEADERS,
        ]
        all_detail_rows = [list(row) for row in workbook["全部明细"].iter_rows(values_only=True)]
        assert all_detail_rows[0] == CUSTOMER_EXPORT_HEADERS
        assert len(all_detail_rows) == 2
        assert ["" if value is None else str(value) for value in all_detail_rows[1]] == csv_data_rows[0]

        # 出口四：HTML 客户报告不展示内部原因码，其余列与 CSV/XLSX 同源。
        html_text = service.export_batch_job_html(job=saved_job)
        assert 'class="status-pill status-data-gap">数据不足 1<' in html_text
        result_row = re.search(r"<tr data-result-row[^>]*>(.*?)</tr>", html_text, re.S)
        assert result_row is not None
        html_cells = [
            html_unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", result_row.group(1), re.S)
        ]
        assert html_cells == [
            csv_item["质控点编码"],
            csv_item["质控点名称"],
            csv_item["判定结果"],
            csv_item["质控结论"],
            csv_item["处理建议"],
            csv_item["证据引用"],
        ]
        assert latest_item["reason_code"] not in html_text
    finally:
        with database.begin() as connection:
            connection.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))
        database.dispose()
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()
