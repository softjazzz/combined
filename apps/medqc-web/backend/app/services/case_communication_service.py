"""病历沟通唯一事实所有者；不写审核、任务完成或缺陷状态。"""

from datetime import datetime, timezone
import threading
from uuid import NAMESPACE_URL, uuid4, uuid5
import weakref

from sqlalchemy import func, inspect as sa_inspect, select, text
from sqlalchemy.exc import IntegrityError

from ..database.connection import SessionLocal
from ..database.models.case_communication import CaseCommunication as Event
from ..database.models.v36_reports import SysUser
from .defect_rectification_service import (
    RectificationError,
    _department,
    _person,
    _persistent_roles,
)
from .medical_records.query_service import (
    _normalize_department_sql_expr,
    normalize_department_name,
)
from .user_scope_owner import user_owner_options

_ENSURE_LOCK = threading.Lock()
_ENSURED_ENGINES: "weakref.WeakSet[object]" = weakref.WeakSet()
_ENSURED_ENGINE_IDS: set[tuple[int, str | None]] = set()


def _department_equals(left, right) -> bool:
    return normalize_department_name(left) == normalize_department_name(right)


def _event_execution_options(session) -> dict:
    bind = session.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "").lower()
    if dialect_name == "sqlite" and Event.__table__.schema:
        return {"schema_translate_map": {Event.__table__.schema: None}}
    return {}


def _ensure_communication_table(session) -> None:
    """幂等确保病历沟通表存在，兼顾 single / split 与 SQLite。"""
    bind = session.get_bind()
    if bind is None:
        return
    target_engine = getattr(bind, "engine", bind)
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "").lower()
    schema = None if dialect_name == "sqlite" else Event.__table__.schema
    cache_key = (id(target_engine), schema)
    with _ENSURE_LOCK:
        try:
            already = target_engine in _ENSURED_ENGINES and cache_key in _ENSURED_ENGINE_IDS
        except TypeError:
            already = cache_key in _ENSURED_ENGINE_IDS
        if already:
            return
        inspector = sa_inspect(bind)
        if not inspector.has_table(Event.__table__.name, schema=schema):
            if hasattr(target_engine, "begin"):
                with target_engine.begin() as ddl_conn:
                    if dialect_name == "postgresql" and schema:
                        ddl_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
                    ddl_target = (
                        ddl_conn.execution_options(schema_translate_map={Event.__table__.schema: None})
                        if dialect_name == "sqlite" and Event.__table__.schema
                        else ddl_conn
                    )
                    Event.__table__.create(bind=ddl_target, checkfirst=True)
            else:
                ddl_target = (
                    bind.execution_options(schema_translate_map={Event.__table__.schema: None})
                    if dialect_name == "sqlite" and Event.__table__.schema
                    else bind
                )
                Event.__table__.create(bind=ddl_target, checkfirst=True)
        try:
            _ENSURED_ENGINES.add(target_engine)
        except TypeError:
            pass
        _ENSURED_ENGINE_IDS.add(cache_key)

SOURCE = "v5_doctor_feedback"
IDENTITY_FIELDS = ("institute_id", "patient_id", "visit_id")
SOURCE_FIELDS = (
    *IDENTITY_FIELDS,
    "scene",
    "root_job_id",
    "envelope_id",
    "rule_set_key",
    "rule_set_version",
)
REQUEST_FIELDS = (
    *SOURCE_FIELDS,
    "recipient_id",
    "action",
    "content",
    "related_event_id",
)
LABELS = {"urge": "病历催办", "opinion": "病历质控意见", "withdraw": "病历催办已撤回"}


def _valid_source(source):
    if any(
        not isinstance(source.get(key), str) or not source[key].strip()
        for key in SOURCE_FIELDS
    ) or source.get("scene") not in {"running", "final"}:
        raise RectificationError("病历沟通缺少可信冻结来源", 409)


MANAGERS = {"admin", "super_admin", "qc_manager", "qc_staff"}


def _is_global_scope(person):
    roles = person["roles"]
    return ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not person["institute_id"]
    )


def _manager(person, institute_id):
    if not person["roles"] & MANAGERS or (
        not _is_global_scope(person)
        and (not person["institute_id"] or person["institute_id"] != institute_id)
    ):
        raise RectificationError("无权管理该机构病历沟通", 403)


