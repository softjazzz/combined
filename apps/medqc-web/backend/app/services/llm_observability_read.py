"""模型调用观测数据的只读聚合服务。

本模块只读取 ``sys.llm_call_events``。它不保存提示词、响应正文、接口地址、
密钥、异常原文或患者三坐标，也不从任务结果中的历史估算字段补数。
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Protocol

from anyio import to_thread
from sqlalchemy import text

from ..database import connection as database_connection


logger = logging.getLogger(__name__)

_STALE_RUNNING_AFTER = timedelta(minutes=10)
_DISPLAY_TIMEZONE_NAME = "Asia/Shanghai"
_DISPLAY_TIMEZONE = timezone(timedelta(hours=8), _DISPLAY_TIMEZONE_NAME)


_SAFE_EVENT_COLUMNS = (
    "logical_call_id",
    "attempt_no",
    "started_at",
    "finished_at",
    "business_scene",
    "root_job_id",
    "record_key_hash",
    "rule_set_key",
    "rule_set_version",
    "executor_key",
    "provider_code",
    "model",
    "model_role",
    "status",
    "safe_error_kind",
    "usage_state",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    "worker_id",
)

_DETAIL_EVENT_COLUMNS = (
    "logical_call_id",
    "attempt_no",
    "business_scene",
    "root_job_id",
    "executor_key",
    "provider_code",
    "model",
    "model_role",
    "status",
    "safe_error_kind",
    "usage_state",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    "started_at",
    "finished_at",
)


class LLMObservabilityUnavailableError(RuntimeError):
    """观测表当前不可读；异常原文不得越过 API 边界。"""


@dataclass(frozen=True)
class LLMObservabilityFilters:
    start_at: datetime | None = None
    end_at: datetime | None = None
    business_scene: str | None = None
    provider_code: str | None = None
    model: str | None = None
    root_job_id: str | None = None
    record_key_hash: str | None = None


class LLMCallEventReader(Protocol):
    async def fetch_events(self, **filters: Any) -> list[dict[str, Any]]: ...


class PostgresLLMCallEventReader:
    """使用参数化 SQL 从唯一事实表读取安全字段。"""

    async def fetch_events(self, **filters: Any) -> list[dict[str, Any]]:
        return await to_thread.run_sync(partial(self._fetch_events_sync, **filters))

    @staticmethod
    def _fetch_events_sync(**filters: Any) -> list[dict[str, Any]]:
        engine = database_connection.engine
        if engine is None:
            raise LLMObservabilityUnavailableError("llm_observability_store_unavailable")

        clauses: list[str] = []
        params: dict[str, Any] = {}
        for key, operator in (
            ("start_at", ">="),
            ("end_at", "<="),
            ("business_scene", "="),
            ("provider_code", "="),
            ("model", "="),
            ("root_job_id", "="),
            ("record_key_hash", "="),
        ):
            value = filters.get(key)
            if value is None or value == "":
                continue
            column = "started_at" if key in {"start_at", "end_at"} else key
            clauses.append(f"{column} {operator} :{key}")
            params[key] = value

        selected_columns = ", ".join(_SAFE_EVENT_COLUMNS)
        sql = f"SELECT {selected_columns} FROM sys.llm_call_events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY started_at ASC, logical_call_id ASC, attempt_no ASC"

        try:
            with engine.connect() as connection:
                result = connection.execute(text(sql), params)
                return [dict(row._mapping) for row in result]
        except Exception as exc:
            logger.warning(
                "llm_observability_read_failed error_type=%s",
                type(exc).__name__,
            )
            raise LLMObservabilityUnavailableError(
                "llm_observability_store_unavailable"
            ) from exc


def _as_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _as_utc_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _known_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sum_known(rows: list[dict[str, Any]], key: str) -> int | None:
    if not rows:
        return 0
    values = [_known_int(row.get(key)) for row in rows]
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _latencies(rows: list[dict[str, Any]]) -> list[int]:
    return sorted(
        value
        for row in rows
        if (value := _known_int(row.get("latency_ms"))) is not None and value >= 0
    )


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _percentile_nearest_rank(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    index = max(0, math.ceil(percentile * len(values)) - 1)
    return sorted(values)[index]


def _peak_concurrency(rows: list[dict[str, Any]]) -> int:
    points: list[tuple[datetime, int, int]] = []
    fallback_end = datetime.now(timezone.utc)
    for row in rows:
        start = _as_utc_datetime(row.get("started_at"))
        if start is None:
            continue
        finish = (
            _as_utc_datetime(row.get("_concurrency_finished_at"))
            or _as_utc_datetime(row.get("finished_at"))
            or fallback_end
        )
        if finish <= start:
            finish = start + timedelta(microseconds=1)
        # 同一时刻先处理结束点，再处理开始点，按 [start, finish) 计算。
        points.append((start, 1, 1))
        points.append((finish, 0, -1))

    active = 0
    peak = 0
    for _, _, delta in sorted(points):
        active += delta
        peak = max(peak, active)
    return peak


def _logical_call_count(rows: list[dict[str, Any]]) -> int:
    return len(
        {
            str(row.get("logical_call_id") or "").strip()
            for row in rows
            if str(row.get("logical_call_id") or "").strip()
        }
    )


def _unknown_usage_count(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if str(row.get("usage_state") or "").strip().lower() != "known"
        or row.get("total_tokens") is None
    )


def _attempt_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    logical_calls = _logical_call_count(rows)
    attempts = len(rows)
    latencies = _latencies(rows)
    success_count = sum(1 for row in rows if row.get("status") == "success")
    failed_count = sum(
        1
        for row in rows
        if str(row.get("status") or "") not in {"success", "running"}
    )
    return {
        "logical_calls": logical_calls,
        "http_attempts": attempts,
        "input_tokens": _sum_known(rows, "input_tokens"),
        "output_tokens": _sum_known(rows, "output_tokens"),
        "total_tokens": _sum_known(rows, "total_tokens"),
        "avg_latency_ms": _average(latencies),
        "p95_latency_ms": _percentile_nearest_rank(latencies, 0.95),
        "peak_concurrency": _peak_concurrency(rows),
        "retry_attempts": sum(
            1 for row in rows if (_known_int(row.get("attempt_no")) or 0) > 1
        ),
        "successful_attempts": success_count,
        "failed_attempts": failed_count,
        "unknown_usage_attempts": _unknown_usage_count(rows),
    }


def _trend_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        started_at = _as_utc_datetime(row.get("started_at"))
        if started_at is not None:
            bucket = started_at.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d")
            groups[bucket].append(row)
    return [
        {"bucket": bucket, **_attempt_summary(group)}
        for bucket, group in sorted(groups.items())
    ]


def _model_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("provider_code") or "unknown"),
            str(row.get("model") or "unknown"),
            str(row.get("model_role") or "unknown"),
        )
        groups[key].append(row)

    items: list[dict[str, Any]] = []
    for (provider_code, model, model_role), group in groups.items():
        summary = _attempt_summary(group)
        items.append(
            {
                "provider_code": provider_code,
                "model": model,
                "model_role": model_role,
                **summary,
            }
        )
    return sorted(
        items,
        key=lambda item: (-int(item["http_attempts"]), item["provider_code"], item["model"]),
    )


def _safe_error_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        status = str(row.get("status") or "unclassified")
        if status in {"success", "running"}:
            continue
        safe_error_kind = str(row.get("safe_error_kind") or status)
        counts[(status, safe_error_kind)] += 1
    return [
        {"status": status, "safe_error_kind": kind, "count": count}
        for (status, kind), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]


def _project_stale_running_attempts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只读投影超时遗留的 running，不篡改事件表中的原始事实。"""

    cutoff = datetime.now(timezone.utc) - _STALE_RUNNING_AFTER
    projected: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        started_at = _as_utc_datetime(row.get("started_at"))
        if row.get("status") == "running" and started_at is not None and started_at <= cutoff:
            row["status"] = "abandoned"
            row["safe_error_kind"] = "stale_running"
            row["_concurrency_finished_at"] = started_at + _STALE_RUNNING_AFTER
        projected.append(row)
    return projected


