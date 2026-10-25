from copy import deepcopy
from datetime import datetime
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models.v36_reports import QCDefect, QCDefectHistory
from app.database.models.v36_reports import QCRecordReview as ReportReview
from app.services.defect_rectification_service import RectificationError
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.record_review_defect_snapshot_service import validate_snapshot
from app.services.record_review_workflow_service import (
    QCRecordReview,
    RecordReviewWorkflowService,
    _ManualSnapshotReadSession,
    _candidate_sources,
    _capture_snapshot,
)


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite:///:memory:", execution_options={"schema_translate_map": {"qc": None}}
    )
    ReportReview.__table__.create(engine)
    sessions = sessionmaker(engine)
    source = dict(
        institute_id="A",
        patient_id="P",
        visit_id="V",
        scene="running",
        root_job_id="J",
        envelope_id="E",
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        rule_set_version="1",
    )
    people = {
        "staff": dict(
            id="staff",
            name="合成质控员",
            roles={"qc_staff"},
            institute_id="A",
            department="内科",
        ),
        "manager": dict(
            id="manager",
            name="合成主管",
            roles={"qc_manager"},
            institute_id="A",
            department="内科",
        ),
        "doctor": dict(
            id="doctor",
            name="合成医生",
            roles={"doctor"},
            institute_id="A",
            department="内科",
        ),
        "outsider": dict(
            id="outsider",
            name="合成外院",
            roles={"qc_staff"},
            institute_id="B",
            department="内科",
        ),
    }

    def snapshot(session, current, captured_at):
        frozen = {
            key: value
            for key, value in current.items()
            if key not in {"root_job_id", "items"}
        } | {"job_id": current["root_job_id"]}
        return validate_snapshot(
            dict(
                schema_version=1,
                complete=True,
                captured_at=captured_at.isoformat() + "+00:00",
                source=frozen,
                auto={"count": 1, "items": [{"defect_id": "R", "rule_id": "R"}]},
                manual={"count": 0, "items": []},
            ),
            source=frozen,
        )

    service = RecordReviewWorkflowService(
        sessions,
        person_loader=lambda session, actor: deepcopy(people[actor]),
        source_loader=lambda session, identity, job, envelope: (
            deepcopy(source) | {"items": [{"rule_id": "R", "is_confirmed_issue": True}]}
        ),
        department_loader=lambda session, identity: "内科",
        snapshot_loader=snapshot,
        candidates_loader=lambda session, actor: [
            deepcopy(source) | {"case_department": "内科"}
        ],
    )
    yield service, sessions, source, people
    engine.dispose()


def submit(service, source, **overrides):
    values = dict(
        source=deepcopy(source),
        expected_state="pending_review",
        decision="approved",
        reason="合成意见",
        request_id=str(uuid4()),
    )
    values.update(overrides)
    return service.submit("staff", **values)


@pytest.mark.parametrize("scene", ["running", "final"])
def test_initial_round_recheck_history_and_report_contract(setup, scene):
    service, sessions, source, _ = setup
    source["scene"] = scene
    assert service.list("staff", scene=scene)["initial_count"] == 1
    initial = submit(service, source, decision="doubtful")
    assert initial["stage"] == "initial"
    assert service.current("staff", source=source)["state"] == "doubtful"
    assert service.list("staff")["pending_count"] == 0
    with sessions() as session:
        row = session.get(QCRecordReview, initial["id"])
        assert row.review_context == "workspace" and row.task_id is None
        assert row.defect_snapshot["case_department"] == "内科"
        validate_snapshot(
            row.defect_snapshot,
            source={**row.defect_snapshot["source"], "created_at": row.created_at},
        )
    old = deepcopy(source)
    source.update(root_job_id="J2", envelope_id="E2", rule_set_version="2")
    assert service.list("staff")["recheck_count"] == 1
    assert service.current("staff", source=source)["state"] == "pending_recheck"
    with pytest.raises(RectificationError) as stale:
        submit(service, old)
    assert stale.value.status == 409
    with pytest.raises(RectificationError):
        submit(service, source)
    # 既有合同不要求复审人分离，保留同一质控员在新结果复审的能力。
    recheck = submit(service, source, expected_state="pending_recheck")
    assert recheck["stage"] == "recheck"
    assert service.list("staff")["pending_count"] == 0
    history = service.list("staff", state="history", page_size=1)
    assert history["total"] == 2 and len(history["items"]) == 1
    assert service.history("staff", initial["id"])["can_submit"] is False
    assert len(service.history("staff", recheck["id"])["history"]) == 2
    source.update(root_job_id="J3", envelope_id="E3")
    assert service.current("staff", source=source)["state"] == "pending_review"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 2


