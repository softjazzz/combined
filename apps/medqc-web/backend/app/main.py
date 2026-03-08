from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
import os
import logging
from fastapi.middleware.cors import CORSMiddleware
from .core.settings import get_settings
from .core.logging import configure_logging, request_logger_middleware
from .core.middleware_errors import UnifiedErrorMiddleware
from .core.middleware_api_version import APIVersionMiddleware

logger = logging.getLogger(__name__)
from .routers import system as system_router
from .routers import proxy as proxy_router
from .routers import auth as auth_router
from .routers import records as records_router
from .routers import qc as qc_router
from .routers import qc_sichuan as qc_sichuan_router
from .routers import qc_settings as qc_settings_router
from .routers import tools as tools_router
from .routers import ingest as ingest_router
from .routers import medical_documents as medical_documents_router
from .routers import debug as debug_router
from .routers import llm_info as llm_info_router
from .routers import qc_llm_configs as qc_llm_configs_router
from .routers import semantic_rules as semantic_rules_router
from .routers import tasks as tasks_router
from .routers import classification as classification_router
from .routers import llm_configs as llm_configs_router
from .routers import medical_records_alias as medical_records_alias_router
from .routers import reports as reports_router
from .routers import appeals as appeals_router
from .routers import remediation as remediation_router
from .routers import department_qc_rules as department_qc_rules_router
from .routers import demo as demo_router
from .routers import frontpage as frontpage_router
from .routers import drg as drg_router
from .routers import smart_upload as smart_upload_router
from .routers import dip as dip_router
from .routers import case_front_page as case_front_page_router
from .routers import icd_search as icd_search_router
from .routers import medical_records as medical_records_router_cdm
from .routers import system_config as system_config_router
from .routers import demo_panel as demo_panel_router
from .routers import defects as defects_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Mount legacy routes to preserve all routes during migration
try:
    from ..main_api import app as legacy_app  # type: ignore
