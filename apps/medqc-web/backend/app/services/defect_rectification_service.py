"""整改唯一状态所有者。待办从本表推导，催办只写提醒事件，不修改缺陷和申诉。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from ..core.roles import effective_roles

from ..database.connection import SessionLocal
from ..database.models.v36_reports import DefectRectification as Task
from ..database.models.v36_reports import DefectRectificationEvent as Event
from ..database.models.v36_reports import SysUser
from .user_scope_owner import user_owner_options

MANAGERS = {"admin", "super_admin", "qc_manager", "qc_staff"}
STATES = {"pending", "submitted", "approved", "rejected"}


class RectificationError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _persistent_roles(role, roles_json):
    """整改授权只读取明确持久角色；损坏的多角色配置不得回退放行。"""
    if roles_json is not None and roles_json != "":
        try:
            roles = json.loads(roles_json)
        except (TypeError, ValueError):
            return set()
        if not isinstance(roles, list) or any(
            not isinstance(item, str) or not item.strip() for item in roles
        ):
            return set()
        return {item.strip() for item in roles}
    return {role.strip()} if isinstance(role, str) and role.strip() else set()


def _person(session, user_id):
    row = session.execute(
        select(SysUser).where(SysUser.id == user_id),
        execution_options=user_owner_options(session),
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        raise RectificationError("账号不可用", 403)
    roles = _effective_persistent_roles(row.role, row.roles_json)
    if not roles:
        raise RectificationError("账号缺少可信持久角色", 403)
    return {
        "id": row.id,
        "name": row.display_name,
        "institute_id": row.institute_id,
        "department": row.department,
        "roles": roles,
    }


def _effective_persistent_roles(role, roles_json):
    # 先验证持久原值，再沿用系统统一权限；损坏 JSON 不借单角色或 HTTP 声明放行。
    return set(effective_roles(list(_persistent_roles(role, roles_json))))


def _manager(person):
    return bool(person["roles"] & MANAGERS)


def _is_global_scope(person):
    roles = person["roles"]
    return ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not person["institute_id"]
    )


def _scope(person, institute_id, department, *, assignee_id=None):
    if _is_global_scope(person):
        return
    if not person["institute_id"] or person["institute_id"] != institute_id:
        raise RectificationError("无权访问该机构整改", 403)
    if not _manager(person) and (
        "doctor" not in person["roles"]
        or person["department"] != department
        or person["id"] != assignee_id
    ):
        raise RectificationError("仅指定医生可处理本科室整改", 403)


def _source(session, data):
    from .feedback_result_source import resolve_target

    return resolve_target(session, data)


def _department(session, identity):
    from .report_case_scope import load_scoring_departments

    department = load_scoring_departments([identity], session=session).get(identity)
    if not department:
        raise RectificationError("缺少可信病例科室", 409)
    return department


def _visible(target, person):
    # 质控显式派发仅授权本条整改，不开放医生端的全量结果或改写其规则可见性。
    if target.get("_dispatchable") is not True:
        raise RectificationError("缺陷未经正式投影或人工审核确认", 409)


def _serialize_value(value):
    if isinstance(value, datetime):
        aware = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return aware.isoformat()
    return value


def _view(row):
    return {
        c.name: _serialize_value(getattr(row, c.name))
        for c in row.__table__.columns
        if c.name not in {"dispatch_document_snapshot", "submission_document_snapshot"}
    }


def _active_urge_ids(events):
    # 医生提交已回应此前提醒；被明确撤回的提醒不再有效，历史行保留。
    submitted_version = max(
        (event.version for event in events if event.action == "submit"), default=0
    )
    withdrawn = {
        event.related_event_id for event in events if event.action == "withdraw_urge"
    }
    return {
        event.id
        for event in events
        if event.action == "urge"
        and event.version > submitted_version
        and event.id not in withdrawn
    }


class DefectRectificationService:
    def __init__(
        self,
        session_factory=None,
        source_loader=None,
        department_loader=None,
        person_loader=None,
        visibility_check=None,
        document_loader=None,
        notification_writer=None,
    ):
        self.sessions = session_factory or SessionLocal
        self.source = source_loader or _source
        self.department = department_loader or _department
        self.person = person_loader or _person
        self.visible = visibility_check or _visible
        self.document_loader = document_loader
        self.notification_writer = notification_writer

    def _snapshot_identity(self, identity):
        from .rectification_document_snapshot import capture_documents

        try:
            return capture_documents(identity, loader=self.document_loader)
        except RectificationError:
            raise
        except ValueError as exc:
            raise RectificationError(str(exc), 422) from exc

    def _snapshot(self, row):
        identity = {
            key: getattr(row, key) for key in ("institute_id", "patient_id", "visit_id")
        }
        return self._snapshot_identity(identity)

    def candidates(self, actor_id, **query):
        from .feedback_result_source import candidates

        return candidates(self, actor_id, **query)

    def _event(
        self,
        session,
        row,
        actor,
        action,
        old,
        comment,
        recipient,
        related_event_id=None,
        document_snapshot=None,
    ):
        event_id = str(uuid4())
        session.add(
            Event(
                id=event_id,
                rectification_id=row.id,
                action=action,
                actor_id=actor["id"],
                old_status=old,
                new_status=row.status,
                version=row.version,
                comment=comment,
                recipient_id=recipient,
                created_at=_now(),
                related_event_id=related_event_id,
                submission_document_snapshot=document_snapshot,
            )
        )
        from .doctor_notification_service import publish_doctor_notification

        writer = self.notification_writer or publish_doctor_notification
        writer(
            session,
            row,
            event_id=event_id,
            action=action,
            actor_id=actor["id"],
            comment=comment,
        )

    def create(self, actor_id, data):
        try:
            with self.sessions() as session, session.begin():
                actor = self.person(session, actor_id)
                if not _manager(actor):
                    raise RectificationError("仅质控人员可以派发", 403)
                identity = tuple(
                    data[key] for key in ("institute_id", "patient_id", "visit_id")
                )
                _scope(actor, identity[0], None)
                department = self.department(session, identity)
                _scope(actor, identity[0], department)
                assignee = self.person(session, data["assignee_id"])
                if (
                    "doctor" not in assignee["roles"]
                    or assignee["institute_id"] != identity[0]
                    or assignee["department"] != department
                ):
                    raise RectificationError("受领人必须为本机构本科室的有效医生", 403)
                target = self.source(session, data)
                self.visible(target, assignee)
                now = _now()
                row = Task(
                    id=str(uuid4()),
                    **{
                        key: target[key]
                        for key in (
                            "institute_id",
                            "patient_id",
                            "visit_id",
                            "scene",
                            "target_kind",
                            "target_id",
                            "root_job_id",
                            "envelope_id",
                            "rule_set_key",
                            "rule_set_version",
                        )
                    },
                    department=department,
                    creator_id=actor_id,
                    assignee_id=assignee["id"],
                    assignee_name=assignee["name"],
                    requirement=data["requirement"],
                    status="pending",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                row.dispatch_document_snapshot = self._snapshot(row)
                session.add(row)
                session.flush()
                self._event(
                    session,
                    row,
                    actor,
                    "assign",
                    None,
                    data["requirement"],
                    assignee["id"],
                )
                session.flush()
                return _view(row)
        except IntegrityError as exc:
            raise RectificationError("同一轮缺陷已派发，请刷新列表", 409) from exc

    def transition(
        self, actor_id, task_id, *, version, action, comment, urge_event_id=None
    ):
        if action != "withdraw_urge" and urge_event_id is not None:
            raise RectificationError("仅撤回催办允许指定催办事件")
        snapshot = None
        if action == "submit":
            # 先在无行锁只读会话完成权限与状态预检，再于锁外拉取 CDM 文书，避免持 FOR UPDATE 锁等待外部读 IO。
            with self.sessions() as read_session:
                pre_actor = self.person(read_session, actor_id)
                pre_row = read_session.get(Task, task_id)
                if pre_row is None:
                    raise RectificationError("整改记录不存在", 404)
                _scope(
                    pre_actor,
                    pre_row.institute_id,
                    pre_row.department,
                    assignee_id=pre_row.assignee_id,
                )
                if pre_row.version != version:
                    raise RectificationError("整改已被更新，请刷新", 409)
                if (
                    pre_actor["id"] != pre_row.assignee_id
                    or "doctor" not in pre_actor["roles"]
                ):
                    raise RectificationError("仅受领医生可提交", 403)
                if pre_row.status not in {"pending", "rejected"}:
                    raise RectificationError("当前状态不能提交", 409)
                identity = {
                    key: getattr(pre_row, key)
                    for key in ("institute_id", "patient_id", "visit_id")
                }
            snapshot = self._snapshot_identity(identity)
        with self.sessions() as session, session.begin():
            actor = self.person(session, actor_id)
            row = session.execute(
                select(Task).where(Task.id == task_id).with_for_update()
            ).scalar_one_or_none()
            if row is None:
                raise RectificationError("整改记录不存在", 404)
            _scope(actor, row.institute_id, row.department, assignee_id=row.assignee_id)
            if row.version != version:
                raise RectificationError("整改已被更新，请刷新", 409)
            old = row.status
            manager = _manager(actor)
            if action == "submit":
                if actor["id"] != row.assignee_id or "doctor" not in actor["roles"]:
                    raise RectificationError("仅受领医生可提交", 403)
                if old not in {"pending", "rejected"}:
                    raise RectificationError("当前状态不能提交", 409)
                changes = {"status": "submitted", "submission": comment}
                recipient = row.creator_id
            elif action in {"approve", "reject"}:
                if not manager or actor["id"] == row.assignee_id:
                    raise RectificationError("仅非受领人的质控人员可验收", 403)
                if old != "submitted":
                    raise RectificationError("尚无待验收的整改提交", 409)
                changes = {
                    "status": "approved" if action == "approve" else "rejected",
                    "review_comment": comment,
                }
                recipient = row.assignee_id
            elif action == "urge":
                if not manager or actor["id"] == row.assignee_id:
                    raise RectificationError("仅非受领人的质控人员可催办", 403)
                if old not in {"pending", "rejected"}:
                    raise RectificationError("当前状态无需催办", 409)
                changes = {}
                recipient = row.assignee_id
            elif action == "withdraw_urge":
                if not manager or actor["id"] == row.assignee_id:
                    raise RectificationError("仅非受领人的质控人员可撤回催办", 403)
                if old not in {"pending", "rejected"}:
                    raise RectificationError("当前状态没有可撤回催办", 409)
                events = session.scalars(
                    select(Event).where(Event.rectification_id == row.id)
                ).all()
                if not urge_event_id or urge_event_id not in _active_urge_ids(events):
                    raise RectificationError(
                        "催办事件已失效或不属于该整改，请刷新", 409
                    )
                changes = {}
                recipient = row.assignee_id
            else:
                raise RectificationError("不支持的整改操作")
            changed = session.execute(
                update(Task)
                .where(Task.id == row.id, Task.version == version)
                .values(**changes, version=version + 1, updated_at=_now())
            )
            if changed.rowcount != 1:
                raise RectificationError("整改已被更新，请刷新", 409)
            session.refresh(row)
            self._event(
                session,
                row,
                actor,
                action,
                old,
                comment,
                recipient,
                urge_event_id,
                snapshot,
            )
            session.flush()
            return _view(row)

    def comparison(self, actor_id, task_id, event_id):
        from .rectification_document_snapshot import compare_documents

        with self.sessions() as session:
            actor = self.person(session, actor_id)
            row = session.get(Task, task_id)
            if row is None:
                raise RectificationError("整改记录不存在", 404)
            _scope(actor, row.institute_id, row.department, assignee_id=row.assignee_id)
            event = session.execute(
                select(Event).where(
                    Event.id == event_id,
                    Event.rectification_id == row.id,
                    Event.action == "submit",
                )
            ).scalar_one_or_none()
            if event is None:
                raise RectificationError("该整改提交不存在", 404)
            identity = {
                key: getattr(row, key)
                for key in ("institute_id", "patient_id", "visit_id")
            }
            try:
                return compare_documents(
                    row.dispatch_document_snapshot,
                    event.submission_document_snapshot,
                    identity,
                )
            except RectificationError:
                raise
            except ValueError as exc:
                raise RectificationError(str(exc), 422) from exc

    def list(self, actor_id, *, state=None, page=1, page_size=20, source=None):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            if not _manager(actor) and "doctor" not in actor["roles"]:
                raise RectificationError("无整改访问权限", 403)
            conditions = []
            if source is not None:
                keys = (
                    "institute_id",
                    "patient_id",
                    "visit_id",
                    "scene",
                    "target_kind",
                    "target_id",
                    "root_job_id",
                    "envelope_id",
                )
                if set(source) != set(keys) or any(
                    not isinstance(source[key], str) or not source[key].strip()
                    for key in keys
                ):
                    raise RectificationError("整改来源必须提供完整八维坐标")
                conditions.extend(getattr(Task, key) == source[key] for key in keys)
            if not _is_global_scope(actor):
                if not actor["institute_id"]:
                    raise RectificationError("账号缺少机构范围", 403)
                conditions.append(Task.institute_id == actor["institute_id"])
                if not _manager(actor):
                    if not actor["department"]:
                        raise RectificationError("账号缺少科室范围", 403)
                    conditions.extend(
                        [
                            Task.assignee_id == actor_id,
                            Task.department == actor["department"],
                        ]
                    )
            if state:
                if state not in STATES:
                    raise RectificationError("整改状态无效")
                conditions.append(Task.status == state)
            total = session.scalar(
                select(func.count()).select_from(Task).where(*conditions)
            )
            rows = session.scalars(
                select(Task)
                .where(*conditions)
                .order_by(Task.updated_at.desc(), Task.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "items": [_view(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def detail(self, actor_id, task_id):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            row = session.get(Task, task_id)
            if row is None:
                raise RectificationError("整改记录不存在", 404)
            _scope(actor, row.institute_id, row.department, assignee_id=row.assignee_id)
            events = session.scalars(
                select(Event)
                .where(Event.rectification_id == row.id)
                .order_by(Event.version)
            ).all()
            active = (
                _active_urge_ids(events)
                if row.status in {"pending", "rejected"}
                else set()
            )
            return {
                **_view(row),
                "events": [
                    {**_view(event), "can_withdraw": event.id in active}
                    for event in events
                ],
            }
