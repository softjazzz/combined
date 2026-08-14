"""
数据同步 API 路由（V4）

统一归口：
- /api/v1/sync/config/pg
- /api/v1/sync/status
- /api/v1/sync/statistics
- /api/v1/sync/test-connection/*
- /api/v1/sync/preflight
- /api/v1/sync/trigger
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError as SAOperationalError
from starlette.concurrency import run_in_threadpool

try:
    from psycopg2 import OperationalError as PGOperationalError
except Exception:  # pragma: no cover - 防御性兜底
    PGOperationalError = tuple()  # type: ignore[assignment]

from ..core.audit import audit_event
from ..core.security import get_current_user
from ..core.rate_limit import enforce_rate_limit
from ..core.response import success_response, get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["data-sync"])


def _ok(request: Request, data: dict | list | str | int | float | bool | None, message: str | None = None):
    return success_response(data=data, message=message, trace_id=get_trace_id(request))


def _err(request: Request, error: str, code: str, data: dict | None = None):
    payload = {
        "success": False,
        "error": error,
        "code": code,
        "trace_id": get_trace_id(request),
    }
    if data is not None:
        payload["data"] = data
    return payload


def _extract_roles(current_user: dict) -> set[str]:
    roles = current_user.get("roles")
    if isinstance(roles, list):
        return {str(role) for role in roles}
    role = current_user.get("role")
    if role:
        return {str(role)}
    return set()


def require_sync_read_access(current_user: dict = Depends(get_current_user)) -> dict:
    roles = _extract_roles(current_user)
    if not roles.intersection({"admin", "qc_manager", "sync_admin", "super_admin"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="数据同步读取权限不足（仅 admin / qc_manager / sync_admin / super_admin 可访问）",
        )
    return current_user


def require_sync_write_access(current_user: dict = Depends(get_current_user)) -> dict:
    roles = _extract_roles(current_user)
    if not roles.intersection({"admin", "sync_admin", "super_admin"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="数据同步写入权限不足（仅 admin / sync_admin / super_admin 可操作）",
        )
    return current_user


def _mask_pg_config(raw: dict) -> dict:
    data = dict(raw)
    password = str(data.get("remote_password") or "")
    data.pop("remote_password", None)
    data["remote_password_set"] = bool(password)
    data["remote_password_display"] = "***" if password else ""
    data["remote_password_ref"] = str(data.get("remote_password_ref") or "")
    data["remote_schema"] = str(data.get("remote_schema") or "public")
    raw_institute_id = str(data.get("default_institute_id") or "").strip()
    institute_configured = bool(raw_institute_id) and (
        raw_institute_id.upper() != "LOCAL-HOSPITAL"
    )
    data["default_institute_id"] = raw_institute_id if institute_configured else ""
    data["default_institute_configured"] = institute_configured
    data["sync_mode"] = str(data.get("sync_mode") or "table")
    return data


class TriggerRequest(BaseModel):
    source: Literal["pg"] = "pg"
    sync_date: Optional[str] = None
    tier: Literal["all"] = "all"
    tables: Optional[list[str]] = None
    scene: Optional[Literal["running", "final", "frontpage", "coding", "settlement", "both"]] = "both"
    date_window: Optional[dict[str, str]] = None
    target_departments: Optional[list[str]] = None
    policy_version: Optional[str] = Field(default=None, max_length=128)
    table_groups: Optional[list[str]] = None
    preflight_fingerprint: Optional[str] = Field(default=None, max_length=96)


class PgConfigUpdate(BaseModel):
    remote_host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    remote_port: Optional[int] = Field(default=None, ge=1, le=65535)
    remote_database: Optional[str] = Field(default=None, min_length=1, max_length=128)
    remote_username: Optional[str] = Field(default=None, min_length=1, max_length=128)
    remote_password_ref: Optional[str] = Field(default=None, max_length=128)
    remote_password: Optional[str] = Field(default=None, max_length=256)
    remote_schema: Optional[str] = Field(default=None, min_length=1, max_length=128)
    default_institute_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    sync_mode: Optional[Literal["table", "procedure"]] = None


class SyncPolicyScheduleUpdate(BaseModel):
    mode: Optional[Literal["interval", "cron"]] = "interval"
    minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class SyncPolicyNightWindowUpdate(BaseModel):
    start: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class SyncPolicyUpdate(BaseModel):
    scope: Optional[Literal["running", "final", "frontpage", "coding", "settlement", "both"]] = None
    target_departments: Optional[list[str]] = None
    start_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    schedule: Optional[SyncPolicyScheduleUpdate] = None
    night_window: Optional[SyncPolicyNightWindowUpdate] = None
    mirror_delay_base_minutes: Optional[int] = Field(default=None, ge=0, le=720)
    keep_policy_version: Optional[bool] = False


class PreflightRequest(BaseModel):
    source: Literal["pg"] = "pg"
    tier: Literal["all"] = "all"
    tables: Optional[list[str]] = None
    scene: Optional[Literal["running", "final", "frontpage", "coding", "settlement", "both"]] = "both"
    date_window: Optional[dict[str, str]] = None
    target_departments: Optional[list[str]] = None
    policy_version: Optional[str] = Field(default=None, max_length=128)
    table_groups: Optional[list[str]] = None


class PgSyncTableConfigItem(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source_table: Optional[str] = Field(default=None, min_length=1, max_length=128)
    date_field: Optional[str] = Field(default=None, min_length=1, max_length=128)
    fallback_date_field: Optional[str] = Field(default=None, max_length=128)
    enabled: Optional[bool] = None


class PgSyncTablesUpdate(BaseModel):
    items: list[PgSyncTableConfigItem] = Field(default_factory=list)


class SyncTemplateApplyRequest(BaseModel):
    template_id: Literal["hospital_standard", "single_department_focus", "multi_department_joint", "night_low_impact"]
    departments: Optional[list[str]] = None


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _infer_trigger_status(source: str, result: dict) -> str:
    if source == "pg":
        explicit_status = str(result.get("status") or "").strip().lower()
        if explicit_status in {"success", "partial", "failed", "rejected"}:
            return explicit_status
        table_rows = result.get("tables")
        if isinstance(table_rows, list) and table_rows:
            has_success = any(str(item.get("status")) == "success" for item in table_rows if isinstance(item, dict))
            has_failed = any(str(item.get("status")) == "failed" for item in table_rows if isinstance(item, dict))
            if has_success and has_failed:
                return "partial"
        return "success" if bool(result.get("success")) else "failed"

    if not bool(result.get("success")):
        return "failed"
    tier_results = result.get("results")
    if isinstance(tier_results, dict):
        has_error = False
        has_synced = False
        for value in tier_results.values():
            if not isinstance(value, dict):
                continue
            if value.get("error"):
                has_error = True
            if int(value.get("synced") or 0) > 0:
                has_synced = True
        if has_error and has_synced:
            return "partial"
        if has_error and not has_synced:
            return "failed"
    return "success"


def _infer_total_records(source: str, result: dict) -> int:
    if source == "pg":
        return int(result.get("total_records") or 0)
    tier_results = result.get("results")
    if not isinstance(tier_results, dict):
        return 0
    total = 0
    for value in tier_results.values():
        if isinstance(value, dict):
            total += int(value.get("synced") or 0)
    return total


def _is_rejected_running(result: dict) -> bool:
    if not isinstance(result, dict):
        return False
    if bool(result.get("success")):
        return False
    message = str(result.get("error") or result.get("message") or "")
    return "同步正在进行中" in message


def _resolve_effective_sync_date(source: str, sync_date: Optional[str]) -> str:
    if sync_date:
        return sync_date
    if source == "pg":
        return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).date().isoformat()


def _build_idempotency_key(
    *,
    source: str,
    tier: str,
    sync_date: str,
    operator: str,
    scene: str = "",
    date_window: Optional[dict[str, str]] = None,
    target_departments: Optional[list[str]] = None,
    tables: Optional[list[str]] = None,
    table_groups: Optional[list[str]] = None,
    policy_version: str = "",
) -> str:
    fingerprint_payload = {
        "source": source,
        "tier": tier,
        "sync_date": sync_date,
        "scene": scene,
        "date_window": date_window or {},
        "target_departments": sorted([str(item) for item in (target_departments or []) if str(item).strip()]),
        "tables": sorted([str(item) for item in (tables or []) if str(item).strip()]),
        "table_groups": sorted([str(item) for item in (table_groups or []) if str(item).strip()]),
        "policy_version": str(policy_version or ""),
        "operator": operator,
    }
    payload = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{source}:{tier}:{sync_date}:{operator}:{digest}"


def _build_preflight_fingerprint(
    *,
    source: str,
    tier: str,
    scene: str = "",
    date_window: Optional[dict[str, str]] = None,
    target_departments: Optional[list[str]] = None,
    tables: Optional[list[str]] = None,
    table_groups: Optional[list[str]] = None,
    policy_version: str = "",
) -> str:
    fingerprint_payload = {
        "source": source,
        "tier": tier,
        "scene": scene,
        "date_window": date_window or {},
        "target_departments": sorted([str(item) for item in (target_departments or []) if str(item).strip()]),
        "tables": sorted([str(item) for item in (tables or []) if str(item).strip()]),
        "table_groups": sorted([str(item) for item in (table_groups or []) if str(item).strip()]),
        "policy_version": str(policy_version or ""),
    }
    payload = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_selected_tables(
    tables: Optional[list[str]],
    table_groups: Optional[list[str]],
) -> tuple[Optional[list[str]], list[str]]:
    direct_tables = [str(item or "").strip() for item in (tables or []) if str(item or "").strip()]
    selected: list[str] = []
    seen: set[str] = set()

    for item in direct_tables:
        if item in seen:
            continue
        seen.add(item)
        selected.append(item)

    missing_groups: list[str] = []
    if table_groups:
        from ..services.etl_sync import expand_table_groups

        group_tables, missing_groups = expand_table_groups(table_groups)
        for item in group_tables:
            key = str(item or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            selected.append(key)

    return (selected or None), missing_groups


def _normalize_date_window_payload(raw: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    start = str(raw.get("start") or raw.get("start_date") or "").strip()
    end = str(raw.get("end") or raw.get("end_date") or "").strip()
    if not start and not end:
        return None
    return {
        "start": start or None,
        "end": end or None,
    }


def _normalize_target_departments(values: Optional[list[str]]) -> Optional[list[str]]:
    if not values:
        return None
    cleaned = [str(item or "").strip() for item in values if str(item or "").strip()]
    if not cleaned:
        return None
    dedup = list(dict.fromkeys(cleaned))
    if len(dedup) == 1 and dedup[0] == "*":
        return ["*"]
    if "*" in dedup:
        dedup = [item for item in dedup if item != "*"]
    return dedup or None


def _raise_mapped_service_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    message = str(exc) or "请求处理失败"
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
    if isinstance(exc, SAOperationalError) or (
        PGOperationalError and isinstance(exc, PGOperationalError)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"数据源连接不可用：{message}",
        )
    raise exc


# ==================== 状态查询 ====================

@router.get("/status")
async def get_sync_status(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取同步状态（仅 PG）"""
    try:
        from ..services.etl_sync import get_sync_state

        return _ok(request, {
            "pg_sync": get_sync_state(),
        })
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.get("/statistics")
async def get_statistics(request: Request, _: dict = Depends(require_sync_read_access)):
    """同步统计（PG 口径，保留旧字段形状）"""
    try:
        from ..services.etl_sync import get_sync_state

        sync_state = get_sync_state()
        is_running = bool(sync_state.get("is_running"))
        logs = sync_state.get("logs") if isinstance(sync_state.get("logs"), list) else []
        failed = sum(1 for item in logs if isinstance(item, dict) and str(item.get("status")) == "failed")
        partial = 1 if str(sync_state.get("last_sync_status")) == "partial" else 0
        pending = 1 if is_running else 0
        return _ok(
            request,
            {
                "PENDING": pending,
                "PARTIAL": partial,
                "SYNCED": int(sync_state.get("total_records_synced") or 0),
                "STALE": 0,
                "FAILED": failed,
            },
        )
    except Exception as exc:
        _raise_mapped_service_error(exc)