def _record_status(rows: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("status") or "unclassified") for row in rows}
    if "running" in statuses:
        return "running"
    has_success = "success" in statuses
    has_failure = any(status != "success" for status in statuses)
    if has_success and has_failure:
        return "partial_failure"
    if has_failure:
        return "failed"
    return "success" if has_success else "unknown"


def _record_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        record_hash = str(row.get("record_key_hash") or "").strip()
        if record_hash:
            groups[record_hash].append(row)

    items: list[dict[str, Any]] = []
    for record_hash, group in groups.items():
        started_values = [
            value
            for row in group
            if (value := _as_utc_datetime(row.get("started_at"))) is not None
        ]
        finished_values = [
            value
            for row in group
            if (value := _as_utc_datetime(row.get("finished_at"))) is not None
        ]
        called_values = [
            _as_utc_datetime(row.get("finished_at"))
            or _as_utc_datetime(row.get("started_at"))
            for row in group
        ]
        called_values = [value for value in called_values if value is not None]
        items.append(
            {
                "record_key_hash": record_hash,
                **_attempt_summary(group),
                "first_started_at": _iso(min(started_values)) if started_values else None,
                "last_finished_at": _iso(max(finished_values)) if finished_values else None,
                "last_called_at": _iso(max(called_values)) if called_values else None,
                "status": _record_status(group),
                "business_scenes": sorted(
                    {
                        str(row.get("business_scene"))
                        for row in group
                        if row.get("business_scene")
                    }
                ),
                "models": sorted(
                    {
                        str(row.get("model"))
                        for row in group
                        if row.get("model")
                    }
                ),
            }
        )
    return sorted(
        items,
        key=lambda item: (item["last_called_at"] or ""),
        reverse=True,
    )


