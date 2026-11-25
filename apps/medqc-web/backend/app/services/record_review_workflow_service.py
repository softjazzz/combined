"""运行/终末病历审核写 owner；决定行本身即不可变工作事件。"""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase

from ..database import connection as db_connection
from ..database.connection import SessionLocal
from ..database.models.v36_reports import QCDefect, QCDefectHistory
from ..database.models.v36_reports import QCRecordReview as ReportReview
from .defect_rectification_service import RectificationError, _department, _person
from .feedback_result_source import current_result
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .record_review_defect_snapshot_service import validate_snapshot
from .record_review_service import _derive_state, _workspace_scene_from_job

SOURCE_FIELDS = (
    "institute_id",
    "patient_id",
    "visit_id",
    "scene",
    "root_job_id",
    "envelope_id",
    "rule_set_key",
    "rule_set_version",
)
STATES = ("pending_review", "pending_recheck", "approved", "doubtful")
REVIEWERS = {"admin", "super_admin", "qc_manager", "qc_staff"}
MAX_CASES = 5000


def _qc_schema() -> str | None:
    return (
        "qc"
        if str(getattr(db_connection, "DB_SCHEMA_MODE", "") or "").strip().lower()
        == "split"
        else None
    )


def _is_global_scope(actor) -> bool:
    roles = actor["roles"]
    return ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not actor["institute_id"]
    )


class _OwnerBase(DeclarativeBase):
    pass


class QCRecordReview(_OwnerBase):
    __table__ = ReportReview.__table__.to_metadata(
        _OwnerBase.metadata, schema=_qc_schema()
    )


def _source(data):
    if not isinstance(data, dict) or any(
        not isinstance(data.get(key), str)
        or not data[key].strip()
        or data[key] != data[key].strip()
        or len(data[key])
        > (
            36
            if key in {"root_job_id", "envelope_id"}
            else 96
            if key.startswith("rule_set_")
            else 128
        )
        for key in SOURCE_FIELDS
    ):
        raise RectificationError("审核来源不完整")
    if (
        data["scene"] not in {"running", "final"}
        or data["rule_set_key"] != LUXIAN_0609_RULE_SET_KEY
    ):
        raise RectificationError("当前仅接通运行和终末病历审核")
    return {key: data[key] for key in SOURCE_FIELDS}


def _authorized(actor, institute_id):
    if not actor["roles"] & REVIEWERS:
        raise RectificationError("仅持久质控账号可审核病历", 403)
    if not _is_global_scope(actor) and (
        not actor["institute_id"] or actor["institute_id"] != institute_id
    ):
        raise RectificationError("无权访问该机构病历审核", 403)


def _case_rows(session, identity, *, scene=None):
    conditions = [
        *(
            getattr(QCRecordReview, key) == value
            for key, value in zip(SOURCE_FIELDS[:3], identity)
        ),
        QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
    ]
    if scene is not None:
        conditions.append(QCRecordReview.scene == scene)
    return session.scalars(
        select(QCRecordReview)
        .where(*conditions)
        .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
    ).all()


def _row_view(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "request_id",
            "institute_id",
            "patient_id",
            "visit_id",
            "scene",
            "envelope_id",
            "rule_set_key",
            "rule_set_version",
            "stage",
            "decision",
            "reason",
            "reviewer_id",
            "created_at",
            "review_context",
        )
    } | {
        "root_job_id": row.job_id,
        "case_department": (row.defect_snapshot or {}).get("case_department"),
    }


class _ManualSnapshotReadSession:
    """只给人工来源报表的 qc 查询固定 owner；持久账号保留自身显式 owner。"""

    def __init__(self, session):
        self.session = session
        schema = _qc_schema()
        self.options = (
            {"schema_translate_map": {None: schema}}
            if schema and session.get_bind().dialect.name == "postgresql"
            else {}
        )

    def get_bind(self):
        return self.session.get_bind()

    def execute(self, *args, **kwargs):
        kwargs.setdefault("execution_options", self.options)
        return self.session.execute(*args, **kwargs)

    def scalars(self, *args, **kwargs):
        kwargs.setdefault("execution_options", self.options)
        return self.session.scalars(*args, **kwargs)


