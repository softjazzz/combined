"""单任务分析精确计数、对象权限与未知值合同。"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCTask, QCTaskRecord
from app.services import task_analysis_service as service


def _environment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory


def _task(task_id="task-1", creator_id="creator"):
    return QCTask(
        id=task_id,
        task_number=f"NO-{task_id}",
        task_name="任务分析样本",
        task_type="one_time",
        scene="running",
        status="in_progress",
        progress=0,
        total_records=0,
        completed_records=0,
        creator_id=creator_id,
        creator_name="创建人",
    )


def _record(index: int, **overrides):
    values = {
        "id": f"record-{index}",
        "task_id": "task-1",
        "record_id": f"record-{index}",
        "assignee_id": "staff-1",
        "assignee_name": "质控员甲",
        "status": "pending",
        "score": None,
        "defect_count": None,
    }
    values.update(overrides)
    return QCTaskRecord(**values)


def test_creator_gets_exact_single_snapshot_aggregation_with_unknowns():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add(_task())
        session.add_all([
            _record(1, status="completed", score=90, defect_count=2),
            _record(2, status="in_progress", assignee_id="staff-2", assignee_name="质控员乙"),
            _record(3, status="skipped", assignee_id=None, assignee_name=None, score=0, defect_count=0),
            _record(4, status="legacy_state", assignee_id="staff-1", assignee_name="旧姓名", score=80, defect_count=1),
        ])

    result = service.get_task_analysis(
        task_id="task-1", actor_id="creator", is_manager=False, session_factory=factory,
    )

    assert result["contract_version"] == "task-analysis-v1"
    assert result["summary"] == {
        "total_records": 4,
        "completed_records": 1,
        "completion_rate": 25.0,
        "average_score": None,
        "score_known_count": 3,
        "score_unknown_count": 1,
        "total_defect_count": None,
        "defect_known_count": 3,
        "defect_unknown_count": 1,
    }
    assert result["status_counts"] == {
        "pending": 0, "in_progress": 1, "completed": 1, "skipped": 1, "unknown": 1,
    }
    assert sum(row["total_records"] for row in result["assignees"]) == 4
    staff_one = next(row for row in result["assignees"] if row["assignee_id"] == "staff-1")
    assert staff_one == {
        "assignee_id": "staff-1", "assignee_name": None,
        "total_records": 2, "completed_records": 1, "completion_rate": 50.0,
    }
    assert any(row["assignee_id"] is None for row in result["assignees"])


def test_all_known_values_produce_whole_task_metrics_and_empty_task_stays_unknown():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add_all([_task(), _task("empty")])
        session.add_all([
            _record(1, status="completed", score=80, defect_count=0),
            _record(2, status="completed", score=90, defect_count=3),
        ])

    full = service.get_task_analysis(
        task_id="task-1", actor_id="manager", is_manager=True, session_factory=factory,
    )
    assert full["summary"]["average_score"] == 85.0
    assert full["summary"]["total_defect_count"] == 3
    assert full["summary"]["completion_rate"] == 100.0

    empty = service.get_task_analysis(
        task_id="empty", actor_id="creator", is_manager=False, session_factory=factory,
    )
    assert empty["summary"]["total_records"] == 0
    assert empty["summary"]["completion_rate"] == 0.0
    assert empty["summary"]["average_score"] is None
    assert empty["summary"]["total_defect_count"] is None
    assert empty["assignees"] == []


def test_more_than_postgrest_default_page_is_counted_exactly():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add(_task())
        session.add_all([
            _record(index, status="completed" if index <= 5 else "pending", score=100, defect_count=0)
            for index in range(1, 1206)
        ])

    result = service.get_task_analysis(
        task_id="task-1", actor_id="creator", is_manager=False, session_factory=factory,
    )
    assert result["summary"]["total_records"] == 1205
    assert result["summary"]["completed_records"] == 5
    assert result["status_counts"]["pending"] == 1200


def test_invalid_numeric_values_stay_unknown_and_real_unassigned_key_cannot_collide():
    _engine, factory = _environment()
    with factory.begin() as session:
        session.add(_task())
        session.add_all([
            _record(1, assignee_id=None, assignee_name=None, score=float("inf"), defect_count=-1),
            _record(2, assignee_id="__unassigned__", assignee_name="真实账号", score=-1, defect_count=1),
        ])

    result = service.get_task_analysis(
        task_id="task-1", actor_id="creator", is_manager=False, session_factory=factory,
    )
    assert result["summary"]["score_known_count"] == 0
    assert result["summary"]["score_unknown_count"] == 2
    assert result["summary"]["defect_known_count"] == 1
    assert result["summary"]["defect_unknown_count"] == 1
    assert result["summary"]["total_defect_count"] is None
    assert {row["assignee_id"] for row in result["assignees"]} == {None, "__unassigned__"}


def test_object_permission_is_checked_before_task_record_query():
    engine, factory = _environment()
    with factory.begin() as session:
        session.add(_task())
        session.add(_record(1))
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda _c, _cu, statement, *_args: statements.append(statement))

    try:
        service.get_task_analysis(
            task_id="task-1", actor_id="other", is_manager=False, session_factory=factory,
        )
    except service.TaskAnalysisForbidden:
        pass
    else:
        raise AssertionError("非创建人必须被拒绝")

    assert len(statements) == 1
    assert "qc_task_records" not in statements[0]


def test_missing_task_and_invalid_identity_do_not_fall_back_to_empty_analysis():
    engine, factory = _environment()
    with factory.begin() as session:
        session.add(_task())
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda _c, _cu, statement, *_args: statements.append(statement))

    try:
        service.get_task_analysis(
            task_id="missing", actor_id="creator", is_manager=False, session_factory=factory,
        )
    except service.TaskAnalysisNotFound:
        pass
    else:
        raise AssertionError("不存在任务必须返回未找到")
    assert len(statements) == 1

    statements.clear()
    try:
        service.get_task_analysis(
            task_id="task-1", actor_id=" ", is_manager=True, session_factory=factory,
        )
    except service.TaskAnalysisInvalid:
        pass
    else:
        raise AssertionError("缺少稳定身份必须被拒绝")
    assert statements == []
