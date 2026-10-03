"""病历初审/复审。

权威 owner：一次已保存的质控结果对象 R = (job_id, envelope_id, 三坐标, rule_set)。
- 决定行只追加、不可修改；同一结果对象只允许一个决定（不区分审核上下文）。
- stage 只由服务端计算：同三坐标 + rule_set_key 在“其他结果对象”上最近一次决定为
  doubtful → recheck，否则 initial。
- 审核上下文 review_context：
  - task：任务受领范围，“结果可用”判定复用 get_task_qc_run_record_result；
  - workspace：运行/终末列表范围，以单病历 DTO（build_latest_single_record_result_dto）
    的最新 ready 结果为当前结果对象；QC_RESULTS.REVIEW 权限由路由层校验。
- 两种上下文共用同一套状态推导、原因校验、幂等重放、advisory lock 与错误类。
- batch_review_states 供病历列表批量挂载 review_state，与单病例同一推导函数；
  batch_current_reviews 供导出，同一查询、同一推导，另带当前决定的原因/审核人/时间。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCRecordReview, QCTask, QCTaskQCRun, QCTaskRecord
from .case_identity import CaseRef
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .qc_rule_sets import SICHUAN_RULE_SETS
from .task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    get_task_qc_run_record_result,
)

HISTORY_LIMIT = 50
CONTEXT_TASK = "task"
CONTEXT_WORKSPACE = "workspace"
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


class RecordReviewTodoScopeUnavailable(RecordReviewUnavailable):
    """请求范围存在尚未接通可信审核来源的场景或规则集。"""


def _task_review_scopes() -> dict[str, str]:
    """任务审核只消费已有运行LX与四川终末结果owner。"""
    return {
        key: rule.scope for key, rule in SICHUAN_RULE_SETS.items()
        if (key == LUXIAN_0609_RULE_SET_KEY and rule.scope == "running")
        or (key.startswith("sc_content_") and rule.scope == "final")
    }


def _task_review_supported(task: Any) -> bool:
    version = task.get("rule_set_version")
    scopes = _task_review_scopes()
    return (isinstance(version, str) and bool(version.strip())
            and task.get("rule_set_key") in scopes
            and scopes[task["rule_set_key"]] == task.get("scene"))


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
        "review_context": row.review_context,
        "scene": row.scene,
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


def _derive_state(decisions: list[Any], job_id: str, envelope_id: str) -> tuple[str, str, Any | None]:
    """单病例与批量共用的唯一状态推导：返回 (state, stage, 当前决定行或 None)。

    decisions 须为同三坐标 + rule_set_key 的全部决定，按 created_at、id 倒序。
    """
    current = next(
        (row for row in decisions if row.job_id == job_id and row.envelope_id == envelope_id), None,
    )
    if current is not None:
        return current.decision, current.stage, current
    stage = _stage_from_decisions(decisions, job_id, envelope_id)
    return ("pending_recheck" if stage == "recheck" else "pending_review"), stage, None


def task_approved_counts(session: Any, tasks: Iterable[Any], records: Iterable[Any]) -> dict[str, int | None]:
    """任务列表审核通过数：每病例只看当前受领结果对象，部分重跑不遮蔽其他病例。

    输入由任务列表 owner 完成权限过滤；这里只读运行、Envelope 和审核决定。
    SC额外读取job冻结范围，不实例化workspace或初始化表；身份或结果歧义使整任务未知。
    """
    task_map = {task["id"]: task for task in tasks}
    record_rows = list(records)
    counts: dict[str, int | None] = {
        key: 0 if _task_review_supported(task) else None
        for key, task in task_map.items()
    }
    if not task_map or not record_rows:
        return counts
    runs: dict[tuple[str, str], list[Any]] = {}
    for chunk in _chunks(task_map):
        for run in session.execute(
            select(QCTaskQCRun.__table__).where(
                QCTaskQCRun.task_id.in_(chunk), QCTaskQCRun.run_scope == "assigned",
            ).order_by(QCTaskQCRun.run_number.desc())
        ).mappings().all():
            runs.setdefault((run["task_id"], run["triggered_by"]), []).append(run)
    job_ids = {run["job_id"] for rows in runs.values() for run in rows}
    sc_job_ids = {run["job_id"] for rows in runs.values() for run in rows
                  if str(task_map[run["task_id"]].get("rule_set_key") or "").startswith("sc_content_")}
    sc_refs: dict[str, set[tuple[str, str, str]] | None] = {}
    sc_pending: set[str] = set()
    if sc_job_ids:
        from .task_list_summary_service import _job_status_table

        job_table = _job_status_table()
        for chunk in _chunks(sc_job_ids):
            for job in session.execute(select(job_table.c.id, job_table.c.filters_json, job_table.c.status).where(
                job_table.c.id.in_(chunk),
            )).mappings().all():
                if job["status"] in {"queued", "pending", "running", "processing"}:
                    sc_pending.add(job["id"])
                try:
                    filters = json.loads(job["filters_json"] or "{}")
                    if not isinstance(filters, dict):
                        raise ValueError()
                    refs = filters.get("record_refs")
                    if not isinstance(refs, list) or not refs:
                        raise ValueError()
                    sc_refs[job["id"]] = {tuple(ref[key] for key in _IDENTITY_KEYS) for ref in refs}
                except (KeyError, TypeError, ValueError):
                    sc_refs[job["id"]] = None
    envelopes: dict[tuple[str, tuple[str, str, str], str, str], list[tuple[str, str]]] = {}
    table = _envelope_table()
    sc_envelopes: dict[str, Any] = {}
    for chunk in _chunks(sc_job_ids):
        for env in session.execute(select(table).where(
            table.c.root_job_id.in_(chunk), table.c.rule_set_key.like("sc_content_%"),
        )).mappings().all():
            sc_envelopes[env["id"]] = env
    for chunk in _chunks(job_ids):
        for env in session.execute(select(
            table.c.id, table.c.root_job_id, table.c.created_by,
            table.c.institute_id, table.c.patient_id, table.c.visit_id,
            table.c.rule_set_key, table.c.rule_set_version,
        ).where(table.c.root_job_id.in_(chunk))).mappings().all():
            key = (env["root_job_id"],
                   (env["institute_id"], env["patient_id"], env["visit_id"]),
                   env["rule_set_key"], env["rule_set_version"])
            owner = env["created_by"]
            if str(env["rule_set_key"]).startswith("sc_content_"):
                from .sc_final_task_review_envelope_service import load_items

                try:
                    load_items(sc_envelopes[env["id"]], source={"job_id": env["root_job_id"], "scene": "final",
                                            **{k: env[k] for k in (*_IDENTITY_KEYS, "rule_set_key", "rule_set_version")}})
                except (KeyError, TypeError, ValueError):
                    owner = None
            envelopes.setdefault(key, []).append((env["id"], owner))
    decisions: dict[tuple[str, str, str], list[Any]] = {}
    for chunk in _chunks(job_ids):
        for review in session.execute(
            select(QCRecordReview).where(QCRecordReview.job_id.in_(chunk))
            .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
        ).scalars().all():
            decisions.setdefault((review.institute_id, review.patient_id, review.visit_id), []).append(review)
    seen: set[tuple[str, tuple[str, str, str]]] = set()
    for record in record_rows:
        task_id = record["task_id"]
        task = task_map[task_id]
        identity = _identity(record)
        if identity is None or (task_id, identity) in seen:
            counts[task_id] = None
            continue
        seen.add((task_id, identity))
        if counts[task_id] is None:
            continue
        for run in runs.get((task_id, record.get("assignee_id")), []):
            ids = envelopes.get((run["job_id"], identity,
                                 task["rule_set_key"], task["rule_set_version"]), [])
            if not ids:
                if task["rule_set_key"].startswith("sc_content_"):
                    if run["job_id"] in sc_pending:
                        continue
                    refs = sc_refs.get(run["job_id"])
                    if refs is None or identity in refs:
                        counts[task_id] = None
                        break
                continue  # 所选病例子集没有本病例：保留其更早的当前结果。
            if len(ids) != 1 or ids[0][1] != run["triggered_by"]:
                counts[task_id] = None
                break
            current_decisions = [item for item in decisions.get(identity, [])
                                 if item.rule_set_key == task["rule_set_key"]
                                 and item.rule_set_version == task["rule_set_version"]]
            state, _, _ = _derive_state(current_decisions, run["job_id"], ids[0][0])
            if state == "approved":
                counts[task_id] += 1
            break
    return counts


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


def _validate_task_envelope(session: Any, *, envelope_id: str, identity: tuple[str, str, str],
                            task: Any, result: dict, actor_id: str) -> None:
    if not task["rule_set_key"].startswith("sc_content_"):
        return
    from .sc_final_task_review_envelope_service import load_items

    table = _envelope_table()
    row = session.execute(select(table).where(
        table.c.id == envelope_id,
    ).with_for_update(read=True)).mappings().first()
    if row is None or row["created_by"] != actor_id:
        raise TaskQCRunConflict("审核结果信封不存在或不属于本人")
    try:
        load_items(row, source={"job_id": result["job_id"], "institute_id": identity[0],
                               "patient_id": identity[1], "visit_id": identity[2],
                               "rule_set_key": task["rule_set_key"],
                               "rule_set_version": task["rule_set_version"], "scene": task["scene"]},
                   result=result)
    except (TypeError, ValueError) as exc:
        raise TaskQCRunConflict("审核信封内容或来源无效") from exc


def _assert_current_sc_result(session: Any, *, task: Any, identity: tuple[str, str, str],
                              task_record_id: str, run_number: int, actor_id: str,
                              factory: Callable[[], Any]) -> None:
    """子集重跑不遮蔽其他病例；只拒绝本病例更新的可用结果对象。"""
    if not task["rule_set_key"].startswith("sc_content_"):
        return
    runs = session.execute(select(QCTaskQCRun.__table__).where(
        QCTaskQCRun.task_id == task["id"], QCTaskQCRun.run_scope == "assigned",
        QCTaskQCRun.triggered_by == actor_id, QCTaskQCRun.run_number > run_number,
    ).order_by(QCTaskQCRun.run_number.desc())).mappings().all()
    for run in runs:
        ids = _envelope_ids(session, job_id=run["job_id"], identity=identity,
                            rule_set_key=task["rule_set_key"], rule_set_version=task["rule_set_version"])
        if not ids:
            try:
                result = _read_result(task_id=task["id"], task_record_id=task_record_id,
                                      run_number=run["run_number"], actor_id=actor_id, workspace_factory=factory)
            except TaskQCRunNotFound:
                continue
            except (TaskQCRunForbidden, TaskQCRunConflict) as exc:
                raise RecordReviewConflict("result_unavailable", "较新结果来源不可核实") from exc
            if result.get("result_state") == "available":
                raise RecordReviewConflict("result_unavailable", "较新结果缺少可信审核信封")
            continue
        if len(ids) != 1:
            raise RecordReviewConflict("result_unavailable", "较新结果对象不唯一")
        try:
            result = _read_result(task_id=task["id"], task_record_id=task_record_id,
                                  run_number=run["run_number"], actor_id=actor_id, workspace_factory=factory)
            if result.get("result_state") != "available":
                continue
            _validate_task_envelope(session, envelope_id=ids[0], identity=identity,
                                    task=task, result=result, actor_id=actor_id)
        except (TaskQCRunNotFound, TaskQCRunForbidden, TaskQCRunConflict) as exc:
            raise RecordReviewConflict("result_unavailable", "较新结果来源不可核实") from exc
        raise RecordReviewConflict("result_changed", "已有较新质控结果，请刷新后审核")


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
    if not _task_review_supported(task):
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
            try:
                _validate_task_envelope(session, envelope_id=envelope_id, identity=identity,
                                        task=task, result=result, actor_id=actor_id)
                _assert_current_sc_result(session, task=task, identity=identity,
                                          task_record_id=task_record_id, run_number=run_number,
                                          actor_id=actor_id, factory=factory)
            except (TaskQCRunConflict, RecordReviewConflict):
                view["reason_code"] = "result_invalid"
                return view
            view["result"]["envelope_id"] = envelope_id
            decisions = _case_decisions(session, identity, rule_set_key, None)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc

    state, stage, current = _derive_state(decisions, job_id, envelope_id)
    if current is not None:
        view.update(state=state, stage=stage, current=_review_dict(current))
        return view
    view.update(state=state, stage=stage, can_submit=can_submit_status)
    return view


# ---------------------------------------------------------------------------
# POST 决定
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DecisionRequest:
    task_id: str | None
    task_record_id: str | None
    run_number: int | None
    decision: str
    reason: str | None
    request_id: str
    envelope_id: str
    actor_id: str
    review_context: str = CONTEXT_TASK
    # workspace 上下文由客户端提交三坐标与 job_id；task 上下文由任务病历推出，保持 None。
    identity: tuple[str, str, str] | None = None
    job_id: str | None = None


def _normalize_request(
    *, task_id: str, task_record_id: str, run_number: int, decision: str,
    reason: str | None, request_id: str, envelope_id: str, actor_id: str,
) -> _DecisionRequest:
    _validate_actor(actor_id)
    if type(run_number) is not int or run_number <= 0:
        raise RecordReviewInvalid("运行序号无效")
    reason = _normalize_decision_fields(
        decision=decision, reason=reason, request_id=request_id, envelope_id=envelope_id,
    )
    return _DecisionRequest(
        task_id=task_id, task_record_id=task_record_id, run_number=run_number,
        decision=decision, reason=reason, request_id=request_id,
        envelope_id=envelope_id, actor_id=actor_id,
    )


def _normalize_decision_fields(
    *, decision: str, reason: str | None, request_id: str, envelope_id: str,
) -> str | None:
    """两种上下文共用的决定字段校验；返回规范化后的原因（存疑必填）。"""
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
    return reason


def _replay(row: QCRecordReview, req: _DecisionRequest) -> dict[str, Any]:
    if (
        (row.review_context or CONTEXT_TASK) != req.review_context
        or (req.job_id is not None and row.job_id != req.job_id)
        or (req.identity is not None and (row.institute_id, row.patient_id, row.visit_id) != req.identity)
        or row.task_id != req.task_id or row.task_record_id != req.task_record_id
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
    return _run_submit(lambda: _submit(req, factory), req)


def _run_submit(submit: Callable[[], dict[str, Any]], req: _DecisionRequest) -> dict[str, Any]:
    """两种上下文共用的提交外壳：唯一约束竞争兜底与数据库故障脱敏。"""
    try:
        return submit()
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


def _insert_decision(
    session: Any, req: _DecisionRequest, *, identity: tuple[str, str, str],
    rule_set_key: str, rule_set_version: str, job_id: str, scene: str,
) -> dict[str, Any]:
    """锁内最后一步（两种上下文共用）：已决定检查 → 计算 stage → 追加一行决定。"""
    decisions = _case_decisions(session, identity, rule_set_key, None)
    if any(row.job_id == job_id and row.envelope_id == req.envelope_id for row in decisions):
        raise RecordReviewConflict("already_decided", "该结果已有审核决定")
    stage = _stage_from_decisions(decisions, job_id, req.envelope_id)
    captured_at = _now()
    snapshot = None
    if stage == "initial":
        from .record_review_defect_snapshot_service import DefectSnapshotInvalid, capture_snapshot

        try:
            snapshot = capture_snapshot(
                session, source={"job_id": job_id, "envelope_id": req.envelope_id,
                                 "institute_id": identity[0], "patient_id": identity[1],
                                 "visit_id": identity[2], "rule_set_key": rule_set_key,
                                 "rule_set_version": rule_set_version, "scene": scene},
                captured_at=captured_at, envelope_table=_envelope_table(),
                batch_job_table_factory=_batch_job_table,
            )
        except DefectSnapshotInvalid as exc:
            raise RecordReviewConflict("defect_snapshot_unavailable", str(exc)) from exc
    row = QCRecordReview(
        id=str(uuid4()), request_id=req.request_id, review_context=req.review_context,
        scene=scene,
        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        rule_set_key=rule_set_key, rule_set_version=rule_set_version,
        job_id=job_id, envelope_id=req.envelope_id,
        task_id=req.task_id, task_record_id=req.task_record_id,
        run_number=req.run_number, stage=stage, decision=req.decision,
        reason=req.reason, reviewer_id=req.actor_id, created_at=captured_at,
        defect_snapshot=snapshot,
    )
    session.add(row)
    session.flush()
    return _review_dict(row)


def _review_scene(value: Any) -> str | None:
    """把任务/作业场景规范到工作台场景；未知值不猜测。"""
    normalized = str(value or "").strip().lower()
    return {
        "running": "running",
        "final": "final",
        "outpatient": "outpatient_emergency",
        "outpatient_emergency": "outpatient_emergency",
    }.get(normalized)


def _required_review_scene(value: Any) -> str:
    scene = _review_scene(value)
    if scene is None:
        raise RecordReviewConflict("result_unavailable", "审核上下文缺少可信场景")
    return scene


def _batch_job_table() -> Any:
    """延迟取得 workspace job 表，便于测试替换且避免模块导入时连接数据库。"""
    from .custom_qc_workspace_service import _batch_jobs_table

    return _batch_jobs_table()


def _workspace_review_scene(
    session: Any, *, job_id: str, identity: tuple[str, str, str],
) -> str:
    """从已核实根 job 的冻结病例快照读取工作场景，不根据病历状态反推。"""
    table = _batch_job_table()
    row = session.execute(
        select(table.c.scene, table.c.scope, table.c.filters_json)
        .where(table.c.id == job_id)
        .with_for_update(read=True)
    ).mappings().first()
    if row is None:
        raise RecordReviewConflict("result_changed", "质控结果所属任务已不存在")
    return _workspace_scene_from_job(row, identity=identity)


def _workspace_scene_from_job(row: Any, *, identity: tuple[str, str, str]) -> str:
    """单例与批量读取共用冻结场景判定，批量调用不重复查询任务。"""
    try:
        filters = json.loads(row["filters_json"] or "{}")
    except (TypeError, ValueError) as exc:
        raise RecordReviewConflict("result_unavailable", "质控结果缺少可信场景") from exc
    if not isinstance(filters, dict):
        raise RecordReviewConflict("result_unavailable", "质控结果缺少可信场景")

    raw_snapshot = filters.get("record_scene_snapshot")
    if raw_snapshot is not None and not isinstance(raw_snapshot, list):
        raise RecordReviewConflict("result_unavailable", "质控结果场景快照格式无效")

    snapshot_scenes: set[str] = set()
    matched_snapshot = False
    for raw in raw_snapshot or []:
        if not isinstance(raw, dict):
            raise RecordReviewConflict("result_unavailable", "质控结果场景快照格式无效")
        snapshot_identity = tuple(str(raw.get(key) or "").strip() for key in _IDENTITY_KEYS)
        if snapshot_identity != identity:
            continue
        matched_snapshot = True
        scene = _review_scene(raw.get("resolved_scene") or raw.get("record_scene"))
        if scene is None:
            raise RecordReviewConflict("result_unavailable", "质控结果场景快照无效")
        snapshot_scenes.add(scene)
    if len(snapshot_scenes) > 1:
        raise RecordReviewConflict("result_unavailable", "质控结果场景快照冲突")
    if matched_snapshot:
        # 混合范围 job 的根 scene 只描述任务外壳；病例快照是单病例归属的权威 owner。
        return next(iter(snapshot_scenes))
    if raw_snapshot is not None:
        raise RecordReviewConflict("result_unavailable", "质控结果缺少当前病例场景快照")

    job_scene = _review_scene(row["scene"])
    scope_scene = _review_scene(row["scope"])
    if job_scene is not None and scope_scene is not None and job_scene != scope_scene:
        raise RecordReviewConflict("result_unavailable", "质控结果根场景冲突")
    scene = job_scene or scope_scene
    if scene is None:
        raise RecordReviewConflict("result_unavailable", "质控结果缺少可信场景")
    return scene


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
            if str(task_rule or "").startswith("sc_content_"):
                from .qc_workspace.canonical_result_store import lock_case_result_mutations

                lock_case_result_mutations(session, [CaseRef(*identity)], rule_set_key=task_rule)
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
            if not _task_review_supported(task):
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
            try:
                _validate_task_envelope(session, envelope_id=req.envelope_id, identity=identity,
                                        task=task, result=result, actor_id=req.actor_id)
            except TaskQCRunConflict as exc:
                raise RecordReviewConflict("result_unavailable", "审核信封不可核实") from exc
            _assert_current_sc_result(session, task=task, identity=identity,
                                      task_record_id=req.task_record_id, run_number=req.run_number,
                                      actor_id=req.actor_id, factory=factory)

            response = _insert_decision(
                session, req, identity=identity, rule_set_key=rule_set_key,
                rule_set_version=rule_set_version, job_id=job_id,
                scene=_required_review_scene(task["scene"]),
            )
    state = response["decision"]
    return {**response, "state": state, "idempotent": False}


# ---------------------------------------------------------------------------
# workspace 上下文：运行/终末列表按单病历 DTO 的最新 ready 结果审核（P0-2）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CaseAnchor:
    job_id: str
    envelope_id: str
    rule_set_version: str


def _normalize_identity(institute_id: Any, patient_id: Any, visit_id: Any) -> tuple[str, str, str] | None:
    parts = []
    for value in (institute_id, patient_id, visit_id):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128:
            return None
        parts.append(value.strip())
    return parts[0], parts[1], parts[2]


def _require_identity(institute_id: Any, patient_id: Any, visit_id: Any) -> tuple[str, str, str]:
    identity = _normalize_identity(institute_id, patient_id, visit_id)
    if identity is None:
        raise RecordReviewInvalid("病历三坐标无效")
    return identity


def _read_case_dto(identity: tuple[str, str, str], factory: Callable[[], Any]) -> Any:
    """复用单病历结果读取器（与结果抽屉同一入口），不另写选择逻辑。"""
    try:
        return factory().build_latest_single_record_result_dto(
            institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        )
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("质控结果暂不可用") from exc


def _case_anchor(dto: Any) -> tuple[_CaseAnchor | None, str | None]:
    """从 DTO 取当前结果对象；不可审核时返回原因码。只读取字段，不重判结果。"""
    if not isinstance(dto, dict):
        return None, "result_invalid"
    state = str(dto.get("state") or "").strip()
    if state != "ready":
        return None, f"result_{state or 'unknown'}"
    if dto.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY:
        return None, "unsupported_rule_set"
    job_id = str(dto.get("job_id") or "").strip()
    root_job_id = str(dto.get("root_job_id") or "").strip()
    version = str(dto.get("rule_set_version") or "").strip()
    if not root_job_id or root_job_id != job_id or len(root_job_id) > 36 or not version:
        return None, "result_invalid"
    envelope_id = str(dto.get("envelope_id") or "").strip()
    if not envelope_id or len(envelope_id) > 36:
        return None, "envelope_missing"
    return _CaseAnchor(job_id=root_job_id, envelope_id=envelope_id, rule_set_version=version), None


def get_case_review(
    *, institute_id: str, patient_id: str, visit_id: str, actor_id: str,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """读取病例在最新 ready 结果上的审核状态、当前决定与历史（workspace 上下文）。"""
    _validate_actor(actor_id)
    identity = _require_identity(institute_id, patient_id, visit_id)
    _require_session()
    dto = _read_case_dto(identity, workspace_factory or _default_workspace_factory)
    anchor, reason_code = _case_anchor(dto)
    try:
        with SessionLocal() as session:
            decisions = _case_decisions(session, identity, LUXIAN_0609_RULE_SET_KEY, None)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc

    view: dict[str, Any] = {
        "review_context": CONTEXT_WORKSPACE,
        "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "state": "unavailable", "stage": None, "reason_code": reason_code, "can_submit": False,
        "current": None, "history": [_review_dict(row) for row in decisions[:HISTORY_LIMIT]],
        "result": {"job_id": None, "envelope_id": None},
    }
    if anchor is None:
        return view
    view["result"] = {"job_id": anchor.job_id, "envelope_id": anchor.envelope_id}
    state, stage, current = _derive_state(decisions, anchor.job_id, anchor.envelope_id)
    view.update(
        state=state, stage=stage,
        current=_review_dict(current) if current is not None else None,
        can_submit=current is None,
    )
    return view


def submit_case_review(
    *, institute_id: str, patient_id: str, visit_id: str, job_id: str, envelope_id: str,
    decision: str, reason: str | None, request_id: str, actor_id: str,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """在锁内重读单病历 DTO 核对结果对象，并追加一条 workspace 上下文决定。"""
    _validate_actor(actor_id)
    identity = _require_identity(institute_id, patient_id, visit_id)
    if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 36:
        raise RecordReviewInvalid("结果任务 ID 无效")
    reason = _normalize_decision_fields(
        decision=decision, reason=reason, request_id=request_id, envelope_id=envelope_id,
    )
    req = _DecisionRequest(
        task_id=None, task_record_id=None, run_number=None,
        decision=decision, reason=reason, request_id=request_id,
        envelope_id=envelope_id, actor_id=actor_id,
        review_context=CONTEXT_WORKSPACE, identity=identity, job_id=job_id,
    )
    _require_session()
    factory = workspace_factory or _default_workspace_factory
    return _run_submit(lambda: _submit_case(req, identity, factory), req)


def _submit_case(
    req: _DecisionRequest, identity: tuple[str, str, str], factory: Callable[[], Any],
) -> dict[str, Any]:
    with SessionLocal() as session:
        with session.begin():
            # 与任务上下文同一把锁：三坐标 + 规则集，保证跨上下文串行判定。
            _advisory_lock(session, identity, LUXIAN_0609_RULE_SET_KEY)
            existing = _find_by_request(session, req.request_id)
            if existing is not None:
                return _replay(existing, req)
            anchor, reason_code = _case_anchor(_read_case_dto(identity, factory))
            if anchor is None:
                if reason_code == "unsupported_rule_set":
                    raise RecordReviewConflict("unsupported_rule_set", "当前规则集不支持病历审核")
                raise RecordReviewConflict("result_unavailable", "当前病历没有可审核的最新质控结果")
            if anchor.job_id != req.job_id or anchor.envelope_id != req.envelope_id:
                raise RecordReviewConflict("result_changed", "质控结果已更新，请刷新后重新审核")
            response = _insert_decision(
                session, req, identity=identity, rule_set_key=LUXIAN_0609_RULE_SET_KEY,
                rule_set_version=anchor.rule_set_version, job_id=anchor.job_id,
                scene=_workspace_review_scene(
                    session, job_id=anchor.job_id, identity=identity,
                ),
            )
    return {**response, "state": response["decision"], "idempotent": False}


def resolve_workspace_result_reference(
    *, institute_id: str, patient_id: str, visit_id: str,
    expected_job_id: str, expected_envelope_id: str,
    workspace_factory: Callable[[], Any] | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """只读解析当前 workspace 结果引用，不授予权限或保证创建原子性。

    返回的是调用时的当前候选。``session`` 仅让 Envelope 存在性、三坐标、
    job、规则版本与场景在调用方事务内再次核实；当前 DTO
    读取器仍自行管理会话，因此本函数不能单独充当后续创建写入的 TOCTOU 守卫。
    它不阻止并发新结果成为 latest；后续创建必须另行明确最新/历史结果政策。
    """
    identity = _require_identity(institute_id, patient_id, visit_id)
    if (
        not isinstance(expected_job_id, str) or not expected_job_id.strip()
        or len(expected_job_id.strip()) > 36
        or not isinstance(expected_envelope_id, str) or not expected_envelope_id.strip()
        or len(expected_envelope_id.strip()) > 36
    ):
        raise RecordReviewInvalid("结果引用无效")
    if session is None:
        _require_session()
    dto = _read_case_dto(identity, workspace_factory or _default_workspace_factory)
    anchor, reason_code = _case_anchor(dto)
    if anchor is None:
        if reason_code == "unsupported_rule_set":
            raise RecordReviewConflict("unsupported_rule_set", "当前规则集不支持申诉来源解析")
        raise RecordReviewConflict("result_unavailable", "当前病历没有可引用的最新质控结果")
    if (
        anchor.job_id != expected_job_id.strip()
        or anchor.envelope_id != expected_envelope_id.strip()
    ):
        raise RecordReviewConflict("result_changed", "质控结果已更新，请刷新后重试")
    from .qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref

    try:
        expected_record_ref = keyed_ref(
            "rec", CaseRef(*identity).as_key(), hmac_key=customer_safe_projection_key(),
        )
    except RuntimeError as exc:
        raise RecordReviewUnavailable("质控结果引用暂不可用") from exc
    if str(dto.get("record_ref") or "").strip() != expected_record_ref:
        raise RecordReviewConflict("result_unavailable", "质控结果病例引用不一致")
    raw_items = dto.get("items") if isinstance(dto, dict) else None
    if not isinstance(raw_items, list):
        raise RecordReviewConflict("result_unavailable", "质控结果条目不可用")

    def build(active_session: Any) -> dict[str, Any]:
        envelope_ids = _envelope_ids(
            active_session, job_id=anchor.job_id, identity=identity,
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=anchor.rule_set_version,
        )
        if len(envelope_ids) != 1:
            raise RecordReviewConflict(
                "result_unavailable",
                "质控结果对象缺失" if not envelope_ids else "质控结果对象不唯一",
            )
        if envelope_ids[0] != anchor.envelope_id:
            raise RecordReviewConflict("result_changed", "质控结果已更新，请刷新后重试")
        return {
            "institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
            "scene": _workspace_review_scene(
                active_session, job_id=anchor.job_id, identity=identity,
            ),
            "root_job_id": anchor.job_id, "envelope_id": anchor.envelope_id,
            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": anchor.rule_set_version,
            "items": [dict(item) if isinstance(item, dict) else item for item in raw_items],
        }

    try:
        if session is not None:
            return build(session)
        with SessionLocal() as read_session:
            return build(read_session)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("质控结果引用暂不可用") from exc


def _batch_anchors(results: Iterable[Any]) -> dict[tuple[str, str, str], tuple[str, str]]:
    """批量锚点校验：锚点不完整或规则集非 LX0609 的病例直接跳过。"""
    anchors: dict[tuple[str, str, str], tuple[str, str]] = {}
    for item in results:
        if not isinstance(item, dict) or item.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY:
            continue
        identity = _normalize_identity(item.get("institute_id"), item.get("patient_id"), item.get("visit_id"))
        job_id = str(item.get("job_id") or "").strip()
        envelope_id = str(item.get("envelope_id") or "").strip()
        if identity is None or not job_id or not envelope_id:
            continue
        anchors[identity] = (job_id, envelope_id)
    return anchors


def _batch_case_decisions(
    session: Any, anchors: dict[tuple[str, str, str], tuple[str, str]],
) -> dict[tuple[str, str, str], list[Any]]:
    """列表挂载与导出共用的唯一批量决定查询：按 visit_id 分块，倒序。"""
    decisions_by_case: dict[tuple[str, str, str], list[Any]] = {}
    for chunk in _chunks(sorted({identity[2] for identity in anchors})):
        for row in session.execute(
            select(
                QCRecordReview.id, QCRecordReview.institute_id, QCRecordReview.patient_id,
                QCRecordReview.visit_id, QCRecordReview.job_id, QCRecordReview.envelope_id,
                QCRecordReview.stage, QCRecordReview.decision, QCRecordReview.reason,
                QCRecordReview.reviewer_id, QCRecordReview.created_at,
            )
            .where(
                QCRecordReview.visit_id.in_(chunk),
                QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            )
            .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
        ).all():
            case = (row.institute_id, row.patient_id, row.visit_id)
            if case in anchors:
                decisions_by_case.setdefault(case, []).append(row)
    return decisions_by_case


def batch_review_states(results: Iterable[Any]) -> dict[tuple[str, str, str], str]:
    """批量推导病例审核状态，供运行/终末列表挂载 review_state。

    入参每项含三坐标、job_id、envelope_id、rule_set_key；锚点不完整或规则集非 LX0609 的
    病例不出现在返回值中（调用方显示为未知）。决定按 visit_id 分块一次性读取，
    状态推导与单病例共用 _derive_state。数据库故障抛 RecordReviewUnavailable。
    """
    anchors = _batch_anchors(results)
    if not anchors:
        return {}
    _require_session()
    try:
        with SessionLocal() as session:
            decisions_by_case = _batch_case_decisions(session, anchors)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc
    return {
        identity: _derive_state(decisions_by_case.get(identity, []), job_id, envelope_id)[0]
        for identity, (job_id, envelope_id) in anchors.items()
    }


def batch_current_reviews(results: Iterable[Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """批量读取病例审核状态及“当前结果对象上的决定”，供服务端导出。

    与 batch_review_states 同一锚点校验、同一决定查询、同一 _derive_state 推导；
    额外返回当前决定的原因、审核人（显示名，缺失时为 None）与决定时间（库内无时区 UTC）。
    尚无决定的病例 decision/reason/reviewer_*/reviewed_at 均为 None。
    锚点不完整的病例不出现在返回值中；数据库故障抛 RecordReviewUnavailable。
    """
    from .case_operation_timeline_service import _display_names

    anchors = _batch_anchors(results)
    if not anchors:
        return {}
    _require_session()
    try:
        with SessionLocal() as session:
            decisions_by_case = _batch_case_decisions(session, anchors)
            derived = {
                identity: _derive_state(decisions_by_case.get(identity, []), job_id, envelope_id)
                for identity, (job_id, envelope_id) in anchors.items()
            }
            reviewer_ids = {
                str(current.reviewer_id)
                for _, _, current in derived.values()
                if current is not None and current.reviewer_id
            }
            names = _display_names(session, reviewer_ids)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc
    views: dict[tuple[str, str, str], dict[str, Any]] = {}
    for identity, (state, _stage, current) in derived.items():
        reviewer_id = str(current.reviewer_id) if current is not None and current.reviewer_id else None
        views[identity] = {
            "state": state,
            "decision": current.decision if current is not None else None,
            "reason": current.reason if current is not None else None,
            "reviewer_id": reviewer_id,
            "reviewer_name": names.get(reviewer_id) if reviewer_id else None,
            "reviewed_at": current.created_at if current is not None else None,
        }
    return views


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

    数据库往返：范围完整性 1 次 + 候选 1 次 + 运行 1 次 + Envelope 按 job 分块 + 决定按 visit 分块；
    仅对“最新有唯一 Envelope 且未决定”的运行调用一次结果读取器。
    """
    task_scene = _task_scene_filter(scene)
    if task_scene == "outpatient":
        raise RecordReviewTodoScopeUnavailable("门急诊病历审核来源尚未接通")
    review_scopes = _task_review_scopes()
    if not review_scopes:
        raise RecordReviewTodoScopeUnavailable("病历审核规则来源尚未接通")
    supported_source = or_(*(and_(QCTask.rule_set_key == key, QCTask.scene == scope)
                             for key, scope in review_scopes.items()))
    unsupported = (
        select(QCTaskRecord.id)
        .join(QCTask, QCTask.id == QCTaskRecord.task_id)
        .join(QCTaskQCRun, QCTaskQCRun.task_id == QCTask.id)
        .where(
            QCTaskRecord.assignee_id == actor_id,
            QCTaskRecord.status.in_(("in_progress", "completed")),
            QCTask.status == "in_progress",
            QCTaskQCRun.run_scope == "assigned", QCTaskQCRun.triggered_by == actor_id,
            (QCTask.rule_set_key.is_(None)
             | ~supported_source
             | QCTask.rule_set_version.is_(None) | (func.trim(QCTask.rule_set_version) == "")
             | QCTask.scene.is_(None)
             | QCTaskRecord.institute_id.is_(None) | (func.trim(QCTaskRecord.institute_id) == "")
             | QCTaskRecord.patient_id.is_(None) | (func.trim(QCTaskRecord.patient_id) == "")
             | QCTaskRecord.visit_id.is_(None) | (func.trim(QCTaskRecord.visit_id) == "")
             | QCTaskRecord.record_id.is_(None) | (QCTaskRecord.record_id != QCTaskRecord.id)),
        ).limit(1)
    )
    if task_scene is not None:
        unsupported = unsupported.where(QCTask.scene == task_scene)
    if session.execute(unsupported).first() is not None:
        raise RecordReviewTodoScopeUnavailable("当前范围包含尚未接通审核来源的任务结果")
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
            supported_source,
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
    envelopes: dict[tuple[str, tuple[str, str, str], str, str], list[str]] = {}
    for chunk in _chunks(job_ids):
        for env in session.execute(
            select(
                table.c.id, table.c.root_job_id, table.c.institute_id,
                table.c.patient_id, table.c.visit_id, table.c.rule_set_key, table.c.rule_set_version,
            ).where(
                table.c.root_job_id.in_(chunk),
                table.c.rule_set_key.in_(review_scopes),
            )
        ).all():
            key = (env.root_job_id, (env.institute_id, env.patient_id, env.visit_id), env.rule_set_key, env.rule_set_version)
            envelopes.setdefault(key, []).append(str(env.id))

    visit_ids = sorted({identity[2] for _, identity in candidates})
    decisions_by_case: dict[tuple[tuple[str, str, str], str], list[Any]] = {}
    for chunk in _chunks(visit_ids):
        for decision in session.execute(
            select(QCRecordReview)
            .where(
                QCRecordReview.visit_id.in_(chunk),
                QCRecordReview.rule_set_key.in_(review_scopes),
            )
            .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc())
        ).scalars().all():
            case = (decision.institute_id, decision.patient_id, decision.visit_id)
            decisions_by_case.setdefault((case, decision.rule_set_key), []).append(decision)

    shared_workspace: list[Any] = []

    def shared_factory() -> Any:
        # 同一次待办计算只构造一个 workspace 实例，并按 job 缓存只读结果，
        # 避免同一 job 下 N 个病例把整份 Canonical 结果反序列化 N 次。
        if not shared_workspace:
            shared_workspace.append(_JobMemoWorkspace(workspace_factory()))
        return shared_workspace[0]

    items: list[dict[str, Any]] = []
    for row, identity in candidates:
        decisions = decisions_by_case.get((identity, row["rule_set_key"]), [])
        decided = {(item.job_id, item.envelope_id) for item in decisions}
        for run in runs_by_task.get(row["task_id"], []):
            ids = envelopes.get((run.job_id, identity, row["rule_set_key"], row["rule_set_version"]), [])
            if len(ids) != 1:
                if row["rule_set_key"].startswith("sc_content_"):
                    if ids:
                        raise RecordReviewTodoScopeUnavailable("当前终末任务审核信封不唯一")
                    try:
                        missing_result = _read_result(
                            task_id=row["task_id"], task_record_id=row["id"],
                            run_number=run.run_number, actor_id=actor_id, workspace_factory=shared_factory,
                        )
                    except TaskQCRunNotFound:
                        continue
                    except (TaskQCRunForbidden, TaskQCRunConflict):
                        raise RecordReviewTodoScopeUnavailable("当前终末任务结果来源不可核实") from None
                    if missing_result.get("result_state") == "available":
                        raise RecordReviewTodoScopeUnavailable("历史终末结果缺少可信审核信封")
                continue  # Envelope 缺失或不唯一：本运行结果不可用，退回更早运行
            envelope_id = ids[0]
            if (run.job_id, envelope_id) in decided and not row["rule_set_key"].startswith("sc_content_"):
                break  # 最新结果对象已有决定：不在待办中
            try:
                result = _read_result(
                    task_id=row["task_id"], task_record_id=row["id"],
                    run_number=run.run_number, actor_id=actor_id,
                    workspace_factory=shared_factory,
                )
            except (TaskQCRunNotFound, TaskQCRunForbidden, TaskQCRunConflict):
                if row["rule_set_key"].startswith("sc_content_"):
                    raise RecordReviewTodoScopeUnavailable("当前终末任务结果来源不可核实") from None
                continue
            if result.get("result_state") != "available" or result.get("job_id") != run.job_id:
                continue
            try:
                _validate_task_envelope(session, envelope_id=envelope_id, identity=identity,
                                        task=row, result=result, actor_id=actor_id)
            except TaskQCRunConflict:
                raise RecordReviewTodoScopeUnavailable("当前终末任务审核信封不可核实") from None
            if (run.job_id, envelope_id) in decided:
                break
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
) -> dict[str, Any]:
    """首页待办计数；与待办列表共用 _pending_todo_items 谓词。"""
    try:
        items = _collect_todos(actor_id, scene, workspace_factory)
    except RecordReviewTodoScopeUnavailable:
        return {"initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable"}
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
    "batch_current_reviews",
    "batch_review_states",
    "count_my_record_review_todos",
    "get_case_review",
    "get_record_review",
    "list_my_record_review_todos",
    "resolve_workspace_result_reference",
    "submit_case_review",
    "submit_record_review",
]
