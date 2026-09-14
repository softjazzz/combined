"""执行失败与临床结果分离：真实 SQLite 事务及客户 DTO。"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace
from app.routers import qc_sichuan


@pytest.fixture
def storage(monkeypatch):
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
        "model_execution_stats": {
            "scope": "exam_lab", "requested_rule_count": 2, "first_success_rule_count": 1,
            "retried_rule_count": 1, "recovered_rule_count": 0, "failed_rule_count": 1,
            "first_answer_success_rate": 0.5, "recovery_success_rate": 0.0, "model_failure_rate": 0.5,
        },
    }
    return summary, [item], [failure]


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

    retried = service.retry_batch_job(job_id="partial-job", created_by="tester")

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

    response = await qc_sichuan.retry_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        job_id="partial-job",
        current_user={"id": "tester"},
    )

    payload = response["data"]
    assert payload["summary"]["execution_status"] == "partial_failed"
    assert payload["items"][0]["rule_id"] == "LX0609-011"
    assert payload["failed_records"][0]["rule_id"] == "LX0609-012"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "test-p" not in serialized
    assert "test-v" not in serialized
