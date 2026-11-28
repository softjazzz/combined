from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
import logging
from typing import Any, Dict, Iterable, List, Optional, Set
import time
import csv
import json
import os
import stat
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect, text
from uuid import UUID, uuid4

from ..core.audit import audit_event
from ..core.export_safety import sanitize_spreadsheet_cell
from ..core.response import success_response, get_trace_id, StatusCode
from ..core.pagination import REPORT_SCAN_LIMIT
from ..core.roles import effective_persistent_roles as _effective_persistent_roles
from ..core.security import get_current_user
from ..core.supabase_client import get_supabase, async_execute
from ..database import connection as db_connection
from ..database.schema_introspection import get_table_columns as _table_columns
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    configured_search_path,
    resolve_user_owner_schema,
)

logger = logging.getLogger(__name__)

# 按作用域隔离的短期内存缓存（全局 vs 各机构独立缓存，避免跨院区串读）
_QC_SUMMARY_CACHE: Dict[str, Dict[str, Any]] | None = None
_QC_SUMMARY_CACHE_TS: float = 0.0
_QC_SUMMARY_TTL_SECONDS = 10.0
_QC_EXPORT_TTL = timedelta(hours=1)
# 质控导出含病历统计信息，只能由受认证端点读取，不能放入静态目录。
_QC_EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "runtime" / "qc_exports"

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_REPORT_READ_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_REPORT_EXPORT_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _table_has_column(table_name: str, column_name: str) -> bool:
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return False
    try:
        with session_factory() as session:
            return column_name in _table_columns(session, table_name)
    except Exception:
        return False


def _resolve_report_actor(
    current_user: Dict[str, Any],
    *,
    allowed_roles: Iterable[str],
    denied_detail: str = "当前用户没有质控报表访问权限",
) -> Dict[str, Any]:
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id or actor_id == "anonymous":
        raise HTTPException(status_code=403, detail="缺少可信账号身份")

    session_factory = db_connection.SessionLocal
    if session_factory is None:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用")

    try:
        with session_factory() as session:
            owner_schema = resolve_user_owner_schema(session)
            inspector = sa_inspect(session.connection())
            if not inspector.has_table("sys_users", schema=owner_schema):
                raise HTTPException(status_code=503, detail="账号持久表不可用")
            user_cols = {
                col["name"]
                for col in inspector.get_columns("sys_users", schema=owner_schema)
            }
            has_institute = "institute_id" in user_cols
            table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
            select_cols = (
                "id, display_name, role, roles_json, is_active, department"
                + (", institute_id" if has_institute else "")
            )
            row = (
                session.execute(
                    text(f"SELECT {select_cols} FROM {table_ref} WHERE id = :uid"),
                    {"uid": actor_id},
                )
                .mappings()
                .one_or_none()
            )
    except HTTPException:
        raise
    except UserOwnerUnavailable:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None
    except Exception:
        logger.error("reports_actor_lookup_failed", exc_info=True)
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None

    if row is None or not bool(row.get("is_active")):
        raise HTTPException(status_code=403, detail="账号不可用")

    roles = _effective_persistent_roles(row.get("role"), row.get("roles_json"))
    if not roles:
        raise HTTPException(status_code=403, detail="账号缺少可信持久角色")

    if not (roles & set(allowed_roles)):
        raise HTTPException(status_code=403, detail=denied_detail)

    is_global = bool(roles & _GLOBAL_ROLES)
    institute_id = row.get("institute_id") if has_institute else None
    if not is_global:
        if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
            raise HTTPException(status_code=403, detail="账号缺少可信机构范围")
    else:
        institute_id = None

    return {
        "id": str(row["id"]),
        "roles": roles,
        "is_global": is_global,
        "institute_id": institute_id,
    }