class LLMObservabilityReadService:
    def __init__(self, *, reader: LLMCallEventReader | None = None):
        self._reader = reader or PostgresLLMCallEventReader()

    async def build_overview(
        self,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        rows = await self._reader.fetch_events(
            start_at=filters.start_at,
            end_at=filters.end_at,
            business_scene=filters.business_scene,
            provider_code=filters.provider_code,
            model=filters.model,
            root_job_id=filters.root_job_id,
            record_key_hash=None,
        )
        rows = _project_stale_running_attempts(rows)
        kpis = {
            **_attempt_summary(rows),
            "record_count": len(
                {
                    str(row.get("record_key_hash") or "").strip()
                    for row in rows
                    if str(row.get("record_key_hash") or "").strip()
                }
            ),
        }
        # 固定合同顺序，避免调用方因字典插入顺序产生漂移。
        kpis = {
            "logical_calls": kpis["logical_calls"],
            "http_attempts": kpis["http_attempts"],
            "record_count": kpis["record_count"],
            "input_tokens": kpis["input_tokens"],
            "output_tokens": kpis["output_tokens"],
            "total_tokens": kpis["total_tokens"],
            "avg_latency_ms": kpis["avg_latency_ms"],
            "p95_latency_ms": kpis["p95_latency_ms"],
            "peak_concurrency": kpis["peak_concurrency"],
            "retry_attempts": kpis["retry_attempts"],
            "successful_attempts": kpis["successful_attempts"],
            "failed_attempts": kpis["failed_attempts"],
            "unknown_usage_attempts": kpis["unknown_usage_attempts"],
        }
        records = _record_items(rows)
        offset = (page - 1) * page_size
        return {
            "range": {
                "start_at": _iso(filters.start_at),
                "end_at": _iso(filters.end_at),
                "business_scene": filters.business_scene,
                "provider_code": filters.provider_code,
                "model": filters.model,
                "root_job_id": filters.root_job_id,
                "timezone": _DISPLAY_TIMEZONE_NAME,
            },
            "kpis": kpis,
            "trends": _trend_items(rows),
            "models": _model_items(rows),
            "safe_errors": _safe_error_items(rows),
            "records": {
                "items": records[offset : offset + page_size],
                "total": len(records),
                "page": page,
                "page_size": page_size,
            },
        }

    async def build_record_calls(
        self,
        *,
        record_key_hash: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        rows = await self._reader.fetch_events(
            start_at=None,
            end_at=None,
            business_scene=None,
            provider_code=None,
            model=None,
            root_job_id=None,
            record_key_hash=record_key_hash,
        )
        rows = _project_stale_running_attempts(rows)
        rows = sorted(
            rows,
            key=lambda row: (
                _as_utc_datetime(row.get("started_at")) or datetime.min.replace(tzinfo=timezone.utc),
                str(row.get("logical_call_id") or ""),
                _known_int(row.get("attempt_no")) or 0,
            ),
            reverse=True,
        )
        offset = (page - 1) * page_size
        items = []
        for row in rows[offset : offset + page_size]:
            item = {key: row.get(key) for key in _DETAIL_EVENT_COLUMNS}
            item["started_at"] = _iso(item["started_at"])
            item["finished_at"] = _iso(item["finished_at"])
            items.append(item)
        return {
            "record_key_hash": record_key_hash,
            "items": items,
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }

    async def build_records(
        self,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        rows = await self._reader.fetch_events(
            start_at=filters.start_at,
            end_at=filters.end_at,
            business_scene=filters.business_scene,
            provider_code=filters.provider_code,
            model=filters.model,
            root_job_id=filters.root_job_id,
            record_key_hash=None,
        )
        rows = _project_stale_running_attempts(rows)
        records = _record_items(rows)
        offset = (page - 1) * page_size
        return {
            "range": {
                "start_at": _iso(filters.start_at),
                "end_at": _iso(filters.end_at),
                "business_scene": filters.business_scene,
                "provider_code": filters.provider_code,
                "model": filters.model,
                "root_job_id": filters.root_job_id,
                "timezone": _DISPLAY_TIMEZONE_NAME,
            },
            "items": records[offset : offset + page_size],
            "total": len(records),
            "page": page,
            "page_size": page_size,
        }
