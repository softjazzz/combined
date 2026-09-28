"""缺陷工作量按冻结场景聚合的独立合同测试。

仅使用 SQLite 合成数据，不连接或写入真实数据库。公开排名入口必须由 SQLAlchemy
完成真实的创建历史关联、人工缺陷过滤、场景过滤与窗口聚合。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview
from app.services import performance_ranking_service as service

SHANGHAI = service.HOSPITAL_TIMEZONE
NOW = datetime(2026, 9, 27, 10, 0, tzinfo=SHANGHAI)
THIS_WEEK_START_UTC = datetime(2026, 9, 20, 16, 0)
THIS_WEEK_END_UTC = datetime(2026, 9, 27, 2, 0)


def _defect(
    defect_id: str,
    creator: str,
    *,
    scene: str | None,
    institute_id: str = "hospital-A",
    patient_id: str = "patient-1",
    visit_id: str = "visit-1",
    origin: str = "manual",
    review_status: str = "pending",
    identity_version: int | None = 1,
) -> dict[str, object]:
    manual = origin == "manual"
    return {
        "id": defect_id,
        "record_id": f"record-{defect_id}",
        "identity_version": identity_version,
        "source_key": "task_assigned_qc",
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "rule_name": "合成人工规则",
        "description": "合成缺陷",
        "severity": "warning",
        "status": "pending",
        "origin": origin,
        "manual_review_status": review_status if manual else None,
        # 自动缺陷故意携带创建人，证明人工谓词而非创建人非空条件将其排除。
        "manual_created_by": creator,
        "scene": scene,
        "deduct_score": 0.0,
        "created_at": THIS_WEEK_START_UTC,
        "updated_at": THIS_WEEK_START_UTC,
    }


def _created(
    history_id: str,
    defect_id: str,
    creator: str,
    created_at: datetime,
) -> dict[str, object]:
    return {
        "id": history_id,
        "defect_id": defect_id,
        "action": "manual_create",
        "actor_id": creator,
        "details": json.dumps({"task_id": "synthetic-task"}),
        "created_at": created_at,
    }


@pytest.fixture
def ranking_env(monkeypatch: pytest.MonkeyPatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (QCDefect, QCDefectHistory, QCRecordReview):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    # 本合同只验证排名事实；姓名搬运已由原服务测试覆盖。
    monkeypatch.setattr(service, "_display_names", lambda _session, _ids: {})
    yield factory
    engine.dispose()


def _insert(
    factory,
    defects: list[dict[str, object]],
    histories: list[dict[str, object]],
) -> None:
    with factory.begin() as session:
        session.execute(QCDefect.__table__.insert(), defects)
        session.execute(QCDefectHistory.__table__.insert(), histories)


def _ranking(scene: str = "all") -> list[dict[str, object]]:
    result = service.get_performance_ranking(
        period="this_week",
        scene=scene,
        now=NOW,
    )
    assert result["unavailable_reason"] is None
    assert isinstance(result["defect_ranking"], list)
    return result["defect_ranking"]


def _by_user(scene: str = "all") -> dict[str, dict[str, object]]:
    return {str(row["user_id"]): row for row in _ranking(scene)}


def test_same_reviewer_is_split_by_exact_frozen_scene(ranking_env):
    defects = [
        _defect("mixed-running", "reviewer-mixed", scene="running", review_status="approved"),
        _defect("mixed-final", "reviewer-mixed", scene="final", review_status="rejected"),
        _defect(
            "mixed-outpatient",
            "reviewer-mixed",
            scene="outpatient_emergency",
        ),
    ]
    histories = [
        _created(f"history-{row['id']}", str(row["id"]), "reviewer-mixed", THIS_WEEK_START_UTC)
        for row in defects
    ]
    _insert(ranking_env, defects, histories)

    assert _by_user("running")["reviewer-mixed"]["count"] == 1
    assert _by_user("final")["reviewer-mixed"] == {
        "user_id": "reviewer-mixed",
        "name": None,
        "count": 1,
        "approved_count": 0,
        "rejected_count": 1,
        "rank": 1,
    }
    assert _by_user("outpatient_emergency")["reviewer-mixed"]["count"] == 1
    assert _by_user()["reviewer-mixed"]["count"] == 3


def test_historical_null_scene_only_belongs_to_all(ranking_env):
    defect = _defect("historical-null", "reviewer-history", scene=None)
    _insert(
        ranking_env,
        [defect],
        [
            _created(
                "history-null",
                "historical-null",
                "reviewer-history",
                THIS_WEEK_START_UTC,
            )
        ],
    )

    assert _by_user()["reviewer-history"]["count"] == 1
    for scene in ("running", "final", "outpatient_emergency"):
        assert "reviewer-history" not in _by_user(scene)


def test_automatic_defect_is_excluded_even_with_creator_and_manual_history(ranking_env):
    defect = _defect(
        "automatic-running",
        "reviewer-auto",
        scene="running",
        origin="auto",
    )
    _insert(
        ranking_env,
        [defect],
        [
            _created(
                "history-auto",
                "automatic-running",
                "reviewer-auto",
                THIS_WEEK_START_UTC,
            )
        ],
    )

    assert "reviewer-auto" not in _by_user()
    assert "reviewer-auto" not in _by_user("running")


def test_unverified_identity_is_excluded_from_all_and_scene_rankings(ranking_env):
    defect = _defect(
        "unverified-identity",
        "reviewer-unverified",
        scene="running",
        identity_version=0,
    )
    _insert(
        ranking_env,
        [defect],
        [
            _created(
                "history-unverified",
                "unverified-identity",
                "reviewer-unverified",
                THIS_WEEK_START_UTC,
            )
        ],
    )

    assert "reviewer-unverified" not in _by_user()
    assert "reviewer-unverified" not in _by_user("running")


def test_same_patient_and_visit_in_different_institutes_remain_distinct(ranking_env):
    defects = [
        _defect(
            "cross-institute-a",
            "reviewer-cross",
            scene="running",
            institute_id="hospital-A",
            patient_id="same-patient",
            visit_id="same-visit",
        ),
        _defect(
            "cross-institute-b",
            "reviewer-cross",
            scene="running",
            institute_id="hospital-B",
            patient_id="same-patient",
            visit_id="same-visit",
        ),
    ]
    histories = [
        _created(f"history-{row['id']}", str(row["id"]), "reviewer-cross", THIS_WEEK_START_UTC)
        for row in defects
    ]
    _insert(ranking_env, defects, histories)

    assert _by_user("running")["reviewer-cross"]["count"] == 2


def test_week_window_is_left_closed_and_right_open(ranking_env):
    defects = [
        _defect("at-start", "reviewer-edge", scene="running"),
        _defect("before-start", "reviewer-edge", scene="running"),
        _defect("before-end", "reviewer-edge", scene="running"),
        _defect("at-end", "reviewer-edge", scene="running"),
    ]
    histories = [
        _created("history-at-start", "at-start", "reviewer-edge", THIS_WEEK_START_UTC),
        _created(
            "history-before-start",
            "before-start",
            "reviewer-edge",
            THIS_WEEK_START_UTC - timedelta(microseconds=1),
        ),
        _created(
            "history-before-end",
            "before-end",
            "reviewer-edge",
            THIS_WEEK_END_UTC - timedelta(microseconds=1),
        ),
        _created("history-at-end", "at-end", "reviewer-edge", THIS_WEEK_END_UTC),
    ]
    _insert(ranking_env, defects, histories)

    assert _by_user("running")["reviewer-edge"]["count"] == 2
