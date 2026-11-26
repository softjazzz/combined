"""统一消息读取及医生交互提醒；已读状态不代替整改/申诉业务状态。"""

from datetime import datetime, timezone
import re
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import MetaData, and_, exists, func, inspect, or_, select, update
from sqlalchemy.orm import DeclarativeBase

from ..database import connection as db_connection
from ..database.connection import SessionLocal
from ..database.models.v36_reports import DefectRectification as Task
from ..database.models.v36_reports import Notification as ReportNotification
from ..database.models.v36_reports import SysUser
from .defect_rectification_service import (
    MANAGERS,
    RectificationError,
    _person,
    _effective_persistent_roles,
)
from .modern_appeal_service import QCAppeal as Appeal
from .user_scope_owner import user_owner_options, resolve_user_owner_schema
from .qc_result_ready_notification import SOURCE as RESULT_SOURCE, ready_predicate, result_tables

SOURCE = "v5_doctor_feedback"
QC_SOURCE = "v5_qc_feedback"
REGISTRATION_SOURCE = "v5_account_registration"
GLOBAL_ADMIN_ROLES = {"admin", "super_admin"}
MODERN_SOURCES = (SOURCE, QC_SOURCE, REGISTRATION_SOURCE, RESULT_SOURCE)
ACCOUNT_REGISTRATION_RELATED_TYPES = (
    "account_registration",
    "account_registration_result",
)
_LEGACY_TYPE_TO_CANONICAL = {
    "remediation_assigned": "remediation",
    "remediation_submitted": "remediation",
    "remediation_approved": "remediation",
    "appeal_created": "appeal_result",
    "appeal_reviewed": "appeal_result",
    "task_assigned": "task_assign",
}
_UUID_PATTERN = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_UUID_FULL_RE = re.compile(rf"^{_UUID_PATTERN}$")
_UUID_RE = re.compile(_UUID_PATTERN)
_RECORD_UUID_ANALYSIS_DONE_RE = re.compile(
    rf"病历\s*{_UUID_PATTERN}\s*analysis\s*完成",
    re.IGNORECASE,
)
_RECORD_UUID_RE = re.compile(rf"病历\s*{_UUID_PATTERN}")
_ANALYSIS_STAGE_RE = re.compile(
    r"(?<![A-Za-z0-9_])analysis(?=(?:[\u4e00-\u9fff]|[^A-Za-z0-9_]|$))",
    re.IGNORECASE,
)
_CJK_REDUNDANT_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])")


def _is_account_registration_row(row) -> bool:
    return (
        row.type == "account_registration"
        or row.related_type in ACCOUNT_REGISTRATION_RELATED_TYPES
        or row.source_key == REGISTRATION_SOURCE
    )


def _is_account_registration_expr():
    return or_(
        Notification.type == "account_registration",
        Notification.related_type.in_(ACCOUNT_REGISTRATION_RELATED_TYPES),
        Notification.source_key == REGISTRATION_SOURCE,
    )


def _is_not_account_registration_expr():
    return and_(
        or_(Notification.type.is_(None), Notification.type != "account_registration"),
        or_(
            Notification.related_type.is_(None),
            Notification.related_type.not_in(ACCOUNT_REGISTRATION_RELATED_TYPES),
        ),
        or_(
            Notification.source_key.is_(None),
            Notification.source_key != REGISTRATION_SOURCE,
        ),
    )


def _canonical_notification_type(row) -> str | None:
    if _is_account_registration_row(row):
        return "account_registration"
    if row.source_key == RESULT_SOURCE or row.related_type == "qc_result_ready":
        return "qc_result_ready"
    if row.related_type == "case_communication":
        return "case_communication"
    if row.related_type == "modern_appeal":
        return "appeal_result"
    if row.related_type == "rectification" and row.type != "defect_urge":
        return "remediation"
    raw_type = row.type
    if isinstance(raw_type, str):
        return _LEGACY_TYPE_TO_CANONICAL.get(raw_type, raw_type)
    return raw_type