def _resolve_table_ref(session, table_name: str) -> Optional[tuple[str, Set[str]]]:
    bind = session.get_bind()
    inspector = sa_inspect(bind)
    if bind.dialect.name != "postgresql":
        if not inspector.has_table(table_name):
            return None
        cols = {col["name"] for col in inspector.get_columns(table_name)}
        return f'"{table_name}"', cols

    schemas = list(dict.fromkeys([*configured_search_path(), "cdm", "qc", "public", "sys"]))
    for schema in schemas:
        if inspector.has_table(table_name, schema=schema):
            cols = {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
            return f'"{schema}"."{table_name}"', cols
    return None


def _load_institute_record_ids(institute_id: str) -> Set[str]:
    """查询持久化归属于指定院区的病历/就诊标识集合（失败关闭返回空集合）。"""
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return set()

    allowed: Set[str] = set()
    try:
        with session_factory() as session:
            table_specs = (
                ("medical_records", ("id", "record_id", "visit_id")),
                ("medical_record_frontpages", ("visit_id", "record_id")),
                ("medical_documents", ("record_id",)),
            )
            for table_name, id_cols in table_specs:
                resolved = _resolve_table_ref(session, table_name)
                if resolved is None:
                    continue
                table_ref, cols = resolved
                if "institute_id" not in cols:
                    continue
                present_ids = [col for col in id_cols if col in cols]
                if not present_ids:
                    continue
                select_sql = ", ".join(f'"{col}"' for col in present_ids)
                rows = (
                    session.execute(
                        text(f"SELECT {select_sql} FROM {table_ref} WHERE institute_id = :inst"),
                        {"inst": institute_id},
                    )
                    .mappings()
                    .all()
                )
                for row in rows:
                    for col in present_ids:
                        val = str(row.get(col) or "").strip()
                        if val:
                            allowed.add(val)
    except Exception:
        logger.warning("reports_institute_record_lookup_failed", exc_info=True)
        return set()
    return allowed


def _filter_rows_by_actor_institute(
    rows: List[Dict[str, Any]],
    actor: Dict[str, Any],
    *,
    allowed_record_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if actor["is_global"]:
        return rows
    inst = actor["institute_id"]
    resolved_ids = allowed_record_ids
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if "institute_id" in row:
            row_inst = row.get("institute_id")
            if isinstance(row_inst, str) and row_inst.strip() == inst:
                filtered.append(row)
            continue
        rid = str(row.get("record_id") or "").strip()
        if not rid:
            continue
        if resolved_ids is None:
            resolved_ids = _load_institute_record_ids(inst)
        if rid in resolved_ids:
            filtered.append(row)
    return filtered


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
        if not stat.S_ISREG(opened_stat.st_mode):
            raise FileNotFoundError(path)

        initial_identity = (file_stat.st_dev, file_stat.st_ino)
        opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
        current_identity = (current_stat.st_dev, current_stat.st_ino)
        # 初始目录项、实际打开的描述符和打开后的目录项必须指向同一文件。
        # 否则攻击者可在首次 lstat 与 os.open 之间把普通文件替换为另一个普通文件。
        if initial_identity != opened_identity or opened_identity != current_identity:
            raise FileNotFoundError(path)
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            return handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _path_is_stale(path: Path, *, stale_before: float) -> bool:
    try:
        return path.lstat().st_mtime <= stale_before
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
            metadata = json.loads(_read_export_artifact(metadata_path))
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


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _normalize_utc(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return _normalize_utc(parsed)
        except ValueError:
            return None
    return None


def _calculate_pass_rate(passed: int, warning: int, failed: int, pending: int) -> float:
    total = passed + warning + failed + pending
    if total <= 0:
        return 0.0
    return round((passed / total) * 100, 1)


def _get_runtime_avg_api_time() -> float:
    """读取运行期已初始化服务的平均接口耗时，不新建 SichuanQCService 实例。"""
    try:
        from . import qc_sichuan

        active_service = getattr(qc_sichuan, "service", None)
        if active_service is not None and hasattr(active_service, "stats"):
            stats = active_service.stats() or {}
            return float(stats.get("avg_api_time", 0.0) or 0.0)
    except Exception:
        pass
    return 0.0


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


def _build_trend_buckets(period: str, *, now: datetime | None = None) -> List[datetime]:
    base = _normalize_utc(now or datetime.now(timezone.utc)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if period == "week":
        return [base - timedelta(days=offset) for offset in range(6, -1, -1)]
    if period == "month":
        return [base - timedelta(days=offset) for offset in range(29, -1, -1)]
    month_starts: List[datetime] = []
    cursor = base.replace(day=1)
    for _ in range(3):
        month_starts.append(cursor)
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    return list(reversed(month_starts))


def _resolve_trend_bucket(period: str, analyzed_at: datetime) -> datetime:
    analyzed_day = _normalize_utc(analyzed_at).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if period == "quarter":
        return analyzed_day.replace(day=1)
    return analyzed_day


async def _fetch_top_categories(
    sb,
    actor: Dict[str, Any],
    *,
    allowed_record_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    try:
        if actor["is_global"]:
            query = sb.table("qc_defects").select("category").limit(REPORT_SCAN_LIMIT)
        elif _table_has_column("qc_defects", "institute_id"):
            query = (
                sb.table("qc_defects")
                .select("category,institute_id")
                .eq("institute_id", actor["institute_id"])
                .limit(REPORT_SCAN_LIMIT)
            )
        else:
            query = sb.table("qc_defects").select("category,record_id").limit(REPORT_SCAN_LIMIT)
        defect_rows = await async_execute(query)
    except Exception as exc:
        logger.warning(f"[reports] 查询 qc_defects 失败: {exc}")
        return []

    rows = _filter_rows_by_actor_institute(
        list(defect_rows.data or []),
        actor,
        allowed_record_ids=allowed_record_ids,
    )
    counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        category = (row.get("category") or "未分类").strip() if isinstance(row.get("category"), str) else "未分类"
        counts[category or "未分类"] += 1

    return [
        {"category": category, "issue_count": count}
        for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]
    ]


async def _fetch_trend_data(sb, period: str, actor: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = sb.table("qc_statistics_view").select(
        "record_id,passed_count,warning_count,failed_count,pending_count,avg_qc_score,last_analyzed_time"
    )
    if not actor["is_global"] and _table_has_column("qc_statistics_view", "institute_id"):
        query = sb.table("qc_statistics_view").select(
            "record_id,institute_id,passed_count,warning_count,failed_count,pending_count,avg_qc_score,last_analyzed_time"
        ).eq("institute_id", actor["institute_id"])
    trend_rows = await async_execute(query.limit(REPORT_SCAN_LIMIT))
    rows = _filter_rows_by_actor_institute(list(trend_rows.data or []), actor)

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
async def qc_summary(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """质控看板汇总（真实聚合 + 角色与持久院区隔离）。

    - 从视图 `qc_statistics_view` 聚合：按病历维度统计文书总数、通过/告警/失败数量、平均分、最近分析时间。
    - `pass_rate` 与 `/qc/trend` 保持一致，由聚合通过/告警/失败/待检数量实时计算，不再从新建空服务实例读取。
    - 保留按院区作用域隔离的 10s 内存缓存以降低数据库压力。
    """
    global _QC_SUMMARY_CACHE, _QC_SUMMARY_CACHE_TS
    actor = _resolve_report_actor(
        current_user,
        allowed_roles=_REPORT_READ_ROLES,
        denied_detail="当前角色无权查看质控汇总报表",
    )
    scope_key = "__global__" if actor["is_global"] else f"inst:{actor['institute_id']}"
    now = time.time()
    if (
        isinstance(_QC_SUMMARY_CACHE, dict)
        and _QC_SUMMARY_CACHE_TS > 0.0
        and scope_key in _QC_SUMMARY_CACHE
    ):
        entry = _QC_SUMMARY_CACHE[scope_key]
        if isinstance(entry, dict) and (now - float(entry.get("ts", 0.0))) < _QC_SUMMARY_TTL_SECONDS:
            return success_response(data=entry["data"], trace_id=get_trace_id(request))

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
    allowed_record_ids: Optional[Set[str]] = (
        None if actor["is_global"] else _load_institute_record_ids(actor["institute_id"])
    )

    if sb is not None:
        try:
            view_query = sb.table("qc_statistics_view").select("*")
            if not actor["is_global"] and _table_has_column("qc_statistics_view", "institute_id"):
                view_query = view_query.eq("institute_id", actor["institute_id"])
            view_rows = await async_execute(view_query.limit(REPORT_SCAN_LIMIT))
            rows = _filter_rows_by_actor_institute(
                list(view_rows.data or []),
                actor,
                allowed_record_ids=allowed_record_ids,
            )
            total_records = len(rows)
            if rows:
                for r in rows:
                    totals["executions"] += int(r.get("total_documents", 0) or 0)
                    totals["passed"] += int(r.get("passed_count", 0) or 0)
                    totals["warning"] += int(r.get("warning_count", 0) or 0)
                    totals["failed"] += int(r.get("failed_count", 0) or 0)
                    totals["pending"] += int(r.get("pending_count", 0) or 0)
                avg_list = [float(r.get("avg_qc_score", 0) or 0) for r in rows if r.get("avg_qc_score") is not None]
                if avg_list:
                    totals["avg_qc_score"] = sum(avg_list) / len(avg_list)
        except Exception as e:
            logger.warning(f"[reports] 查询 qc_statistics_view 失败: {e}")

        try:
            rr = await async_execute(sb.table("qc_rules").select("*").eq("is_active", True).limit(REPORT_SCAN_LIMIT))
            rule_rows = list(rr.data or [])
            if not actor["is_global"]:
                rule_rows = [
                    row for row in rule_rows
                    if not row.get("institute_id")
                    or str(row.get("institute_id")).strip() == actor["institute_id"]
                ]
            active_rules = len(rule_rows)
        except Exception as e:
            logger.warning(f"[reports] 查询 qc_rules 失败: {e}")

        top_categories = await _fetch_top_categories(
            sb,
            actor,
            allowed_record_ids=allowed_record_ids,
        )
    else:
        top_categories = []

    pass_rate = _calculate_pass_rate(
        totals["passed"],
        totals["warning"],
        totals["failed"],
        totals["pending"],
    )

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "kpis": {
            "total_records": total_records,
            "active_rules": active_rules,
            "qc_executions": totals["executions"],
            "pass_rate": pass_rate,
            "avg_api_time": _get_runtime_avg_api_time(),
            "avg_qc_score": round(totals["avg_qc_score"], 2),
            "passed": totals["passed"],
            "warning": totals["warning"],
            "failed": totals["failed"],
            "pending": totals["pending"],
        },
        "top_categories": top_categories,
    }
    if not isinstance(_QC_SUMMARY_CACHE, dict) or _QC_SUMMARY_CACHE_TS == 0.0:
        _QC_SUMMARY_CACHE = {}
    _QC_SUMMARY_CACHE[scope_key] = {"ts": now, "data": data}
    _QC_SUMMARY_CACHE_TS = now
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/qc/trend")
async def qc_trend(
    request: Request,
    period: str = Query("month", description="时间段: week | month | quarter"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    actor = _resolve_report_actor(
        current_user,
        allowed_roles=_REPORT_READ_ROLES,
        denied_detail="当前角色无权查看质控趋势报表",
    )
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
        items = await _fetch_trend_data(sb, period, actor)
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
    - 仅限质控管理员或系统管理员导出，非全局角色按持久院区隔离。
    - 导出单元格统一做公式注入安全转义。
    - 导出文件保存在私有运行目录；仅创建者或全局管理员可通过受认证下载端点读取。
    - 文件自创建起保留一小时，下一次导出或下载时清理过期文件。
    """
    actor = _resolve_report_actor(
        current_user,
        allowed_roles=_REPORT_EXPORT_ROLES,
        denied_detail="仅质控管理员或系统管理员可导出质控汇总报表",
    )

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=StatusCode.SERVICE_UNAVAILABLE, detail="supabase unavailable")

    q = sb.table("qc_statistics_view").select("*").limit(REPORT_SCAN_LIMIT)
    if not actor["is_global"] and _table_has_column("qc_statistics_view", "institute_id"):
        q = q.eq("institute_id", actor["institute_id"])
    if payload.record_ids:
        q = q.in_("record_id", payload.record_ids)
    resp = await async_execute(q)
    rows: List[Dict[str, Any]] = _filter_rows_by_actor_institute(
        list(resp.data or []),
        actor,
    )

    _cleanup_expired_exports()
    export_id = uuid4().hex
    file_path, metadata_path = _export_paths(export_id)
    owner = actor["id"]

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
            writer.writerow({k: sanitize_spreadsheet_cell(r.get(k)) for k in headers})

    created_at = datetime.now(timezone.utc)
    try:
        metadata_path.write_text(
            json.dumps(
                {
                    "export_id": export_id,
                    "owner": owner,
                    "institute_id": actor["institute_id"],
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
            "institute_scope": actor["institute_id"],
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
        trace_id=get_trace_id(request),
    )


@router.get("/qc/export/{export_id}/download")
async def download_qc_export(
    export_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """下载私有质控汇总 CSV。"""
    actor = _resolve_report_actor(
        current_user,
        allowed_roles=_REPORT_EXPORT_ROLES,
        denied_detail="无权下载质控汇总报表",
    )

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

    if not actor["is_global"]:
        meta_inst = metadata.get("institute_id")
        if actor["id"] != metadata.get("owner") or (
            meta_inst is not None and meta_inst != actor["institute_id"]
        ):
            raise HTTPException(status_code=403, detail="无权下载其他用户或机构生成的质控报表")

    try:
        file_content = _read_export_artifact(file_path)
    except OSError:
        raise HTTPException(status_code=404, detail="未找到质控导出文件") from None

    audit_event(
        request,
        action="reports.qc.export.download",
        resource=f"/api/v1/reports/qc/export/{export_id}/download",
        outcome="success",
        details={"export_id": export_id, "institute_scope": actor["institute_id"]},
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
