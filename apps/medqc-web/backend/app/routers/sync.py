"""
数据同步 API 路由 — 统一管理 PG 存储过程同步 和 MongoDB 增量同步

端点：
  GET  /api/v1/sync/status     查看同步状态
  POST /api/v1/sync/trigger    手动触发同步
  GET  /api/v1/sync/config     获取抽取配置
  PUT  /api/v1/sync/config     修改抽取配置
  GET  /api/v1/sync/statistics 同步统计
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sync", tags=["data-sync"])


# ==================== 状态查询 ====================

@router.get("/status")
async def get_sync_status():
    """获取同步状态（PG + MongoDB）"""
    from ..services.etl_sync import get_sync_state
    from ..services.mongo_sync import get_mongo_sync_state

    return {
        "pg_sync": get_sync_state(),
        "mongo_sync": get_mongo_sync_state(),
    }


# ==================== 触发同步 ====================

class TriggerRequest(BaseModel):
    source: str = "pg"          # pg / mongo
    sync_date: Optional[str] = None   # PG 存储过程用
    tier: str = "all"           # MongoDB: tier1 / tier2 / tier3 / all
    tables: Optional[list] = None     # PG: 指定同步的表

@router.post("/trigger")
async def trigger_sync(req: TriggerRequest):
    """手动触发数据同步"""
    if req.source == "mongo":
        from ..services.mongo_sync import run_mongo_sync
        result = run_mongo_sync(tier=req.tier)
        return result
    else:
        from ..services.etl_sync import run_sync
        result = run_sync(sync_date=req.sync_date, tables=req.tables)
        return result


# ==================== MongoDB 配置 ====================

@router.get("/config/mongo")
async def get_mongo_config():
    """获取 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config
    from dataclasses import asdict

    config = load_mongo_config()
    data = asdict(config)
    # 隐藏 URI 中的密码
    if data.get("mongo_uri") and "@" in data["mongo_uri"]:
        parts = data["mongo_uri"].split("@")
        cred = parts[0].rsplit(":", 1)
        data["mongo_uri_display"] = cred[0] + ":***@" + parts[1]
    else:
        data["mongo_uri_display"] = data.get("mongo_uri", "")
    return data


class MongoConfigUpdate(BaseModel):
    mongo_uri: Optional[str] = None
    mongo_database: Optional[str] = None
    read_preference: Optional[str] = None
    discharge_stable_days: Optional[int] = None
    tier1_interval_minutes: Optional[int] = None
    tier2_interval_minutes: Optional[int] = None
    tier3_cron: Optional[str] = None
    max_batch_size: Optional[int] = None
    inter_request_delay_ms: Optional[int] = None
    night_window_start: Optional[str] = None
    night_window_end: Optional[str] = None
    target_departments: Optional[list] = None
    enabled: Optional[bool] = None

@router.put("/config/mongo")
async def update_mongo_config(update: MongoConfigUpdate):
    """更新 MongoDB 同步配置"""
    from ..services.etl_config import load_mongo_config, save_mongo_config

    config = load_mongo_config()
    for k, v in update.dict(exclude_none=True).items():
        if hasattr(config, k):
            setattr(config, k, v)

    saved = save_mongo_config(config)
    return {"success": True, "config": saved}


# ==================== 连接测试 ====================

@router.post("/test-connection/mongo")
async def test_mongo_connection():
    """测试 MongoDB 连接"""
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
        result = connector.test_connection()
        return result
    finally:
        connector.close()


# ==================== 同步统计 ====================

@router.get("/statistics")
async def get_statistics():
    """同步统计（各状态 visit 数量）"""
    from ..services.mongo_sync import get_sync_statistics
    return get_sync_statistics()


# ==================== PG 同步配置（已有 etl_sync 的包装） ====================

@router.get("/config/pg")
async def get_pg_config():
    """获取 PG 同步配置"""
    from ..services.etl_sync import load_db_config
    config = load_db_config()
    # 隐藏密码
    if config.get("remote_password"):
        config["remote_password_display"] = "***"
    return config


@router.post("/test-connection/pg-remote")
async def test_pg_remote():
    """测试远端 PG 连接"""
    from ..services.etl_sync import test_remote_connection
    return test_remote_connection()


@router.post("/test-connection/pg-local")
async def test_pg_local():
    """测试本地 PG 连接"""
    from ..services.etl_sync import test_local_connection
    return test_local_connection()