except Exception:  # pragma: no cover
    legacy_app = None


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例

    该函数负责:
    1. 加载配置和初始化日志
    2. 配置 CORS 跨域策略
    3. 注册中间件（API 版本控制、日志记录、错误处理）
    4. 注册全局异常处理器
    5. 注册所有业务路由
    6. 挂载静态文件服务

    Returns:
        FastAPI: 配置完成的 FastAPI 应用实例

    Middleware 执行顺序（按注册顺序逆序执行）:
        1. APIVersionMiddleware - API 版本控制和向后兼容
        2. request_logger_middleware - 请求/响应日志记录
        3. UnifiedErrorMiddleware - 统一错误格式处理
        4. CORSMiddleware - 跨域资源共享

    Example:
        >>> app = create_app()
        >>> # 使用 uvicorn 运行
        >>> import uvicorn
        >>> uvicorn.run(app, host="0.0.0.0", port=8001)
    """
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="医疗质控系统API",
        description="模块化后端应用（重构入口）",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    # Normalize origins: pydantic AnyHttpUrl renders with trailing '/',
    # but CORS matching expects exact origin without trailing slash
    normalized_origins = [str(o).rstrip("/") for o in settings.CORS_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=normalized_origins or [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # API Version middleware (with backward compatibility)
    # 禁用重定向，避免307导致CORS问题（前端已使用/api/v1/*路径）
    app.add_middleware(APIVersionMiddleware, enable_legacy_redirect=False)
    # Logging middleware
    app.middleware("http")(request_logger_middleware)
    # Unified error shape
    app.add_middleware(UnifiedErrorMiddleware)

    # Global exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        trace_id = getattr(request.state, "trace_id", "unknown")

        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={"trace_id": trace_id, "path": request.url.path}
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "trace_id": trace_id,
            },
            headers={"X-Trace-ID": trace_id}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误"""
        trace_id = getattr(request.state, "trace_id", "unknown")

        logger.warning(
            f"Validation Error: {exc.errors()}",
            extra={"trace_id": trace_id, "path": request.url.path}
        )

        # 格式化验证错误信息
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "请求参数验证失败",
                "code": "VALIDATION_ERROR",
                "trace_id": trace_id,
                "details": errors
            },
            headers={"X-Trace-ID": trace_id}
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理所有其他异常"""
        trace_id = getattr(request.state, "trace_id", "unknown")

        import traceback
        tb = traceback.format_exc()

        logger.error(
            f"Internal Server Error: {str(exc)}",
            extra={"trace_id": trace_id, "path": request.url.path, "traceback": tb}
        )

        # 在生产环境中不暴露详细的错误信息
        error_detail = str(exc) if logger.level == logging.DEBUG else "服务器内部错误"

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": error_detail,
                "code": "INTERNAL_ERROR",
                "trace_id": trace_id,
                # 只在调试模式下返回堆栈信息
                **({"traceback": tb} if logger.level == logging.DEBUG else {})
            },
            headers={"X-Trace-ID": trace_id}
        )

    # Routers (new ones first so they can override legacy equivalents)
    app.include_router(system_router.router)
    app.include_router(proxy_router.router)
    app.include_router(auth_router.router)
    app.include_router(records_router.router)
    app.include_router(qc_router.router)
    app.include_router(qc_sichuan_router.router)
    app.include_router(qc_settings_router.router)
    app.include_router(tools_router.router)
    app.include_router(ingest_router.router)
    app.include_router(medical_documents_router.router)
    app.include_router(debug_router.router)
    app.include_router(llm_info_router.router)
    app.include_router(qc_llm_configs_router.router)
    app.include_router(semantic_rules_router.router)
    app.include_router(tasks_router.router)
    app.include_router(classification_router.router)
    app.include_router(llm_configs_router.router)
    # Compatibility alias for /api/medical-records endpoints
    app.include_router(medical_records_alias_router.router)
    app.include_router(reports_router.router)
    app.include_router(appeals_router.router)
    app.include_router(remediation_router.router)
    # Department QC Rules (Migration 009)
    app.include_router(department_qc_rules_router.router)
    # Demo page for LX33 rules (no auth required)
    app.include_router(demo_router.router)
    # Front page auto-generation (demo + future real extraction)
    app.include_router(frontpage_router.router)
    # DRG/DIP demo APIs (to support DRG pages in web)
    app.include_router(case_front_page_router.router)
    app.include_router(drg_router.router)
    # 智能上传 + 字段映射 + 报表生成（从 drg 项目迁移）
    app.include_router(smart_upload_router.router)
    # DIP 入组预测 (泸州市)
    app.include_router(dip_router.router)
    # ICD 编码搜索（基于本地编码库 JSON）
    app.include_router(icd_search_router.router)
    # CDM 病案数据 API（连接 Repository 层）
    app.include_router(medical_records_router_cdm.router)
    # 系统配置与 ETL 同步管理
    app.include_router(system_config_router.router)
    # 演示面板 API (P5/P7/P8)
    app.include_router(demo_panel_router.router)
    # 缺陷操作管理（催办/整改/审核/导出）
    app.include_router(defects_router.router)

    # Static files: expose /downloads for exported reports
    downloads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "downloads"))
    os.makedirs(downloads_dir, exist_ok=True)
    app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")

    # Include legacy routes afterwards to keep compatibility
    # Temporarily disabled to avoid route conflicts with semantic-rules
    # if legacy_app is not None:
    #     app.include_router(legacy_app.router)  # type: ignore[attr-defined]

    # Startup event: 初始化四川质控服务
    @app.on_event("startup")
    async def startup_event():
        """应用启动时初始化四川质控服务"""
        logger.info("🚀 应用启动中...")
        try:
            # 初始化 CDM 数据库
            from .database import init_db
            init_db()
            logger.info("ℹ️ 跳过启动阶段的四川质控服务初始化（将按需懒加载）")
        except Exception as exc:
            logger.error(f"❌ 启动初始化失败: {exc}")

    return app


app = create_app()
