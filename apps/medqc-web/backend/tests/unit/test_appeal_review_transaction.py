from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

from app.database.models.qc import QCAppeal, QCAppealReview
from app.schemas.appeals import ReviewAction
from app.services import appeal_review_service
from app.services.appeal_review_service import (
    AppealReviewConflict,
    AppealReviewNotFound,
    AppealWithdrawForbidden,
    review_appeal_atomically,
    withdraw_appeal_atomically,
)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCAppeal.__table__.create(engine)
    QCAppealReview.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def _add_appeal(session_factory, *, appeal_id: str = "appeal-1", status: str = "pending") -> None:
    with session_factory() as session:
        session.add(
            QCAppeal(
                id=appeal_id,
                appeal_number=f"AP-{appeal_id}",
                qc_result_id="result-1",
                record_id="record-1",
                appeal_type="defect",
                reason="需要重新核对该质控结果",
                priority="medium",
                appellant_id="user-1",
                appellant_name="申诉人",
                status=status,
            )
        )
        session.commit()


@pytest.mark.parametrize(
    ("action", "expected_status", "expected_resolution"),
    [
        (ReviewAction.APPROVE, "approved", "申诉已批准"),
        (ReviewAction.REJECT, "rejected", "申诉已拒绝"),
        (ReviewAction.REQUEST_INFO, "reviewing", None),
        (ReviewAction.FORWARD, "reviewing", None),
    ],
)
def test_review_updates_appeal_and_history_in_one_commit(
    monkeypatch,
    session_factory,
    action,
    expected_status,
    expected_resolution,
):
    _add_appeal(session_factory)
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)

    result = review_appeal_atomically(
        "appeal-1",
        action=action,
        comment="审核意见",
        resolution=None,
        reviewer_id="reviewer-1",
        reviewer_name="审核人",
        reviewer_role="quality_manager",
    )

    assert result["status"] == expected_status
    assert result["reviewer_id"] == "reviewer-1"
    assert result["reviewer_name"] == "审核人"
    assert result["review_result"] == "审核意见"
    assert result["resolution"] == expected_resolution
    assert isinstance(result["review_date"], datetime)
    assert result["review_date"].tzinfo is not None
    assert result["updated_at"].tzinfo is not None

    with session_factory() as session:
        appeal = session.get(QCAppeal, "appeal-1")
        history = session.execute(select(QCAppealReview)).scalars().all()

    assert appeal is not None
    assert appeal.status == expected_status
    assert len(history) == 1
    assert history[0].action == action.value
    assert history[0].comment == "审核意见"
    assert history[0].reviewer_role == "quality_manager"
    assert history[0].metadata_json == {}


def test_review_metadata_type_matches_postgres_and_sqlite():
    column = QCAppealReview.__table__.c.metadata
    assert "metadata JSONB" in str(
        CreateTable(QCAppealReview.__table__).compile(dialect=postgresql.dialect())
    )
    assert "metadata JSON" in str(
        CreateTable(QCAppealReview.__table__).compile(dialect=sqlite.dialect())
    )
    assert column.name == "metadata"


def test_postgres_appeal_lookup_pins_qc_schema_before_select():
    statements = []
    appeal = object()

    class FakeSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement):
            statements.append(str(statement))
            return SimpleNamespace(scalar_one_or_none=lambda: appeal)

    assert appeal_review_service._lock_appeal(FakeSession(), "appeal-1") is appeal
    assert statements[0] == "SET LOCAL search_path TO qc"
    assert "FOR UPDATE" in statements[1]


def test_reviewing_appeal_can_reach_terminal_status(monkeypatch, session_factory):
    _add_appeal(session_factory, status="reviewing")
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)

    result = review_appeal_atomically(
        "appeal-1",
        action=ReviewAction.APPROVE,
        comment=None,
        resolution="复核通过",
        reviewer_id="reviewer-1",
        reviewer_name="审核人",
        reviewer_role="reviewer",
    )

    assert result["status"] == "approved"
    assert result["resolution"] == "复核通过"