def _type_filter_predicate(notification_type: str):
    if notification_type == "account_registration":
        return _is_account_registration_expr()
    if notification_type == "system":
        return and_(Notification.type == "system", _is_not_account_registration_expr())
    if notification_type == "qc_result_ready":
        return or_(
            Notification.type == "qc_result_ready",
            Notification.related_type == "qc_result_ready",
            Notification.source_key == RESULT_SOURCE,
        )
    if notification_type == "case_communication":
        return or_(
            Notification.type == "case_communication",
            Notification.related_type == "case_communication",
        )
    if notification_type == "appeal_result":
        return or_(
            Notification.type.in_(
                ("appeal_result", "appeal_created", "appeal_reviewed")
            ),
            Notification.related_type == "modern_appeal",
        )
    if notification_type == "remediation":
        return or_(
            Notification.type.in_(
                (
                    "remediation",
                    "remediation_assigned",
                    "remediation_submitted",
                    "remediation_approved",
                )
            ),
            and_(
                Notification.related_type == "rectification",
                or_(Notification.type.is_(None), Notification.type != "defect_urge"),
            ),
        )
    if notification_type == "task_assign":
        return Notification.type.in_(("task_assign", "task_assigned"))
    return Notification.type == notification_type


def _readable_visit_label(visit_id: str | None) -> str | None:
    text = str(visit_id or "").strip()
    if not text or _UUID_FULL_RE.match(text):
        return None
    return text


def sanitize_legacy_notification_text(
    text: str | None, *, visit_id: str | None = None
) -> str | None:
    """读取投影层清洗历史通知中的英文阶段码（如 analysis）与裸露 36 位 UUID。"""
    if not isinstance(text, str) or not text:
        return text
    cleaned = text
    visit_label = _readable_visit_label(visit_id)
    if _RECORD_UUID_ANALYSIS_DONE_RE.search(cleaned):
        replacement = f"病历 {visit_label} 分析完成" if visit_label else "该病历分析完成"
        cleaned = _RECORD_UUID_ANALYSIS_DONE_RE.sub(replacement, cleaned)
    if _RECORD_UUID_RE.search(cleaned):
        replacement = f"病历 {visit_label}" if visit_label else "该病历"
        cleaned = _RECORD_UUID_RE.sub(replacement, cleaned)
    if _UUID_RE.search(cleaned):
        replacement = f"病历 {visit_label}" if visit_label else "该病历"
        cleaned = _UUID_RE.sub(replacement, cleaned)
    if _ANALYSIS_STAGE_RE.search(cleaned):
        cleaned = _ANALYSIS_STAGE_RE.sub("病历分析", cleaned)
    if cleaned != text:
        cleaned = cleaned.replace("该病历 病历分析", "该病历分析")
        cleaned = cleaned.replace("该病历病历分析", "该病历分析")
        cleaned = _CJK_REDUNDANT_SPACE_RE.sub("", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


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
                SysUser.is_active.is_(True),
                or_(
                    SysUser.institute_id == source.institute_id,
                    and_(
                        SysUser.institute_id.is_(None),
                        or_(
                            SysUser.role.in_(tuple(GLOBAL_ADMIN_ROLES)),
                            SysUser.roles_json.is_not(None),
                        ),
                    ),
                ),
            ),
            execution_options=user_owner_options(session),
        )
        .scalars()
        .all()
    )
    same_inst_roles = (
        {"admin", "super_admin", "qc_manager"}
        if appeal
        else (MANAGERS | GLOBAL_ADMIN_ROLES)
    )
    eligible = []
    for row in rows:
        if row.id == actor_id:
            continue
        roles = _effective_persistent_roles(row.role, row.roles_json)
        if row.institute_id == source.institute_id:
            if roles & same_inst_roles:
                eligible.append(row)
        elif row.institute_id is None and (roles & GLOBAL_ADMIN_ROLES):
            eligible.append(row)
    # 优先原派发人（含无机构全局 admin）；不能处理申诉或已停用时先转同机构主管，再兜底全局 admin。
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
    same_institute_managers = [
        row
        for row in eligible
        if row.institute_id == source.institute_id
        and _effective_persistent_roles(row.role, row.roles_json)
        & {"admin", "super_admin", "qc_manager"}
    ]
    global_admins = [
        row
        for row in eligible
        if row.institute_id is None
        and _effective_persistent_roles(row.role, row.roles_json) & GLOBAL_ADMIN_ROLES
    ]
    recipients = preferred or same_institute_managers or global_admins
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


