"""
增强版主API服务
集成层级化医疗文书分类功能
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import logging

# 导入增强版分类API
from enhanced_classification_api import router as classification_router

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="医疗文书分类系统 - 增强版",
    description="基于层级化分类的医疗文书智能识别和质控系统",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(classification_router)

# 健康检查端点
@app.get("/health", summary="健康检查")
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "features": [
            "hierarchical_classification",
            "nursing_document_recognition", 
            "medical_order_recognition",
            "quality_control",
            "statistics"
        ]
    }

# 系统信息端点
@app.get("/system/info", summary="系统信息")
async def get_system_info():
    """获取系统信息和功能列表"""
    return {
        "system": "医疗文书分类系统",
        "version": "2.0.0",
        "description": "基于层级化分类的医疗文书智能识别系统",
        "capabilities": {
            "classification": {
                "hierarchical": True,
                "categories": 7,
                "types": 28,
                "confidence_threshold": 0.5
            },
            "recognition": {
                "nursing_documents": True,
                "medical_orders": True,
                "admission_records": True,
                "progress_notes": True,
                "discharge_records": True,
                "examination_reports": True
            },
            "quality_control": {
                "templates": 4,
                "automated": True,
                "scoring": True
            },
            "statistics": {
                "real_time": True,
                "category_distribution": True,
                "confidence_analysis": True
            }
        },
        "database": {
            "tables": [
                "document_categories_test",
                "document_types_test", 
                "medical_documents_test",
                "qc_templates_test",
                "document_qc_results_test"
            ],
            "views": [
                "document_classification_stats_test"
            ]
        },
        "api_endpoints": {
            "classification": "/api/enhanced-classification/classify",
            "categories": "/api/enhanced-classification/categories",
            "documents": "/api/enhanced-classification/documents/{record_id}",
            "statistics": "/api/enhanced-classification/statistics"
        }
    }

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "服务器内部错误",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# 404处理
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "接口不存在",
            "path": str(request.url.path),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    logger.info("启动增强版医疗文书分类系统...")
    logger.info("功能特性:")
    logger.info("- 层级化文书分类 (7个一级分类, 28个二级分类)")
    logger.info("- 护理文书智能识别")
    logger.info("- 医嘱记录智能识别") 
    logger.info("- 质控模板系统")
    logger.info("- 实时统计分析")
    
    uvicorn.run(
        "main_enhanced:app",
        host="0.0.0.0",
        port=8001,  # 使用不同端口避免冲突
        reload=True,
        log_level="info"
    )
