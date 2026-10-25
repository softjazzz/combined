from __future__ import annotations

from app.services.luxian_0609.record_result_read_model import (
    select_latest_authoritative_record_result_job,
)


def test_new_full_run_uses_its_own_frozen_scope_even_when_release_scope_shrinks():
    old = {**_job("old-full", created_at="2026-10-24T10:00:00"),
           "result_rule_scope": ["rule-a", "rule-b"], "result_scope_kind": "full"}
    new = {**_job("new-full", created_at="2026-10-25T10:00:00"),
           "result_rule_scope": ["rule-a"], "result_scope_kind": "full"}
    selection = select_latest_authoritative_record_result_job(
        [old, new], record_id="visit-1", rule_set_key="luxian_0609",
        rule_set_version="2026-06-09", prefer_full_scope=True,
    )
    assert selection.job["id"] == "new-full"


def test_incomparable_targeted_scopes_are_not_combined_into_full_results():
    first = {**_job("target-a", created_at="2026-10-24T10:00:00"),
             "result_rule_scope": ["rule-a"], "result_scope_kind": "targeted"}
    second = {**_job("target-b", created_at="2026-10-25T10:00:00"),
              "result_rule_scope": ["rule-b"], "result_scope_kind": "targeted"}
    selection = select_latest_authoritative_record_result_job(
        [first, second], record_id="visit-1", rule_set_key="luxian_0609",
        rule_set_version="2026-06-09", prefer_full_scope=True,
    )
    assert selection.state == "technical_error"
    assert selection.reason_code == "record_result_scope_conflict"


def _job(
    job_id: str,
    *,
    created_at: str,
    record_ids: list[str] | None = None,
    created_by: str = "reviewer-a",
    status: str = "completed",
    rule_set_key: str = "luxian_0609",
    rule_set_version: str = "2026-06-09",
):
    return {
        "id": job_id,
        "created_at": created_at,
        "record_ids": record_ids or ["visit-1"],
        "created_by": created_by,
        "status": status,
        "filters": {
            "rule_set_key": rule_set_key,
            "rule_set_version": rule_set_version,
        },
    }


def test_select_latest_authoritative_record_job_uses_only_identity_and_current_generation():
    selection = select_latest_authoritative_record_result_job(
        [
            _job("old", created_at="2026-07-29T09:00:00"),
            _job("new", created_at="2026-07-29T10:00:00"),
            _job("other-user", created_at="2026-07-29T11:00:00", created_by="reviewer-b"),
            _job("other-record", created_at="2026-07-29T11:00:00", record_ids=["visit-2"]),
            _job("running", created_at="2026-07-29T11:00:00", status="running"),
            _job("old-version", created_at="2026-07-29T11:00:00", rule_set_version="2026-01-01"),
        ],
        record_id="visit-1",
        rule_set_key="luxian_0609",
        rule_set_version="2026-06-09",
    )

    assert selection.state == "ready"
    assert selection.job is not None
    assert selection.job["id"] == "other-user"
    assert selection.candidate_count == 3


def test_select_latest_authoritative_record_job_fails_closed_for_current_generation_tie():
    selection = select_latest_authoritative_record_result_job(
        [
            _job("first", created_at="2026-07-29T10:00:00"),
            _job("second", created_at="2026-07-29T10:00:00"),
        ],
        record_id="visit-1",
        rule_set_key="luxian_0609",
        rule_set_version="2026-06-09",
    )

    assert selection.state == "technical_error"
    assert selection.reason_code == "record_result_task_generation_conflict"


def test_select_latest_authoritative_record_job_does_not_choose_a_candidate_by_explanation_or_status():
    sparse_new = _job("new", created_at="2026-07-29T10:00:00")
    sparse_new["items"] = [{"rule_id": "LX0609-01-01-02", "conclusion": ""}]
    verbose_old = _job("old", created_at="2026-07-29T09:00:00")
    verbose_old["items"] = [{"rule_id": "LX0609-01-01-02", "conclusion": "历史长文案"}]

    selection = select_latest_authoritative_record_result_job(
        [verbose_old, sparse_new],
        record_id="visit-1",
        rule_set_key="luxian_0609",
        rule_set_version="2026-06-09",
    )

    assert selection.job is not None
    assert selection.job["id"] == "new"


def test_select_latest_authoritative_record_job_prefers_latest_finished_generation_and_accepts_summary_version():
    earlier_finished = _job("earlier", created_at="2026-07-29T11:00:00")
    earlier_finished["finished_at"] = "2026-07-29T11:10:00"
    later_finished = _job("later", created_at="2026-07-29T09:00:00")
    later_finished["finished_at"] = "2026-07-29T12:00:00"
    later_finished["filters"] = {"rule_set_key": "luxian_0609"}
    later_finished["summary"] = {"rule_set_version": "2026-06-09"}

    selection = select_latest_authoritative_record_result_job(
        [earlier_finished, later_finished],
        record_id="visit-1",
        rule_set_key="luxian_0609",
        rule_set_version="2026-06-09",
    )

    assert selection.state == "ready"
    assert selection.job is not None
    assert selection.job["id"] == "later"


def test_select_latest_authoritative_record_job_uses_latest_completed_job_across_creators():
    selection = select_latest_authoritative_record_result_job(
        [
            _job("older-owner", created_at="2026-07-29T10:00:00", created_by="reviewer-a"),
            _job("newer-owner", created_at="2026-07-29T11:00:00", created_by="reviewer-b"),
        ],
        record_id="visit-1",
        rule_set_key="luxian_0609",
        rule_set_version="2026-06-09",
    )

    assert selection.state == "ready"
    assert selection.job is not None
    assert selection.job["id"] == "newer-owner"
