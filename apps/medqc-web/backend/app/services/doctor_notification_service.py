"""统一消息读取及医生交互提醒；已读状态不代替整改/申诉业务状态。"""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import MetaData, and_, exists, func, inspect, or_, select, update
from sqlalchemy.orm import DeclarativeBase

from ..database.connection import SessionLocal
from ..database.models.v36_reports import DefectRectification as Task
from ..database.models.v36_reports import Notification as ReportNotification
from ..database.models.v36_reports import SysUser
from .defect_rectification_service import (
    MANAGERS,
    RectificationError,
    _person,
    _persistent_roles,
)
from .modern_appeal_service import QCAppeal as Appeal
from .user_scope_owner import user_owner_options, resolve_user_owner_schema

SOURCE = "v5_doctor_feedback"
QC_SOURCE = "v5_qc_feedback"
REGISTRATION_SOURCE = "v5_account_registration"


def _publish_qc_notification(
    session, source, *, event_id, action, actor_id, appeal, comment
):
    labels = (
        {"create": "医生提交了申诉", "withdraw": "医生撤回了申诉"}
        if appeal
        else {"submit": "医生提交了整改"}
    )
    rows = (
        session.execute(
            select(SysUser).where(
                SysUser.is_active.is_(True), SysUser.institute_id == source.institute_id
            ),
            execution_options=user_owner_options(session),
        )
        .scalars()
        .all()
    )
    eligible = [
        row
        for row in rows
        if row.id != actor_id
        and _persistent_roles(row.role, row.roles_json)
        & ({"admin", "qc_manager"} if appeal else MANAGERS)
    ]
    # 优先原派发人；不能处理申诉或已停用时转同机构主管，避免丢给无权审核者。
    creator_id = getattr(source, "creator_id", None)
    if appeal:
        from .modern_appeal_service import SOURCE_FIELDS

        creator_id = session.scalar(
            select(Task.creator_id)
            .where(
                Task.assignee_id == source.appellant_id,
                *(getattr(Task, key) == getattr(source, key) for key in SOURCE_FIELDS),
            )
            .limit(1)
        )
    preferred = [row for row in eligible if row.id == creator_id]
    recipients = preferred or [
        row
        for row in eligible
        if _persistent_roles(row.role, row.roles_json) & {"admin", "qc_manager"}
    ]
    if not recipients:
        raise RectificationError(
            "没有可接收反馈的同机构质控账号，请联系管理员配置", 409
        )
    kind = "modern_appeal" if appeal else "rectification"
    for recipient in recipients:
        session.add(
            Notification(
                id=str(
                    uuid5(
                        NAMESPACE_URL, f"{QC_SOURCE}:{kind}:{event_id}:{recipient.id}"
                    )
                ),
                type="appeal_result" if appeal else "remediation",
                title=labels[action],
                content=f"{ {'running': '运行', 'final': '终末'}.get(source.scene, '未知场景') } · {source.visit_id} · {source.target_id}。{comment or ''}",
                record_id=f"feedback:{kind}:{source.id}",
                identity_version=1,
                source_key=QC_SOURCE,
                institute_id=source.institute_id,
                patient_id=source.patient_id,
                visit_id=source.visit_id,
                severity="info",
                sender_id=actor_id,
                recipient_id=recipient.id,
                related_type=kind,
                related_id=source.id,
                is_read=False,
                created_at=datetime.utcnow(),
            )
        )


class _Base(DeclarativeBase):
    pass


class Notification(_Base):
    __table__ = ReportNotification.__table__.to_metadata(_Base.metadata, schema="qc")


