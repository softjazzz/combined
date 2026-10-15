"""执行失败与临床结果分离：真实 SQLite 事务及客户 DTO。"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace
from app.routers import qc_sichuan
from app.services.case_identity import CaseRef
from app.services.qc_workspace.partial_record_delivery import select_complete_record_items

pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


@pytest.fixture
def storage(monkeypatch):
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
        "status": "queued",
        "max_attempts": 3,
        "completed_attempts": 0,
        "remaining_failure_count": 1,
        "should_retry": True,
        "next_attempt": 1,
        "delay_seconds": 0.0,
    }
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
    assert len(retried["items"]) == 1
    assert retried["items"][0]["rule_id"] == "LX0609-06-01-04"
    assert retried["items"][0]["status"] == "compliant"
    assert retried["failed_records"][0]["rule_id"] == "LX0609-06-01-05"
    retry_scope = retried["filters"]["failed_rule_retry"]
    assert retry_scope["rule_ids"] == ["LX0609-06-01-05"]
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
    assert safe["items"][0]["rule_id"] == "LX0609-06-01-04"
    assert safe["failed_records"][0]["rule_id"] == "LX0609-06-01-05"
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
    assert payload["items"][0]["rule_id"] == "LX0609-06-01-04"
    assert payload["failed_records"][0]["rule_id"] == "LX0609-06-01-05"
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


def test_root_leaf_rerun_replaces_published_canonical_envelopes(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    first_claim = _complete_full_run(service)
    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [
        ("test-va", 2),
        ("test-vb", 2),
    ]

    # 任务列表对 completed 的 0609 任务提供“重试”。
    assert service.retry_batch_job(job_id="rerun-job", created_by="tester")["status"] == "queued"
    rerun_claim = service.mark_batch_job_running(job_id="rerun-job")
    assert isinstance(rerun_claim, str) and rerun_claim != first_claim
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=rerun_claim,
        summary=_partial_summary(total_records=2, delivered=2, failed_rules=[_RERUN_RULE_IDS[1]]),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    ) is True

    job = _load_job(engine, jobs, job_id="rerun-job")
    root_refs = _root_envelope_refs(engine, envelopes, root_job_id="rerun-job")
    assert root_refs == [("test-va", 2)]
    assert len(root_refs) == job["success_count"] == 1

    stale = service.build_latest_single_record_result_dto(
        institute_id=_RERUN_RECORD_B["institute_id"],
        patient_id=_RERUN_RECORD_B["patient_id"],
        visit_id=_RERUN_RECORD_B["visit_id"],
        rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
        rule_set_version=workspace.RULE_SET_VERSION,
    )
    assert stale["state"] == "not_found"
    assert stale["items"] == []

    export_items = service._load_batch_job_export_items(job=job)
    # 导出只包含本次实际交付的病历结果（客户投影不保留原三坐标字段）。
    assert len(export_items) == 2
    assert {item["display_status"] for item in export_items} == {"compliant"}


def test_root_leaf_failed_attempt_without_delivery_removes_previous_results(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)

    assert service.retry_batch_job(job_id="rerun-job", created_by="tester")["status"] == "queued"
    rerun_claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=rerun_claim,
        summary={
            "total_records": 2,
            "success_count": 0,
            "failed_count": 2,
            "execution_status": "failed",
            "completed_rule_count": 0,
            "failed_rule_count": 4,
            "failed_rule_ids": list(_RERUN_RULE_IDS),
        },
        items=[],
        failed_records=[
            _rule_failure(record, rule_id)
            for record in (_RERUN_RECORD_A, _RERUN_RECORD_B)
            for rule_id in _RERUN_RULE_IDS
        ],
    ) is True

    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == []
    for record in (_RERUN_RECORD_A, _RERUN_RECORD_B):
        latest = service.build_latest_single_record_result_dto(
            institute_id=record["institute_id"],
            patient_id=record["patient_id"],
            visit_id=record["visit_id"],
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
        )
        assert latest["state"] == "not_found"
    job = _load_job(engine, jobs, job_id="rerun-job")
    with pytest.raises(ValueError, match="尚未形成可导出"):
        service._load_batch_job_export_items(job=job)


def test_late_root_leaf_attempt_failure_does_not_delete_published_canonical(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    first_claim = _complete_full_run(service)

    assert service.retry_batch_job(job_id="rerun-job", created_by="tester")["status"] == "queued"
    assert isinstance(service.mark_batch_job_running(job_id="rerun-job"), str)
    # 旧代次迟到完成：CAS 未命中，既不能覆盖任务也不能删除当前 root 结果。
    assert service.complete_batch_job(
        job_id="rerun-job",
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
    assert _load_job(engine, jobs, job_id="rerun-job")["status"] == "running"


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
    assert [item["visit_id"] for item in retried["items"]] == ["test-va", "test-va"]

    rerun_claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job",
        attempt_filters_json=rerun_claim,
        summary=_completed_summary(total_records=2, delivered=4),
        items=[
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_A, _RERUN_RULE_IDS[1]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[0]),
            _canonical_item(_RERUN_RECORD_B, _RERUN_RULE_IDS[1]),
        ],
        failed_records=[],
    ) is True

    assert _root_envelope_refs(engine, envelopes, root_job_id="rerun-job") == [
        ("test-va", 2),
        ("test-vb", 2),
    ]
    job = _load_job(engine, jobs, job_id="rerun-job")
    assert job["success_count"] == 2
    assert len(service._load_batch_job_export_items(job=job)) == 4


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
