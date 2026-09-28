"""全部任务列表的只读 CSV 导出。"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask

MAX_EXPORT_ROWS = 5_000

_HEADERS = (
    ("task_number", "任务编号"),
    ("task_name", "任务名称"),
    ("scene", "场景"),
    ("task_type", "任务类型"),
    ("status", "状态"),
    ("progress", "进度（%）"),
    ("total_records", "总病历"),
    ("completed_records", "已完成"),
    ("creator_name", "创建人"),
    ("created_at", "创建时间"),
    ("deadline", "截止时间"),
    ("rule_set_key", "规则集"),
    ("rule_set_version", "规则版本"),
    ("sampling_method", "抽样方式"),
    ("assign_method", "分配方式"),
)

_SCENE_LABELS = {
    "running": "运行",
    "final": "终末",
    "outpatient": "门急诊",
}
_TASK_TYPE_LABELS = {"one_time": "单次任务", "scheduled": "定时任务"}
_STATUS_LABELS = {
    "draft": "草稿",
    "sampling": "抽样中",
    "assigned": "已分配",
    "in_progress": "进行中",
    "completed": "已完成",
    "cancelled": "已取消",
}
_SAMPLING_LABELS = {"all": "全部", "count": "按数量", "percentage": "按比例"}
_ASSIGN_LABELS = {
    "keep": "保留原分配",
    "by_department": "按科室",
    "by_ratio": "按比例",
    "by_type": "按病历类型",
    "by_original_reviewer": "原质控员",
}
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class TaskExportInvalid(ValueError):
    """筛选参数不符合任务列表合同。"""


class TaskExportTooLarge(RuntimeError):
    """匹配任务超过同步导出的固定上限。"""

    def __init__(self, matched_at_least: int, limit: int = MAX_EXPORT_ROWS) -> None:
        super().__init__(f"匹配任务超过 {limit} 条，请缩小筛选范围")
        self.matched_at_least = matched_at_least
        self.limit = limit


class TaskExportUnavailable(RuntimeError):
    """任务数据源不可用。"""


@dataclass(frozen=True)
class TaskExportResult:
    content: bytes
    row_count: int


def _filter_value(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TaskExportInvalid(f"{field} 无效")
    if value == "":
        return None
    return value


def _csv_safe(value: Any) -> str | int | float:
    if value is None or value == "":
        return "未知"
    if isinstance(value, (datetime, date)):
        text = value.isoformat()
    elif isinstance(value, bool):
        text = "是" if value else "否"
    elif isinstance(value, (int, float)):
        return value
    else:
        text = str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _display_value(key: str, value: Any) -> Any:
    if key == "scene":
        return _SCENE_LABELS.get(value, value)
    if key == "task_type":
        return _TASK_TYPE_LABELS.get(value, value)
    if key == "status":
        return _STATUS_LABELS.get(value, value)
    if key == "sampling_method":
        return _SAMPLING_LABELS.get(value, value)
    if key == "assign_method":
        return _ASSIGN_LABELS.get(value, value)
    return value


def render_task_export_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    """按固定白名单渲染 CSV；自由文本统一防电子表格公式注入。"""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=[label for _, label in _HEADERS])
    writer.writeheader()
    for row in rows:
        writer.writerow({
            label: _csv_safe(_display_value(key, row.get(key)))
            for key, label in _HEADERS
        })
    return stream.getvalue().encode("utf-8-sig")


def export_all_tasks(
    *,
    scene: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    session_factory: Callable[[], Any] | None = None,
) -> TaskExportResult:
    """一次只读 SQL 快照取得全部匹配行；多一行仅用于显式上限判断。"""
    normalized_scene = _filter_value(scene, field="scene")
    normalized_status = _filter_value(status, field="status")
    normalized_keyword = _filter_value(keyword, field="keyword")
    if normalized_scene not in {None, "running", "final", "outpatient", "unclassified"}:
        raise TaskExportInvalid("无效的任务场景")
    factory = session_factory or SessionLocal
    if factory is None:
        raise TaskExportUnavailable("数据库会话不可用")

    columns = [getattr(QCTask, key) for key, _label in _HEADERS]
    query = select(QCTask.id, *columns)
    if normalized_scene == "unclassified":
        query = query.where(QCTask.scene.is_(None))
    elif normalized_scene is not None:
        query = query.where(QCTask.scene == normalized_scene)
    if normalized_status is not None:
        query = query.where(QCTask.status == normalized_status)
    if normalized_keyword is not None:
        pattern = f"%{normalized_keyword}%"
        query = query.where(or_(QCTask.task_name.ilike(pattern), QCTask.task_number.ilike(pattern)))
    query = query.order_by(QCTask.created_at.desc(), QCTask.id.desc()).limit(MAX_EXPORT_ROWS + 1)

    try:
        # 单条 SELECT 同时承担范围读取和上限探测，避免跨页时看到不同数据库快照。
        with factory() as session:
            rows = list(session.execute(query).mappings().all())
    except TaskExportTooLarge:
        raise
    except Exception as exc:
        raise TaskExportUnavailable("任务导出数据源不可用") from exc

    if len(rows) > MAX_EXPORT_ROWS:
        raise TaskExportTooLarge(len(rows))
    return TaskExportResult(content=render_task_export_csv(rows), row_count=len(rows))