def _capture_snapshot(session, current, captured_at):
    """从正式投影和现有人工来源 owner 冻结初审事实；来源失败不记为零。"""
    from .manual_defect_review_service import _manual_scope
    from .manual_quality_report_service import (
        ManualQualityReportService,
        _source as manual_source,
    )

    items = current.get("items")
    if not isinstance(items, list) or not items:
        raise RectificationError("保存结果条目不完整，审核未提交", 409)
    ids = [item.get("rule_id") for item in items if isinstance(item, dict)]
    if (
        len(ids) != len(items)
        or any(not isinstance(key, str) or not key.strip() for key in ids)
        or len(set(ids)) != len(ids)
    ):
        raise RectificationError("保存结果规则身份无效", 409)
    if any(type(item.get("is_confirmed_issue")) is not bool for item in items):
        raise RectificationError("保存结果缺陷投影不完整", 409)
    auto = [
        {"defect_id": item["rule_id"], "rule_id": item["rule_id"]}
        for item in items
        if item["is_confirmed_issue"]
    ]
    qc_session = _ManualSnapshotReadSession(session)
    defects = qc_session.scalars(
        select(QCDefect)
        .where(
            *_manual_scope(),
            *(getattr(QCDefect, key) == current[key] for key in SOURCE_FIELDS[:3]),
        )
        .with_for_update()
    ).all()
    data = ManualQualityReportService()._batch(qc_session, defects)
    manual = []
    for defect in defects:
        task, _, target = manual_source(
            defect,
            data["histories"].get(defect.id, []),
            data["records"],
            data["runs"],
            data["jobs"],
            data["envelopes"],
        )
        if target is None or task["task_id"] not in data["tasks"]:
            raise RectificationError("人工缺陷来源不完整，审核未提交", 409)
        if target[:4] != tuple(current[key] for key in SOURCE_FIELDS[:4]) or target[
            -2:
        ] != (current["root_job_id"], current["envelope_id"]):
            continue
        if defect.manual_review_status != "approved":
            continue
        histories = qc_session.scalars(
            select(QCDefectHistory)
            .where(
                QCDefectHistory.defect_id == defect.id,
                QCDefectHistory.action.in_(
                    (
                        "manual_create",
                        "manual_review_approved",
                        "manual_review_rejected",
                    )
                ),
            )
            .with_for_update(read=True)
        ).all()
        creates = [row for row in histories if row.action == "manual_create"]
        approvals = [row for row in histories if row.action == "manual_review_approved"]
        if len(histories) != 2 or len(creates) != 1 or len(approvals) != 1:
            raise RectificationError("人工缺陷审核历史不唯一", 409)
        create, approve = creates[0], approvals[0]
        try:
            creation_details = json.loads(create.details)
            details = json.loads(approve.details)
        except (TypeError, ValueError) as exc:
            raise RectificationError("人工缺陷审核历史无效", 409) from exc
        if (
            not isinstance(creation_details, dict)
            or creation_details.get("envelope_id") != current["envelope_id"]
        ):
            raise RectificationError("人工缺陷创建结果引用不一致，审核未提交", 409)
        if (
            not isinstance(details, dict)
            or details.get("from_status") != "pending"
            or details.get("to_status") != "approved"
            or details.get("reviewer") != approve.actor_id
            or not approve.actor_id
            or approve.actor_id == create.actor_id
            or create.actor_id != defect.manual_created_by
            or not create.created_at
            or not approve.created_at
            or not create.created_at <= approve.created_at <= captured_at
        ):
            raise RectificationError("人工缺陷审核身份或时点无效", 409)
        manual.append(
            {
                "defect_id": defect.id,
                "created_by": defect.manual_created_by,
                "creation_history_id": create.id,
                "approval_history_id": approve.id,
            }
        )
    frozen = {key: current[key] for key in SOURCE_FIELDS if key != "root_job_id"} | {
        "job_id": current["root_job_id"]
    }
    snapshot = {
        "schema_version": 1,
        "complete": True,
        "source": frozen,
        "captured_at": captured_at.replace(tzinfo=timezone.utc).isoformat(),
        "auto": {"count": len(auto), "items": auto},
        "manual": {"count": len(manual), "items": manual},
    }
    return validate_snapshot(snapshot, source=frozen)


def _candidate_sources(session, actor):
    from .custom_qc_workspace_service import CustomQCWorkspaceService, _batch_jobs_table
    from .feedback_result_source import _BorrowedReadSession
    from .report_case_scope import load_current_workstation_records

    records = load_current_workstation_records(
        department=None,
        doctor=None,
        hospital_status="all",
        institute_id=None if _is_global_scope(actor) else actor["institute_id"],
    )
    if len(records) > MAX_CASES:
        raise RectificationError("病历审核范围超过5000份，无法完整核对", 422)
    summaries = CustomQCWorkspaceService(
        readonly=True
    ).build_luxian_0609_completed_record_result_summaries(
        record_refs=records,
        include_items=False,
        include_rule_set_context=True,
        session_factory=lambda: _BorrowedReadSession(session),
    )
    if any(row.get("status") not in {"ready", "not_run"} for row in summaries.values()):
        raise RectificationError("当前保存结果存在读取失败，审核待办暂不可用", 503)
    job_ids = {
        row.get("root_job_id")
        for row in summaries.values()
        if row.get("status") == "ready"
    }
    table = _batch_jobs_table(readonly=True)
    jobs = {
        row["id"]: row
        for row in session.execute(
            select(
                table.c.id, table.c.scene, table.c.scope, table.c.filters_json
            ).where(table.c.id.in_(job_ids))
        ).mappings()
    }
    sources = []
    for record in records:
        identity = tuple(record[key] for key in SOURCE_FIELDS[:3])
        result = summaries.get(identity, {})
        if result.get("status") != "ready":
            continue
        job = jobs.get(result.get("root_job_id"))
        if job is None:
            raise RectificationError("当前保存结果任务来源不可用", 503)
        scene = _workspace_scene_from_job(job, identity=identity)
        if scene not in {"running", "final"}:
            continue
        sources.append(
            _source({**record, **result, "scene": scene})
            | {"case_department": record["department"]}
        )
    return sources


