"""失败项恢复的范围、原成功结果和离线应答保护。"""

from copy import deepcopy
import json

import pytest

from app.services.qc_workspace.offline_failure_recovery import (
    ReadonlyRetryWorkspace, replay_response, validate_recovery_merge,
)


def item(rule="LX0609-07-01-02", visit="synthetic-target", status="non_compliant"):
    return {"institute_id": "synthetic-hospital", "patient_id": "synthetic-patient", "visit_id": visit, "rule_id": rule, "status": status}


def baseline():
    return {"status": "failed", "parent_job_id": None,
            "items_json": json.dumps([item("LX0609-07-04-01", status="compliant")]),
            "failed_records_json": json.dumps([item()])}


def test_only_appends_original_failed_pair_and_preserves_success():
    before = baseline()
    success = json.loads(before["items_json"])
    assert validate_recovery_merge(before, items=success + [item()], failures=[]) == {("synthetic-hospital", "synthetic-patient", "synthetic-target")}
    assert success == json.loads(before["items_json"])


def test_successful_result_must_not_be_changed():
    before = baseline()
    altered = json.loads(before["items_json"])
    altered[0]["status"] = "non_compliant"
    with pytest.raises(ValueError, match="successful_results_changed"):
        validate_recovery_merge(before, items=altered + [item()], failures=[])


@pytest.mark.parametrize("change", ["institute_id", "patient_id", "visit_id", "rule_id"])
def test_cross_coordinate_or_other_rule_cannot_be_recovered(change):
    before = baseline()
    added = item()
    added[change] = "out-of-scope"
    with pytest.raises(ValueError):
        validate_recovery_merge(before, items=json.loads(before["items_json"]) + [added], failures=[])


@pytest.mark.parametrize("status", ["technical_error", "uncertain", "evaluation_unknown", "failed"])
def test_non_deliverable_recovery_is_rejected(status):
    before = baseline()
    with pytest.raises(ValueError, match="deliverable"):
        validate_recovery_merge(before, items=json.loads(before["items_json"]) + [item(status=status)], failures=[])


def test_other_failure_is_preserved_during_partial_recovery():
    before = baseline()
    remaining = item("LX0609-07-04-01", visit="synthetic-other")
    before["failed_records_json"] = json.dumps([item(), remaining])
    validate_recovery_merge(before, items=json.loads(before["items_json"]) + [item()], failures=[remaining])
    with pytest.raises(ValueError, match="remaining_failures_changed"):
        validate_recovery_merge(before, items=json.loads(before["items_json"]) + [item()], failures=[])


def test_duplicate_result_is_rejected():
    before = baseline()
    with pytest.raises(ValueError, match="duplicate"):
        validate_recovery_merge(before, items=json.loads(before["items_json"]) + [item(), item()], failures=[])


@pytest.mark.parametrize("fault", [None, "expired", "frozen", "scope", "field_gap", "wrong_case", "duplicate_table"])
def test_recovery_requires_fresh_live_four_table_chain_for_exact_failed_case(fault):
    from datetime import datetime, timedelta, timezone
    from app.services.qc_workspace.offline_failure_recovery import content_digest, validate_material_recovery_gate

    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    cases = [{"sample": f"C{i:02}", "institute_id": "synthetic-hospital", "patient_id": "synthetic-patient", "visit_id": f"synthetic-{i}"} for i in range(1, 28)]
    failure = {**cases[17], "rule_id": "LX0609-07-01-02"}
    checks = [{"sample": "C18", "category": category, "table": table, "passed": True} for category, table in (
        ("transfusion", "bloodtrans_record"), ("transfusion", "blood_application"), ("orders", "inpat_drug_order"), ("orders", "inpat_nondrug_order"))]
    # 其他病例的待核实材料不能掩盖目标病例验收，也不阻止已验证配对独立恢复。
    checks.append({"sample": "C01", "category": "discharge", "table": "discharge_record", "passed": False})
    material = {"source_mode": "live_readonly", "captured_at_utc": now.isoformat(), "scope_digest": content_digest(cases), "checks": checks}
    if fault == "expired":
        material["captured_at_utc"] = (now - timedelta(minutes=31)).isoformat()
    elif fault == "frozen":
        material["source_mode"] = "frozen_export"
    elif fault == "scope":
        cases[17]["institute_id"] = "other-hospital"
    elif fault == "field_gap":
        checks[0]["passed"] = False
    elif fault == "wrong_case":
        failure = {**cases[16], "rule_id": failure["rule_id"]}
    elif fault == "duplicate_table":
        checks[0]["table"] = checks[1]["table"]
    if fault:
        with pytest.raises(ValueError):
            validate_material_recovery_gate(material, cases, [failure], now=now)
    else:
        validate_material_recovery_gate(material, cases, [failure], now=now)


def test_replay_requires_exact_unique_prompt_and_does_not_double_charge():
    recording = {"prompt": "original prompt", "response": {"content": "recorded", "usage": {"total_tokens": 999}}}
    original = deepcopy(recording)
    assert replay_response([recording], "original prompt")["usage"]["total_tokens"] == 0
    assert recording == original
    for recordings, prompt in (([recording], "changed prompt"), ([recording, recording], "original prompt")):
        with pytest.raises(ValueError, match="not_uniquely_matched"):
            replay_response(recordings, prompt)


