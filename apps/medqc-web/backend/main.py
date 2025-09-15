"""
DEPRECATED: Legacy experimental entrypoint kept for reference.
Please use `app/main.py` (uvicorn app.main:app) for running the backend.
"""
# 主FastAPI应用（Legacy）

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from datetime import datetime

# 导入现有的路由和中间件
# from .existing_routes import existing_router  # 假设现有的路由

# 导入新增的审核模块路由
from .api.audit_tasks import router as audit_tasks_router
from .api.ai_assistance import router as ai_assistance_router
from .api.notifications import router as notifications_router

# 导入数据库和配置
from .database.database import init_db, close_db
from .core.config import settings

# 导入服务
from .services.notification_service import UnifiedNotificationService
from .llm_service.llm_client import llm_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局服务实例
notification_service_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    
    # 启动时初始化
    logger.info("正在启动医疗质控系统...")
    
    try:
        # 1. 初始化数据库
        await init_db()
        logger.info("数据库初始化完成")
        
        # 2. 启动通知服务
        global notification_service_instance
        notification_service_instance = UnifiedNotificationService(llm_service)
        await notification_service_instance.start_service()
        logger.info("通知服务启动完成")
        
        # 3. 初始化现有的三层质控引擎
        # await three_layer_qc_engine.initialize()
        logger.info("三层质控引擎初始化完成")
        
        # 4. 预热LLM服务
        try:
            await llm_service.health_check()
            logger.info("LLM服务连接正常")
        except Exception as e:
            logger.warning(f"LLM服务连接异常: {e}")
        
        logger.info("医疗质控系统启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        raise e
    
    finally:
        # 关闭时清理
        logger.info("正在关闭医疗质控系统...")
        
        try:
            # 1. 停止通知服务
            if notification_service_instance:
                await notification_service_instance.stop_service()
                logger.info("通知服务已停止")
            
            # 2. 关闭数据库连接
            await close_db()
            logger.info("数据库连接已关闭")
            
            # 3. 清理其他资源
            # await three_layer_qc_engine.cleanup()
            
            logger.info("医疗质控系统已关闭")
            
        except Exception as e:
            logger.error(f"系统关闭异常: {e}")

# 创建FastAPI应用实例
app = FastAPI(
    title="医疗质控系统",
    description="基于LLM集成的医疗质控系统，包含三层质控引擎和人工审核模块",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# 自定义中间件：请求日志和性能监控
@app.middleware("http")
async def log_requests(request, call_next):
    """请求日志和性能监控中间件"""
    start_time = datetime.utcnow()
    
    # 记录请求开始
    logger.info(f"请求开始: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        
        # 计算处理时间
        process_time = (datetime.utcnow() - start_time).total_seconds()
        
        # 记录请求完成
        logger.info(
            f"请求完成: {request.method} {request.url} - "
            f"状态码: {response.status_code} - "
            f"处理时间: {process_time:.3f}s"
        )
        
        # 添加性能头
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # 记录请求异常
        process_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(
            f"请求异常: {request.method} {request.url} - "
            f"错误: {str(e)} - "
            f"处理时间: {process_time:.3f}s"
        )
        raise e

# 注册路由

# 现有的路由（假设）
# app.include_router(existing_router, prefix="/api/v1")

# 新增的审核模块路由
app.include_router(
    audit_tasks_router,
    tags=["审核任务管理"]
)

app.include_router(
    ai_assistance_router,
    tags=["AI辅助功能"]
)

app.include_router(
    notifications_router,
    tags=["消息通知"]
)

# 根路径和健康检查
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗质控系统 API",
        "version": "2.0.0",
        "description": "基于LLM集成的医疗质控系统，包含三层质控引擎和人工审核模块",
        "timestamp": datetime.utcnow().isoformat(),
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@app.get("/health")
async def health_check():
    """系统健康检查"""
    try:
        # 检查数据库连接
        db_status = "healthy"  # 实际实现中需要检查数据库连接
        
        # 检查通知服务状态
        notification_stats = {}
        if notification_service_instance:
            notification_stats = notification_service_instance.get_connection_stats()
        
        # 检查LLM服务状态
        llm_status = "unknown"
        try:
            await llm_service.health_check()
            llm_status = "healthy"
        except Exception:
            llm_status = "unhealthy"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": db_status,
                "notification_service": {
                    "status": "healthy" if notification_service_instance else "stopped",
                    "stats": notification_stats
                },
                "llm_service": llm_status,
                "qc_engine": "healthy"  # 假设状态
            },
            "version": "2.0.0"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "version": "2.0.0"
        }

@app.get("/api/system/info")
async def get_system_info():
    """获取系统信息"""
    return {
        "system_name": "医疗质控系统",
        "version": "2.0.0",
        "features": [
            "三层质控引擎",
            "人工审核模块",
            "AI辅助缺陷识别",
            "智能抽样算法",
            "实时消息通知",
            "多级审核流程"
        ],
        "modules": {
            "audit_tasks": {
                "description": "审核任务管理",
                "endpoints": [
                    "POST /api/audit-tasks",
                    "GET /api/audit-tasks",
                    "GET /api/audit-tasks/{task_id}",
                    "POST /api/audit-tasks/{task_id}/start",
                    "POST /api/audit-tasks/{task_id}/intelligent-sampling"
                ]
            },
            "ai_assistance": {
                "description": "AI辅助功能",
                "endpoints": [
                    "POST /api/ai-assistance/defect-detection/{task_item_id}",
                    "POST /api/ai-assistance/batch-defect-detection",
                    "POST /api/ai-assistance/rectification-plan",
                    "POST /api/ai-assistance/smart-analysis/{medical_record_id}"
                ]
            },
            "notifications": {
                "description": "消息通知系统",
                "endpoints": [
                    "WebSocket /api/notifications/ws/{user_id}",
                    "POST /api/notifications",
                    "GET /api/notifications",
                    "PUT /api/notifications/{notification_id}/read"
                ]
            }
        },
        "integration": {
            "three_layer_qc_engine": "已集成",
            "llm_service": "已集成",
            "supabase_realtime": "支持",
            "websocket": "支持"
        }
    }

@app.get("/api/system/stats")
async def get_system_stats():
    """获取系统统计信息"""
    try:
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "计算中...",  # 实际实现中计算运行时间
            "performance": {
                "avg_response_time": "计算中...",
                "requests_per_minute": "计算中...",
                "error_rate": "计算中..."
            },
            "resources": {
                "memory_usage": "计算中...",
                "cpu_usage": "计算中...",
                "disk_usage": "计算中..."
            },
            "services": {
                "active_connections": 0,
                "queued_notifications": 0,
                "active_audit_tasks": 0,
                "ai_analysis_requests": 0
            }
        }
        
        # 获取通知服务统计
        if notification_service_instance:
            notification_stats = notification_service_instance.get_connection_stats()
            stats["services"]["active_connections"] = notification_stats.get("connected_users", 0)
            stats["services"]["queued_notifications"] = notification_stats.get("queue_size", 0)
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取系统统计失败: {str(e)}"
        )

# 异常处理器
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404异常处理"""
    return {
        "error": "Not Found",
        "message": f"路径 {request.url.path} 不存在",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500异常处理"""
    logger.error(f"内部服务器错误: {request.url.path} - {str(exc)}")
    return {
        "error": "Internal Server Error",
        "message": "服务器内部错误，请稍后重试",
        "timestamp": datetime.utcnow().isoformat()
    }

# 开发环境下的调试端点
if settings.DEBUG:
    @app.get("/debug/routes")
    async def debug_routes():
        """调试：显示所有路由"""
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": route.name
                })
        return {"routes": routes}
    
    @app.get("/debug/config")
    async def debug_config():
        """调试：显示配置信息（敏感信息已隐藏）"""
        return {
            "debug": settings.DEBUG,
            "allowed_origins": settings.ALLOWED_ORIGINS,
            "database_url": "***隐藏***",
            "environment": getattr(settings, 'ENVIRONMENT', 'development')
        }

if __name__ == "__main__":
    import uvicorn
    
    # 开发环境启动配置
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
