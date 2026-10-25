"""持久账号管理；固定账号 owner，不依赖演示身份或内存回退。"""

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import MetaData, func, or_, select, text
from sqlalchemy.exc import IntegrityError

from ..core.security import get_password_hash
from ..database.connection import SessionLocal
from ..database.models.v36_reports import SysUser
from .defect_rectification_service import RectificationError, _persistent_roles
from .user_scope_owner import resolve_user_owner_schema

logger = logging.getLogger(__name__)
ROLES = {"admin", "qc_manager", "qc_staff", "doctor"}


def _iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _view(row):
    return {
        key: row[key]
        for key in (
            "id",
            "username",
            "email",
            "display_name",
            "institute_id",
            "department",
            "is_active",
        )
    } | {
        "roles": sorted(_persistent_roles(row["role"], row["roles_json"])),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
        "last_login_at": _iso(row["last_login_at"]),
    }


class AccountManagementService:
    def __init__(self, session_factory=None):
        self.sessions = session_factory or SessionLocal

    def _table(self, session):
        owner = resolve_user_owner_schema(session)
        return SysUser.__table__.to_metadata(MetaData(), schema=owner)

    def _admin(self, session, table, actor_id):
        row = (
            session.execute(
                select(table).where(table.c.id == actor_id).with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if (
            row is None
            or not row["is_active"]
            or "admin" not in _persistent_roles(row["role"], row["roles_json"])
        ):
            raise RectificationError("仅持久系统管理员可以管理账号", 403)
        return row

    def _write_lock(self, session):
        # 串行维护账号，避免大小写冲突及多个管理员相互停用的竞态。
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(10252501)"))

    def _scope(self, actor, institute_id):
        if actor["institute_id"] and actor["institute_id"] != institute_id:
            raise RectificationError("仅可管理本机构账号", 403)

    def list(
        self, actor_id, *, keyword="", role=None, active=None, page=1, page_size=20
    ):
        if (
            not 1 <= page <= 10000
            or not 1 <= page_size <= 100
            or role not in (None, *ROLES)
        ):
            raise RectificationError("账号筛选无效")
        with self.sessions() as session, session.begin():
            table = self._table(session)
            actor = self._admin(session, table, actor_id)
            statement = select(table)
            if actor["institute_id"]:
                statement = statement.where(
                    table.c.institute_id == actor["institute_id"]
                )
            if keyword.strip():
                pattern = f"%{keyword.strip().lower().replace('/', '//').replace('%', '/%').replace('_', '/_')}%"
                statement = statement.where(
                    or_(
                        *(
                            func.lower(column).like(pattern, escape="/")
                            for column in (
                                table.c.username,
                                table.c.email,
                                table.c.display_name,
                                table.c.department,
                            )
                        )
                    )
                )
            if active is not None:
                statement = statement.where(table.c.is_active == active)
            # 角色 JSON 由同一解析器校验，不以包含字符串判断授权；不读取口令哈希。
            if role:
                candidates = session.execute(
                    statement.with_only_columns(
                        table.c.id, table.c.role, table.c.roles_json
                    )
                ).mappings()
                ids = [
                    row["id"]
                    for row in candidates
                    if role in _persistent_roles(row["role"], row["roles_json"])
                ]
                statement = statement.where(table.c.id.in_(ids))
            total = session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            start = (page - 1) * page_size
            columns = [column for column in table.c if column.name != "password_hash"]
            rows = session.execute(
                statement.with_only_columns(*columns)
                .order_by(table.c.created_at.desc(), table.c.id)
                .offset(start)
                .limit(page_size)
            ).mappings()
            return {
                "items": [_view(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
                "actor_id": actor_id,
                "managed_institute_id": actor["institute_id"],
            }

    def create(self, actor_id, data):
        try:
            with self.sessions() as session, session.begin():
                self._write_lock(session)
                table = self._table(session)
                actor = self._admin(session, table, actor_id)
                self._scope(actor, data["institute_id"])
                username, email = (
                    data["username"].strip(),
                    data["email"].strip().lower(),
                )
                duplicate = session.scalar(
                    select(table.c.id)
                    .where(
                        or_(
                            func.lower(table.c.username) == username.lower(),
                            func.lower(table.c.email) == email,
                            func.lower(table.c.username) == email,
                            func.lower(table.c.email) == username.lower(),
                            table.c.phone == username,
                        )
                    )
                    .limit(1)
                )
                if duplicate:
                    raise RectificationError("用户名或邮箱已被使用", 409)
                roles = sorted(set(data["roles"]))
                if not roles or set(roles) - ROLES:
                    raise RectificationError("账号角色无效")
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                user_id = str(uuid4())
                session.execute(
                    table.insert().values(
                        id=user_id,
                        username=username,
                        email=email,
                        display_name=data["display_name"],
                        institute_id=data["institute_id"],
                        department=data["department"],
                        role=roles[0],
                        roles_json=json.dumps(roles),
                        is_active=True,
                        password_hash=get_password_hash(data["password"]),
                        created_at=now,
                        updated_at=now,
                    )
                )
                row = (
                    session.execute(select(table).where(table.c.id == user_id))
                    .mappings()
                    .one()
                )
                result = _view(row)
            logger.info("account.create actor_id=%s target_id=%s", actor_id, user_id)
            return result
        except IntegrityError as exc:
            raise RectificationError("账号标识冲突，请刷新核对", 409) from exc

    def update(self, actor_id, user_id, data):
        with self.sessions() as session, session.begin():
            self._write_lock(session)
            table = self._table(session)
            actor = self._admin(session, table, actor_id)
            row = (
                session.execute(
                    select(table).where(table.c.id == user_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RectificationError("账号不存在", 404)
            self._scope(actor, row["institute_id"])
            self._scope(actor, data["institute_id"])
            if _persistent_roles(row["role"], row["roles_json"]) - ROLES:
                raise RectificationError("专用角色由原权限系统维护，不在此覆盖", 409)
            expected = data["expected_updated_at"]
            if expected is not None and expected.tzinfo is not None:
                expected = expected.astimezone(timezone.utc).replace(tzinfo=None)
            if expected != row["updated_at"]:
                raise RectificationError("账号已被修改，请刷新后再操作", 409)
            roles = sorted(set(data["roles"]))
            if not roles or set(roles) - ROLES:
                raise RectificationError("账号角色无效")
            if user_id == actor_id and (
                not data["is_active"]
                or set(roles) != _persistent_roles(row["role"], row["roles_json"])
                or data["institute_id"] != row["institute_id"]
                or data["department"] != row["department"]
            ):
                raise RectificationError("不能变更自身授权范围、角色或停用自身", 409)
            session.execute(
                table.update()
                .where(table.c.id == user_id)
                .values(
                    display_name=data["display_name"],
                    institute_id=data["institute_id"],
                    department=data["department"],
                    role=roles[0],
                    roles_json=json.dumps(roles),
                    is_active=data["is_active"],
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            result = _view(
                session.execute(select(table).where(table.c.id == user_id))
                .mappings()
                .one()
            )
        logger.info(
            "account.update actor_id=%s target_id=%s active=%s roles=%s",
            actor_id,
            user_id,
            data["is_active"],
            roles,
        )
        return result
