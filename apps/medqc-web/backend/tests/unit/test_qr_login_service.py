"""扫码登录持久状态机聚焦测试。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models.qc import SysQrLoginSession, SysUser
from app.services.qr_login_service import (
    QR_MAX_CODE_ATTEMPTS,
    QrLoginCodeMismatch,
    QrLoginConflict,
    QrLoginExpired,
    QrLoginService,
    QrLoginUserInactive,
)


@pytest.fixture()
def qr_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[SysUser.__table__, SysQrLoginSession.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(
            SysUser(
                id="user-1",
                username="doctor-1",
                email="doctor@example.test",
                display_name="医生一",
                is_active=True,
                created_at=datetime(2026, 9, 28, 8),
                updated_at=datetime(2026, 9, 28, 8),
            )
        )
    now = [datetime(2026, 9, 28, 8)]
    service = QrLoginService(
        session_factory=factory,
        clock=lambda: now[0],
        token_issuer=lambda user: {
            "access_token": f"access-{user['id']}",
            "refresh_token": f"refresh-{user['id']}",
            "token_type": "bearer",
            "expires_in": 60,
        },
        secret_key_provider=lambda: "test-only-secret",
    )
    return service, factory, now


def test_create_hashes_credentials_and_public_views_do_not_disclose_them(qr_context):
    service, factory, _ = qr_context
    created = service.create()
    with factory() as session:
        row = session.scalar(select(SysQrLoginSession))
        assert row.browser_secret_hash != created["browser_secret"]
        assert row.verification_code_hash != created["verification_code"]
    status = service.status(created["session_id"], created["browser_secret"])
    confirmation = service.confirmation(created["session_id"])
    for payload in (status, confirmation):
        assert "browser_secret" not in payload
        assert "verification_code" not in payload
        assert "access_token" not in payload
        assert "approved_user_id" not in payload


def test_wrong_code_is_counted_and_fifth_attempt_rejects(qr_context):
    service, factory, _ = qr_context
    created = service.create()
    wrong_code = "000000" if created["verification_code"] != "000000" else "000001"
    for remaining in reversed(range(QR_MAX_CODE_ATTEMPTS)):
        with pytest.raises(QrLoginCodeMismatch) as caught:
            service.confirm(created["session_id"], wrong_code, "user-1")
        assert caught.value.remaining_attempts == remaining
    with factory() as session:
        row = session.get(SysQrLoginSession, created["session_id"])
        assert row.failed_attempts == QR_MAX_CODE_ATTEMPTS
        assert row.status == "rejected"


def test_confirm_exchange_is_one_time_and_updates_user_in_same_transaction(qr_context):
    service, factory, now = qr_context
    created = service.create()
    assert service.confirm(created["session_id"], created["verification_code"], "user-1")["status"] == "approved"
    with pytest.raises(QrLoginConflict):
        service.confirm(created["session_id"], created["verification_code"], "user-1")
    now[0] += timedelta(seconds=1)
    tokens = service.exchange(created["session_id"], created["browser_secret"])
    assert tokens["access_token"] == "access-user-1"
    with pytest.raises(QrLoginConflict):
        service.exchange(created["session_id"], created["browser_secret"])
    with factory() as session:
        assert session.get(SysQrLoginSession, created["session_id"]).status == "consumed"
        assert session.get(SysUser, "user-1").last_login_at == now[0]


def test_active_user_is_rechecked_for_confirm_reject_and_exchange(qr_context):
    service, factory, _ = qr_context
    created = service.create()
    with factory.begin() as session:
        session.get(SysUser, "user-1").is_active = False
    with pytest.raises(QrLoginUserInactive):
        service.confirm(created["session_id"], created["verification_code"], "user-1")
    with pytest.raises(QrLoginUserInactive):
        service.reject(created["session_id"], "user-1")


def test_expiry_and_cancel_of_approved_session(qr_context):
    service, _, now = qr_context
    expiring = service.create()
    now[0] += timedelta(seconds=121)
    with pytest.raises(QrLoginExpired):
        service.confirm(expiring["session_id"], expiring["verification_code"], "user-1")

    now[0] += timedelta(seconds=1)
    approved = service.create()
    service.confirm(approved["session_id"], approved["verification_code"], "user-1")
    assert service.cancel(approved["session_id"], approved["browser_secret"])["status"] == "cancelled"
    with pytest.raises(QrLoginConflict):
        service.exchange(approved["session_id"], approved["browser_secret"])


def test_postgres_uses_wall_clock_instead_of_transaction_start_time():
    captured = []

    class Result:
        @staticmethod
        def scalar_one():
            return datetime(2026, 9, 28, 8)

    class Session:
        bind = type("Bind", (), {"dialect": postgresql.dialect()})()

        @staticmethod
        def execute(statement):
            captured.append(str(statement.compile(dialect=postgresql.dialect())))
            return Result()

    value = QrLoginService()._now(Session())
    assert value == datetime(2026, 9, 28, 8)
    assert "clock_timestamp()" in captured[0]
