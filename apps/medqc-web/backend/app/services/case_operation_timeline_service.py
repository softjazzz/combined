"""病历级操作记录时间线（V3.6 合同 docs/plans/2026-09-27-v36-case-operation-timeline-design.md）。

本服务只做装配和排序：每类事件的事实仍由原 owner 负责，这里不重新判定任何状态。
- qc_run_completed：Envelope（结果对象）+ 批量 job（操作人、任务上下文）
- record_review：qc_record_reviews 病历初审/复审决定
- manual_defect_created / manual_defect_reviewed：人工缺陷谓词下的 qc_defect_history
- task_record_completed：qc_task_records 的完成时间（由任务病历完成服务写入）；
  started_at 目前无任何写入方，不作为事件来源
所有来源都按 institute_id/patient_id/visit_id 三坐标精确匹配；任一来源读取失败，
整个时间线视为不可用，不返回“只缺一部分”的结果。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, column, select, table
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory, QCRecordReview, SysUser
from .manual_defect_review_service import _manual_scope, _task_identity

DEFAULT_LIMIT = 100
MAX_LIMIT = 200
MAX_IDENTITY_LENGTH = 128

_CREATE_ACTION = "manual_create"
# 人工缺陷审核历史动作 → 审核结论；与 manual_defect_review_service 写入的动作一致。
_REVIEW_ACTIONS = {
    "manual_review_approved": "approved",
    "manual_review_rejected": "rejected",
}

# 只声明本服务读取的列；completed_at 由 task_record_completion_service 写入。
_TASK_RECORDS = table(
    "qc_task_records",
    column("id", String),
    column("task_id", String),
    column("institute_id", String),
    column("patient_id", String),
    column("visit_id", String),
    column("assignee_id", String),
    column("completed_run_number", Integer),
    column("completed_at", DateTime),
)


class CaseOperationTimelineInvalid(ValueError):
    """请求参数不符合合同（三坐标或 limit 非法）。"""


class CaseOperationTimelineUnavailable(RuntimeError):
    """数据库不可用或任一来源读取失败；对外只给脱敏提示。"""


def _envelope_table() -> Any:
    """Envelope 表对象；单独封装便于测试替换为无 schema 的同构表。"""
    from .custom_qc_workspace_service import _record_result_envelopes_table

    return _record_result_envelopes_table()


def _batch_jobs_table() -> Any:
    """批量 job 表对象；单独封装便于测试替换为无 schema 的同构表。"""
    from .custom_qc_workspace_service import _batch_jobs_table as workspace_batch_jobs_table

    return workspace_batch_jobs_table()


def _case_identity(institute_id: Any, patient_id: Any, visit_id: Any) -> tuple[str, str, str]:
    values = (institute_id, patient_id, visit_id)
    if any(
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > MAX_IDENTITY_LENGTH
        for value in values
    ):
        raise CaseOperationTimelineInvalid("病例三坐标无效")
    return (institute_id, patient_id, visit_id)


def _json_object(raw: Any) -> dict[str, Any] | None:
    """解析 JSON 文本为对象；失败返回 None，不影响事件本身。"""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _task_context(filters_json: Any) -> dict[str, Any]:
    """从 job filters 中取任务上下文；两项都合法才附带，否则返回空字典。"""
    filters = _json_object(filters_json)
    if filters is None:
        return {}
    task_id = filters.get("task_id")
    run_number = filters.get("task_run_number")
    if not isinstance(task_id, str) or not task_id.strip():
        return {}
    if type(run_number) is int:
        normalized = run_number
    elif isinstance(run_number, str) and run_number.isascii() and run_number.isdecimal():
        normalized = int(run_number)
    else:
        return {}
    if normalized <= 0:
        return {}
    return {"task_id": task_id.strip(), "task_run_number": normalized}


def _event(
    event_id: str, event_type: str, occurred_at: Any, actor_id: Any, summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": event_type,
        "occurred_at": occurred_at,
        "actor_id": actor_id if isinstance(actor_id, str) and actor_id else None,
        "actor_name": None,
        "summary": summary,
    }


def _sort_key(event: dict[str, Any]) -> tuple[datetime, str]:
    # 库内时间统一为无时区 UTC；如遇带时区值先换算，避免混合比较报错。
    occurred_at: datetime = event["occurred_at"]
    if occurred_at.tzinfo is not None:
        occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
    return (occurred_at, event["id"])


def _run_events(session: Any, identity: tuple[str, str, str]) -> list[dict[str, Any]]:
    envelopes = _envelope_table()
    rows = session.execute(
        select(
            envelopes.c.id, envelopes.c.root_job_id, envelopes.c.rule_set_version,
            envelopes.c.result_count, envelopes.c.updated_at,
        ).where(
            envelopes.c.institute_id == identity[0],
            envelopes.c.patient_id == identity[1],
            envelopes.c.visit_id == identity[2],
        )
    ).all()
    jobs_by_id: dict[str, Any] = {}
    job_ids = sorted({str(row.root_job_id) for row in rows if row.root_job_id})
    if job_ids:
        jobs = _batch_jobs_table()
        for job in session.execute(
            select(jobs.c.id, jobs.c.created_by, jobs.c.filters_json).where(jobs.c.id.in_(job_ids))
        ).all():
            jobs_by_id[str(job.id)] = job
    events = []
    for row in rows:
        job = jobs_by_id.get(str(row.root_job_id))
        summary: dict[str, Any] = {
            "job_id": row.root_job_id,
            "rule_set_version": row.rule_set_version,
            "result_count": row.result_count,
        }
        if job is not None:
            summary.update(_task_context(job.filters_json))
        events.append(_event(
            f"envelope:{row.id}", "qc_run_completed", row.updated_at,
            job.created_by if job is not None else None, summary,
        ))
    return events


def _review_events(session: Any, identity: tuple[str, str, str]) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            QCRecordReview.id, QCRecordReview.review_context, QCRecordReview.stage,
            QCRecordReview.decision, QCRecordReview.reason, QCRecordReview.job_id,
            QCRecordReview.task_id, QCRecordReview.reviewer_id, QCRecordReview.created_at,
        ).where(
            QCRecordReview.institute_id == identity[0],
            QCRecordReview.patient_id == identity[1],
            QCRecordReview.visit_id == identity[2],
        )
    ).all()
    return [
        _event(f"review:{row.id}", "record_review", row.created_at, row.reviewer_id, {
            "review_context": row.review_context,
            "stage": row.stage,
            "decision": row.decision,
            "reason": row.reason,
            "job_id": row.job_id,
            "task_id": row.task_id,
        })
        for row in rows
    ]


def _manual_defect_events(session: Any, identity: tuple[str, str, str]) -> list[dict[str, Any]]:
    # 只取人工缺陷谓词下的历史；自动缺陷历史不进入时间线（旧入口身份未核实）。
    rows = session.execute(
        select(
            QCDefectHistory.id, QCDefectHistory.defect_id, QCDefectHistory.action,
            QCDefectHistory.actor_id, QCDefectHistory.details, QCDefectHistory.created_at,
            QCDefect.rule_name, QCDefect.manual_created_by,
        ).join(QCDefect, QCDefect.id == QCDefectHistory.defect_id).where(
            *_manual_scope(),
            QCDefect.institute_id == identity[0],
            QCDefect.patient_id == identity[1],
            QCDefect.visit_id == identity[2],
            QCDefectHistory.action.in_((_CREATE_ACTION, *_REVIEW_ACTIONS)),
        )
    ).all()
    creates_by_defect: dict[str, list[Any]] = {}
    for row in rows:
        if row.action == _CREATE_ACTION:
            creates_by_defect.setdefault(row.defect_id, []).append(row)
    events = []
    for row in rows:
        if row.action == _CREATE_ACTION:
            # 任务坐标沿用审核列表同一解析规则：唯一 manual_create 且操作人为创建人才可信。
            task = _task_identity(creates_by_defect[row.defect_id], row.manual_created_by)
            events.append(_event(
                f"defect_history:{row.id}", "manual_defect_created", row.created_at, row.actor_id, {
                    "defect_id": row.defect_id,
                    "rule_name": row.rule_name,
                    "task_id": task["task_id"],
                    "run_number": task["run_number"],
                },
            ))
            continue
        details = _json_object(row.details) or {}
        reason = details.get("reason")
        summary: dict[str, Any] = {"defect_id": row.defect_id}
        # 结论以历史 action 为准；details.to_status 仅作交叉校验，存在且不一致时省略结论以免误报。
        decision = _REVIEW_ACTIONS[row.action]
        to_status = details.get("to_status")
        if to_status is None or to_status == decision:
            summary["decision"] = decision
        summary["reason"] = reason if isinstance(reason, str) else None
        events.append(_event(
            f"defect_history:{row.id}", "manual_defect_reviewed", row.created_at, row.actor_id,
            summary,
        ))
    return events


def _task_record_events(session: Any, identity: tuple[str, str, str]) -> list[dict[str, Any]]:
    records = _TASK_RECORDS
    rows = session.execute(
        select(
            records.c.id, records.c.task_id, records.c.assignee_id,
            records.c.completed_run_number, records.c.completed_at,
        ).where(
            records.c.institute_id == identity[0],
            records.c.patient_id == identity[1],
            records.c.visit_id == identity[2],
            records.c.completed_at.is_not(None),
        )
    ).all()
    events = []
    for row in rows:
        if row.completed_at is not None:
            events.append(_event(
                f"task_record:{row.id}:completed", "task_record_completed", row.completed_at,
                row.assignee_id, {
                    "task_id": row.task_id,
                    "task_record_id": row.id,
                    "completed_run_number": row.completed_run_number,
                },
            ))
    return events


def _display_names(session: Any, actor_ids: set[str]) -> dict[str, str]:
    if not actor_ids:
        return {}
    rows = session.execute(
        select(SysUser.id, SysUser.display_name).where(SysUser.id.in_(sorted(actor_ids)))
    ).all()
    return {str(row.id): row.display_name for row in rows if row.display_name}


def list_case_operations(
    *, institute_id: str, patient_id: str, visit_id: str, limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """按三坐标装配病历操作记录：倒序（同时间按 id）排序后截断，total 为合并后的精确总数。"""
    identity = _case_identity(institute_id, patient_id, visit_id)
    if type(limit) is not int or limit < 1 or limit > MAX_LIMIT:
        raise CaseOperationTimelineInvalid("limit 无效")
    if SessionLocal is None:
        raise CaseOperationTimelineUnavailable("数据库会话不可用")
    try:
        with SessionLocal() as session:
            events = [
                *_run_events(session, identity),
                *_review_events(session, identity),
                *_manual_defect_events(session, identity),
                *_task_record_events(session, identity),
            ]
            events = [event for event in events if isinstance(event["occurred_at"], datetime)]
            events.sort(key=_sort_key, reverse=True)
            items = events[:limit]
            names = _display_names(session, {e["actor_id"] for e in items if e["actor_id"]})
    except (SQLAlchemyError, RuntimeError) as exc:
        # RuntimeError 覆盖 job 表在未配置数据库时的懒加载失败；任一来源失败即整体不可用。
        raise CaseOperationTimelineUnavailable("病例操作记录读取失败") from exc
    for event in items:
        event["actor_name"] = names.get(event["actor_id"]) if event["actor_id"] else None
    return {
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "items": items,
        "total": len(events),
        "limit": limit,
    }
