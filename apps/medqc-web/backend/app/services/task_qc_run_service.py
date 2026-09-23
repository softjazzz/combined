"""把已抽样任务与四川 workspace 批量 job 原子关联。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from .case_identity import CaseRef
from .custom_qc_workspace_service import project_customer_safe_result_item
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .luxian_0916.execution_integrity import (
    LUXIAN_0916_RULE_IDS,
    LUXIAN_0916_RULE_SET_KEY,
    validate_luxian_0916_task_delivery,
)
from .luxian_0916.rule_catalog import get_luxian_0916_rule_definition
from .qc_rule_sets import get_sichuan_rule_set
from .qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref
from .sichuan_workspace_batch_prepare import (
    SichuanWorkspaceBatchJobCreateRequest,
    prepare_workspace_batch_job,
)


logger = logging.getLogger(__name__)


class TaskQCRunNotFound(LookupError):
    pass


class TaskQCRunForbidden(PermissionError):
    pass


class TaskQCRunConflict(ValueError):
    pass


class TaskQCRunDispatchError(RuntimeError):
    def __init__(self, job_id: str):
        super().__init__(f"批量质控任务 {job_id} 已创建，但后台派发失败")
        self.job_id = job_id


def _task_and_refs(
    session: Session, task_id: str, actor_id: str, run_scope: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    task_row = session.execute(
        select(QCTask.__table__)
        .where(QCTask.id == task_id)
        .with_for_update()
    ).mappings().first()
    if task_row is None:
        raise TaskQCRunNotFound("任务不存在")
    task = dict(task_row)
    if run_scope == "all" and task.get("creator_id") != actor_id:
        raise TaskQCRunForbidden("仅任务创建人可启动整批质控")
    scene = task.get("scene")
    if scene == "outpatient":
        raise TaskQCRunConflict("门急诊场景尚无可执行的规则集与 workspace 资料链")
    if scene not in ("running", "final"):
        raise TaskQCRunConflict("历史任务尚无完整三坐标执行合同")
    allowed_statuses = {"sampling", "assigned", "in_progress", "completed"} if run_scope == "all" else {
        "assigned", "in_progress", "completed",
    }
    if task.get("status") not in allowed_statuses:
        raise TaskQCRunConflict("任务未完成抽样或已取消")
    rule_set_key = task.get("rule_set_key")
    rule_set = get_sichuan_rule_set(rule_set_key) if rule_set_key else None
    if rule_set is None or rule_set.scope != scene:
        raise TaskQCRunConflict("任务规则集已失效或与场景不匹配")
    frozen_version = task.get("rule_set_version")
    if not frozen_version or frozen_version != rule_set.version:
        raise TaskQCRunConflict("任务规则集版本缺失或已与当前目录不一致")

    rows = session.execute(
        select(QCTaskRecord.__table__)
        .where(QCTaskRecord.task_id == task_id)
        .order_by(QCTaskRecord.created_at, QCTaskRecord.id)
    ).mappings().all()
    try:
        expected_count = int(task.get("total_records"))
    except (TypeError, ValueError) as exc:
        raise TaskQCRunConflict("任务抽样数量无效") from exc
    if expected_count <= 0 or len(rows) != expected_count:
        raise TaskQCRunConflict("任务抽样关联与数量不一致")

    refs: list[dict[str, str]] = []
    assigned_refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        identity = tuple(str(row.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id"))
        if any(not value or len(value) > 100 for value in identity):
            raise TaskQCRunConflict("任务病历缺少完整三坐标")
        if row["record_id"] != row["id"] or identity in seen:
            raise TaskQCRunConflict("任务病历身份不符合三坐标抽样合同")
        if run_scope == "assigned" and not str(row.get("assignee_id") or "").strip():
            raise TaskQCRunConflict("任务病历尚未完成分配")
        seen.add(identity)
        ref = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
        refs.append(ref)
        if row.get("assignee_id") == actor_id:
            assigned_refs.append(ref)
    if run_scope == "assigned":
        if not assigned_refs:
            raise TaskQCRunForbidden("当前用户未获分配此任务病历")
        return task, assigned_refs
    return task, refs


def _next_run_number(session: Session, task_id: str, workspace: Any) -> int:
    previous = session.execute(
        select(QCTaskQCRun.__table__)
        .where(QCTaskQCRun.task_id == task_id)
        .order_by(QCTaskQCRun.run_number.desc())
        .limit(1)
    ).mappings().first()
    if previous is None:
        return 1
    job = workspace.get_batch_job(job_id=previous["job_id"], created_by=previous["triggered_by"])
    if job is None:
        raise TaskQCRunConflict("上次质控 job 不可读取，请先核对运行历史")
    if job.get("status") not in {"completed", "failed", "canceled", "cancelled"}:
        raise TaskQCRunConflict("任务已有运行中或状态未知的质控 job")
    return int(previous["run_number"]) + 1


def create_task_qc_run(
    *,
    task_id: str,
    actor_id: str,
    current_user: dict[str, Any],
    workspace_factory: Callable[[], Any],
    qc_service: Any,
    dispatch: Callable[[str], Any],
    run_scope: str = "all",
) -> dict[str, Any]:
    """任务行锁串行化重跑；job 和运行关联同一事务，提交后才派发。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    if not actor_id or len(actor_id) > 64:
        raise TaskQCRunForbidden("当前用户缺少有效身份")
    if run_scope not in {"all", "assigned"}:
        raise TaskQCRunConflict("运行范围无效")

    with SessionLocal() as session:
        with session.begin():
            task, refs = _task_and_refs(session, task_id, actor_id, run_scope)
            workspace = workspace_factory()
            run_number = _next_run_number(session, task_id, workspace)
            payload = SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key=task["rule_set_key"],
                scope=task["scene"],
                record_refs=refs,
            )
            prepared = prepare_workspace_batch_job(
                payload,
                current_user=current_user,
                qc_service=qc_service,
                workspace=workspace,
                task_run_context={"task_id": task_id, "run_number": str(run_number)},
            )
            filters = prepared.create_kwargs.get("filters")
            if (
                not isinstance(filters, dict)
                or filters.get("rule_set_key") != task["rule_set_key"]
                or filters.get("rule_set_version") != task["rule_set_version"]
            ):
                raise TaskQCRunConflict("准备后的规则集版本与任务冻结值不一致")
            job = workspace.create_batch_job(
                created_by=actor_id,
                session=session,
                **prepared.create_kwargs,
            )
            job_id = str(job.get("id") or "").strip()
            if not job_id:
                raise RuntimeError("workspace job 创建未返回有效 ID")
            session.add(QCTaskQCRun(
                task_id=task_id,
                run_number=run_number,
                job_id=job_id,
                triggered_by=actor_id,
                run_scope=run_scope,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ))
        # 事务已提交，worker 现在才能读到完整 job 与关联。
    try:
        dispatch(job_id)
    except Exception as exc:
        logger.exception("任务质控 job 派发失败: %s", job_id)
        try:
            workspace.fail_batch_job(job_id=job_id, error_message="后台派发失败，请重试任务质控")
        except Exception:
            logger.exception("无法标记派发失败的 job: %s", job_id)
        raise TaskQCRunDispatchError(job_id) from exc
    return {"task_id": task_id, "run_number": run_number, "job_id": job_id,
            "run_scope": run_scope, "status": "queued"}


