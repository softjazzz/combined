"""病历初审/复审（任务受领范围）。

权威 owner：一次已保存的质控结果对象 R = (job_id, envelope_id, 三坐标, rule_set)。
- 决定行只追加、不可修改；同一结果对象只允许一个决定。
- stage 只由服务端计算：同三坐标 + rule_set_key 在“其他结果对象”上最近一次决定为
  doubtful → recheck，否则 initial。
- “结果可用”判定复用 get_task_qc_run_record_result，不另写核对。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCRecordReview, QCTask, QCTaskQCRun, QCTaskRecord
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    get_task_qc_run_record_result,
)

HISTORY_LIMIT = 50
_IN_CHUNK = 500
_IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")
# 首页 scene -> QCTask.scene 实际取值（QCTask CHECK：running/final/outpatient）。
_SCENE_TO_TASK_SCENE = {
    "outpatient_emergency": "outpatient",
    "running": "running",
    "final": "final",
}


class RecordReviewNotFound(LookupError):
    pass


class RecordReviewForbidden(PermissionError):
    pass


class RecordReviewInvalid(ValueError):
    pass


class RecordReviewConflict(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RecordReviewUnavailable(RuntimeError):
    pass


def _envelope_table() -> Any:
    """Envelope 表对象；单独封装便于测试替换为无 schema 的同构表。"""
    from .custom_qc_workspace_service import _record_result_envelopes_table

    return _record_result_envelopes_table()


def _default_workspace_factory() -> Any:
    from .custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService()


class _JobMemoWorkspace:
    """单次待办计算内的只读缓存：job 与其 Canonical 条目按 job_id 只加载一次。

    仅缓存结果读取器使用的两个只读方法，其他属性原样透传；不跨请求复用。
    """

    def __init__(self, workspace: Any) -> None:
        self._workspace = workspace
        self._jobs: dict[tuple[str, str], Any] = {}
        self._items: dict[tuple[str, bool], Any] = {}

    def get_batch_job(self, *, job_id: str, created_by: str) -> Any:
        key = (job_id, created_by)
        if key not in self._jobs:
            self._jobs[key] = self._workspace.get_batch_job(job_id=job_id, created_by=created_by)
        return self._jobs[key]

    def _load_batch_job_canonical_items(self, *, job: Any, allow_partial: bool) -> Any:
        key = (str(job.get("id") or "") if isinstance(job, dict) else "", bool(allow_partial))
        if not key[0]:
            return self._workspace._load_batch_job_canonical_items(job=job, allow_partial=allow_partial)
        if key not in self._items:
            self._items[key] = self._workspace._load_batch_job_canonical_items(
                job=job, allow_partial=allow_partial,
            )
        return self._items[key]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._workspace, name)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_session() -> None:
    if SessionLocal is None:
        raise RecordReviewUnavailable("数据库会话不可用")


def _validate_actor(actor_id: str) -> None:
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 64:
        raise RecordReviewForbidden("当前用户缺少有效身份")


def _identity(record: Any) -> tuple[str, str, str] | None:
    parts = tuple(record.get(key) for key in _IDENTITY_KEYS)
    if any(not isinstance(part, str) or not part.strip() or len(part) > 128 for part in parts):
        return None
    if record.get("record_id") != record.get("id"):
        return None
    return parts  # type: ignore[return-value]


def _chunks(values: Iterable[Any]) -> Iterable[list[Any]]:
    items = list(values)
    for start in range(0, len(items), _IN_CHUNK):
        yield items[start:start + _IN_CHUNK]


def _review_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "task_id": row.task_id,
        "task_record_id": row.task_record_id,
        "run_number": row.run_number,
        "job_id": row.job_id,
        "envelope_id": row.envelope_id,
        "rule_set_key": row.rule_set_key,
        "rule_set_version": row.rule_set_version,
        "stage": row.stage,
        "decision": row.decision,
        "reason": row.reason,
        "reviewer_id": row.reviewer_id,
        "created_at": row.created_at,
    }


def _stage_from_decisions(decisions: list[Any], job_id: str, envelope_id: str) -> str:
    """decisions 须已按 created_at、id 倒序；只看其他结果对象上的最近一次决定。"""
    for row in decisions:
        if row.job_id == job_id and row.envelope_id == envelope_id:
            continue
        return "recheck" if row.decision == "doubtful" else "initial"
    return "initial"


def _envelope_ids(
    session: Any, *, job_id: str, identity: tuple[str, str, str],
    rule_set_key: str, rule_set_version: str,
) -> list[str]:
    table = _envelope_table()
    rows = session.execute(
        select(table.c.id).where(
            table.c.root_job_id == job_id,
            table.c.institute_id == identity[0],
            table.c.patient_id == identity[1],
            table.c.visit_id == identity[2],
            table.c.rule_set_key == rule_set_key,
            table.c.rule_set_version == rule_set_version,
        )
    ).all()
    return [str(row.id) for row in rows]


def _case_decisions(session: Any, identity: tuple[str, str, str], rule_set_key: str, limit: int | None) -> list[Any]:
    statement = (
        select(QCRecordReview)
        .where(
            QCRecordReview.institute_id == identity[0],
            QCRecordReview.patient_id == identity[1],
            QCRecordReview.visit_id == identity[2],
            QCRecordReview.rule_set_key == rule_set_key,
        )
        .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.execute(statement).scalars().all())


def _read_result(
    *, task_id: str, task_record_id: str, run_number: int, actor_id: str,
    workspace_factory: Callable[[], Any],
) -> dict[str, Any]:
    """复用任务运行结果读取器；异常语义原样上抛，由调用方映射。"""
    result = get_task_qc_run_record_result(
        task_id=task_id, run_number=run_number, task_record_id=task_record_id,
        actor_id=actor_id, workspace_factory=workspace_factory, run_scope="assigned",
    )
    if (
        not isinstance(result, dict)
        or result.get("task_id") != task_id
        or result.get("task_record_id") != task_record_id
        or result.get("run_number") != run_number
    ):
        raise TaskQCRunConflict("任务病历质控结果身份不一致")
    return result


def _load_context(session: Any, task_id: str, task_record_id: str, actor_id: str, *, lock: bool) -> tuple[Any, Any]:
    task_query = select(QCTask.__table__).where(QCTask.id == task_id)
    task = session.execute(task_query.with_for_update(read=True) if lock else task_query).mappings().first()
    if task is None:
        raise RecordReviewNotFound("任务不存在")
    record_query = select(QCTaskRecord.__table__).where(
        QCTaskRecord.id == task_record_id, QCTaskRecord.task_id == task_id,
    )
    record = session.execute(record_query.with_for_update(read=True) if lock else record_query).mappings().first()
    if record is None:
        raise RecordReviewNotFound("任务病历不存在")
    if record["assignee_id"] != actor_id:
        raise RecordReviewForbidden("当前用户未受领该病历")
    return task, record


def _can_submit_status(task: Any, record: Any) -> bool:
    return task["status"] == "in_progress" and record["status"] in {"in_progress", "completed"}


# ---------------------------------------------------------------------------
# GET 视图
# ---------------------------------------------------------------------------


def get_record_review(
    *, task_id: str, task_record_id: str, run_number: int, actor_id: str,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """读取任务病历在指定受领运行上的审核状态、当前决定与历史。"""
    _validate_actor(actor_id)
    _require_session()
    if type(run_number) is not int or run_number <= 0:
        raise RecordReviewInvalid("运行序号无效")
    factory = workspace_factory or _default_workspace_factory
    try:
        with SessionLocal() as session:
            task, record = _load_context(session, task_id, task_record_id, actor_id, lock=False)
            identity = _identity(record)
            rule_set_key = task["rule_set_key"]
            rule_set_version = task["rule_set_version"]
            can_submit_status = _can_submit_status(task, record)
            history = (
                _case_decisions(session, identity, rule_set_key, HISTORY_LIMIT)
                if identity and rule_set_key else []
            )
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc

    view: dict[str, Any] = {
        "task_id": task_id, "task_record_id": task_record_id, "run_number": run_number,
        "state": "unavailable", "stage": None, "reason_code": None, "can_submit": False,
        "current": None, "history": [_review_dict(row) for row in history],
        "result": {"job_id": None, "envelope_id": None},
    }
    if identity is None:
        view["reason_code"] = "identity_incomplete"
        return view
    if rule_set_key != LUXIAN_0609_RULE_SET_KEY or not rule_set_version:
        view["reason_code"] = "unsupported_rule_set"
        return view

    try:
        result = _read_result(
            task_id=task_id, task_record_id=task_record_id, run_number=run_number,
            actor_id=actor_id, workspace_factory=factory,
        )
    except TaskQCRunNotFound as exc:
        raise RecordReviewNotFound(str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise RecordReviewForbidden(str(exc)) from exc
    except TaskQCRunConflict:
        view["reason_code"] = "result_invalid"
        return view
    job_id = str(result.get("job_id") or "").strip()
    view["result"]["job_id"] = job_id or None
    if result.get("result_state") != "available" or not job_id:
        view["reason_code"] = f"result_{result.get('result_state') or 'unknown'}"
        return view

    try:
        with SessionLocal() as session:
            envelope_ids = _envelope_ids(
                session, job_id=job_id, identity=identity,
                rule_set_key=rule_set_key, rule_set_version=rule_set_version,
            )
            if len(envelope_ids) != 1:
                view["reason_code"] = "envelope_missing" if not envelope_ids else "envelope_ambiguous"
                return view
            envelope_id = envelope_ids[0]
            view["result"]["envelope_id"] = envelope_id
            decisions = _case_decisions(session, identity, rule_set_key, None)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc

    current = next(
        (row for row in decisions if row.job_id == job_id and row.envelope_id == envelope_id), None,
    )
    if current is not None:
        view.update(state=current.decision, stage=current.stage, current=_review_dict(current))
        return view
    stage = _stage_from_decisions(decisions, job_id, envelope_id)
    view.update(
        state="pending_recheck" if stage == "recheck" else "pending_review",
        stage=stage, can_submit=can_submit_status,
    )
    return view


# ---------------------------------------------------------------------------
# POST 决定
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DecisionRequest:
    task_id: str
    task_record_id: str
    run_number: int
    decision: str
    reason: str | None
    request_id: str
    envelope_id: str
    actor_id: str


def _normalize_request(
    *, task_id: str, task_record_id: str, run_number: int, decision: str,
    reason: str | None, request_id: str, envelope_id: str, actor_id: str,
) -> _DecisionRequest:
    _validate_actor(actor_id)
    if type(run_number) is not int or run_number <= 0:
        raise RecordReviewInvalid("运行序号无效")
    if decision not in {"approved", "doubtful"}:
        raise RecordReviewInvalid("审核决定无效")
    try:
        canonical = str(UUID(str(request_id)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise RecordReviewInvalid("请求 ID 无效") from exc
    if canonical != request_id:
        raise RecordReviewInvalid("请求 ID 无效")
    if not isinstance(envelope_id, str) or not envelope_id.strip() or len(envelope_id) > 36:
        raise RecordReviewInvalid("结果对象 ID 无效")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > 2000:
            raise RecordReviewInvalid("原因无效")
        reason = reason.strip() or None
    if decision == "doubtful" and not reason:
        raise RecordReviewInvalid("存疑必须填写原因")
    return _DecisionRequest(
        task_id=task_id, task_record_id=task_record_id, run_number=run_number,
        decision=decision, reason=reason, request_id=request_id,
        envelope_id=envelope_id, actor_id=actor_id,
    )


def _replay(row: QCRecordReview, req: _DecisionRequest) -> dict[str, Any]:
    if (
        row.task_id != req.task_id or row.task_record_id != req.task_record_id
        or row.run_number != req.run_number or row.decision != req.decision
        or (row.reason or None) != req.reason or row.envelope_id != req.envelope_id
        or row.reviewer_id != req.actor_id
    ):
        raise RecordReviewConflict("idempotency_conflict", "请求 ID 已被其他审核内容使用")
    return {**_review_dict(row), "idempotent": True}


def _find_by_request(session: Any, request_id: str) -> QCRecordReview | None:
    return session.execute(
        select(QCRecordReview).where(QCRecordReview.request_id == request_id)
    ).scalars().first()


def _advisory_lock(session: Any, identity: tuple[str, str, str], rule_set_key: str) -> None:
    """PostgreSQL 事务级 advisory lock；SQLite 测试环境没有该函数，跳过。"""
    if session.get_bind().dialect.name != "postgresql":
        return
    key = "qc_record_review|" + "|".join((*identity, rule_set_key))
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def submit_record_review(
    *, task_id: str, task_record_id: str, run_number: int, decision: str,
    reason: str | None, request_id: str, envelope_id: str, actor_id: str,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """在单事务内核对结果对象并追加一条审核决定。"""
    req = _normalize_request(
        task_id=task_id, task_record_id=task_record_id, run_number=run_number,
        decision=decision, reason=reason, request_id=request_id,
        envelope_id=envelope_id, actor_id=actor_id,
    )
    _require_session()
    factory = workspace_factory or _default_workspace_factory
    try:
        return _submit(req, factory)
    except IntegrityError:
        # 并发竞争：唯一约束兜底，回滚后按请求 ID / 结果对象重新判定。
        try:
            with SessionLocal() as session:
                existing = _find_by_request(session, req.request_id)
                if existing is not None:
                    return _replay(existing, req)
                # Envelope 行 id 为全局唯一 UUID，已唯一确定 job、三坐标与规则集，
                # 等价于完整唯一键 uq_qc_record_reviews_result。
                taken = session.execute(
                    select(QCRecordReview.id).where(
                        QCRecordReview.envelope_id == req.envelope_id,
                    ).limit(1)
                ).first()
        except SQLAlchemyError as exc:
            raise RecordReviewUnavailable("审核数据暂不可用") from exc
        if taken is not None:
            raise RecordReviewConflict("already_decided", "该结果已有审核决定")
        raise RecordReviewUnavailable("审核保存失败，请稍后重试")
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc


def _submit(req: _DecisionRequest, factory: Callable[[], Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        # 幂等重放不需要重新核对结果，也不受后续状态变化影响。
        existing = _find_by_request(session, req.request_id)
        if existing is not None:
            return _replay(existing, req)
        _, record = _load_context(session, req.task_id, req.task_record_id, req.actor_id, lock=False)
        identity = _identity(record)
        if identity is None:
            raise RecordReviewConflict("result_unavailable", "任务病历缺少完整三坐标")

    with SessionLocal() as session:
        with session.begin():
            task_rule = session.execute(
                select(QCTask.rule_set_key).where(QCTask.id == req.task_id)
            ).scalar_one_or_none()
            _advisory_lock(session, identity, str(task_rule or ""))
            existing = _find_by_request(session, req.request_id)
            if existing is not None:
                return _replay(existing, req)
            task, record = _load_context(session, req.task_id, req.task_record_id, req.actor_id, lock=True)
            if _identity(record) != identity:
                raise RecordReviewConflict("result_changed", "任务病历身份已变化")
            if not _can_submit_status(task, record):
                raise RecordReviewConflict("state_conflict", "任务或病历当前状态不允许审核")
            rule_set_key = task["rule_set_key"]
            rule_set_version = task["rule_set_version"]
            if rule_set_key != LUXIAN_0609_RULE_SET_KEY or not rule_set_version:
                raise RecordReviewConflict("unsupported_rule_set", "当前规则集不支持病历审核")
            run = session.execute(
                select(QCTaskQCRun.__table__).where(
                    QCTaskQCRun.task_id == req.task_id,
                    QCTaskQCRun.run_number == req.run_number,
                )
            ).mappings().first()
            if run is None:
                raise RecordReviewNotFound("任务运行不存在")
            if run["run_scope"] != "assigned" or run["triggered_by"] != req.actor_id:
                raise RecordReviewForbidden("仅本人受领运行可提交审核")

            try:
                result = _read_result(
                    task_id=req.task_id, task_record_id=req.task_record_id,
                    run_number=req.run_number, actor_id=req.actor_id,
                    workspace_factory=factory,
                )
            except TaskQCRunNotFound as exc:
                raise RecordReviewNotFound(str(exc)) from exc
            except TaskQCRunForbidden as exc:
                raise RecordReviewForbidden(str(exc)) from exc
            except TaskQCRunConflict as exc:
                raise RecordReviewConflict("result_unavailable", "本次质控结果不可用于审核") from exc
            if result.get("result_state") != "available":
                raise RecordReviewConflict("result_unavailable", "本次质控结果不可用于审核")
            job_id = str(result.get("job_id") or "").strip()
            if not job_id or job_id != run["job_id"]:
                raise RecordReviewConflict("result_changed", "任务运行身份已变化")

            envelope_ids = _envelope_ids(
                session, job_id=job_id, identity=identity,
                rule_set_key=rule_set_key, rule_set_version=rule_set_version,
            )
            if len(envelope_ids) != 1:
                raise RecordReviewConflict(
                    "result_unavailable",
                    "质控结果对象缺失" if not envelope_ids else "质控结果对象不唯一",
                )
            if envelope_ids[0] != req.envelope_id:
                raise RecordReviewConflict("result_changed", "质控结果已被替换，请刷新后重新审核")

            decisions = _case_decisions(session, identity, rule_set_key, None)
            if any(row.job_id == job_id and row.envelope_id == req.envelope_id for row in decisions):
                raise RecordReviewConflict("already_decided", "该结果已有审核决定")
            stage = _stage_from_decisions(decisions, job_id, req.envelope_id)
            row = QCRecordReview(
                id=str(uuid4()), request_id=req.request_id,
                institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
                rule_set_key=rule_set_key, rule_set_version=rule_set_version,
                job_id=job_id, envelope_id=req.envelope_id,
                task_id=req.task_id, task_record_id=req.task_record_id,
                run_number=req.run_number, stage=stage, decision=req.decision,
                reason=req.reason, reviewer_id=req.actor_id, created_at=_now(),
            )
            session.add(row)
            session.flush()
            response = _review_dict(row)
    state = response["decision"]
    return {**response, "state": state, "idempotent": False}


# ---------------------------------------------------------------------------
# 待办：列表与计数共用同一谓词
# ---------------------------------------------------------------------------


def _task_scene_filter(scene: str | None) -> str | None:
    if scene is None or scene == "all":
        return None
    if scene not in _SCENE_TO_TASK_SCENE:
        raise RecordReviewInvalid("无效的场景")
    return _SCENE_TO_TASK_SCENE[scene]


def _pending_todo_items(
    session: Any, *, actor_id: str, scene: str | None,
    workspace_factory: Callable[[], Any],
) -> list[dict[str, Any]]:
    """待办唯一谓词：本人受领、任务进行中、最新可用的本人 assigned 运行结果尚无决定。

    数据库往返：候选 1 次 + 运行 1 次 + Envelope 按 job 分块 + 决定按 visit 分块；
    仅对“最新有唯一 Envelope 且未决定”的运行调用一次结果读取器。
    """
    task_scene = _task_scene_filter(scene)
    statement = (
        select(
            QCTaskRecord.id, QCTaskRecord.task_id, QCTaskRecord.record_id,
            QCTaskRecord.institute_id, QCTaskRecord.patient_id, QCTaskRecord.visit_id,
            QCTaskRecord.status, QCTaskRecord.created_at,
            QCTask.task_name, QCTask.scene, QCTask.rule_set_key, QCTask.rule_set_version,
            QCTask.created_at.label("task_created_at"),
        )
        .join(QCTask, QCTask.id == QCTaskRecord.task_id)
        .where(
            QCTaskRecord.assignee_id == actor_id,
            QCTaskRecord.status.in_(("in_progress", "completed")),
            QCTask.status == "in_progress",
            QCTask.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            QCTask.rule_set_version.is_not(None),
        )
        .order_by(QCTask.created_at.desc(), QCTask.id, QCTaskRecord.created_at, QCTaskRecord.id)
    )
    if task_scene is not None:
        statement = statement.where(QCTask.scene == task_scene)
    candidates = []
    for row in session.execute(statement).mappings().all():
        identity = _identity(row)
        if identity is not None:
            candidates.append((dict(row), identity))
    if not candidates:
        return []

    task_ids = sorted({row["task_id"] for row, _ in candidates})
    runs_by_task: dict[str, list[Any]] = {}
    for chunk in _chunks(task_ids):
        for run in session.execute(
            select(QCTaskQCRun.task_id, QCTaskQCRun.run_number, QCTaskQCRun.job_id)
            .where(
                QCTaskQCRun.task_id.in_(chunk),
                QCTaskQCRun.run_scope == "assigned",
                QCTaskQCRun.triggered_by == actor_id,
            )
            .order_by(QCTaskQCRun.run_number.desc())
        ).all():
            runs_by_task.setdefault(run.task_id, []).append(run)
    job_ids = sorted({run.job_id for runs in runs_by_task.values() for run in runs})
    if not job_ids:
        return []

    table = _envelope_table()
    envelopes: dict[tuple[str, tuple[str, str, str], str], list[str]] = {}
    for chunk in _chunks(job_ids):
        for env in session.execute(
            select(
                table.c.id, table.c.root_job_id, table.c.institute_id,
                table.c.patient_id, table.c.visit_id, table.c.rule_set_version,
            ).where(
                table.c.root_job_id.in_(chunk),
                table.c.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            )
        ).all():
            key = (env.root_job_id, (env.institute_id, env.patient_id, env.visit_id), env.rule_set_version)
            envelopes.setdefault(key, []).append(str(env.id))

    visit_ids = sorted({identity[2] for _, identity in candidates})
    decisions_by_case: dict[tuple[str, str, str], list[Any]] = {}
    for chunk in _chunks(visit_ids):
        for decision in session.execute(
            select(QCRecordReview)
            .where(
                QCRecordReview.visit_id.in_(chunk),
                QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            )
            .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
        ).scalars().all():
            case = (decision.institute_id, decision.patient_id, decision.visit_id)
            decisions_by_case.setdefault(case, []).append(decision)

    shared_workspace: list[Any] = []

    def shared_factory() -> Any:
        # 同一次待办计算只构造一个 workspace 实例，并按 job 缓存只读结果，
        # 避免同一 job 下 N 个病例把整份 Canonical 结果反序列化 N 次。
        if not shared_workspace:
            shared_workspace.append(_JobMemoWorkspace(workspace_factory()))
        return shared_workspace[0]

    items: list[dict[str, Any]] = []
    for row, identity in candidates:
        decisions = decisions_by_case.get(identity, [])
        decided = {(item.job_id, item.envelope_id) for item in decisions}
        for run in runs_by_task.get(row["task_id"], []):
            ids = envelopes.get((run.job_id, identity, row["rule_set_version"]), [])
            if len(ids) != 1:
                continue  # Envelope 缺失或不唯一：本运行结果不可用，退回更早运行
            envelope_id = ids[0]
            if (run.job_id, envelope_id) in decided:
                break  # 最新结果对象已有决定：不在待办中
            try:
                result = _read_result(
                    task_id=row["task_id"], task_record_id=row["id"],
                    run_number=run.run_number, actor_id=actor_id,
                    workspace_factory=shared_factory,
                )
            except (TaskQCRunNotFound, TaskQCRunForbidden, TaskQCRunConflict):
                continue
            if result.get("result_state") != "available" or result.get("job_id") != run.job_id:
                continue
            stage = _stage_from_decisions(decisions, run.job_id, envelope_id)
            items.append({
                "task_id": row["task_id"], "task_name": row["task_name"],
                "task_scene": row["scene"], "task_record_id": row["id"],
                "record_status": row["status"],
                "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
                "rule_set_key": row["rule_set_key"], "rule_set_version": row["rule_set_version"],
                "run_number": run.run_number, "job_id": run.job_id, "envelope_id": envelope_id,
                "stage": stage,
                "state": "pending_recheck" if stage == "recheck" else "pending_review",
            })
            break
    return items


def _collect_todos(actor_id: str, scene: str | None, workspace_factory: Callable[[], Any] | None) -> list[dict[str, Any]]:
    _validate_actor(actor_id)
    _require_session()
    _task_scene_filter(scene)
    try:
        with SessionLocal() as session:
            return _pending_todo_items(
                session, actor_id=actor_id, scene=scene,
                workspace_factory=workspace_factory or _default_workspace_factory,
            )
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核待办暂不可用") from exc


def list_my_record_review_todos(
    *, actor_id: str, stage: str | None = None, scene: str | None = None,
    page: int = 1, page_size: int = 20,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    if stage not in (None, "initial", "recheck"):
        raise RecordReviewInvalid("stage 无效")
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise RecordReviewInvalid("分页参数无效")
    items = _collect_todos(actor_id, scene, workspace_factory)
    if stage is not None:
        items = [item for item in items if item["stage"] == stage]
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size], "total": len(items),
        "page": page, "page_size": page_size, "stage": stage, "scene": scene or "all",
    }


def count_my_record_review_todos(
    actor_id: str, scene: str | None = None,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, int]:
    """首页待办计数；与待办列表共用 _pending_todo_items 谓词。"""
    items = _collect_todos(actor_id, scene, workspace_factory)
    return {
        "initial": sum(1 for item in items if item["stage"] == "initial"),
        "recheck": sum(1 for item in items if item["stage"] == "recheck"),
    }


__all__ = [
    "RecordReviewConflict",
    "RecordReviewForbidden",
    "RecordReviewInvalid",
    "RecordReviewNotFound",
    "RecordReviewUnavailable",
    "count_my_record_review_todos",
    "get_record_review",
    "list_my_record_review_todos",
    "submit_record_review",
]