def _qc_schema(connection=None) -> str | None:
    if connection is not None and connection.dialect.name == "sqlite":
        return None
    return (
        "qc"
        if str(getattr(db_connection, "DB_SCHEMA_MODE", "") or "").strip().lower()
        == "split"
        else None
    )


class _Base(DeclarativeBase):
    pass


class Notification(_Base):
    __table__ = ReportNotification.__table__.to_metadata(
        _Base.metadata, schema=_qc_schema()
    )


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
        {
            "approve": "申诉审核通过",
            "reject": "申诉已驳回",
            "supersede": "原轮次申诉已因新轮质控终结",
            "close_stale": "原轮次申诉已因新轮质控终结",
        }
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
            Notification.source_key.not_in((SOURCE, QC_SOURCE, REGISTRATION_SOURCE, RESULT_SOURCE)),
        )
        modern = False
        qc_feedback = False
        is_global_admin = (
            "sync_admin" in actor["roles"]
            or (bool(actor["roles"] & GLOBAL_ADMIN_ROLES) and not actor["institute_id"])
        )
        if (
            actor["roles"] & (MANAGERS | GLOBAL_ADMIN_ROLES) and actor["institute_id"]
        ) or is_global_admin:
            identity = ("institute_id", "patient_id", "visit_id")
            task_institute_cond = (
                (Task.institute_id.is_not(None), func.trim(Task.institute_id) != "")
                if is_global_admin
                else (Task.institute_id == actor["institute_id"],)
            )
            task = exists(
                select(Task.id).where(
                    Task.id == Notification.related_id,
                    *task_institute_cond,
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
            if actor["roles"] & {"admin", "super_admin", "qc_manager"}:
                appeal_institute_cond = (
                    (
                        Appeal.institute_id.is_not(None),
                        func.trim(Appeal.institute_id) != "",
                    )
                    if is_global_admin
                    else (Appeal.institute_id == actor["institute_id"],)
                )
                appeal = exists(
                    select(Appeal.id).where(
                        Appeal.id == Notification.related_id,
                        *appeal_institute_cond,
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
            notif_institute_cond = (
                (
                    Notification.institute_id.is_not(None),
                    func.trim(Notification.institute_id) != "",
                )
                if is_global_admin
                else (Notification.institute_id == actor["institute_id"],)
            )
            qc_feedback = and_(
                Notification.source_key == QC_SOURCE,
                Notification.identity_version == 1,
                *notif_institute_cond,
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
            schema = _qc_schema(connection)
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
            reviewer = bool(actor["roles"] & {"admin", "sync_admin", "super_admin"})
            if reviewer and actor["institute_id"] and not (actor["roles"] & {"sync_admin", "super_admin"}):
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
            Notification.recipient_id == actor["id"],
            or_(legacy, modern, qc_feedback, registration, ready_predicate(session, actor, Notification))
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
        if row.source_key == RESULT_SOURCE:
            item["interaction_target"] = {"kind": "qc_result_ready", "id": row.id}
        item["type"] = _canonical_notification_type(row)
        if row.source_key not in MODERN_SOURCES:
            item["title"] = sanitize_legacy_notification_text(
                item.get("title"), visit_id=row.visit_id
            )
            item["content"] = sanitize_legacy_notification_text(
                item.get("content"), visit_id=row.visit_id
            )
        return item

    def result_ready(self, actor_id, notification_id, loader):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            row = session.scalar(select(Notification).where(
                Notification.id == notification_id,
                Notification.source_key == RESULT_SOURCE,
                Notification.recipient_id == actor_id,
            ))
            tables = result_tables(session)
            if row is None or not tables:
                raise RectificationError("结果通知不存在或已失效", 404)
            jobs, _ = tables
            # 读取期间锁定同一根任务，避免重试把旧通知悄悄换成新一轮结果。
            session.execute(select(jobs.c.id).where(jobs.c.id == row.record_id).with_for_update(read=True)).first()
            if not session.scalar(select(Notification.id).where(
                Notification.id == notification_id, self._predicate(actor, session)
            )):
                raise RectificationError("结果通知不存在或已失效", 404)
            return loader(row.record_id, actor_id)

    def list(self, actor_id, *, type=None, is_read=None, page=1, page_size=20):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            predicate = self._predicate(actor, session)
            statement = select(Notification).where(predicate)
            if type:
                statement = statement.where(_type_filter_predicate(type))
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
