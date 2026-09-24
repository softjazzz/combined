"""执行失败与临床结果分离：真实 SQLite 事务及客户 DTO。"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace
from app.routers import qc_sichuan
from app.services.case_identity import CaseRef
from app.services.qc_workspace.partial_record_delivery import select_complete_record_items


@pytest.fixture
def storage(monkeypatch):
    service_engine = sa.create_engine("sqlite://")

    @sa.event.listens_for(service_engine, "connect")
    def _attach_qc_schema(dbapi_connection, _connection_record):
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS qc")

    monkeypatch.setattr(workspace, "engine", service_engine)
    monkeypatch.setattr(workspace, "_sync_batch_job_parent_columns", lambda **_: None)
    service = workspace.CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
    monkeypatch.setattr(workspace, "_session", factory)
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="partial-job", draft_id="sichuan-rule-library", created_by="tester", status="running", rule_code="LX0609",
            created_at=datetime(2026, 9, 14), updated_at=datetime(2026, 9, 14),
            rule_name="测试", scope="final", total_records=1,
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-011", "LX0609-012"],
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
    service_engine.dispose()


def _payload():
    identity = {"institute_id": "test-i", "patient_id": "test-p", "visit_id": "test-v"}
    item = {
        **identity, "rule_id": "LX0609-011", "rule_version": "2026-06-09",
        "schema_version": "lx0609-customer-result-v2",
        "status": "compliant", "result_status": "compliant", "display_status": "compliant",
        "is_compliant": True, "reason_code": "exam_result_recorded", "findings": "已记录检查结果。",
    }
    failure = {**identity, "rule_id": "LX0609-012", "reason_code": "model_invalid_output", "error_phase": "result_status"}
    summary = {
        "total_records": 1, "success_count": 0, "failed_count": 1, "compliant_records": 0,
        "execution_status": "partial_failed", "completed_rule_count": 1, "failed_rule_count": 1,
        "failed_rule_ids": ["LX0609-012"],
        "automatic_failed_rule_retry": {
            "max_attempts": 3,
            "completed_attempts": 0,
            "remaining_failure_count": 1,
            "status": "queued",
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
        {**record_a, "rule_id": "LX0609-011"},
        {**record_b, "rule_id": "LX0609-011"},
        {**record_b, "rule_id": "LX0609-012"},
    ]
    failures = [{**record_a, "rule_id": "LX0609-012"}]

    selected_items, selected_refs = select_complete_record_items(
        items=items,
        failures=failures,
        expected_rule_ids=["LX0609-011", "LX0609-012"],
    )

    assert [item["visit_id"] for item in selected_items] == ["test-vb", "test-vb"]
    assert [record_ref.as_dict() for record_ref in selected_refs] == [record_b]


def test_partial_delivery_fails_closed_when_failure_identity_is_incomplete():
    selected_items, selected_refs = select_complete_record_items(
        items=[{
            "institute_id": "test-i",
            "patient_id": "test-p",
            "visit_id": "test-v",
            "rule_id": "LX0609-011",
        }],
        failures=[{"visit_id": "test-v", "rule_id": "LX0609-012"}],
        expected_rule_ids=["LX0609-011"],
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
        failures.append({**failures[0], "rule_id": "LX0609-011"})
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
        "status": "queued",
        "max_attempts": 3,
        "completed_attempts": 0,
        "remaining_failure_count": 1,
        "should_retry": True,
        "next_attempt": 1,
        "delay_seconds": 0.0,
    }
    assert len(safe["items"]) == len(items)
    assert safe["failed_records"][0]["rule_id"] == "LX0609-012"


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
                    "rule_ids": ["LX0609-011", "LX0609-012"],
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
        item(record_a, "LX0609-011"),
        item(record_b, "LX0609-011"),
        item(record_b, "LX0609-012"),
    ]
    failures = [{
        **record_a,
        "rule_id": "LX0609-012",
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
        "failed_rule_ids": ["LX0609-012"],
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


@pytest.mark.parametrize(
    ("items", "failures", "execution_status", "expected_status"),
    [
        ([{"rule_id": "SC-001", "status": "non_compliant", "is_compliant": False}], [], "completed", "completed"),
        ([{"rule_id": "SC-001", "status": "non_compliant", "is_compliant": False}],
         [{"rule_id": "SC-001", "error_phase": "evaluate_document", "visit_id": "test-v"}],
         "partial_failed", "failed"),
        ([], [{"rule_id": "SC-001", "error_phase": "rule_lookup"}], "failed", "failed"),
    ],
    ids=["nonempty-success", "partial-failure", "global-rule-lookup-failure"],
)
def test_sc_job_persists_raw_results_without_canonical(
    storage, items, failures, execution_status, expected_status,
):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "partial-job").values(
                filters_json=json.dumps({"rule_set_key": "sc_content_v1", "rule_ids": ["SC-001"]})
            )
        )

    service.complete_batch_job(
        job_id="partial-job",
        summary={
            "total_records": 1,
            "success_count": 0 if failures else 1,
            "failed_count": len(failures),
            "execution_status": execution_status,
            "completed_rule_count": len(items),
            "failed_rule_count": len(failures),
        },
        items=items,
        failed_records=failures,
    )

    with engine.connect() as connection:
        row = connection.execute(
            sa.select(table.c.status, table.c.items_json, table.c.failed_records_json, table.c.summary_json)
        ).one()
    assert row.status == expected_status
    assert json.loads(row.items_json) == items
    assert json.loads(row.failed_records_json) == failures
    assert json.loads(row.summary_json)["execution_status"] == execution_status


@pytest.mark.parametrize("rule_set_key", ["custom_rule_set", "", "sc_content_unknown_v1"])
def test_custom_job_keeps_existing_canonical_write_path(storage, monkeypatch, rule_set_key):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "partial-job").values(
                filters_json=json.dumps({"rule_set_key": rule_set_key})
            )
        )
    captured = []
    monkeypatch.setattr(
        service, "_write_record_result_envelopes",
        lambda *_args, **kwargs: captured.append(kwargs) or (),
    )

    service.complete_batch_job(
        job_id="partial-job",
        summary={"total_records": 1, "success_count": 1},
        items=[{"rule_id": "CUSTOM-001", "status": "non_compliant"}],
        failed_records=[],
    )

    assert len(captured) == 1
    assert captured[0]["items"][0]["rule_id"] == "CUSTOM-001"


@pytest.mark.parametrize("rule_set_key", ["custom_rule_set", "", "sc_content_unknown_v1"])
def test_custom_job_keeps_existing_failed_item_validation(storage, rule_set_key):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "partial-job").values(
                filters_json=json.dumps({"rule_set_key": rule_set_key})
            )
        )

    with pytest.raises(ValueError, match="病例身份"):
        service.complete_batch_job(
            job_id="partial-job",
            summary={
                "total_records": 1,
                "execution_status": "partial_failed",
                "completed_rule_count": 1,
                "failed_rule_count": 1,
            },
            items=[{"rule_id": "CUSTOM-001", "status": "non_compliant"}],
            failed_records=[{"rule_id": "CUSTOM-002", "error_phase": "rule_lookup"}],
        )


def test_partial_envelope_writer_narrows_record_contract_without_mutating_job(monkeypatch):
    service = object.__new__(workspace.CustomQCWorkspaceService)
    service._record_result_envelope_table = object()
    record_a = {"institute_id": "test-i", "patient_id": "test-pa", "visit_id": "test-va"}
    record_b = {"institute_id": "test-i", "patient_id": "test-pb", "visit_id": "test-vb"}
    job_row = {
        "id": "partial-job",
        "filters_json": json.dumps({
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_ids": ["LX0609-011"],
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
        items=[{**record_b, "rule_id": "LX0609-011"}],
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
    summary["rule_count"] = 2
    service.complete_batch_job(
        job_id="partial-job",
        summary=summary,
        items=items,
        failed_records=failures,
    )

    retried = service.retry_batch_job(
        job_id="partial-job",
        created_by="tester",
        automatic=True,
    )

    assert retried is not None
    assert retried["status"] == "queued"
    assert len(retried["items"]) == 1
    assert retried["items"][0]["rule_id"] == "LX0609-011"
    assert retried["items"][0]["status"] == "compliant"
    assert retried["failed_records"][0]["rule_id"] == "LX0609-012"
    retry_scope = retried["filters"]["failed_rule_retry"]
    assert retry_scope["rule_ids"] == ["LX0609-012"]
    assert retry_scope["record_refs"] == [
        {"institute_id": "test-i", "patient_id": "test-p", "visit_id": "test-v"}
    ]
    assert retry_scope["pending_count"] == 1
    assert retried["summary"]["execution_status"] == "partial_failed"
    assert retried["summary"]["retry_status"] == "queued"
    assert retried["summary"]["retry_trigger"] == "automatic"
    safe = workspace.project_customer_safe_batch_job(
        retried,
        hmac_key="synthetic-test-key",
    )
    assert len(safe["items"]) == 1
    assert safe["items"][0]["rule_id"] == "LX0609-011"
    assert safe["failed_records"][0]["rule_id"] == "LX0609-012"
    with engine.connect() as connection:
        row = dict(connection.execute(sa.select(table)).mappings().one())
    assert json.loads(row["items_json"]) == items
    assert json.loads(row["failed_records_json"])[0]["record_key"] == '["test-i","test-p","test-v"]'


@pytest.mark.asyncio
async def test_retry_route_rejects_unverified_final_without_requeue(storage, monkeypatch):
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

    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.retry_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),
            job_id="partial-job",
            current_user={"id": "tester"},
        )

    assert exc.value.status_code == 422
    assert "final_archive_unverified" in exc.value.detail
    assert service.get_batch_job(job_id="partial-job", created_by="tester")["status"] == "failed"
