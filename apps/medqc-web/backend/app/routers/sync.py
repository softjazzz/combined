"""
数据同步 API 路由（V4）

统一归口：
- /api/v1/sync/config/mongo
- /api/v1/sync/config/pg
- /api/v1/sync/status
- /api/v1/sync/statistics
- /api/v1/sync/test-connection/*
- /api/v1/sync/preflight
- /api/v1/sync/trigger
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

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
    if not roles.intersection({"admin", "qc_manager"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="数据同步读取权限不足（仅 admin / qc_manager 可访问）",
        )
    return current_user


def require_sync_write_access(current_user: dict = Depends(get_current_user)) -> dict:
    roles = _extract_roles(current_user)
    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="数据同步写入权限不足（仅 admin 可操作）",
        )
    return current_user


def _mask_mongo_uri(uri: str) -> str:
    if not uri:
        return ""
    if "@" in uri:
        parts = uri.split("@")
        cred = parts[0].rsplit(":", 1)
        if len(cred) == 2:
            return f"{cred[0]}:***@{parts[1]}"
    return uri


def _mask_pg_config(raw: dict) -> dict:
    data = dict(raw)
    password = str(data.get("remote_password") or "")
    data.pop("remote_password", None)
    data["remote_password_set"] = bool(password)
    data["remote_password_display"] = "***" if password else ""
    data["remote_password_ref"] = str(data.get("remote_password_ref") or "")
    return data


class TriggerRequest(BaseModel):
    source: Literal["pg", "mongo"] = "pg"
    sync_date: Optional[str] = None
    tier: Literal["tier1", "tier2", "tier3", "all"] = "all"
    tables: Optional[list[str]] = None


class MongoConfigUpdate(BaseModel):
    mongo_uri: Optional[str] = Field(default=None, min_length=1, max_length=500)
    mongo_database: Optional[str] = Field(default=None, min_length=1, max_length=128)
    read_preference: Optional[Literal["primary", "primaryPreferred", "secondary", "secondaryPreferred", "nearest"]] = None
    max_pool_size: Optional[int] = Field(default=None, ge=1, le=50)
    socket_timeout_ms: Optional[int] = Field(default=None, ge=1000, le=120000)
    connect_timeout_ms: Optional[int] = Field(default=None, ge=1000, le=60000)
    discharge_stable_days: Optional[int] = Field(default=None, ge=0, le=60)
    lookback_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    rescan_recent_days: Optional[int] = Field(default=None, ge=0, le=60)
    tier1_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    tier2_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    tier3_cron: Optional[str] = Field(default=None, min_length=3, max_length=80)
    max_batch_size: Optional[int] = Field(default=None, ge=10, le=5000)
    tier3_batch_size: Optional[int] = Field(default=None, ge=10, le=2000)
    inter_request_delay_ms: Optional[int] = Field(default=None, ge=0, le=10000)
    max_concurrent: Optional[int] = Field(default=None, ge=1, le=20)
    query_timeout_s: Optional[int] = Field(default=None, ge=1, le=600)
    retry_max: Optional[int] = Field(default=None, ge=0, le=20)
    retry_backoff: Optional[list[int]] = Field(default=None)
    night_window_start: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    night_window_end: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    target_departments: Optional[list[str]] = None
    enabled: Optional[bool] = None


class PgConfigUpdate(BaseModel):
    remote_host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    remote_port: Optional[int] = Field(default=None, ge=1, le=65535)
    remote_database: Optional[str] = Field(default=None, min_length=1, max_length=128)
    remote_username: Optional[str] = Field(default=None, min_length=1, max_length=128)
    remote_password_ref: Optional[str] = Field(default=None, max_length=128)
    remote_password: Optional[str] = Field(default=None, max_length=256)


class PreflightRequest(BaseModel):
    source: Literal["mongo", "pg"] = "mongo"
    tier: Literal["tier1", "tier2", "tier3", "all"] = "all"
    tables: Optional[list[str]] = None


class SyncTemplateApplyRequest(BaseModel):
    template_id: Literal["hospital_standard", "single_department_focus", "multi_department_joint", "night_low_impact"]
    departments: Optional[list[str]] = None


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _infer_trigger_status(source: str, result: dict) -> str:
    if source == "pg":
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


def _build_idempotency_key(*, source: str, tier: str, sync_date: str, operator: str) -> str:
    return f"{source}:{tier}:{sync_date}:{operator}"


# ==================== 状态查询 ====================

@router.get("/status")
async def get_sync_status(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取同步状态（PG + MongoDB）"""
    from ..services.etl_sync import get_sync_state
    from ..services.mongo_sync import get_mongo_sync_state

    return _ok(request, {
        "pg_sync": get_sync_state(),
        "mongo_sync": get_mongo_sync_state(),
    })


@router.get("/statistics")
async def get_statistics(request: Request, _: dict = Depends(require_sync_read_access)):
    """同步统计（各状态 visit 数量）"""
    from ..services.mongo_sync import get_sync_statistics

    return _ok(request, get_sync_statistics())