@pytest.mark.parametrize("status", ["approved", "accepted", "rejected", "withdrawn"])
def test_terminal_appeal_cannot_be_reviewed_again(
    monkeypatch,
    session_factory,
    status,
):
    _add_appeal(session_factory, status=status)
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)

    with pytest.raises(AppealReviewConflict):
        review_appeal_atomically(
            "appeal-1",
            action=ReviewAction.REJECT,
            comment="再次审核",
            resolution=None,
            reviewer_id="reviewer-1",
            reviewer_name="审核人",
            reviewer_role="reviewer",
        )

    with session_factory() as session:
        assert session.get(QCAppeal, "appeal-1").status == status
        assert session.scalar(select(QCAppealReview)) is None


def test_missing_appeal_raises_not_found(monkeypatch, session_factory):
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)

    with pytest.raises(AppealReviewNotFound):
        review_appeal_atomically(
            "missing",
            action=ReviewAction.APPROVE,
            comment=None,
            resolution=None,
            reviewer_id="reviewer-1",
            reviewer_name="审核人",
            reviewer_role="reviewer",
        )


def test_history_and_status_are_rolled_back_together(monkeypatch, session_factory):
    _add_appeal(session_factory)

    class FailingAfterFlushSession(Session):
        def flush(self, objects=None):
            super().flush(objects)
            raise RuntimeError("simulated persistence failure")

    failing_factory = sessionmaker(
        bind=session_factory.kw["bind"],
        class_=FailingAfterFlushSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(appeal_review_service, "SessionLocal", failing_factory)

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        review_appeal_atomically(
            "appeal-1",
            action=ReviewAction.APPROVE,
            comment="审核意见",
            resolution=None,
            reviewer_id="reviewer-1",
            reviewer_name="审核人",
            reviewer_role="reviewer",
        )

    with session_factory() as session:
        appeal = session.get(QCAppeal, "appeal-1")
        assert appeal.status == "pending"
        assert session.scalar(select(QCAppealReview)) is None


def test_unavailable_session_factory_raises_clear_error(monkeypatch):
    monkeypatch.setattr(appeal_review_service, "SessionLocal", None)

    with pytest.raises(RuntimeError, match="数据库会话不可用"):
        review_appeal_atomically(
            "appeal-1",
            action=ReviewAction.APPROVE,
            comment=None,
            resolution=None,
            reviewer_id="reviewer-1",
            reviewer_name="审核人",
            reviewer_role="reviewer",
        )


def test_withdraw_only_appellant_and_reviewable_status(monkeypatch, session_factory):
    _add_appeal(session_factory)
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)

    with pytest.raises(AppealWithdrawForbidden):
        withdraw_appeal_atomically("appeal-1", appellant_id="other", reason=None)

    result = withdraw_appeal_atomically(
        "appeal-1", appellant_id="user-1", reason="主动撤回"
    )
    assert result["status"] == "withdrawn"
    assert result["resolution"] == "主动撤回"
    assert result["resolution_date"].tzinfo is not None

    with pytest.raises(AppealReviewConflict):
        review_appeal_atomically(
            "appeal-1",
            action=ReviewAction.APPROVE,
            comment=None,
            resolution=None,
            reviewer_id="reviewer-1",
            reviewer_name="审核人",
            reviewer_role="qc_manager",
        )


def test_reviewed_appeal_cannot_be_withdrawn(monkeypatch, session_factory):
    _add_appeal(session_factory)
    monkeypatch.setattr(appeal_review_service, "SessionLocal", session_factory)
    review_appeal_atomically(
        "appeal-1",
        action=ReviewAction.APPROVE,
        comment=None,
        resolution=None,
        reviewer_id="reviewer-1",
        reviewer_name="审核人",
        reviewer_role="qc_manager",
    )

    with pytest.raises(AppealReviewConflict):
        withdraw_appeal_atomically("appeal-1", appellant_id="user-1", reason=None)

    with session_factory() as session:
        assert session.get(QCAppeal, "appeal-1").status == "approved"
        assert len(session.execute(select(QCAppealReview)).scalars().all()) == 1
