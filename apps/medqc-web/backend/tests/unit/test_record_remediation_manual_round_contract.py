"""独立反例：人工缺陷必须保留创建轮次，不借用当前病例结果锚点。"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.defect_rectification import DefectRectification as Task
from app.database.models.defect_rectification import DefectRectificationEvent as Event
from app.database.models.qc import QCAppeal
from app.services import record_remediation_report_service as report
from app.services.record_quality_report_service import CaseRow, ReportContext


IDENTITY = ("synthetic-H", "synthetic-P", "synthetic-V")


def source(job="J2", envelope="E2"):
    return dict(zip(report.SOURCE_KEYS[:3], IDENTITY)) | {
        "scene": "running",
        "target_kind": "task_manual_defect",
        "target_id": "M1",
        "root_job_id": job,
        "envelope_id": envelope,
    }


@pytest.fixture
def env():
    engine = create_engine("sqlite://").execution_options(
        schema_translate_map={"qc": None}
    )
    for owner in (Task, Event, QCAppeal):
        owner.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 10, 1)
    with sessions.begin() as session:
        # 同缺陷在两个不同结果上的owner并存，用不同提醒事实揭示任何跨轮串账。
        for task_id, job, envelope, urged in (
            ("old-owner", "J1", "E1", False),
            ("new-owner", "J2", "E2", True),
        ):
            actions = [("assign", "pending")]
            if urged:
                actions.append(("urge", "pending"))
            actions.extend([("submit", "submitted"), ("approve", "approved")])
            session.add(
                Task(
                    **source(job, envelope),
                    id=task_id,
                    rule_set_key="synthetic",
                    rule_set_version="v1",
                    department="合成科室",
                    creator_id="synthetic-qc",
                    assignee_id="synthetic-doctor",
                    assignee_name="合成医生",
                    requirement="合成要求",
                    status="approved",
                    version=len(actions),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            previous = None
            for version, (action, state) in enumerate(actions, 1):
                session.add(
                    Event(
                        id=f"{task_id}-{action}",
                        rectification_id=task_id,
                        actor_id="synthetic-doctor"
                        if action == "submit"
                        else "synthetic-qc",
                        action=action,
                        version=version,
                        old_status=previous,
                        new_status=state,
                        created_at=now,
                        recipient_id="synthetic-doctor",
                        comment="合成事件",
                    )
                )
                previous = state
    ctx = ReportContext(
        scene="running",
        scope={
            "scene": "running",
            "defect_source": "manual",
            "completed_from": "2026-10-01T00:00:00Z",
        },
        rows=[
            CaseRow(
                identity=IDENTITY,
                patient_name="合成患者",
                department="合成科室",
                doctor="合成医生",
                completed_at="2026-10-01",
                auto_defect_rule_ids=[],
            )
        ],
        record_total=1,
        unavailable_total=0,
        standard=None,
        score_status="no_standard",
        review_status="available",
        manual_status="available",
        rule_meta={},
        department_record_totals={},
        doctor_record_totals={},
        saved_results={IDENTITY: {"root_job_id": "J2", "envelope_id": "E2"}},
    )
    yield sessions, ctx
    engine.dispose()


def analyze(env, frozen):
    sessions, ctx = env
    calls = []

    def manual_loader(session, identities, scene):
        calls.append((session, identities, scene))
        return [
            {
                "identity": IDENTITY,
                "id": "M1",
                "rule_name": "合成人工缺陷",
                "review_status": "approved",
                "source": frozen,
            }
        ]

    result = report.build_analysis(
        ctx,
        actor_id="synthetic-qc",
        sessions=sessions,
        manual_loader=manual_loader,
        jobs_loader=lambda session, targets: {
            job: {"scene": "running", "scope": "running", "filters_json": "{}"}
            for job in ("J1", "J2")
        },
        person_loader=lambda session, actor: {
            "roles": {"qc_manager"},
            "institute_id": IDENTITY[0],
        },
    )
    assert len(calls) == 1 and calls[0][1:] == ([IDENTITY], "running")
    assert result["scope"] == ctx.scope
    return result


def test_old_manual_round_keeps_original_source_and_never_attaches_new_owner(env):
    result = analyze(env, source("J1", "E1"))
    row = result["rows"][0]
    assert (row["root_job_id"], row["envelope_id"]) == ("J1", "E1")
    assert row["rectification_state"] == "source_unknown"
    assert row["source_reason"] == "not_current_round"
    assert (
        row["rectification_id"] is None and row["events"] == [] and row["labels"] == []
    )
    assert result["state_counts"]["not_dispatched"] == 0
    assert result["state_counts"]["source_unknown"] == 1
    assert all(label["defect_total"] == 0 for label in result["labels"])


@pytest.mark.parametrize(
    "frozen",
    [
        None,
        {**source(), "root_job_id": ""},
        {**source(), "envelope_id": ""},
        {**source(), "institute_id": "other-H"},
    ],
)
def test_incomplete_or_cross_institute_manual_source_never_borrows_current_anchor(
    env, frozen
):
    result = analyze(env, frozen)
    row = result["rows"][0]
    assert row["rectification_state"] == "source_unknown" and not row["source_known"]
    assert row["source_reason"] == "manual_source_missing"
    assert row["rectification_id"] is None and row["labels"] == []
    assert result["state_counts"]["not_dispatched"] == 0


def test_same_round_approved_manual_owner_uses_its_submission_reminder(env):
    result = analyze(env, source())
    row = result["rows"][0]
    assert row["source_known"] and row["rectification_state"] == "approved"
    assert row["rectification_id"] == "new-owner"
    assert row["labels"] == ["urged_rectified"]
    assert row["submission_event_id"] == "new-owner-submit"
    assert row["submission_urge_ids"] == ["new-owner-urge"]
    assert row["current_urge_ids"] == []
    assert all(event["id"].startswith("new-owner-") for event in row["events"])
    assert (
        next(
            label["defect_total"]
            for label in result["labels"]
            if label["key"] == "self_rectified"
        )
        == 0
    )
