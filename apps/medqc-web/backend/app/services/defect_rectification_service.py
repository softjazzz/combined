"""整改唯一状态所有者。待办从本表推导，催办只写提醒事件，不修改缺陷和申诉。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..database.connection import SessionLocal
from ..database.models.defect_rectification import DefectRectification as Task
from ..database.models.defect_rectification import DefectRectificationEvent as Event
from ..database.models.qc import QCDefect, SysUser
from .user_scope_owner import user_owner_options

MANAGERS = {"admin", "qc_manager", "qc_staff"}
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
        select(SysUser).where(SysUser.id == user_id), execution_options=user_owner_options(session),
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        raise RectificationError("账号不可用", 403)
    roles = _persistent_roles(row.role, row.roles_json)
    if not roles:
        raise RectificationError("账号缺少可信持久角色", 403)
    return {"id": row.id, "name": row.display_name, "institute_id": row.institute_id,
            "department": row.department, "roles": roles}


def _manager(person):
    return bool(person["roles"] & MANAGERS)


def _scope(person, institute_id, department, *, assignee_id=None):
    if "admin" in person["roles"]:
        return
    if not person["institute_id"] or person["institute_id"] != institute_id:
        raise RectificationError("无权访问该机构整改", 403)
    if not _manager(person) and (
        "doctor" not in person["roles"] or person["department"] != department
        or person["id"] != assignee_id
    ):
        raise RectificationError("仅指定医生可处理本科室整改", 403)


def _source(session, data):
    from .appeal_manual_target_service import resolve_task_manual_defect_target
    from .appeal_workspace_target_service import resolve_workspace_appeal_target
    from .custom_qc_workspace_service import CustomQCWorkspaceService
    from .qc_workspace.canonical_result_store import lock_case_result_mutations
    from .case_identity import CaseRef
    from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY

    identity = {key: data[key] for key in ("institute_id", "patient_id", "visit_id")}
    if data["target_kind"] == "canonical_defect":
        lock_case_result_mutations(session, [CaseRef.from_mapping(identity)], rule_set_key=LUXIAN_0609_RULE_SET_KEY)
    if data["target_kind"] == "canonical_defect":
        target = resolve_workspace_appeal_target(
            target_kind="canonical_defect", **identity, rule_id=data["target_id"],
            expected_job_id=data["root_job_id"], expected_envelope_id=data["envelope_id"],
            workspace_factory=CustomQCWorkspaceService, session=session,
        )
    else:
        target = resolve_task_manual_defect_target(
            defect_id=data["target_id"], workspace_factory=CustomQCWorkspaceService,
            session=session, lock=True,
        )
        defect = session.execute(select(QCDefect).where(QCDefect.id == data["target_id"])).scalar_one()
        if defect.manual_review_status != "approved" or defect.status not in {"pending", "urged", "rejected"}:
            raise RectificationError("仅已审核且有效的人工缺陷可派发", 409)
    for key in (*identity, "scene", "target_kind", "target_id", "root_job_id", "envelope_id"):
        if str(target.get(key) or "") != data[key]:
            raise RectificationError("缺陷来源已变化，请刷新后重试", 409)
    return target


def _department(session, identity):
    from .medical_records.query_service import load_scoring_departments
    department = load_scoring_departments([identity], session=session).get(identity)
    if not department:
        raise RectificationError("缺少可信病例科室", 409)
    return department


def _visible(target, person):
    if target["target_kind"] != "canonical_defect":
        return
    from .doctor_rule_visibility_service import visible_rule_ids
    allowed = visible_rule_ids(
        rule_set_key=target["rule_set_key"], rule_set_version=target["rule_set_version"],
        institute_id=person["institute_id"], department_name=person["department"],
    )
    if not target.get("_can_show_to_doctor") or target["target_id"] not in allowed:
        raise RectificationError("该缺陷未对受领医生开放", 409)


def _view(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _active_urge_ids(events):
    # 医生提交已回应此前提醒；被明确撤回的提醒不再有效，历史行保留。
    submitted_version = max((event.version for event in events if event.action == "submit"), default=0)
    withdrawn = {event.related_event_id for event in events if event.action == "withdraw_urge"}
    return {event.id for event in events
            if event.action == "urge" and event.version > submitted_version and event.id not in withdrawn}


class DefectRectificationService:
    def __init__(self, session_factory=None, source_loader=None, department_loader=None,
                 person_loader=None, visibility_check=None):
        self.sessions = session_factory or SessionLocal
        self.source = source_loader or _source
        self.department = department_loader or _department
        self.person = person_loader or _person
        self.visible = visibility_check or _visible

    def candidates(self, actor_id, *, institute_id, patient_id, visit_id, expected_job_id):
        from .custom_qc_workspace_service import CustomQCWorkspaceService
        from .record_review_service import resolve_workspace_result_reference
        from .scoring_service import project_customer_items
        from .doctor_rule_visibility_service import project_doctor_visible_items
        from .appeal_manual_target_service import resolve_task_manual_defect_target

        identity = (institute_id, patient_id, visit_id)
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            if not _manager(actor):
                raise RectificationError("仅质控人员可以派发", 403)
            department = self.department(session, identity)
            _scope(actor, institute_id, department)
            people = session.scalars(select(SysUser).where(
                SysUser.institute_id == institute_id, SysUser.department == department,
                SysUser.is_active.is_(True),
            ), execution_options=user_owner_options(session)).all()
            doctors = [{"id": person.id, "name": person.display_name} for person in people
                       if "doctor" in _persistent_roles(person.role, person.roles_json)]
            workspace = CustomQCWorkspaceService()
            dto = workspace.build_latest_single_record_result_dto(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
            )
            if dto.get("state") != "ready" or dto.get("job_id") != expected_job_id:
                raise RectificationError("当前质控结果已变化或不可用", 409)
            source = resolve_workspace_result_reference(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
                expected_job_id=expected_job_id, expected_envelope_id=str(dto.get("envelope_id") or ""),
                workspace_factory=CustomQCWorkspaceService, session=session,
            )
            items = project_doctor_visible_items(
                project_customer_items(source["items"]), rule_set_key=source["rule_set_key"],
                rule_set_version=source["rule_set_version"], institute_id=institute_id,
                department_name=department,
            )
            targets = [{"target_kind": "canonical_defect", "target_id": item["rule_id"],
                        "label": item.get("rule_name") or item["rule_id"],
                        "scene": source["scene"], "root_job_id": source["root_job_id"],
                        "envelope_id": source["envelope_id"]}
                       for item in items if item.get("is_confirmed_issue") is True]
            manual = session.scalars(select(QCDefect).where(
                QCDefect.institute_id == institute_id, QCDefect.patient_id == patient_id,
                QCDefect.visit_id == visit_id, QCDefect.source_key == "task_assigned_qc",
                QCDefect.origin == "manual", QCDefect.manual_review_status == "approved",
                QCDefect.scene == source["scene"], QCDefect.status.in_(["pending", "urged", "rejected"]),
            ).order_by(QCDefect.id).limit(201)).all()
            if len(manual) > 200:
                raise RectificationError("人工缺陷超过单病例候选上限", 422)
            for row in manual:
                target = resolve_task_manual_defect_target(
                    defect_id=row.id, workspace_factory=CustomQCWorkspaceService, session=session,
                )
                if target["root_job_id"] != expected_job_id:
                    continue
                targets.append({key: target[key] for key in (
                    "target_kind", "target_id", "scene", "root_job_id", "envelope_id",
                )} | {"label": row.rule_name or row.rule_code or "人工缺陷"})
            return {"targets": targets, "doctors": doctors, "department": department}

    def _event(self, session, row, actor, action, old, comment, recipient, related_event_id=None):
        session.add(Event(id=str(uuid4()), rectification_id=row.id, action=action,
                          actor_id=actor["id"], old_status=old, new_status=row.status,
                          version=row.version, comment=comment, recipient_id=recipient,
                          created_at=_now(), related_event_id=related_event_id))

    def create(self, actor_id, data):
        try:
            with self.sessions() as session, session.begin():
                actor = self.person(session, actor_id)
                if not _manager(actor):
                    raise RectificationError("仅质控人员可以派发", 403)
                identity = tuple(data[key] for key in ("institute_id", "patient_id", "visit_id"))
                department = self.department(session, identity)
                _scope(actor, identity[0], department)
                assignee = self.person(session, data["assignee_id"])
                if ("doctor" not in assignee["roles"] or assignee["institute_id"] != identity[0]
                        or assignee["department"] != department):
                    raise RectificationError("受领人必须为本机构本科室的有效医生", 403)
                target = self.source(session, data)
                self.visible(target, assignee)
                now = _now()
                row = Task(id=str(uuid4()), **{key: target[key] for key in (
                    "institute_id", "patient_id", "visit_id", "scene", "target_kind", "target_id",
                    "root_job_id", "envelope_id", "rule_set_key", "rule_set_version",
                )}, department=department, creator_id=actor_id, assignee_id=assignee["id"],
                    assignee_name=assignee["name"], requirement=data["requirement"],
                    status="pending", version=1, created_at=now, updated_at=now)
                session.add(row)
                session.flush()
                self._event(session, row, actor, "assign", None, data["requirement"], assignee["id"])
                session.flush()
                return _view(row)
        except IntegrityError as exc:
            raise RectificationError("同一轮缺陷已派发，请刷新列表", 409) from exc

    def transition(self, actor_id, task_id, *, version, action, comment, urge_event_id=None):
        with self.sessions() as session, session.begin():
            actor = self.person(session, actor_id)
            row = session.execute(select(Task).where(Task.id == task_id).with_for_update()).scalar_one_or_none()
            if row is None:
                raise RectificationError("整改记录不存在", 404)
            _scope(actor, row.institute_id, row.department, assignee_id=row.assignee_id)
            if row.version != version:
                raise RectificationError("整改已被更新，请刷新", 409)
            old = row.status
            manager = _manager(actor)
            if action != "withdraw_urge" and urge_event_id is not None:
                raise RectificationError("仅撤回催办允许指定催办事件")
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
                changes = {"status": "approved" if action == "approve" else "rejected",
                           "review_comment": comment}
                recipient = row.assignee_id
            elif action == "urge":
                if not manager:
                    raise RectificationError("仅质控人员可催办", 403)
                if old not in {"pending", "rejected"}:
                    raise RectificationError("当前状态无需催办", 409)
                changes = {}
                recipient = row.assignee_id
            elif action == "withdraw_urge":
                if not manager:
                    raise RectificationError("仅质控人员可撤回催办", 403)
                if old not in {"pending", "rejected"}:
                    raise RectificationError("当前状态没有可撤回催办", 409)
                events = session.scalars(select(Event).where(Event.rectification_id == row.id)).all()
                if not urge_event_id or urge_event_id not in _active_urge_ids(events):
                    raise RectificationError("催办事件已失效或不属于该整改，请刷新", 409)
                changes = {}
                recipient = row.assignee_id
            else:
                raise RectificationError("不支持的整改操作")
            changed = session.execute(update(Task).where(Task.id == row.id, Task.version == version)
                                      .values(**changes, version=version + 1, updated_at=_now()))
            if changed.rowcount != 1:
                raise RectificationError("整改已被更新，请刷新", 409)
            session.refresh(row)
            self._event(session, row, actor, action, old, comment, recipient, urge_event_id)
            session.flush()
            return _view(row)

    def list(self, actor_id, *, state=None, page=1, page_size=20, source=None):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            if not _manager(actor) and "doctor" not in actor["roles"]:
                raise RectificationError("无整改访问权限", 403)
            conditions = []
            if source is not None:
                keys = ("institute_id", "patient_id", "visit_id", "scene", "target_kind", "target_id", "root_job_id", "envelope_id")
                if set(source) != set(keys) or any(not isinstance(source[key], str) or not source[key].strip() for key in keys):
                    raise RectificationError("整改来源必须提供完整八维坐标")
                conditions.extend(getattr(Task, key) == source[key] for key in keys)
            if "admin" not in actor["roles"]:
                if not actor["institute_id"]:
                    raise RectificationError("账号缺少机构范围", 403)
                conditions.append(Task.institute_id == actor["institute_id"])
                if not _manager(actor):
                    if not actor["department"]:
                        raise RectificationError("账号缺少科室范围", 403)
                    conditions.extend([Task.assignee_id == actor_id, Task.department == actor["department"]])
            if state:
                if state not in STATES:
                    raise RectificationError("整改状态无效")
                conditions.append(Task.status == state)
            total = session.scalar(select(func.count()).select_from(Task).where(*conditions))
            rows = session.scalars(select(Task).where(*conditions).order_by(Task.updated_at.desc(), Task.id)
                                   .offset((page - 1) * page_size).limit(page_size)).all()
            return {"items": [_view(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    def detail(self, actor_id, task_id):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            row = session.get(Task, task_id)
            if row is None:
                raise RectificationError("整改记录不存在", 404)
            _scope(actor, row.institute_id, row.department, assignee_id=row.assignee_id)
            events = session.scalars(select(Event).where(Event.rectification_id == row.id)
                                     .order_by(Event.version)).all()
            active = _active_urge_ids(events) if row.status in {"pending", "rejected"} else set()
            return {**_view(row), "events": [
                {**_view(event), "can_withdraw": event.id in active} for event in events
            ]}
