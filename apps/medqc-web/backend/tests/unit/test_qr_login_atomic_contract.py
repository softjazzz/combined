"""扫码登录事务回滚与授权身份不可替换合同。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from app.database.models.qc import SysQrLoginSession, SysUser
from app.services.qr_login_service import (
    QrLoginConflict,
    QrLoginNotFound,
    QrLoginService,
    QrLoginUnavailable,
)
from tests.unit.test_qr_login_service import qr_context  # noqa: F401


def _service_with_issuer(factory, now, token_issuer):
    return QrLoginService(
        session_factory=factory,
        clock=lambda: now[0],
        token_issuer=token_issuer,
        secret_key_provider=lambda: "test-only-secret",
    )


def _approve(service: QrLoginService) -> dict:
    created = service.create()
    service.confirm(created["session_id"], created["verification_code"], "user-1")
    return created


def test_token_issuer_failure_does_not_consume_session_or_update_last_login(qr_context):  # noqa: F811
    service, factory, now = qr_context
    created = _approve(service)
    issuer_calls: list[dict] = []

    def failing_issuer(user):
        issuer_calls.append(dict(user))
        raise RuntimeError("synthetic token failure")

    failing_service = _service_with_issuer(factory, now, failing_issuer)
    with pytest.raises(QrLoginUnavailable, match="登录令牌签发失败"):
        failing_service.exchange(created["session_id"], created["browser_secret"])

    assert issuer_calls == [{"id": "user-1", "email": "doctor@example.test"}]
    with factory() as session:
        row = session.get(SysQrLoginSession, created["session_id"])
        user = session.get(SysUser, "user-1")
        assert row.status == "approved"
        assert row.consumed_at is None
        assert user.last_login_at is None


def test_commit_failure_rolls_back_consumed_and_last_login_without_returning_token(qr_context):  # noqa: F811
    service, factory, now = qr_context
    created = _approve(service)
    issued_tokens: list[dict] = []

    def recording_issuer(user):
        payload = {
            "access_token": f"access-{user['id']}",
            "refresh_token": f"refresh-{user['id']}",
            "token_type": "bearer",
            "expires_in": 60,
        }
        issued_tokens.append(payload)
        return payload

    failing_service = _service_with_issuer(factory, now, recording_issuer)

    def fail_before_commit(_session):
        raise SQLAlchemyError("synthetic commit failure")

    event.listen(factory.class_, "before_commit", fail_before_commit, once=True)
    not_returned = object()
    result = not_returned
    try:
        with pytest.raises(QrLoginUnavailable, match="扫码登录兑换失败"):
            result = failing_service.exchange(created["session_id"], created["browser_secret"])
    finally:
        event.remove(factory.class_, "before_commit", fail_before_commit)

    assert result is not_returned
    assert len(issued_tokens) == 1
    with factory() as session:
        row = session.get(SysQrLoginSession, created["session_id"])
        user = session.get(SysUser, "user-1")
        assert row.status == "approved"
        assert row.consumed_at is None
        assert user.last_login_at is None


def test_wrong_browser_secret_cannot_read_cancel_or_exchange(qr_context):  # noqa: F811
    service, factory, _ = qr_context
    created = service.create()
    wrong_secret = created["browser_secret"] + "-wrong"

    with pytest.raises(QrLoginNotFound):
        service.status(created["session_id"], wrong_secret)
    with pytest.raises(QrLoginNotFound):
        service.cancel(created["session_id"], wrong_secret)

    service.confirm(created["session_id"], created["verification_code"], "user-1")
    with pytest.raises(QrLoginNotFound):
        service.exchange(created["session_id"], wrong_secret)

    with factory() as session:
        row = session.get(SysQrLoginSession, created["session_id"])
        user = session.get(SysUser, "user-1")
        assert row.status == "approved"
        assert row.consumed_at is None
        assert user.last_login_at is None


def test_second_user_cannot_replace_approved_user(qr_context):  # noqa: F811
    service, factory, _ = qr_context
    with factory.begin() as session:
        session.add(
            SysUser(
                id="user-2",
                username="doctor-2",
                email="doctor-2@example.test",
                display_name="医生二",
                is_active=True,
                created_at=datetime(2026, 9, 28, 8),
                updated_at=datetime(2026, 9, 28, 8),
            )
        )

    created = _approve(service)
    with factory() as session:
        original = session.scalar(
            select(SysQrLoginSession).where(SysQrLoginSession.id == created["session_id"])
        )
        original_approved_at = original.approved_at

    with pytest.raises(QrLoginConflict):
        service.confirm(created["session_id"], created["verification_code"], "user-2")

    with factory() as session:
        row = session.get(SysQrLoginSession, created["session_id"])
        assert row.status == "approved"
        assert row.approved_user_id == "user-1"
        assert row.approved_at == original_approved_at