def list_task_qc_runs(*, task_id: str, actor_id: str, run_scope: str = "all") -> list[dict[str, Any]]:
    """只返回请求范围内本人可见的 run；job 状态由 workspace 接口提供。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    if not actor_id or len(actor_id) > 64:
        raise TaskQCRunForbidden("当前用户缺少有效身份")
    if run_scope not in {"all", "assigned"}:
        raise TaskQCRunConflict("运行范围无效")
    with SessionLocal() as session:
        task = session.execute(
            select(QCTask.id, QCTask.creator_id).where(QCTask.id == task_id)
        ).mappings().first()
        if task is None:
            raise TaskQCRunNotFound("任务不存在")
        if run_scope == "all" and task["creator_id"] != actor_id:
            raise TaskQCRunForbidden("仅任务创建人可查看整批质控运行历史")
        if run_scope == "assigned":
            is_assignee = session.execute(
                select(QCTaskRecord.id).where(
                    QCTaskRecord.task_id == task_id,
                    QCTaskRecord.assignee_id == actor_id,
                ).limit(1)
            ).first() is not None
            has_history = session.execute(
                select(QCTaskQCRun.job_id).where(
                    QCTaskQCRun.task_id == task_id,
                    QCTaskQCRun.run_scope == "assigned",
                    QCTaskQCRun.triggered_by == actor_id,
                ).limit(1)
            ).first() is not None
            if not is_assignee and not has_history:
                raise TaskQCRunForbidden("当前用户未获分配此任务病历")
        statement = (
            select(QCTaskQCRun.__table__)
            .where(QCTaskQCRun.task_id == task_id, QCTaskQCRun.run_scope == run_scope)
            .order_by(QCTaskQCRun.run_number.desc())
        )
        if run_scope == "assigned":
            statement = statement.where(QCTaskQCRun.triggered_by == actor_id)
        rows = session.execute(statement).mappings().all()
        return [dict(row) for row in rows]


def get_task_qc_run_record_result(
    *, task_id: str, run_number: int, task_record_id: str, actor_id: str,
    workspace_factory: Callable[[], Any], run_scope: str = "all",
) -> dict[str, Any]:
    """只读取指定运行的权威结果，不改写任务病历状态。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    if not actor_id or len(actor_id) > 64:
        raise TaskQCRunForbidden("当前用户缺少有效身份")
    if run_scope not in {"all", "assigned"} or run_number <= 0:
        raise TaskQCRunConflict("运行范围或序号无效")

    with SessionLocal() as session:
        task = session.execute(
            select(QCTask.id, QCTask.creator_id, QCTask.rule_set_key, QCTask.scene)
            .where(QCTask.id == task_id)
        ).mappings().first()
        if task is None:
            raise TaskQCRunNotFound("任务不存在")
        record = session.execute(
            select(QCTaskRecord.__table__).where(
                QCTaskRecord.id == task_record_id, QCTaskRecord.task_id == task_id,
            )
        ).mappings().first()
        if record is None:
            raise TaskQCRunNotFound("任务病历不存在")
        run = session.execute(
            select(QCTaskQCRun.__table__).where(
                QCTaskQCRun.task_id == task_id,
                QCTaskQCRun.run_number == run_number,
            )
        ).mappings().first()
        if run is None:
            raise TaskQCRunNotFound("任务运行不存在")
        if run["run_scope"] != run_scope:
            raise TaskQCRunForbidden("当前范围不可查看此运行")
        if run_scope == "all":
            if task["creator_id"] != actor_id or run["triggered_by"] != actor_id:
                raise TaskQCRunForbidden("仅任务创建人可查看整批质控结果")
        elif run["triggered_by"] != actor_id or record["assignee_id"] != actor_id:
            raise TaskQCRunForbidden("仅运行人可查看当前受领的病历结果")
        identity = tuple(str(record.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id"))
        if any(not part or len(part) > 100 for part in identity) or record["record_id"] != record["id"]:
            raise TaskQCRunConflict("任务病历缺少完整三坐标")
        case_ref = CaseRef(*identity)
        rule_set_key = task["rule_set_key"]
        if rule_set_key not in {LUXIAN_0609_RULE_SET_KEY, LUXIAN_0916_RULE_SET_KEY}:
            raise TaskQCRunConflict("当前规则集尚不支持任务病历结果下钻")
        rule_set = get_sichuan_rule_set(rule_set_key)
        if rule_set is None or rule_set.scope != task["scene"]:
            raise TaskQCRunConflict("任务规则集已失效或与场景不匹配")
        job_id = str(run["job_id"] or "").strip()
        job_owner = str(run["triggered_by"] or "").strip()
        if not job_id or not job_owner:
            raise TaskQCRunConflict("任务运行缺少有效质控 job")

    workspace = workspace_factory()
    job = workspace.get_batch_job(job_id=job_id, created_by=job_owner)
    if job is None:
        raise TaskQCRunConflict("本次质控 job 不可读取")
    filters = job.get("filters") if isinstance(job.get("filters"), dict) else {}
    frozen_refs = filters.get("record_refs")
    valid_frozen_refs = (
        [CaseRef.from_mapping(ref) for ref in frozen_refs if isinstance(ref, dict)]
        if isinstance(frozen_refs, list) else []
    )
    if (
        str(job.get("id") or "") != job_id
        or str(job.get("created_by") or "") != job_owner
        or str(filters.get("task_id") or "") != task_id
        or str(filters.get("task_run_number") or "") != str(run_number)
        or str(filters.get("rule_set_key") or "") != rule_set_key
        or str(filters.get("query_scope") or "") != str(task["scene"] or "")
        or not valid_frozen_refs
        or len(valid_frozen_refs) != len(frozen_refs)
        or len(set(valid_frozen_refs)) != len(valid_frozen_refs)
        or any(
            not all(str(ref.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id"))
            for ref in frozen_refs
        )
        or case_ref not in valid_frozen_refs
    ):
        raise TaskQCRunConflict("任务运行与冻结质控范围不一致")

    result = {
        "task_id": task_id, "run_number": run_number, "task_record_id": task_record_id,
        "job_id": job_id, "job_status": str(job.get("status") or ""),
        "result_state": "pending", "rule_set_key": rule_set_key,
        "items": [],
    }
    status = result["job_status"]
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    partial = status == "failed" and summary.get("execution_status") == "partial_failed"
    if status in {"queued", "pending", "running", "processing"}:
        return result
    if status in {"canceled", "cancelled"} or (status == "failed" and not partial):
        result["result_state"] = "unavailable"
        return result
    if status != "completed" and not partial:
        raise TaskQCRunConflict("质控 job 状态未知")

    if rule_set_key == LUXIAN_0916_RULE_SET_KEY:
        return _luxian_0916_record_result(
            result=result, job=job, filters=filters, case_ref=case_ref,
            frozen_refs=frozen_refs, partial=partial,
        )

    try:
        canonical_items = workspace._load_batch_job_canonical_items(job=job, allow_partial=partial)
        hmac_key = customer_safe_projection_key()
        target_ref = keyed_ref("rec", case_ref.as_key(), hmac_key=hmac_key)
        raw_target_items = [
            item for item in canonical_items
            if isinstance(item, dict) and item.get("record_ref") == target_ref
        ]
        if raw_target_items:
            scoped_rule_ids = filters.get("scoped_customer_rule_ids") or filters.get("rule_ids") or []
            expected_rule_ids = {
                str(rule_id).strip().upper()
                for key_group in (
                    scoped_rule_ids,
                    filters.get("gate_only_customer_rule_ids") or [],
                    filters.get("paused_customer_rule_ids") or [],
                )
                if isinstance(key_group, list)
                for rule_id in key_group
                if str(rule_id).strip()
            }
            delivered_rule_ids = [
                str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
                for item in raw_target_items
            ]
            if (
                not expected_rule_ids
                or any(not rule_id for rule_id in delivered_rule_ids)
                or len(set(delivered_rule_ids)) != len(delivered_rule_ids)
                or set(delivered_rule_ids) != expected_rule_ids
            ):
                raise ValueError("Canonical Envelope 规则集合不完整")
        target_items = [project_customer_safe_result_item(item, hmac_key=hmac_key) for item in raw_target_items]
    except ValueError as exc:
        raise TaskQCRunConflict("本次质控 Canonical 结果不完整，无法安全展示") from exc
    if not target_items:
        if not partial:
            raise TaskQCRunConflict("本次质控 Canonical 结果缺少目标病历")
        result["result_state"] = "unavailable"
        return result
    result["result_state"] = "available"
    result["items"] = target_items
    return result


def _luxian_0916_record_result(
    *, result: dict[str, Any], job: dict[str, Any], filters: dict[str, Any],
    case_ref: CaseRef, frozen_refs: list[dict[str, Any]], partial: bool,
) -> dict[str, Any]:
    planned_rules = filters.get("rule_ids")
    if (
        not isinstance(planned_rules, list)
        or len(planned_rules) != len(LUXIAN_0916_RULE_IDS)
        or any(not isinstance(rule_id, str) for rule_id in planned_rules)
        or set(planned_rules) != set(LUXIAN_0916_RULE_IDS)
    ):
        raise TaskQCRunConflict("本次质控冻结规则与 LX0916 目录不一致")
    items = job.get("items")
    failures = job.get("failed_records")
    summary = job.get("summary")
    if (
        not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
        or not isinstance(failures, list)
        or any(not isinstance(failure, dict) for failure in failures)
        or not isinstance(summary, dict)
        or summary.get("execution_status") != ("partial_failed" if partial else "completed")
    ):
        raise TaskQCRunConflict("本次质控 LX0916 结果不完整，无法安全展示")
    try:
        validate_luxian_0916_task_delivery(
            summary=summary, items=items, failures=failures,
            expected_rule_ids=LUXIAN_0916_RULE_IDS,
            expected_record_refs=frozen_refs,
        )
    except (TypeError, ValueError) as exc:
        raise TaskQCRunConflict("本次质控 LX0916 结果不完整，无法安全展示") from exc

    identity = tuple(case_ref)
    if any(
        tuple(str(failure.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id")) == identity
        for failure in failures
    ):
        result["result_state"] = "unavailable"
        return result
    target_items = [
        item for item in items
        if tuple(str(item.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id")) == identity
    ]
    if len(target_items) != len(LUXIAN_0916_RULE_IDS):
        raise TaskQCRunConflict("本次质控 LX0916 结果缺少目标病历")
    if any(
        item.get("rule_id") not in LUXIAN_0916_RULE_IDS
        or not isinstance(item.get("evidence"), list)
        for item in target_items
    ):
        raise TaskQCRunConflict("本次质控 LX0916 结果不符合展示合同")
    result["result_state"] = "available"
    result["items"] = [
        {
            "rule_id": item["rule_id"],
            "rule_name": get_luxian_0916_rule_definition(item["rule_id"]).name,
            "status": item["status"],
            "reason_code": item["reason_code"],
            "findings": item["findings"],
            "evidence": list(item.get("evidence") or []),
            "suggestion": item.get("suggestion") or "",
        }
        for item in target_items
    ]
    return result
