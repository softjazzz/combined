import json
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace as Row
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCDefect
from app.services import manual_quality_report_service as module
from app.services.defect_rectification_service import RectificationError
from tests.unit.test_task_manual_defect_service import (
    env as _creation_env,
    create as create_manual,
)


@pytest.fixture
def creation_env(monkeypatch):
    yield from _creation_env.__wrapped__(monkeypatch)


def chain(defect_id="d1", hospital="H1", creator="u1", department="内科"):
    history = Row(
        actor_id=creator,
        details=json.dumps(
            {
                "task_id": "T1",
                "task_record_id": "R1",
                "run_number": 1,
                "job_id": "J1",
                "scene": "running",
            }
        ),
    )
    record = {
        "id": "R1",
        "task_id": "T1",
        "record_id": "R1",
        "institute_id": hospital,
        "patient_id": "P1",
        "visit_id": "V1",
        "department": department,
    }
    run = {
        "task_id": "T1",
        "run_number": 1,
        "job_id": "J1",
        "triggered_by": creator,
        "run_scope": "assigned",
    }
    job = {
        "id": "J1",
        "created_by": creator,
        "filters_json": json.dumps(
            {
                "task_id": "T1",
                "task_run_number": 1,
                "query_scope": "running",
                "rule_set_key": "synthetic-rules",
                "rule_set_version": "v1",
                "record_refs": [
                    {
                        key: record[key]
                        for key in ("institute_id", "patient_id", "visit_id")
                    }
                ],
            }
        ),
    }
    envelope = {
        "id": "E1",
        "record_id": "V1",
        "created_by": creator,
        "result_count": 1,
        "envelope_json": json.dumps(
            {
                "schema_version": module.RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": module.CANONICAL_RESULT_DELIVERY_MODE,
                "items": [{"rule_id": "synthetic-rule"}],
            }
        ),
    }
    return {
        "histories": {defect_id: [history]},
        "records": {"R1": record},
        "runs": {("T1", 1): run},
        "jobs": {"J1": job},
        "envelopes": {
            ("J1", hospital, "P1", "V1", "synthetic-rules", "v1"): [envelope]
        },
        "rectifications": {},
        "people": {creator: "合成质控员"},
        "tasks": {"T1": "合成已保存任务"},
    }


def defect(defect_id="d1", **changes):
    return Row(
        id=defect_id,
        record_id="R1",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        scene="running",
        manual_created_by="u1",
        **changes,
    )


def resolve(row, data):
    return module._source(
        row,
        data["histories"].get(row.id, []),
        data["records"],
        data["runs"],
        data["jobs"],
        data["envelopes"],
    )


def test_original_run_preserved_not_current_run_or_other_scene():
    data = chain()
    data["runs"][("T1", 2)] = {**data["runs"][("T1", 1)], "job_id": "J2"}
    task, department, source = resolve(defect(), data)
    assert task["run_number"] == 1 and department == "内科"
    assert source == (
        "H1",
        "P1",
        "V1",
        "running",
        "task_manual_defect",
        "d1",
        "J1",
        "E1",
    )
    data["runs"][("T1", 1)]["job_id"] = "J2"
    assert resolve(defect(), data)[2] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_history",
        "actor",
        "record_identity",
        "scene",
        "missing_job",
        "config_scene",
        "envelope_identity",
        "duplicate_envelope",
        "payload",
        "count",
    ],
)
def test_incomplete_or_crossed_source_is_unknown(mutation):
    data = chain()
    if mutation == "duplicate_history":
        data["histories"]["d1"] *= 2
    if mutation == "actor":
        data["histories"]["d1"][0].actor_id = "other"
    if mutation == "record_identity":
        data["records"]["R1"]["patient_id"] = "other"
    if mutation == "scene":
        data["histories"]["d1"][0].details = json.dumps(
            {
                "task_id": "T1",
                "task_record_id": "R1",
                "run_number": 1,
                "job_id": "J1",
                "scene": "final",
            }
        )
    if mutation == "missing_job":
        data["jobs"] = {}
    if mutation == "config_scene":
        data["jobs"]["J1"]["filters_json"] = data["jobs"]["J1"]["filters_json"].replace(
            '"running"', '"final"'
        )
    if mutation == "envelope_identity":
        data["envelopes"] = {}
    envelope = next(iter(data["envelopes"].values()))[0] if data["envelopes"] else None
    if mutation == "duplicate_envelope":
        next(iter(data["envelopes"].values())).append(deepcopy(envelope))
    if mutation == "payload":
        envelope["envelope_json"] = "broken"
    if mutation == "count":
        envelope["result_count"] = 0
    assert resolve(defect(), data)[2] is None