def test_idempotent_request_and_no_update_or_duplicate_event(setup):
    service, sessions, source, _ = setup
    request_id = str(uuid4())
    row = submit(service, source, request_id=request_id)
    assert submit(service, source, request_id=request_id)["idempotent"] is True
    with pytest.raises(RectificationError) as conflict:
        submit(service, source, request_id=request_id, reason="另一条意见")
    assert conflict.value.status == 409
    with pytest.raises(RectificationError):
        submit(service, source)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 1
        assert session.get(QCRecordReview, row["id"]).reason == "合成意见"


@pytest.mark.parametrize("actor", ["doctor", "outsider"])
def test_persistent_role_and_institute_boundary(setup, actor):
    service, sessions, source, _ = setup
    with pytest.raises(RectificationError) as error:
        service.current(actor, source=source)
    assert error.value.status == 403
    with pytest.raises(RectificationError):
        service.submit(
            actor,
            source=source,
            expected_state="pending_review",
            decision="approved",
            reason="",
            request_id=str(uuid4()),
        )
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 0


@pytest.mark.parametrize(
    "key,value",
    [("rule_set_version", "bad"), ("scene", "final"), ("envelope_id", "old")],
)
def test_source_version_scene_and_envelope_mismatch_fail_closed(setup, key, value):
    service, sessions, source, _ = setup
    with pytest.raises(RectificationError) as error:
        submit(service, {**source, key: value})
    assert error.value.status == 409
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 0


