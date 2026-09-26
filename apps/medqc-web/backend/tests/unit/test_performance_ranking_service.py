"""工作表现排名服务：统计窗口、病历/缺陷口径、竞争排名、显示名与场景（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview, SysUser
from app.services import performance_ranking_service as service

SHANGHAI = service.HOSPITAL_TIMEZONE
# 2026-09-27 为周日；医院时区当前时刻 2026-09-27 10:00（UTC 02:00）。
NOW = datetime(2026, 9, 27, 10, 0, tzinfo=SHANGHAI)
# 本周一 00:00（+08:00）= 2026-09-21 00:00 → 库内 UTC 2026-09-20 16:00。
THIS_MONDAY_UTC = datetime(2026, 9, 20, 16, 0)


def utc(delta_minutes: int) -> datetime:
    """相对本周一 0 点（库内 UTC）的偏移分钟。"""
    return THIS_MONDAY_UTC + timedelta(minutes=delta_minutes)


# ---------- 窗口 ----------

def test_this_week_window_converts_to_naive_utc():
    window = service.compute_window("this_week", NOW)
    assert window.label == "本周"
    assert window.local_start.isoformat() == "2026-09-21T00:00:00+08:00"
    assert window.local_end.isoformat() == "2026-09-27T10:00:00+08:00"
    assert window.utc_start == THIS_MONDAY_UTC and window.utc_start.tzinfo is None
    assert window.utc_end == datetime(2026, 9, 27, 2, 0)


def test_last_week_excludes_this_week():
    window = service.compute_window("last_week", NOW)
    assert window.label == "上周"
    assert window.local_start.isoformat() == "2026-09-14T00:00:00+08:00"
    assert window.local_end.isoformat() == "2026-09-21T00:00:00+08:00"
    assert window.utc_start == datetime(2026, 9, 13, 16, 0)
    assert window.utc_end == THIS_MONDAY_UTC


def test_this_month_window():
    window = service.compute_window("this_month", NOW)
    assert window.label == "本月"
    assert window.local_start.isoformat() == "2026-09-01T00:00:00+08:00"
    assert window.utc_start == datetime(2026, 8, 31, 16, 0)


def test_monday_boundary_uses_hospital_date_not_utc_date():
    # UTC 周日 16:30 已是医院本地周一 00:30：本周从本地当天 0 点开始。
    now = datetime(2026, 9, 20, 16, 30, tzinfo=timezone.utc)
    window = service.compute_window("this_week", now)
    assert window.local_start.isoformat() == "2026-09-21T00:00:00+08:00"
    assert window.utc_start == THIS_MONDAY_UTC
    # UTC 周日 15:59 仍是本地周日 23:59：本周一为上一周一。
    earlier = service.compute_window("this_week", datetime(2026, 9, 20, 15, 59, tzinfo=timezone.utc))
    assert earlier.local_start.isoformat() == "2026-09-14T00:00:00+08:00"
    last = service.compute_window("last_week", now)
    assert last.utc_end == THIS_MONDAY_UTC


@pytest.mark.parametrize("period", ["", "recent_7_days", "THIS_WEEK", None])
def test_invalid_period_rejected(period):
    with pytest.raises(service.PerformanceRankingInvalid):
        service.compute_window(period, NOW)


def test_naive_now_rejected():
    with pytest.raises(service.PerformanceRankingInvalid):
        service.compute_window("this_week", datetime(2026, 9, 27, 10, 0))


# ---------- 合成数据 ----------

def _review(review_id, reviewer, minutes, *, stage="initial", context="task"):
    task = context == "task"
    return {
        "id": review_id, "request_id": f"req-{review_id}",
        "institute_id": "hospital-A", "patient_id": "P1", "visit_id": f"V-{review_id}",
        "rule_set_key": "luxian_0609", "rule_set_version": "v1",
        "job_id": "job-1", "envelope_id": f"env-{review_id}",
        "task_id": "task-1" if task else None,
        "task_record_id": "tr-1" if task else None,
        "run_number": 1 if task else None,
        "stage": stage, "decision": "approved", "reason": None,
        "reviewer_id": reviewer, "created_at": utc(minutes), "review_context": context,
    }


def _defect(defect_id, creator, *, review_status="pending", origin="manual"):
    manual = origin == "manual"
    return {
        "id": defect_id, "record_id": "tr-1", "identity_version": 1,
        "source_key": "task_assigned_qc",
        "institute_id": "hospital-A", "patient_id": "P1", "visit_id": "V1",
        "rule_name": "合成人工规则", "description": "合成缺陷", "severity": "warning",
        "status": "pending", "origin": origin,
        "manual_review_status": review_status if manual else None,
        # 自动缺陷也填创建人，用以证明是人工缺陷谓词（而非空创建人）把它排除。
        "manual_created_by": creator,
        "deduct_score": 0.0, "created_at": utc(0), "updated_at": utc(0),
    }


def _create(history_id, defect_id, actor, minutes):
    return {
        "id": history_id, "defect_id": defect_id, "action": "manual_create", "actor_id": actor,
        "details": json.dumps({"task_id": "task-1"}), "created_at": utc(minutes),
    }


def build_env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for model in (QCDefect, QCDefectHistory, QCRecordReview, SysUser):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            # u-b：本周 3 条（任务初审、病历列表复审、周一 0 点整边界）
            _review("r1", "u-b", 60),
            _review("r2", "u-b", 120, stage="recheck", context="workspace"),
            _review("r3", "u-b", 0),
            # u-a：本周 3 条，与 u-b 并列，按 user_id 升序排在前
            _review("r4", "u-a", 30), _review("r5", "u-a", 31, context="workspace"),
            _review("r6", "u-a", 32, stage="recheck"),
            # u-c：本周 1 条；上周 2 条（周一 0 点前 1 分钟属于上周）
            _review("r7", "u-c", 10),
            _review("r8", "u-c", -1), _review("r9", "u-c", -60 * 24 * 3),
            # 上上周：不属于上周
            _review("r10", "u-c", -60 * 24 * 7 - 1),
        ])
        session.execute(QCDefect.__table__.insert(), [
            _defect("d1", "qc-1", review_status="approved"),
            _defect("d2", "qc-1", review_status="rejected"),
            _defect("d3", "qc-1"),
            _defect("d4", "qc-2", review_status="approved"),
            _defect("d-old", "qc-2", review_status="rejected"),
            _defect("auto-1", "qc-9", origin="auto"),
            _defect("d-dup", "qc-3"),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            _create("h1", "d1", "qc-1", 5), _create("h2", "d2", "qc-1", 6),
            _create("h3", "d3", "qc-1", 7), _create("h4", "d4", "qc-2", 8),
            _create("h-old", "d-old", "qc-2", -5),
            # 自动缺陷即使有同名动作历史也不计入
            _create("h-auto", "auto-1", "qc-9", 9),
            # 同一缺陷两条 manual_create：只按最早一条计一次
            _create("h-dup-1", "d-dup", "qc-3", 10), _create("h-dup-2", "d-dup", "qc-3", 11),
        ])
        session.execute(SysUser.__table__.insert(), [
            {"id": "u-a", "username": "ua", "display_name": "合成质控员甲",
             "created_at": utc(0), "updated_at": utc(0)},
            {"id": "qc-1", "username": "qc1", "display_name": "合成缺陷员",
             "created_at": utc(0), "updated_at": utc(0)},
        ])
    monkeypatch.setattr(service, "SessionLocal", factory)
    return engine, factory


@pytest.fixture
def env(monkeypatch):
    engine, factory = build_env(monkeypatch)
    yield factory
    engine.dispose()


def ranking(period="this_week", scene="all"):
    return service.get_performance_ranking(period=period, scene=scene, now=NOW)


# ---------- 病历排名 ----------

def test_record_ranking_competition_and_stable_order(env):
    data = ranking()
    assert data["unavailable_reason"] is None
    assert data["range"] == {
        "start": "2026-09-21T00:00:00+08:00", "end": "2026-09-27T10:00:00+08:00",
    }
    assert data["record_ranking"] == [
        {"user_id": "u-a", "name": "合成质控员甲", "count": 3,
         "initial_count": 2, "recheck_count": 1, "rank": 1},
        {"user_id": "u-b", "name": None, "count": 3,
         "initial_count": 2, "recheck_count": 1, "rank": 1},
        {"user_id": "u-c", "name": None, "count": 1,
         "initial_count": 1, "recheck_count": 0, "rank": 3},
    ]


def test_record_ranking_counts_both_review_contexts(env):
    by_user = {row["user_id"]: row for row in ranking()["record_ranking"]}
    # u-b 的复审来自病历列表（workspace）上下文，u-a 的一条初审也是 workspace。
    assert by_user["u-b"]["recheck_count"] == 1
    assert by_user["u-a"]["count"] == 3


def test_last_week_excludes_this_week_rows(env):
    data = ranking("last_week")
    assert data["period_label"] == "上周"
    assert data["record_ranking"] == [
        {"user_id": "u-c", "name": None, "count": 2,
         "initial_count": 2, "recheck_count": 0, "rank": 1},
    ]
    assert data["defect_ranking"] == [
        {"user_id": "qc-2", "name": None, "count": 1,
         "approved_count": 0, "rejected_count": 1, "rank": 1},
    ]


def test_top_ten_limit(env):
    with env.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            _review(f"bulk-{i}", f"z-{i:02d}", 200 + i) for i in range(12)
        ])
    rows = ranking()["record_ranking"]
    assert len(rows) == service.RANKING_LIMIT
    assert [r["user_id"] for r in rows[3:]] == [f"z-{i:02d}" for i in range(7)]
    assert all(r["rank"] == 3 for r in rows[2:])


# ---------- 缺陷排名 ----------

def test_defect_ranking_counts_manual_only_with_review_split(env):
    assert ranking()["defect_ranking"] == [
        {"user_id": "qc-1", "name": "合成缺陷员", "count": 3,
         "approved_count": 1, "rejected_count": 1, "rank": 1},
        {"user_id": "qc-2", "name": None, "count": 1,
         "approved_count": 1, "rejected_count": 0, "rank": 2},
        {"user_id": "qc-3", "name": None, "count": 1,
         "approved_count": 0, "rejected_count": 0, "rank": 2},
    ]


def test_auto_defect_not_counted(env):
    users = {row["user_id"] for row in ranking()["defect_ranking"]}
    assert "qc-9" not in users and None not in users


def test_empty_window_returns_empty_lists(env):
    data = service.get_performance_ranking(
        period="this_week", scene="all", now=datetime(2027, 1, 6, tzinfo=SHANGHAI),
    )
    assert data["defect_ranking"] == [] and data["record_ranking"] == []
    assert data["unavailable_reason"] is None


# ---------- 场景与失败 ----------

@pytest.mark.parametrize("scene", ["outpatient_emergency", "running", "final"])
def test_non_all_scene_returns_null_without_db(monkeypatch, scene):
    monkeypatch.setattr(service, "SessionLocal", None)
    data = ranking(scene=scene)
    assert data["defect_ranking"] is None and data["record_ranking"] is None
    assert data["unavailable_reason"] == "scene_not_attributable"
    assert data["scene"] == scene and data["period"] == "this_week"


def test_invalid_period_rejected_before_db(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.PerformanceRankingInvalid):
        ranking(period="recent")


def test_missing_session_factory_is_unavailable(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.PerformanceRankingUnavailable):
        ranking()


def test_query_failure_is_unavailable(env, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OperationalError("SELECT secret FROM somewhere", {}, Exception("boom"))

    monkeypatch.setattr(service, "_record_ranking", boom)
    with pytest.raises(service.PerformanceRankingUnavailable):
        ranking()
