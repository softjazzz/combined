"""管理员维护账号医院与科室。

医院＋科室共同构成医生申诉范围，只能由管理员在此原子写入；个人资料与
公开注册不能修改。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import SysUser
from .auth_store import _normalize_roles
from .user_scope_owner import UserOwnerUnavailable, user_owner_options

DEPARTMENT_MAX_LENGTH = 100
INSTITUTE_ID_MAX_LENGTH = 128


class AdminUserNotFound(LookupError):
    """账号不存在。"""


class AdminUserConflict(RuntimeError):
    """账号已被他人修改。"""


class AdminUserInvalid(ValueError):
    """请求参数不符合合同。"""


class AdminUserUnavailable(RuntimeError):
    """账号持久库不可用；不回退内存用户。"""


class AdminUserForbidden(PermissionError):
    """当前身份不是持久账号库中的有效管理员。"""


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
        "institute_id": str(user.institute_id or "").strip() or None,
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


def normalize_institute_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdminUserInvalid("机构 ID 必须是字符串")
    text = value.strip()
    if len(text) > INSTITUTE_ID_MAX_LENGTH:
        raise AdminUserInvalid(f"机构 ID 不能超过 {INSTITUTE_ID_MAX_LENGTH} 个字符")
    return text or None


def normalize_scope(institute_id: Any, department: Any) -> tuple[Optional[str], Optional[str]]:
    normalized_institute = normalize_institute_id(institute_id)
    normalized_department = normalize_department(department)
    if (normalized_institute is None) != (normalized_department is None):
        raise AdminUserInvalid("机构与科室必须同时配置或同时清空")
    return normalized_institute, normalized_department


def _default_scope_options_loader(session: Session) -> list[dict[str, str]]:
    from .medical_records.query_service import list_scoring_department_options

    return list_scoring_department_options(session=session)


class AdminUserService:
    def __init__(
        self,
        session_factory: Optional[Callable[[], Session]] = None,
        scope_options_loader: Optional[Callable[[Session], list[dict[str, str]]]] = None,
    ) -> None:
        factory = session_factory or SessionLocal
        if factory is None:
            raise AdminUserUnavailable("账号库不可用")
        self._session_factory = factory
        self._scope_options_loader = scope_options_loader or _default_scope_options_loader

    @staticmethod
    def _bind_owner(session: Session) -> None:
        try:
            options = user_owner_options(session)
            if options:
                session.connection(execution_options=options)
        except UserOwnerUnavailable as exc:
            raise AdminUserUnavailable("账号库 owner 不可用") from exc

    def _scope_options(self, session: Session) -> list[dict[str, str]]:
        try:
            raw = self._scope_options_loader(session)
        except AdminUserUnavailable:
            raise
        except Exception as exc:
            raise AdminUserUnavailable("机构科室选项暂不可用") from exc
        pairs = sorted({
            (
                str(item.get("institute_id") or "").strip(),
                str(item.get("department") or item.get("department_name") or "").strip(),
            )
            for item in list(raw or [])
            if isinstance(item, dict)
        })
        return [
            {"institute_id": institute_id, "department": department}
            for institute_id, department in pairs
            if institute_id and department
        ]

    def list_scope_options(self) -> dict[str, Any]:
        with self._session_factory() as session:
            items = self._scope_options(session)
        return {
            "items": items,
            "institutes": sorted({item["institute_id"] for item in items}),
        }

    def require_durable_admin(self, user_id: Any) -> dict[str, Any]:
        normalized_id = str(user_id or "").strip()
        if not normalized_id:
            raise AdminUserForbidden("管理员账号不存在或已停用")
        try:
            with self._session_factory() as session:
                self._bind_owner(session)
                user = session.execute(
                    select(SysUser).where(SysUser.id == normalized_id).limit(1)
                ).scalar_one_or_none()
        except AdminUserUnavailable:
            raise
        except Exception as exc:
            raise AdminUserUnavailable("管理员账号重验暂不可用") from exc
        if user is None or not bool(user.is_active):
            raise AdminUserForbidden("管理员账号不存在或已停用")
        actor = _view(user)
        if "admin" not in set(actor["roles"]):
            raise AdminUserForbidden("当前账号已无管理员权限")
        return actor

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
            clauses.append(or_(
                SysUser.institute_id.is_(None),
                func.trim(SysUser.institute_id) == "",
                SysUser.department.is_(None),
                func.trim(SysUser.department) == "",
            ))
        elif department:
            clauses.append(SysUser.department == department.strip())
        with self._session_factory() as session:
            self._bind_owner(session)
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

    def set_scope(
        self,
        *,
        user_id: str,
        institute_id: Any,
        department: Any,
        expected_updated_at: datetime,
    ) -> dict[str, Any]:
        normalized_institute, normalized_department = normalize_scope(institute_id, department)
        expected = _naive_utc(expected_updated_at)
        if expected is None:
            raise AdminUserInvalid("expected_updated_at 必须是有效时间")
        if normalized_institute is not None:
            # 病例科室查询不能复用绑定到 sys owner 的连接，否则 schema_translate_map
            # 会把 CDM 表错误翻译到 sys schema。
            with self._session_factory() as option_session:
                allowed = {
                    (item["institute_id"], item["department"])
                    for item in self._scope_options(option_session)
                }
            if (normalized_institute, normalized_department) not in allowed:
                raise AdminUserInvalid("机构与科室组合不在可选范围内")
        with self._session_factory() as session:
            self._bind_owner(session)
            user = session.execute(
                select(SysUser).where(SysUser.id == user_id).with_for_update()
            ).scalar_one_or_none()
            if user is None:
                raise AdminUserNotFound("账号不存在")
            if _naive_utc(user.updated_at) != expected:
                raise AdminUserConflict("账号已被修改，请刷新后重试")
            previous_institute = str(user.institute_id or "").strip() or None
            previous_department = str(user.department or "").strip() or None
            user.institute_id = normalized_institute
            user.department = normalized_department
            # 显式严格推进版本，同值写入或时钟回拨也能被后续 CAS 感知。
            now = datetime.utcnow()
            user.updated_at = now if now > expected else expected + timedelta(microseconds=1)
            session.commit()
            session.refresh(user)
            return {
                **_view(user),
                "previous_institute_id": previous_institute,
                "previous_department": previous_department,
            }