def test_snapshot_failure_and_transaction_event_failure_roll_back(setup):
    service, sessions, source, _ = setup
    valid_snapshot = service.snapshot
    service.snapshot = lambda *args: (_ for _ in ()).throw(
        RuntimeError("snapshot unavailable")
    )
    with pytest.raises(RuntimeError):
        submit(service, source)
    service.snapshot = valid_snapshot

    def reject_insert(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO"):
            raise RuntimeError("event unavailable")

    event.listen(sessions.kw["bind"], "before_cursor_execute", reject_insert)
    with pytest.raises(RuntimeError):
        submit(service, source)
    event.remove(sessions.kw["bind"], "before_cursor_execute", reject_insert)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 0


def test_list_failure_never_becomes_zero(setup):
    service, _, _, _ = setup
    service.candidates = lambda *args: (_ for _ in ()).throw(
        RuntimeError("source unavailable")
    )
    with pytest.raises(RuntimeError):
        service.list("staff")


def test_default_snapshot_requires_formal_projection(setup):
    service, _, source, _ = setup
    service.snapshot = _capture_snapshot
    service.source = lambda *args: {**source, "items": [{"rule_id": "R"}]}
    with pytest.raises(RectificationError) as error:
        submit(service, source)
    assert error.value.status == 409


def test_history_scope_survives_new_round_but_not_role_removal(setup):
    service, _, source, people = setup
    row = submit(service, source)
    source.update(root_job_id="new", envelope_id="new")
    assert service.history("staff", row["id"])["root_job_id"] == "J"
    people["staff"]["roles"] = {"doctor"}
    with pytest.raises(RectificationError) as error:
        service.history("staff", row["id"])
    assert error.value.status == 403


def test_paused_scene_and_missing_department_are_rejected(setup):
    service, _, source, _ = setup
    with pytest.raises(RectificationError):
        submit(service, {**source, "scene": "outpatient_emergency"})
    service.department = lambda *args: ""
    with pytest.raises(RectificationError):
        submit(service, source)


def test_candidate_result_technical_error_does_not_reduce_pending_count_to_zero(
    setup, monkeypatch
):
    from app.services import custom_qc_workspace_service, report_case_scope

    service, sessions, source, people = setup
    monkeypatch.setattr(
        report_case_scope, "load_current_workstation_records", lambda **kwargs: [source]
    )
    monkeypatch.setattr(
        custom_qc_workspace_service,
        "CustomQCWorkspaceService",
        lambda **kwargs: SimpleNamespace(
            build_luxian_0609_completed_record_result_summaries=lambda **kwargs: {
                ("A", "P", "V"): {"status": "technical_error"}
            }
        ),
    )
    with sessions() as session, pytest.raises(RectificationError) as error:
        _candidate_sources(session, people["staff"])
    assert error.value.status == 503


def test_invalid_snapshot_is_never_saved_as_confirmed_zero(setup):
    service, sessions, source, _ = setup
    service.snapshot = lambda *args: {
        "complete": True,
        "auto": {"count": 0, "items": []},
    }
    with pytest.raises(ValueError):
        submit(service, source)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 0


def test_default_snapshot_freezes_actual_projection_and_proves_no_manual_rows(setup):
    service, sessions, source, _ = setup
    QCDefect.__table__.create(sessions.kw["bind"])
    service.snapshot = _capture_snapshot
    row = submit(service, source)
    with sessions() as session:
        frozen = session.get(QCRecordReview, row["id"]).defect_snapshot
        assert frozen["auto"] == {
            "count": 1,
            "items": [{"defect_id": "R", "rule_id": "R"}],
        }
        assert frozen["manual"] == {"count": 0, "items": []}
        validate_snapshot(frozen, source=frozen["source"])


def test_manual_snapshot_reads_pin_qc_without_overriding_user_owner():
    from unittest.mock import Mock

    session = Mock()
    session.get_bind.return_value.dialect.name = "postgresql"
    scoped = _ManualSnapshotReadSession(session)
    statement = select(QCDefect)
    scoped.execute(statement)
    session.execute.assert_called_once_with(
        statement, execution_options={"schema_translate_map": {None: "qc"}}
    )
    scoped.scalars(statement, execution_options={"schema_translate_map": {None: "sys"}})
    session.scalars.assert_called_once_with(
        statement, execution_options={"schema_translate_map": {None: "sys"}}
    )


@pytest.mark.parametrize("created_envelope", ["E", "E-old", None])
def test_manual_snapshot_requires_explicit_creation_envelope_even_when_job_is_same(
    setup, monkeypatch, created_envelope
):
    from app.services import manual_quality_report_service as manual_report
    from app.services.qc_workspace.canonical_result_store import (
        CANONICAL_RESULT_DELIVERY_MODE,
        RECORD_RESULT_ENVELOPE_SCHEMA,
    )

    service, sessions, source, _ = setup
    for model in (QCDefect, QCDefectHistory):
        model.__table__.create(sessions.kw["bind"])
    creation_details = {
        "task_id": "T",
        "task_record_id": "TR",
        "run_number": 1,
        "job_id": "J",
        "scene": "running",
    }
    if created_envelope is not None:
        creation_details["envelope_id"] = created_envelope
    identity = {key: source[key] for key in ("institute_id", "patient_id", "visit_id")}
    with sessions.begin() as session:
        session.add(
            QCDefect(
                id="D",
                record_id="TR",
                **identity,
                scene="running",
                identity_version=1,
                source_key="task_assigned_qc",
                origin="manual",
                manual_review_status="approved",
                manual_created_by="creator",
                status="pending",
            )
        )
        session.add_all(
            [
                QCDefectHistory(
                    id="HC",
                    defect_id="D",
                    action="manual_create",
                    actor_id="creator",
                    details=json.dumps(creation_details),
                    created_at=datetime(2020, 1, 1),
                ),
                QCDefectHistory(
                    id="HA",
                    defect_id="D",
                    action="manual_review_approved",
                    actor_id="manager",
                    details=json.dumps(
                        {
                            "from_status": "pending",
                            "to_status": "approved",
                            "reviewer": "manager",
                        }
                    ),
                    created_at=datetime(2020, 1, 2),
                ),
            ]
        )

    def batch(self, session, defects):
        histories = list(
            session.scalars(
                select(QCDefectHistory).where(QCDefectHistory.action == "manual_create")
            )
        )
        return {
            "histories": {"D": histories},
            "records": {
                "TR": {
                    **identity,
                    "task_id": "T",
                    "record_id": "TR",
                    "department": "内科",
                }
            },
            "runs": {
                ("T", 1): {
                    "job_id": "J",
                    "run_scope": "assigned",
                    "triggered_by": "creator",
                }
            },
            "jobs": {
                "J": {
                    "created_by": "creator",
                    "filters_json": json.dumps(
                        {
                            "task_id": "T",
                            "task_run_number": 1,
                            "query_scope": "running",
                            "rule_set_key": source["rule_set_key"],
                            "rule_set_version": "1",
                            "record_refs": [identity],
                        }
                    ),
                }
            },
            "envelopes": {
                ("J", "A", "P", "V", source["rule_set_key"], "1"): [
                    {
                        "id": "E",
                        "record_id": "V",
                        "created_by": "creator",
                        "envelope_json": json.dumps(
                            {
                                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                                "items": [{"rule_id": "R"}],
                            }
                        ),
                        "result_count": 1,
                    }
                ]
            },
            "tasks": {"T": "合成任务"},
        }

    monkeypatch.setattr(manual_report.ManualQualityReportService, "_batch", batch)
    # 报表来源按同 job 当前唯一 Envelope 派生，审核必须另核对创建事件的显式绑定。
    with sessions() as session:
        defect = session.get(QCDefect, "D")
        data = batch(None, session, [defect])
        assert (
            manual_report._source(
                defect,
                data["histories"]["D"],
                data["records"],
                data["runs"],
                data["jobs"],
                data["envelopes"],
            )[2][-1]
            == "E"
        )
    service.snapshot = _capture_snapshot
    if created_envelope == "E":
        review = submit(service, source)
        with sessions() as session:
            snapshot = session.get(QCRecordReview, review["id"]).defect_snapshot
            assert snapshot["manual"] == {
                "count": 1,
                "items": [
                    {
                        "defect_id": "D",
                        "created_by": "creator",
                        "creation_history_id": "HC",
                        "approval_history_id": "HA",
                    }
                ],
            }
    else:
        with pytest.raises(RectificationError) as error:
            submit(service, source)
        assert error.value.status == 409
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(QCRecordReview)) == 0
            assert session.get(QCDefect, "D").manual_review_status == "approved"
