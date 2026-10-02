"""双列表列查询：只读取既有字段，在完整候选集分页前筛选排序。"""
from __future__ import annotations

import json
from typing import Any, Mapping
from datetime import datetime, timezone

RECORD_COLUMNS = {"patient", "department", "admission", "discharge", "latestQc", "score", "grade", "review"}
DEFECT_COLUMNS = {"patient", "department", "source", "rule", "document", "status"}
MAX_COLUMN_RECORDS = 5000


class WorkstationColumnRangeTooLarge(ValueError):
    pass


class WorkstationColumnInvalid(ValueError):
    pass


def normalize_column_query(view: str, filters: str | None, sort: str | None, direction: str):
    allowed = DEFECT_COLUMNS if view == "defects" else RECORD_COLUMNS
    if direction not in {"asc", "desc"} or (sort and sort not in allowed):
        raise WorkstationColumnInvalid("列表排序列或方向无效")
    try:
        parsed = json.loads(filters) if filters else {}
    except (TypeError, ValueError) as exc:
        raise WorkstationColumnInvalid("列筛选格式无效") from exc
    if not isinstance(parsed, dict) or any(
        key not in allowed or not isinstance(value, str) or len(value) > 100
        for key, value in parsed.items()
    ):
        raise WorkstationColumnInvalid("列筛选字段或关键字无效")
    return {key: value.strip().casefold() for key, value in parsed.items() if value.strip()}, sort or None, direction


def column_value(row: Mapping[str, Any], column: str, view: str):
    if view == "defects":
        fields = {
            "patient": "patient_name", "department": "department", "source": "source",
            "rule": "rule_id", "document": "document", "status": "status",
        }
        value = row.get(fields[column])
        if column == "rule":
            return " ".join(str(row.get(key) or "") for key in ("rule_id", "rule_name", "description"))
        if column == "source":
            return {"auto": "自动缺陷", "manual": "人工缺陷"}.get(value, value)
        if column == "status":
            return "确认缺陷" if row.get("source") == "auto" else {"approved": "审核通过", "pending": "待审核", "rejected": "已驳回"}.get(value)
        if column == "patient":
            return " ".join(str(row.get(key) or "") for key in ("patient_name", "institute_id", "patient_id", "visit_id"))
        return value
    summary = row.get("latest_qc_summary") or {}
    score = summary.get("score_state") or {}
    if column in {"score", "grade"}:
        return score.get(column) if score.get("status") == "scored" else None
    if column == "latestQc":
        value = summary.get("completed_at")
        if value:
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return value
            except ValueError:
                pass
        return None
    if column == "review":
        return {"pending_review": "待审核", "pending_recheck": "待复审", "approved": "审核通过", "doubtful": "审核存疑"}.get(summary.get("review_state"))
    if column == "patient":
        return " ".join(str(row.get(key) or "") for key in ("name", "instituteId", "patientId", "id"))
    return row.get({"patient": "name", "department": "department", "admission": "admissionDate", "discharge": "dischargeDate"}[column])


def query_columns(rows: list[dict], *, view: str, filters: dict[str, str], sort: str | None, direction: str):
    result = [row for row in rows if all(
        value in ("未知" if column_value(row, key, view) is None else str(column_value(row, key, view))).casefold() for key, value in filters.items()
    )]
    if not sort:
        return result
    # 次键固定三坐标与缺陷ID；未知值始终置后，不伪造0或空日期。
    result.sort(key=lambda row: tuple(str(row.get(key) or "") for key in (
        "instituteId", "patientId", "id", "institute_id", "patient_id", "visit_id", "defect_id", "rule_id",
    )))
    known = [row for row in result if column_value(row, sort, view) not in (None, "")]
    unknown = [row for row in result if column_value(row, sort, view) in (None, "")]
    def sort_value(row):
        value = column_value(row, sort, view)
        if sort == "latestQc":
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
            except ValueError:
                return float("-inf")
        return value
    known.sort(key=sort_value, reverse=direction == "desc")
    return known + unknown
