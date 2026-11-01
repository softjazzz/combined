from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.services import custom_qc_workspace_service as workspace
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
from tests.unit.test_luxian_0609_canonical_result_delivery import _published_pilot_item_for_read_boundary


RULES = ["LX0609-01-01-01", "LX0609-09-01-01"]
REF = {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}


@pytest.fixture
def saved_jobs(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata = MetaData()
    jobs = workspace._batch_jobs_table(readonly=True).to_metadata(metadata, schema=None)
    envelopes = workspace._record_result_envelopes_table().to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    service = object.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table = jobs
    service._record_result_envelope_table = envelopes
    monkeypatch.setattr(workspace, "_session", lambda: Session(engine))
    monkeypatch.setattr(workspace, "customer_safe_projection_key", lambda: "test-latest-full-result")

    def add(job_id, hour, rules, *, failed=False, identity=None, bad_items=False, record_rule_map=None):
        identity = identity or REF
        filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                   "scoped_customer_rule_ids": rules, "rule_ids": rules,
                   "record_refs": [identity], "selected_rule_ids": [] if rules == RULES else rules}
        if record_rule_map is not None:
            filters["record_rule_map"] = record_rule_map
        raw_items = [_published_pilot_item_for_read_boundary(rule) for rule in rules[:1] if failed] if failed else [
            _published_pilot_item_for_read_boundary(rule) for rule in rules
        ]
        for item in raw_items:
            item.update(identity, record_id=identity["visit_id"])
        failures = [{**identity, "rule_id": rules[-1], "reason_code": "model_invalid_output",
                     "failure_status": "technical_error"}] if failed else []
        if bad_items:
            raw_items = raw_items * 2
        summary = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                   "execution_status": "partial_failed" if failed else "completed",
                   "rule_results": [{"rule_code": item["rule_id"], "items": [item]} for item in raw_items]}
        now = datetime(2026, 10, 25, hour)
        row = {"id": job_id, "draft_id": "draft", "rule_code": "LX0609",
               "rule_name": "合成任务", "status": "failed" if failed else "completed",
               "filters_json": json.dumps(filters, ensure_ascii=False),
               "record_ids_json": json.dumps([identity["visit_id"]]),
               "summary_json": json.dumps(summary, ensure_ascii=False),
               "items_json": json.dumps(raw_items, ensure_ascii=False),
               "failed_records_json": json.dumps(failures, ensure_ascii=False),
               "created_by": "tester", "created_at": now, "updated_at": now, "finished_at": now}
        with Session(engine) as session:
            session.execute(jobs.insert().values(**row))
            if not failed:
                CanonicalResultStore(envelopes).replace_for_job(
                    session, job_row=row, items=raw_items, now=now,
                    projector=lambda item: envelope_item_from_rule_result(item, hmac_key="test-latest-full-result"),
                    projection_key="test-latest-full-result",
                )
            session.commit()
        return row

    yield service, add, engine, jobs
    engine.dispose()


def read(service):
    return service.build_latest_single_record_result_dto(**REF)


def test_newer_targeted_run_does_not_replace_full_results(saved_jobs):
    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("targeted", 12, RULES[:1])
    result = read(service)
    assert result["job_id"] == "full"
    assert result["expected_rule_count"] == 2
    assert result["result_rule_count"] == 2


def test_latest_failed_full_run_exposes_saved_items_and_failure_without_old_merge(saved_jobs):
    service, add, engine, jobs = saved_jobs
    add("old-full", 10, RULES)
    add("new-targeted", 12, RULES[:1])
    before = add("latest-failed-full", 13, RULES, failed=True)
    result = read(service)
    assert result["state"] == "ready"
    assert result["job_id"] == "latest-failed-full"
    assert result["execution_status"] == "partial_failed"
    assert result["expected_rule_count"] == 2
    assert result["result_rule_count"] == 1
    assert result["failed_rule_ids"] == RULES[1:]
    assert result["is_complete"] is False
    assert [item["rule_id"] for item in result["items"]] == RULES[:1]
    with Session(engine) as session:
        stored = session.execute(jobs.select().where(jobs.c.id == before["id"])).mappings().one()
        assert stored["summary_json"] == before["summary_json"]


@pytest.mark.parametrize("identity", [
    {**REF, "institute_id": "other-hospital"}, {**REF, "patient_id": "other-patient"},
])
def test_failed_same_visit_other_identity_does_not_replace_results(saved_jobs, identity):
    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("wrong-identity", 13, RULES, failed=True, identity=identity)
    assert read(service)["job_id"] == "full"


def test_corrupt_partial_results_fail_closed_without_returning_older_results(saved_jobs):
    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("failed-bad", 13, RULES, failed=True, bad_items=True)
    result = read(service)
    assert result["state"] == "technical_error"
    assert result["job_id"] == "failed-bad"
    assert result["items"] == []


def test_partial_summary_without_authoritative_items_does_not_restore_old_results(saved_jobs):
    service, add, engine, jobs = saved_jobs
    add("full", 10, RULES)
    add("failed-summary-only", 13, RULES, failed=True)
    with Session(engine) as session:
        session.execute(
            jobs.update().where(jobs.c.id == "failed-summary-only").values(items_json=None)
        )
        session.commit()
    result = read(service)
    assert result["state"] == "technical_error"
    assert result["reason_code"] == "saved_partial_result_invalid"
    assert result["job_id"] == "failed-summary-only"
    assert result["items"] == []


def test_completed_record_summary_also_ignores_newer_targeted_subset(saved_jobs):
    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("targeted", 12, RULES[:1])
    projections = service.build_luxian_0609_completed_record_result_summaries(record_refs=[REF])
    assert projections[tuple(REF.values())]["status"] == "ready"
    assert projections[tuple(REF.values())]["total_rule_count"] == 2


def test_targeted_only_task_is_labeled_with_its_frozen_scope(saved_jobs):
    service, add, *_ = saved_jobs
    add("targeted-only", 12, RULES[:1])
    result = read(service)
    assert result["result_scope"] == "targeted"
    assert result["expected_rule_count"] == 1


def test_newer_failed_targeted_task_also_does_not_replace_full_results(saved_jobs):
    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("failed-targeted", 13, RULES[:1], failed=True)
    assert read(service)["job_id"] == "full"


def test_record_rule_map_cannot_inflate_one_cases_targeted_scope(saved_jobs):
    from app.services.case_identity import CaseRef

    service, add, *_ = saved_jobs
    add("full", 10, RULES)
    add("mapped-target", 12, RULES, record_rule_map={CaseRef.from_mapping(REF).as_key(): RULES[:1]})
    assert read(service)["job_id"] == "full"
