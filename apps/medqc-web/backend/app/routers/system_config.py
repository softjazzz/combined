"""
系统配置与同步管理 API

路由前缀: /api/system
功能: 数据库连接状态检测、ETL 同步触发与状态查询
"""

from fastapi import APIRouter, Query, BackgroundTasks, Depends, HTTPException, Request, status
from typing import Optional
from ..core.audit import audit_event
from ..core.security import require_global_system_admin
from ..core.response import success_response, error_response, get_trace_id

def require_legacy_system_available() -> None:
    from ..database import clinical_connection
    from ..services.clinical_source_policy import fixed_cdm

    selection = clinical_connection.current_selection()
    if (selection is not None and selection.get("id") == "independent_cdm") or fixed_cdm():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="legacy_system_sync_disabled_in_independent_cdm",
        )


router = APIRouter(
    prefix="/api/system",
    tags=["系统配置"],
    dependencies=[
        Depends(require_global_system_admin),
        Depends(require_legacy_system_available),
    ],
)

def _reject_legacy_write_endpoint(path: str):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=f"Legacy write endpoint retired: {path}. Please use /api/v1/sync/*",
    )


# ==================== 数据库连接状态 ====================

@router.get("/db/status")
def get_db_status(request: Request):
    """获取本地 + 远端数据库连接状态"""
    from ..services.etl_sync import test_local_connection, test_remote_connection

    return success_response(
        data={
            "local": test_local_connection(),
            "remote": test_remote_connection(),
        },
        message="获取数据库连接状态成功",
        trace_id=get_trace_id(request),
    )


@router.get("/db/local")
def get_local_db_status(request: Request):
    """获取本地数据库连接状态和表数据量"""
    from ..services.etl_sync import test_local_connection
    return success_response(
        data=test_local_connection(),
        message="获取本地数据库状态成功",
        trace_id=get_trace_id(request),
    )


@router.get("/db/remote")
def get_remote_db_status(request: Request):
    """测试远端数据库连接"""
    from ..services.etl_sync import test_remote_connection
    return success_response(
        data=test_remote_connection(),
        message="获取远端数据库状态成功",
        trace_id=get_trace_id(request),
    )


# ==================== 数据库配置（页面可编辑）====================

@router.get("/db/config")
def get_db_config(request: Request):
    """获取远端数据库配置（密码脱敏）"""
    from ..services.etl_sync import load_db_config
    cfg = load_db_config()
    # 密码只返回是否已设置，不返回明文
    return success_response(
        data={
            "remote_host": cfg.get("remote_host", ""),
            "remote_port": cfg.get("remote_port", "5432"),
            "remote_database": cfg.get("remote_database", ""),
            "remote_username": cfg.get("remote_username", ""),
            "remote_password_set": bool(cfg.get("remote_password", "")),
            "remote_password_ref": cfg.get("remote_password_ref", ""),
        },
        message="获取数据库配置成功",
        trace_id=get_trace_id(request),
    )


@router.put("/db/config")
def update_db_config(request: Request, data: dict):
    """
    保存远端数据库配置并测试连接
    
    Body: { remote_host, remote_port, remote_database, remote_username, remote_password }
    如果 remote_password 为空字符串，则保留原密码不变
    """
    from ..services.etl_sync import load_db_config, save_db_config, test_remote_connection
    _reject_legacy_write_endpoint("/api/system/db/config")

    # 合并配置（密码为空则保留原值）
    old_cfg = load_db_config()
    incoming_password = data.get("remote_password")
    new_cfg = {
        "remote_host": data.get("remote_host", old_cfg["remote_host"]),
        "remote_port": data.get("remote_port", old_cfg["remote_port"]),
        "remote_database": data.get("remote_database", old_cfg["remote_database"]),
        "remote_username": data.get("remote_username", old_cfg["remote_username"]),
        "remote_password_ref": data.get("remote_password_ref", old_cfg.get("remote_password_ref", "")),
    }

    # 保存到 JSON 文件（口令仅运行时注入，不持久化）
    save_db_config(new_cfg, runtime_password=incoming_password)

    # 测试新连接
    conn_result = test_remote_connection()
    audit_event(
        request,
        action="sync.config.pg.update.legacy",
        resource="/api/system/db/config",
        outcome="success" if bool(conn_result.get("connected")) else "degraded",
        details={
            "remote_host": new_cfg.get("remote_host"),
            "remote_port": new_cfg.get("remote_port"),
            "remote_database": new_cfg.get("remote_database"),
            "connection_ok": bool(conn_result.get("connected")),
        },
    )

    return success_response(
        data={
            "connection": conn_result,
            "deprecated": True,
        },
        message="配置已保存（兼容旧接口，建议迁移到 /api/v1/sync/config/pg）",
        trace_id=get_trace_id(request),
    )




@router.post("/sync/trigger")
def trigger_sync(
    request: Request,
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
    _reject_legacy_write_endpoint("/api/system/sync/trigger")

    state = get_sync_state()
    if state["is_running"]:
        return error_response(
            error="同步正在进行中，请稍后再试",
            code="SYNC_RUNNING",
            trace_id=get_trace_id(request),
        )

    table_list = tables.split(",") if tables else None

    # 后台执行同步任务
    background_tasks.add_task(run_sync, sync_date, table_list)
    audit_event(
        request,
        action="sync.trigger.legacy",
        resource="/api/system/sync/trigger",
        outcome="accepted",
        details={
            "sync_date": sync_date or "yesterday",
            "tables_count": len(table_list or []),
        },
    )

    return success_response(
        data={
            "tables": table_list or "全部核心表",
            "deprecated": True,
        },
        message=f"同步任务已启动，日期: {sync_date or '昨天'}（兼容旧接口，建议迁移到 /api/v1/sync/trigger）",
        trace_id=get_trace_id(request),
    )


@router.get("/sync/status")
def get_sync_status(request: Request):
    """获取当前同步状态和最近一次同步日志"""
    from ..services.etl_sync import get_sync_state
    return success_response(
        data=get_sync_state(),
        message="获取同步状态成功",
        trace_id=get_trace_id(request),
    )


# ==================== 同步配置 ====================

@router.get("/sync/tables")
def get_sync_tables(request: Request):
    """获取可同步的表列表"""
    from ..services.etl_sync import list_sync_tables
    tables = list_sync_tables()
    return success_response(
        data={
            "tables": [
                {
                    "name": t["name"],
                    "label": t["label"],
                    "procedure": t.get("procedure"),
                    "source_table": t.get("source_table"),
                    "date_field": t.get("date_field"),
                    "fallback_date_field": t.get("fallback_date_field"),
                    "enabled": bool(t.get("enabled")),
                }
                for t in tables
            ]
        },
        message="获取同步表配置成功",
        trace_id=get_trace_id(request),
    )