def _recipient(person, event):
    if (
        "doctor" not in person["roles"]
        or person["id"] != event.recipient_id
        or person["institute_id"] != event.institute_id
        or not _department_equals(person["department"], event.department)
    ):
        raise RectificationError("无权读取该病历沟通", 403)


def _source(session, data, *, candidate=False):
    from .feedback_result_source import current_result

    current = current_result(
        session,
        tuple(data[key] for key in IDENTITY_FIELDS),
        data["root_job_id"],
        None if candidate else data["envelope_id"],
    )
    if not candidate and current["scene"] != data["scene"]:
        raise RectificationError("病历场景与当前保存结果不一致", 409)
    return {key: current[key] for key in SOURCE_FIELDS}


def publish_case_communication_notification(session, event):
    from .doctor_notification_service import Notification

    notice = Notification(
        id=str(uuid5(NAMESPACE_URL, f"{SOURCE}:case_communication:{event.id}")),
        type="case_communication",
        title=LABELS[event.action],
        content=f"{'运行' if event.scene == 'running' else '终末'} · {event.visit_id}。{event.content}",
        record_id=f"feedback:case_communication:{event.id}",
        identity_version=1,
        source_key=SOURCE,
        **{key: getattr(event, key) for key in IDENTITY_FIELDS},
        severity="warning" if event.action == "urge" else "info",
        sender_id=event.actor_id,
        recipient_id=event.recipient_id,
        related_type="case_communication",
        related_id=event.id,
        is_read=False,
        created_at=event.created_at,
    )
    event.notification_id = notice.id
    session.add(notice)
    return notice


def event_view(event, notice, *, withdrawn=False):
    _valid_source({key: getattr(event, key) for key in SOURCE_FIELDS})
    if (
        not notice
        or notice.id != event.notification_id
        or notice.identity_version != 1
        or notice.source_key != SOURCE
        or notice.related_type != "case_communication"
        or notice.related_id != event.id
        or notice.recipient_id != event.recipient_id
        or any(getattr(notice, key) != getattr(event, key) for key in IDENTITY_FIELDS)
    ):
        raise RectificationError("病历沟通通知来源不完整或不一致", 409)

    def value(item):
        return (
            item.replace(tzinfo=timezone.utc).isoformat()
            if isinstance(item, datetime)
            else item
        )

    return {
        column.name: value(getattr(event, column.name))
        for column in Event.__table__.columns
    } | {
        "is_read": notice.is_read,
        "read_at": value(notice.read_at),
        "withdrawn": withdrawn,
    }


def _verify_envelope(session, data):
    from .feedback_result_source import verify_historical_envelope

    return verify_historical_envelope(
        session,
        tuple(data[key] for key in IDENTITY_FIELDS),
        data["root_job_id"],
        data["envelope_id"],
    )