@pytest.mark.parametrize("status,parent", [("completed", None), ("running", None), ("failed", "synthetic-parent")])
def test_only_original_failed_leaf_root_is_accepted(status, parent):
    before = baseline()
    before.update(status=status, parent_job_id=parent)
    with pytest.raises(ValueError, match="failed_leaf_root"):
        validate_recovery_merge(before, items=json.loads(before["items_json"]) + [item()], failures=[])


def test_readonly_workspace_never_delegates_progress_or_completion_writes():
    class Owner:
        def __getattr__(self, name):
            raise AssertionError("unexpected_owner_write:" + name)
    job = {"status": "failed", "summary": {"execution_status": "partial_failed"}, "filters": {"rule_ids": ["LX0609-07-01-02"], "rule_set_key": "luxian_0609_qc_v1"},
           "items": json.loads(baseline()["items_json"]), "failed_records": json.loads(baseline()["failed_records_json"])}
    workspace = ReadonlyRetryWorkspace(Owner(), job)
    workspace.mark_batch_job_running()
    workspace.update_batch_job_progress(items=[])
    workspace.complete_batch_job(items=job["items"], failed_records=[])
    assert workspace.completion["items"] == job["items"]
    assert workspace.retry_batch_job() is None


@pytest.mark.parametrize("fault", [None, "stale_baseline", "save_failure"])
def test_real_completion_transaction_preserves_other_envelope_rows(monkeypatch, fault):
    """实际 Session/UPDATE/事务，信封写入范围受测；不连接业务 PG。"""
    from datetime import datetime
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as owner

    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    jobs = sa.Table("jobs", metadata,
        sa.Column("id", sa.String, primary_key=True),
        *[sa.Column(name, sa.String) for name in ("created_by", "status", "filters_json", "items_json", "failed_records_json", "summary_json", "parent_job_id")],
        *[sa.Column(name, sa.Integer) for name in ("total_records", "success_count", "failed_count", "issue_records", "compliant_records", "total_tokens")],
        sa.Column("total_processing_time", sa.Float), sa.Column("finished_at", sa.DateTime), sa.Column("updated_at", sa.DateTime))
    envelopes = sa.Table("envelopes", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("root_job_id", sa.String), sa.Column("created_by", sa.String), sa.Column("rule_set_key", sa.String), sa.Column("visit_id", sa.String))
    metadata.create_all(engine)
    original = item("LX0609-07-04-01", visit="synthetic-complete", status="compliant")
    filters = json.dumps({"rule_set_key": "luxian_0609_qc_v1", owner.LX0609_ATTEMPT_FILTER_KEY: "original-attempt", "rule_ids": ["LX0609-07-01-02"]})
    row = {**baseline(), "id": "synthetic-job", "created_by": "synthetic-owner", "filters_json": filters,
           "items_json": json.dumps([original]), "summary_json": "{}", "updated_at": datetime(2026, 1, 1)}
    with engine.begin() as connection:
        connection.execute(jobs.insert().values(**row))
        connection.execute(envelopes.insert().values(id="preserve-this-row", root_job_id=row["id"], created_by=row["created_by"], rule_set_key="luxian_0609_qc_v1", visit_id="synthetic-complete"))
    monkeypatch.setattr(owner, "_session", lambda: Session(engine))
    workspace = owner.CustomQCWorkspaceService.__new__(owner.CustomQCWorkspaceService)
    workspace._batch_job_table, workspace._record_result_envelope_table = jobs, envelopes
    workspace.refresh_parent_batch_job = lambda **kwargs: None
    def write(session, *, items, expected_record_refs, **kwargs):
        assert [value["visit_id"] for value in items] == ["synthetic-target"]
        assert [ref.visit_id for ref in expected_record_refs] == ["synthetic-target"]
        if fault == "save_failure":
            raise ValueError("simulated_envelope_failure")
        session.execute(envelopes.insert().values(id="new-target-only", root_job_id=row["id"], visit_id="synthetic-target"))
        return ()
    workspace._write_record_result_envelopes = write
    expected = dict(row)
    if fault == "stale_baseline":
        expected["summary_json"] = '{"changed":true}'
    def complete():
        workspace.complete_batch_job(job_id=row["id"], summary={"execution_status": "completed", "total_records": 2, "success_count": 2},
            items=[original, item()], failed_records=[], recovery_baseline=expected)
    if fault:
        with pytest.raises(ValueError):
            complete()
    else:
        complete()
    with engine.connect() as connection:
        saved = connection.execute(sa.select(jobs)).mappings().one()
        ids = connection.execute(sa.select(envelopes.c.id).order_by(envelopes.c.id)).scalars().all()
    assert "preserve-this-row" in ids
    assert saved["items_json"] == row["items_json"] if fault else json.loads(saved["items_json"])[0] == original
    assert saved["status"] == ("failed" if fault else "completed")
    assert len(ids) == (1 if fault else 2)