# ==================== PG 配置 ====================

@router.get("/config/pg")
async def get_pg_config(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 PG 同步配置（密码脱敏）"""
    try:
        from ..services.etl_sync import load_db_config

        config = load_db_config()
        return _ok(request, _mask_pg_config(config))
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.put("/config/pg")
async def update_pg_config(
    request: Request,
    update: PgConfigUpdate,
    current_user: dict = Depends(require_sync_write_access),
):
    """更新 PG 同步配置（仅 admin）"""
    try:
        from ..services.etl_sync import load_db_config, save_db_config, test_remote_connection

        current = load_db_config()
        incoming = update.model_dump(exclude_none=True)

        if "remote_port" in incoming:
            incoming["remote_port"] = str(incoming["remote_port"])

        remote_password = incoming.get("remote_password")
        if remote_password is not None and remote_password == "":
            incoming.pop("remote_password", None)
            remote_password = None

        merged = {**current, **incoming}
        institute_id = str(merged.get("default_institute_id") or "").strip()
        if not institute_id or institute_id.upper() == "LOCAL-HOSPITAL":
            raise ValueError("请填写本院长期稳定的机构标识，不能使用系统占位值")
        merged["default_institute_id"] = institute_id
        save_db_config(merged, runtime_password=remote_password)
        conn_result = test_remote_connection()
        audit_event(
            request,
            action="sync.config.pg.update",
            resource="/api/v1/sync/config/pg",
            outcome="success" if bool(conn_result.get("connected")) else "degraded",
            current_user=current_user,
            details={
                "changed_fields": sorted(update.model_dump(exclude_none=True).keys()),
                "remote_host": merged.get("remote_host"),
                "remote_port": merged.get("remote_port"),
                "connection_ok": bool(conn_result.get("connected")),
            },
        )
        return _ok(
            request,
            {
                "config": _mask_pg_config(merged),
                "connection": conn_result,
            },
        )
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.get("/config/policy")
async def get_sync_policy(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 PG 抽取策略（scope/日期窗口/调度/夜间窗口）。"""
    try:
        from ..services.sync_policy import load_sync_policy

        policy = load_sync_policy()
        return _ok(request, policy)
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.put("/config/policy")
async def update_sync_policy(
    request: Request,
    update: SyncPolicyUpdate,
    current_user: dict = Depends(require_sync_write_access),
):
    """更新 PG 抽取策略（仅 admin）。"""
    try:
        from ..services.sync_policy import save_sync_policy

        payload = update.model_dump(exclude_none=True)
        keep_policy_version = bool(payload.pop("keep_policy_version", False))
        saved = save_sync_policy(payload, keep_policy_version=keep_policy_version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        _raise_mapped_service_error(exc)

    audit_event(
        request,
        action="sync.config.policy.update",
        resource="/api/v1/sync/config/policy",
        outcome="success",
        current_user=current_user,
        details={
            "changed_fields": sorted(update.model_dump(exclude_none=True).keys()),
            "scope": saved.get("scope"),
            "policy_version": saved.get("policy_version"),
        },
    )
    return _ok(request, saved)


@router.get("/config/pg/tables")
async def get_pg_sync_tables(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 PG 表直连同步配置（分阶段启用）"""
    try:
        from ..services.etl_sync import list_sync_tables

        items = list_sync_tables()
        return _ok(request, {"items": items, "total": len(items)})
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.get("/config/pg/table-groups")
async def get_pg_sync_table_groups(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 PG 同步表分组（核心8/扩展分组/全量56）。"""
    try:
        from ..services.etl_sync import list_sync_table_groups

        items = list_sync_table_groups()
        return _ok(request, {"items": items, "total": len(items)})
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.put("/config/pg/tables")
async def update_pg_sync_tables(
    request: Request,
    payload: PgSyncTablesUpdate,
    current_user: dict = Depends(require_sync_write_access),
):
    """更新 PG 表直连同步配置（仅 admin）"""
    try:
        from ..services.etl_sync import save_sync_tables_config

        updates = [item.model_dump(exclude_none=True) for item in payload.items]
        items = save_sync_tables_config(updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        _raise_mapped_service_error(exc)

    audit_event(
        request,
        action="sync.config.pg.tables.update",
        resource="/api/v1/sync/config/pg/tables",
        outcome="success",
        current_user=current_user,
        details={
            "changed_count": len(updates),
            "changed_tables": sorted([str(item.get("name")) for item in updates if item.get("name")])[:50],
        },
    )
    return _ok(request, {"items": items, "total": len(items)})


# ==================== 连接测试 ====================

@router.post("/test-connection/pg-remote")
async def test_pg_remote(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试远端 PG 连接（仅 admin）"""
    try:
        from ..services.etl_sync import test_remote_connection

        return _ok(request, test_remote_connection())
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.post("/test-connection/pg-local")
async def test_pg_local(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试本地 PG 连接（仅 admin）"""
    try:
        from ..services.etl_sync import test_local_connection

        return _ok(request, test_local_connection())
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.post("/test-connection/all")
async def test_all_connections(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试全连接（远端 PG + 本地 PG）"""
    try:
        from ..services.etl_sync import test_local_connection, test_remote_connection

        pg_remote = test_remote_connection()
        pg_local = test_local_connection()
        all_connected = bool(pg_remote.get("connected")) and bool(pg_local.get("connected"))
        connected_count = int(bool(pg_remote.get("connected"))) + int(bool(pg_local.get("connected")))
        return _ok(request, {
            "all_connected": all_connected,
            "connected_count": connected_count,
            "total_sources": 2,
            "pg_remote": pg_remote,
            "pg_local": pg_local,
        })
    except Exception as exc:
        _raise_mapped_service_error(exc)


@router.get("/departments")
async def get_departments(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取科室列表（仅源 PG 口径）。"""
    try:
        from ..services.etl_sync import list_remote_departments
        result = list_remote_departments(limit=500)
        items = list(result.get("items") or [])
        return _ok(
            request,
            {
                "items": items,
                "total": len(items),
                "source": "pg",
                "meta": {
                    "schema": result.get("schema"),
                    "source_table": result.get("source_table"),
                    "source_column": result.get("source_column"),
                },
            },
        )
    except Exception as exc:
        _raise_mapped_service_error(exc)


# ==================== 试运行预检 ====================

@router.post("/preflight")
async def run_preflight(
    request: Request,
    req: PreflightRequest,
    _: dict = Depends(require_sync_write_access),
):
    """
    试运行预检（不落库、不触发实际同步）
    """
    try:
        from ..services.etl_sync import (
            estimate_pg_sync_impact,
            test_local_connection,
            test_remote_connection,
            validate_pg_sync_plan,
        )

        local_result = test_local_connection()
        remote_result = test_remote_connection()
        blockers: list[str] = []
        warnings: list[str] = []

        if not local_result.get("connected"):
            blockers.append(f"本地 PG 未连通: {local_result.get('error', '未知错误')}")
        if not remote_result.get("connected"):
            blockers.append(f"远端 PG 未连通: {remote_result.get('error', '未知错误')}")

        if req.tables and len(req.tables) > 10:
            warnings.append("本次指定同步表数量较多，建议分批执行。")

        selected_tables, missing_groups = _resolve_selected_tables(req.tables, req.table_groups)
        if missing_groups:
            blockers.append(f"未知同步分组: {', '.join(missing_groups)}")

        execution_plan = validate_pg_sync_plan(tables=selected_tables, include_disabled=False)
        full_matrix_plan = validate_pg_sync_plan(tables=selected_tables, include_disabled=True)
        blockers.extend([str(item) for item in execution_plan.get("blockers", [])])
        warnings.extend([str(item) for item in execution_plan.get("warnings", [])])
        warnings.extend([str(item) for item in full_matrix_plan.get("warnings", [])])
        warnings = list(dict.fromkeys([w for w in warnings if str(w).strip()]))

        date_window_payload = _normalize_date_window_payload(req.date_window)
        target_departments = _normalize_target_departments(req.target_departments)
        policy_version = str(req.policy_version or "")
        scene = str(req.scene or "both")
        impact_meta: dict[str, object] = {
            "estimated_impact": 0,
            "estimate_basis": "eligible_visit_count",
            "date_window": date_window_payload or {},
            "target_departments": target_departments or ["*"],
        }
        if not blockers:
            try:
                impact_meta = estimate_pg_sync_impact(
                    scene=scene,
                    date_window=date_window_payload,
                    target_departments=target_departments,
                )
                warnings.extend(
                    str(item)
                    for item in (impact_meta.get("warnings") or [])
                    if str(item).strip()
                )
                if int(impact_meta.get("estimated_impact") or 0) <= 0:
                    blockers.append("当前日期范围和科室条件下未找到可同步病历，请调整范围或源库配置后重试")
                    warnings.append("候选病历数为 0，本次不会触发正式同步。")
            except Exception as exc:
                logger.warning(
                    "sync_preflight_scope_resolution_failed error_type=%s",
                    type(exc).__name__,
                )
                blockers.append("候选病历范围解析失败，请检查日期、科室和源库住院登记配置")
        preflight_fingerprint = _build_preflight_fingerprint(
            source=req.source,
            tier="all",
            scene=scene,
            date_window=date_window_payload,
            target_departments=target_departments,
            tables=selected_tables,
            table_groups=req.table_groups,
            policy_version=policy_version,
        )
        return _ok(request, {
            "source": "pg",
            "tier": "all",
            "mode": execution_plan.get("mode"),
            "remote_schema": execution_plan.get("remote_schema"),
            "executable": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "estimated_impact": int(impact_meta.get("estimated_impact") or 0),
            "estimate_basis": str(impact_meta.get("estimate_basis") or "eligible_visit_count"),
            "risk_level": "low" if len(blockers) == 0 else "high",
            "preflight_fingerprint": preflight_fingerprint,
            "matrix_scope": {
                "execution": execution_plan.get("matrix_scope", "enabled"),
                "full": full_matrix_plan.get("matrix_scope", "all"),
            },
            "table_validations": full_matrix_plan.get("table_validations", []),
            "target_tables": full_matrix_plan.get("target_tables", []),
            "execution_table_validations": execution_plan.get("table_validations", []),
            "execution_target_tables": execution_plan.get("target_tables", []),
            "scene": scene,
            "date_window": impact_meta.get("date_window") or date_window_payload or {},
            "target_departments": impact_meta.get("target_departments") or target_departments or ["*"],
            "policy_version": policy_version,
            "table_groups": req.table_groups or [],
            "connections": {
                "pg_remote": remote_result,
                "pg_local": local_result,
            },
        })
    except Exception as exc:
        _raise_mapped_service_error(exc)


# ==================== 触发同步 ====================

@router.post("/trigger")
async def trigger_sync(
    request: Request,
    req: TriggerRequest,
    current_user: dict = Depends(require_sync_write_access),
):
    """手动触发数据同步（仅 admin）"""
    enforce_rate_limit(
        request,
        bucket="sync_trigger",
        max_requests=5,
        window_seconds=60,
    )
    from ..services.sync_idempotency import complete_sync_trigger, reserve_sync_trigger

    effective_tier = "all"
    effective_sync_date = _resolve_effective_sync_date(req.source, req.sync_date)
    operator_email = str(current_user.get("email") or current_user.get("id") or "unknown").strip().lower()
    selected_tables, missing_groups = _resolve_selected_tables(req.tables, req.table_groups)
    if missing_groups:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"未知同步分组: {', '.join(missing_groups)}",
        )

    date_window_payload = _normalize_date_window_payload(req.date_window)
    target_departments = _normalize_target_departments(req.target_departments)
    policy_version = str(req.policy_version or "").strip()
    scene = str(req.scene or "both")
    expected_preflight_fingerprint = _build_preflight_fingerprint(
        source=req.source,
        tier=effective_tier,
        scene=scene,
        date_window=date_window_payload,
        target_departments=target_departments,
        tables=selected_tables,
        table_groups=req.table_groups,
        policy_version=policy_version,
    )
    supplied_preflight_fingerprint = str(req.preflight_fingerprint or "").strip()
    if supplied_preflight_fingerprint and supplied_preflight_fingerprint != expected_preflight_fingerprint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="预检结果已过期：同步范围已变化，请重新试运行后再执行。",
        )
    idempotency_key = _build_idempotency_key(
        source=req.source,
        tier=effective_tier,
        sync_date=effective_sync_date,
        operator=operator_email,
        scene=scene,
        date_window=date_window_payload,
        target_departments=target_departments,
        tables=selected_tables,
        table_groups=req.table_groups,
        policy_version=policy_version,
    )

    reservation = reserve_sync_trigger(
        idempotency_key=idempotency_key,
        source=req.source,
        tier=effective_tier,
        sync_date=effective_sync_date,
        operator_email=operator_email,
    )
    if not reservation.created:
        reused_success = reservation.status in {"success", "partial"}
        if isinstance(reservation.result, dict) and "success" in reservation.result:
            reused_success = bool(reservation.result.get("success")) or reservation.status == "partial"
        reused_payload: dict[str, object] = {
            "run_id": reservation.run_id,
            "status": reservation.status,
            "success": reused_success,
            "idempotency_key": idempotency_key,
            "idempotent_reused": True,
        }
        if reservation.result is not None:
            reused_payload["result"] = reservation.result
            if isinstance(reservation.result.get("warnings"), list):
                reused_payload["warnings"] = reservation.result.get("warnings")
        if reservation.error:
            reused_payload["error"] = reservation.error
        audit_event(
            request,
            action="sync.trigger",
            resource="/api/v1/sync/trigger",
            outcome="reused",
            current_user=current_user,
            details={
                "source": req.source,
                "tier": effective_tier,
                "sync_date": effective_sync_date,
                "run_id": reservation.run_id,
                "idempotency_key": idempotency_key,
                "status": reservation.status,
            },
        )
        return _ok(request, reused_payload, message="检测到重复触发，返回已有任务")

    run_id = reservation.run_id
    started_at = datetime.now(timezone.utc)

    try:
        from ..services.etl_sync import run_sync
        result = await run_in_threadpool(
            run_sync,
            sync_date=effective_sync_date,
            tables=selected_tables,
            scene=scene,
            policy_version=policy_version,
            date_window=date_window_payload,
            target_departments=target_departments,
            run_id=run_id,
        )
    except Exception as exc:
        complete_sync_trigger(
            idempotency_key=idempotency_key,
            status="failed",
            result=None,
            error=str(exc),
        )
        _raise_mapped_service_error(exc)

    finished_at = datetime.now(timezone.utc)
    status_name = _infer_trigger_status(req.source, result)
    total_records = _infer_total_records(req.source, result)

    try:
        if _is_rejected_running(result):
            complete_sync_trigger(
                idempotency_key=idempotency_key,
                status="rejected",
                result=result if isinstance(result, dict) else None,
                error=str(result.get("error") or result.get("message") or "同步正在进行中"),
            )
            audit_event(
                request,
                action="sync.trigger",
                resource="/api/v1/sync/trigger",
                outcome="rejected_running",
                current_user=current_user,
                details={
                    "source": req.source,
                    "tier": effective_tier,
                    "sync_date": effective_sync_date,
                    "run_id": run_id,
                    "idempotency_key": idempotency_key,
                },
            )
            return _err(request, str(result.get("error") or "同步正在进行中"), code="SYNC_ALREADY_RUNNING")

        from ..services.sync_run_history import append_sync_run_record

        operator = {
            "id": current_user.get("id"),
            "email": current_user.get("email"),
            "roles": current_user.get("roles") or [],
        }
        append_sync_run_record(
            {
                "id": run_id,
                "source": req.source,
                "tier": effective_tier,
                "tables": selected_tables or [],
                "table_groups": req.table_groups or [],
                "scene": scene,
                "date_window": date_window_payload or {},
                "target_departments": target_departments or ["*"],
                "policy_version": policy_version,
                "status": status_name,
                "started_at": _utc_iso(started_at),
                "finished_at": _utc_iso(finished_at),
                "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
                "total_records": total_records,
                "error": result.get("error") if isinstance(result, dict) else None,
                "operator": operator,
            }
        )
        logger.info(
            "sync.trigger operator=%s source=%s tier=%s status=%s total_records=%s",
            current_user.get("email"),
            req.source,
            effective_tier,
            status_name,
            total_records,
        )
    except Exception as exc:
        logger.warning("写入同步历史失败: %s", exc)

    if (
        isinstance(result, dict)
        and bool(result.get("success")) is False
        and status_name != "partial"
    ):
        complete_sync_trigger(
            idempotency_key=idempotency_key,
            status="failed",
            result=result,
            error=str(result.get("error") or "同步执行失败"),
        )
        audit_event(
            request,
            action="sync.trigger",
            resource="/api/v1/sync/trigger",
            outcome="failed",
            current_user=current_user,
            details={
                "source": req.source,
                "tier": effective_tier,
                "sync_date": effective_sync_date,
                "scene": scene,
                "run_id": run_id,
                "idempotency_key": idempotency_key,
                "status": status_name,
                "total_records": total_records,
                "error": result.get("error"),
            },
        )
        return _err(
            request,
            str(result.get("error") or "同步执行失败"),
            code="SYNC_TRIGGER_FAILED",
            data=result,
        )

    complete_sync_trigger(
        idempotency_key=idempotency_key,
        status=status_name,
        result=result if isinstance(result, dict) else None,
        error="",
    )
    payload = dict(result) if isinstance(result, dict) else {"result": result}
    payload.setdefault("run_id", run_id)
    payload["idempotency_key"] = idempotency_key
    payload["idempotent_reused"] = False
    audit_event(
        request,
        action="sync.trigger",
        resource="/api/v1/sync/trigger",
        outcome=status_name,
        current_user=current_user,
        details={
            "source": req.source,
            "tier": effective_tier,
            "sync_date": effective_sync_date,
            "scene": scene,
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "status": status_name,
            "total_records": total_records,
        },
    )
    return _ok(request, payload)



# ==================== 只读映射视图（P0） ====================

@router.get("/mappings")
async def get_sync_mappings(request: Request, _: dict = Depends(require_sync_read_access)):
    """保留接口：当前返回空映射。"""
    return _ok(request, {"items": [], "total": 0})


@router.get("/runs")
async def get_sync_runs(
    request: Request,
    source: Optional[Literal["pg"]] = Query(default=None),
    tier: Optional[Literal["tier1", "tier2", "tier3", "all"]] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=500),
    limit: int = Query(default=50, ge=1, le=500),
    _: dict = Depends(require_sync_read_access),
):
    """获取同步运行历史（最近 N 次）"""
    from ..services.sync_run_history import list_sync_run_records

    kwargs = {
        "source": source,
        "tier": tier,
        "limit": limit,
    }
    if page != 1:
        kwargs["page"] = page
    if page_size is not None:
        kwargs["page_size"] = page_size

    return _ok(
        request,
        list_sync_run_records(**kwargs),
    )


@router.get("/templates")
async def get_sync_templates(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取同步模板目录"""
    from ..services.sync_templates import list_sync_templates

    return _ok(request, {"items": list_sync_templates()})


@router.post("/templates/apply")
async def apply_sync_template(
    request: Request,
    req: SyncTemplateApplyRequest,
    current_user: dict = Depends(require_sync_write_access),
):
    """应用同步模板（仅 admin，PG 策略口径）。"""
    try:
        from ..services.sync_policy import save_sync_policy
        from ..services.sync_templates import list_sync_templates
    except Exception as exc:
        _raise_mapped_service_error(exc)

    template = next((item for item in list_sync_templates() if item.get("id") == req.template_id), None)
    if not template:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"未知模板: {req.template_id}")

    normalized_departments: list[str] = []
    for dep in req.departments or []:
        name = str(dep or "").strip()
        if name and name not in normalized_departments:
            normalized_departments.append(name)

    requires_departments = bool(template.get("requires_departments"))
    allow_multi_departments = bool(template.get("allow_multi_departments"))
    if requires_departments and not normalized_departments:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该模板必须选择科室")
    if "*" in normalized_departments and len(normalized_departments) > 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="科室列表不允许同时包含 * 和具体科室")
    if not allow_multi_departments and len([d for d in normalized_departments if d != "*"]) > 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="该模板仅支持单科室")

    defaults = template.get("defaults") or {}
    payload: dict = {}

    target_departments = normalized_departments or defaults.get("target_departments") or ["*"]
    payload["target_departments"] = target_departments

    schedule_minutes = defaults.get("tier1_interval_minutes")
    if schedule_minutes:
        payload["schedule"] = {"mode": "interval", "minutes": int(schedule_minutes)}

    night_start = defaults.get("night_window_start")
    night_end = defaults.get("night_window_end")
    if night_start or night_end:
        payload["night_window"] = {
            "start": str(night_start or "22:00"),
            "end": str(night_end or "06:00"),
        }

    try:
        saved = save_sync_policy(payload, keep_policy_version=False)
    except Exception as exc:
        _raise_mapped_service_error(exc)
    audit_event(
        request,
        action="sync.template.apply",
        resource="/api/v1/sync/templates/apply",
        outcome="success",
        current_user=current_user,
        details={
            "template_id": req.template_id,
            "departments_count": len(req.departments or []),
            "scope": saved.get("scope"),
            "policy_version": saved.get("policy_version"),
        },
    )
    return _ok(request, {"template_id": req.template_id, "policy": saved})
