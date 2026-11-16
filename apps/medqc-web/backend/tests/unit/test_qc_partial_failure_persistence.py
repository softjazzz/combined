"""执行失败与临床结果分离：真实 SQLite 事务及客户 DTO。"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.routers import qc_sichuan
from app.services.case_identity import CaseRef
from app.services.qc_workspace.partial_record_delivery import select_complete_record_items
from app.services.qc_dispatch.repository import QCDispatchRepository

pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


def _install_retry_account(monkeypatch):
    from app.database import connection
    from app.database.models.v36_reports import SysUser
    from sqlalchemy.pool import StaticPool
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add(SysUser(id="tester", username="synthetic-retry-owner", display_name="合成重试账号",
                            password_hash="synthetic", role="qc_manager", institute_id="test-i", is_active=True))
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    return engine


@pytest.fixture
def storage(monkeypatch):
    account_engine = _install_retry_account(monkeypatch)
    service = workspace.CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    # 终态保存会整体替换该 root 的正式 Canonical，隔离库里也要有真实结果表。
    envelope_table = service._record_result_envelope_table.to_metadata(metadata, schema=None)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
    service._record_result_envelope_table = envelope_table
    monkeypatch.setattr(workspace, "_session", factory)
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="partial-job", draft_id="sichuan-rule-library", created_by="tester", status="running", rule_code="LX0609",
            created_at=datetime(2026, 9, 14), updated_at=datetime(2026, 9, 14),
            rule_name="测试", scope="final", total_records=1,
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05"],
                "record_refs": [
                    {"institute_id": "test-i", "patient_id": "test-p", "visit_id": "test-v"}
                ],
            }),
        ))
    def no_canonical(*args, **kwargs):
        pytest.fail("执行失败不得调用完整 Canonical 写入")
    monkeypatch.setattr(service, "_write_record_result_envelopes", no_canonical)
    yield service, engine, table
    engine.dispose()
    account_engine.dispose()


def _payload():
    identity = {"institute_id": "test-i", "patient_id": "test-p", "visit_id": "test-v"}
    item = {
        **identity, "rule_id": "LX0609-06-01-04", "rule_version": "2026-06-09",
        "schema_version": "lx0609-customer-result-v2",
        "status": "compliant", "result_status": "compliant", "display_status": "compliant",
        "is_compliant": True, "reason_code": "exam_result_recorded", "findings": "已记录检查结果。",
    }
    failure = {**identity, "rule_id": "LX0609-06-01-05", "reason_code": "model_invalid_output", "error_phase": "result_status"}
    summary = {
        "total_records": 1, "success_count": 0, "failed_count": 1, "compliant_records": 0,
        "execution_status": "partial_failed", "completed_rule_count": 1, "failed_rule_count": 1,
        "failed_rule_ids": ["LX0609-06-01-05"],
        "automatic_failed_rule_retry": {
            "max_attempts": 3,
            "completed_attempts": 0,
            "remaining_failure_count": 1,
            "status": "planned",
            "should_retry": True,
            "next_attempt": 1,
            "delay_seconds": 0.0,
            "internal_failure_details": "must-not-leak",
        },
        "model_execution_stats": {
            "scope": "exam_lab", "requested_rule_count": 2, "first_success_rule_count": 1,
            "retried_rule_count": 1, "recovered_rule_count": 0, "failed_rule_count": 1,
            "first_answer_success_rate": 0.5, "recovery_success_rate": 0.0, "model_failure_rate": 0.5,
        },
    }
    return summary, [item], [failure]


def test_partial_delivery_selects_only_complete_records_without_failures():
    record_a = {"institute_id": "test-i", "patient_id": "test-pa", "visit_id": "test-va"}
    record_b = {"institute_id": "test-i", "patient_id": "test-pb", "visit_id": "test-vb"}
    items = [
        {**record_a, "rule_id": "LX0609-06-01-04"},
        {**record_b, "rule_id": "LX0609-06-01-04"},
        {**record_b, "rule_id": "LX0609-06-01-05"},
    ]
    failures = [{**record_a, "rule_id": "LX0609-06-01-05"}]

    selected_items, selected_refs = select_complete_record_items(
        items=items,
        failures=failures,
        expected_rule_ids=["LX0609-06-01-04", "LX0609-06-01-05"],
    )

    assert [item["visit_id"] for item in selected_items] == ["test-vb", "test-vb"]
    assert [record_ref.as_dict() for record_ref in selected_refs] == [record_b]


def test_partial_delivery_fails_closed_when_failure_identity_is_incomplete():
    selected_items, selected_refs = select_complete_record_items(
        items=[{
            "institute_id": "test-i",
            "patient_id": "test-p",
            "visit_id": "test-v",
            "rule_id": "LX0609-06-01-04",
        }],
        failures=[{"visit_id": "test-v", "rule_id": "LX0609-06-01-05"}],
        expected_rule_ids=["LX0609-06-01-04"],
    )

    assert selected_items == ()
    assert selected_refs == ()


def test_progress_update_does_not_reload_complete_result_payload(storage, monkeypatch):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update()
            .where(table.c.id == "partial-job")
            .values(
                summary_json=json.dumps({"existing": True}),
                items_json=json.dumps([{"payload": "x" * 10000}]),
            )
        )

    monkeypatch.setattr(
        service,
        "get_batch_job_for_processing",
        lambda **_: pytest.fail("进度写入后不得重新加载完整任务结果"),
    )

    result = service.update_batch_job_progress(
        job_id="partial-job",
        step_key="run",
        rule_index=1,
        rule_count=2,
        processed_records=1,
        total_records=2,
        summary_patch={"success_count": 1},
    )

    assert result == {
        "id": "partial-job",
        "status": "running",
        "summary": {
            "existing": True,
            "success_count": 1,
            "rule_count": 2,
            "progress": {
                "step_key": "run",
                "rule_index": 1,
                "rule_count": 2,
                "processed_records": 1,
                "total_records": 2,
            },
            "updated_at": result["summary"]["updated_at"],
        },
    }
    with engine.connect() as connection:
        row = connection.execute(
            sa.select(table.c.items_json, table.c.summary_json).where(
                table.c.id == "partial-job"
            )
        ).one()
    assert len(json.loads(row.items_json)[0]["payload"]) == 10000
    assert json.loads(row.summary_json)["progress"]["processed_records"] == 1


def test_cancel_check_reads_only_task_status(storage):
    service, engine, table = storage

    assert service.is_batch_job_canceled_or_missing(job_id="partial-job") is False
    assert service.is_batch_job_canceled_or_missing(job_id="missing-job") is True

    with engine.begin() as connection:
        connection.execute(
            table.update()
            .where(table.c.id == "partial-job")
            .values(status="canceled")
        )

    assert service.is_batch_job_canceled_or_missing(job_id="partial-job") is True


@pytest.mark.parametrize("all_failed", [False, True])
def test_failed_job_persists_valid_items_and_operational_failure(storage, all_failed):
    service, engine, table = storage
    summary, items, failures = _payload()
    if all_failed:
        items = []
        failures.append({**failures[0], "rule_id": "LX0609-06-01-04"})
        summary.update(execution_status="failed", completed_rule_count=0, failed_rule_count=2, failed_count=2)
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items, failed_records=failures)
    with engine.connect() as connection:
        row = dict(connection.execute(sa.select(table)).mappings().one())
    assert row["status"] == "failed"
    assert json.loads(row["items_json"]) == items
    assert json.loads(row["failed_records_json"]) == failures
    saved = json.loads(row["summary_json"])
    assert saved["progress"]["step_key"] == "failed"
    job = workspace._row_to_batch_job(row, include_items=True)
    safe = workspace.project_customer_safe_batch_job(job, hmac_key="synthetic-test-key")
    assert safe["status"] == "failed"
    assert safe["summary"]["execution_status"] == summary["execution_status"]
    assert safe["summary"]["compliant_records"] == 0
    assert safe["summary"]["failed_rule_count"] == len(failures)
    assert safe["summary"]["model_execution_stats"]["model_failure_rate"] == 0.5
    assert safe["summary"]["automatic_failed_rule_retry"] == {
        "status": "planned",
        "max_attempts": 3,
        "completed_attempts": 0,
        "remaining_failure_count": 1,
        "should_retry": True,
        "next_attempt": 1,
        "delay_seconds": 0.0,
    }
    # 进程若在 planned 与实际入队之间退出，不得向客户端伪报 retrying。
    assert qc_sichuan._batch_job_status_for_header(job) == "failed"
    assert len(safe["items"]) == len(items)
    assert safe["failed_records"][0]["rule_id"] == "LX0609-06-01-05"


def test_failed_child_keeps_parent_failed_and_other_compliant_case_count(storage):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="parent-job", draft_id="test-draft", created_by="tester", status="running",
            rule_code="LX0609", rule_name="测试", scope="final", job_kind="parent",
            created_at=datetime(2026, 9, 14), updated_at=datetime(2026, 9, 14),
            child_job_ids_json='["partial-job"]',
        ))
        connection.execute(table.update().where(table.c.id == "partial-job").values(parent_job_id="parent-job"))
    summary, items, failures = _payload()
    items.append({**items[0], "patient_id": "test-p2", "visit_id": "test-v2"})
    summary.update(total_records=2, completed_rule_count=2, success_count=1, compliant_records=1)
    summary["model_execution_stats"]["raw_prompt"] = "must-not-leak"
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items, failed_records=failures)
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.status).where(table.c.id == "parent-job")).scalar_one() == "failed"
        parent_summary = json.loads(connection.execute(sa.select(table.c.summary_json).where(table.c.id == "parent-job")).scalar_one())
        assert parent_summary["execution_status"] == "partial_failed"
        assert parent_summary["completed_rule_count"] == 2
        assert parent_summary["failed_rule_count"] == 1
        row = dict(connection.execute(sa.select(table).where(table.c.id == "partial-job")).mappings().one())
    safe = workspace.project_customer_safe_batch_job(workspace._row_to_batch_job(row, include_items=True), hmac_key="synthetic-test-key")
    assert safe["summary"]["compliant_records"] == 1
    assert "must-not-leak" not in json.dumps(safe)


def test_partial_job_writes_only_fully_completed_record_envelopes(storage, monkeypatch):
    service, engine, table = storage
    record_a = {"institute_id": "test-i", "patient_id": "test-pa", "visit_id": "test-va"}
    record_b = {"institute_id": "test-i", "patient_id": "test-pb", "visit_id": "test-vb"}
    with engine.begin() as connection:
        connection.execute(
            table.update()
            .where(table.c.id == "partial-job")
            .values(
                total_records=2,
                record_ids_json=json.dumps(["test-va", "test-vb"]),
                filters_json=json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05"],
                    "record_refs": [record_a, record_b],
                }),
            )
        )

    def item(identity, rule_id):
        return {
            **identity,
            "rule_id": rule_id,
            "rule_version": "2026-06-09",
            "schema_version": "lx0609-customer-result-v2",
            "status": "compliant",
            "result_status": "compliant",
            "display_status": "compliant",
            "is_compliant": True,
            "reason_code": "fact_present",
            "findings": "已完成核对。",
        }

    items = [
        item(record_a, "LX0609-06-01-04"),
        item(record_b, "LX0609-06-01-04"),
        item(record_b, "LX0609-06-01-05"),
    ]
    failures = [{
        **record_a,
        "rule_id": "LX0609-06-01-05",
        "reason_code": "model_invalid_output",
        "error_phase": "result_status",
    }]
    summary = {
        "total_records": 2,
        "success_count": 1,
        "failed_count": 1,
        "execution_status": "partial_failed",
        "completed_rule_count": 3,
        "failed_rule_count": 1,
        "failed_rule_ids": ["LX0609-06-01-05"],
    }
    captured = {}

    def capture_envelopes(*_args, **kwargs):
        captured.update(kwargs)
        return ()

    monkeypatch.setattr(service, "_write_record_result_envelopes", capture_envelopes)

    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )

    assert [item["visit_id"] for item in captured["items"]] == ["test-vb", "test-vb"]
    assert [record_ref.as_dict() for record_ref in captured["expected_record_refs"]] == [record_b]
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.status)).scalar_one() == "failed"


def test_non_luxian_partial_job_does_not_write_luxian_envelopes(storage, monkeypatch):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update()
            .where(table.c.id == "partial-job")
            .values(filters_json=json.dumps({
                "rule_set_key": "another_rule_set",
                "rule_ids": ["OTHER-001"],
            }))
        )

    monkeypatch.setattr(
        service,
        "_write_record_result_envelopes",
        lambda *_args, **_kwargs: pytest.fail("不应写入泸县 Canonical Envelope"),
    )

    service.complete_batch_job(
        job_id="partial-job",
        summary={
            "total_records": 1,
            "success_count": 0,
            "failed_count": 1,
            "execution_status": "failed",
            "completed_rule_count": 0,
            "failed_rule_count": 1,
            "failed_rule_ids": ["OTHER-001"],
        },
        items=[],
        failed_records=[{
            "institute_id": "test-i",
            "patient_id": "test-p",
            "visit_id": "test-v",
            "rule_id": "OTHER-001",
            "reason_code": "model_invalid_output",
            "error_phase": "result_status",
        }],
    )


def test_partial_envelope_writer_narrows_record_contract_without_mutating_job(monkeypatch):
    service = workspace.CustomQCWorkspaceService()
    record_a = {"institute_id": "test-i", "patient_id": "test-pa", "visit_id": "test-va"}
    record_b = {"institute_id": "test-i", "patient_id": "test-pb", "visit_id": "test-vb"}
    job_row = {
        "id": "partial-job",
        "filters_json": json.dumps({
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_ids": ["LX0609-06-01-04"],
            "record_refs": [record_a, record_b],
        }),
    }
    captured = {}

    class CapturingStore:
        def __init__(self, _table):
            pass

        def replace_for_job(self, _session, **kwargs):
            captured.update(kwargs)
            return ()

    monkeypatch.setattr(workspace, "CanonicalResultStore", CapturingStore)

    service._write_record_result_envelopes(
        object(),
        job_row=job_row,
        items=[{**record_b, "rule_id": "LX0609-06-01-04"}],
        now=datetime(2026, 9, 15),
        expected_record_refs=[CaseRef.from_mapping(record_b)],
    )

    assert json.loads(captured["job_row"]["filters_json"])["record_refs"] == [record_b]
    assert json.loads(job_row["filters_json"])["record_refs"] == [record_a, record_b]


@pytest.mark.parametrize("invalid", ["bad_item", "no_failure"])
def test_partial_failure_is_not_a_bypass_for_invalid_delivery(storage, invalid):
    service, engine, table = storage
    summary, items, failures = _payload()
    if invalid == "bad_item":
        items[0].update(status="technical_error", result_status="technical_error", display_status="technical_error")
    else:
        failures = []
    with pytest.raises(ValueError):
        service.complete_batch_job(job_id="partial-job", summary=summary, items=items, failed_records=failures)
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.status)).scalar_one() == "running"


def test_retry_partial_failure_preserves_valid_items_and_queues_only_failed_rule(storage):
    service, engine, table = storage
    summary, items, failures = _payload()
    # 输出格式错误按现行合同不自动重跑；此正例验证可恢复的传输故障。
    failures[0]["reason_code"] = "model_transport_error"
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )

    with engine.connect() as connection:
        accepted_filters_json = connection.execute(
            sa.select(table.c.filters_json).where(table.c.id == "partial-job")
        ).scalar_one()
    assert service.retry_batch_job(
        job_id="partial-job",
        created_by="tester",
        automatic=True,
        expected_attempt_filters_json='{"stale_attempt":true}',
    ) is None
    retried = service.retry_batch_job(
        job_id="partial-job",
        created_by="tester",
        automatic=True,
        expected_attempt_filters_json=accepted_filters_json,
    )

    assert retried is not None
    assert retried["status"] == "queued"
    assert retried["id"] != "partial-job"
    assert retried["items"] == retried["failed_records"] == []
    retry_scope = retried["filters"]["failed_rule_retry"]
    assert retry_scope["rule_ids"] == ["LX0609-06-01-05"]
    assert retry_scope["record_refs"] == [
        {"institute_id": "test-i", "patient_id": "test-p", "visit_id": "test-v"}
    ]
    assert retry_scope["pending_count"] == 1
    assert "execution_status" not in retried["summary"]


    assert retried["summary"]["retry_status"] == "queued"
    assert retried["summary"]["retry_trigger"] == "automatic"
    safe = workspace.project_customer_safe_batch_job(
        retried,
        hmac_key="synthetic-test-key",
    )
    assert safe["items"] == safe["failed_records"] == []
    assert safe["retry_of_job_id"] == "partial-job"
    with engine.connect() as connection:
        row = dict(connection.execute(sa.select(table).where(table.c.id == "partial-job")).mappings().one())
    assert json.loads(row["items_json"]) == items
    assert json.loads(row["failed_records_json"]) == failures


@pytest.mark.parametrize("enqueue_outcome", ["queued", "none", "raise"])
def test_mq_auto_retry_preserves_success_and_delays_only_one_next_generation(
    storage, monkeypatch, enqueue_outcome,
):
    """业务线失败提示与 MQ 延迟投递使用同一个真实事务 owner。"""
    service, engine, table = storage
    sessions = sessionmaker(bind=engine)
    repository = QCDispatchRepository(sessions, table, schema=None)
    repository.dispatch_table.metadata.create_all(engine)
    service._qc_dispatch = repository
    job_id = str(uuid.uuid4())
    now = datetime(2026, 10, 31, 12, 0, 0)
    monkeypatch.setattr(workspace, "_now_utc", lambda: now)
    with sessions.begin() as session:
        filters = json.loads(session.execute(sa.select(table.c.filters_json)).scalar_one())
        filters["qc_dispatch"] = {"schema_version": 1, "mode": "rabbitmq"}
        session.execute(table.update().values(id=job_id, filters_json=json.dumps(filters)))
        repository.add_dispatch(session, job_id=job_id, mode="rabbitmq", enqueue_leaf=True)

    summary, items, failures = _payload()
    failures[0]["reason_code"] = "model_transport_error"
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id=job_id, summary=summary, items=items, failed_records=failures,
    )
    before = service.get_batch_job_for_processing(job_id=job_id)
    with sessions() as session:
        expected_filters = session.execute(sa.select(table.c.filters_json)).scalar_one()
    original_retry = service.retry_batch_job
    calls = []

    def enqueue_once(**kwargs):
        calls.append(kwargs)
        if enqueue_outcome == "raise":
            raise RuntimeError("synthetic MQ enqueue failure")
        if enqueue_outcome == "none":
            return None
        return original_retry(**kwargs)

    monkeypatch.setattr(service, "retry_batch_job", enqueue_once)
    kwargs = dict(
        workspace=service, job_id=job_id, created_by="tester",
        expected_attempt_filters_json=expected_filters, retry_delay_seconds=17.0,
    )
    if enqueue_outcome == "raise":
        with pytest.raises(RuntimeError, match="synthetic MQ enqueue failure"):
            batch_worker._enqueue_automatic_failed_rule_retry(**kwargs)
    else:
        result = batch_worker._enqueue_automatic_failed_rule_retry(**kwargs)
        assert (result is not None) == (enqueue_outcome == "queued")

    assert len(calls) == 1
    assert calls[0]["retry_delay_seconds"] == 17.0
    assert calls[0]["expected_attempt_filters_json"] == expected_filters
    after = service.get_batch_job_for_processing(job_id=job_id)
    assert after["items"] == before["items"]
    assert len(after["failed_records"]) == len(before["failed_records"]) == 1
    assert all(
        after["failed_records"][0][key] == value
        for key, value in before["failed_records"][0].items()
    )
    with sessions() as session:
        outbox = session.execute(sa.select(repository.outbox_table)).mappings().all()
    dispatch = repository.get_dispatch(job_id)
    if enqueue_outcome == "queued":
        assert after["status"] == "failed"
        assert result["id"] != job_id
        assert result["summary"]["automatic_failed_rule_retry"]["status"] == "queued"
        assert result["items"] == result["failed_records"] == []
        assert dispatch.generation == 1
        assert dispatch.recovery_reason_code == "retry_successor_created"
        successor = repository.get_dispatch(result["id"])
        assert successor.generation == 1
        assert successor.failure_count == dispatch.failure_count + 1
        assert successor.failure_budget == dispatch.failure_budget
        assert all(candidate.job_id != job_id for candidate in repository.list_recovery_candidates())
        from app.qc_worker.recovery import WorkerRecovery, RecoveryOutcome
        assert WorkerRecovery(repository=repository, workspace=service).recover_failed_job(job_id) == RecoveryOutcome.RETRY_SCHEDULED
        # 旧扫描器持有的分类写入不能撤销已提交的独立重试关联。
        assert repository.register_recovery(job_id, dispatch.generation, recovery_kind="unstarted",
                                             reason_code="stale_scan") is False
        assert repository.record_terminal_failure(job_id, dispatch.generation, error_code="worker_failed") is False
        assert len(outbox) == 2
        next_delivery = next(row for row in outbox if row["job_id"] == result["id"])
        assert next_delivery["available_at"] == now + timedelta(seconds=17)
    else:
        assert after["status"] == "failed"
        plan = after["summary"]["automatic_failed_rule_retry"]
        assert plan["status"] == "enqueue_failed"
        assert plan["should_retry"] is False
        assert dispatch.generation == 1
        assert len(outbox) == 1


def test_automatic_retry_announces_queued_only_after_retry_cas_succeeds(storage):
    service, engine, table = storage
    summary, items, failures = _payload()
    failures[0]["reason_code"] = "model_transport_error"
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )
    with engine.connect() as connection:
        expected_filters = connection.execute(
            sa.select(table.c.filters_json).where(table.c.id == "partial-job")
        ).scalar_one()

    queued = batch_worker._enqueue_automatic_failed_rule_retry(
        workspace=service,
        job_id="partial-job",
        created_by="tester",
        expected_attempt_filters_json=expected_filters,
    )

    assert queued is not None and queued["status"] == "queued"
    assert queued["summary"]["automatic_failed_rule_retry"]["status"] == "queued"
    assert queued["summary"]["automatic_failed_rule_retry"]["should_retry"] is True
    queued_items = list(queued["items"])
    queued_failures = list(queued["failed_records"])
    running_claim = service.mark_batch_job_running(job_id=queued["id"])
    assert isinstance(running_claim, str)
    running = service.get_batch_job_for_processing(job_id=queued["id"])
    assert running["summary"]["automatic_failed_rule_retry"]["status"] == "running"
    assert running["items"] == queued_items
    assert running["failed_records"] == queued_failures

    service.fail_batch_job(
        job_id=queued["id"],
        attempt_filters_json=running_claim,
        error_message="synthetic retry execution interruption",
    )
    interrupted = service.get_batch_job(job_id=queued["id"], created_by="tester")
    interrupted_plan = interrupted["summary"]["automatic_failed_rule_retry"]
    assert interrupted["status"] == "failed"
    assert interrupted_plan["status"] == "interrupted"
    assert interrupted_plan["should_retry"] is False
    assert interrupted_plan["reason_code"] == "retry_execution_interrupted"
    assert interrupted["items"] == queued_items
    assert interrupted["failed_records"] == queued_failures
    safe_interrupted = workspace.project_customer_safe_batch_job(
        interrupted,
        hmac_key="synthetic-test-key",
    )
    assert safe_interrupted["summary"]["automatic_failed_rule_retry"] == {
        "status": "interrupted",
        "max_attempts": 3,
        "completed_attempts": 0,
        "remaining_failure_count": 1,
        "should_retry": False,
        "next_attempt": 1,
        "delay_seconds": 0.0,
        "reason_code": "retry_execution_interrupted",
    }
    assert qc_sichuan._batch_job_status_for_header(interrupted) == "failed"


@pytest.mark.parametrize("late_after_claim", [False, True], ids=["queued-fails", "late-queued-cas"])
def test_queued_auto_retry_failure_terminates_only_the_exact_queued_generation(
    storage,
    late_after_claim,
):
    service, engine, table = storage
    summary, items, failures = _payload()
    failures[0]["reason_code"] = "model_transport_error"
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )
    with engine.connect() as connection:
        completed_filters = connection.execute(
            sa.select(table.c.filters_json).where(table.c.id == "partial-job")
        ).scalar_one()
    queued = batch_worker._enqueue_automatic_failed_rule_retry(
        workspace=service,
        job_id="partial-job",
        created_by="tester",
        expected_attempt_filters_json=completed_filters,
    )
    assert queued is not None and queued["status"] == "queued"
    with engine.connect() as connection:
        queued_filters = connection.execute(
            sa.select(table.c.filters_json).where(table.c.id == queued["id"])
        ).scalar_one()
    queued_items = list(queued["items"])
    queued_failures = list(queued["failed_records"])

    running_claim = None
    if late_after_claim:
        running_claim = service.mark_batch_job_running(job_id=queued["id"])
        assert isinstance(running_claim, str)
    service.fail_batch_job(
        job_id=queued["id"],
        queued_only=True,
        expected_queued_filters_json=queued_filters,
        error_message="synthetic queued start failure",
    )
    current = service.get_batch_job(job_id=queued["id"], created_by="tester")
    assert current["items"] == queued_items
    assert current["failed_records"] == queued_failures
    if late_after_claim:
        assert current["status"] == "running"
        assert current["summary"]["automatic_failed_rule_retry"]["status"] == "running"
        service.fail_batch_job(
            job_id=queued["id"],
            attempt_filters_json=running_claim,
            error_message="cleanup current generation",
        )
    else:
        retry_plan = current["summary"]["automatic_failed_rule_retry"]
        assert current["status"] == "failed"
        assert retry_plan["status"] == "interrupted"
        assert retry_plan["should_retry"] is False
        assert retry_plan["reason_code"] == "retry_start_interrupted"
        assert "luxian_0609_usage_observation_complete" not in current["summary"]
        assert qc_sichuan._batch_job_status_for_header(current) == "failed"


@pytest.mark.parametrize("failure_mode", ["return_none", "raise"])
def test_automatic_retry_enqueue_failure_revokes_planned_without_erasing_results(
    storage,
    monkeypatch,
    failure_mode,
):
    service, engine, table = storage
    summary, items, failures = _payload()
    failures[0]["reason_code"] = "model_transport_error"
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )
    persisted_before_enqueue = service.get_batch_job(
        job_id="partial-job",
        created_by="tester",
    )
    with engine.connect() as connection:
        expected_filters = connection.execute(
            sa.select(table.c.filters_json).where(table.c.id == "partial-job")
        ).scalar_one()

    def _failed_enqueue(**_kwargs):
        if failure_mode == "raise":
            raise RuntimeError("synthetic enqueue failure")
        return None

    monkeypatch.setattr(service, "retry_batch_job", _failed_enqueue)
    if failure_mode == "raise":
        with pytest.raises(RuntimeError, match="synthetic enqueue failure"):
            batch_worker._enqueue_automatic_failed_rule_retry(
                workspace=service,
                job_id="partial-job",
                created_by="tester",
                expected_attempt_filters_json=expected_filters,
            )
    else:
        assert batch_worker._enqueue_automatic_failed_rule_retry(
            workspace=service,
            job_id="partial-job",
            created_by="tester",
            expected_attempt_filters_json=expected_filters,
        ) is None

    persisted = service.get_batch_job(job_id="partial-job", created_by="tester")
    retry_plan = persisted["summary"]["automatic_failed_rule_retry"]
    assert persisted["status"] == "failed"
    assert retry_plan["status"] == "enqueue_failed"
    assert retry_plan["should_retry"] is False
    assert retry_plan["reason_code"] == "retry_enqueue_failed"
    assert persisted["items"] == persisted_before_enqueue["items"]
    assert persisted["failed_records"] == persisted_before_enqueue["failed_records"]
    assert qc_sichuan._batch_job_status_for_header(persisted) == "failed"


def test_output_format_failure_does_not_auto_retry_or_erase_valid_results(storage):
    service, engine, table = storage
    summary, items, failures = _payload()
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items, failed_records=failures)
    with engine.connect() as connection:
        before = dict(connection.execute(sa.select(table).where(table.c.id == "partial-job")).mappings().one())
    assert service.retry_batch_job(job_id="partial-job", created_by="tester", automatic=True,
                                   expected_attempt_filters_json=before["filters_json"]) is None
    with engine.connect() as connection:
        after = dict(connection.execute(sa.select(table).where(table.c.id == "partial-job")).mappings().one())
    assert after == before


def test_automatic_retry_skips_terminal_pair_without_losing_it_or_successful_items(storage):
    service, engine, table = storage
    summary, items, failures = _payload()
    terminal = {**failures[0], "rule_id": "LX0609-05-01-03", "reason_code": "model_invalid_output"}
    transient = {**failures[0], "rule_id": "LX0609-06-01-05", "reason_code": "model_timeout"}
    summary.update(failed_rule_count=2, failed_rule_ids=[terminal["rule_id"], transient["rule_id"]])
    with engine.begin() as conn:
        filters = json.loads(conn.execute(sa.select(table.c.filters_json)).scalar_one())
        filters["rule_ids"] = [items[0]["rule_id"], terminal["rule_id"], transient["rule_id"]]
        conn.execute(table.update().values(filters_json=json.dumps(filters)))
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items,
                               failed_records=[terminal, transient])
    with engine.connect() as conn:
        expected = conn.execute(sa.select(table.c.filters_json)).scalar_one()
    retried = service.retry_batch_job(job_id="partial-job", created_by="tester", automatic=True,
                                     expected_attempt_filters_json=expected)
    assert retried["filters"]["failed_rule_retry"]["rule_ids"] == [transient["rule_id"]]
    assert retried["filters"]["failed_rule_retry"]["pending_count"] == 1
    assert retried["failed_records"] == retried["items"] == []
    original = service.get_batch_job(job_id="partial-job", created_by="tester")
    assert len(original["failed_records"]) == 2
    assert original["items"][0]["rule_id"] == items[0]["rule_id"]


@pytest.mark.parametrize("rule_id", ("LX0609-03-01-04", "LX0609-04-02-07", "LX0609-12-02-01"))
@pytest.mark.parametrize("automatic", (False, True))
def test_paused_rule_retry_stops_new_attempt_and_preserves_history(storage, rule_id, automatic):
    """暂停后不再创建重试任务，已保存的成功项和失败事实保持不变。"""
    service, engine, table = storage
    summary, items, failures = _payload()
    failure = {**failures[0], "rule_id": rule_id, "reason_code": "model_timeout"}
    summary.update(failed_rule_ids=[rule_id])
    with engine.begin() as conn:
        filters = json.loads(conn.execute(sa.select(table.c.filters_json)).scalar_one())
        filters["rule_ids"] = [items[0]["rule_id"], rule_id]
        conn.execute(table.update().values(filters_json=json.dumps(filters)))
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items,
                               failed_records=[failure])
    with engine.connect() as conn:
        before = [dict(row) for row in conn.execute(sa.select(table)).mappings()]

    with pytest.raises(ValueError, match="retry_rule_scope_paused"):
        service.retry_batch_job(job_id="partial-job", created_by="tester", automatic=automatic,
                                expected_attempt_filters_json=before[0]["filters_json"])

    with engine.connect() as conn:
        after = [dict(row) for row in conn.execute(sa.select(table)).mappings()]
    assert after == before
    original = service.get_batch_job(job_id="partial-job", created_by="tester")
    assert original["items"][0]["rule_id"] == items[0]["rule_id"]
    assert original["failed_records"][0]["rule_id"] == rule_id
    assert original["failed_records"][0]["reason_code"] == "model_timeout"


def test_automatic_terminal_retry_does_not_fall_back_to_full_batch(storage):
    service, engine, table = storage
    summary, items, failures = _payload()
    failure = {**failures[0], "rule_id": "LX0609-06-01-05", "reason_code": "execution_program_error"}
    with engine.begin() as conn:
        filters = json.loads(conn.execute(sa.select(table.c.filters_json)).scalar_one())
        filters["rule_ids"] = [items[0]["rule_id"], failure["rule_id"]]
        conn.execute(table.update().values(filters_json=json.dumps(filters)))
    summary.update(failed_rule_ids=[failure["rule_id"]])
    service.complete_batch_job(job_id="partial-job", summary=summary, items=items, failed_records=[failure])
    with engine.connect() as conn:
        expected = conn.execute(sa.select(table.c.filters_json)).scalar_one()
    assert service.retry_batch_job(job_id="partial-job", created_by="tester", automatic=True,
                                    expected_attempt_filters_json=expected) is None
    current = service.get_batch_job(job_id="partial-job", created_by="tester")
    assert current["status"] == "failed"
    assert current["items"][0]["rule_id"] == items[0]["rule_id"]


@pytest.mark.asyncio
async def test_retry_route_returns_customer_safe_partial_result(storage, monkeypatch):
    service, _, _ = storage
    summary, items, failures = _payload()
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args, **kwargs: None)
    from unittest.mock import AsyncMock
    monkeypatch.setattr(qc_sichuan, "get_qc_service", AsyncMock(return_value=object()))
    monkeypatch.setattr(qc_sichuan, "capture_luxian_0609_task_runtime", lambda _: {"synthetic": True})

    response = await qc_sichuan.retry_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        job_id="partial-job",
        current_user={"id": "tester"},
    )

    payload = response["data"]
    assert payload["status"] == "queued"
    assert payload["retry_of_job_id"] == "partial-job"
    assert payload["items"] == payload["failed_records"] == []
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "test-p" not in serialized
    assert "test-v" not in serialized


# --- 原始 0609 叶子根任务：终态保存必须整体替换该 root 的 Canonical ---

_RERUN_RULE_IDS = ("LX0609-06-01-04", "LX0609-06-01-05")
_RERUN_RECORD_A = {"institute_id": "test-i", "patient_id": "test-pa", "visit_id": "test-va"}
_RERUN_RECORD_B = {"institute_id": "test-i", "patient_id": "test-pb", "visit_id": "test-vb"}


def _canonical_item(identity: dict, rule_id: str) -> dict:
    return {
        **identity,
        "rule_id": rule_id,
        "rule_version": workspace.RULE_SET_VERSION,
        "schema_version": "lx0609-customer-result-v2",
        "status": "compliant",
        "result_status": "compliant",
        "display_status": "compliant",
        "is_compliant": True,
        "reason_code": "fact_present",
        "findings": "已完成核对。",
    }


def _rule_failure(identity: dict, rule_id: str) -> dict:
    return {
        **identity,
        "rule_id": rule_id,
        "reason_code": "model_invalid_output",
        "error_phase": "result_status",
        "error": "规则执行未形成可交付结果",
    }


def _partial_summary(*, total_records: int, delivered: int, failed_rules: list[str]) -> dict:
    return {
        "total_records": total_records,
        "success_count": total_records - 1,
        "failed_count": 1,
        "execution_status": "partial_failed",
        "completed_rule_count": delivered,
        "failed_rule_count": len(failed_rules),
        "failed_rule_ids": list(failed_rules),
    }


def _completed_summary(*, total_records: int, delivered: int) -> dict:
    return {
        "total_records": total_records,
        "success_count": total_records,
        "failed_count": 0,
        "execution_status": "completed",
        "completed_rule_count": delivered,
        "failed_rule_count": 0,
        "failed_rule_ids": [],
    }


def _root_envelope_refs(engine, envelopes, *, root_job_id: str) -> list[tuple[str, int]]:
    with engine.connect() as connection:
        return sorted(
            (row["visit_id"], row["result_count"])
            for row in connection.execute(
                sa.select(envelopes.c.visit_id, envelopes.c.result_count).where(
                    envelopes.c.root_job_id == root_job_id
                )
            ).mappings()
        )


def _load_job(engine, jobs, *, job_id: str) -> dict:
    with engine.connect() as connection:
        return workspace._row_to_batch_job(
            dict(
                connection.execute(sa.select(jobs).where(jobs.c.id == job_id))
                .mappings()
                .one()
            ),
            include_items=True,
        )


@pytest.fixture
def canonical_storage(monkeypatch):
    """叶子根任务的正式 Canonical 写入：任务表与结果表都落在隔离 SQLite。"""

    account_engine = _install_retry_account(monkeypatch)
    service = workspace.CustomQCWorkspaceService()
    metadata = sa.MetaData()
    jobs = service._batch_job_table.to_metadata(metadata, schema=None)
    envelopes = service._record_result_envelope_table.to_metadata(metadata, schema=None)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = jobs
    service._record_result_envelope_table = envelopes
    monkeypatch.setattr(workspace, "_session", factory)
    with engine.begin() as connection:
        connection.execute(jobs.insert().values(
            id="rerun-job",
            draft_id="sichuan-rule-library",
            created_by="tester",
            status="queued",
            rule_code="LX0609",
            rule_name="重跑验证任务",
            scope="final",
            created_at=datetime(2026, 9, 20),
            updated_at=datetime(2026, 9, 20),
            total_records=2,
            record_ids_json=json.dumps(["test-va", "test-vb"]),
            filters_json=json.dumps({
                "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": workspace.RULE_SET_VERSION,
                "rule_ids": list(_RERUN_RULE_IDS),
                "scoped_customer_rule_ids": list(_RERUN_RULE_IDS),
                "record_refs": [_RERUN_RECORD_A, _RERUN_RECORD_B],
            }),
        ))
    yield service, engine, jobs, envelopes
    engine.dispose()
    account_engine.dispose()


def _complete_full_run(service) -> str:
    claim = service.mark_batch_job_running(job_id="rerun-job")
    assert isinstance(claim, str)
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=claim,
        summary=_completed_summary(total_records=2, delivered=4),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[],
    ) is True
    return claim


@pytest.mark.parametrize("previous_full", [False, True])
@pytest.mark.parametrize("delivered", [0, 1])
def test_pool_and_worklist_show_same_partial_round_as_detail_and_export(
    canonical_storage, monkeypatch, previous_full, delivered,
):
    from app.services.medical_records import query_service
    from app.services.workstation.worklist_service import WorkstationAggregationService

    service, engine, jobs, _ = canonical_storage
    if previous_full:
        _complete_full_run(service)
    with engine.begin() as connection:
        template = dict(connection.execute(sa.select(jobs)).mappings().first())
        template.update(id="new-partial", status="queued", summary_json=None, items_json=None,
                        failed_records_json=None, finished_at=None,
                        created_at=datetime(2026, 9, 22), updated_at=datetime(2026, 9, 22))
        connection.execute(jobs.insert().values(**template))
    claim = service.mark_batch_job_running(job_id="new-partial")
    items = [_canonical_item(_RERUN_RECORD_A, rule) for rule in _RERUN_RULE_IDS]
    items += [_canonical_item(_RERUN_RECORD_B, rule) for rule in _RERUN_RULE_IDS[:delivered]]
    failed_rules = list(_RERUN_RULE_IDS[delivered:])
    assert service.complete_batch_job(
        job_id="new-partial", attempt_filters_json=claim,
        summary={**_partial_summary(total_records=2, delivered=len(items), failed_rules=failed_rules),
                 "rule_results": [{"rule_code": rule, "items": [x for x in items if x["rule_id"] == rule]}
                                  for rule in _RERUN_RULE_IDS]},
        items=items, failed_records=[_rule_failure(_RERUN_RECORD_B, rule) for rule in failed_rules],
    )
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(workspace, "CustomQCWorkspaceService", lambda: service)
    owner = object.__new__(WorkstationAggregationService)
    owner._session_factory = factory
    identity = tuple(CaseRef.from_mapping(_RERUN_RECORD_B))
    pool = query_service._load_latest_luxian_0609_qc_summaries(
        [_RERUN_RECORD_B], session_factory=factory,
    )[identity]
    worklist = owner._load_luxian_0609_summaries([_RERUN_RECORD_B])[identity]
    detail = service.build_latest_single_record_result_dto(**_RERUN_RECORD_B)
    exported = service.build_luxian_0609_completed_record_result_summaries(
        record_refs=[_RERUN_RECORD_B], include_latest_partial=True,
        session_factory=factory,
    )[identity]
    assert pool == worklist == exported
    assert detail["state"] == "ready"
    assert pool["status"] == ("ready" if delivered else "failed")
    assert pool["job_id"] == detail["job_id"] == "new-partial"
    assert pool["total_rule_count"] == detail["completed_rule_count"] == delivered
    assert pool["failed_rule_ids"] == detail["failed_rule_ids"] == failed_rules
    bulk = service.build_latest_luxian_0609_record_result_dtos(record_refs=[_RERUN_RECORD_B])[identity]
    assert bulk["state"] == "ready"
    assert bulk["execution_status"] == detail["execution_status"]
    assert bulk["failed_rule_ids"] == failed_rules
    normalized = query_service._normalize_latest_qc_summary_map({identity: pool})
    assert normalized[identity]["execution_status"] == detail["execution_status"]
    assert normalized[identity]["failed_rule_ids"] == failed_rules
    counts = query_service._build_qc_summary([_RERUN_RECORD_B], normalized)
    assert counts["ready_records"] == counts["not_run_records"] == 0
    assert counts["partial_failed_records" if delivered else "failed_records"] == 1
    monkeypatch.setattr(owner, "_load_luxian_home_records", lambda *_args, **_kwargs: [
        {**ref, "department": "合成科室"} for ref in (_RERUN_RECORD_A, _RERUN_RECORD_B)
    ])
    home = owner._build_luxian_0609_home_projection(
        None, department=None, keyword=None, priority_limit=10,
    )
    assert home["kpis"]["qc_completed_total"] == 1
    assert home["kpis"]["qc_partial_failed_total" if delivered else "qc_failed_total"] == 1


def _insert_independent_full_task(engine, jobs):
    """合成新建任务；全量再执行不再允许重置上一轮任务身份。"""
    with engine.begin() as connection:
        template = dict(connection.execute(sa.select(jobs).where(jobs.c.id == "rerun-job")).mappings().one())
        template.update(id="new-full-job", status="queued", summary_json=None, items_json=None,
                        failed_records_json=None, error_message=None, started_at=None, finished_at=None,
                        success_count=0, failed_count=0,
                        created_at=datetime(2027, 1, 1), updated_at=datetime(2027, 1, 1))
        connection.execute(jobs.insert().values(**template))


def test_new_full_task_preserves_previous_canonical_and_shows_current_partial(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    first_claim = _complete_full_run(service)
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [
        ("test-va", 2),
        ("test-vb", 2),
    ]

    previous_job = _load_job(engine, jobs, job_id="rerun-job")
    new_id = service.retry_batch_job(job_id="rerun-job", created_by="tester")["id"]
    rerun_claim = service.mark_batch_job_running(job_id=new_id)
    assert isinstance(rerun_claim, str) and rerun_claim != first_claim
    current_items = [
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
    ]
    assert service.complete_batch_job(
        job_id=new_id,
        attempt_filters_json=rerun_claim,
        summary={**_partial_summary(total_records=2, delivered=3, failed_rules=[_RERUN_RULE_IDS[1]]),
                 "rule_results": [{"rule_code": rule, "items": [item for item in current_items
                                   if item["rule_id"] == rule]} for rule in _RERUN_RULE_IDS]},
        items=current_items,
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True

    job = _load_job(engine, jobs, job_id=new_id)
    root_refs = _root_envelope_refs(engine, envelopes, root_job_id=new_id)
    assert root_refs == [("test-va", 2)]
    assert len(root_refs) == job["success_count"] == 1
    assert _load_job(engine, jobs, job_id="rerun-job") == previous_job
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [("test-va", 2), ("test-vb", 2)]

    stale = service.build_latest_single_record_result_dto(
        institute_id=_RERUN_RECORD_B["institute_id"],
        patient_id=_RERUN_RECORD_B["patient_id"],
        visit_id=_RERUN_RECORD_B["visit_id"],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )
    # 同次失败任务的有效项仍可查看；不能取回上轮该病例的第二条合规结果。
    assert stale["state"] == "ready"
    assert stale["data_origin"] == "saved_partial_task"
    assert stale["job_id"] == new_id
    assert stale["is_complete"] is False
    assert stale["completed_rule_count"] == 1
    assert stale["failed_rule_ids"] == [_RERUN_RULE_IDS[1]]
    assert [item["rule_id"] for item in stale["items"]] == [_RERUN_RULE_IDS[0]]

    export_items = service._load_batch_job_export_items(job=job)
    # 导出只包含本次实际交付的病历结果（客户投影不保留原三坐标字段）。
    assert len(export_items) == 2
    assert {item["display_status"] for item in export_items} == {"compliant"}


def test_precise_retry_interruption_keeps_authoritative_success_items_readable(canonical_storage):
    """精确新尝试不冒充原全量交付，较完整原任务仍按其身份只读。"""

    service, engine, jobs, _ = canonical_storage
    first_claim = service.mark_batch_job_running(job_id="rerun-job")
    initial_items = [
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
    ]
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=first_claim,
        summary={
            **_partial_summary(
                total_records=2,
                delivered=len(initial_items),
                failed_rules=[_RERUN_RULE_IDS[1]],
            ),
            "rule_results": [
                {
                    "rule_code": rule_id,
                    "items": [item for item in initial_items if item["rule_id"] == rule_id],
                }
                for rule_id in _RERUN_RULE_IDS
            ],
        },
        items=initial_items,
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True

    source_id = "rerun-job"
    original = _load_job(engine, jobs, job_id=source_id)
    for interruption in range(2):
        retried = service.retry_batch_job(job_id=source_id, created_by="tester")
        assert retried is not None and retried["status"] == "queued"
        source_id = retried["id"]
        retry_claim = service.mark_batch_job_running(job_id=source_id)
        assert isinstance(retry_claim, str)
        service.update_batch_job_progress(
            job_id=source_id, attempt_filters_json=retry_claim, step_key="run",
            rule_index=0, rule_count=1, processed_records=0, total_records=1,
            summary_patch={"rule_results": []},
        )
        service.fail_batch_job(job_id=source_id, attempt_filters_json=retry_claim,
                               error_message=f"synthetic retry interruption {interruption + 1}")
        # 原任务仍提供其真实部分交付；新中断任务不携带旧成功项。
        assert _load_job(engine, jobs, job_id="rerun-job") == original
        persisted = _load_job(engine, jobs, job_id=source_id)
        assert persisted["items"] == []
        assert persisted["summary"]["rule_results"] == []
        latest = service.build_latest_single_record_result_dto(
            institute_id=_RERUN_RECORD_B["institute_id"], patient_id=_RERUN_RECORD_B["patient_id"],
            visit_id=_RERUN_RECORD_B["visit_id"], rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
        )
        assert latest["job_id"] == "rerun-job"
        assert [item["rule_id"] for item in latest["items"]] == [_RERUN_RULE_IDS[0]]
        assert latest["state"] == "ready"
        assert latest["is_complete"] is False
        bulk = service.build_latest_luxian_0609_record_result_dtos(
            record_refs=[_RERUN_RECORD_B], rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
        )[tuple(CaseRef.from_mapping(_RERUN_RECORD_B))]
        assert bulk["job_id"] == "rerun-job"
        assert [item["rule_id"] for item in bulk["items"]] == [_RERUN_RULE_IDS[0]]
        assert bulk["state"] == "ready"


@pytest.mark.parametrize(
    "corruption",
    ["duplicate", "success_failure_overlap", "wrong_coordinate", "out_of_scope", "bad_status"],
)
def test_saved_partial_reader_rejects_corrupt_authoritative_success_set(
    canonical_storage,
    corruption,
):
    service, engine, jobs, _ = canonical_storage
    claim = service.mark_batch_job_running(job_id="rerun-job")
    initial_items = [
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
    ]
    failures = [_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])]
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=claim,
        summary={
            **_partial_summary(total_records=2, delivered=3, failed_rules=[_RERUN_RULE_IDS[1]]),
            "rule_results": [],
        },
        items=initial_items,
        failed_records=failures,
    ) is True

    corrupted_items = [dict(item) for item in initial_items]
    corrupted_failures = [dict(item) for item in failures]
    if corruption == "duplicate":
        corrupted_items.append(dict(corrupted_items[-1]))
    elif corruption == "success_failure_overlap":
        corrupted_failures.append(_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]))
    elif corruption == "wrong_coordinate":
        corrupted_items = corrupted_items[:-1]
    elif corruption == "out_of_scope":
        corrupted_items[-1]["rule_id"] = "LX0609-06-01-06"
    else:
        corrupted_items[-1].update(
            status="technical_error",
            result_status="technical_error",
            display_status="technical_error",
            is_compliant=None,
        )
    with engine.begin() as connection:
        connection.execute(
            jobs.update().where(jobs.c.id == "rerun-job").values(
                items_json=json.dumps(corrupted_items),
                failed_records_json=json.dumps(corrupted_failures),
            )
        )

    latest = service.build_latest_single_record_result_dto(
        institute_id=_RERUN_RECORD_B["institute_id"],
        patient_id=_RERUN_RECORD_B["patient_id"],
        visit_id=_RERUN_RECORD_B["visit_id"],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )
    assert latest["state"] == "technical_error"
    assert latest["reason_code"] == "saved_partial_result_invalid"
    assert latest["items"] == []


def test_canceled_precise_retry_rejects_late_failure_and_completion_callbacks(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    claim = service.mark_batch_job_running(job_id="rerun-job")
    baseline_items = [
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
        _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
    ]
    baseline_failure = _rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=claim,
        summary={
            **_partial_summary(total_records=2, delivered=3, failed_rules=[_RERUN_RULE_IDS[1]]),
            "rule_results": [],
        },
        items=baseline_items,
        failed_records=[baseline_failure],
    ) is True
    retry_baseline = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert retry_baseline["status"] == "queued"
    retry_claim = service.mark_batch_job_running(job_id=retry_baseline["id"])
    canceled = service.cancel_batch_job(job_id=retry_baseline["id"], created_by="tester")
    assert canceled["status"] == "canceled"

    service.fail_batch_job(
        job_id=retry_baseline["id"],
        attempt_filters_json=retry_claim,
        error_message="late failure",
    )
    assert service.complete_batch_job(
        job_id=retry_baseline["id"],
        attempt_filters_json=retry_claim,
        summary=_completed_summary(total_records=2, delivered=4),
        items=[
            *baseline_items,
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[],
    ) is False

    persisted = _load_job(engine, jobs, job_id=retry_baseline["id"])
    assert persisted["status"] == "canceled"
    assert persisted["items"] == retry_baseline["items"]
    assert persisted["failed_records"] == retry_baseline["failed_records"]



def test_bulk_latest_uses_same_full_partial_generation_as_single_record(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    full_filters = {
        "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": workspace.RULE_SET_VERSION,
        "rule_ids": list(_RERUN_RULE_IDS),
        "selected_rule_ids": [],
        "scoped_customer_rule_ids": list(_RERUN_RULE_IDS),
        "record_refs": [_RERUN_RECORD_B],
    }
    with engine.begin() as connection:
        connection.execute(jobs.insert().values(
            id="new-partial-job",
            draft_id="sichuan-rule-library",
            created_by="tester",
            status="queued",
            rule_code="LX0609",
            rule_name="新一轮全量失败任务",
            scope="final",
            created_at=datetime(2026, 9, 21, 10, 0),
            updated_at=datetime(2026, 9, 21, 10, 0),
            total_records=1,
            record_ids_json=json.dumps([_RERUN_RECORD_B["visit_id"]]),
            filters_json=json.dumps(full_filters),
        ))
    partial_claim = service.mark_batch_job_running(job_id="new-partial-job")
    partial_item = _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0])
    assert service.complete_batch_job(
        job_id="new-partial-job",
        attempt_filters_json=partial_claim,
        summary={
            **_partial_summary(total_records=1, delivered=1, failed_rules=[_RERUN_RULE_IDS[1]]),
            "rule_results": [
                {"rule_code": _RERUN_RULE_IDS[0], "items": [partial_item]},
                {"rule_code": _RERUN_RULE_IDS[1], "items": []},
            ],
        },
        items=[partial_item],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True

    # 更晚的局部成功任务不能覆盖已有全量冻结范围。
    targeted_filters = {
        **full_filters,
        "rule_ids": [_RERUN_RULE_IDS[0]],
        "selected_rule_ids": [_RERUN_RULE_IDS[0]],
        "scoped_customer_rule_ids": [_RERUN_RULE_IDS[0]],
        "record_rule_map": {
            CaseRef.from_mapping(_RERUN_RECORD_B).as_key(): [_RERUN_RULE_IDS[0]],
        },
    }
    with engine.begin() as connection:
        connection.execute(jobs.insert().values(
            id="newer-targeted-job",
            draft_id="sichuan-rule-library",
            created_by="tester",
            status="queued",
            rule_code="LX0609",
            rule_name="更晚局部任务",
            scope="final",
            created_at=datetime(2026, 9, 21, 11, 0),
            updated_at=datetime(2026, 9, 21, 11, 0),
            total_records=1,
            record_ids_json=json.dumps([_RERUN_RECORD_B["visit_id"]]),
            filters_json=json.dumps(targeted_filters),
        ))
    targeted_claim = service.mark_batch_job_running(job_id="newer-targeted-job")
    assert service.complete_batch_job(
        job_id="newer-targeted-job",
        attempt_filters_json=targeted_claim,
        summary=_completed_summary(total_records=1, delivered=1),
        items=[partial_item],
        failed_records=[],
    ) is True

    single = service.build_latest_single_record_result_dto(
        institute_id=_RERUN_RECORD_B["institute_id"],
        patient_id=_RERUN_RECORD_B["patient_id"],
        visit_id=_RERUN_RECORD_B["visit_id"],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )
    bulk = service.build_latest_luxian_0609_record_result_dtos(
        record_refs=[_RERUN_RECORD_B],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )[tuple(CaseRef.from_mapping(_RERUN_RECORD_B))]

    assert single["job_id"] == bulk["job_id"] == "new-partial-job"
    assert single["data_origin"] == bulk["data_origin"] == "saved_partial_task"
    assert single["expected_rule_count"] == bulk["expected_rule_count"] == 2
    assert bulk["is_complete"] is False
    assert bulk["failed_rule_ids"] == [_RERUN_RULE_IDS[1]]
    assert [item["rule_id"] for item in bulk["items"]] == [_RERUN_RULE_IDS[0]]

    # 更新的同 visit 完成任务若缺少三坐标 Envelope，partial 候选也不能绕过歧义护栏。
    with engine.begin() as connection:
        connection.execute(jobs.insert().values(
            id="ambiguous-completed-job",
            draft_id="sichuan-rule-library",
            created_by="tester",
            status="completed",
            rule_code="LX0609",
            rule_name="缺少Envelope的更新任务",
            scope="final",
            created_at=datetime(2027, 1, 22, 10, 0),
            finished_at=datetime(2027, 1, 22, 10, 5),
            updated_at=datetime(2027, 1, 22, 10, 5),
            total_records=1,
            record_ids_json=json.dumps([_RERUN_RECORD_B["visit_id"]]),
            filters_json=json.dumps(full_filters),
        ))
    blocked = service.build_latest_luxian_0609_record_result_dtos(
        record_refs=[_RERUN_RECORD_B],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )[tuple(CaseRef.from_mapping(_RERUN_RECORD_B))]
    assert blocked["state"] == "technical_error"
    assert blocked["reason_code"] == "canonical_envelope_missing"
    assert blocked["expected_rule_count"] == 2


@pytest.mark.parametrize("complete_summary", [False, True])
def test_new_failed_task_does_not_present_or_remove_previous_results(canonical_storage, complete_summary):
    service, engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)

    previous_job = _load_job(engine, jobs, job_id="rerun-job")
    _insert_independent_full_task(engine, jobs)
    rerun_claim = service.mark_batch_job_running(job_id="new-full-job")
    assert service.complete_batch_job(
        job_id="new-full-job",
        attempt_filters_json=rerun_claim,
        summary={
            "total_records": 2,
            "success_count": 0,
            "failed_count": 2,
            "execution_status": "failed",
            "completed_rule_count": 0,
            "failed_rule_count": 4,
            "failed_rule_ids": list(_RERUN_RULE_IDS),
            **({"rule_results": []} if complete_summary else {}),
        },
        items=[],
        failed_records=[
            _rule_failure(record, rule_id)
            for record in (_RERUN_RECORD_A, _RERUN_RECORD_B)
            for rule_id in _RERUN_RULE_IDS
        ],
    ) is True

    assert _root_envelope_refs(engine, envelopes, root_job_id="new-full-job") == []
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [("test-va", 2), ("test-vb", 2)]
    assert _load_job(engine, jobs, job_id="rerun-job") == previous_job
    for record in (_RERUN_RECORD_A, _RERUN_RECORD_B):
        latest = service.build_latest_single_record_result_dto(
            institute_id=record["institute_id"],
            patient_id=record["patient_id"],
            visit_id=record["visit_id"],
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
        )
        assert latest["job_id"] == "new-full-job"
        assert latest["data_origin"] == "saved_partial_task"
        assert latest["items"] == []
        assert latest["is_complete"] is False
        if complete_summary:
            assert latest["state"] == "ready"
            assert latest["execution_status"] == "failed"
            assert latest["completed_rule_count"] == 0
            assert latest["failed_rule_count"] == 2
            assert latest["failed_rule_ids"] == list(_RERUN_RULE_IDS)
        else:
            # 损坏/不完整的历史摘要仍按读取合同失败关闭，不能伪装为没有质控。
            assert latest["state"] == "technical_error"
            assert latest["reason_code"] == "saved_partial_result_invalid"
        bulk = service.build_latest_luxian_0609_record_result_dtos(
            record_refs=[record],
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
        )[tuple(CaseRef.from_mapping(record))]
        if complete_summary:
            assert bulk["state"] == "ready"
            assert bulk["execution_status"] == "failed"
            assert bulk["items"] == []
            assert bulk["failed_rule_ids"] == list(_RERUN_RULE_IDS)
        else:
            assert bulk["state"] == "technical_error"
            assert bulk["reason_code"] == "saved_partial_result_invalid"
    job = _load_job(engine, jobs, job_id="new-full-job")
    with pytest.raises(ValueError, match="尚未形成可导出"):
        service._load_batch_job_export_items(job=job)


def test_late_root_leaf_attempt_failure_does_not_delete_published_canonical(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    first_claim = _complete_full_run(service)

    previous_job = _load_job(engine, jobs, job_id="rerun-job")
    _insert_independent_full_task(engine, jobs)
    assert isinstance(service.mark_batch_job_running(job_id="new-full-job"), str)
    # 旧代次迟到完成：CAS 未命中，不能套用旧 claim 覆盖新任务或删除历史 root 结果。
    assert service.complete_batch_job(
        job_id="new-full-job",
        attempt_filters_json=first_claim,
        summary=_completed_summary(total_records=2, delivered=4),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[],
    ) is False

    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [
        ("test-va", 2),
        ("test-vb", 2),
    ]
    assert _load_job(engine, jobs, job_id="rerun-job") == previous_job
    assert _load_job(engine, jobs, job_id="new-full-job")["status"] == "running"


def test_precise_failed_rule_retry_keeps_other_records_in_canonical(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    first_claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=first_claim,
        summary=_partial_summary(total_records=2, delivered=2, failed_rules=[_RERUN_RULE_IDS[1]]),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [("test-va", 2)]

    retried = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert retried["status"] == "queued"
    retry_scope = retried["filters"]["failed_rule_retry"]
    assert retry_scope["rule_ids"] == [_RERUN_RULE_IDS[1]]
    assert retry_scope["record_refs"] == [_RERUN_RECORD_B]
    assert retried["items"] == []
    new_id = retried["id"]
    original = _load_job(engine, jobs, job_id="rerun-job")
    rerun_claim = service.mark_batch_job_running(job_id=new_id)
    assert service.complete_batch_job(
        job_id=new_id, attempt_filters_json=rerun_claim,
        summary=_completed_summary(total_records=1, delivered=1),
        items=[_canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])], failed_records=[],
    ) is True
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [("test-va", 2)]
    assert _root_envelope_refs(engine, envelopes, root_job_id=new_id) == [("test-vb", 1)]
    assert _load_job(engine, jobs, job_id="rerun-job") == original
    job = _load_job(engine, jobs, job_id=new_id)
    assert job["success_count"] == 1
    assert len(service._load_batch_job_export_items(job=job)) == 1


def test_child_leaf_completion_does_not_delete_root_published_canonical(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    # 只声明子任务归属，不建父任务行：隔离子任务自身的 Envelope 写入语义，
    # 父任务 root 的整体替换由 refresh_parent_batch_job 负责。
    with engine.begin() as connection:
        connection.execute(
            jobs.update().where(jobs.c.id == "rerun-job").values(parent_job_id="parent-job")
        )
        # 同一 root 下已由其它子任务交付的第三份病历。
        connection.execute(envelopes.insert().values(
            id="existing-envelope",
            job_id="other-child-job",
            root_job_id="parent-job",
            created_by="tester",
            record_id="test-vc",
            institute_id="test-i",
            patient_id="test-pc",
            visit_id="test-vc",
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
            envelope_json=json.dumps({"items": []}),
            result_count=0,
            created_at=datetime(2026, 9, 20),
            updated_at=datetime(2026, 9, 20),
        ))

    claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=claim,
        summary=_partial_summary(total_records=2, delivered=2, failed_rules=[_RERUN_RULE_IDS[1]]),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True

    assert _root_envelope_refs(engine, envelopes, root_job_id="parent-job") == [
        ("test-va", 2),
        ("test-vc", 0),
    ]