@pytest.fixture
def setup():
    engine = create_engine("sqlite://")
    QCDefect.__table__.create(engine)
    sessions = sessionmaker(engine)
    with sessions() as session, session.begin():
        for id, hospital, creator, review, scene, origin in [
            ("d1", "H1", "u1", "pending", "running", "manual"),
            ("d2", "H1", "u2", "approved", "running", "manual"),
            ("d3", "H2", "u3", "rejected", "running", "manual"),
            ("d4", "H1", "u1", "pending", "final", "manual"),
            ("auto", "H1", "u1", "pending", "running", "auto"),
        ]:
            session.add(
                QCDefect(
                    id=id,
                    record_id="R1",
                    institute_id=hospital,
                    patient_id="P1",
                    visit_id="V1",
                    scene=scene,
                    identity_version=1,
                    source_key="task_assigned_qc",
                    origin=origin,
                    manual_created_by=creator,
                    manual_review_status=review if origin == "manual" else None,
                    rule_name="合成缺陷",
                    created_at=datetime(2026, 10, 1, 8),
                    updated_at=datetime(2026, 10, 1),
                )
            )
    people = {
        "manager": {
            "id": "manager",
            "roles": {"qc_manager"},
            "institute_id": "H1",
            "department": "内科",
        },
        "admin": {
            "id": "admin",
            "roles": {"admin"},
            "institute_id": None,
            "department": None,
        },
        "u1": {
            "id": "u1",
            "roles": {"qc_staff"},
            "institute_id": "H1",
            "department": "内科",
        },
        "doctor": {
            "id": "doctor",
            "roles": {"doctor"},
            "institute_id": "H1",
            "department": "内科",
        },
    }
    service = module.ManualQualityReportService(
        sessions, lambda session, actor: people[actor]
    )

    def batch(session, rows):
        combined = chain()
        # 本合成任务只有第一例来源完整，其余明确未知。
        if not any(row.id == "d1" for row in rows):
            combined["histories"] = {}
        return combined

    service._batch = Mock(side_effect=batch)
    return service


def report(service, actor="manager", **kwargs):
    return service.report(
        actor,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        scene="running",
        **kwargs,
    )


def test_current_states_independent_scope_and_filter_before_page(setup):
    result = report(setup, page_size=1)
    assert result["total"] == 2 and len(result["items"]) == 1
    assert result["summary"]["review"] == {
        "pending": 1,
        "approved": 1,
        "rejected": 0,
        "unknown": 0,
    }
    assert result["summary"]["rectification"]["unassigned"] == 1
    assert result["summary"]["rectification"]["unknown"] == 1
    assert "已确认统计口径" in result["assumption"]
    assert "待确认" not in result["assumption"]
    assert result["as_of"].endswith("Z") and result["timezone"] == "Asia/Shanghai"
    assert report(setup, task_id="T1")["total"] == 1
    assert report(setup, creator_id="u2")["summary"]["entered"] == 1
    assert report(setup, institute_id="H1", department="内科")["total"] == 1
    assert report(setup, "admin")["total"] == 3
    assert report(setup, "u1")["total"] == 1
    assert setup._batch.call_count == 6


@pytest.mark.parametrize("state", ["pending", "submitted", "approved", "rejected"])
def test_modern_rectification_current_state_never_replaces_review_or_counts_events(
    setup, state
):
    original = setup._batch.side_effect

    def batch(session, rows):
        data = original(session, rows)
        keys = (
            "institute_id",
            "patient_id",
            "visit_id",
            "scene",
            "target_kind",
            "target_id",
            "root_job_id",
            "envelope_id",
        )
        values = ("H1", "P1", "V1", "running", "task_manual_defect", "d1", "J1", "E1")
        data["rectifications"] = {"d1": [Row(**dict(zip(keys, values)), status=state)]}
        return data

    setup._batch.side_effect = batch
    result = report(setup, creator_id="u1")
    assert result["summary"]["entered"] == 1
    assert result["summary"]["review"]["pending"] == 1
    assert result["summary"]["rectification"][state] == 1


def test_wrong_round_rectification_not_unassigned_or_new_round_status(setup):
    original = setup._batch.side_effect

    def batch(session, rows):
        data = original(session, rows)
        data["rectifications"] = {
            "d1": [
                Row(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    scene="running",
                    target_kind="task_manual_defect",
                    target_id="d1",
                    root_job_id="J2",
                    envelope_id="E2",
                    status="approved",
                )
            ]
        }
        return data

    setup._batch.side_effect = batch
    result = report(setup, creator_id="u1")
    assert result["summary"]["rectification"]["unknown"] == 1
    assert result["summary"]["rectification"]["approved"] == 0
    assert result["summary"]["rectification"]["unassigned"] == 0


def test_batch_read_count_does_not_grow_with_candidates(monkeypatch):
    import sqlalchemy as sa

    metadata = sa.MetaData()
    jobs = sa.Table("synthetic_jobs", metadata, sa.Column("id", sa.String))
    envelopes = sa.Table(
        "synthetic_envelopes",
        metadata,
        *[
            sa.Column(key, sa.String)
            for key in ("root_job_id", "institute_id", "patient_id", "visit_id")
        ],
    )
    histories = [
        Row(defect_id=f"d{i}", **vars(chain()["histories"]["d1"][0]))
        for i in range(100)
    ]
    session = Mock()
    session.scalars.side_effect = [histories, [], [], []]
    result = Mock()
    result.mappings.return_value = []
    session.execute.return_value = result
    monkeypatch.setattr(module, "user_owner_options", lambda session: {})
    service = module.ManualQualityReportService(tables=(jobs, envelopes))
    service._batch(session, [defect(f"d{i}") for i in range(100)])
    assert session.scalars.call_count == 4
    assert session.execute.call_count == 4


