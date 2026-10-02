"""任务列表只读补充字段；运行状态搬运 job owner，不构造有隐式 DDL 的 workspace。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Column, MetaData, String, Table, Text, select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import DB_SCHEMA_MODE, SessionLocal
from ..database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from .record_review_service import task_approved_counts


def _job_status_table() -> Table:
    # 仅声明既有表的必要列，不 create_all、反射或补列。
    return Table(
        "custom_qc_batch_jobs", MetaData(),
        Column("id", String), Column("created_by", String),
        Column("status", String), Column("filters_json", Text),
        schema="qc" if DB_SCHEMA_MODE == "split" else None,
    )


def unknown_summary() -> dict[str, Any]:
    return {"assigned_to_me": None, "qc_assignees": None, "approved_records": None,
            "actual_completed_at": None, "qc_run_statuses": None}


def get_task_list_summaries(
    *, task_ids: list[str], actor_id: str, tab: str, is_manager: bool,
) -> dict[str, dict[str, Any]]:
    """仅补创建/管理分页任务，独立复核权限范围；受领列表保持旧合同。"""
    summaries = {task_id: unknown_summary() for task_id in task_ids}
    if not task_ids or not actor_id or SessionLocal is None or tab not in {"created", "all"}:
        return summaries
    if tab == "all" and not is_manager:
        return summaries
    try:
        with SessionLocal() as session:
            query = select(QCTask.__table__).where(QCTask.id.in_(task_ids))
            if tab == "created":
                query = query.where(QCTask.creator_id == actor_id)
            tasks = session.execute(query).mappings().all()
            ids = [task["id"] for task in tasks]
            if not ids:
                return summaries
            records = session.execute(select(QCTaskRecord.__table__).where(
                QCTaskRecord.task_id.in_(ids),
            )).mappings().all()
            by_task: dict[str, list[Any]] = {task_id: [] for task_id in ids}
            for record in records:
                by_task[record["task_id"]].append(record)
            for task in tasks:
                rows = by_task[task["id"]]
                assignees: dict[str, str | None] = {}
                for row in rows:
                    if row["assignee_id"]:
                        actor = row["assignee_id"]
                        name = row["assignee_name"] or None
                        if actor in assignees and assignees[actor] != name:
                            assignees[actor] = None
                        else:
                            assignees[actor] = name
                finished = None
                if task["status"] == "completed" and rows and all(
                    row["status"] == "completed" and row["completed_at"] is not None for row in rows
                ):
                    finished = max(row["completed_at"] for row in rows).isoformat() + "Z"
                summaries[task["id"]].update(
                    assigned_to_me=sum(row["assignee_id"] == actor_id for row in rows),
                    qc_assignees=[{"id": key, "name": value} for key, value in sorted(assignees.items())],
                    actual_completed_at=finished,
                )
            try:
                approved = task_approved_counts(session, tasks, records)
                for task_id, count in approved.items():
                    summaries[task_id]["approved_records"] = count
            except SQLAlchemyError:
                session.rollback()
            # 每个运行范围/owner 只搬最新一条持久运行，job id 去重。
            runs = session.execute(select(QCTaskQCRun.__table__).where(
                QCTaskQCRun.task_id.in_(ids),
            ).order_by(QCTaskQCRun.run_number.desc())).mappings().all()
            latest: dict[tuple[str, str, str], Any] = {}
            for run in runs:
                latest.setdefault((run["task_id"], run["run_scope"], run["triggered_by"]), run)
            selected = list(latest.values())
            table = _job_status_table()
            jobs = session.execute(select(table).where(table.c.id.in_({run["job_id"] for run in selected}))).mappings().all() if selected else []
            job_map = {job["id"]: job for job in jobs}
            for task in tasks:
                states = []
                seen_jobs: set[str] = set()
                valid = True
                for run in selected:
                    if run["task_id"] != task["id"] or run["job_id"] in seen_jobs:
                        continue
                    seen_jobs.add(run["job_id"])
                    job = job_map.get(run["job_id"])
                    try:
                        filters = json.loads(job["filters_json"]) if job else None
                    except (TypeError, ValueError):
                        filters = None
                    if (job is None or job["created_by"] != run["triggered_by"] or not isinstance(filters, dict)
                        or filters.get("task_id") != task["id"]
                        or str(filters.get("task_run_number")) != str(run["run_number"])
                        or filters.get("rule_set_key") != task["rule_set_key"]
                        or filters.get("rule_set_version") != task["rule_set_version"]
                        or filters.get("query_scope") != task["scene"]
                        or job["status"] not in {"queued", "running", "completed", "failed", "canceled"}):
                        valid = False
                        break
                    states.append(job["status"])
                summaries[task["id"]]["qc_run_statuses"] = states if valid else None
    except SQLAlchemyError:
        # 不把数据库读取失败解释为零、未执行或已完成。
        return summaries
    return summaries
