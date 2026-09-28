"""扫码登录一次性会话的持久状态机。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..core.security import issue_login_token_pair
from ..core.settings import get_settings
from ..database import connection
from ..database.models.qc import SysQrLoginSession, SysUser


QR_SESSION_TTL_SECONDS = 120
QR_POLL_INTERVAL_MS = 1500
QR_MAX_CODE_ATTEMPTS = 5
class QrLoginError(RuntimeError):
    pass


class QrLoginNotFound(QrLoginError):
    pass


class QrLoginConflict(QrLoginError):
    pass


class QrLoginExpired(QrLoginConflict):
    pass


class QrLoginCodeMismatch(QrLoginError):
    def __init__(self, remaining_attempts: int):
        self.remaining_attempts = max(0, int(remaining_attempts))
        super().__init__("确认码错误")


class QrLoginUserInactive(QrLoginError):
    pass


class QrLoginUnavailable(QrLoginError):
    pass


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso_utc(value: datetime) -> str:
    return _utc_naive(value).isoformat(timespec="milliseconds") + "Z"


class QrLoginService:
    def __init__(
        self,
        *,
        session_factory: Any = None,
        clock: Callable[[], datetime] | None = None,
        token_issuer: Callable[[Mapping[str, Any]], dict[str, Any]] = issue_login_token_pair,
        secret_key_provider: Callable[[], str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._token_issuer = token_issuer
        self._secret_key_provider = secret_key_provider or (lambda: get_settings().JWT_SECRET)

    def _factory(self):
        factory = self._session_factory or connection.SessionLocal
        if factory is None:
            raise QrLoginUnavailable("扫码登录存储不可用")
        return factory

    def _now(self, session: Any) -> datetime:
        if self._clock is not None:
            return _utc_naive(self._clock())
        dialect = getattr(getattr(session, "bind", None), "dialect", None)
        dialect_name = str(getattr(dialect, "name", "") or "")
        clock_expression = func.clock_timestamp() if dialect_name == "postgresql" else func.current_timestamp()
        value = session.execute(select(clock_expression)).scalar_one()
        if not isinstance(value, datetime):
            raise QrLoginUnavailable("数据库时钟不可用")
        return _utc_naive(value)

    def _digest(self, purpose: str, value: str) -> str:
        key = str(self._secret_key_provider() or "").encode("utf-8")
        if not key:
            raise QrLoginUnavailable("扫码登录密钥不可用")
        return hmac.new(key, f"qr-login:{purpose}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()

    def _locked_session(self, session: Any, session_id: str) -> SysQrLoginSession:
        row = session.execute(
            select(SysQrLoginSession)
            .where(SysQrLoginSession.id == str(session_id or "").strip())
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise QrLoginNotFound("扫码会话不存在")
        return row

    def _assert_browser_secret(self, row: SysQrLoginSession, browser_secret: str) -> None:
        supplied = str(browser_secret or "").strip()
        expected = self._digest("browser-secret", supplied)
        if not supplied or not hmac.compare_digest(str(row.browser_secret_hash), expected):
            raise QrLoginNotFound("扫码会话不存在")

    @staticmethod
    def _expire(row: SysQrLoginSession, now: datetime) -> bool:
        if row.status in {"pending", "approved"} and _utc_naive(row.expires_at) <= now:
            row.status = "expired"
            return True
        return row.status == "expired"

    @staticmethod
    def _status_payload(row: SysQrLoginSession) -> dict[str, Any]:
        return {
            "session_id": row.id,
            "status": row.status,
            "expires_at": _iso_utc(row.expires_at),
        }

    def _active_user(self, session: Any, user_id: str) -> SysUser:
        normalized = str(user_id or "").strip()
        user = session.execute(
            select(SysUser)
            .where(SysUser.id == normalized, SysUser.is_active.is_(True))
            .with_for_update()
        ).scalar_one_or_none()
        if user is None or not str(user.email or "").strip():
            raise QrLoginUserInactive("授权账号不存在或已停用")
        return user

    def create(self) -> dict[str, Any]:
        browser_secret = secrets.token_urlsafe(32)
        verification_code = f"{secrets.randbelow(1_000_000):06d}"
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    now = self._now(session)
                    row = SysQrLoginSession(
                        id=str(uuid4()),
                        browser_secret_hash=self._digest("browser-secret", browser_secret),
                        verification_code_hash=self._digest("verification-code", verification_code),
                        status="pending",
                        failed_attempts=0,
                        created_at=now,
                        expires_at=now + timedelta(seconds=QR_SESSION_TTL_SECONDS),
                    )
                    session.add(row)
                    session.flush()
                    payload = {
                        "session_id": row.id,
                        "browser_secret": browser_secret,
                        "verification_code": verification_code,
                        "expires_at": _iso_utc(row.expires_at),
                        "poll_interval_ms": QR_POLL_INTERVAL_MS,
                    }
            return payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码会话创建失败") from exc

    def status(self, session_id: str, browser_secret: str) -> dict[str, Any]:
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    self._assert_browser_secret(row, browser_secret)
                    self._expire(row, self._now(session))
                    payload = self._status_payload(row)
            return payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码状态读取失败") from exc

    def confirmation(self, session_id: str) -> dict[str, Any]:
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    self._expire(row, self._now(session))
                    payload = self._status_payload(row)
                    payload["remaining_attempts"] = max(
                        0, QR_MAX_CODE_ATTEMPTS - int(row.failed_attempts),
                    )
            return payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码确认状态读取失败") from exc

    def confirm(self, session_id: str, verification_code: str, user_id: str) -> dict[str, Any]:
        mismatch: QrLoginCodeMismatch | None = None
        failure: QrLoginError | None = None
        payload: dict[str, Any] | None = None
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    now = self._now(session)
                    if self._expire(row, now):
                        failure = QrLoginExpired("扫码会话已过期")
                    elif row.status != "pending":
                        failure = QrLoginConflict(f"扫码会话当前状态为 {row.status}")
                    else:
                        user = self._active_user(session, user_id)
                        supplied = self._digest("verification-code", str(verification_code or "").strip())
                        if not hmac.compare_digest(str(row.verification_code_hash), supplied):
                            row.failed_attempts = min(
                                QR_MAX_CODE_ATTEMPTS, int(row.failed_attempts) + 1,
                            )
                            if row.failed_attempts >= QR_MAX_CODE_ATTEMPTS:
                                row.status = "rejected"
                            mismatch = QrLoginCodeMismatch(
                                QR_MAX_CODE_ATTEMPTS - int(row.failed_attempts),
                            )
                        else:
                            changed = session.execute(
                                update(SysQrLoginSession)
                                .where(
                                    SysQrLoginSession.id == row.id,
                                    SysQrLoginSession.status == "pending",
                                    SysQrLoginSession.failed_attempts == row.failed_attempts,
                                )
                                .values(
                                    status="approved",
                                    approved_user_id=user.id,
                                    approved_at=now,
                                )
                            )
                            if changed.rowcount != 1:
                                failure = QrLoginConflict("扫码会话已被处理")
                            else:
                                row.status = "approved"
                                row.approved_user_id = user.id
                                row.approved_at = now
                                payload = self._status_payload(row)
            if mismatch is not None:
                raise mismatch
            if failure is not None:
                raise failure
            return payload or {"session_id": session_id, "status": "approved"}
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码确认失败") from exc

    def reject(self, session_id: str, user_id: str) -> dict[str, Any]:
        failure: QrLoginError | None = None
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    self._active_user(session, user_id)
                    now = self._now(session)
                    if self._expire(row, now):
                        failure = QrLoginExpired("扫码会话已过期")
                    elif row.status == "rejected":
                        payload = self._status_payload(row)
                    elif row.status != "pending":
                        failure = QrLoginConflict(f"扫码会话当前状态为 {row.status}")
                        payload = self._status_payload(row)
                    else:
                        row.status = "rejected"
                        payload = self._status_payload(row)
            if failure is not None:
                raise failure
            return payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码拒绝失败") from exc

    def cancel(self, session_id: str, browser_secret: str) -> dict[str, Any]:
        failure: QrLoginError | None = None
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    self._assert_browser_secret(row, browser_secret)
                    now = self._now(session)
                    if self._expire(row, now):
                        payload = self._status_payload(row)
                    elif row.status == "cancelled":
                        payload = self._status_payload(row)
                    elif row.status not in {"pending", "approved"}:
                        failure = QrLoginConflict(f"扫码会话当前状态为 {row.status}")
                        payload = self._status_payload(row)
                    else:
                        row.status = "cancelled"
                        payload = self._status_payload(row)
            if failure is not None:
                raise failure
            return payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码取消失败") from exc

    def exchange(self, session_id: str, browser_secret: str) -> dict[str, Any]:
        failure: QrLoginError | None = None
        token_payload: dict[str, Any] | None = None
        factory = self._factory()
        try:
            with factory() as session:
                with session.begin():
                    row = self._locked_session(session, session_id)
                    self._assert_browser_secret(row, browser_secret)
                    now = self._now(session)
                    if self._expire(row, now):
                        failure = QrLoginExpired("扫码会话已过期")
                    elif row.status != "approved":
                        failure = QrLoginConflict(f"扫码会话当前状态为 {row.status}")
                    else:
                        user = self._active_user(session, str(row.approved_user_id or ""))
                        try:
                            token_payload = self._token_issuer({"id": user.id, "email": user.email})
                        except Exception as exc:
                            raise QrLoginUnavailable("登录令牌签发失败") from exc
                        changed = session.execute(
                            update(SysQrLoginSession)
                            .where(
                                SysQrLoginSession.id == row.id,
                                SysQrLoginSession.status == "approved",
                                SysQrLoginSession.approved_user_id == user.id,
                            )
                            .values(status="consumed", consumed_at=now)
                        )
                        if changed.rowcount != 1:
                            failure = QrLoginConflict("扫码会话已被兑换")
                            token_payload = None
                        else:
                            user.last_login_at = now
            if failure is not None:
                raise failure
            if token_payload is None:
                raise QrLoginUnavailable("登录令牌签发失败")
            return token_payload
        except QrLoginError:
            raise
        except SQLAlchemyError as exc:
            raise QrLoginUnavailable("扫码登录兑换失败") from exc


default_qr_login_service = QrLoginService()


__all__ = [
    "QR_MAX_CODE_ATTEMPTS",
    "QR_POLL_INTERVAL_MS",
    "QR_SESSION_TTL_SECONDS",
    "QrLoginCodeMismatch",
    "QrLoginConflict",
    "QrLoginExpired",
    "QrLoginNotFound",
    "QrLoginService",
    "QrLoginUnavailable",
    "QrLoginUserInactive",
    "default_qr_login_service",
]
