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
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["data-sync"])


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


# ==================== 状态查询 ====================

@router.get("/status")
async def get_sync_status(_: dict = Depends(require_sync_read_access)):
    """获取同步状态（PG + MongoDB）"""
    from ..services.etl_sync import get_sync_state
    from ..services.mongo_sync import get_mongo_sync_state

    return {
        "pg_sync": get_sync_state(),
        "mongo_sync": get_mongo_sync_state(),
    }


@router.get("/statistics")
async def get_statistics(_: dict = Depends(require_sync_read_access)):
    """同步统计（各状态 visit 数量）"""
    from ..services.mongo_sync import get_sync_statistics

    return get_sync_statistics()


# ==================== MongoDB 配置 ====================

@router.get("/config/mongo")
async def get_mongo_config(_: dict = Depends(require_sync_read_access)):
    """获取 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config

    config = load_mongo_config()
    data = asdict(config)
    data["mongo_uri_display"] = _mask_mongo_uri(str(data.get("mongo_uri") or ""))
    return data


@router.put("/config/mongo")
async def update_mongo_config(
    update: MongoConfigUpdate,
    _: dict = Depends(require_sync_write_access),
):
    """更新 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config, save_mongo_config

    config = load_mongo_config()
    for key, value in update.model_dump(exclude_none=True).items():
        if hasattr(config, key):
            setattr(config, key, value)

    saved = save_mongo_config(config)
    saved["mongo_uri_display"] = _mask_mongo_uri(str(saved.get("mongo_uri") or ""))
    return {"success": True, "config": saved}


# ==================== PG 配置 ====================

@router.get("/config/pg")
async def get_pg_config(_: dict = Depends(require_sync_read_access)):
    """获取 PG 同步配置（密码脱敏）"""
    from ..services.etl_sync import load_db_config

    config = load_db_config()
    return _mask_pg_config(config)


@router.put("/config/pg")
async def update_pg_config(
    update: PgConfigUpdate,
    _: dict = Depends(require_sync_write_access),
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

    merged = {**current, **incoming}
    save_db_config(merged)
    conn_result = test_remote_connection()
    return {
        "success": True,
        "config": _mask_pg_config(merged),
        "connection": conn_result,
    }


# ==================== 连接测试 ====================

@router.post("/test-connection/mongo")
async def test_mongo_connection(_: dict = Depends(require_sync_write_access)):
    """测试 MongoDB 连接（仅 admin）"""
    from ..services.etl_config import load_mongo_config
    from ..services.mongo_sync import MongoConnector

    config = load_mongo_config()
    if not config.mongo_uri:
        return {"connected": False, "error": "mongo_uri 未配置"}

    connector = MongoConnector(
        uri=config.mongo_uri,
        database=config.mongo_database,
        read_preference=config.read_preference,
        max_pool_size=1,
        socket_timeout_ms=config.query_timeout_s * 1000,
        connect_timeout_ms=config.connect_timeout_ms,
    )
    try:
        return connector.test_connection()
    finally:
        connector.close()


@router.post("/test-connection/pg-remote")
async def test_pg_remote(_: dict = Depends(require_sync_write_access)):
    """测试远端 PG 连接（仅 admin）"""
    from ..services.etl_sync import test_remote_connection

    return test_remote_connection()


@router.post("/test-connection/pg-local")
async def test_pg_local(_: dict = Depends(require_sync_write_access)):
    """测试本地 PG 连接（仅 admin）"""
    from ..services.etl_sync import test_local_connection

    return test_local_connection()


@router.post("/test-connection/all")
async def test_all_connections(_: dict = Depends(require_sync_write_access)):
    """测试全连接（Mongo + 远端 PG + 本地 PG）"""
    from ..services.etl_sync import test_local_connection, test_remote_connection

    mongo = await test_mongo_connection(_)  # 复用同一路由逻辑
    pg_remote = test_remote_connection()
    pg_local = test_local_connection()
    all_connected = bool(mongo.get("connected")) and bool(pg_remote.get("connected")) and bool(pg_local.get("connected"))
    connected_count = int(bool(mongo.get("connected"))) + int(bool(pg_remote.get("connected"))) + int(bool(pg_local.get("connected")))
    return {
        "all_connected": all_connected,
        "connected_count": connected_count,
        "total_sources": 3,
        "mongo": mongo,
        "pg_remote": pg_remote,
        "pg_local": pg_local,
    }


# ==================== 试运行预检 ====================

@router.post("/preflight")
async def run_preflight(
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
        return {
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
        }

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

    return {
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
    }


# ==================== 触发同步 ====================

@router.post("/trigger")
async def trigger_sync(
    req: TriggerRequest,
    current_user: dict = Depends(require_sync_write_access),
):
    """手动触发数据同步（仅 admin）"""
    started_at = datetime.now(timezone.utc)

    if req.source == "mongo":
        from ..services.mongo_sync import run_mongo_sync

        result = run_mongo_sync(tier=req.tier)
    else:
        from ..services.etl_sync import run_sync

        result = run_sync(sync_date=req.sync_date, tables=req.tables)

    finished_at = datetime.now(timezone.utc)
    status_name = _infer_trigger_status(req.source, result)
    total_records = _infer_total_records(req.source, result)

    try:
        if _is_rejected_running(result):
            return result

        from ..services.sync_run_history import append_sync_run_record

        operator = {
            "id": current_user.get("id"),
            "email": current_user.get("email"),
            "roles": current_user.get("roles") or [],
        }
        append_sync_run_record(
            {
                "id": f"syncrun-{uuid.uuid4().hex[:12]}",
                "source": req.source,
                "tier": req.tier if req.source == "mongo" else "all",
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
    except Exception as exc:
        logger.warning("写入同步历史失败: %s", exc)

    return result


# ==================== 只读映射视图（P0） ====================

@router.get("/mappings")
async def get_sync_mappings(_: dict = Depends(require_sync_read_access)):
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
    return {"items": items, "total": len(items)}


@router.get("/runs")
async def get_sync_runs(
    source: Optional[Literal["mongo", "pg"]] = Query(default=None),
    tier: Optional[Literal["tier1", "tier2", "tier3", "all"]] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    _: dict = Depends(require_sync_read_access),
):
    """获取同步运行历史（最近 N 次）"""
    from ..services.sync_run_history import list_sync_run_records

    return list_sync_run_records(source=source, tier=tier, limit=limit)


@router.get("/templates")
async def get_sync_templates(_: dict = Depends(require_sync_read_access)):
    """获取同步模板目录"""
    from ..services.sync_templates import list_sync_templates

    return {"items": list_sync_templates()}


@router.post("/templates/apply")
async def apply_sync_template(
    req: SyncTemplateApplyRequest,
    _: dict = Depends(require_sync_write_access),
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
    return {"success": True, "template_id": req.template_id, "config": saved}
