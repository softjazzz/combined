"""单任务只读分析；任务病历状态是唯一完成事实来源。"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskRecord

_KNOWN_STATUSES = ("pending", "in_progress", "completed", "skipped")


class TaskAnalysisInvalid(ValueError):
    """请求身份或任务标识无效。"""


class TaskAnalysisNotFound(LookupError):
    """任务不存在。"""


class TaskAnalysisForbidden(PermissionError):
    """当前账号无权读取该任务的整任务分析。"""


class TaskAnalysisUnavailable(RuntimeError):
    """分析数据源不可用。"""


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _rate(completed: int, total: int) -> float:
    return round(100.0 * completed / total, 2) if total else 0.0


def get_task_analysis(
    *,
    task_id: str,
    actor_id: str,
    is_manager: bool,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """先验证整任务对象权限，再按 ``qc_task_records`` 做无分页精确聚合。"""
    normalized_task_id = _text(task_id)
    normalized_actor_id = _text(actor_id)
    if normalized_task_id is None or len(normalized_task_id) > 100:
        raise TaskAnalysisInvalid("任务标识无效")
    if normalized_actor_id is None or len(normalized_actor_id) > 64:
        raise TaskAnalysisInvalid("当前用户缺少有效身份")

    factory = session_factory or SessionLocal
    if factory is None:
        raise TaskAnalysisUnavailable("数据库会话不可用")

    with factory() as session:
        task = session.execute(
            select(
                QCTask.id,
                QCTask.task_number,
                QCTask.task_name,
                QCTask.scene,
                QCTask.status,
                QCTask.creator_id,
                QCTask.creator_name,
            ).where(QCTask.id == normalized_task_id)
        ).mappings().first()
        if task is None:
            raise TaskAnalysisNotFound("任务不存在")
        if not is_manager and task["creator_id"] != normalized_actor_id:
            raise TaskAnalysisForbidden("仅任务创建人或管理员可查看整任务分析")

        # 一次只读必要列形成同一批聚合输入；不经过 PostgREST 分页，也不加载病例正文。
        record_rows = session.execute(
            select(
                QCTaskRecord.id,
                QCTaskRecord.assignee_id,
                QCTaskRecord.assignee_name,
                QCTaskRecord.status,
                QCTaskRecord.score,
                QCTaskRecord.defect_count,
            ).where(QCTaskRecord.task_id == normalized_task_id)
        ).mappings().all()

    total = len(record_rows)
    completed = sum(row["status"] == "completed" for row in record_rows)
    scores = [
        float(row["score"])
        for row in record_rows
        if isinstance(row["score"], (int, float))
        and not isinstance(row["score"], bool)
        and math.isfinite(float(row["score"]))
        and float(row["score"]) >= 0
    ]
    defects = [
        row["defect_count"]
        for row in record_rows
        if type(row["defect_count"]) is int and row["defect_count"] >= 0
    ]
    score_known = len(scores)
    defect_known = len(defects)

    status_counts = {status: 0 for status in _KNOWN_STATUSES}
    status_counts["unknown"] = 0
    for row in record_rows:
        key = row["status"] if row["status"] in _KNOWN_STATUSES else "unknown"
        status_counts[key] += 1

    assignees: dict[str | None, dict[str, Any]] = {}
    for row in record_rows:
        assignee_id = _text(row["assignee_id"])
        key = assignee_id
        item = assignees.setdefault(
            key,
            {
                "assignee_id": assignee_id,
                "assignee_name": _text(row["assignee_name"]),
                "total_records": 0,
                "completed_records": 0,
            },
        )
        item["total_records"] += 1
        if row["status"] == "completed":
            item["completed_records"] += 1
        # 同一账号出现冲突快照时不猜测名称，保留为未知。
        row_name = _text(row["assignee_name"])
        if item["assignee_name"] != row_name:
            item["assignee_name"] = None

    assignee_items = list(assignees.values())
    for item in assignee_items:
        item["completion_rate"] = _rate(item["completed_records"], item["total_records"])
    assignee_items.sort(
        key=lambda item: (
            -item["total_records"],
            item["assignee_name"] or "",
            item["assignee_id"] or "",
        )
    )

    # 只要存在未知项，全任务指标保持未知；已知/未知样本数仍供界面解释。
    average_score = round(sum(scores) / total, 2) if total > 0 and score_known == total else None
    total_defects = sum(defects) if total > 0 and defect_known == total else None
    return {
        "contract_version": "task-analysis-v1",
        "task": {
            "id": task["id"],
            "task_number": task["task_number"],
            "task_name": task["task_name"],
            "scene": task["scene"],
            "status": task["status"],
            "creator_id": task["creator_id"],
            "creator_name": task["creator_name"],
        },
        "summary": {
            "total_records": total,
            "completed_records": completed,
            "completion_rate": _rate(completed, total),
            "average_score": average_score,
            "score_known_count": score_known,
            "score_unknown_count": total - score_known,
            "total_defect_count": total_defects,
            "defect_known_count": defect_known,
            "defect_unknown_count": total - defect_known,
        },
        "status_counts": status_counts,
        "assignees": assignee_items,
    }
