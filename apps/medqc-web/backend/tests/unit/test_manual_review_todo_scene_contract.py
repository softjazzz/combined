"""人工缺陷待审核列表与计数的场景一致性合同。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory
from app.services import manual_defect_review_service as service


BASE_TIME = datetime(2026, 9, 28, 8)


def _defect(
    key: str,
    *,
    scene: str | None,
    institute: str = "hospital-a",
    review_status: str = "pending",
    minutes: int = 0,
) -> dict:
    return {
        "id": key,
        "record_id": f"record-{key}",
        "identity_version": 1,
        "source_key": "task_assigned_qc",
        "institute_id": institute,
        "patient_id": "same-patient",
        "visit_id": "same-visit",
        "rule_code": "RULE-1",
        "rule_name": "合成规则",
        "description": "合成人工缺陷",
        "severity": "warning",
        "location": "病程记录",
        "suggestion": "请核实",
        "status": "pending",
        "origin": "manual",
        "manual_review_status": review_status,
        "manual_created_by": "creator-1",
        "scene": scene,
        "deduct_score": 0,
        "created_at": BASE_TIME + timedelta(minutes=minutes),
        "updated_at": BASE_TIME + timedelta(minutes=minutes),
    }


def _history(defect_id: str) -> dict:
    return {
        "id": f"history-{defect_id}",
        "defect_id": defect_id,
        "action": "manual_create",
        "actor_id": "creator-1",
        "details": json.dumps({
            "task_id": "task-1",
            "task_record_id": f"task-record-{defect_id}",
            "run_number": 1,
        }),
        "created_at": BASE_TIME,
    }


@pytest.fixture
def database(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCDefect.__table__.create(engine)
    QCDefectHistory.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    pending = [
        _defect("running-a", scene="running", minutes=1),
        _defect(
            "running-b", scene="running", institute="hospital-b", minutes=2,
        ),
        _defect("final", scene="final", minutes=3),
        _defect("outpatient", scene="outpatient_emergency", minutes=4),
        _defect("historic-null", scene=None, minutes=5),
    ]
    with factory.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            *pending,
            _defect(
                "running-approved",
                scene="running",
                review_status="approved",
                minutes=6,
            ),
        ])
        session.execute(
            QCDefectHistory.__table__.insert(),
            [_history(row["id"]) for row in pending],
        )
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.mark.parametrize(
    ("scene", "expected_ids"),
    [
        (
            "all",
            {"running-a", "running-b", "final", "outpatient", "historic-null"},
        ),
        ("running", {"running-a", "running-b"}),
        ("final", {"final"}),
        ("outpatient_emergency", {"outpatient"}),
    ],
)
def test_pending_list_and_count_share_the_exact_scene_scope(
    database, scene, expected_ids,
):
    result = service.list_manual_defects(
        review_status="pending",
        page=1,
        page_size=100,
        scene=scene,
    )
    listed_ids = {item["id"] for item in result["items"]}
    count = service.count_pending_manual_defects(scene=scene)

    assert result["scene"] == scene
    assert listed_ids == expected_ids
    assert result["total"] == count == len(expected_ids)


def test_running_pagination_keeps_total_and_full_identity(database):
    first = service.list_manual_defects(
        review_status="pending", page=1, page_size=1, scene="running",
    )
    second = service.list_manual_defects(
        review_status="pending", page=2, page_size=1, scene="running",
    )
    beyond = service.list_manual_defects(
        review_status="pending", page=3, page_size=1, scene="running",
    )

    assert first["total"] == second["total"] == beyond["total"] == 2
    assert first["scene"] == second["scene"] == beyond["scene"] == "running"
    rows = [*first["items"], *second["items"]]
    assert {row["id"] for row in rows} == {"running-a", "running-b"}
    assert {
        (row["institute_id"], row["patient_id"], row["visit_id"])
        for row in rows
    } == {
        ("hospital-a", "same-patient", "same-visit"),
        ("hospital-b", "same-patient", "same-visit"),
    }
    assert beyond["items"] == []


@pytest.mark.parametrize("scene", ["", "outpatient", "RUNNING", None])
def test_invalid_scene_is_rejected_by_list_and_count_before_reading(
    database, monkeypatch, scene,
):
    monkeypatch.setattr(
        service,
        "SessionLocal",
        lambda: pytest.fail("无效场景不应打开数据库会话"),
    )
    with pytest.raises(service.ManualDefectReviewInvalid, match="场景"):
        service.list_manual_defects(scene=scene)
    with pytest.raises(service.ManualDefectReviewInvalid, match="场景"):
        service.count_pending_manual_defects(scene=scene)
