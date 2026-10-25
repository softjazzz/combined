"""V5 已派发现代缺陷申诉；只冻结引用，不修改缺陷、整改或保存结果。"""

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase

from ..database.connection import SessionLocal
from ..database.models.v36_reports import DefectRectification
from ..database.models.v36_reports import QCAppeal as ReportAppeal
from ..database.models.v36_reports import QCAppealReview as ReportAppealReview
from .defect_rectification_service import RectificationError, _department, _person
from .feedback_result_source import resolve_target

SOURCE_FIELDS = (
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
OPEN = ("pending", "reviewing")
STATES = (*OPEN, "approved", "rejected", "withdrawn")
REVIEWERS = {"admin", "qc_manager"}


class _OwnerBase(DeclarativeBase):
    pass


# 复用报表合同但固定表 owner；不能给整个会话套 qc 映射（会污染 CDM 查询）。
class QCAppeal(_OwnerBase):
    __table__ = ReportAppeal.__table__.to_metadata(_OwnerBase.metadata, schema="qc")


class QCAppealReview(_OwnerBase):
    __table__ = ReportAppealReview.__table__.to_metadata(
        _OwnerBase.metadata, schema="qc"
    )


def _reviewer(actor):
    return bool(actor["roles"] & REVIEWERS)


def _view(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _authorized(actor, row):
    if "admin" not in actor["roles"] and (
        not actor["institute_id"] or actor["institute_id"] != row.institute_id
    ):
        raise RectificationError("无权访问该机构申诉", 403)
    if not _reviewer(actor) and (
        "doctor" not in actor["roles"]
        or row.appellant_id != actor["id"]
        or not actor["department"]
        or actor["department"] != row.case_department
    ):
        raise RectificationError("仅可访问本人本科室申诉", 403)


def _modern(statement, model=QCAppeal):
    # 历史旧主键申诉留在旧入口，不猜测来源或串接同号病历。
    return statement.where(
        model.target_kind.in_(("canonical_defect", "task_manual_defect")),
        model.scene.in_(("running", "final")),
        *(func.trim(getattr(model, key)) != "" for key in SOURCE_FIELDS),
        func.trim(model.case_department) != "",
    )


class ModernAppealService:
    def __init__(
        self,
        session_factory=None,
        person_loader=None,
        source_loader=None,
        department_loader=None,
    ):
        self.sessions = session_factory or SessionLocal
        self.person = person_loader or _person
        self.source = source_loader or resolve_target
        self.department = department_loader or _department

    @contextmanager
    def _session(self):
        with self.sessions() as session:
            # ORM flush 也固定 qc owner；账号查询仍显式使用其 sys/public owner。
            with session.begin():
                yield session

    def create(self, actor_id, *, rectification_id, reason):
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000:
            raise RectificationError("申诉原因须为10至2000字")
        try:
            with self._session() as session:
                actor = self.person(session, actor_id)
                task = session.scalar(
                    select(DefectRectification)
                    .where(
                        DefectRectification.id == rectification_id,
                    )
                    .with_for_update(read=True)
                )
                if task is None:
                    raise RectificationError("整改对象不存在", 404)
                # 显式派发只授权这一条缺陷，不开放医生端全量规则结果。
                if (
                    "doctor" not in actor["roles"]
                    or task.assignee_id != actor_id
                    or not actor["institute_id"]
                    or task.institute_id != actor["institute_id"]
                    or not actor["department"]
                    or task.department != actor["department"]
                ):
                    raise RectificationError("仅指定医生可申诉本科室已派发缺陷", 403)
                identity = tuple(getattr(task, key) for key in SOURCE_FIELDS[:3])
                department = self.department(session, identity)
                if department != task.department:
                    raise RectificationError("病例科室已变化，请重新核对派发", 409)
                data = {key: getattr(task, key) for key in SOURCE_FIELDS}
                target = self.source(session, data)
                if task.scene not in {"running", "final"} or any(
                    not data[key] or target.get(key) != data[key]
                    for key in SOURCE_FIELDS
                ):
                    raise RectificationError("申诉缺陷冻结来源不一致", 409)
                now = datetime.now(timezone.utc)
                row = QCAppeal(
                    id=str(uuid4()),
                    **data,
                    qc_result_id=None,
                    record_id=None,
                    appeal_type="defect",
                    defect_item=task.target_id,
                    reason=reason.strip(),
                    priority="medium",
                    appellant_id=actor_id,
                    appellant_name=actor["name"],
                    appellant_department=department,
                    case_department=department,
                    status="pending",
                    created_at=now.replace(tzinfo=None),
                    updated_at=now,
                )
                session.add(row)
                session.flush()
                return _view(row)
        except IntegrityError as exc:
            constraint = getattr(
                getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
            )
            if constraint == "uq_qc_appeals_open_target" or (
                "UNIQUE constraint failed" in str(exc.orig)
                and "qc_appeals.appellant_id" in str(exc.orig)
            ):
                raise RectificationError("同一轮缺陷已有未完结申诉，请刷新核对", 409) from exc
            raise

    def _predicate(self, actor, statement):
        statement = _modern(statement)
        if not _reviewer(actor) and "doctor" not in actor["roles"]:
            raise RectificationError("仅医生与申诉审核人员可访问", 403)
        if "admin" not in actor["roles"]:
            if not actor["institute_id"]:
                raise RectificationError("账号缺少可信机构", 403)
            statement = statement.where(QCAppeal.institute_id == actor["institute_id"])
        if not _reviewer(actor):
            if not actor["department"]:
                raise RectificationError("账号缺少可信科室", 403)
            statement = statement.where(
                QCAppeal.appellant_id == actor["id"],
                QCAppeal.case_department == actor["department"],
            )
        return statement

    def list(self, actor_id, *, state=None, scene=None, page=1, page_size=10):
        if state not in (None, "open", *STATES) or scene not in (
            None,
            "running",
            "final",
        ):
            raise RectificationError("申诉筛选无效")
        if not 1 <= page <= 10000 or not 1 <= page_size <= 100:
            raise RectificationError("申诉分页无效")
        with self._session() as session:
            actor = self.person(session, actor_id)
            statement = self._predicate(actor, select(QCAppeal))
            if scene:
                statement = statement.where(QCAppeal.scene == scene)
            # 待办计数与下钻共用同一授权、场景及状态条件。
            pending = statement.where(QCAppeal.status.in_(OPEN))
            pending_count = session.scalar(
                select(func.count()).select_from(pending.subquery())
            )
            if state:
                statement = statement.where(
                    QCAppeal.status.in_(OPEN)
                    if state == "open"
                    else QCAppeal.status == state
                )
            total = session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            rows = session.scalars(
                statement.order_by(QCAppeal.created_at.desc(), QCAppeal.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return {
                "items": [_view(row) for row in rows],
                "total": total,
                "pending_count": pending_count,
                "page": page,
                "page_size": page_size,
            }

    def detail(self, actor_id, appeal_id):
        with self._session() as session:
            actor = self.person(session, actor_id)
            row = session.scalar(
                self._predicate(actor, select(QCAppeal)).where(QCAppeal.id == appeal_id)
            )
            if row is None:
                raise RectificationError("申诉不存在或不在授权范围", 404)
            events = session.scalars(
                select(QCAppealReview)
                .where(QCAppealReview.appeal_id == row.id)
                .order_by(QCAppealReview.created_at, QCAppealReview.id)
            ).all()
            return {**_view(row), "events": [_view(event) for event in events]}

    def transition(self, actor_id, appeal_id, *, expected_status, action, comment):
        if expected_status not in OPEN or action not in {
            "approve",
            "reject",
            "withdraw",
        }:
            raise RectificationError("申诉操作无效")
        if not isinstance(comment, str) or not 10 <= len(comment.strip()) <= 2000:
            raise RectificationError("处理意见须为10至2000字")
        with self._session() as session:
            actor = self.person(session, actor_id)
            row = session.scalar(
                _modern(select(QCAppeal))
                .where(QCAppeal.id == appeal_id)
                .with_for_update()
            )
            if row is None:
                raise RectificationError("现代申诉不存在", 404)
            _authorized(actor, row)
            if row.status != expected_status:
                raise RectificationError("申诉状态已变化，请刷新核对", 409)
            if action == "withdraw":
                if "doctor" not in actor["roles"] or row.appellant_id != actor_id:
                    raise RectificationError("仅申诉医生本人可以撤回", 403)
                status = "withdrawn"
            else:
                if not _reviewer(actor) or row.appellant_id == actor_id:
                    raise RectificationError("仅独立质控审核人员可以审核", 403)
                data = {key: getattr(row, key) for key in SOURCE_FIELDS}
                source = self.source(session, data)
                if any(source.get(key) != data[key] for key in SOURCE_FIELDS):
                    raise RectificationError("申诉来源已变化", 409)
                status = "approved" if action == "approve" else "rejected"
            now = datetime.now(timezone.utc)
            changes = {
                "status": status,
                "updated_at": now,
                "resolution": comment.strip(),
                "resolution_date": now,
            }
            if action != "withdraw":
                changes.update(
                    reviewer_id=actor_id,
                    reviewer_name=actor["name"],
                    review_result=comment.strip(),
                    review_date=now,
                )
            # 行锁外再用 CAS，避免无行锁数据库/重复提交产生第二条审核事件。
            result = session.execute(
                update(QCAppeal)
                .where(QCAppeal.id == appeal_id, QCAppeal.status == expected_status)
                .values(**changes)
            )
            if result.rowcount != 1:
                raise RectificationError("申诉状态已变化，请刷新核对", 409)
            session.add(
                QCAppealReview(
                    id=str(uuid4()),
                    appeal_id=row.id,
                    reviewer_id=actor_id,
                    reviewer_name=actor["name"],
                    reviewer_role="doctor"
                    if action == "withdraw"
                    else ("admin" if "admin" in actor["roles"] else "qc_manager"),
                    action=action,
                    comment=comment.strip(),
                    created_at=now,
                )
            )
            session.flush()
            session.refresh(row)
            return _view(row)
