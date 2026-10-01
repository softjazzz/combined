"""病历级操作记录时间线服务：来源装配、三坐标隔离、排序截断、失败语义（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview, SysUser
from app.database.models.defect_rectification import DefectRectification, DefectRectificationEvent
from app.services import case_operation_timeline_service as service

T0 = datetime(2026, 9, 1, 8, 0, 0)
CASE = ("hospital-A", "P1", "V1")
OTHER_INSTITUTE = ("hospital-B", "P1", "V1")


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _tables(metadata: sa.MetaData) -> dict[str, sa.Table]:
    """Envelope / job / 任务记录的无 schema 同构表（只含服务读取与约束所需的列）。"""
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("rule_set_key", sa.String(96), nullable=False),
        sa.Column("rule_set_version", sa.String(96), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    jobs = sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filters_json", sa.Text, nullable=False, default="{}"),
        sa.Column("created_by", sa.String(64), nullable=False),
    )
    task_records = sa.Table(
        "qc_task_records", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("record_id", sa.String(100), nullable=False),
        sa.Column("institute_id", sa.String(100)),
        sa.Column("patient_id", sa.String(100)),
        sa.Column("visit_id", sa.String(100)),
        sa.Column("assignee_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_run_number", sa.Integer),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )
    return {"envelopes": envelopes, "jobs": jobs, "task_records": task_records}


def _envelope(env_id, root_job_id, minutes, identity=CASE, result_count=3):
    return {
        "id": env_id, "job_id": f"leaf-{env_id}", "root_job_id": root_job_id,
        "created_by": "env-writer", "record_id": "record-a",
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "rule_set_key": "luxian_0609", "rule_set_version": "v1",
        "envelope_json": "{}", "result_count": result_count,
        "created_at": at(minutes), "updated_at": at(minutes),
    }


def _review(review_id, minutes, identity=CASE, envelope_id="env-1"):
    return {
        "id": review_id, "request_id": f"req-{review_id}",
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "rule_set_key": "luxian_0609", "rule_set_version": "v1",
        "job_id": "job-task", "envelope_id": envelope_id,
        "task_id": "task-1", "task_record_id": "tr-1", "run_number": 2,
        "stage": "initial", "decision": "doubtful", "reason": "合成存疑原因",
        "reviewer_id": "mgr-1", "created_at": at(minutes), "review_context": "task",
    }


def _defect(defect_id, identity=CASE, origin="manual"):
    return {
        "id": defect_id, "record_id": "tr-1", "identity_version": 1,
        "source_key": "task_assigned_qc",
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "rule_name": "合成人工规则", "description": "合成缺陷", "severity": "warning",
        "status": "pending", "origin": origin,
        "manual_review_status": "approved" if origin == "manual" else None,
        "manual_created_by": "qc-1" if origin == "manual" else None,
        "deduct_score": 0.0, "created_at": T0, "updated_at": T0,
    }


def _history(history_id, defect_id, action, actor, minutes, details):
    return {
        "id": history_id, "defect_id": defect_id, "action": action, "actor_id": actor,
        "details": details if isinstance(details, str) else json.dumps(details, ensure_ascii=False),
        "created_at": at(minutes),
    }


def build_env(monkeypatch):
    """建表造数并把服务的会话与表对象替换为 SQLite 内存库；返回 session 工厂与表。"""
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    metadata = sa.MetaData()
    tables = _tables(metadata)
    metadata.create_all(engine)
    rectification_engine = engine.execution_options(schema_translate_map={"qc": None})
    for model in (DefectRectification, DefectRectificationEvent):
        model.__table__.create(rectification_engine)
    for model in (QCDefect, QCDefectHistory, QCRecordReview, SysUser):
        model.__table__.create(engine)
    factory = sessionmaker(bind=rectification_engine, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(tables["jobs"].insert(), [
            {"id": "job-task", "created_by": "qc-1",
             "filters_json": json.dumps({"task_id": "task-1", "task_run_number": "2"})},
            {"id": "job-bad", "created_by": "qc-2", "filters_json": "{不是 JSON"},
        ])
        session.execute(tables["envelopes"].insert(), [
            _envelope("env-1", "job-task", 10),
            _envelope("env-2", "job-bad", 11, result_count=0),
            _envelope("env-other", "job-task", 12, identity=OTHER_INSTITUTE),
        ])
        session.execute(QCRecordReview.__table__.insert(), [
            _review("rv-1", 20), _review("rv-other", 21, identity=OTHER_INSTITUTE),
        ])
        session.execute(QCDefect.__table__.insert(), [
            _defect("md-1"), _defect("md-other", identity=OTHER_INSTITUTE),
            _defect("auto-1", origin="auto"),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            _history("h-create", "md-1", "manual_create", "qc-1", 30, {
                "task_id": "task-1", "task_record_id": "tr-1", "run_number": 2, "job_id": "job-task",
            }),
            _history("h-review", "md-1", "manual_review_approved", "mgr-1", 31, {
                "reason": "核实无误", "reviewer": "mgr-1",
                "from_status": "pending", "to_status": "approved",
            }),
            _history("h-other", "md-other", "manual_create", "qc-1", 32, {"task_id": "task-9"}),
            _history("h-auto", "auto-1", "approve", "mgr-1", 33, {"reason": "自动缺陷审批"}),
        ])
        session.execute(tables["task_records"].insert(), [
            {"id": "tr-1", "task_id": "task-1", "record_id": "record-a",
             "institute_id": CASE[0], "patient_id": CASE[1], "visit_id": CASE[2],
             "assignee_id": "qc-1", "status": "completed", "completed_run_number": 2,
             "started_at": at(5), "completed_at": at(40)},
            {"id": "tr-pending", "task_id": "task-2", "record_id": "record-a",
             "institute_id": CASE[0], "patient_id": CASE[1], "visit_id": CASE[2],
             "assignee_id": "qc-1", "status": "pending", "completed_run_number": None,
             "started_at": None, "completed_at": None},
            {"id": "tr-other", "task_id": "task-1", "record_id": "record-a",
             "institute_id": OTHER_INSTITUTE[0], "patient_id": "P1", "visit_id": "V1",
             "assignee_id": "qc-1", "status": "in_progress", "completed_run_number": None,
             "started_at": at(6), "completed_at": None},
        ])
        session.execute(SysUser.__table__.insert(), [
            {"id": "qc-1", "username": "qc1", "display_name": "合成质控员",
             "role": "qc_staff", "roles_json": '["qc_staff"]', "is_active": True,
             "institute_id": CASE[0],
             "created_at": T0, "updated_at": T0},
            {"id": "mgr-1", "username": "mgr1", "display_name": "合成质控主管",
             "role": "qc_manager", "roles_json": '["qc_manager"]', "is_active": True,
             "institute_id": CASE[0],
             "created_at": T0, "updated_at": T0},
        ])
    monkeypatch.setattr(service, "SessionLocal", factory)
    monkeypatch.setattr(service, "_envelope_table", lambda: tables["envelopes"])
    monkeypatch.setattr(service, "_batch_jobs_table", lambda: tables["jobs"])
    monkeypatch.setattr(service, "_TASK_RECORDS", tables["task_records"])
    return engine, factory, tables


@pytest.fixture
def env(monkeypatch):
    engine, factory, tables = build_env(monkeypatch)
    yield factory, tables
    engine.dispose()


def timeline(identity=CASE, limit=100, actor_id="mgr-1"):
    return service.list_case_operations(
        actor_id=actor_id,
        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2], limit=limit,
    )


def test_all_event_types_with_fields(env):
    data = timeline()
    by_id = {item["id"]: item for item in data["items"]}
    assert data["total"] == 6 and data["limit"] == 100
    assert (data["institute_id"], data["patient_id"], data["visit_id"]) == CASE
    assert [item["id"] for item in data["items"]] == [
        "task_record:tr-1:completed", "defect_history:h-review", "defect_history:h-create",
        "review:rv-1", "envelope:env-2", "envelope:env-1",
    ]
    # started_at 无写入方，不作为事件来源；只有开始时间的任务病历不产生事件。
    assert not any(item["id"].endswith(":started") for item in data["items"])
    assert by_id["envelope:env-1"] == {
        "id": "envelope:env-1", "type": "qc_run_completed", "occurred_at": at(10),
        "actor_id": "qc-1", "actor_name": "合成质控员",
        "summary": {"job_id": "job-task", "rule_set_version": "v1", "result_count": 3,
                    "task_id": "task-1", "task_run_number": 2},
    }
    assert by_id["review:rv-1"]["type"] == "record_review"
    assert by_id["review:rv-1"]["actor_name"] == "合成质控主管"
    assert by_id["review:rv-1"]["summary"] == {
        "review_context": "task", "stage": "initial", "decision": "doubtful",
        "reason": "合成存疑原因", "job_id": "job-task", "task_id": "task-1",
    }
    assert by_id["defect_history:h-create"]["type"] == "manual_defect_created"
    assert by_id["defect_history:h-create"]["summary"] == {
        "defect_id": "md-1", "rule_name": "合成人工规则", "task_id": "task-1", "run_number": 2,
    }
    assert by_id["defect_history:h-review"]["type"] == "manual_defect_reviewed"
    assert by_id["defect_history:h-review"]["actor_id"] == "mgr-1"
    assert by_id["defect_history:h-review"]["summary"] == {
        "defect_id": "md-1", "decision": "approved", "reason": "核实无误",
    }
    assert by_id["task_record:tr-1:completed"]["summary"] == {
        "task_id": "task-1", "task_record_id": "tr-1", "completed_run_number": 2,
    }


def test_bad_filters_json_keeps_event_without_task_fields(env):
    item = {i["id"]: i for i in timeline()["items"]}["envelope:env-2"]
    assert item["actor_id"] == "qc-2" and item["actor_name"] is None
    assert item["summary"] == {"job_id": "job-bad", "rule_set_version": "v1", "result_count": 0}


def add_rectification(factory, *, task_id="rect-old", identity=CASE, job="old-job", envelope="old-envelope"):
    with factory.begin() as session:
        session.add(DefectRectification(
            id=task_id, institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
            scene="final", target_kind="canonical_defect", target_id="rule-001",
            root_job_id=job, envelope_id=envelope, rule_set_key="luxian_0609",
            rule_set_version="frozen-v1", department="合成科室", creator_id="mgr-1",
            assignee_id="doctor-1", assignee_name="合成医生", requirement="合成要求",
            status="approved", version=5, created_at=at(45), updated_at=at(49),
        ))
        for version, (action, old, new) in enumerate([
            ("assign", None, "pending"), ("urge", "pending", "pending"),
            ("submit", "pending", "submitted"), ("reject", "submitted", "rejected"),
            ("approve", "submitted", "approved"),
        ], 1):
            session.add(DefectRectificationEvent(
                id=f"{task_id}-{version}", rectification_id=task_id, action=action,
                actor_id="mgr-1", old_status=old, new_status=new, version=version,
                comment=f"合成{action}", recipient_id="doctor-1", created_at=at(44 + version),
            ))


def test_rectification_history_keeps_frozen_round_and_event_snapshots(env):
    factory, _ = env
    add_rectification(factory)
    add_rectification(factory, task_id="rect-new", job="new-job", envelope="new-envelope")
    add_rectification(factory, task_id="rect-other", identity=OTHER_INSTITUTE)
    data = timeline()
    events = [event for event in data["items"] if event["id"].startswith("rectification_event:")]
    assert len(events) == 10 and data["total"] == 16
    assert {event["type"] for event in events} == {
        "rectification_assigned", "rectification_urged", "rectification_submitted",
        "rectification_rejected", "rectification_approved",
    }
    old = {event["type"]: event for event in events if event["summary"]["rectification_id"] == "rect-old"}
    for event in old.values():
        assert event["summary"]["root_job_id"] == "old-job"
        assert event["summary"]["envelope_id"] == "old-envelope"
        assert event["summary"]["rule_set_version"] == "frozen-v1"
        assert event["summary"]["scene"] == "final"
        assert event["actor_name"] == "合成质控主管"
    assert old["rectification_assigned"]["summary"]["new_status"] == "pending"
    assert old["rectification_urged"]["summary"]["new_status"] == "pending"
    assert old["rectification_urged"]["summary"]["version"] == 2
    limited = timeline(limit=2)
    assert len(limited["items"]) == 2 and limited["total"] == 16
    with factory() as session:
        assert session.get(DefectRectification, "rect-old").status == "approved"
        assert session.get(DefectRectification, "rect-old").version == 5


@pytest.mark.parametrize("changes", [
    {"is_active": False}, {"institute_id": "hospital-B"}, {"institute_id": None},
    {"roles_json": '["doctor"]'}, {"roles_json": "broken"},
])
def test_persistent_account_scope_fails_closed(env, changes):
    factory, _ = env
    with factory.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "mgr-1").values(**changes))
    with pytest.raises(service.CaseOperationTimelineForbidden):
        timeline()


def test_unknown_persistent_account_fails_closed(env):
    with pytest.raises(service.CaseOperationTimelineForbidden):
        timeline(actor_id="missing-user")


def test_withdraw_urge_history_keeps_original_reference(env):
    factory, _ = env
    add_rectification(factory)
    with factory.begin() as session:
        session.add(DefectRectificationEvent(
            id="withdraw-old", rectification_id="rect-old", action="withdraw_urge", actor_id="mgr-1",
            old_status="pending", new_status="pending", version=6, comment="合成撤回提醒",
            recipient_id="doctor-1", related_event_id="rect-old-2", created_at=at(60),
        ))
    event = timeline()["items"][0]
    assert event["type"] == "rectification_urge_withdrawn"
    assert event["summary"]["related_event_id"] == "rect-old-2"
    assert event["summary"]["root_job_id"] == "old-job"
    assert event["summary"]["new_status"] == "pending"


def test_same_visit_other_institute_is_isolated(env):
    factory, _ = env
    with factory.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "mgr-1").values(
            role="admin", roles_json='["admin"]',
        ))
    data = timeline(OTHER_INSTITUTE)
    assert sorted(item["id"] for item in data["items"]) == [
        "defect_history:h-other", "envelope:env-other", "review:rv-other",
    ]
    assert data["total"] == 3
    assert all("env-1" not in item["id"] for item in data["items"])


def test_auto_defect_history_excluded(env):
    ids = {item["id"] for item in timeline()["items"]}
    assert "defect_history:h-auto" not in ids
    assert not any(item.get("summary", {}).get("defect_id") == "auto-1" for item in timeline()["items"])


def test_same_time_ordered_by_id_stably(env):
    factory, tables = env
    with factory.begin() as session:
        session.execute(tables["envelopes"].insert(), [
            _envelope("env-z", "job-task", 50), _envelope("env-a", "job-task", 50),
        ])
        session.execute(QCRecordReview.__table__.insert(), [_review("rv-m", 50, envelope_id="env-z")])
    first = [item["id"] for item in timeline()["items"]][:3]
    second = [item["id"] for item in timeline()["items"]][:3]
    assert first == second == ["review:rv-m", "envelope:env-z", "envelope:env-a"]


def test_limit_truncates_and_total_is_exact(env):
    data = timeline(limit=2)
    assert data["total"] == 6 and data["limit"] == 2
    assert [item["id"] for item in data["items"]] == [
        "task_record:tr-1:completed", "defect_history:h-review",
    ]


def test_missing_display_name_is_null(env):
    factory, _ = env
    with factory.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "mgr-1").values(display_name=""))
    item = {i["id"]: i for i in timeline()["items"]}["review:rv-1"]
    assert item["actor_id"] == "mgr-1" and item["actor_name"] is None


def test_display_names_loaded_in_one_query(env):
    factory, _ = env
    statements: list[str] = []
    engine = factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute",
                    lambda conn, cursor, stmt, *a: statements.append(stmt))
    timeline()
    assert sum("sys_users" in stmt for stmt in statements) == 2
    # 各来源各一次查询（Envelope 与 job 分两次批量），加一次显示名。
    assert len(statements) == 8


@pytest.mark.parametrize("identity", [
    ("", "P1", "V1"), (" hospital-A", "P1", "V1"), ("hospital-A", "P1 ", "V1"),
    ("hospital-A", "P1", "x" * 129), ("hospital-A", None, "V1"),
])
def test_invalid_identity_rejected(env, identity):
    with pytest.raises(service.CaseOperationTimelineInvalid):
        timeline(identity)


@pytest.mark.parametrize("limit", [0, 201, "10", True])
def test_invalid_limit_rejected(env, limit):
    with pytest.raises(service.CaseOperationTimelineInvalid):
        timeline(limit=limit)


@pytest.mark.parametrize("source", ["envelopes", "jobs", "reviews", "defects", "task_records", "users", "rectifications"])
def test_any_source_failure_makes_whole_timeline_unavailable(env, monkeypatch, source):
    factory, tables = env
    engine = factory.kw["bind"]
    markers = {
        "envelopes": "luxian_0609_record_result_envelopes", "jobs": "custom_qc_batch_jobs",
        "reviews": "qc_record_reviews", "defects": "qc_defect_history",
        "task_records": "qc_task_records", "users": "sys_users",
        "rectifications": "qc_defect_rectification_events",
    }

    def fail(conn, cursor, statement, *args):
        if markers[source] in statement:
            raise OperationalError("SELECT secret FROM somewhere", {}, Exception("boom"))

    sa.event.listen(engine, "before_cursor_execute", fail)
    with pytest.raises(service.CaseOperationTimelineUnavailable):
        timeline()


def test_job_table_lazy_load_failure_is_unavailable(env, monkeypatch):
    def broken():
        raise RuntimeError("DATABASE_URL is not configured")

    monkeypatch.setattr(service, "_batch_jobs_table", broken)
    with pytest.raises(service.CaseOperationTimelineUnavailable):
        timeline()


def test_missing_session_factory_is_unavailable(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.CaseOperationTimelineUnavailable):
        timeline()


def test_review_decision_mapped_from_action_and_cross_checked(env):
    factory, _ = env
    with factory.begin() as session:
        session.execute(QCDefectHistory.__table__.insert(), [
            _history("h-rej", "md-1", "manual_review_rejected", "mgr-1", 60, {
                "reason": "证据不足", "to_status": "rejected",
            }),
            _history("h-mismatch", "md-1", "manual_review_approved", "mgr-1", 61, {
                "reason": "不一致样例", "to_status": "rejected",
            }),
            _history("h-baddetail", "md-1", "manual_review_rejected", "mgr-1", 62, "{坏 JSON"),
        ])
    by_id = {item["id"]: item for item in timeline()["items"]}
    assert by_id["defect_history:h-rej"]["summary"] == {
        "defect_id": "md-1", "decision": "rejected", "reason": "证据不足",
    }
    # to_status 与 action 不一致：省略 decision，不输出原始 action 字符串。
    assert by_id["defect_history:h-mismatch"]["summary"] == {
        "defect_id": "md-1", "reason": "不一致样例",
    }
    assert by_id["defect_history:h-baddetail"]["summary"] == {
        "defect_id": "md-1", "decision": "rejected", "reason": None,
    }
    decisions = {
        item["summary"].get("decision") for item in by_id.values()
        if item["type"] == "manual_defect_reviewed"
    }
    assert decisions <= {"approved", "rejected", None}
