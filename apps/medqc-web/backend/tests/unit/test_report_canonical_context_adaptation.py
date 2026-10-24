"""定向适配：报表锚点来自目标线已选中的 Canonical 行，不改变客户读取合同。"""

import json
from copy import deepcopy

import pytest

from app.services import custom_qc_workspace_service as workspace


class ReadSession:
    def __init__(self, jobs, envelopes):
        self.rows = iter([jobs, envelopes])
        self.statements = []

    def execute(self, sql):
        self.statements.append(sql)
        if not sql.is_select:
            raise AssertionError("报表只允许 SELECT")
        return self

    def mappings(self):
        return self

    def all(self):
        return next(self.rows)

    def close(self):
        pass


@pytest.fixture
def reader(workspace_tables_without_database):
    return workspace.CustomQCWorkspaceService(readonly=True)


def rows(*, invalid=False):
    job = {"id": "synthetic-current", "status": "completed", "created_at": "2026-10-23T10:00:00",
           "finished_at": "2026-10-23T10:01:00", "filters_json": json.dumps({
               "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}),
           "record_ids_json": '["visit-1"]', "summary_json": "{}"}
    envelope = {"id": "synthetic-envelope", "root_job_id": job["id"], "job_id": job["id"],
                "institute_id": "A", "patient_id": "patient-1", "visit_id": "visit-1",
                "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                "envelope_json": json.dumps({"schema_version": "invalid" if invalid else "lx0609-record-result-envelope-v1",
                                             "delivery_mode": "canonical_straight_through", "items": [{
                                                 "rule_id": "LX0609-01-01-01", "status": "compliant",
                                                 "result_status": "compliant", "is_compliant": True}]})}
    return job, envelope


def read(reader, jobs, envelopes, *, context=False):
    session = ReadSession(jobs, envelopes)
    result = reader.build_luxian_0609_completed_record_result_summaries(
        record_refs=[{"institute_id": "A", "patient_id": "patient-1", "visit_id": "visit-1"}],
        session_factory=lambda: session, include_items=True, include_rule_set_context=context)
    assert len(session.statements) == 2
    return result[("A", "patient-1", "visit-1")]


def test_opt_in_adds_only_selected_persistent_anchors(reader):
    job, envelope = rows()
    before = deepcopy((job, envelope))
    original = read(reader, [job], [envelope])
    adapted = read(reader, [job], [envelope], context=True)
    assert original["status"] == "ready"
    context = {key: adapted.pop(key) for key in ("root_job_id", "envelope_id", "rule_set_key", "rule_set_version")}
    assert context == {"root_job_id": job["id"], "envelope_id": envelope["id"],
                       "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}
    assert adapted == original
    assert (job, envelope) == before


def test_other_institute_same_visit_cannot_supply_anchor(reader):
    job, envelope = rows()
    envelope["institute_id"] = "B"
    assert read(reader, [job], [envelope], context=True) == {"status": "not_run"}


@pytest.mark.parametrize("fault", ["invalid", "duplicate", "tie"])
def test_invalid_or_ambiguous_result_never_gets_anchors(reader, fault):
    job, envelope = rows(invalid=fault == "invalid")
    jobs, envelopes = [job], [envelope]
    if fault == "duplicate":
        envelopes.append({**envelope, "id": "synthetic-duplicate"})
    if fault == "tie":
        jobs.append({**job, "id": "synthetic-tie"})
        envelopes.append({**envelope, "id": "synthetic-tie-envelope", "root_job_id": "synthetic-tie", "job_id": "synthetic-tie"})
    result = read(reader, jobs, envelopes, context=True)
    assert result["status"] == "technical_error"
    assert set(result).isdisjoint({"root_job_id", "envelope_id", "rule_set_key", "rule_set_version"})
