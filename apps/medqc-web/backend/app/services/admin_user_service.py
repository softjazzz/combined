"""管理员维护账号科室。

科室是医生数据范围与申诉授权的唯一依据（见 ``core/data_scope.py``），
只能由管理员在此写入；个人资料与公开注册不能修改。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import SysUser
from .auth_store import _normalize_roles

DEPARTMENT_MAX_LENGTH = 100


class AdminUserNotFound(LookupError):
    """账号不存在。"""


class AdminUserConflict(RuntimeError):
    """账号已被他人修改。"""


class AdminUserInvalid(ValueError):
    """请求参数不符合合同。"""


class AdminUserUnavailable(RuntimeError):
    """账号持久库不可用；不回退内存用户。"""


def _naive_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def _view(user: SysUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": str(user.username or "").strip(),
        "display_name": str(user.display_name or "").strip(),
        "department": str(user.department or "").strip() or None,
        "roles": _normalize_roles(user.role, user.roles_json),
        "is_active": bool(user.is_active),
        "updated_at": _iso(user.updated_at),
    }


def normalize_department(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdminUserInvalid("科室必须是字符串")
    text = value.strip()
    if len(text) > DEPARTMENT_MAX_LENGTH:
        raise AdminUserInvalid(f"科室不能超过 {DEPARTMENT_MAX_LENGTH} 个字符")
    return text or None


class AdminUserService:
    def __init__(self, session_factory: Optional[Callable[[], Session]] = None) -> None:
        factory = session_factory or SessionLocal
        if factory is None:
            raise AdminUserUnavailable("账号库不可用")
        self._session_factory = factory

    def list_users(
        self, *, query: Optional[str], department: Optional[str], page: int, page_size: int,
    ) -> dict[str, Any]:
        clauses = []
        keyword = str(query or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            clauses.append(or_(
                SysUser.username.ilike(pattern),
                SysUser.display_name.ilike(pattern),
                SysUser.email.ilike(pattern),
            ))
        if department == "__unassigned__":
            clauses.append(or_(SysUser.department.is_(None), func.trim(SysUser.department) == ""))
        elif department:
            clauses.append(SysUser.department == department.strip())
        with self._session_factory() as session:
            total = int(session.execute(
                select(func.count()).select_from(SysUser).where(*clauses)
            ).scalar() or 0)
            users = session.execute(
                select(SysUser).where(*clauses)
                .order_by(SysUser.display_name, SysUser.id)
                .offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
            departments = session.execute(
                select(SysUser.department).where(SysUser.department.is_not(None))
                .distinct().order_by(SysUser.department)
            ).scalars().all()
        return {
            "items": [_view(user) for user in users],
            "total": total,
            "page": page,
            "page_size": page_size,
            "departments": [item.strip() for item in departments if item and item.strip()],
        }

    def set_department(
        self, *, user_id: str, department: Any, expected_updated_at: datetime,
    ) -> dict[str, Any]:
        normalized = normalize_department(department)
        expected = _naive_utc(expected_updated_at)
        if expected is None:
            raise AdminUserInvalid("expected_updated_at 必须是有效时间")
        with self._session_factory() as session:
            user = session.execute(
                select(SysUser).where(SysUser.id == user_id).with_for_update()
            ).scalar_one_or_none()
            if user is None:
                raise AdminUserNotFound("账号不存在")
            if _naive_utc(user.updated_at) != expected:
                raise AdminUserConflict("账号已被修改，请刷新后重试")
            before = str(user.department or "").strip() or None
            user.department = normalized
            # 显式严格推进版本，同值写入或时钟回拨也能被后续 CAS 感知。
            now = datetime.utcnow()
            user.updated_at = now if now > expected else expected + timedelta(microseconds=1)
            session.commit()
            session.refresh(user)
            return {**_view(user), "previous_department": before}

