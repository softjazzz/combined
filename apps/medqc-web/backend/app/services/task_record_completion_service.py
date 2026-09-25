"""受领质控员显式完成任务病历；不改变病历审核或复审状态。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func, select, update

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from .task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    get_task_qc_run_record_result,
)


class TaskRecordCompletionNotFound(LookupError):
    pass


class TaskRecordCompletionForbidden(PermissionError):
    pass


class TaskRecordCompletionConflict(ValueError):
    pass


class TaskRecordCompletionUnavailable(RuntimeError):
    pass


def _verified_result(
    *, task_id: str, task_record_id: str, actor_id: str,
    run_number: int, workspace_factory: Callable[[], Any],
) -> str:
    try:
        result = get_task_qc_run_record_result(
            task_id=task_id, task_record_id=task_record_id,
            actor_id=actor_id, run_number=run_number,
            workspace_factory=workspace_factory, run_scope="assigned",
        )
    except TaskQCRunNotFound as exc:
        raise TaskRecordCompletionNotFound(str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise TaskRecordCompletionForbidden(str(exc)) from exc
    except TaskQCRunConflict as exc:
        raise TaskRecordCompletionConflict(str(exc)) from exc
    if not isinstance(result, dict) or result.get("result_state") != "available":
        raise TaskRecordCompletionConflict("本次质控结果尚不可用于完成病历")
    if (
        result.get("task_id") != task_id
        or result.get("task_record_id") != task_record_id
        or type(result.get("run_number")) is not int
        or result["run_number"] != run_number
        or not isinstance(result.get("items"), list)
        or not result["items"]
    ):
        raise TaskRecordCompletionConflict("任务病历质控结果身份不一致或缺少明细")
    job_id = result.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise TaskRecordCompletionConflict("任务病历质控结果缺少运行身份")
    return job_id


def complete_assigned_task_record(
    *, task_id: str, task_record_id: str, actor_id: str,
    run_number: int, workspace_factory: Callable[[], Any],
) -> dict[str, Any]:
    """先核实交付结果，再原子提交质控员的病历级完成动作。"""
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 64:
        raise TaskRecordCompletionForbidden("当前用户缺少有效身份")
    if type(run_number) is not int or run_number <= 0:
        raise TaskRecordCompletionConflict("运行序号无效")
    if SessionLocal is None:
        raise TaskRecordCompletionUnavailable("数据库会话不可用")

    # 已提交的同一运行允许幂等重试，不要求历史 workspace job 永久可读。
    with SessionLocal() as session:
        previously_completed = session.execute(
            select(QCTaskRecord.status, QCTaskRecord.completed_run_number).where(
                QCTaskRecord.id == task_record_id,
                QCTaskRecord.task_id == task_id,
            )
        ).first()
    replay_candidate = previously_completed is not None and (
        previously_completed.status == "completed"
        and previously_completed.completed_run_number == run_number
    )
    job_id = None if replay_candidate else _verified_result(
        task_id=task_id, task_record_id=task_record_id,
        actor_id=actor_id, run_number=run_number,
        workspace_factory=workspace_factory,
    )

    with SessionLocal() as session:
        with session.begin():
            task = session.execute(
                select(QCTask.__table__).where(QCTask.id == task_id).with_for_update()
            ).mappings().first()
            if task is None:
                raise TaskRecordCompletionNotFound("任务不存在")
            record = session.execute(
                select(QCTaskRecord.__table__).where(
                    QCTaskRecord.id == task_record_id,
                    QCTaskRecord.task_id == task_id,
                ).with_for_update()
            ).mappings().first()
            if record is None:
                raise TaskRecordCompletionNotFound("任务病历不存在")
            if record["assignee_id"] != actor_id:
                raise TaskRecordCompletionForbidden("当前用户未受领该病历")

            identity = tuple(record.get(key) for key in ("institute_id", "patient_id", "visit_id"))
            if (
                any(not isinstance(part, str) or not part.strip() or len(part) > 100 for part in identity)
                or record["record_id"] != record["id"]
            ):
                raise TaskRecordCompletionConflict("任务病历缺少完整三坐标")
            run = session.execute(
                select(QCTaskQCRun.__table__).where(
                    QCTaskQCRun.task_id == task_id,
                    QCTaskQCRun.run_number == run_number,
                ).with_for_update()
            ).mappings().first()
            if run is None:
                raise TaskRecordCompletionNotFound("任务运行不存在")
            if run["run_scope"] != "assigned" or run["triggered_by"] != actor_id:
                raise TaskRecordCompletionForbidden("仅受领运行人可完成此病历")
            if (
                not isinstance(run["job_id"], str)
                or not run["job_id"].strip()
                or (job_id is not None and run["job_id"] != job_id)
            ):
                raise TaskRecordCompletionConflict("任务运行身份或分配已变化")

            total_actual, completed_before = session.execute(
                select(
                    func.count(QCTaskRecord.id),
                    func.count(QCTaskRecord.id).filter(QCTaskRecord.status == "completed"),
                ).where(QCTaskRecord.task_id == task_id)
            ).one()
            total = task["total_records"]
            if type(total) is not int or total <= 0 or total_actual != total:
                raise TaskRecordCompletionConflict("任务抽样关联与数量不一致")
            if record["status"] == "completed":
                if record["completed_run_number"] != run_number:
                    raise TaskRecordCompletionConflict("病历已由其他运行完成")
                if task["status"] not in {"in_progress", "completed"}:
                    raise TaskRecordCompletionConflict("任务当前状态不允许完成病历")
                expected_progress = 100.0 * completed_before / total
                if (
                    task["status"] != ("completed" if completed_before == total else "in_progress")
                    or task["completed_records"] != completed_before
                    or task["progress"] is None
                    or abs(float(task["progress"]) - expected_progress) > 0.000001
                    or record["completed_at"] is None
                    or record["score"] is not None
                    or record["defect_count"] is not None
                ):
                    raise TaskRecordCompletionConflict("任务完成状态或进度与病历关联不一致")
                idempotent = True
            elif job_id is not None and record["status"] == "in_progress" and task["status"] == "in_progress":
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                changed = session.execute(
                    update(QCTaskRecord)
                    .where(
                        QCTaskRecord.id == task_record_id,
                        QCTaskRecord.task_id == task_id,
                        QCTaskRecord.assignee_id == actor_id,
                        QCTaskRecord.status == "in_progress",
                    )
                    .values(
                        status="completed", completed_at=now,
                        completed_run_number=run_number,
                        score=None, defect_count=None,
                    )
                )
                if changed.rowcount != 1:
                    raise TaskRecordCompletionConflict("病历状态已变化，请刷新后重试")
                idempotent = False
            else:
                raise TaskRecordCompletionConflict("任务或病历当前状态不允许完成")

            completed = completed_before if idempotent else completed_before + 1
            progress = 100.0 * completed / total
            status = "completed" if completed == total else "in_progress"
            if not idempotent:
                changed_task = session.execute(
                    update(QCTask)
                    .where(QCTask.id == task_id, QCTask.status == "in_progress")
                    .values(
                        completed_records=completed, progress=progress,
                        status=status, updated_at=now,
                    )
                )
                if changed_task.rowcount != 1:
                    raise TaskRecordCompletionConflict("任务状态已变化，请刷新后重试")
            return {
                "task_id": task_id,
                "task_record_id": task_record_id,
                "status": "completed",
                "run_number": run_number,
                "idempotent": idempotent,
                "score": None,
                "defect_count": None,
                "completed_records": completed,
                "total_records": total,
                "progress": progress,
            }
