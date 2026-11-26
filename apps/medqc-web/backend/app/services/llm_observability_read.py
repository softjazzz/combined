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
    "cached_input_tokens",
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
    "cached_input_tokens",
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
    """使用参数化 SQL 从唯一事实表读取安全字段与聚合结果。"""

    @staticmethod
    def _is_sqlite(engine: Any) -> bool:
        dialect = getattr(engine, "dialect", None)
        return str(getattr(dialect, "name", "") or "").strip().lower() == "sqlite"

    @classmethod
    def _table_name(cls, engine: Any, connection: Any | None = None) -> str:
        if not cls._is_sqlite(engine):
            return "sys.llm_call_events"
        if connection is not None:
            try:
                dbs = connection.execute(text("PRAGMA database_list")).fetchall()
                if any(str(row[1]) == "sys" for row in dbs):
                    return "sys.llm_call_events"
            except Exception:
                pass
        return "llm_call_events"

    @classmethod
    def _build_where(
        cls,
        *,
        is_sqlite: bool,
        filters: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
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
            if key in {"start_at", "end_at"}:
                if is_sqlite:
                    clauses.append(f"julianday(started_at) {operator} julianday(:{key})")
                    params[key] = _iso(value) or value
                else:
                    clauses.append(f"started_at {operator} :{key}")
                    params[key] = value
            else:
                clauses.append(f"{key} {operator} :{key}")
                params[key] = value
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where_sql, params

    @staticmethod
    def _sql_expressions(is_sqlite: bool) -> dict[str, str]:
        if is_sqlite:
            stale_cond = "status = 'running' AND started_at IS NOT NULL AND julianday(started_at) <= julianday(:stale_cutoff)"
            bucket_expr = "date(julianday(started_at) + (8.0 / 24.0))"
            start_ts = "julianday(started_at)"
            finish_ts = (
                "CASE "
                f"WHEN {stale_cond} THEN julianday(started_at) + (10.0 / 1440.0) "
                "WHEN finished_at IS NOT NULL THEN julianday(finished_at) "
                "ELSE julianday(:now_utc) END"
            )
            called_at_expr = "COALESCE(finished_at, started_at)"
            called_at_sort = "MAX(julianday(COALESCE(finished_at, started_at)))"
        else:
            stale_cond = "status = 'running' AND started_at IS NOT NULL AND started_at <= :stale_cutoff"
            bucket_expr = "to_char(started_at AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM-DD')"
            start_ts = "started_at"
            finish_ts = (
                "CASE "
                f"WHEN {stale_cond} THEN started_at + INTERVAL '10 minutes' "
                "WHEN finished_at IS NOT NULL THEN finished_at "
                "ELSE :now_utc END"
            )
            called_at_expr = "COALESCE(finished_at, started_at)"
            called_at_sort = "MAX(COALESCE(finished_at, started_at))"

        eff_status = (
            "CASE "
            f"WHEN {stale_cond} THEN 'abandoned' "
            "ELSE COALESCE(NULLIF(status, ''), 'unclassified') END"
        )
        eff_safe_error = (
            "CASE "
            f"WHEN {stale_cond} THEN 'stale_running' "
            "ELSE COALESCE(NULLIF(safe_error_kind, ''), COALESCE(NULLIF(status, ''), 'unclassified')) END"
        )
        return {
            "stale_cond": stale_cond,
            "eff_status": eff_status,
            "eff_safe_error": eff_safe_error,
            "bucket_expr": bucket_expr,
            "start_ts": start_ts,
            "finish_ts": finish_ts,
            "called_at_expr": called_at_expr,
            "called_at_sort": called_at_sort,
        }

    @staticmethod
    def _attempt_select_columns(exprs: dict[str, str], *, is_sqlite: bool) -> str:
        eff_status = exprs["eff_status"]
        p95_col = (
            ""
            if is_sqlite
            else ", percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) "
            "FILTER (WHERE latency_ms IS NOT NULL AND latency_ms >= 0) AS p95_latency_ms"
        )
        return (
            "COUNT(DISTINCT NULLIF(TRIM(COALESCE(logical_call_id, '')), '')) AS logical_calls, "
            "COUNT(*) AS http_attempts, "
            "SUM(input_tokens) AS input_tokens, "
            "SUM(cached_input_tokens) AS cached_input_tokens, "
            "SUM(output_tokens) AS output_tokens, "
            "SUM(total_tokens) AS total_tokens, "
            "AVG(CASE WHEN latency_ms IS NOT NULL AND latency_ms >= 0 THEN CAST(latency_ms AS FLOAT) END) AS avg_latency_ms, "
            "SUM(CASE WHEN attempt_no > 1 THEN 1 ELSE 0 END) AS retry_attempts, "
            f"SUM(CASE WHEN ({eff_status}) = 'success' THEN 1 ELSE 0 END) AS successful_attempts, "
            f"SUM(CASE WHEN ({eff_status}) NOT IN ('success', 'running') THEN 1 ELSE 0 END) AS failed_attempts, "
            "SUM(CASE WHEN LOWER(TRIM(COALESCE(usage_state, ''))) != 'known' OR total_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_usage_attempts, "
            "SUM(CASE WHEN LOWER(TRIM(COALESCE(usage_state, ''))) = 'known' AND cached_input_tokens IS NULL THEN 1 ELSE 0 END) AS unknown_cache_usage_attempts"
            f"{p95_col}"
        )

    @staticmethod
    def _row_to_attempt_summary(
        row: dict[str, Any],
        *,
        p95_latency_ms: int | None,
        peak_concurrency: int,
    ) -> dict[str, Any]:
        http_attempts = int(row.get("http_attempts") or 0)
        avg_raw = row.get("avg_latency_ms")
        avg_latency = round(float(avg_raw), 2) if avg_raw is not None else None
        if http_attempts == 0:
            input_tokens: int | None = 0
            cached_input_tokens: int | None = 0
            output_tokens: int | None = 0
            total_tokens: int | None = 0
        else:
            input_tokens = _known_int(row.get("input_tokens"))
            cached_input_tokens = _known_int(row.get("cached_input_tokens"))
            output_tokens = _known_int(row.get("output_tokens"))
            total_tokens = _known_int(row.get("total_tokens"))
        return {
            "logical_calls": int(row.get("logical_calls") or 0),
            "http_attempts": http_attempts,
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": _known_int(p95_latency_ms),
            "peak_concurrency": int(peak_concurrency or 0),
            "retry_attempts": int(row.get("retry_attempts") or 0),
            "successful_attempts": int(row.get("successful_attempts") or 0),
            "failed_attempts": int(row.get("failed_attempts") or 0),
            "unknown_usage_attempts": int(row.get("unknown_usage_attempts") or 0),
            "unknown_cache_usage_attempts": int(row.get("unknown_cache_usage_attempts") or 0),
        }

    @staticmethod
    def _query_peak_concurrency(
        connection: Any,
        *,
        table: str,
        where_sql: str,
        extra_and: str,
        params: dict[str, Any],
        exprs: dict[str, str],
        group_exprs: list[tuple[str, str]] | None = None,
    ) -> dict[tuple[Any, ...], int]:
        where_parts = []
        if where_sql:
            where_parts.append(where_sql.removeprefix(" WHERE "))
        where_parts.append("started_at IS NOT NULL")
        if extra_and:
            where_parts.append(extra_and)
        combined_where = " WHERE " + " AND ".join(where_parts)

        start_ts = exprs["start_ts"]
        finish_ts = exprs["finish_ts"]
        if group_exprs:
            grp_select = ", ".join(f"{expr} AS {alias}" for expr, alias in group_exprs) + ", "
            grp_cols = ", ".join(alias for _, alias in group_exprs)
            partition_clause = f"PARTITION BY {grp_cols} "
            outer_select = f"{grp_cols}, COALESCE(MAX(active), 0) AS peak_concurrency"
            outer_group = f" GROUP BY {grp_cols}"
        else:
            grp_select = ""
            grp_cols = ""
            partition_clause = ""
            outer_select = "COALESCE(MAX(active), 0) AS peak_concurrency"
            outer_group = ""

        grp_pass = (grp_cols + ", ") if grp_cols else ""
        sql = (
            f"WITH intervals AS ("
            f"SELECT {grp_select}{start_ts} AS s, {finish_ts} AS f "
            f"FROM {table}{combined_where}"
            f"), points AS ("
            f"SELECT {grp_pass}s AS ts, 1 AS ord, 1 AS delta FROM intervals "
            f"UNION ALL "
            f"SELECT {grp_pass}CASE WHEN f <= s THEN s ELSE f END AS ts, "
            f"CASE WHEN f <= s THEN 2 ELSE 0 END AS ord, -1 AS delta FROM intervals"
            f"), running AS ("
            f"SELECT {grp_pass}SUM(delta) OVER ({partition_clause}ORDER BY ts ASC, ord ASC "
            f"ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS active FROM points"
            f") SELECT {outer_select} FROM running{outer_group}"
        )
        rows = connection.execute(text(sql), params).mappings().all()
        if not group_exprs:
            val = int(rows[0]["peak_concurrency"] or 0) if rows else 0
            return {(): val}
        return {
            tuple(row[alias] for _, alias in group_exprs): int(row["peak_concurrency"] or 0)
            for row in rows
        }

    @staticmethod
    def _query_sqlite_p95(
        connection: Any,
        *,
        table: str,
        where_sql: str,
        extra_and: str,
        params: dict[str, Any],
        group_exprs: list[tuple[str, str]] | None = None,
    ) -> dict[tuple[Any, ...], int | None]:
        where_parts = []
        if where_sql:
            where_parts.append(where_sql.removeprefix(" WHERE "))
        where_parts.append("latency_ms IS NOT NULL AND latency_ms >= 0")
        if extra_and:
            where_parts.append(extra_and)
        combined_where = " WHERE " + " AND ".join(where_parts)

        if group_exprs:
            grp_select = ", ".join(f"{expr} AS {alias}" for expr, alias in group_exprs) + ", "
            grp_cols = ", ".join(alias for _, alias in group_exprs)
            partition_clause = f"PARTITION BY {grp_cols} "
            outer_cols = f"{grp_cols}, latency_ms AS p95_latency_ms"
        else:
            grp_select = ""
            grp_cols = ""
            partition_clause = ""
            outer_cols = "latency_ms AS p95_latency_ms"

        grp_pass = (grp_cols + ", ") if grp_cols else ""
        sql = (
            f"WITH base AS (SELECT {grp_select}latency_ms FROM {table}{combined_where}), "
            f"ranked AS ("
            f"SELECT {grp_pass}latency_ms, "
            f"ROW_NUMBER() OVER ({partition_clause}ORDER BY latency_ms ASC) AS rn, "
            f"COUNT(*) OVER ({partition_clause}) AS cnt "
            f"FROM base"
            f") SELECT {outer_cols} FROM ranked WHERE rn = ((19 * cnt + 19) / 20)"
        )
        rows = connection.execute(text(sql), params).mappings().all()
        if not group_exprs:
            return {(): _known_int(rows[0]["p95_latency_ms"])} if rows else {}
        return {
            tuple(row[alias] for _, alias in group_exprs): _known_int(row["p95_latency_ms"])
            for row in rows
        }

    @classmethod
    def _fetch_records_page_in_connection(
        cls,
        connection: Any,
        *,
        table: str,
        is_sqlite: bool,
        where_sql: str,
        params: dict[str, Any],
        exprs: dict[str, str],
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        record_cond = "record_key_hash IS NOT NULL AND TRIM(record_key_hash) != ''"
        base_cond = where_sql.removeprefix(" WHERE ") if where_sql else ""
        record_where = (
            f" WHERE {base_cond} AND {record_cond}"
            if base_cond
            else f" WHERE {record_cond}"
        )

        total = int(
            connection.execute(
                text(f"SELECT COUNT(DISTINCT TRIM(record_key_hash)) FROM {table}{record_where}"),
                params,
            ).scalar()
            or 0
        )
        if total == 0:
            return [], 0

        eff_status = exprs["eff_status"]
        attempt_cols = cls._attempt_select_columns(exprs, is_sqlite=is_sqlite)
        offset = (page - 1) * page_size
        page_params = {**params, "page_limit": page_size, "page_offset": offset}
        sql = (
            f"SELECT TRIM(record_key_hash) AS record_key_hash, "
            f"{attempt_cols}, "
            f"MIN(started_at) AS first_started_at, "
            f"MAX(finished_at) AS last_finished_at, "
            f"MAX({exprs['called_at_expr']}) AS last_called_at, "
            f"MAX(CASE WHEN ({eff_status}) = 'running' THEN 1 ELSE 0 END) AS has_running, "
            f"MAX(CASE WHEN ({eff_status}) = 'success' THEN 1 ELSE 0 END) AS has_success, "
            f"MAX(CASE WHEN ({eff_status}) NOT IN ('success', 'running') THEN 1 ELSE 0 END) AS has_failure "
            f"FROM {table}{record_where} "
            f"GROUP BY TRIM(record_key_hash) "
            f"ORDER BY {exprs['called_at_sort']} DESC, TRIM(record_key_hash) DESC "
            f"LIMIT :page_limit OFFSET :page_offset"
        )
        record_rows = [dict(row) for row in connection.execute(text(sql), page_params).mappings().all()]
        if not record_rows:
            return [], total

        record_hashes = [str(row["record_key_hash"]) for row in record_rows]
        hash_placeholders = ", ".join(f":rk_{idx}" for idx in range(len(record_hashes)))
        hash_params = {**params, **{f"rk_{idx}": val for idx, val in enumerate(record_hashes)}}
        hash_filter = f"TRIM(record_key_hash) IN ({hash_placeholders})"

        peaks = cls._query_peak_concurrency(
            connection,
            table=table,
            where_sql=where_sql,
            extra_and=hash_filter,
            params=hash_params,
            exprs=exprs,
            group_exprs=[("TRIM(record_key_hash)", "record_key_hash")],
        )
        sqlite_p95: dict[tuple[Any, ...], int | None] = {}
        if is_sqlite:
            sqlite_p95 = cls._query_sqlite_p95(
                connection,
                table=table,
                where_sql=where_sql,
                extra_and=hash_filter,
                params=hash_params,
                group_exprs=[("TRIM(record_key_hash)", "record_key_hash")],
            )

        meta_where = (
            f" WHERE {base_cond} AND {hash_filter}"
            if base_cond
            else f" WHERE {hash_filter}"
        )
        meta_rows = connection.execute(
            text(
                f"SELECT DISTINCT TRIM(record_key_hash) AS record_key_hash, business_scene, model "
                f"FROM {table}{meta_where}"
            ),
            hash_params,
        ).mappings().all()
        scenes_by_hash: dict[str, set[str]] = defaultdict(set)
        models_by_hash: dict[str, set[str]] = defaultdict(set)
        for meta in meta_rows:
            rh = str(meta["record_key_hash"])
            if meta.get("business_scene"):
                scenes_by_hash[rh].add(str(meta["business_scene"]))
            if meta.get("model"):
                models_by_hash[rh].add(str(meta["model"]))

        items: list[dict[str, Any]] = []
        for row in record_rows:
            rh = str(row["record_key_hash"])
            p95_val = sqlite_p95.get((rh,)) if is_sqlite else row.get("p95_latency_ms")
            summary = cls._row_to_attempt_summary(
                row,
                p95_latency_ms=p95_val,
                peak_concurrency=peaks.get((rh,), 0),
            )
            if row.get("has_running"):
                rec_status = "running"
            elif row.get("has_success") and row.get("has_failure"):
                rec_status = "partial_failure"
            elif row.get("has_failure"):
                rec_status = "failed"
            elif row.get("has_success"):
                rec_status = "success"
            else:
                rec_status = "unknown"
            items.append(
                {
                    "record_key_hash": rh,
                    **summary,
                    "first_started_at": _iso(row.get("first_started_at")),
                    "last_finished_at": _iso(row.get("last_finished_at")),
                    "last_called_at": _iso(row.get("last_called_at")),
                    "status": rec_status,
                    "business_scenes": sorted(scenes_by_hash.get(rh, set())),
                    "models": sorted(models_by_hash.get(rh, set())),
                }
            )
        return items, total

    async def fetch_events(self, **filters: Any) -> list[dict[str, Any]]:
        return await to_thread.run_sync(partial(self._fetch_events_sync, **filters))

    @classmethod
    def _fetch_events_sync(cls, **filters: Any) -> list[dict[str, Any]]:
        engine = database_connection.engine
        if engine is None:
            raise LLMObservabilityUnavailableError("llm_observability_store_unavailable")

        is_sqlite = cls._is_sqlite(engine)
        where_sql, params = cls._build_where(is_sqlite=is_sqlite, filters=filters)
        selected_columns = ", ".join(_SAFE_EVENT_COLUMNS)

        try:
            with engine.connect() as connection:
                table = cls._table_name(engine, connection)
                sql = (
                    f"SELECT {selected_columns} FROM {table}{where_sql}"
                    " ORDER BY started_at ASC, logical_call_id ASC, attempt_no ASC"
                )
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

    async def fetch_overview_sql(
        self,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        return await to_thread.run_sync(
            partial(
                self._fetch_overview_sql_sync,
                filters=filters,
                page=page,
                page_size=page_size,
            )
        )

    @classmethod
    def _fetch_overview_sql_sync(
        cls,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        engine = database_connection.engine
        if engine is None:
            raise LLMObservabilityUnavailableError("llm_observability_store_unavailable")

        is_sqlite = cls._is_sqlite(engine)
        filter_dict = {
            "start_at": filters.start_at,
            "end_at": filters.end_at,
            "business_scene": filters.business_scene,
            "provider_code": filters.provider_code,
            "model": filters.model,
            "root_job_id": filters.root_job_id,
            "record_key_hash": None,
        }
        where_sql, base_params = cls._build_where(is_sqlite=is_sqlite, filters=filter_dict)
        now_utc = datetime.now(timezone.utc)
        stale_cutoff = now_utc - _STALE_RUNNING_AFTER
        params = {
            **base_params,
            "now_utc": _iso(now_utc) if is_sqlite else now_utc,
            "stale_cutoff": _iso(stale_cutoff) if is_sqlite else stale_cutoff,
        }
        exprs = cls._sql_expressions(is_sqlite)
        attempt_cols = cls._attempt_select_columns(exprs, is_sqlite=is_sqlite)

        try:
            with engine.connect() as connection:
                table = cls._table_name(engine, connection)

                # 1. KPIs (1 row)
                kpi_sql = (
                    f"SELECT {attempt_cols}, "
                    "COUNT(DISTINCT NULLIF(TRIM(COALESCE(record_key_hash, '')), '')) AS record_count, "
                    "SUM(CASE WHEN record_key_hash IS NULL OR TRIM(record_key_hash) = '' THEN 1 ELSE 0 END) AS unbound_record_attempts "
                    f"FROM {table}{where_sql}"
                )
                kpi_row = dict(connection.execute(text(kpi_sql), params).mappings().one())
                kpi_peak = cls._query_peak_concurrency(
                    connection,
                    table=table,
                    where_sql=where_sql,
                    extra_and="",
                    params=params,
                    exprs=exprs,
                ).get((), 0)
                kpi_p95 = (
                    cls._query_sqlite_p95(
                        connection,
                        table=table,
                        where_sql=where_sql,
                        extra_and="",
                        params=params,
                    ).get(())
                    if is_sqlite
                    else kpi_row.get("p95_latency_ms")
                )
                kpi_summary = cls._row_to_attempt_summary(
                    kpi_row,
                    p95_latency_ms=kpi_p95,
                    peak_concurrency=kpi_peak,
                )
                kpis = {
                    "logical_calls": kpi_summary["logical_calls"],
                    "http_attempts": kpi_summary["http_attempts"],
                    "record_count": int(kpi_row.get("record_count") or 0),
                    "unbound_record_attempts": int(kpi_row.get("unbound_record_attempts") or 0),
                    "input_tokens": kpi_summary["input_tokens"],
                    "cached_input_tokens": kpi_summary["cached_input_tokens"],
                    "output_tokens": kpi_summary["output_tokens"],
                    "total_tokens": kpi_summary["total_tokens"],
                    "avg_latency_ms": kpi_summary["avg_latency_ms"],
                    "p95_latency_ms": kpi_summary["p95_latency_ms"],
                    "peak_concurrency": kpi_summary["peak_concurrency"],
                    "retry_attempts": kpi_summary["retry_attempts"],
                    "successful_attempts": kpi_summary["successful_attempts"],
                    "failed_attempts": kpi_summary["failed_attempts"],
                    "unknown_usage_attempts": kpi_summary["unknown_usage_attempts"],
                    "unknown_cache_usage_attempts": kpi_summary["unknown_cache_usage_attempts"],
                }

                # 2. Trends (<= 31 rows for 30d window)
                base_cond = where_sql.removeprefix(" WHERE ") if where_sql else ""
                trend_where = (
                    f" WHERE {base_cond} AND started_at IS NOT NULL"
                    if base_cond
                    else " WHERE started_at IS NOT NULL"
                )
                bucket_expr = exprs["bucket_expr"]
                trend_sql = (
                    f"SELECT {bucket_expr} AS bucket, {attempt_cols} "
                    f"FROM {table}{trend_where} "
                    f"GROUP BY {bucket_expr} "
                    f"ORDER BY bucket ASC"
                )
                trend_rows = [
                    dict(row) for row in connection.execute(text(trend_sql), params).mappings().all()
                ]
                trend_peaks = cls._query_peak_concurrency(
                    connection,
                    table=table,
                    where_sql=where_sql,
                    extra_and="",
                    params=params,
                    exprs=exprs,
                    group_exprs=[(bucket_expr, "bucket")],
                ) if trend_rows else {}
                trend_p95 = (
                    cls._query_sqlite_p95(
                        connection,
                        table=table,
                        where_sql=where_sql,
                        extra_and="started_at IS NOT NULL",
                        params=params,
                        group_exprs=[(bucket_expr, "bucket")],
                    )
                    if (is_sqlite and trend_rows)
                    else {}
                )
                trends = [
                    {
                        "bucket": str(row["bucket"]),
                        **cls._row_to_attempt_summary(
                            row,
                            p95_latency_ms=trend_p95.get((row["bucket"],)) if is_sqlite else row.get("p95_latency_ms"),
                            peak_concurrency=trend_peaks.get((row["bucket"],), 0),
                        ),
                    }
                    for row in trend_rows
                    if row.get("bucket")
                ]

                # 3. Models
                provider_expr = "COALESCE(NULLIF(provider_code, ''), 'unknown')"
                model_expr = "COALESCE(NULLIF(model, ''), 'unknown')"
                role_expr = "COALESCE(NULLIF(model_role, ''), 'unknown')"
                model_sql = (
                    f"SELECT {provider_expr} AS provider_code, "
                    f"{model_expr} AS model, "
                    f"{role_expr} AS model_role, "
                    f"{attempt_cols} "
                    f"FROM {table}{where_sql} "
                    f"GROUP BY {provider_expr}, {model_expr}, {role_expr} "
                    f"ORDER BY http_attempts DESC, provider_code ASC, model ASC, model_role ASC"
                )
                model_rows = [
                    dict(row) for row in connection.execute(text(model_sql), params).mappings().all()
                ]
                model_groups = [
                    (provider_expr, "provider_code"),
                    (model_expr, "model"),
                    (role_expr, "model_role"),
                ]
                model_peaks = (
                    cls._query_peak_concurrency(
                        connection,
                        table=table,
                        where_sql=where_sql,
                        extra_and="",
                        params=params,
                        exprs=exprs,
                        group_exprs=model_groups,
                    )
                    if model_rows
                    else {}
                )
                model_p95 = (
                    cls._query_sqlite_p95(
                        connection,
                        table=table,
                        where_sql=where_sql,
                        extra_and="",
                        params=params,
                        group_exprs=model_groups,
                    )
                    if (is_sqlite and model_rows)
                    else {}
                )
                models = [
                    {
                        "provider_code": str(row["provider_code"]),
                        "model": str(row["model"]),
                        "model_role": str(row["model_role"]),
                        **cls._row_to_attempt_summary(
                            row,
                            p95_latency_ms=(
                                model_p95.get((row["provider_code"], row["model"], row["model_role"]))
                                if is_sqlite
                                else row.get("p95_latency_ms")
                            ),
                            peak_concurrency=model_peaks.get(
                                (row["provider_code"], row["model"], row["model_role"]), 0
                            ),
                        ),
                    }
                    for row in model_rows
                ]

                # 4. Safe errors
                eff_status = exprs["eff_status"]
                eff_safe_error = exprs["eff_safe_error"]
                error_cond = f"({eff_status}) NOT IN ('success', 'running')"
                error_where = (
                    f" WHERE {base_cond} AND {error_cond}"
                    if base_cond
                    else f" WHERE {error_cond}"
                )
                error_sql = (
                    f"SELECT ({eff_status}) AS eff_status, "
                    f"({eff_safe_error}) AS eff_safe_error_kind, "
                    f"COUNT(*) AS cnt "
                    f"FROM {table}{error_where} "
                    f"GROUP BY ({eff_status}), ({eff_safe_error}) "
                    f"ORDER BY cnt DESC, eff_status ASC, eff_safe_error_kind ASC"
                )
                safe_errors = [
                    {
                        "status": str(row["eff_status"]),
                        "safe_error_kind": str(row["eff_safe_error_kind"]),
                        "count": int(row["cnt"] or 0),
                    }
                    for row in connection.execute(text(error_sql), params).mappings().all()
                ]

                # 5. Paginated records
                record_items, record_total = cls._fetch_records_page_in_connection(
                    connection,
                    table=table,
                    is_sqlite=is_sqlite,
                    where_sql=where_sql,
                    params=params,
                    exprs=exprs,
                    page=page,
                    page_size=page_size,
                )

                return {
                    "kpis": kpis,
                    "trends": trends,
                    "models": models,
                    "safe_errors": safe_errors,
                    "records": {
                        "items": record_items,
                        "total": record_total,
                        "page": page,
                        "page_size": page_size,
                    },
                }
        except Exception as exc:
            logger.warning(
                "llm_observability_read_failed error_type=%s",
                type(exc).__name__,
            )
            raise LLMObservabilityUnavailableError(
                "llm_observability_store_unavailable"
            ) from exc

    async def fetch_records_page(
        self,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        return await to_thread.run_sync(
            partial(
                self._fetch_records_page_sync,
                filters=filters,
                page=page,
                page_size=page_size,
            )
        )

    @classmethod
    def _fetch_records_page_sync(
        cls,
        *,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        engine = database_connection.engine
        if engine is None:
            raise LLMObservabilityUnavailableError("llm_observability_store_unavailable")

        is_sqlite = cls._is_sqlite(engine)
        filter_dict = {
            "start_at": filters.start_at,
            "end_at": filters.end_at,
            "business_scene": filters.business_scene,
            "provider_code": filters.provider_code,
            "model": filters.model,
            "root_job_id": filters.root_job_id,
            "record_key_hash": None,
        }
        where_sql, base_params = cls._build_where(is_sqlite=is_sqlite, filters=filter_dict)
        now_utc = datetime.now(timezone.utc)
        stale_cutoff = now_utc - _STALE_RUNNING_AFTER
        params = {
            **base_params,
            "now_utc": _iso(now_utc) if is_sqlite else now_utc,
            "stale_cutoff": _iso(stale_cutoff) if is_sqlite else stale_cutoff,
        }
        exprs = cls._sql_expressions(is_sqlite)
        try:
            with engine.connect() as connection:
                table = cls._table_name(engine, connection)
                return cls._fetch_records_page_in_connection(
                    connection,
                    table=table,
                    is_sqlite=is_sqlite,
                    where_sql=where_sql,
                    params=params,
                    exprs=exprs,
                    page=page,
                    page_size=page_size,
                )
        except Exception as exc:
            logger.warning(
                "llm_observability_read_failed error_type=%s",
                type(exc).__name__,
            )
            raise LLMObservabilityUnavailableError(
                "llm_observability_store_unavailable"
            ) from exc

    async def fetch_record_calls_page(
        self,
        *,
        record_key_hash: str,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        return await to_thread.run_sync(
            partial(
                self._fetch_record_calls_page_sync,
                record_key_hash=record_key_hash,
                filters=filters,
                page=page,
                page_size=page_size,
            )
        )

    @classmethod
    def _fetch_record_calls_page_sync(
        cls,
        *,
        record_key_hash: str,
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        engine = database_connection.engine
        if engine is None:
            raise LLMObservabilityUnavailableError("llm_observability_store_unavailable")

        is_sqlite = cls._is_sqlite(engine)
        filter_dict = {
            "start_at": filters.start_at,
            "end_at": filters.end_at,
            "business_scene": filters.business_scene,
            "provider_code": filters.provider_code,
            "model": filters.model,
            "root_job_id": filters.root_job_id,
            "record_key_hash": record_key_hash,
        }
        where_sql, params = cls._build_where(is_sqlite=is_sqlite, filters=filter_dict)
        selected_columns = ", ".join(_DETAIL_EVENT_COLUMNS)
        offset = (page - 1) * page_size
        order_started = "julianday(started_at) DESC" if is_sqlite else "started_at DESC"
        try:
            with engine.connect() as connection:
                table = cls._table_name(engine, connection)
                total = int(
                    connection.execute(
                        text(f"SELECT COUNT(*) FROM {table}{where_sql}"),
                        params,
                    ).scalar()
                    or 0
                )
                if total == 0:
                    return [], 0
                page_params = {**params, "page_limit": page_size, "page_offset": offset}
                sql = (
                    f"SELECT {selected_columns} FROM {table}{where_sql} "
                    f"ORDER BY {order_started}, logical_call_id DESC, attempt_no DESC "
                    f"LIMIT :page_limit OFFSET :page_offset"
                )
                rows = [
                    dict(row._mapping)
                    for row in connection.execute(text(sql), page_params)
                ]
                rows = _project_stale_running_attempts(rows)
                items = []
                for row in rows:
                    item = {key: row.get(key) for key in _DETAIL_EVENT_COLUMNS}
                    item["started_at"] = _iso(item["started_at"])
                    item["finished_at"] = _iso(item["finished_at"])
                    items.append(item)
                return items, total
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


def _unknown_cache_usage_count(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if str(row.get("usage_state") or "").strip().lower() == "known"
        and row.get("cached_input_tokens") is None
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
        "cached_input_tokens": _sum_known(rows, "cached_input_tokens"),
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
        "unknown_cache_usage_attempts": _unknown_cache_usage_count(rows),
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
        range_payload = {
            "start_at": _iso(filters.start_at),
            "end_at": _iso(filters.end_at),
            "business_scene": filters.business_scene,
            "provider_code": filters.provider_code,
            "model": filters.model,
            "root_job_id": filters.root_job_id,
            "timezone": _DISPLAY_TIMEZONE_NAME,
        }
        sql_overview = getattr(self._reader, "fetch_overview_sql", None)
        if callable(sql_overview):
            aggregated = await sql_overview(
                filters=filters,
                page=page,
                page_size=page_size,
            )
            return {
                "scope": {
                    "account_scope": "all_accounts",
                    "record_scope": "all_observed_records",
                },
                "range": range_payload,
                **aggregated,
            }

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
            "unbound_record_attempts": sum(
                1
                for row in rows
                if not str(row.get("record_key_hash") or "").strip()
            ),
        }
        # 固定合同顺序，避免调用方因字典插入顺序产生漂移。
        kpis = {
            "logical_calls": kpis["logical_calls"],
            "http_attempts": kpis["http_attempts"],
            "record_count": kpis["record_count"],
            "unbound_record_attempts": kpis["unbound_record_attempts"],
            "input_tokens": kpis["input_tokens"],
            "cached_input_tokens": kpis["cached_input_tokens"],
            "output_tokens": kpis["output_tokens"],
            "total_tokens": kpis["total_tokens"],
            "avg_latency_ms": kpis["avg_latency_ms"],
            "p95_latency_ms": kpis["p95_latency_ms"],
            "peak_concurrency": kpis["peak_concurrency"],
            "retry_attempts": kpis["retry_attempts"],
            "successful_attempts": kpis["successful_attempts"],
            "failed_attempts": kpis["failed_attempts"],
            "unknown_usage_attempts": kpis["unknown_usage_attempts"],
            "unknown_cache_usage_attempts": kpis["unknown_cache_usage_attempts"],
        }
        records = _record_items(rows)
        offset = (page - 1) * page_size
        return {
            "scope": {
                "account_scope": "all_accounts",
                "record_scope": "all_observed_records",
            },
            "range": range_payload,
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
        filters: LLMObservabilityFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        sql_calls = getattr(self._reader, "fetch_record_calls_page", None)
        if callable(sql_calls):
            items, total = await sql_calls(
                record_key_hash=record_key_hash,
                filters=filters,
                page=page,
                page_size=page_size,
            )
            return {
                "record_key_hash": record_key_hash,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        rows = await self._reader.fetch_events(
            start_at=filters.start_at,
            end_at=filters.end_at,
            business_scene=filters.business_scene,
            provider_code=filters.provider_code,
            model=filters.model,
            root_job_id=filters.root_job_id,
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
        range_payload = {
            "start_at": _iso(filters.start_at),
            "end_at": _iso(filters.end_at),
            "business_scene": filters.business_scene,
            "provider_code": filters.provider_code,
            "model": filters.model,
            "root_job_id": filters.root_job_id,
            "timezone": _DISPLAY_TIMEZONE_NAME,
        }
        sql_records = getattr(self._reader, "fetch_records_page", None)
        if callable(sql_records):
            items, total = await sql_records(
                filters=filters,
                page=page,
                page_size=page_size,
            )
            return {
                "range": range_payload,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

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
            "range": range_payload,
            "items": records[offset : offset + page_size],
            "total": len(records),
            "page": page,
            "page_size": page_size,
        }
