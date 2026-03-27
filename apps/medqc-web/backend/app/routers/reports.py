from collections import defaultdict
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Request
import logging
from typing import List, Dict, Any
import time
import csv
import os
from pydantic import BaseModel

from ..core.audit import audit_event
from ..core.response import success_response, get_trace_id, StatusCode
from ..core.pagination import REPORT_SCAN_LIMIT
from ..core.supabase_client import get_supabase, async_execute
from ..services.sichuan_qc_service import SichuanQCService

logger = logging.getLogger(__name__)

# naive in-memory cache for summary
_QC_SUMMARY_CACHE: Dict[str, Any] | None = None
_QC_SUMMARY_CACHE_TS: float = 0.0
_QC_SUMMARY_TTL_SECONDS = 10.0


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _calculate_pass_rate(passed: int, warning: int, failed: int, pending: int) -> float:
    total = passed + warning + failed + pending
    if total <= 0:
        return 0.0
    return round((passed / total) * 100, 1)


def _init_trend_bucket(period: str, bucket_time: datetime) -> Dict[str, Any]:
    if period == "quarter":
        label = f"{bucket_time.year}-{bucket_time.month:02d}"
    else:
        label = bucket_time.strftime("%m-%d")
    return {
        "period": label,
        "bucket_time": bucket_time,
        "record_count": 0,
        "score_total": 0.0,
        "score_count": 0,
        "passed": 0,
        "warning": 0,
        "failed": 0,
        "pending": 0,
    }


def _build_trend_buckets(period: str) -> List[datetime]:
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return [now - timedelta(days=offset) for offset in range(6, -1, -1)]
    if period == "month":
        return [now - timedelta(days=offset) for offset in range(29, -1, -1)]
    month_starts: List[datetime] = []
    cursor = now.replace(day=1)
    for _ in range(3):
        month_starts.append(cursor)
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    return list(reversed(month_starts))


def _resolve_trend_bucket(period: str, analyzed_at: datetime) -> datetime:
    analyzed_day = analyzed_at.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "quarter":
        return analyzed_day.replace(day=1)
    return analyzed_day


async def _fetch_top_categories(sb) -> List[Dict[str, Any]]:
    try:
        defect_rows = await async_execute(
            sb.table("qc_defects").select("category").limit(REPORT_SCAN_LIMIT)
        )
    except Exception as exc:
        logger.warning(f"[reports] 查询 qc_defects 失败: {exc}")
        return []

    counts: Dict[str, int] = defaultdict(int)
    for row in defect_rows.data or []:
        category = (row.get("category") or "未分类").strip() if isinstance(row.get("category"), str) else "未分类"
        counts[category or "未分类"] += 1

    return [
        {"category": category, "issue_count": count}
        for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]
    ]


async def _fetch_trend_data(sb, period: str) -> List[Dict[str, Any]]:
    trend_rows = await async_execute(
        sb.table("qc_statistics_view")
        .select(
            "record_id,passed_count,warning_count,failed_count,pending_count,avg_qc_score,last_analyzed_time"
        )
        .limit(REPORT_SCAN_LIMIT)
    )
    rows = list(trend_rows.data or [])

    buckets = {bucket: _init_trend_bucket(period, bucket) for bucket in _build_trend_buckets(period)}
    if not buckets:
        return []

    for row in rows:
        analyzed_at = _parse_datetime(row.get("last_analyzed_time"))
        if analyzed_at is None:
            continue

        bucket_key = _resolve_trend_bucket(period, analyzed_at)
        if bucket_key not in buckets:
            continue

        bucket = buckets[bucket_key]
        bucket["record_count"] += 1
        score = row.get("avg_qc_score")
        if score is not None:
            bucket["score_total"] += float(score or 0)
            bucket["score_count"] += 1
        bucket["passed"] += int(row.get("passed_count", 0) or 0)
        bucket["warning"] += int(row.get("warning_count", 0) or 0)
        bucket["failed"] += int(row.get("failed_count", 0) or 0)
        bucket["pending"] += int(row.get("pending_count", 0) or 0)

    data = []
    for bucket_time in sorted(buckets.keys()):
        bucket = buckets[bucket_time]
        average_score = (
            round(bucket["score_total"] / bucket["score_count"], 1) if bucket["score_count"] else 0.0
        )
        data.append(
            {
                "period": bucket["period"],
                "record_count": bucket["record_count"],
                "average_score": average_score,
                "pass_rate": _calculate_pass_rate(
                    bucket["passed"], bucket["warning"], bucket["failed"], bucket["pending"]
                ),
            }
        )

    return data


