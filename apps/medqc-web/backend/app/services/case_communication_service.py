"""病例沟通只保存提醒和意见，不写病历审核或缺陷状态。"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError

from ..database.connection import SessionLocal
from ..database.models.case_communication import CaseCommunication as Event
from ..database.models.qc import Notification, SysUser
from .defect_rectification_service import RectificationError, _department, _person, _persistent_roles
from .user_scope_owner import user_owner_options

SOURCE_FIELDS = ("institute_id", "patient_id", "visit_id", "scene", "root_job_id", "envelope_id")
REQUEST_FIELDS = (*SOURCE_FIELDS, "recipient_id", "action", "content", "related_event_id")


def _manager(person, institute_id):
    if not person["roles"] & {"admin", "qc_manager"} or (
        "admin" not in person["roles"] and person["institute_id"] != institute_id
    ):
        raise RectificationError("无权管理该机构病例沟通", 403)


def _recipient(person, event):
    if ("doctor" not in person["roles"] or person["id"] != event.recipient_id
        or person["institute_id"] != event.institute_id or person["department"] != event.department):
        raise RectificationError("无权读取该病例沟通", 403)


def _source(session, data, *, candidate=False):
    from .case_identity import CaseRef
    from .custom_qc_workspace_service import CustomQCWorkspaceService
    from .record_review_service import _case_anchor, resolve_workspace_result_reference
    from .qc_workspace.canonical_result_store import lock_case_result_mutations
    identity = {key: data[key] for key in SOURCE_FIELDS[:3]}
    envelope_id = data.get("envelope_id")
    if candidate:
        dto = CustomQCWorkspaceService().build_latest_single_record_result_dto(**identity, rule_set_key="luxian_0609_qc_v1")
        anchor, _ = _case_anchor(dto)
        if not anchor or anchor.job_id != data["root_job_id"]:
            raise RectificationError("当前质控结果已变化，请刷新病例", 409)
        envelope_id = anchor.envelope_id
    else:
        lock_case_result_mutations(session, [CaseRef.from_mapping(identity)], rule_set_key="luxian_0609_qc_v1")
    result = resolve_workspace_result_reference(**identity, expected_job_id=data["root_job_id"],
        expected_envelope_id=envelope_id, workspace_factory=CustomQCWorkspaceService, session=session)
    if result["scene"] != data["scene"]:
        raise RectificationError("病例场景与当前质控结果不一致", 409)
    return {key: result[key] for key in (*SOURCE_FIELDS, "rule_set_key", "rule_set_version")}


def communication_rows(session, identity):
    return session.execute(select(Event, Notification).outerjoin(Notification, Notification.id == Event.notification_id)
        .where(*(getattr(Event, key) == value for key, value in zip(SOURCE_FIELDS[:3], identity)))).all()


def event_view(event, notice=None, *, withdrawn=False):
    if event.action != "withdraw" and (not notice or notice.id != event.notification_id
        or notice.identity_version != 1 or notice.source_key != "case_communication"
        or notice.related_type != "case_communication" or notice.related_id != event.id
        or notice.recipient_id != event.recipient_id
        or any(getattr(notice, key) != getattr(event, key) for key in SOURCE_FIELDS[:3])):
        raise RuntimeError("病例沟通通知来源不完整或不一致")
    return {key: getattr(event, key) for key in (*SOURCE_FIELDS, "rule_set_key", "rule_set_version",
        "id", "actor_id", "recipient_id", "department", "action", "content", "request_id", "related_event_id", "created_at")} | {
        "notification_id": event.notification_id, "is_read": notice.is_read if notice else None,
        "read_at": notice.read_at if notice else None, "withdrawn": withdrawn,
    }


class CaseCommunicationService:
    def __init__(self, sessions=None, source=None, department=None, person=None):
        self.sessions = sessions or SessionLocal
        self.source = source or _source
        self.department = department or _department
        self.person = person or _person

    def candidates(self, actor_id, data):
        with self.sessions() as session:
            _manager(self.person(session, actor_id), data["institute_id"])
            identity = tuple(data[key] for key in SOURCE_FIELDS[:3])
            department = self.department(session, identity)
            source = self.source(session, data, candidate=True)
            people = session.execute(select(SysUser).where(SysUser.is_active.is_(True),
                SysUser.institute_id == identity[0], SysUser.department == department),
                execution_options=user_owner_options(session)).scalars().all()
            doctors = [{"id": person.id, "name": person.display_name} for person in people
                if "doctor" in _persistent_roles(person.role, person.roles_json)]
            rows = communication_rows(session, identity)
            withdrawn = {event.related_event_id for event, _ in rows if event.action == "withdraw"}
            return {"source": source, "doctors": doctors, "items": [event_view(event, notice, withdrawn=event.id in withdrawn)
                for event, notice in rows if all(getattr(event, key) == source[key] for key in SOURCE_FIELDS)]}

    def create(self, actor_id, data):
        if data.get("action") not in {"urge", "opinion", "withdraw"} or not isinstance(data.get("content"), str) or not 1 <= len(data["content"].strip()) <= 2000:
            raise RectificationError("沟通动作或正文无效", 422)
        if (data["action"] == "withdraw") != bool(data.get("related_event_id")):
            raise RectificationError("撤回须且仅须提供原催办事件", 422)
        try:
            with self.sessions() as session, session.begin():
                actor = self.person(session, actor_id)
                _manager(actor, data["institute_id"])
                previous = session.execute(select(Event).where(Event.actor_id == actor_id, Event.request_id == data["request_id"])).scalar_one_or_none()
                if previous:
                    if any(getattr(previous, key) != data.get(key) for key in REQUEST_FIELDS):
                        raise RectificationError("同一请求标识的内容已变化", 409)
                    return event_view(previous, session.get(Notification, previous.notification_id) if previous.notification_id else None)
                source = self.source(session, data)
                if any(source[key] != data[key] for key in SOURCE_FIELDS):
                    raise RectificationError("沟通来源已变化", 409)
                identity = tuple(data[key] for key in SOURCE_FIELDS[:3])
                department = self.department(session, identity)
                recipient = self.person(session, data["recipient_id"])
                if "doctor" not in recipient["roles"] or recipient["institute_id"] != identity[0] or recipient["department"] != department:
                    raise RectificationError("受领人不是同院本科室有效医生", 403)
                if data["action"] == "withdraw":
                    original = session.execute(select(Event).where(Event.id == data["related_event_id"]).with_for_update()).scalar_one_or_none()
                    if not original or original.action != "urge" or original.recipient_id != recipient["id"] or any(getattr(original, key) != data[key] for key in SOURCE_FIELDS):
                        raise RectificationError("原催办与当前病例轮次不一致", 409)
                    if session.execute(select(Event.id).where(Event.related_event_id == original.id)).first():
                        raise RectificationError("该催办已撤回", 409)
                event = Event(id=str(uuid4()), **source, department=department, actor_id=actor_id,
                    recipient_id=recipient["id"], action=data["action"], content=data["content"],
                    request_id=data["request_id"], related_event_id=data.get("related_event_id"),
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None))
                notice = None
                if event.action != "withdraw":
                    notice = Notification(id=str(uuid4()), type="case_communication", title="病历催办" if event.action == "urge" else "质控意见",
                        content=event.content, identity_version=1, source_key="case_communication",
                        **{key: source[key] for key in SOURCE_FIELDS[:3]}, sender_id=actor_id, recipient_id=recipient["id"],
                        related_type="case_communication", related_id=event.id, is_read=False, created_at=event.created_at)
                    event.notification_id = notice.id
                    session.add(notice)
                session.add(event)
                session.flush()
                return event_view(event, notice)
        except IntegrityError as exc:
            with self.sessions() as session:
                _manager(self.person(session, actor_id), data["institute_id"])
                previous = session.execute(select(Event).where(Event.actor_id == actor_id, Event.request_id == data["request_id"])).scalar_one_or_none()
                if previous and all(getattr(previous, key) == data.get(key) for key in REQUEST_FIELDS):
                    return event_view(previous, session.get(Notification, previous.notification_id) if previous.notification_id else None)
            raise RectificationError("请求或催办已被并发处理，请刷新核对", 409) from exc

    def inbox(self, actor_id, page=1, page_size=20):
        if not isinstance(page, int) or not isinstance(page_size, int) or page < 1 or not 1 <= page_size <= 100:
            raise RectificationError("分页参数无效", 422)
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            if "doctor" not in actor["roles"] or not actor["institute_id"] or not actor["department"]:
                raise RectificationError("仅有可信院科的医生可读取病例沟通", 403)
            withdrawal = Event.__table__.alias("withdrawal")
            query = select(Event, Notification).outerjoin(Notification, Notification.id == Event.notification_id).where(
                Event.recipient_id == actor_id, Event.institute_id == actor["institute_id"], Event.department == actor["department"],
                Event.action.in_(("urge", "opinion")),
                ~exists(select(withdrawal.c.id).where(withdrawal.c.related_event_id == Event.id)))
            total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
            rows = session.execute(query.order_by(Event.created_at.desc(), Event.id.desc())
                .offset((page - 1) * page_size).limit(page_size)).all()
            return {"items": [event_view(event, notice) for event, notice in rows],
                "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}

    def read(self, actor_id, event_id):
        with self.sessions() as session, session.begin():
            event = session.get(Event, event_id)
            if not event or not event.notification_id:
                raise RectificationError("沟通消息不存在", 404)
            _recipient(self.person(session, actor_id), event)
            notice = session.execute(select(Notification).where(Notification.id == event.notification_id,
                Notification.recipient_id == actor_id, Notification.related_type == "case_communication", Notification.related_id == event.id).with_for_update()).scalar_one_or_none()
            if not notice:
                raise RectificationError("通知来源不可用", 409)
            event_view(event, notice)
            if not notice.is_read:
                notice.is_read = True
                notice.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.flush()
            return event_view(event, notice)

    def detail(self, actor_id, event_id):
        with self.sessions() as session:
            event = session.get(Event, event_id)
            if not event or not event.notification_id:
                raise RectificationError("沟通消息不存在", 404)
            _recipient(self.person(session, actor_id), event)
            notice = session.execute(select(Notification).where(Notification.id == event.notification_id,
                Notification.recipient_id == actor_id, Notification.related_type == "case_communication",
                Notification.related_id == event.id)).scalar_one_or_none()
            if not notice:
                raise RectificationError("通知来源不可用", 409)
            return event_view(event, notice)
