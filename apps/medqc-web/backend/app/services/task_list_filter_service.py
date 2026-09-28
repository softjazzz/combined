"""任务列表、统计与导出共用的科室和创建日期筛选合同。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TaskListFilterInvalid(ValueError):
    """调用方提供的筛选参数无效。"""


class TaskDepartmentScopeInvalid(ValueError):
    """已保存的任务科室范围无法可靠解释。"""


@dataclass(frozen=True)
class TaskListFilter:
    department: str | None
    created_start: date | None
    created_end: date | None

    @property
    def utc_start(self) -> datetime | None:
        if self.created_start is None:
            return None
        return datetime.combine(
            self.created_start, time.min, HOSPITAL_TIMEZONE
        ).astimezone(timezone.utc)

    @property
    def utc_end_exclusive(self) -> datetime | None:
        if self.created_end is None:
            return None
        return datetime.combine(
            self.created_end + timedelta(days=1), time.min, HOSPITAL_TIMEZONE
        ).astimezone(timezone.utc)


def _optional_text(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TaskListFilterInvalid(f"{field} 无效")
    normalized = value.strip()
    return normalized or None


def _optional_date(value: str | None, *, field: str) -> date | None:
    normalized = _optional_text(value, field=field)
    if normalized is None:
        return None
    if not _DATE_PATTERN.fullmatch(normalized):
        raise TaskListFilterInvalid(f"{field} 必须为 YYYY-MM-DD")
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise TaskListFilterInvalid(f"{field} 不是有效日期") from exc


def parse_task_list_filter(
    *,
    department: str | None = None,
    created_start: str | None = None,
    created_end: str | None = None,
) -> TaskListFilter:
    """解析公共筛选参数；日期表示上海医院日历日且首尾均包含。"""
    start = _optional_date(created_start, field="created_start")
    end = _optional_date(created_end, field="created_end")
    if start is not None and end is not None and start > end:
        raise TaskListFilterInvalid("created_start 不能晚于 created_end")
    parsed = TaskListFilter(
        department=_optional_text(department, field="department"),
        created_start=start,
        created_end=end,
    )
    try:
        _ = parsed.utc_start
        _ = parsed.utc_end_exclusive
    except (OverflowError, ValueError) as exc:
        raise TaskListFilterInvalid("创建日期超出支持范围") from exc
    return parsed


def parse_saved_departments(value: Any) -> tuple[str, ...]:
    """严格解析任务保存的科室范围，避免子串匹配造成串科室。"""
    if value in (None, ""):
        return ()
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise TaskDepartmentScopeInvalid("任务科室范围不是有效 JSON") from exc
    if not isinstance(decoded, list):
        raise TaskDepartmentScopeInvalid("任务科室范围必须是列表")

    departments: list[str] = []
    seen: set[str] = set()
    for item in decoded:
        if not isinstance(item, str) or not item.strip():
            raise TaskDepartmentScopeInvalid("任务科室范围包含无效成员")
        normalized = item.strip()
        if normalized not in seen:
            seen.add(normalized)
            departments.append(normalized)
    return tuple(departments)


def task_matches_department(value: Any, department: str | None) -> bool:
    """仅在启用科室筛选时解析历史范围，未筛选时不受脏历史数据影响。"""
    if department is None:
        return True
    saved_departments = parse_saved_departments(value)
    return not saved_departments or department in saved_departments


def postgres_timestamp(value: datetime) -> str:
    """输出可供 PostgREST 比较 timestamptz 的 UTC ISO 值。"""
    return value.isoformat().replace("+00:00", "Z")


def sqlalchemy_timestamp(value: datetime) -> datetime:
    """QCTask.created_at 为无时区 UTC DateTime，SQL 查询使用同一基准。"""
    return value.astimezone(timezone.utc).replace(tzinfo=None)