class RecordReviewWorkflowService:
    def __init__(
        self,
        sessions=None,
        person_loader=None,
        source_loader=None,
        department_loader=None,
        snapshot_loader=None,
        candidates_loader=None,
    ):
        self.sessions = sessions or SessionLocal
        self.person = person_loader or _person
        self.source = source_loader or current_result
        self.department = department_loader or _department
        self.snapshot = snapshot_loader or _capture_snapshot
        self.candidates = candidates_loader or _candidate_sources

    def _resolve(self, session, actor, source):
        _authorized(actor, source["institute_id"])
        identity = tuple(source[key] for key in SOURCE_FIELDS[:3])
        department = self.department(session, identity)
        if not isinstance(department, str) or not department.strip():
            raise RectificationError("缺少可信病例科室", 409)
        current = self.source(
            session, identity, source["root_job_id"], source["envelope_id"]
        )
        if any(current.get(key) != source[key] for key in SOURCE_FIELDS):
            raise RectificationError("当前保存结果来源或版本已变化，请刷新核对", 409)
        return current, department

    def current(self, actor_id, *, source):
        source = _source(source)
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            _, department = self._resolve(session, actor, source)
            rows = _case_rows(
                session,
                tuple(source[key] for key in SOURCE_FIELDS[:3]),
                scene=source["scene"],
            )
            state, stage, row = _derive_state(
                rows,
                source["root_job_id"],
                source["envelope_id"],
                scene=source["scene"],
            )
            return {
                **source,
                "case_department": department,
                "state": state,
                "stage": stage,
                "current_review": _row_view(row) if row else None,
                "history": [_row_view(item) for item in rows],
                "can_submit": row is None,
            }

    def history(self, actor_id, review_id):
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            row = session.get(QCRecordReview, review_id)
            if row is None or row.scene not in {"running", "final"}:
                raise RectificationError("审核历史不存在", 404)
            _authorized(actor, row.institute_id)
            view = _row_view(row)
            rows = _case_rows(
                session,
                (row.institute_id, row.patient_id, row.visit_id),
                scene=row.scene,
            )
            return {
                **{key: view[key] for key in SOURCE_FIELDS},
                "case_department": view["case_department"],
                "state": row.decision,
                "stage": row.stage,
                "current_review": view,
                "history": [_row_view(item) for item in rows],
                "can_submit": False,
            }

    def submit(self, actor_id, *, source, expected_state, decision, reason, request_id):
        source = _source(source)
        if (
            expected_state not in STATES[:2]
            or decision not in STATES[2:]
            or not isinstance(reason, str)
            or len(reason) > 2000
            or (decision == "doubtful" and not reason.strip())
        ):
            raise RectificationError("审核决定、预期状态或原因无效")
        try:
            if str(UUID(request_id)) != request_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError) as exc:
            raise RectificationError("审核请求ID无效") from exc
        reason = reason.strip() or None
        try:
            with self.sessions.begin() as session:
                actor = self.person(session, actor_id)
                _authorized(actor, source["institute_id"])
                prior = session.scalar(
                    select(QCRecordReview).where(
                        QCRecordReview.request_id == request_id
                    )
                )
                if prior:
                    view = _row_view(prior)
                    if (
                        any(view[key] != source[key] for key in SOURCE_FIELDS)
                        or prior.reviewer_id != actor_id
                        or prior.decision != decision
                        or prior.reason != reason
                    ):
                        raise RectificationError("请求ID已用于其他审核内容", 409)
                    return view | {"idempotent": True}
                identity = tuple(source[key] for key in SOURCE_FIELDS[:3])
                # 锁串行化同病例同场景跨结果的阶段推导，唯一约束兜底同结果竞争。
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(
                        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                        {
                            "key": "record_review|"
                            + "|".join(
                                (*identity, source["rule_set_key"], source["scene"])
                            )
                        },
                    )
                current, department = self._resolve(session, actor, source)
                state, stage, row = _derive_state(
                    _case_rows(session, identity, scene=source["scene"]),
                    source["root_job_id"],
                    source["envelope_id"],
                    scene=source["scene"],
                )
                if row is not None or state != expected_state:
                    raise RectificationError("审核状态已变化，请刷新核对", 409)
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                snapshot = (
                    self.snapshot(session, current, now) if stage == "initial" else {}
                )
                if stage == "initial":
                    frozen = {
                        key: source[key]
                        for key in SOURCE_FIELDS
                        if key != "root_job_id"
                    } | {"job_id": source["root_job_id"], "created_at": now}
                    snapshot = validate_snapshot(snapshot, source=frozen)
                snapshot = {**snapshot, "case_department": department}
                review = QCRecordReview(
                    id=str(uuid4()),
                    request_id=request_id,
                    **{
                        key: source[key]
                        for key in SOURCE_FIELDS
                        if key != "root_job_id"
                    },
                    job_id=source["root_job_id"],
                    review_context="workspace",
                    task_id=None,
                    task_record_id=None,
                    run_number=None,
                    stage=stage,
                    decision=decision,
                    reason=reason,
                    reviewer_id=actor_id,
                    created_at=now,
                    defect_snapshot=snapshot,
                )
                session.add(review)
                session.flush()
                return _row_view(review) | {"idempotent": False}
        except IntegrityError as exc:
            raise RectificationError(
                "该结果已有决定或审核请求已提交，请刷新核对", 409
            ) from exc

    def list(self, actor_id, *, state="open", scene=None, page=1, page_size=10):
        if (
            state not in ("open", "history", *STATES)
            or scene not in (None, "running", "final")
            or type(page) is not int
            or not 1 <= page <= 10000
            or type(page_size) is not int
            or not 1 <= page_size <= 100
        ):
            raise RectificationError("审核筛选或分页无效")
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            if not actor["roles"] & REVIEWERS or (
                not _is_global_scope(actor) and not actor["institute_id"]
            ):
                raise RectificationError("缺少持久质控账号或机构范围", 403)
            sources = self.candidates(session, actor)
            identities = [
                tuple(source[key] for key in SOURCE_FIELDS[:3]) for source in sources
            ]
            grouped = {}
            for start in range(0, len(identities), 500):
                rows = session.scalars(
                    select(QCRecordReview)
                    .where(
                        tuple_(
                            QCRecordReview.institute_id,
                            QCRecordReview.patient_id,
                            QCRecordReview.visit_id,
                        ).in_(identities[start : start + 500]),
                        QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                    )
                    .order_by(
                        QCRecordReview.created_at.desc(), QCRecordReview.id.desc()
                    )
                )
                for row in rows:
                    grouped.setdefault(
                        (row.institute_id, row.patient_id, row.visit_id, row.scene), []
                    ).append(row)
            items = []
            for source in sources:
                source = _source(source) | {
                    "case_department": source.get("case_department")
                }
                _authorized(actor, source["institute_id"])
                if scene and source["scene"] != scene:
                    continue
                rows = grouped.get(
                    (*tuple(source[key] for key in SOURCE_FIELDS[:3]), source["scene"]),
                    [],
                )
                current_state, stage, row = _derive_state(
                    rows,
                    source["root_job_id"],
                    source["envelope_id"],
                    scene=source["scene"],
                )
                items.append(
                    {
                        **source,
                        "state": current_state,
                        "stage": stage,
                        "review_id": row.id if row else None,
                    }
                )
            initial_count = sum(item["state"] == "pending_review" for item in items)
            recheck_count = sum(item["state"] == "pending_recheck" for item in items)
            if state == "history":
                statement = select(QCRecordReview).where(
                    QCRecordReview.scene.in_(("running", "final")),
                    QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                )
                if not _is_global_scope(actor):
                    statement = statement.where(
                        QCRecordReview.institute_id == actor["institute_id"]
                    )
                if scene:
                    statement = statement.where(QCRecordReview.scene == scene)
                items = [
                    {**_row_view(row), "state": row.decision, "review_id": row.id}
                    for row in session.scalars(
                        statement.order_by(
                            QCRecordReview.created_at.desc(), QCRecordReview.id.desc()
                        )
                    )
                ]
            else:
                items = (
                    [item for item in items if item["state"] in STATES[:2]]
                    if state == "open"
                    else [item for item in items if item["state"] == state]
                )
            return {
                "items": items[(page - 1) * page_size : page * page_size],
                "total": len(items),
                "pending_count": initial_count + recheck_count,
                "initial_count": initial_count,
                "recheck_count": recheck_count,
                "page": page,
                "page_size": page_size,
            }
