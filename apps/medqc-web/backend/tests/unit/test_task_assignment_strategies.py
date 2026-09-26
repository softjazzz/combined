"""任务分配策略：按原质控员、按科室（合同 2026-09-27 第 2 节），SQLite 隔离库。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRecordReview, QCTask, QCTaskRecord, SysUser
from app.services import task_assignment_service as service


USERS = {
    "qc-1": ("甲", "内科"),
    "qc-2": ("乙", "外科"),
    "qc-3": ("丙", "内科"),
}


def person(user_id):
    return {"user_id": user_id, "user_name": USERS[user_id][0]}


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (QCTask, QCTaskRecord, SysUser, QCRecordReview):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)

    def seed(*, method, departments=("内科", "内科", "外科", "内科"), assignee_config=None,
             status="sampling"):
        with factory.begin() as session:
            session.add_all([
                SysUser(id=user_id, username=user_id, display_name=name, department=department,
                        role="qc_staff", is_active=True)
                for user_id, (name, department) in USERS.items()
            ])
            session.add(QCTask(
                id="task-1", task_number="QC-1", task_name="策略任务", task_type="one_time",
                scene="running", status=status, creator_id="owner", total_records=len(departments),
                assign_method=method,
                assignee_config=json.dumps(assignee_config) if assignee_config is not None else None,
            ))
            for index, department in enumerate(departments):
                session.add(QCTaskRecord(
                    id=f"row-{index}", task_id="task-1", record_id=f"row-{index}",
                    institute_id="hospital", patient_id=f"patient-{index}", visit_id=f"visit-{index}",
                    status="pending", department=department,
                    created_at=datetime(2026, 1, 1, 0, 0, index),
                ))

    def review(index, reviewer, *, second, review_id=None, visit=None):
        review_id = review_id or f"rv-{index}-{reviewer}-{second}"
        with factory.begin() as session:
            session.add(QCRecordReview(
                id=review_id, request_id=f"req-{review_id}",
                institute_id="hospital", patient_id=f"patient-{index}", visit_id=visit or f"visit-{index}",
                rule_set_key="rs", rule_set_version="v1", job_id=f"job-{review_id}",
                envelope_id=f"env-{review_id}", stage="initial", decision="approved",
                reviewer_id=reviewer, created_at=datetime(2026, 2, 1, 0, 0, second),
                review_context="workspace",
            ))

    def assignments():
        with factory() as session:
            task = session.execute(select(QCTask.__table__)).mappings().one()
            rows = session.execute(
                select(QCTaskRecord.__table__).order_by(QCTaskRecord.created_at)
            ).mappings().all()
            return task["status"], [row["assignee_id"] for row in rows]

    yield engine, seed, review, assignments
    engine.dispose()


def assign(method, people, fallback=None):
    return service.assign_task_records(
        task_id="task-1", actor_id="owner", assignees=[person(u) for u in people],
        method=method, fallback=fallback,
    )


def reasons(result):
    return {item["user_id"]: item["reason_counts"] for item in result["assignment_details"]}


# ---------------- 按原质控员 ----------------

def test_original_reviewer_hits_and_ratio_fallback(db):
    _, seed, review, assignments = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "by_ratio"})
    review(0, "qc-2", second=1)
    review(2, "qc-1", second=1)
    review(3, "outsider", second=1)  # 不在选定人中 → 走兜底

    result = assign("by_original_reviewer", ["qc-1", "qc-2"], "by_ratio")

    # row-0→乙、row-2→甲 命中；row-1、row-3 兜底按比例：row-1→甲、row-3→乙
    assert assignments() == ("assigned", ["qc-2", "qc-1", "qc-1", "qc-2"])
    assert result["idempotent"] is False
    assert result["total_assigned"] == 4
    assert reasons(result) == {
        "qc-1": {"original_reviewer": 1, "department": 0, "ratio_fallback": 1},
        "qc-2": {"original_reviewer": 1, "department": 0, "ratio_fallback": 1},
    }


def test_original_reviewer_uses_latest_decision(db):
    _, seed, review, assignments = db
    seed(method="by_original_reviewer", departments=("内科",), assignee_config={"fallback": "reject"})
    review(0, "qc-1", second=1)
    review(0, "qc-2", second=5)
    # 同一时间戳按 id 降序取：rv-z 胜出
    review(0, "qc-1", second=9, review_id="rv-a")
    review(0, "qc-2", second=9, review_id="rv-z")

    assign("by_original_reviewer", ["qc-1", "qc-2"], "reject")
    assert assignments() == ("assigned", ["qc-2"])


def test_original_reviewer_matches_full_identity_not_visit_only(db):
    engine, seed, _, _ = db
    seed(method="by_original_reviewer", departments=("内科",), assignee_config={"fallback": "reject"})
    # 同 visit_id 但不同患者的审核不得冒充
    with sessionmaker(bind=engine).begin() as session:
        session.add(QCRecordReview(
            id="rv-x", request_id="req-x", institute_id="hospital", patient_id="other",
            visit_id="visit-0", rule_set_key="rs", rule_set_version="v1", job_id="job-x",
            envelope_id="env-x", stage="initial", decision="approved", reviewer_id="qc-1",
            created_at=datetime(2026, 2, 1), review_context="workspace",
        ))
    with pytest.raises(service.AssignmentConflict) as info:
        assign("by_original_reviewer", ["qc-1"], "reject")
    assert info.value.code == "original_reviewer_unmatched"


def test_original_reviewer_reject_reports_unmatched_count_without_writes(db):
    _, seed, review, assignments = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "reject"})
    review(0, "qc-1", second=1)
    review(1, "qc-3", second=1)  # 原质控员不在选定人中

    with pytest.raises(service.AssignmentConflict) as info:
        assign("by_original_reviewer", ["qc-1", "qc-2"], "reject")
    assert info.value.code == "original_reviewer_unmatched"
    assert info.value.details == {"unmatched_count": 3}
    assert assignments() == ("sampling", [None] * 4)


def test_original_reviewer_batches_review_lookup(db, monkeypatch):
    engine, seed, review, _ = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "by_ratio"})
    monkeypatch.setattr(service, "_REVIEW_LOOKUP_CHUNK", 3)
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        if "qc_record_reviews" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assign("by_original_reviewer", ["qc-1"], "by_ratio")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2  # 4 个 visit_id，块大小 3 → 2 次查询，不逐行


@pytest.mark.parametrize("fallback", [None, "keep"])
def test_original_reviewer_requires_valid_fallback(db, fallback):
    _, seed, _, assignments = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "by_ratio"})
    with pytest.raises(service.AssignmentConflict, match="fallback"):
        assign("by_original_reviewer", ["qc-1"], fallback)
    assert assignments()[0] == "sampling"


def test_original_reviewer_fallback_must_match_creation_config(db):
    _, seed, _, assignments = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "reject"})
    with pytest.raises(service.AssignmentConflict, match="创建配置"):
        assign("by_original_reviewer", ["qc-1"], "by_ratio")
    assert assignments()[0] == "sampling"


def test_fallback_rejected_for_other_methods(db):
    _, seed, _, _ = db
    seed(method="by_ratio")
    with pytest.raises(service.AssignmentConflict, match="fallback"):
        assign("by_ratio", ["qc-1"], "by_ratio")


def test_assigned_same_method_is_idempotent_without_recompute(db):
    _, seed, review, assignments = db
    seed(method="by_original_reviewer", assignee_config={"fallback": "by_ratio"})
    review(0, "qc-2", second=1)
    first = assign("by_original_reviewer", ["qc-1", "qc-2"], "by_ratio")
    before = assignments()
    # 审核数据变化后重放不得重算
    review(1, "qc-2", second=2)
    replay = assign("by_original_reviewer", ["qc-1", "qc-2"], "by_ratio")
    assert assignments() == before
    assert replay["idempotent"] is True
    assert replay["assignment_summary"] == first["assignment_summary"]
    assert [(d["user_id"], d["count"]) for d in replay["assignment_details"]] == [
        (d["user_id"], d["count"]) for d in first["assignment_details"]
    ]
    assert all(d["reason_counts"] is None for d in replay["assignment_details"])


def test_assigned_different_method_conflicts(db):
    _, seed, _, assignments = db
    seed(method="by_department")
    assign("by_department", ["qc-1", "qc-2"])
    with pytest.raises(service.AssignmentConflict, match="分配方式"):
        assign("by_ratio", ["qc-1", "qc-2"])
    with pytest.raises(service.AssignmentConflict, match="分配方式"):
        assign("by_original_reviewer", ["qc-1", "qc-2"], "by_ratio")
    assert assignments()[0] == "assigned"


# ---------------- 按科室 ----------------

def test_department_hits_and_splits_same_department_by_ratio(db):
    _, seed, _, assignments = db
    seed(method="by_department")
    result = assign("by_department", ["qc-1", "qc-2", "qc-3"])
    # 内科 row-0/1/3 由 甲、丙 按比例：甲 2、丙 1；外科 row-2 → 乙
    assert assignments() == ("assigned", ["qc-1", "qc-1", "qc-2", "qc-3"])
    assert result["assignment_summary"] == {"甲": 2, "乙": 1, "丙": 1}
    assert reasons(result) == {
        "qc-1": {"original_reviewer": 0, "department": 2, "ratio_fallback": 0},
        "qc-2": {"original_reviewer": 0, "department": 1, "ratio_fallback": 0},
        "qc-3": {"original_reviewer": 0, "department": 1, "ratio_fallback": 0},
    }
    replay = assign("by_department", ["qc-1", "qc-2", "qc-3"])
    assert replay["idempotent"] is True
    assert reasons(replay)["qc-1"] == {"original_reviewer": 0, "department": 2, "ratio_fallback": 0}


@pytest.mark.parametrize("missing", [None, "  "])
def test_department_missing_rejected(db, missing):
    _, seed, _, assignments = db
    seed(method="by_department", departments=("内科", missing, missing))
    with pytest.raises(service.AssignmentConflict) as info:
        assign("by_department", ["qc-1", "qc-2"])
    assert info.value.code == "department_missing"
    assert info.value.details == {"missing_count": 2}
    assert assignments() == ("sampling", [None] * 3)


def test_department_unassigned_lists_departments(db):
    _, seed, _, assignments = db
    seed(method="by_department", departments=("内科", "儿科", "外科", "眼科"))
    with pytest.raises(service.AssignmentConflict) as info:
        assign("by_department", ["qc-1", "qc-2"])
    assert info.value.code == "department_unassigned"
    assert info.value.details == {"departments": ["儿科", "眼科"]}
    assert assignments() == ("sampling", [None] * 4)


def test_department_uses_sys_user_department_not_request(db):
    _, seed, _, _ = db
    seed(method="by_department", departments=("外科",))
    people = [{"user_id": "qc-1", "user_name": "甲", "department": "外科"}]
    with pytest.raises(service.AssignmentConflict) as info:
        service.assign_task_records(task_id="task-1", actor_id="owner", assignees=people, method="by_department")
    assert info.value.code == "department_unassigned"


def test_by_ratio_details_unchanged_without_reason_counts(db):
    _, seed, _, _ = db
    seed(method="by_ratio")
    result = assign("by_ratio", ["qc-1", "qc-2"])
    assert result["assignment_details"] == [
        {"user_id": "qc-1", "user_name": "甲", "count": 2},
        {"user_id": "qc-2", "user_name": "乙", "count": 2},
    ]


# ---------------- 分配接口入参与结构化 409 ----------------

@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import tasks

    calls = []

    def fake_assign(**kwargs):
        calls.append(kwargs)
        if kwargs["method"] == "by_department":
            raise service.AssignmentConflict(
                "以下科室没有对应受领人：儿科", code="department_unassigned", departments=["儿科"],
            )
        return {
            "task_id": "task-1", "total_assigned": 1, "assignment_summary": {"甲": 1},
            "assignment_details": [{
                "user_id": "qc-1", "user_name": "甲", "count": 1,
                "reason_counts": {"original_reviewer": 1, "department": 0, "ratio_fallback": 0},
            }],
            "idempotent": False,
        }

    monkeypatch.setattr(tasks, "assign_task_records", fake_assign)
    monkeypatch.setattr(tasks, "audit_event", lambda *_args, **_kwargs: None)
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[tasks.get_current_user] = lambda: {
        "id": "owner", "roles": ["qc_manager"], "display_name": "质控科",
    }
    with TestClient(app) as test_client:
        yield test_client, calls


def _body(method, **extra):
    return {"assignees": [{"user_id": "qc-1", "user_name": "甲"}], "method": method, **extra}


def test_api_passes_fallback_and_returns_reason_counts(api):
    client, calls = api
    response = client.post("/api/v1/tasks/task-1/assign", json=_body("by_original_reviewer", fallback="by_ratio"))
    assert response.status_code == 200, response.text
    assert calls[-1]["fallback"] == "by_ratio" and calls[-1]["method"] == "by_original_reviewer"
    assert response.json()["data"]["assignment_details"][0]["reason_counts"]["original_reviewer"] == 1


@pytest.mark.parametrize("body", [
    _body("by_original_reviewer"),
    _body("by_original_reviewer", fallback="keep"),
    _body("by_ratio", fallback="by_ratio"),
])
def test_api_rejects_invalid_fallback(api, body):
    client, calls = api
    response = client.post("/api/v1/tasks/task-1/assign", json=body)
    assert response.status_code == 422
    assert calls == []


def test_api_ratio_request_omits_fallback(api):
    client, calls = api
    response = client.post("/api/v1/tasks/task-1/assign", json=_body("by_ratio"))
    assert response.status_code == 200
    assert calls[-1]["fallback"] is None


def test_api_coded_conflict_is_structured_409(api):
    client, _ = api
    response = client.post("/api/v1/tasks/task-1/assign", json=_body("by_department"))
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "department_unassigned", "message": "以下科室没有对应受领人：儿科", "departments": ["儿科"],
    }
