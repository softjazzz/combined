"""统一消息读取及医生交互提醒；已读状态不代替整改/申诉业务状态。"""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, exists, func, inspect, or_, select, update
from sqlalchemy.orm import DeclarativeBase

from ..database.connection import SessionLocal
from ..database.models.v36_reports import DefectRectification as Task
from ..database.models.v36_reports import Notification as ReportNotification
from .defect_rectification_service import RectificationError, _person
from .modern_appeal_service import QCAppeal as Appeal

SOURCE = "v5_doctor_feedback"


class _Base(DeclarativeBase):
    pass


class Notification(_Base):
    __table__ = ReportNotification.__table__.to_metadata(_Base.metadata, schema="qc")


def publish_doctor_notification(
    session, source, *, event_id, action, actor_id, appeal=False, comment=None
):
    labels = (
        {"approve": "申诉审核通过", "reject": "申诉已驳回"}
        if appeal
        else {
            "assign": "新的整改任务",
            "urge": "整改催办提醒",
            "withdraw_urge": "整改催办已撤回",
            "approve": "整改验收通过",
            "reject": "整改驳回待重提",
        }
    )
    if action not in labels:
        return
    recipient = source.appellant_id if appeal else source.assignee_id
    kind = "modern_appeal" if appeal else "rectification"
    comment = (
        comment
        if comment is not None
        else (
            source.review_result
            if appeal
            else (
                source.review_comment
                if action in {"approve", "reject"}
                else source.requirement
            )
        )
    )
    session.add(
        Notification(
            id=str(uuid5(NAMESPACE_URL, f"{SOURCE}:{kind}:{event_id}")),
            type="appeal_result"
            if appeal
            else (
                "defect_urge" if action in {"urge", "withdraw_urge"} else "remediation"
            ),
            title=labels[action],
            content=f"{ {'running':'运行','final':'终末','outpatient_emergency':'门急诊'}.get(source.scene,'未知场景')} · {source.visit_id} · {source.target_id}。{comment or ''}",
            record_id=f"feedback:{kind}:{source.id}",
            identity_version=1,
            source_key=SOURCE,
            institute_id=source.institute_id,
            patient_id=source.patient_id,
            visit_id=source.visit_id,
            severity="warning" if action in {"assign", "urge", "reject"} else "info",
            sender_id=actor_id,
            recipient_id=recipient,
            related_type=kind,
            related_id=source.id,
            is_read=False,
            created_at=datetime.utcnow(),
        )
    )


class DoctorNotificationService:
    def __init__(self, session_factory=None, person_loader=None):
        self.sessions = session_factory or SessionLocal
        self.person = person_loader or _person

    def _predicate(self, actor, session):
        legacy = or_(
            Notification.source_key.is_(None), Notification.source_key != SOURCE
        )
        modern = False
        if "doctor" in actor["roles"] and actor["institute_id"] and actor["department"]:
            identity = ["institute_id", "patient_id", "visit_id"]
            task = exists(
                select(Task.id).where(
                    Task.id == Notification.related_id,
                    Task.assignee_id == actor["id"],
                    Task.department == actor["department"],
                    *(
                        getattr(Task, key) == getattr(Notification, key)
                        for key in identity
                    ),
                )
            )
            appeal = exists(
                select(Appeal.id).where(
                    Appeal.id == Notification.related_id,
                    Appeal.appellant_id == actor["id"],
                    Appeal.case_department == actor["department"],
                    *(
                        getattr(Appeal, key) == getattr(Notification, key)
                        for key in identity
                    ),
                )
            )
            # 沟通表属于独立历史前置；缺表时只拒绝此类消息，不影响既有整改/申诉。
            communication = False
            connection = session.connection()
            schema = None if connection.dialect.name == "sqlite" else "qc"
            if inspect(connection).has_table("qc_case_communications", schema=schema):
                from ..database.models.case_communication import CaseCommunication

                communication = exists(
                    select(CaseCommunication.id).where(
                        CaseCommunication.id == Notification.related_id,
                        CaseCommunication.recipient_id == actor["id"],
                        CaseCommunication.department == actor["department"],
                        CaseCommunication.notification_id == Notification.id,
                        CaseCommunication.scene.in_(("running", "final")),
                        *(
                            func.trim(getattr(CaseCommunication, key)) != ""
                            for key in (
                                "patient_id", "visit_id", "root_job_id", "envelope_id",
                                "rule_set_key", "rule_set_version",
                            )
                        ),
                        *(
                            getattr(CaseCommunication, key) == getattr(Notification, key)
                            for key in identity
                        ),
                    )
                )
            modern = and_(
                Notification.source_key == SOURCE,
                Notification.identity_version == 1,
                Notification.institute_id == actor["institute_id"],
                or_(
                    and_(Notification.related_type == "rectification", task),
                    and_(Notification.related_type == "modern_appeal", appeal),
                    and_(Notification.related_type == "case_communication", communication),
                ),
            )
        return and_(Notification.recipient_id == actor["id"], or_(legacy, modern))

    def _view(self, row, actor):
        item = {
            column.name: (
                getattr(row, column.name).replace(tzinfo=timezone.utc).isoformat()
                if isinstance(getattr(row, column.name), datetime)
                else getattr(row, column.name)
            )
            for column in row.__table__.columns
        }
        if row.source_key == SOURCE:
            # EXISTS 已证明对象冻结科室与持久账号一致。
            item["department"] = actor["department"]
            item["interaction_target"] = {
                "kind": row.related_type,
                "id": row.related_id,
            }
        return item

    def list(self, actor_id, *, type=None, is_read=None, page=1, page_size=20):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            predicate = self._predicate(actor, session)
            statement = select(Notification).where(predicate)
            if type:
                statement = statement.where(Notification.type == type)
            if is_read is not None:
                statement = statement.where(Notification.is_read == is_read)
            total = session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            unread = session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(predicate, Notification.is_read.is_(False))
            )
            rows = session.scalars(
                statement.order_by(Notification.created_at.desc(), Notification.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "items": [self._view(row, actor) for row in rows],
                "total": total,
                "unread_count": unread,
                "page": page,
                "page_size": page_size,
            }

    def overview_rows(self, actor_id, start, end):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            rows = session.scalars(
                select(Notification)
                .where(
                    self._predicate(actor, session),
                    Notification.created_at >= start,
                    Notification.created_at < end,
                )
                .order_by(Notification.created_at.desc(), Notification.id)
                .limit(500)
            ).all()
            return [self._view(row, actor) for row in rows]

    def mark_read(self, actor_id, notification_id=None):
        with self.sessions() as session, session.begin():
            actor = self.person(session, actor_id)
            statement = update(Notification).where(self._predicate(actor, session))
            if notification_id:
                statement = statement.where(Notification.id == notification_id)
            else:
                statement = statement.where(Notification.is_read.is_(False))
            count = session.execute(
                statement.values(is_read=True, read_at=datetime.utcnow())
            ).rowcount
            if notification_id and count == 0:
                raise RectificationError("通知不存在或不在授权范围", 404)
            return count
