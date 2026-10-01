"""人工缺陷审核服务：仅限任务受领人工缺陷、行锁 CAS、同事务历史（SQLite 合成数据）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory
from app.services import manual_defect_review_service as service

BASE_TIME = datetime(2026, 9, 1, 8, 0, 0)


def _defect(defect_id: str, *, minutes: int, created_by: str = "qc-1",
            review: str | None = "pending", origin: str | None = "manual",
            source_key: str | None = "task_assigned_qc", identity_version: int | None = 1,
            **extra):
    row = {
        "id": defect_id, "record_id": "record-a", "identity_version": identity_version,
        "source_key": source_key, "institute_id": "hospital-A", "patient_id": "patient",
        "visit_id": "visit", "rule_code": "R-1", "rule_name": "合成规则",
        "description": "合成缺陷说明", "severity": "warning", "location": "病程记录",
        "suggestion": "合成整改建议", "evidence": "合成证据", "category": "manual",
        "status": "pending", "origin": origin, "scene": None,
        "manual_review_status": review,
        "manual_created_by": created_by if origin == "manual" else None,
        "deduct_score": 0.0,
        "created_at": BASE_TIME + timedelta(minutes=minutes),
        "updated_at": BASE_TIME + timedelta(minutes=minutes),
    }
    row.update(extra)
    return row


def _create_history(defect_id: str, *, actor: str = "qc-1", run_number: int = 1,
                    task_record_id: str = "record-a"):
    return {
        "id": f"h-{defect_id}", "defect_id": defect_id, "action": "manual_create",
        "actor_id": actor,
        "details": json.dumps({"task_id": "task-1", "task_record_id": task_record_id,
                               "run_number": run_number, "job_id": "job-1"}),
        "created_at": BASE_TIME,
    }


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCDefect.__table__.create(engine)
    QCDefectHistory.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            _defect("m-1", minutes=1),
            _defect("m-2", minutes=2, scene="final"),
            _defect("m-3", minutes=3, scene="outpatient_emergency"),
            # 同一 created_at，按 id 倒序稳定
            _defect("m-4a", minutes=4),
            _defect("m-4b", minutes=4),
            _defect("m-approved", minutes=5, review="approved"),
            _defect("m-rejected", minutes=6, review="rejected"),
            _defect("m-self", minutes=7, created_by="qc-9"),
            _defect("m-nohist", minutes=8),
            # 以下不在合同范围内，一律 404 / 不计数
            _defect("auto-1", minutes=9, origin="auto", review=None),
            _defect("legacy-manual", minutes=10, source_key=None, identity_version=None),
            _defect("other-source", minutes=11, source_key="other"),
            _defect("old-version", minutes=12, identity_version=2),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            _create_history("m-1"),
            _create_history("m-2", run_number=2, task_record_id="record-b"),
            _create_history("m-3"),
            _create_history("m-4a"),
            _create_history("m-4b"),
            _create_history("m-approved"),
            _create_history("m-rejected"),
            _create_history("m-self", actor="qc-9"),
        ])
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _state(factory, defect_id):
    with factory() as session:
        row = session.execute(sa.select(
            QCDefect.manual_review_status, QCDefect.status, QCDefect.approved_by,
            QCDefect.approved_at, QCDefect.rejected_by, QCDefect.reject_reason,
            QCDefect.deduct_score,
        ).where(QCDefect.id == defect_id)).one()
        history = session.execute(sa.select(
            QCDefectHistory.action, QCDefectHistory.actor_id, QCDefectHistory.details,
        ).where(
            QCDefectHistory.defect_id == defect_id,
            QCDefectHistory.action != "manual_create",
        )).all()
    return row, history


def test_case_pages_reach_rows_after_default_limit(sessions):
    with sessions.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            _defect(f"page-{index:03}", minutes=index + 20, scene="running")
            for index in range(205)
        ])
    params = dict(institute_id="hospital-A", patient_id="patient", visit_id="visit", scene="running")
    first = service.list_case_manual_defects(**params)
    second = service.list_case_manual_defects(**params, offset=200)
    assert first["total"] == second["total"] == 205
    assert len(first["items"]) == 200 and len(second["items"]) == 5
    assert second["offset"] == 200 and second["limit"] == 200
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}
    assert second["items"][-1]["id"] == "page-000"


@pytest.mark.parametrize("offset,limit", [(-1, 200), (True, 200), (0, 0), (0, 201), (0, False)])
def test_case_page_rejects_invalid_bounds(sessions, offset, limit):
    with pytest.raises(service.ManualDefectReviewInvalid):
        service.list_case_manual_defects(institute_id="hospital-A", patient_id="patient", visit_id="visit", offset=offset, limit=limit)


def test_report_batch_uses_full_identity_and_manual_scope(sessions, monkeypatch):
    with sessions.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            _defect("other-hospital", minutes=20, institute_id="hospital-B"),
            _defect("other-patient", minutes=21, patient_id="other"),
        ])
    monkeypatch.setattr(service, "_CASE_BATCH_CHUNK", 1)
    items = service.list_manual_defects_for_cases([
        ("hospital-A", "patient", "visit"),
        ("hospital-A", "patient", "visit"),
        ("hospital-X", "patient", "visit"),
    ])
    assert len(items) == 9
    assert {row["identity"] for row in items} == {("hospital-A", "patient", "visit")}
    assert {row["review_status"] for row in items} == {"pending", "approved", "rejected"}
    assert all({"identity", "id", "rule_code", "review_status"} <= set(row) for row in items)


def test_report_batch_filters_same_identity_by_frozen_scene(sessions):
    with sessions.begin() as session:
        session.execute(
            QCDefect.__table__.update().where(QCDefect.id == "m-1").values(scene="running")
        )
    identity = [("hospital-A", "patient", "visit")]
    assert {row["id"] for row in service.list_manual_defects_for_cases(identity, scene="running")} == {"m-1"}
    assert {row["id"] for row in service.list_manual_defects_for_cases(identity, scene="final")} == {"m-2"}


def test_report_batch_empty_does_not_open_session(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    assert service.list_manual_defects_for_cases([]) == []
    with pytest.raises(service.ManualDefectReviewInvalid):
        service.list_manual_defects_for_cases([("hospital-A", " patient", "visit")])


def test_approve_updates_only_review_status_and_appends_history(sessions):
    result = service.review_manual_defect(
        defect_id="m-1", reviewer_id="mgr-1", decision="approved",
        reason="  核实无误 ", expected_status="pending",
    )
    assert result["manual_review_status"] == "approved"
    assert result["previous_status"] == "pending"
    assert result["reason"] == "核实无误"
    row, history = _state(sessions, "m-1")
    assert row == ("approved", "pending", None, None, None, None, 0.0)
    assert len(history) == 1
    action, actor, details = history[0]
    assert (action, actor) == ("manual_review_approved", "mgr-1")
    assert json.loads(details) == {
        "reason": "核实无误", "reviewer": "mgr-1",
        "from_status": "pending", "to_status": "approved",
    }
    # 其他缺陷不受影响
    assert _state(sessions, "m-3")[0][0] == "pending"


def test_reject_requires_non_blank_reason(sessions):
    for reason in (None, "", "   "):
        with pytest.raises(service.ManualDefectReviewInvalid):
            service.review_manual_defect(
                defect_id="m-1", reviewer_id="mgr-1", decision="rejected",
                reason=reason, expected_status="pending",
            )
    assert _state(sessions, "m-1") == (
        ("pending", "pending", None, None, None, None, 0.0), [],
    )
    service.review_manual_defect(
        defect_id="m-1", reviewer_id="mgr-1", decision="rejected",
        reason="证据不足", expected_status="pending",
    )
    row, history = _state(sessions, "m-1")
    assert row[0] == "rejected" and row[4] is None and row[5] is None
    assert history[0][0] == "manual_review_rejected"
    assert json.loads(history[0][2])["reason"] == "证据不足"


def test_invalid_decision_and_expected_status(sessions):
    with pytest.raises(service.ManualDefectReviewInvalid):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="pending", expected_status="pending")
    with pytest.raises(service.ManualDefectReviewInvalid):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="approved", expected_status="approved")
    with pytest.raises(service.ManualDefectReviewInvalid):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="approved", reason="x" * 2001)


def test_self_review_forbidden(sessions):
    with pytest.raises(service.ManualDefectReviewForbidden):
        service.review_manual_defect(defect_id="m-self", reviewer_id="qc-9",
                                     decision="approved", expected_status="pending")
    assert _state(sessions, "m-self") == (
        ("pending", "pending", None, None, None, None, 0.0), [],
    )


@pytest.mark.parametrize("defect_id", [
    "auto-1", "legacy-manual", "other-source", "old-version", "missing", "",
])
def test_out_of_scope_rows_are_not_found(sessions, defect_id):
    with pytest.raises(service.ManualDefectReviewNotFound):
        service.review_manual_defect(defect_id=defect_id, reviewer_id="mgr-1",
                                     decision="approved", expected_status="pending")


def test_second_review_conflicts_not_pending(sessions):
    service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                 decision="approved", expected_status="pending")
    with pytest.raises(service.ManualDefectReviewConflict) as excinfo:
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-2",
                                     decision="rejected", reason="再审",
                                     expected_status="pending")
    assert excinfo.value.code == "not_pending"
    row, history = _state(sessions, "m-1")
    assert row[0] == "approved" and len(history) == 1


def test_cas_zero_rows_conflicts(sessions, monkeypatch):
    """行锁读到 pending 后条件更新零命中（并发抢先）→ 409 且不写历史。"""
    real_execute = sa.orm.Session.execute

    def racing_execute(self, statement, *args, **kwargs):
        if getattr(statement, "is_update", False) and getattr(statement, "is_dml", False):
            real_execute(self, QCDefect.__table__.update().where(
                QCDefect.__table__.c.id == "m-1").values(manual_review_status="approved"))
        return real_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(sa.orm.Session, "execute", racing_execute)
    with pytest.raises(service.ManualDefectReviewConflict):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="rejected", reason="x",
                                     expected_status="pending")
    monkeypatch.undo()
    # 整笔回滚：抢先写入也在同一事务中，一并回滚
    assert _state(sessions, "m-1") == (
        ("pending", "pending", None, None, None, None, 0.0), [],
    )


def test_history_failure_rolls_back_status_via_monkeypatch(sessions, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("history insert failed")

    monkeypatch.setattr(service, "_append_review_history", boom)
    with pytest.raises(RuntimeError):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="approved", expected_status="pending")
    assert _state(sessions, "m-1") == (
        ("pending", "pending", None, None, None, None, 0.0), [],
    )


def test_history_db_failure_rolls_back_and_is_unavailable(sessions):
    with sessions.begin() as session:
        session.execute(sa.text(
            "CREATE TRIGGER block_review_history BEFORE INSERT ON qc_defect_history "
            "WHEN NEW.action LIKE 'manual_review_%' "
            "BEGIN SELECT RAISE(ABORT, 'secret sql detail'); END"
        ))
    with pytest.raises(service.ManualDefectReviewUnavailable) as excinfo:
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="approved", expected_status="pending")
    assert "secret" not in str(excinfo.value)
    assert _state(sessions, "m-1") == (
        ("pending", "pending", None, None, None, None, 0.0), [],
    )


def test_list_filters_scope_orders_and_reads_task_identity(sessions):
    data = service.list_manual_defects(review_status="pending", page=1, page_size=100)
    ids = [item["id"] for item in data["items"]]
    assert ids == ["m-nohist", "m-self", "m-4b", "m-4a", "m-3", "m-2", "m-1"]
    assert data["total"] == 7
    assert data["scene"] == "all"
    by_id = {item["id"]: item for item in data["items"]}
    assert (by_id["m-2"]["task_id"], by_id["m-2"]["task_record_id"],
            by_id["m-2"]["run_number"]) == ("task-1", "record-b", 2)
    assert (by_id["m-nohist"]["task_id"], by_id["m-nohist"]["run_number"]) == (None, None)
    assert set(by_id["m-1"]) == {
        "id", "institute_id", "patient_id", "visit_id", "task_id", "task_record_id",
        "run_number", "rule_code", "rule_name", "description", "severity", "location",
        "suggestion", "manual_review_status", "manual_created_by", "created_at",
    }
    assert [i["id"] for i in service.list_manual_defects(review_status="approved")["items"]] == [
        "m-approved"]
    rejected = service.list_manual_defects(review_status="rejected")
    assert rejected["total"] == 1 and rejected["items"][0]["id"] == "m-rejected"


def test_list_history_is_batched_in_one_query(sessions):
    statements = []

    @sa.event.listens_for(sessions.kw["bind"], "before_cursor_execute")
    def capture(conn, cursor, statement, *args):
        statements.append(statement)

    service.list_manual_defects(review_status="pending", page=1, page_size=100)
    sa.event.remove(sessions.kw["bind"], "before_cursor_execute", capture)
    assert sum("qc_defect_history" in s for s in statements) == 1
    assert len(statements) == 3


def test_list_pagination_boundaries(sessions):
    page1 = service.list_manual_defects(review_status="pending", page=1, page_size=3)
    page3 = service.list_manual_defects(review_status="pending", page=3, page_size=3)
    beyond = service.list_manual_defects(review_status="pending", page=4, page_size=3)
    assert [i["id"] for i in page1["items"]] == ["m-nohist", "m-self", "m-4b"]
    assert [i["id"] for i in page3["items"]] == ["m-1"]
    assert beyond["items"] == [] and beyond["total"] == 7
    for kwargs in ({"page": 0}, {"page_size": 0}, {"page_size": 101},
                   {"review_status": "all"}, {"page": True}):
        with pytest.raises(service.ManualDefectReviewInvalid):
            service.list_manual_defects(**kwargs)


def test_count_pending_matches_list_total(sessions):
    assert service.count_pending_manual_defects() == 7
    service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                 decision="approved", expected_status="pending")
    count = service.count_pending_manual_defects()
    assert count == 6
    assert count == service.list_manual_defects(review_status="pending")["total"]


@pytest.mark.parametrize(
    ("scene", "expected_ids"),
    [
        ("running", ["m-1"]),
        ("final", ["m-2"]),
        ("outpatient_emergency", ["m-3"]),
    ],
)
def test_list_and_count_filter_exact_scene(sessions, scene, expected_ids):
    # 给一条明确 running；未标注的历史行仍只应进入 all。
    with sessions.begin() as session:
        session.execute(
            QCDefect.__table__.update().where(QCDefect.id == "m-1").values(scene="running")
        )
    data = service.list_manual_defects(scene=scene, page_size=100)
    assert data["scene"] == scene
    assert [item["id"] for item in data["items"]] == expected_ids
    assert data["total"] == service.count_pending_manual_defects(scene=scene) == 1
    all_data = service.list_manual_defects(scene="all", page_size=100)
    assert all_data["total"] == 7
    assert "m-nohist" in {item["id"] for item in all_data["items"]}


@pytest.mark.parametrize("scene", ["", "outpatient", "RUNNING", None])
def test_bad_scene_is_rejected_before_opening_session(monkeypatch, scene):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.ManualDefectReviewInvalid, match="场景"):
        service.list_manual_defects(scene=scene)
    with pytest.raises(service.ManualDefectReviewInvalid, match="场景"):
        service.count_pending_manual_defects(scene=scene)


def test_database_errors_are_unavailable(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool)  # 空库：无表
    monkeypatch.setattr(service, "SessionLocal", sessionmaker(bind=engine))
    with pytest.raises(service.ManualDefectReviewUnavailable):
        service.list_manual_defects()
    with pytest.raises(service.ManualDefectReviewUnavailable):
        service.count_pending_manual_defects()
    with pytest.raises(service.ManualDefectReviewUnavailable):
        service.review_manual_defect(defect_id="m-1", reviewer_id="mgr-1",
                                     decision="approved", expected_status="pending")
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.ManualDefectReviewUnavailable):
        service.count_pending_manual_defects()