@pytest.mark.parametrize(
    "actor,kwargs",
    [("doctor", {}), ("manager", {"institute_id": "H2"}), ("u1", {"creator_id": "u2"})],
)
def test_persistent_permissions_fail_closed(setup, actor, kwargs):
    with pytest.raises(RectificationError) as error:
        report(setup, actor, **kwargs)
    assert error.value.status == 403
    setup._batch.assert_not_called()


def test_errors_limits_and_bad_dates_do_not_fabricate_zero(setup, monkeypatch):
    with pytest.raises(RectificationError):
        report(setup, department="内科")
    with pytest.raises(RectificationError):
        report(setup, page_size=101)
    monkeypatch.setattr(module, "MAX_ROWS", 1)
    with pytest.raises(RectificationError):
        report(setup)
    monkeypatch.setattr(module, "MAX_ROWS", 10000)
    setup._batch.side_effect = RuntimeError("synthetic-source-failure")
    with pytest.raises(RuntimeError):
        report(setup)
    setup.person = Mock(side_effect=RectificationError("账号失活", 403))
    with pytest.raises(RectificationError):
        report(setup)


def test_csv_formula_and_unknown_are_explicit_without_private_text():
    text = module.csv_export(
        [
            {
                "id": "=SUM(1)",
                "rule_name": " @evil",
                "creator_name": "\tformula",
                "review_status": "pending",
                "rectification_status": "unknown",
                "evidence": "private text",
            }
        ]
    )
    assert "'=SUM(1)" in text and "' @evil" in text and "'\tformula" in text
    assert "private text" not in text and "统计口径（已确认）" in text and "未知" in text
    assert "已确认统计口径" in text and "待确认" not in text


def test_hospital_calendar_left_closed_right_open_utc_boundaries(setup):
    with setup.sessions() as session, session.begin():
        for id, created in [
            ("before", datetime(2026, 9, 30, 15, 59, 59)),
            ("start", datetime(2026, 9, 30, 16)),
            ("last", datetime(2026, 10, 1, 15, 59, 59)),
            ("end", datetime(2026, 10, 1, 16)),
        ]:
            session.add(
                QCDefect(
                    id=id,
                    record_id="R1",
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    scene="running",
                    identity_version=1,
                    source_key="task_assigned_qc",
                    origin="manual",
                    manual_created_by="u1",
                    manual_review_status="pending",
                    created_at=created,
                    updated_at=created,
                )
            )
    result = report(setup)
    ids = {item["id"] for item in result["items"]}
    assert {"start", "last"} <= ids and not {"before", "end"} & ids
    assert result["total"] == 4


def test_real_manual_creation_owner_persists_identity_used_by_report(creation_env):
    from sqlalchemy import select
    from app.database.models.qc import QCDefectHistory, QCTaskRecord, QCTaskQCRun

    created = create_manual(creation_env)
    sessions = creation_env[0]
    with sessions() as session:
        row = session.get(QCDefect, created["id"])
        histories = session.scalars(
            select(QCDefectHistory).where(QCDefectHistory.defect_id == row.id)
        ).all()
        record = (
            session.execute(
                select(QCTaskRecord.__table__).where(QCTaskRecord.id == "record-a")
            )
            .mappings()
            .one()
        )
        run = (
            session.execute(
                select(QCTaskQCRun.__table__).where(
                    QCTaskQCRun.task_id == "task-1", QCTaskQCRun.run_number == 1
                )
            )
            .mappings()
            .one()
        )
        data = chain()
        filters = {
            "task_id": "task-1",
            "task_run_number": 1,
            "query_scope": "running",
            "rule_set_key": "synthetic-rules",
            "rule_set_version": "v1",
            "record_refs": [
                {
                    "institute_id": "hospital-A",
                    "patient_id": "patient",
                    "visit_id": "visit",
                }
            ],
        }
        task, _, source = module._source(
            row,
            histories,
            {"record-a": record},
            {("task-1", 1): run},
            {
                "job-1": {
                    "id": "job-1",
                    "created_by": "qc-1",
                    "filters_json": json.dumps(filters),
                }
            },
            {
                ("job-1", "hospital-A", "patient", "visit", "synthetic-rules", "v1"): [
                    {
                        **next(iter(data["envelopes"].values()))[0],
                        "record_id": "visit",
                        "created_by": "qc-1",
                    }
                ]
            },
        )
        assert row.record_id == task["task_record_id"] == "record-a"
        assert task["run_number"] == 1 and source[-2:] == ("job-1", "E1")