class CaseCommunicationService:
    def __init__(
        self,
        sessions=None,
        source=None,
        department=None,
        person=None,
        notification_writer=None,
        envelope_verifier=None,
    ):
        self.sessions = sessions or SessionLocal
        self.source = source or _source
        self.department = department or _department
        self.person = person or _person
        self.notification_writer = (
            notification_writer or publish_case_communication_notification
        )
        if envelope_verifier is not None:
            self.envelope_verifier = envelope_verifier
        elif source is None:
            self.envelope_verifier = _verify_envelope
        else:
            self.envelope_verifier = None

    def _rows(self, session, *conditions, page=None, page_size=20):
        from .doctor_notification_service import Notification

        exec_options = _event_execution_options(session)
        query = (
            select(Event, Notification)
            .outerjoin(Notification, Notification.id == Event.notification_id)
            .where(*conditions)
        )
        query = query.order_by(Event.created_at.desc(), Event.id.desc())
        if page is not None:
            query = query.offset((page - 1) * page_size).limit(page_size)
        rows = session.execute(query, execution_options=exec_options).all()
        ids = [event.id for event, _ in rows]
        withdrawn = (
            set(
                session.scalars(
                    select(Event.related_event_id).where(
                        Event.action == "withdraw", Event.related_event_id.in_(ids)
                    ),
                    execution_options=exec_options,
                ).all()
            )
            if ids
            else set()
        )
        return [
            event_view(event, notice, withdrawn=event.id in withdrawn)
            for event, notice in rows
        ]

    def candidates(self, actor_id, data):
        with self.sessions() as session:
            _ensure_communication_table(session)
            _manager(self.person(session, actor_id), data["institute_id"])
            identity = tuple(data[key] for key in IDENTITY_FIELDS)
            department = normalize_department_name(self.department(session, identity))
            source = self.source(session, data, candidate=True)
            _valid_source(source)
            people = session.scalars(
                select(SysUser).where(
                    SysUser.is_active.is_(True),
                    SysUser.institute_id == identity[0],
                    _normalize_department_sql_expr(SysUser.department) == department,
                ),
                execution_options=user_owner_options(session),
            ).all()
            doctors = [
                {"id": person.id, "name": person.display_name}
                for person in people
                if "doctor" in _persistent_roles(person.role, person.roles_json)
            ]
            return {
                "source": source,
                "department": department,
                "doctors": doctors,
                "items": self._rows(
                    session,
                    *(getattr(Event, key) == source[key] for key in SOURCE_FIELDS),
                ),
            }

    def _existing(self, session, actor_id, data):
        exec_options = _event_execution_options(session)
        previous = session.scalar(
            select(Event).where(
                Event.actor_id == actor_id, Event.request_id == data["request_id"]
            ),
            execution_options=exec_options,
        )
        if previous is None:
            return None
        if any(getattr(previous, key) != data.get(key) for key in REQUEST_FIELDS):
            raise RectificationError("同一请求标识的内容已变化", 409)
        recipient = self.person(session, previous.recipient_id)
        _recipient(recipient, previous)
        rows = self._rows(
            session,
            *(getattr(Event, key) == getattr(previous, key) for key in SOURCE_FIELDS),
            Event.recipient_id == previous.recipient_id,
        )
        return next(item for item in rows if item["id"] == previous.id)

    def create(self, actor_id, data):
        if (
            data.get("action") not in LABELS
            or not isinstance(data.get("content"), str)
            or not 1 <= len(data["content"].strip()) <= 2000
            or not data.get("request_id")
        ):
            raise RectificationError("沟通动作、正文或请求标识无效", 422)
        if (data["action"] == "withdraw") != bool(data.get("related_event_id")):
            raise RectificationError("撤回须且仅须提供原催办事件", 422)
        data = {**data, "content": data["content"].strip()}
        with self.sessions() as init_session:
            _ensure_communication_table(init_session)
        try:
            with self.sessions() as session, session.begin():
                exec_options = _event_execution_options(session)
                _manager(self.person(session, actor_id), data["institute_id"])
                previous = self._existing(session, actor_id, data)
                if previous:
                    return previous
                if data["action"] == "withdraw":
                    _valid_source(data)
                    department = normalize_department_name(
                        self.department(
                            session, tuple(data[key] for key in IDENTITY_FIELDS)
                        )
                    )
                    recipient = self.person(session, data["recipient_id"])
                    if (
                        "doctor" not in recipient["roles"]
                        or recipient["institute_id"] != data["institute_id"]
                        or not _department_equals(recipient["department"], department)
                    ):
                        raise RectificationError("受领人须为同院本科室有效医生", 403)
                    original = session.scalar(
                        select(Event)
                        .where(Event.id == data["related_event_id"])
                        .with_for_update(),
                        execution_options=exec_options,
                    )
                    if (
                        not original
                        or original.action != "urge"
                        or original.recipient_id != recipient["id"]
                        or not _department_equals(original.department, department)
                        or any(
                            getattr(original, key) != data[key]
                            for key in SOURCE_FIELDS
                        )
                    ):
                        raise RectificationError(
                            "原催办与当前病历、收件人或冻结轮次不一致", 409
                        )
                    if self.envelope_verifier is not None:
                        self.envelope_verifier(session, data)
                    if session.scalar(
                        select(Event.id).where(Event.related_event_id == original.id),
                        execution_options=exec_options,
                    ):
                        raise RectificationError("该催办已撤回", 409)
                    self._rows(session, Event.id == original.id)
                    source = {key: getattr(original, key) for key in SOURCE_FIELDS}
                else:
                    source = self.source(session, data)
                    _valid_source(source)
                    if any(source[key] != data[key] for key in SOURCE_FIELDS):
                        raise RectificationError("病历沟通冻结来源已变化", 409)
                    department = normalize_department_name(
                        self.department(
                            session, tuple(data[key] for key in IDENTITY_FIELDS)
                        )
                    )
                    recipient = self.person(session, data["recipient_id"])
                    if (
                        "doctor" not in recipient["roles"]
                        or recipient["institute_id"] != source["institute_id"]
                        or not _department_equals(recipient["department"], department)
                    ):
                        raise RectificationError("受领人须为同院本科室有效医生", 403)
                event = Event(
                    id=str(uuid4()),
                    **source,
                    department=department,
                    actor_id=actor_id,
                    recipient_id=recipient["id"],
                    action=data["action"],
                    content=data["content"],
                    request_id=data["request_id"],
                    related_event_id=data.get("related_event_id"),
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                notice = self.notification_writer(session, event)
                session.add(event)
                session.flush()
                return event_view(event, notice)
        except IntegrityError as exc:
            with self.sessions() as session:
                _manager(self.person(session, actor_id), data["institute_id"])
                previous = self._existing(session, actor_id, data)
                if previous:
                    return previous
            raise RectificationError(
                "请求或原催办已被并发处理，请刷新核对", 409
            ) from exc

    def inbox(self, actor_id, page=1, page_size=20):
        from .doctor_notification_service import Notification

        if (
            type(page) is not int
            or type(page_size) is not int
            or page < 1
            or not 1 <= page_size <= 100
        ):
            raise RectificationError("分页参数无效", 422)
        with self.sessions() as session:
            _ensure_communication_table(session)
            exec_options = _event_execution_options(session)
            actor = self.person(session, actor_id)
            if (
                "doctor" not in actor["roles"]
                or not actor["institute_id"]
                or not actor["department"]
            ):
                raise RectificationError("仅有可信院科的医生可读取病历沟通", 403)
            normalized_actor_dept = normalize_department_name(actor["department"])
            conditions = (
                Event.recipient_id == actor_id,
                Event.institute_id == actor["institute_id"],
                _normalize_department_sql_expr(Event.department) == normalized_actor_dept,
                Notification.id == Event.notification_id,
                Notification.recipient_id == actor_id,
                Notification.source_key == SOURCE,
                Notification.identity_version == 1,
                Notification.related_type == "case_communication",
                Notification.related_id == Event.id,
                *(
                    getattr(Notification, key) == getattr(Event, key)
                    for key in IDENTITY_FIELDS
                ),
                *(
                    func.length(func.trim(getattr(Event, key))) > 0
                    for key in SOURCE_FIELDS
                ),
                Event.scene.in_(("running", "final")),
            )
            total = session.scalar(
                select(func.count())
                .select_from(Event)
                .join(Notification, Notification.id == Event.notification_id)
                .where(*conditions),
                execution_options=exec_options,
            )
            rows = self._rows(session, *conditions, page=page, page_size=page_size)
            return {
                "items": rows,
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": page * page_size < total,
            }

    def detail(self, actor_id, event_id):
        with self.sessions() as session:
            _ensure_communication_table(session)
            exec_options = _event_execution_options(session)
            event = session.scalar(
                select(Event).where(Event.id == event_id),
                execution_options=exec_options,
            )
            if not event:
                raise RectificationError("病历沟通不存在", 404)
            _recipient(self.person(session, actor_id), event)
            history = self._rows(
                session,
                Event.recipient_id == actor_id,
                _normalize_department_sql_expr(Event.department)
                == normalize_department_name(event.department),
                *(getattr(Event, key) == getattr(event, key) for key in SOURCE_FIELDS),
            )
            result = next(item for item in history if item["id"] == event.id)
            return result | {"history": history}

    def read(self, actor_id, event_id):
        from .doctor_notification_service import DoctorNotificationService

        detail = self.detail(actor_id, event_id)
        DoctorNotificationService(self.sessions, self.person).mark_read(
            actor_id, detail["notification_id"]
        )
        return self.detail(actor_id, event_id)
