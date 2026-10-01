"""整改分析合成 owner 与内存库；不访问真实业务库。"""

import csv
import io
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models.defect_rectification import DefectRectification as Task
from app.database.models.defect_rectification import DefectRectificationEvent as Event
from app.database.models.qc import QCAppeal
from app.services import record_remediation_report_service as report
from app.services.record_quality_report_service import CaseRow, ReportContext


def history(actions):
    return [
        SimpleNamespace(
            id=f"event{version}",
            version=version,
            action=action,
            new_status=state,
            related_event_id=related,
        )
        for version, (action, state, related) in enumerate(actions, 1)
    ]


def test_approved_uses_effective_urge_at_submission_not_current_query_time():
    events = history(
        [
            ("assign", "pending", None),
            ("urge", "pending", None),
            ("submit", "submitted", None),
            ("approve", "approved", None),
            ("withdraw_urge", "approved", "event2"),
        ]
    )
    task = SimpleNamespace(version=5, status="approved")
    assert report.classify_rectification(task, events) == (
        ["urged_rectified"],
        "approved",
        "event3",
        ["event2"],
    )
    # 提交前已撤回提醒，不应因历史曾催办而归到催办已整改。
    events = history(
        [
            ("assign", "pending", None),
            ("urge", "pending", None),
            ("withdraw_urge", "pending", "event2"),
            ("submit", "submitted", None),
            ("approve", "approved", None),
        ]
    )
    assert report.classify_rectification(task, events) == (
        ["self_rectified"],
        "approved",
        "event4",
        [],
    )


def test_resubmission_clears_previous_submit_reminders_and_freezes_latest_submit():
    events = history(
        [
            ("assign", "pending", None),
            ("urge", "pending", None),
            ("submit", "submitted", None),
            ("reject", "rejected", None),
            ("submit", "submitted", None),
            ("approve", "approved", None),
        ]
    )
    assert report.classify_rectification(
        SimpleNamespace(version=6, status="approved"), events
    ) == (["self_rectified"], "approved", "event5", [])


def test_submitted_is_waiting_acceptance_and_missing_task_never_means_pending():
    events = history(
        [
            ("assign", "pending", None),
            ("urge", "pending", None),
            ("submit", "submitted", None),
        ]
    )
    assert report.classify_rectification(
        SimpleNamespace(version=3, status="submitted"), events
    ) == ([], "pending_acceptance", "event3", ["event2"])
    assert report.classify_rectification(None, []) == ([], "not_dispatched", None, [])
    assert (
        report.classify_rectification(
            SimpleNamespace(version=3, status="approved"), events[:1]
        )[1]
        == "history_unknown"
    )


@pytest.fixture
def setup():
    engine = create_engine("sqlite://").execution_options(
        schema_translate_map={"qc": None}
    )
    for model in (Task, Event, QCAppeal):
        model.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield engine, sessions
    engine.dispose()


def context(scene="running", source="all", count=1):
    identities = [("H", f"P{i}", "V") for i in range(count)]
    rows = [
        CaseRow(
            identity=identity,
            patient_name="=合成姓名",
            department="内科",
            doctor="甲医生",
            completed_at="2026-10-01",
            auto_defect_rule_ids=["R1", "R2"],
            rule_statuses={"R1": "non_compliant", "R2": "non_compliant"},
        )
        for identity in identities
    ]
    return ReportContext(
        scene=scene,
        scope={"scene": scene, "defect_source": source},
        rows=rows,
        record_total=count,
        unavailable_total=0,
        standard=None,
        score_status="no_standard",
        review_status="available",
        manual_status="available",
        rule_meta={},
        department_record_totals={},
        doctor_record_totals={},
        saved_results={
            identity: {"root_job_id": "J", "envelope_id": "E"}
            for identity in identities
        },
    )


def task_and_history(sessions, identity=("H", "P0", "V"), scene="running", **changes):
    now = datetime(2026, 10, 1)
    data = (
        dict(zip(report.SOURCE_KEYS[:3], identity))
        | {
            "id": identity[1],
            "scene": scene,
            "target_kind": "canonical_defect",
            "target_id": "R1",
            "root_job_id": "J",
            "envelope_id": "E",
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "v1",
            "department": "内科",
            "creator_id": "manager",
            "assignee_id": "doctor",
            "assignee_name": "合成医生",
            "requirement": "合成要求",
            "status": "pending",
            "version": 2,
            "created_at": now,
            "updated_at": now,
        }
        | changes
    )
    with sessions.begin() as session:
        session.add(Task(**data))
        session.flush()
        for version, action in ((1, "assign"), (2, "urge")):
            session.add(
                Event(
                    id=f"{data['id']}-{version}",
                    rectification_id=data["id"],
                    action=action,
                    actor_id="manager",
                    old_status=None if version == 1 else "pending",
                    new_status="pending",
                    version=version,
                    comment="合成提醒",
                    recipient_id="doctor",
                    created_at=now,
                )
            )


