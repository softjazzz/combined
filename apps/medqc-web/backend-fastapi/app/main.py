"""
FastAPI 主应用
DRG/DIP 系统后端服务
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import time

try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger("drg")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def _noop(*args, **kwargs):
        return None

    logger.remove = _noop
    logger.add = _noop

from app.config import settings
from app.api import coding, drg, auth, case_front_page

# ============================================
# 配置日志
# ============================================
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL
)
logger.add(
    "logs/drg_api_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL
)

# ============================================
# 创建 FastAPI 应用
# ============================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## DRG/DIP 系统后端 API

    提供以下核心功能：

    ### 3.2.1 编码智能辅助
    - **ICD 编码推荐**：使用 LLM 推荐 ICD-10/ICD-9-CM-3 编码
    - **编码校验**：检查编码完整性和逻辑一致性
    - **编码库搜索**：全文搜索 ICD 编码

    ### 3.2.2 自动入组预测
    - **DRG 分组预测**：调用 OpenDRG 引擎进行分组
    - **费用预测**：预估 DRG 基准支付金额
    - **分组历史**：追踪分组版本变更

    ### 3.3 事中监控
    - **实时预警**：费用超标、住院日过长等预警
    - **编码优化建议**：LLM 分析病历后给出的建议

    ### 技术栈
    - **框架**：FastAPI + Uvicorn
    - **数据库**：Supabase (PostgreSQL)
    - **分组引擎**：OpenDRG
    - **LLM**：DeepSeek-V3 (阿里云百炼)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ============================================
# CORS 中间件
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# 请求日志中间件
# ============================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求"""
    start_time = time.time()

    # 记录请求
    logger.info(f"🔵 {request.method} {request.url.path}")

    # 处理请求
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # 记录响应
        logger.info(
            f"✅ {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.2f}ms"
        )

        # 添加处理时间头
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response

    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"❌ {request.method} {request.url.path} - "
            f"Error: {str(e)} - "
            f"Time: {process_time:.2f}ms"
        )
        raise

# ============================================
# 全局异常处理
# ============================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
        }
    )

# ============================================
# 注册路由
# ============================================
# 认证路由（不添加 prefix，因为 auth.router 已经包含了 /api/v1/auth）
app.include_router(
    auth.router,
    tags=["认证"]
)

app.include_router(
    coding.router,
    prefix=settings.API_V1_PREFIX,
    tags=["编码辅助"]
)

app.include_router(
    drg.router,
    prefix=settings.API_V1_PREFIX,
    tags=["DRG分组"]
)

app.include_router(
    case_front_page.router,
    prefix=settings.API_V1_PREFIX,
    tags=["病案首页"]
)

# ============================================
# 根路径和健康检查
# ============================================
@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/api/v1/status", tags=["系统"])
async def api_status():
    """API 状态"""
    return {
        "status": "ok",
        "api_version": "v1",
        "services": {
            "database": "connected",  # TODO: 实际检查数据库连接
            "llm": "available",       # TODO: 实际检查 LLM 服务
            "drg_grouper": "ready"    # TODO: 实际检查 DRG 分组引擎
        }
    }


# ============================================
# 启动和关闭事件
# ============================================
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"📝 日志级别: {settings.LOG_LEVEL}")
    logger.info(f"🌍 CORS 允许源: {settings.CORS_ORIGINS}")
    logger.info(f"🗄️  Supabase URL: {settings.SUPABASE_URL}")
    logger.info(f"🤖 LLM 模型: {settings.DEEPSEEK_MODEL}")
    logger.info(f"🏥 DRG 地区: {settings.OPENDRG_DEFAULT_REGION}")
    logger.info(f"📚 API 文档: http://localhost:8001/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("=" * 60)
    logger.info(f"👋 {settings.APP_NAME} 关闭中...")
    logger.info("=" * 60)


# ============================================
# 主函数（用于开发调试）
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
