from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
import logging
from typing import List, Dict, Any
import time
import csv
import json
import os
import stat
from pathlib import Path
from pydantic import BaseModel
from uuid import UUID, uuid4

from ..core.audit import audit_event
from ..core.response import success_response, get_trace_id, StatusCode
from ..core.pagination import REPORT_SCAN_LIMIT
from ..core.security import get_current_user
from ..core.supabase_client import get_supabase, async_execute
from ..services.sichuan_qc_service import SichuanQCService

logger = logging.getLogger(__name__)

# naive in-memory cache for summary
_QC_SUMMARY_CACHE: Dict[str, Any] | None = None
_QC_SUMMARY_CACHE_TS: float = 0.0
_QC_SUMMARY_TTL_SECONDS = 10.0
_QC_EXPORT_TTL = timedelta(hours=1)
# 质控导出含病历统计信息，只能由受认证端点读取，不能放入静态目录。
_QC_EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "runtime" / "qc_exports"


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _export_owner(current_user: Dict[str, Any]) -> str:
    for key in ("id", "user_id", "email", "username"):
        value = str(current_user.get(key) or "").strip()
        if value and value != "anonymous":
            return value
    raise HTTPException(status_code=403, detail="当前用户没有质控报表导出权限")


def _is_export_admin(current_user: Dict[str, Any]) -> bool:
    roles = {str(role).strip().lower() for role in current_user.get("roles", []) if str(role).strip()}
    single_role = str(current_user.get("role") or "").strip().lower()
    if single_role:
        roles.add(single_role)
    return bool(roles.intersection({"admin", "super_admin"}))


def _export_paths(export_id: str) -> tuple[Path, Path]:
    try:
        normalized_id = UUID(str(export_id)).hex
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid export id") from exc
    return (
        _QC_EXPORT_DIR / f"{normalized_id}.csv",
        _QC_EXPORT_DIR / f"{normalized_id}.json",
    )


def _metadata_expired(metadata: Dict[str, Any], *, now: datetime) -> bool:
    raw_expires_at = metadata.get("expires_at")
    if not isinstance(raw_expires_at, str):
        return True
    try:
        expires_at = datetime.fromisoformat(raw_expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def _delete_export_files(csv_path: Path, metadata_path: Path) -> None:
    for path in (csv_path, metadata_path):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            logger.warning("[reports] 无法删除过期质控导出文件: %s", path)


def _read_export_artifact(path: Path) -> bytes:
    """只从私有导出目录读取稳定的普通文件，不跟随链接或重解析入口。"""

    file_stat = path.lstat()
    if path.is_symlink() or (
        getattr(file_stat, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise FileNotFoundError(path)
    if not stat.S_ISREG(file_stat.st_mode) or path.resolve().parent != _QC_EXPORT_DIR.resolve():
        raise FileNotFoundError(path)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened_stat = os.fstat(descriptor)
        current_stat = path.lstat()
        if path.is_symlink() or (
            getattr(current_stat, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise FileNotFoundError(path)
        if (opened_stat.st_dev, opened_stat.st_ino) != (
            current_stat.st_dev,
            current_stat.st_ino,
        ):
            raise FileNotFoundError(path)
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            return handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _path_is_stale(path: Path, *, stale_before: float) -> bool:
    try:
        return path.stat().st_mtime <= stale_before
    except FileNotFoundError:
        return False
    except OSError:
        logger.warning("[reports] 无法检查质控导出文件更新时间: %s", path)
        return False


def _cleanup_expired_exports(*, now: datetime | None = None) -> None:
    current_time = now or datetime.now(timezone.utc)
    _QC_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stale_before = current_time.timestamp() - _QC_EXPORT_TTL.total_seconds()
    for metadata_path in _QC_EXPORT_DIR.glob("*.json"):
        try:
            csv_path, expected_metadata_path = _export_paths(metadata_path.stem)
            if expected_metadata_path != metadata_path:
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            expired = not isinstance(metadata, dict) or _metadata_expired(metadata, now=current_time)
        except FileNotFoundError:
            # glob 后文件可能已被另一个清理者删除。
            continue
        except (OSError, ValueError, json.JSONDecodeError):
            csv_path = _QC_EXPORT_DIR / f"{metadata_path.stem}.csv"
            expired = _path_is_stale(metadata_path, stale_before=stale_before)
        if expired:
            _delete_export_files(csv_path, metadata_path)

    # CSV 先写入、metadata 后写入。只回收超过 TTL 且没有 metadata 的文件，
    # 让正在创建的导出在一个 TTL 内不受并发清理影响。
    for csv_path in _QC_EXPORT_DIR.glob("*.csv"):
        try:
            expected_csv_path, metadata_path = _export_paths(csv_path.stem)
        except ValueError:
            continue
        if expected_csv_path != csv_path or metadata_path.exists():
            continue
        if _path_is_stale(csv_path, stale_before=stale_before):
            _delete_export_files(csv_path, metadata_path)


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
async def qc_export(
    request: Request,
    payload: ExportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """导出质控汇总（CSV）。

    - 数据来源：`qc_statistics_view`（若 Supabase 可用），否则返回 503。
    - 导出文件保存在私有运行目录；仅创建者或管理员可通过受认证下载端点读取。
    - 文件自创建起保留一小时，下一次导出或下载时清理过期文件。
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

    _cleanup_expired_exports()
    export_id = uuid4().hex
    file_path, metadata_path = _export_paths(export_id)
    owner = _export_owner(current_user)

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

    created_at = datetime.now(timezone.utc)
    try:
        metadata_path.write_text(
            json.dumps(
                {
                    "export_id": export_id,
                    "owner": owner,
                    "created_at": created_at.isoformat(),
                    "expires_at": (created_at + _QC_EXPORT_TTL).isoformat(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        _delete_export_files(file_path, metadata_path)
        raise

    download_url = f"/api/v1/reports/qc/export/{export_id}/download"
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
        current_user=current_user,
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


@router.get("/qc/export/{export_id}/download")
async def download_qc_export(
    export_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """下载私有质控汇总 CSV。"""
    _cleanup_expired_exports()
    try:
        file_path, metadata_path = _export_paths(export_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="未找到质控导出文件") from None

    try:
        metadata = json.loads(_read_export_artifact(metadata_path))
    except (OSError, json.JSONDecodeError, UnicodeError):
        raise HTTPException(status_code=404, detail="未找到质控导出文件") from None
    if not isinstance(metadata, dict) or _metadata_expired(metadata, now=datetime.now(timezone.utc)):
        _delete_export_files(file_path, metadata_path)
        raise HTTPException(status_code=404, detail="质控导出文件已过期")

    owner = _export_owner(current_user)
    if owner != metadata.get("owner") and not _is_export_admin(current_user):
        raise HTTPException(status_code=403, detail="无权下载其他用户生成的质控报表")

    try:
        file_content = _read_export_artifact(file_path)
    except OSError:
        raise HTTPException(status_code=404, detail="未找到质控导出文件") from None

    audit_event(
        request,
        action="reports.qc.export.download",
        resource=f"/api/v1/reports/qc/export/{export_id}/download",
        outcome="success",
        details={"export_id": export_id},
        current_user=current_user,
    )
    return Response(
        content=file_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="qc_summary_{export_id}.csv"',
        },
    )