def publish_doctor_notification(
    session, source, *, event_id, action, actor_id, appeal=False, comment=None
):
    if (appeal and action in {"create", "withdraw"}) or (
        not appeal and action == "submit"
    ):
        return _publish_qc_notification(
            session,
            source,
            event_id=event_id,
            action=action,
            actor_id=actor_id,
            appeal=appeal,
            comment=comment,
        )
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
            content=f"{ {'running': '运行', 'final': '终末', 'outpatient_emergency': '门急诊'}.get(source.scene, '未知场景') } · {source.visit_id} · {source.target_id}。{comment or ''}",
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
            Notification.source_key.is_(None),
            Notification.source_key.not_in((SOURCE, QC_SOURCE, REGISTRATION_SOURCE)),
        )
        modern = False
        qc_feedback = False
        if actor["roles"] & MANAGERS and actor["institute_id"]:
            identity = ("institute_id", "patient_id", "visit_id")
            task = exists(
                select(Task.id).where(
                    Task.id == Notification.related_id,
                    Task.institute_id == actor["institute_id"],
                    Task.assignee_id != actor["id"],
                    Task.scene.in_(("running", "final")),
                    Task.target_kind.in_(("canonical_defect", "task_manual_defect")),
                    *(
                        func.trim(getattr(Task, key)) != ""
                        for key in (
                            "patient_id",
                            "visit_id",
                            "root_job_id",
                            "envelope_id",
                            "target_id",
                            "rule_set_key",
                            "rule_set_version",
                        )
                    ),
                    *(
                        getattr(Task, key) == getattr(Notification, key)
                        for key in identity
                    ),
                )
            )
            appeal = False
            if actor["roles"] & {"admin", "qc_manager"}:
                appeal = exists(
                    select(Appeal.id).where(
                        Appeal.id == Notification.related_id,
                        Appeal.institute_id == actor["institute_id"],
                        Appeal.appellant_id != actor["id"],
                        Appeal.scene.in_(("running", "final")),
                        Appeal.target_kind.in_(
                            ("canonical_defect", "task_manual_defect")
                        ),
                        func.trim(Appeal.case_department) != "",
                        *(
                            func.trim(getattr(Appeal, key)) != ""
                            for key in (
                                "patient_id",
                                "visit_id",
                                "root_job_id",
                                "envelope_id",
                                "target_id",
                                "rule_set_key",
                                "rule_set_version",
                            )
                        ),
                        *(
                            getattr(Appeal, key) == getattr(Notification, key)
                            for key in identity
                        ),
                    )
                )
            qc_feedback = and_(
                Notification.source_key == QC_SOURCE,
                Notification.identity_version == 1,
                Notification.institute_id == actor["institute_id"],
                or_(
                    and_(Notification.related_type == "rectification", task),
                    and_(Notification.related_type == "modern_appeal", appeal),
                ),
            )
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
                                "patient_id",
                                "visit_id",
                                "root_job_id",
                                "envelope_id",
                                "rule_set_key",
                                "rule_set_version",
                            )
                        ),
                        *(
                            getattr(CaseCommunication, key)
                            == getattr(Notification, key)
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
                    and_(
                        Notification.related_type == "case_communication", communication
                    ),
                ),
            )
        registration = False
        owner = resolve_user_owner_schema(session)
        if inspect(session.connection()).has_table("sys_user_registrations", schema=owner):
            from ..database.models.account_registration import registration_tables

            users = SysUser.__table__.to_metadata(MetaData(), schema=owner)
            applications, _ = registration_tables(users)
            application = exists(select(applications.c.user_id).where(
                applications.c.user_id == Notification.related_id,
                applications.c.requested_institute_id == Notification.institute_id,
            ))
            reviewer = "admin" in actor["roles"]
            if reviewer and actor["institute_id"]:
                reviewer = Notification.institute_id == actor["institute_id"]
            registration = and_(
                Notification.source_key == REGISTRATION_SOURCE,
                Notification.identity_version == 1,
                application,
                or_(
                    and_(Notification.related_type == "account_registration", reviewer),
                    and_(Notification.related_type == "account_registration_result", Notification.related_id == actor["id"]),
                ),
            )
        return and_(
            Notification.recipient_id == actor["id"], or_(legacy, modern, qc_feedback, registration)
        )

    def _view(self, row, actor, session):
        item = {
            column.name: (
                getattr(row, column.name).replace(tzinfo=timezone.utc).isoformat()
                if isinstance(getattr(row, column.name), datetime)
                else getattr(row, column.name)
            )
            for column in row.__table__.columns
        }
        if row.source_key in (SOURCE, QC_SOURCE):
            # EXISTS 已证明对象冻结科室与持久账号一致。
            if row.source_key == QC_SOURCE:
                model = Task if row.related_type == "rectification" else Appeal
                column = Task.department if model is Task else Appeal.case_department
                item["department"] = session.scalar(
                    select(column).where(model.id == row.related_id)
                )
            else:
                item["department"] = actor["department"]
            item["interaction_target"] = {
                "kind": row.related_type,
                "id": row.related_id,
            }
        if row.source_key == REGISTRATION_SOURCE:
            item["interaction_target"] = {"kind": row.related_type, "id": row.related_id}
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
                "items": [self._view(row, actor, session) for row in rows],
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
            return [self._view(row, actor, session) for row in rows]

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
