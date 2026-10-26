"""注册、审批及通知同事务；申请值不是可信业务授权，不回退内存账号。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..core.security import get_password_hash, verify_password
from ..database.models.account_registration import registration_tables
from .account_management_service import AccountManagementService, ROLES, _iso
from .defect_rectification_service import RectificationError, _persistent_roles, _effective_persistent_roles
from .doctor_notification_service import Notification

SOURCE = "v5_account_registration"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_view(row):
    return {
        key: row[key]
        for key in (
            "user_id",
            "status",
            "requested_institute_id",
            "requested_department",
            "version",
            "review_comment",
        )
    } | {key: _iso(row[key]) for key in ("submitted_at", "reviewed_at", "updated_at")}


def _account_view(user, registration):
    return {
        "display_name": user["display_name"],
        "is_active": bool(user["is_active"]),
        "institute_id": user["institute_id"]
        if registration["status"] == "approved"
        else None,
        "department": user["department"]
        if registration["status"] == "approved"
        else None,
        "roles": sorted(_persistent_roles(user["role"], user["roles_json"]))
        if registration["status"] == "approved"
        else [],
    }


def _event(
    session, events, row, actor_id, action, comment, institute, department, roles
):
    event_id = str(uuid4())
    session.execute(
        events.insert().values(
            id=event_id,
            registration_id=row["user_id"],
            actor_id=actor_id,
            action=action,
            version=row["version"],
            comment=comment,
            institute_id=institute,
            department=department,
            roles_json=json.dumps(roles),
            created_at=_now(),
        )
    )
    return event_id


def publish_registration_notification(
    session, *, row, event_id, sender_id, recipients, pending
):
    for recipient in recipients:
        session.add(
            Notification(
                id=str(uuid4()),
                type="system",
                title="账号注册待审批"
                if pending
                else (
                    "账号已开通" if row["status"] == "approved" else "注册申请已驳回"
                ),
                content=(
                    "有新的账号申请待核定。"
                    if pending
                    else (
                        "管理员已开通账号，可正常登录工作台。"
                        if row["status"] == "approved"
                        else "账号尚未开通。"
                    )
                )
                + (row["review_comment"] or ""),
                record_id=f"registration:{row['user_id']}:{row['version']}",
                identity_version=1,
                source_key=SOURCE,
                institute_id=row["requested_institute_id"],
                sender_id=sender_id,
                recipient_id=recipient,
                related_type=(
                    "account_registration" if pending else "account_registration_result"
                ),
                related_id=row["user_id"],
                severity="info",
                is_read=False,
                created_at=_now(),
            )
        )


class AccountRegistrationService(AccountManagementService):
    def __init__(self, session_factory=None, notification_writer=None):
        super().__init__(session_factory)
        self.notify = notification_writer or publish_registration_notification

    def _tables(self, session):
        users = self._table(session)
        registration, events = registration_tables(users)
        return users, registration, events

    def departments(self):
        from .registration_departments import registration_departments

        with self.sessions() as session:
            return {"items": [
                {key: option[key] for key in ("key", "name", "label")}
                for option in registration_departments(session)
            ]}

    def _recipients(self, session, users, institute):
        rows = session.execute(
            sa.select(users.c.id, users.c.role, users.c.roles_json, users.c.institute_id).where(
                users.c.is_active.is_(True),
            )
        ).mappings()
        result = [
            row["id"]
            for row in rows
            if "admin" in _effective_persistent_roles(row["role"], row["roles_json"])
            and (row["institute_id"] in (institute, None, "")
                 or "sync_admin" in _persistent_roles(row["role"], row["roles_json"]))
        ]
        if not result:
            raise RectificationError(
                "申请机构尚未配置可审批的持久管理员，请联系系统管理员", 409
            )
        return result

    def submit(self, data):
        from ..schemas.registration import RegistrationCreate

        data = RegistrationCreate.model_validate(data).model_dump()
        password = data["password"]
        email = str(data["email"] or "").lower() or None
        try:
            with self.sessions() as session, session.begin():
                if data["department_key"]:
                    from .registration_departments import registration_departments

                    selected = next((option for option in registration_departments(session)
                                     if option["key"] == data["department_key"]), None)
                    if selected is None:
                        raise RectificationError("科室选项已失效，请刷新科室列表后重新选择", 409)
                    data["institute_id"], data["department"] = selected["institute_id"], selected["name"]
                self._write_lock(session)
                users, registrations, events = self._tables(session)
                recipients = self._recipients(session, users, data["institute_id"])
                identifiers = [data["username"].lower()]
                if email:
                    identifiers.append(email)
                if data["phone"]:
                    identifiers.append(data["phone"])
                matches = (
                    session.execute(
                        sa.select(users)
                        .where(
                            sa.or_(
                                sa.func.lower(users.c.username).in_(identifiers),
                                sa.func.lower(users.c.email).in_(identifiers),
                                users.c.phone.in_(identifiers),
                            )
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .all()
                )
                now = _now()
                if matches:
                    old = matches[0]
                    request = (
                        session.execute(
                            sa.select(registrations)
                            .where(registrations.c.user_id == old["id"])
                            .with_for_update()
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if not (
                        len(matches) == 1
                        and request
                        and request["status"] == "rejected"
                        and not old["is_active"]
                        and old["username"].lower() == data["username"].lower()
                        and (not email or str(old["email"] or "").lower() == email)
                        and verify_password(password, old["password_hash"])
                    ):
                        raise RectificationError(
                            "账号标识已被使用；已有申请请查询审核结果", 409
                        )
                    user_id, version = old["id"], request["version"] + 1
                    session.execute(
                        users.update()
                        .where(users.c.id == user_id)
                        .values(
                            display_name=data["display_name"],
                            phone=data["phone"],
                            updated_at=now,
                        )
                    )
                else:
                    user_id, version = str(uuid4()), 1
                    session.execute(
                        users.insert().values(
                            id=user_id,
                            username=data["username"],
                            email=email,
                            password_hash=get_password_hash(password),
                            display_name=data["display_name"],
                            phone=data["phone"],
                            institute_id=None,
                            department=None,
                            role="doctor",
                            roles_json='["doctor"]',
                            is_active=False,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                values = dict(
                    status="pending",
                    requested_institute_id=data["institute_id"],
                    requested_department=data["department"],
                    version=version,
                    review_comment=None,
                    reviewed_by=None,
                    reviewed_at=None,
                    submitted_at=now,
                    updated_at=now,
                )
                if matches:
                    session.execute(
                        registrations.update()
                        .where(registrations.c.user_id == user_id)
                        .values(**values)
                    )
                else:
                    session.execute(
                        registrations.insert().values(user_id=user_id, **values)
                    )
                row = {"user_id": user_id, **values}
                event_id = _event(
                    session,
                    events,
                    row,
                    user_id,
                    "submit",
                    "提交注册申请",
                    data["institute_id"],
                    data["department"],
                    [],
                )
                self.notify(
                    session,
                    row=row,
                    event_id=event_id,
                    sender_id=user_id,
                    recipients=recipients,
                    pending=True,
                )
                session.flush()
                return _safe_view(row)
        except IntegrityError as exc:
            raise RectificationError("账号标识冲突，请查询已有申请", 409) from exc

    def status(self, account, password):
        with self.sessions() as session:
            users, registrations, _ = self._tables(session)
            row = (
                session.execute(
                    sa.select(users)
                    .where(
                        sa.or_(
                            sa.func.lower(users.c.username) == account.strip().lower(),
                            sa.func.lower(users.c.email) == account.strip().lower(),
                        )
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if (
                row is None
                or not row["password_hash"]
                or not verify_password(password, row["password_hash"])
            ):
                raise RectificationError("账号或口令不正确", 401)
            result = (
                session.execute(
                    sa.select(registrations).where(registrations.c.user_id == row["id"])
                )
                .mappings()
                .one_or_none()
            )
            if result is None:
                raise RectificationError("该账号没有注册申请，请使用登录入口", 404)
            return _safe_view(result) | _account_view(row, result)

    def own_status(self, user_id):
        with self.sessions() as session:
            users, registrations, _ = self._tables(session)
            row = (
                session.execute(
                    sa.select(registrations).where(registrations.c.user_id == user_id)
                )
                .mappings()
                .one_or_none()
            )
            user = (
                session.execute(sa.select(users).where(users.c.id == user_id))
                .mappings()
                .one_or_none()
            )
            if row is None or user is None or not user["is_active"]:
                raise RectificationError("没有可查看的开通结果", 404)
            return _safe_view(row) | _account_view(user, row)

    def list(self, actor_id, *, status="pending", page=1, page_size=20):
        if (
            status not in ("pending", "approved", "rejected")
            or not 1 <= page <= 10000
            or not 1 <= page_size <= 100
        ):
            raise RectificationError("申请筛选无效")
        with self.sessions() as session, session.begin():
            users, registrations, _ = self._tables(session)
            actor = self._admin(session, users, actor_id, for_update=False)
            statement = (
                sa.select(
                    registrations, users.c.username, users.c.email, users.c.display_name
                )
                .join(users, users.c.id == registrations.c.user_id)
                .where(registrations.c.status == status)
            )
            if self._scoped_institute(actor):
                statement = statement.where(
                    registrations.c.requested_institute_id == actor["institute_id"]
                )
            total = session.scalar(
                sa.select(sa.func.count()).select_from(statement.subquery())
            )
            rows = session.execute(
                statement.order_by(
                    registrations.c.submitted_at.desc(), registrations.c.user_id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).mappings()
            return {
                "items": [
                    _safe_view(row)
                    | {key: row[key] for key in ("username", "email", "display_name")}
                    for row in rows
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def detail(self, actor_id, user_id):
        with self.sessions() as session, session.begin():
            users, registrations, events = self._tables(session)
            actor = self._admin(session, users, actor_id, for_update=False)
            row = (
                session.execute(
                    sa.select(
                        registrations,
                        users.c.username,
                        users.c.email,
                        users.c.display_name,
                    )
                    .join(users, users.c.id == registrations.c.user_id)
                    .where(registrations.c.user_id == user_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RectificationError("注册申请不存在", 404)
            self._scope(actor, row["requested_institute_id"])
            history = session.execute(
                sa.select(events)
                .where(events.c.registration_id == user_id)
                .order_by(events.c.version)
            ).mappings()
            return (
                _safe_view(row)
                | {key: row[key] for key in ("username", "email", "display_name")}
                | {
                    "history": [
                        dict(event) | {"created_at": _iso(event["created_at"])}
                        for event in history
                    ],
                }
            )

    def review(self, actor_id, user_id, data):
        from ..schemas.registration import RegistrationReview

        data = RegistrationReview.model_validate(data).model_dump()
        with self.sessions() as session, session.begin():
            self._write_lock(session)
            users, registrations, events = self._tables(session)
            actor = self._admin(session, users, actor_id)
            row = (
                session.execute(
                    sa.select(registrations)
                    .where(registrations.c.user_id == user_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RectificationError("注册申请不存在", 404)
            self._scope(actor, row["requested_institute_id"])
            if row["status"] != "pending" or row["version"] != data["expected_version"]:
                raise RectificationError("申请已处理或已重新提交，请刷新后再操作", 409)
            if user_id == actor_id:
                raise RectificationError("不能审批自己的注册申请", 403)
            approved = data["decision"] == "approve"
            roles = sorted(set(data["roles"] or []))
            if approved:
                self._scope(actor, data["institute_id"])
                if set(roles) - ROLES:
                    raise RectificationError("授权角色无效")
            target = (
                session.execute(
                    sa.select(users).where(users.c.id == user_id).with_for_update()
                )
                .mappings()
                .one()
            )
            if target["is_active"] or _persistent_roles(
                target["role"], target["roles_json"]
            ) - {"doctor"}:
                raise RectificationError("申请账号状态异常，请核对原账号授权", 409)
            now = _now()
            updated = dict(row) | dict(
                status="approved" if approved else "rejected",
                version=row["version"] + 1,
                reviewed_by=actor_id,
                review_comment=data["comment"],
                reviewed_at=now,
                updated_at=now,
            )
            session.execute(
                registrations.update()
                .where(
                    registrations.c.user_id == user_id,
                    registrations.c.version == data["expected_version"],
                    registrations.c.status == "pending",
                )
                .values(
                    **{key: value for key, value in updated.items() if key != "user_id"}
                )
            )
            if approved:
                session.execute(
                    users.update()
                    .where(users.c.id == user_id)
                    .values(
                        is_active=True,
                        institute_id=data["institute_id"],
                        department=data["department"],
                        role=roles[0],
                        roles_json=json.dumps(roles),
                        updated_at=now,
                    )
                )
            event_id = _event(
                session,
                events,
                updated,
                actor_id,
                data["decision"],
                data["comment"],
                data["institute_id"] if approved else row["requested_institute_id"],
                data["department"] if approved else row["requested_department"],
                roles if approved else [],
            )
            self.notify(
                session,
                row=updated,
                event_id=event_id,
                sender_id=actor_id,
                recipients=[user_id],
                pending=False,
            )
            session.flush()
            return _safe_view(updated)