def analysis(ctx, sessions, **options):
    return report.build_analysis(
        ctx,
        actor_id="manager",
        sessions=sessions,
        person_loader=lambda session, actor: {
            "roles": {"qc_manager"},
            "institute_id": "H",
        },
        jobs_loader=lambda session, targets: {
            "J": {"scene": ctx.scene, "scope": ctx.scene, "filters_json": "{}"}
        },
        manual_loader=lambda session, identities, scene: [],
        **options,
    )


@pytest.mark.parametrize("scene", ["running", "final"])
def test_frozen_target_overlap_summary_page_and_csv_are_same_set(setup, scene):
    _, sessions = setup
    ctx = context(scene)
    task_and_history(sessions, scene=scene)
    with sessions.begin() as session:
        session.add(
            QCAppeal(
                id="appeal1",
                appeal_type="defect",
                reason="合成申诉",
                appellant_id="doctor",
                appellant_name="合成医生",
                status="pending",
                target_kind="canonical_defect",
                target_id="R1",
                institute_id="H",
                patient_id="P0",
                visit_id="V",
                scene=scene,
                root_job_id="J",
                envelope_id="E",
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version="v1",
                case_department="内科",
            )
        )
    result = analysis(ctx, sessions)
    assert result["contract_status"] == "assumed_unconfirmed"
    labels = {row["key"]: row["defect_total"] for row in result["labels"]}
    assert labels["clinical_appeal"] == labels["urged_pending"] == 1
    assert labels["not_urged_pending"] == 0
    assert result["state_counts"]["not_dispatched"] == 1
    page = report.page(result, label="clinical_appeal")
    assert page["total"] == 1 and page["items"][0]["target_id"] == "R1"
    assert (
        page["items"][0]["current_urge_ids"] == ["P0-2"]
        and page["items"][0]["submission_urge_ids"] == []
    )
    exported = report.export_csv(result, label="clinical_appeal")
    assert exported.startswith(b"\xef\xbb\xbf")
    csv_rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
    assert (
        len(csv_rows) == 1 and csv_rows[0]["target_id"] == page["items"][0]["target_id"]
    )
    assert csv_rows[0]["patient_name"].startswith("'=")
    assert "待确认" in csv_rows[0]["统计口径"]


@pytest.mark.parametrize(
    "changes",
    [
        {"root_job_id": "old"},
        {"envelope_id": "old"},
        {"scene": "final"},
        {"target_id": "other"},
        {"patient_id": "other"},
    ],
)
def test_old_round_or_other_target_never_attaches(setup, changes):
    _, sessions = setup
    task_and_history(sessions, **changes)
    result = analysis(context(), sessions)
    assert sum(row["defect_total"] for row in result["labels"]) == 0
    assert result["state_counts"]["not_dispatched"] == 2


def test_missing_frozen_reference_is_unknown_and_owner_failure_propagates(setup):
    _, sessions = setup
    task_and_history(sessions)
    ctx = context()
    ctx.saved_results[("H", "P0", "V")] = {}
    result = analysis(ctx, sessions)
    assert result["state_counts"]["source_unknown"] == 2
    assert sum(row["defect_total"] for row in result["labels"]) == 0
    with pytest.raises(RuntimeError, match="source fault"):
        report.build_analysis(
            context(),
            actor_id="manager",
            sessions=sessions,
            person_loader=lambda session, actor: {
                "roles": {"qc_manager"},
                "institute_id": "H",
            },
            jobs_loader=lambda session, targets: (_ for _ in ()).throw(
                RuntimeError("source fault")
            ),
            manual_loader=lambda session, identities, scene: [],
        )


@pytest.mark.parametrize("count", [1, 20])
def test_owner_and_history_queries_do_not_grow_per_defect(setup, count):
    engine, sessions = setup
    ctx = context(count=count)
    for identity in (row.identity for row in ctx.rows):
        task_and_history(sessions, identity)
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = analysis(ctx, sessions)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(result["rows"]) == count * 2
    assert len(statements) == 3
    assert (
        sum("qc_defect_rectification_events" in statement for statement in statements)
        == 1
    )
