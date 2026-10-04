"""单病例候选查询：真实 SQL 投影、旧身份回退和代次冲突保护。"""
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace


@pytest.fixture
def reader(monkeypatch):
    # 仅写内存 SQLite 合成任务，不接触业务数据库或初始化服务表。
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "jobs", metadata,
        *(sa.Column(key, sa.Text, primary_key=key == "id") for key in (
            "id", "status", "parent_job_id", "filters_json", "record_ids_json",
            "summary_json", "items_json", "created_at", "finished_at",
        )),
    )
    envelopes = sa.Table(
        "envelopes", metadata,
        *(sa.Column(key, sa.Text) for key in (
            "root_job_id", "institute_id", "patient_id", "visit_id",
            "rule_set_key", "rule_set_version",
        )),
    )
    metadata.create_all(engine)
    service = workspace.CustomQCWorkspaceService.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table = jobs
    service._record_result_envelope_table = envelopes
    monkeypatch.setattr(workspace, "_session", lambda: Session(engine))
    monkeypatch.setattr(service, "_load_record_result_envelope_items", lambda *a, **kw: None)
    monkeypatch.setattr(service, "_aggregate_parent_job", lambda *a, **kw: pytest.fail("不能聚合历史结果"))
    statements = []
    sa.event.listen(engine, "before_cursor_execute", lambda c, cur, sql, p, ctx, many: statements.append(sql))

    def add(job_id, *, filters=None, summary=None, status="completed", stamp="2026-10-01", visit="v", patient="p"):
        with engine.begin() as connection:
            connection.execute(jobs.insert().values(
                id=job_id, status=status, parent_job_id=None,
                filters_json=json.dumps(filters if filters is not None else {"rule_set_key": "rules", "rule_set_version": "version"}),
                record_ids_json=json.dumps([visit]), summary_json=json.dumps(summary),
                items_json="不可解析的历史 payload", created_at=stamp, finished_at=stamp,
            ))
            connection.execute(envelopes.insert().values(
                root_job_id=job_id, institute_id="i", patient_id=patient, visit_id=visit,
                rule_set_key="rules", rule_set_version="version",
            ))

    def read():
        statements.clear()
        return service.build_latest_single_record_result_dto(
            institute_id="i", patient_id="p", visit_id="v", rule_set_key="rules",
            rule_set_version="version", expected_rule_ids=["LX0609-01-01-01"],
        )

    yield add, read, statements
    engine.dispose()


@pytest.mark.parametrize("status", ["completed", "failed", "running", "queued", "canceled"])
def test_exact_envelope_selects_case_without_legacy_payload(reader, status):
    add, read, statements = reader
    add("current", status=status, summary={"rule_set_key": "wrong"})
    result = read()
    assert result["job_id"] == "current"
    assert result["reason_code"] == "canonical_result_envelope_missing"
    assert len(statements) == 1
    projection = statements[0].split("FROM")[0]
    assert "summary_json" not in projection
    assert "items_json" not in projection
    assert "filters_json" in projection


@pytest.mark.parametrize("filters", [{}, {"rule_set_key": "rules"}, {"rule_set_version": "version"}])
def test_missing_filter_identity_loads_summary_lazily(reader, filters):
    add, read, statements = reader
    add("legacy", filters=filters, summary={"rule_set_key": "rules", "rule_set_version": "version"})
    assert read()["job_id"] == "legacy"
    assert len(statements) == 2
    assert "summary_json" in statements[1]
    assert "items_json" not in statements[1]


def test_filter_identity_still_wins_over_summary(reader):
    add, read, _ = reader
    add("legacy", filters={"rule_set_key": "wrong"}, summary={"rule_set_key": "rules", "rule_set_version": "version"})
    assert read()["state"] == "not_found"


def test_same_generation_still_fails_closed(reader):
    add, read, _ = reader
    add("a")
    add("b")
    result = read()
    assert result["reason_code"] == "record_result_task_generation_conflict"
    assert result["job_id"] == ""


def test_latest_exact_patient_wins_without_quality_ranking(reader):
    add, read, _ = reader
    add("old", stamp="2026-09-01")
    add("current")
    add("other-patient", stamp="2026-10-02", patient="other")
    assert read()["job_id"] == "current"
