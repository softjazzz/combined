"""门急诊病历列表与导出的统一只读 owner。"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Awaitable, Callable, Mapping

from ..core.supabase_client import async_execute

SOURCE_PAGE_SIZE = 1_000
MAX_SOURCE_ROWS = 100_000
MAX_EXPORT_ROWS = 10_000
ALLOWED_SORT_FIELDS = frozenset({
    "visit_date", "score", "defect_count", "patient_name", "department",
})
ALLOWED_SORT_ORDERS = frozenset({"asc", "desc"})


class OutpatientRecordInvalid(ValueError):
    pass


class OutpatientRecordSourceUnavailable(RuntimeError):
    pass


class OutpatientRecordSourceTooLarge(RuntimeError):
    def __init__(self, count: int) -> None:
        super().__init__(f"门急诊病历源超过 {MAX_SOURCE_ROWS} 条，无法保证完整读取")
        self.count = count


class OutpatientRecordExportTooLarge(RuntimeError):
    def __init__(self, count: int) -> None:
        super().__init__(f"匹配病历共 {count} 条，超过导出上限 {MAX_EXPORT_ROWS} 条")
        self.count = count


@dataclass(frozen=True)
class OutpatientRecordFilter:
    keyword: str | None = None
    department: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scoring_standard: str | None = None
    sort_field: str = "visit_date"
    sort_order: str = "desc"


@dataclass(frozen=True)
class OutpatientRecordPage:
    items: list[dict[str, Any]]
    total: int


@dataclass(frozen=True)
class OutpatientRecordExport:
    content: bytes
    row_count: int


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_number(value: Any, cast: Callable[[Any], Any]) -> Any:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if cast is int and isinstance(value, float) and not value.is_integer():
            return None
        converted = cast(value)
        if isinstance(converted, float) and not math.isfinite(converted):
            return None
        return converted
    except (TypeError, ValueError):
        return None


def normalize_date_only(value: Any) -> str:
    text = _text(value)
    return text[:10] if len(text) >= 10 else text


def _visit_type(row: Mapping[str, Any]) -> str:
    visit_type = _text(row.get("visit_type")).lower()
    if visit_type in {"outpatient", "emergency"}:
        return visit_type
    record_type = _text(row.get("record_type")).lower()
    if "emergency" in record_type or "急诊" in record_type:
        return "emergency"
    if "outpatient" in record_type or "门诊" in record_type:
        return "outpatient"
    return ""


def normalize_record(row: Mapping[str, Any]) -> dict[str, Any]:
    score = _optional_number(row.get("score"), float)
    if score is None:
        score = _optional_number(row.get("overall_score"), float)
    return {
        "id": row.get("id") or row.get("record_id") or row.get("visit_id") or "",
        "record_id": row.get("record_id") or row.get("mr_no") or row.get("visit_id") or row.get("id") or "",
        "patient_name": row.get("patient_name") or row.get("name") or "",
        "department": row.get("department") or row.get("department_name") or row.get("admission_dept_name") or "",
        "doctor_name": row.get("doctor_name") or row.get("attending_physician_sign") or row.get("doctor") or "",
        "visit_type": _visit_type(row),
        "visit_date": (
            normalize_date_only(row.get("visit_date"))
            or normalize_date_only(row.get("admission_date"))
            or normalize_date_only(row.get("admission_datetime"))
            or normalize_date_only(row.get("created_at"))
        ),
        "status": row.get("status") if row.get("status") not in (None, "") else None,
        "score": score,
        "defect_count": _optional_number(row.get("defect_count"), int),
        "scoring_standard": row.get("scoring_standard") or row.get("score_standard") or None,
        "source": "records",
    }


def build_filter(
    *,
    keyword: str | None = None,
    department: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    scoring_standard: str | None = None,
    sort_field: str | None = "visit_date",
    sort_order: str | None = "desc",
) -> OutpatientRecordFilter:
    def parsed_date(value: str | None, label: str) -> date | None:
        text = _text(value)
        if not text:
            return None
        try:
            if len(text) != 10:
                raise ValueError
            return date.fromisoformat(text)
        except ValueError:
            raise OutpatientRecordInvalid(f"{label}格式无效，应为 YYYY-MM-DD") from None

    start = parsed_date(start_date, "开始日期")
    end = parsed_date(end_date, "结束日期")
    if start and end and start > end:
        raise OutpatientRecordInvalid("开始日期不能晚于结束日期")
    field = _text(sort_field) or "visit_date"
    order = (_text(sort_order) or "desc").lower()
    if field not in ALLOWED_SORT_FIELDS:
        raise OutpatientRecordInvalid("不支持的排序字段")
    if order not in ALLOWED_SORT_ORDERS:
        raise OutpatientRecordInvalid("排序方向仅支持 asc 或 desc")
    return OutpatientRecordFilter(
        keyword=_text(keyword) or None,
        department=_text(department) or None,
        status=_text(status) or None,
        start_date=start,
        end_date=end,
        scoring_standard=_text(scoring_standard) or None,
        sort_field=field,
        sort_order=order,
    )


async def load_source_rows(
    *,
    source: Any,
    table_name: str,
    execute: Callable[[Any], Awaitable[Any]] = async_execute,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expected_count: int | None = None
    offset = 0
    try:
        while True:
            query = (
                source.table(table_name)
                .select("*", count="exact")
                .order("id", desc=False)
                .range(offset, offset + SOURCE_PAGE_SIZE - 1)
            )
            response = await execute(query)
            page = getattr(response, "data", None)
            count = getattr(response, "count", None)
            if (
                not isinstance(page, list)
                or type(count) is not int
                or count < 0
                or len(page) > SOURCE_PAGE_SIZE
            ):
                raise OutpatientRecordSourceUnavailable("门急诊病历源返回无效")
            if count > MAX_SOURCE_ROWS:
                raise OutpatientRecordSourceTooLarge(count)
            if expected_count is None:
                expected_count = count
            elif count != expected_count:
                raise OutpatientRecordSourceUnavailable("门急诊病历源读取期间发生变化")
            if not page and offset < count:
                raise OutpatientRecordSourceUnavailable("门急诊病历源分页读取不完整")
            rows.extend(dict(row) for row in page if isinstance(row, Mapping))
            if len(rows) != offset + len(page):
                raise OutpatientRecordSourceUnavailable("门急诊病历源包含无效记录")
            offset += len(page)
            if offset >= count:
                break
        source_ids = [_text(row.get("id")) for row in rows]
        if (
            expected_count is None
            or len(rows) != expected_count
            or any(not item_id for item_id in source_ids)
            or len(set(source_ids)) != len(source_ids)
        ):
            raise OutpatientRecordSourceUnavailable("门急诊病历源读取不完整")
        return rows
    except (OutpatientRecordSourceUnavailable, OutpatientRecordSourceTooLarge):
        raise
    except Exception as exc:
        raise OutpatientRecordSourceUnavailable("门急诊病历数据源暂不可用") from exc


def filter_and_sort(
    source_rows: list[Mapping[str, Any]], filters: OutpatientRecordFilter,
) -> list[dict[str, Any]]:
    rows = [normalize_record(row) for row in source_rows]
    rows = [row for row in rows if row["visit_type"] in {"outpatient", "emergency"}]
    if filters.keyword:
        keyword = filters.keyword.casefold()
        rows = [
            row for row in rows
            if any(keyword in _text(row.get(field)).casefold() for field in (
                "record_id", "patient_name", "doctor_name",
            ))
        ]
    if filters.department:
        rows = [row for row in rows if _text(row.get("department")) == filters.department]
    if filters.status:
        rows = [row for row in rows if _text(row.get("status")) == filters.status]
    if filters.scoring_standard:
        rows = [
            row for row in rows
            if _text(row.get("scoring_standard")) == filters.scoring_standard
        ]
    if filters.start_date:
        rows = [
            row for row in rows
            if normalize_date_only(row.get("visit_date")) >= filters.start_date.isoformat()
        ]
    if filters.end_date:
        rows = [
            row for row in rows
            if normalize_date_only(row.get("visit_date"))
            and normalize_date_only(row.get("visit_date")) <= filters.end_date.isoformat()
        ]

    def sort_value(row: Mapping[str, Any]) -> Any:
        value = row.get(filters.sort_field)
        return value.casefold() if isinstance(value, str) else value

    known = [row for row in rows if row.get(filters.sort_field) not in (None, "")]
    unknown = [row for row in rows if row.get(filters.sort_field) in (None, "")]
    known.sort(key=lambda row: _text(row.get("id")))
    known.sort(key=sort_value, reverse=filters.sort_order == "desc")
    unknown.sort(key=lambda row: _text(row.get("id")))
    return known + unknown


async def query_records(
    *,
    source: Any,
    table_name: str,
    filters: OutpatientRecordFilter,
    page: int,
    page_size: int,
    execute: Callable[[Any], Awaitable[Any]] = async_execute,
) -> OutpatientRecordPage:
    rows = filter_and_sort(
        await load_source_rows(source=source, table_name=table_name, execute=execute),
        filters,
    )
    start = (page - 1) * page_size
    return OutpatientRecordPage(items=rows[start:start + page_size], total=len(rows))


_EXPORT_FIELDS = (
    ("record_id", "病历号"),
    ("patient_name", "姓名"),
    ("visit_type", "就诊类型"),
    ("department", "科室"),
    ("doctor_name", "医生"),
    ("visit_date", "日期"),
    ("status", "状态"),
    ("score", "分数"),
    ("defect_count", "缺陷数"),
    ("scoring_standard", "评分标准"),
)


def _csv_safe(value: Any) -> Any:
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _export_value(row: Mapping[str, Any], field: str) -> Any:
    # 页面尚无门急诊现代质控结果 owner；不得从旧列表行恢复隐藏的质控结论。
    if field in {"status", "score", "defect_count", "scoring_standard"}:
        return ""
    return row.get(field)


async def export_records(
    *,
    source: Any,
    table_name: str,
    filters: OutpatientRecordFilter,
    execute: Callable[[Any], Awaitable[Any]] = async_execute,
) -> OutpatientRecordExport:
    rows = filter_and_sort(
        await load_source_rows(source=source, table_name=table_name, execute=execute),
        filters,
    )
    if len(rows) > MAX_EXPORT_ROWS:
        raise OutpatientRecordExportTooLarge(len(rows))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[label for _, label in _EXPORT_FIELDS])
    writer.writeheader()
    for row in rows:
        writer.writerow({
            label: _csv_safe(_export_value(row, field)) for field, label in _EXPORT_FIELDS
        })
    return OutpatientRecordExport(
        content=("\ufeff" + output.getvalue()).encode("utf-8"),
        row_count=len(rows),
    )
