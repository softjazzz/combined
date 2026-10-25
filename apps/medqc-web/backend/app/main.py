from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
import os
import logging
from fastapi.middleware.cors import CORSMiddleware
from .core.settings import get_settings
from .core.logging import configure_logging, request_logger_middleware
from .core.otel import configure_otel
from .core.middleware_errors import UnifiedErrorMiddleware
from .core.middleware_api_version import APIVersionMiddleware
from .core.access_control import enforce_default_auth
from .core.http import close_shared_http_resources

logger = logging.getLogger(__name__)
from .routers import system as system_router
from .routers import proxy as proxy_router
from .routers import auth as auth_router
from .routers import records as records_router
from .routers import qc as qc_router
from .routers import qc_sichuan as qc_sichuan_router
from .routers import qc_diagnostics as qc_diagnostics_router
from .routers import runtime_build as runtime_build_router
from .routers import luxian_0609_preproduction as luxian_0609_preproduction_router
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
from .routers import llm_observability_read as llm_observability_read_router
from .routers import medical_records_alias as medical_records_alias_router
from .routers import reports as reports_router
from .routers import appeals as appeals_router
from .routers import remediation as remediation_router
from .routers import department_qc_rules as department_qc_rules_router
from .routers import demo as demo_router
from .routers import frontpage as frontpage_router
from .routers import frontpage_settings as frontpage_settings_router
from .routers import drg as drg_router
from .routers import smart_upload as smart_upload_router
from .routers import dip as dip_router
from .routers import case_front_page as case_front_page_router
from .routers import icd_search as icd_search_router
from .routers import medical_records as medical_records_router_cdm
from .routers import system_config as system_config_router
from .routers import demo_panel as demo_panel_router
from .routers import defects as defects_router
from .routers import dashboard_api as dashboard_api_router
from .routers import emr_render as emr_render_router
from .routers import scoring_rules as scoring_rules_router
from .routers import staff_ranking as staff_ranking_router
from .routers import notifications as notifications_router
from .routers import settlement as settlement_router
from .routers import scoring_config as scoring_config_router
from .routers import sync as sync_router
from .routers import workstation as workstation_router
from .routers import custom_qc as custom_qc_router
from .routers import qc_sample_pools as qc_sample_pools_router
from .routers import rule_validation as rule_validation_router
from .routers import qc_agent as qc_agent_router
from .routers import sqlbot as sqlbot_router
from .routers import clinical_completeness as clinical_completeness_router
from .routers import pre_grouping as pre_grouping_router
from .routers import payment_monitoring as payment_monitoring_router
from .routers import product_activation as product_activation_router
from .routers import quality_reports as quality_reports_router
from .routers import staff_work_analysis as staff_work_analysis_router
from .routers import manual_quality_reports as manual_quality_reports_router
from .routers import manual_defect_reviews as manual_defect_reviews_router
from .routers import core_system_reports as core_system_reports_router
from .routers import special_record_reports as special_record_reports_router
from .routers import defect_rectifications as defect_rectifications_router
from .routers import modern_appeals as modern_appeals_router
from .routers import case_communications as case_communications_router
from .routers import record_reviews as record_reviews_router
# Mount legacy routes to preserve all routes during migration
try:
    from ..main_api import app as legacy_app  # type: ignore
except Exception:  # pragma: no cover
    legacy_app = None