@router.get("/qc/summary")
async def qc_summary(request: Request):
    """质控看板汇总（改为真实聚合）。

    - 从视图 `qc_statistics_view` 聚合：按病历维度统计文书总数、通过/告警/失败数量、平均分、最近分析时间。
    - `active_rules` 仍按启用规则计数。
    - 保留 10s 内存缓存以降低 Supabase 压力。
    """
    global _QC_SUMMARY_CACHE, _QC_SUMMARY_CACHE_TS
    now = time.time()
    if _QC_SUMMARY_CACHE is not None and (now - _QC_SUMMARY_CACHE_TS) < _QC_SUMMARY_TTL_SECONDS:
        # 返回缓存时也要包装成统一格式
        cached_data = _QC_SUMMARY_CACHE.get("data") if isinstance(_QC_SUMMARY_CACHE, dict) and "data" in _QC_SUMMARY_CACHE else _QC_SUMMARY_CACHE
        return success_response(data=cached_data, trace_id=get_trace_id(request))

    sb = get_supabase()
    active_rules = 0
    total_records = 0
    totals = {
        "executions": 0,
        "passed": 0,
        "warning": 0,
        "failed": 0,
        "pending": 0,
        "avg_qc_score": 0.0,
    }

    if sb is not None:
        try:
            # 读取聚合视图
            view_rows = await async_execute(sb.table("qc_statistics_view").select("*").limit(REPORT_SCAN_LIMIT))
            rows = view_rows.data or []
            total_records = len(rows)
            if rows:
                for r in rows:
                    totals["executions"] += int(r.get("total_documents", 0) or 0)
                    totals["passed"] += int(r.get("passed_count", 0) or 0)
                    totals["warning"] += int(r.get("warning_count", 0) or 0)
                    totals["failed"] += int(r.get("failed_count", 0) or 0)
                    totals["pending"] += int(r.get("pending_count", 0) or 0)
                # 平均分（按视图返回的 avg_qc_score 做一次简单均值）
                avg_list = [float(r.get("avg_qc_score", 0) or 0) for r in rows if r.get("avg_qc_score") is not None]
                if avg_list:
                    totals["avg_qc_score"] = sum(avg_list) / len(avg_list)
        except Exception as e:
            logger.warning(f"[reports] 查询 qc_statistics_view 失败: {e}")

        try:
            rr = await async_execute(sb.table("qc_rules").select("*").eq("is_active", True).limit(REPORT_SCAN_LIMIT))
            active_rules = len(rr.data or [])
        except Exception as e:
            logger.warning(f"[reports] 查询 qc_rules 失败: {e}")

        top_categories = await _fetch_top_categories(sb)
    else:
        top_categories = []

    qc_stats = SichuanQCService().stats()

    data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "kpis": {
            "total_records": total_records,
            "active_rules": active_rules,
            "qc_executions": totals["executions"],
            "pass_rate": qc_stats.get("success_rate", 0.0),
            "avg_api_time": qc_stats.get("avg_api_time", 0.0),
            "avg_qc_score": round(totals["avg_qc_score"], 2),
            "passed": totals["passed"],
            "warning": totals["warning"],
            "failed": totals["failed"],
            "pending": totals["pending"],
        },
        "top_categories": [],
    }
    data["top_categories"] = top_categories
    # 缓存数据部分（不包含 success/trace_id）
    _QC_SUMMARY_CACHE = data
    _QC_SUMMARY_CACHE_TS = now
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/qc/trend")
async def qc_trend(
    request: Request,
    period: str = Query("month", description="时间段: week | month | quarter"),
):
    if period not in {"week", "month", "quarter"}:
        raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail="invalid period")

    sb = get_supabase()
    if sb is None:
        return success_response(
            data={"period": period, "items": []},
            message="Supabase 不可用，返回空趋势数据",
            trace_id=get_trace_id(request),
        )

    try:
        items = await _fetch_trend_data(sb, period)
    except Exception as exc:
        logger.warning(f"[reports] 查询 qc 趋势失败: {exc}")
        items = []

    return success_response(
        data={"period": period, "items": items},
        message="获取趋势数据成功",
        trace_id=get_trace_id(request),
    )


class ExportRequest(BaseModel):
    record_ids: List[str] | None = None


@router.post("/qc/export")
async def qc_export(request: Request, payload: ExportRequest):
    """导出质控汇总（CSV）。

    - 数据来源：`qc_statistics_view`（若 Supabase 可用），否则返回 503。
    - 文件位置：`app/downloads/qc_summary_*.csv`，通过 `/downloads/*` 访问。
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=StatusCode.SERVICE_UNAVAILABLE, detail="supabase unavailable")

    # 查询视图
    q = sb.table("qc_statistics_view").select("*").limit(REPORT_SCAN_LIMIT)
    if payload.record_ids:
        # 过滤指定 record_id
        q = q.in_("record_id", payload.record_ids)
    resp = await async_execute(q)
    rows: List[Dict[str, Any]] = list(resp.data or [])

    export_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"qc_summary_{export_id}.csv"
    downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, filename)

    # 写 CSV
    headers = [
        "record_id",
        "total_documents",
        "passed_count",
        "warning_count",
        "failed_count",
        "pending_count",
        "avg_qc_score",
        "last_analyzed_time",
    ]
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in headers})

    download_url = f"/downloads/{filename}"
    audit_event(
        request,
        action="reports.qc.export",
        resource="/api/v1/reports/qc/export",
        outcome="success",
        details={
            "requested_records_count": len(payload.record_ids or []),
            "export_rows": len(rows),
            "download_url": download_url,
        },
    )

    return success_response(
        data={
            "export_id": export_id,
            "requested_records": payload.record_ids or [],
            "download_url": download_url,
            "count": len(rows),
        },
        message="导出成功",
        trace_id=get_trace_id(request)
    )


