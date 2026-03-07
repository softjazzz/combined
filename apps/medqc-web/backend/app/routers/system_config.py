"""
系统配置与同步管理 API

路由前缀: /api/system
功能: 数据库连接状态检测、ETL 同步触发与状态查询
"""

from fastapi import APIRouter, Query, BackgroundTasks
from typing import Optional

router = APIRouter(prefix="/api/system", tags=["系统配置"])


# ==================== 数据库连接状态 ====================

@router.get("/db/status")
async def get_db_status():
    """获取本地 + 远端数据库连接状态"""
    from ..services.etl_sync import test_local_connection, test_remote_connection

    return {
        "local": test_local_connection(),
        "remote": test_remote_connection(),
    }


@router.get("/db/local")
async def get_local_db_status():
    """获取本地数据库连接状态和表数据量"""
    from ..services.etl_sync import test_local_connection
    return test_local_connection()


@router.get("/db/remote")
async def get_remote_db_status():
    """测试远端数据库连接"""
    from ..services.etl_sync import test_remote_connection
    return test_remote_connection()


# ==================== 数据库配置（页面可编辑）====================

@router.get("/db/config")
async def get_db_config():
    """获取远端数据库配置（密码脱敏）"""
    from ..services.etl_sync import load_db_config
    cfg = load_db_config()
    # 密码只返回是否已设置，不返回明文
    return {
        "remote_host": cfg.get("remote_host", ""),
        "remote_port": cfg.get("remote_port", "5432"),
        "remote_database": cfg.get("remote_database", ""),
        "remote_username": cfg.get("remote_username", ""),
        "remote_password_set": bool(cfg.get("remote_password", "")),
    }


@router.put("/db/config")
async def update_db_config(data: dict):
    """
    保存远端数据库配置并测试连接
    
    Body: { remote_host, remote_port, remote_database, remote_username, remote_password }
    如果 remote_password 为空字符串，则保留原密码不变
    """
    from ..services.etl_sync import load_db_config, save_db_config, test_remote_connection

    # 合并配置（密码为空则保留原值）
    old_cfg = load_db_config()
    new_cfg = {
        "remote_host": data.get("remote_host", old_cfg["remote_host"]),
        "remote_port": data.get("remote_port", old_cfg["remote_port"]),
        "remote_database": data.get("remote_database", old_cfg["remote_database"]),
        "remote_username": data.get("remote_username", old_cfg["remote_username"]),
        "remote_password": data.get("remote_password") or old_cfg.get("remote_password", ""),
    }

    # 保存到 JSON 文件
    save_db_config(new_cfg)

    # 测试新连接
    conn_result = test_remote_connection()

    return {
        "success": True,
        "message": "配置已保存",
        "connection": conn_result,
    }




@router.post("/sync/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    sync_date: Optional[str] = Query(None, description="同步日期，格式 YYYY-MM-DD，默认昨天"),
    tables: Optional[str] = Query(None, description="要同步的表名，逗号分隔，默认全部"),
):
    """
    手动触发 ETL 同步（后台执行）
    
    - 不传参数：同步昨天的所有核心表
    - 指定日期：CALL web.mr('2025-06-01')
    - 指定表：tables=mr,diagnosis
    """
    from ..services.etl_sync import run_sync, get_sync_state

    state = get_sync_state()
    if state["is_running"]:
        return {"success": False, "message": "同步正在进行中，请稍后再试"}

    table_list = tables.split(",") if tables else None

    # 后台执行同步任务
    background_tasks.add_task(run_sync, sync_date, table_list)

    return {
        "success": True,
        "message": f"同步任务已启动，日期: {sync_date or '昨天'}",
        "tables": table_list or "全部核心表",
    }


@router.get("/sync/status")
async def get_sync_status():
    """获取当前同步状态和最近一次同步日志"""
    from ..services.etl_sync import get_sync_state
    return get_sync_state()


# ==================== 同步配置 ====================

@router.get("/sync/tables")
async def get_sync_tables():
    """获取可同步的表列表"""
    from ..services.etl_sync import SYNC_TABLES
    return {
        "tables": [
            {"name": t["name"], "label": t["label"], "procedure": t["procedure"]}
            for t in SYNC_TABLES
        ]
    }