class UTF8JSONResponse(JSONResponse):
    """JSON response with explicit charset=utf-8 for Windows CJK compatibility."""
    media_type = "application/json; charset=utf-8"


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
    configure_logging()
    settings = get_settings()
    logger.info("LLM diagnostics at startup: %s", settings.llm_diagnostics())

    app = FastAPI(
        title="医疗质控系统API",
        description="模块化后端应用（重构入口）",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        dependencies=[Depends(enforce_default_auth)],
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
        # 任务详情 409 时附带任务状态，跨域部署下前端也需能读取
        expose_headers=["X-Batch-Job-Status", "Content-Disposition", "X-Special-Classification-Version",
                        "X-Special-Standard-Id", "X-Special-Standard-Version", "X-Special-Binding-Version"],
    )

    # API Version middleware (with backward compatibility)
    # 禁用重定向，避免307导致CORS问题（前端已使用/api/v1/*路径）
    app.add_middleware(APIVersionMiddleware, enable_legacy_redirect=False)
    # Logging middleware
    app.middleware("http")(request_logger_middleware)
    # Unified error shape
    app.add_middleware(UnifiedErrorMiddleware)

    @app.middleware("http")
    async def trace_header_writeback_middleware(request: Request, call_next):
        """确保最终响应头中的 X-Trace-ID 与请求 trace_id 保持一致。"""
        response = await call_next(request)
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            response.headers["X-Trace-ID"] = str(trace_id)
        return response

    # P2-OBS-01: optional OTel bootstrap (fail-open, no startup blocking).
    configure_otel(app)

    # Global exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        trace_id = getattr(request.state, "trace_id", "unknown")

        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={"trace_id": trace_id, "path": request.url.path}
        )

        response_headers = {"X-Trace-ID": trace_id}
        if exc.headers:
            response_headers.update(exc.headers)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "trace_id": trace_id,
            },
            headers=response_headers,
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
    app.include_router(qc_diagnostics_router.router)
    app.include_router(runtime_build_router.router)
    app.include_router(luxian_0609_preproduction_router.router)
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
    app.include_router(llm_observability_read_router.router)
    # Compatibility alias for /api/medical-records endpoints
    app.include_router(medical_records_alias_router.router)
    app.include_router(reports_router.router)
    app.include_router(appeals_router.router)
    app.include_router(remediation_router.router)
    app.include_router(defect_rectifications_router.router)
    app.include_router(modern_appeals_router.router)
    app.include_router(case_communications_router.router)
    app.include_router(record_reviews_router.router)
    # Department QC Rules (Migration 009)
    app.include_router(department_qc_rules_router.router)
    # Demo page for LX33 rules (no auth required)
    app.include_router(demo_router.router)
    # Front page auto-generation (demo + future real extraction)
    app.include_router(frontpage_router.router)
    # Front page extraction settings
    app.include_router(frontpage_settings_router.router)
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
    # Dashboard 统计聚合（待办统计/表现排名/概览）
    app.include_router(dashboard_api_router.router)
    # EMR 文书渲染（文书内容+缺陷标注）
    app.include_router(emr_render_router.router)
    # 评分标准配置（扣分规则 CRUD + 导入导出）
    app.include_router(scoring_rules_router.router)
    # 质控员工作量排名
    app.include_router(staff_ranking_router.router)
    # 通知与申诉（消息+整改跟踪+问题闭环）
    app.include_router(notifications_router.router)
    # 医保结算清单（查询+质控+导出）
    app.include_router(settlement_router.router)
    # 甲乙丙阈值配置
    app.include_router(scoring_config_router.router)
    # 数据同步（PG 同步链路）
    app.include_router(sync_router.router)
    # Workstation V4 聚合工作台
    app.include_router(workstation_router.router)
    # 自定义质控点体验中心
    app.include_router(custom_qc_router.router)
    # 客户人工问题样本池
    app.include_router(qc_sample_pools_router.router)
    # 规则验收（以规则为中心的测试病例、运行、复核与批准）
    app.include_router(rule_validation_router.router)
    # 受控质控 Agent 工具层
    app.include_router(qc_agent_router.router)
    # SQLBot 独立问数嵌入配置
    app.include_router(sqlbot_router.router)
    # 诊断及手术操作完整性校验
    app.include_router(clinical_completeness_router.router)
    # 事前自动模拟入组
    app.include_router(pre_grouping_router.router)
    # 医保付费监测
    app.include_router(payment_monitoring_router.router)
    app.include_router(product_activation_router.router)
    app.include_router(quality_reports_router.router)
    app.include_router(staff_work_analysis_router.router)
    app.include_router(manual_quality_reports_router.router)
    app.include_router(manual_defect_reviews_router.router)
    app.include_router(core_system_reports_router.router)
    app.include_router(special_record_reports_router.router)

    # Include legacy routes afterwards to keep compatibility
    # Temporarily disabled to avoid route conflicts with semantic-rules
    # if legacy_app is not None:
    #     app.include_router(legacy_app.router)  # type: ignore[attr-defined]

    # Startup event: 初始化四川质控服务
    @app.on_event("startup")
    async def startup_event():
        """应用启动时初始化"""
        from .core.acceptance_startup import resolve_startup_mode, validate_acceptance_schema

        startup_mode = resolve_startup_mode(
            os.getenv("MEDQC_STARTUP_MODE"), environment=settings.ENV,
        )
        runtime_build_router.initialize_runtime_build(app)
        logger.info("🚀 应用启动中...")
        strict_startup_checks = (
            settings.ENV.lower() == "production"
            or os.getenv("STRICT_STARTUP_CHECKS", "false").lower() in {"1", "true", "yes"}
        )

        # P0-SEC-05: production must not boot with built-in demo users.
        from .storage.memory import assert_no_default_demo_users_in_production
        assert_no_default_demo_users_in_production(settings.ENV)

        # 前置校验 DATA_SOURCE（ADR-2026-03-16：启动即失败）
        from .database.repository import validate_data_source
        validate_data_source()

        if startup_mode == "acceptance":
            from .database.connection import DB_SCHEMA_MODE, engine

            validate_acceptance_schema(engine, schema_mode=DB_SCHEMA_MODE)
            app.state.startup_mode = startup_mode
            logger.info("验收启动结构检查通过；不执行DDL、后台预热或旧任务恢复")
            return

        try:
            # 初始化 CDM 数据库
            from .database import init_db
            init_db()
            # 预热可持久化后台任务服务，启动时恢复未完成任务。
            from .services.smart_upload_async_service import get_smart_upload_async_service
            from .services.drg.batch_task_service import get_batch_task_manager

            get_smart_upload_async_service()
            get_batch_task_manager()
            try:
                from .services.local_icd_service import _get_icd_data

                _get_icd_data()
                logger.info("✅ 本地 ICD 编码库预热完成")
            except Exception:
                logger.warning("本地 ICD 编码库预热失败，将按需加载", exc_info=True)

            try:
                from .services.llm_config_loader import LLMConfigLoader

                await LLMConfigLoader.load_config(config_name="default", user_id=None)
                logger.info("✅ LLM 默认配置预热完成")
            except Exception:
                logger.warning("LLM 默认配置预热失败，将按需加载", exc_info=True)

            # 只重投尚未领取的 LX0609 叶任务；Worker 再校验冻结模型/构建身份。
            qc_sichuan_router.resume_queued_luxian_0609_workspace_jobs()
            qc_sichuan_router.start_luxian_0609_task_recovery_monitor()

            # 生产可启用 SC 规则来源持续巡检（巡检接口等价 /rules/source）
            qc_sichuan_router.start_rule_source_monitor()
            logger.info("ℹ️ 跳过启动阶段的四川质控服务初始化（将按需懒加载）")
        except Exception as exc:
            logger.error(f"❌ 启动初始化失败: {exc}")
            if strict_startup_checks:
                raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭时清理后台任务。"""
        try:
            await qc_sichuan_router.stop_luxian_0609_task_recovery_monitor()
            await qc_sichuan_router.stop_rule_source_monitor()
        except Exception:
            logger.warning("停止 SC 规则来源巡检任务失败", exc_info=True)
        finally:
            close_shared_http_resources()

    return app


app = create_app()