# ==================== MongoDB 配置 ====================

@router.get("/config/mongo")
async def get_mongo_config(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config

    config = load_mongo_config()
    data = asdict(config)
    data["mongo_uri_display"] = _mask_mongo_uri(str(data.get("mongo_uri") or ""))
    return _ok(request, data)


@router.put("/config/mongo")
async def update_mongo_config(
    request: Request,
    update: MongoConfigUpdate,
    current_user: dict = Depends(require_sync_write_access),
):
    """更新 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config, save_mongo_config

    config = load_mongo_config()
    for key, value in update.model_dump(exclude_none=True).items():
        if hasattr(config, key):
            setattr(config, key, value)

    saved = save_mongo_config(config)
    saved["mongo_uri_display"] = _mask_mongo_uri(str(saved.get("mongo_uri") or ""))
    audit_event(
        request,
        action="sync.config.mongo.update",
        resource="/api/v1/sync/config/mongo",
        outcome="success",
        current_user=current_user,
        details={
            "changed_fields": sorted(update.model_dump(exclude_none=True).keys()),
            "enabled": bool(saved.get("enabled")),
        },
    )
    return _ok(request, {"config": saved})


# ==================== PG 配置 ====================

@router.get("/config/pg")
async def get_pg_config(request: Request, _: dict = Depends(require_sync_read_access)):
    """获取 PG 同步配置（密码脱敏）"""
    from ..services.etl_sync import load_db_config

    config = load_db_config()
    return _ok(request, _mask_pg_config(config))


@router.put("/config/pg")
async def update_pg_config(
    request: Request,
    update: PgConfigUpdate,
    current_user: dict = Depends(require_sync_write_access),
):
    """更新 PG 同步配置（仅 admin）"""
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


# ==================== 连接测试 ====================

@router.post("/test-connection/mongo")
async def test_mongo_connection(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试 MongoDB 连接（仅 admin）"""
    from ..services.etl_config import load_mongo_config
    from ..services.mongo_sync import MongoConnector

    config = load_mongo_config()
    if not config.mongo_uri:
        return _ok(request, {"connected": False, "error": "mongo_uri 未配置"})

    connector = MongoConnector(
        uri=config.mongo_uri,
        database=config.mongo_database,
        read_preference=config.read_preference,
        max_pool_size=1,
        socket_timeout_ms=config.query_timeout_s * 1000,
        connect_timeout_ms=config.connect_timeout_ms,
    )
    try:
        return _ok(request, connector.test_connection())
    finally:
        connector.close()


@router.post("/test-connection/pg-remote")
async def test_pg_remote(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试远端 PG 连接（仅 admin）"""
    from ..services.etl_sync import test_remote_connection

    return _ok(request, test_remote_connection())


@router.post("/test-connection/pg-local")
async def test_pg_local(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试本地 PG 连接（仅 admin）"""
    from ..services.etl_sync import test_local_connection

    return _ok(request, test_local_connection())


@router.post("/test-connection/all")
async def test_all_connections(request: Request, _: dict = Depends(require_sync_write_access)):
    """测试全连接（远端 PG + 本地 PG）"""
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


@router.get("/departments")
async def get_mongo_departments(request: Request, _: dict = Depends(require_sync_read_access)):
    """从远端 Mongo 实时获取科室列表（用于模板科室选择）"""
    from ..services.etl_config import load_mongo_config
    from ..services.mongo_sync import MongoConnector

    config = load_mongo_config()
    if not config.mongo_uri:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="mongo_uri 未配置")

    connector = MongoConnector(
        uri=config.mongo_uri,
        database=config.mongo_database,
        read_preference=config.read_preference,
        max_pool_size=1,
        socket_timeout_ms=config.query_timeout_s * 1000,
        connect_timeout_ms=config.connect_timeout_ms,
    )
    try:
        db = connector.get_db()
        raw_departments = db["mr"].distinct("discharge_dept_name")
        items = sorted(
            {
                str(item).strip()
                for item in raw_departments
                if str(item or "").strip()
            }
        )
        return _ok(request, {"items": items, "total": len(items)})
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"获取科室失败: {str(exc)[:200]}",
        )
    finally:
        connector.close()


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
    if req.source == "pg":
        from ..services.etl_sync import get_sync_state, test_local_connection, test_remote_connection

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

        sync_state = get_sync_state()
        estimated_impact = int(sync_state.get("total_records_synced") or 0)
        return _ok(request, {
            "source": "pg",
            "tier": "all",
            "executable": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "estimated_impact": estimated_impact,
            "risk_level": "low" if len(blockers) == 0 else "high",
            "connections": {
                "pg_remote": remote_result,
                "pg_local": local_result,
            },
        })

    from ..services.etl_config import load_mongo_config
    from ..services.mongo_sync import MongoConnector, get_mongo_sync_state, get_sync_statistics

    config = load_mongo_config()
    blockers = []
    warnings = []

    if not config.enabled:
        blockers.append("Mongo 同步总开关已关闭。")
    if not config.mongo_uri:
        blockers.append("mongo_uri 未配置。")

    mongo_result = {"connected": False, "error": "mongo_uri 未配置"}
    if config.mongo_uri:
        connector = MongoConnector(
            uri=config.mongo_uri,
            database=config.mongo_database,
            read_preference=config.read_preference,
            max_pool_size=1,
            socket_timeout_ms=config.query_timeout_s * 1000,
            connect_timeout_ms=config.connect_timeout_ms,
        )
        try:
            mongo_result = connector.test_connection()
        finally:
            connector.close()
        if not mongo_result.get("connected"):
            blockers.append(f"Mongo 连接失败: {mongo_result.get('error', '未知错误')}")

    if req.tier == "tier3" and not str(config.tier3_cron or "").strip():
        blockers.append("Tier3 定时表达式为空。")
    if config.max_batch_size > 500:
        warnings.append("单批处理量较大，可能对源端造成较高压力。")
    if config.inter_request_delay_ms < 100:
        warnings.append("请求间隔较小，建议评估源端负载风险。")

    stats = get_sync_statistics()
    pending = int(stats.get("PENDING", 0))
    partial = int(stats.get("PARTIAL", 0))
    failed = int(stats.get("FAILED", 0))
    stale = int(stats.get("STALE", 0))
    estimated_impact = pending + partial + stale
    if failed > 0:
        warnings.append(f"当前存在 {failed} 条失败记录，建议先排查错误后再执行。")

    if blockers:
        risk_level = "high"
    elif failed > 0 or stale > 0:
        risk_level = "medium"
    else:
        risk_level = "low"

    return _ok(request, {
        "source": "mongo",
        "tier": req.tier,
        "executable": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "estimated_impact": estimated_impact,
        "risk_level": risk_level,
        "connections": {"mongo": mongo_result},
        "state": get_mongo_sync_state(),
        "statistics": stats,
    })


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

    effective_tier = req.tier if req.source == "mongo" else "all"
    effective_sync_date = _resolve_effective_sync_date(req.source, req.sync_date)
    operator_email = str(current_user.get("email") or current_user.get("id") or "unknown").strip().lower()
    idempotency_key = _build_idempotency_key(
        source=req.source,
        tier=effective_tier,
        sync_date=effective_sync_date,
        operator=operator_email,
    )

    reservation = reserve_sync_trigger(
        idempotency_key=idempotency_key,
        source=req.source,
        tier=effective_tier,
        sync_date=effective_sync_date,
        operator_email=operator_email,
    )
    if not reservation.created:
        reused_payload: dict[str, object] = {
            "run_id": reservation.run_id,
            "status": reservation.status,
            "idempotency_key": idempotency_key,
            "idempotent_reused": True,
        }
        if reservation.result is not None:
            reused_payload["result"] = reservation.result
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

    if req.source == "mongo":
        from ..services.mongo_sync import run_mongo_sync

        result = run_mongo_sync(tier=req.tier)
    else:
        from ..services.etl_sync import run_sync

        result = run_sync(sync_date=effective_sync_date, tables=req.tables)

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
                "tables": req.tables or [],
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

    if isinstance(result, dict) and bool(result.get("success")) is False:
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
    """获取 Mongo -> CDM 映射（只读）"""
    from ..services.etl_config import COLLECTION_KEY_FIELDS, MONGO_COLLECTION_MAP, TIER2_COLLECTIONS

    items = []
    for source_collection, target_table in MONGO_COLLECTION_MAP.items():
        tier = "tier2" if source_collection in TIER2_COLLECTIONS else "tier3"
        items.append(
            {
                "source_collection": source_collection,
                "target_table": target_table,
                "key_fields": COLLECTION_KEY_FIELDS.get(source_collection, []),
                "tier": tier,
                "enabled": True,
            }
        )
    return _ok(request, {"items": items, "total": len(items)})


@router.get("/runs")
async def get_sync_runs(
    request: Request,
    source: Optional[Literal["mongo", "pg"]] = Query(default=None),
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
    """应用同步模板（仅 admin）"""
    from ..services.etl_config import load_mongo_config, save_mongo_config
    from ..services.sync_templates import build_template_overrides

    config = load_mongo_config()
    try:
        overrides = build_template_overrides(
            template_id=req.template_id,
            departments=req.departments,
            current_config=config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    saved = save_mongo_config(config)
    saved["mongo_uri_display"] = _mask_mongo_uri(str(saved.get("mongo_uri") or ""))
    audit_event(
        request,
        action="sync.template.apply",
        resource="/api/v1/sync/templates/apply",
        outcome="success",
        current_user=current_user,
        details={
            "template_id": req.template_id,
            "departments_count": len(req.departments or []),
            "enabled": bool(saved.get("enabled")),
        },
    )
    return _ok(request, {"template_id": req.template_id, "config": saved})
