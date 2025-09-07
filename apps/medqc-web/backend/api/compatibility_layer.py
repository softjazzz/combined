# API兼容性层
# 提供向后兼容性，确保现有前端代码无缝迁移到增强版API

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

from .unified_api_standards import (
    UnifiedAPIResponse, ErrorResponse, APIVersion, 
    create_success_response, create_error_response,
    api_performance_monitor, APIPathStandards
)
from .enhanced_ai_assistance import router as enhanced_ai_router
from .enhanced_audit_tasks import router as enhanced_audit_router
from ..database.database import get_db
from ..auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

# 兼容性路由器
compatibility_router = APIRouter(prefix="/api/v1", tags=["API兼容性层"])

# 请求转换器
class RequestTransformer:
    """请求格式转换器"""
    
    @staticmethod
    def transform_ai_assistance_request(legacy_request: Dict[str, Any]) -> Dict[str, Any]:
        """转换AI辅助请求格式"""
        
        # 将v1格式转换为v2格式
        transformed = {
            "task_item_id": legacy_request.get("taskItemId"),
            "analysis_context": {
                "medical_record": legacy_request.get("medicalRecord", {}),
                "audit_level": legacy_request.get("auditLevel", "LEVEL_2"),
                "reviewer_expertise": legacy_request.get("reviewerExpertise", [])
            },
            "use_cache": legacy_request.get("useCache", True)
        }
        
        return transformed
    
    @staticmethod
    def transform_audit_task_request(legacy_request: Dict[str, Any]) -> Dict[str, Any]:
        """转换审核任务请求格式"""
        
        # 将v1格式转换为v2格式
        transformed = {
            "task_name": legacy_request.get("taskName"),
            "task_type": legacy_request.get("taskType"),
            "audit_level": legacy_request.get("auditLevel"),
            "audit_scope": {
                "departments": legacy_request.get("departments", []),
                "document_types": legacy_request.get("documentTypes", []),
                "date_range": legacy_request.get("dateRange"),
                "patient_types": legacy_request.get("patientTypes", [])
            },
            "sampling_config": {
                "sampling_method": legacy_request.get("samplingMethod", "stratified"),
                "total_sample_size": legacy_request.get("totalSampleSize"),
                "sampling_ratio": legacy_request.get("samplingRatio", 0.1),
                "stratification_rules": legacy_request.get("stratificationRules", [])
            },
            "assigned_reviewers": legacy_request.get("assignedReviewers", []),
            "planned_start_date": legacy_request.get("plannedStartDate"),
            "planned_end_date": legacy_request.get("plannedEndDate"),
            "description": legacy_request.get("description"),
            "priority": legacy_request.get("priority", 5)
        }
        
        return transformed

# 响应转换器
class ResponseTransformer:
    """响应格式转换器"""
    
    @staticmethod
    def transform_to_legacy_format(enhanced_response: UnifiedAPIResponse) -> Dict[str, Any]:
        """将增强版响应转换为v1格式"""
        
        legacy_response = {
            "success": enhanced_response.success,
            "message": enhanced_response.message,
            "data": enhanced_response.data
        }
        
        # 添加错误信息（如果有）
        if enhanced_response.errors:
            legacy_response["errors"] = enhanced_response.errors
        
        # 添加警告信息（如果有）
        if enhanced_response.warnings:
            legacy_response["warnings"] = enhanced_response.warnings
        
        return legacy_response
    
    @staticmethod
    def transform_paginated_response(enhanced_response: UnifiedAPIResponse) -> Dict[str, Any]:
        """转换分页响应格式"""
        
        if not enhanced_response.data:
            return ResponseTransformer.transform_to_legacy_format(enhanced_response)
        
        paginated_data = enhanced_response.data
        
        return {
            "success": enhanced_response.success,
            "message": enhanced_response.message,
            "data": {
                "items": paginated_data.get("items", []),
                "total": paginated_data.get("total", 0),
                "page": paginated_data.get("page", 1),
                "pageSize": paginated_data.get("page_size", 20),
                "totalPages": paginated_data.get("total_pages", 0)
            }
        }

# AI辅助功能兼容性端点
@compatibility_router.post("/ai-assistance/defect-detection/{task_item_id}")
@api_performance_monitor("兼容性AI缺陷识别")
async def legacy_detect_defects(
    task_item_id: str,
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    兼容性AI缺陷识别端点
    自动转发到增强版API并转换响应格式
    """
    try:
        logger.info(f"兼容性API调用 - AI缺陷识别: {task_item_id}")
        
        # 转换请求格式
        transformed_request = RequestTransformer.transform_ai_assistance_request(request_data)
        
        # 调用增强版API（内部调用）
        from .enhanced_ai_assistance import enhanced_detect_defects_for_task_item
        
        enhanced_response = await enhanced_detect_defects_for_task_item(
            task_item_id=task_item_id,
            analysis_context=transformed_request["analysis_context"],
            use_cache=transformed_request["use_cache"],
            background_tasks=None,  # 兼容性调用不使用后台任务
            db=db,
            current_user=current_user,
            _=None
        )
        
        # 转换响应格式
        legacy_response = ResponseTransformer.transform_to_legacy_format(enhanced_response)
        
        logger.info("兼容性API调用成功")
        return legacy_response
        
    except Exception as e:
        logger.error(f"兼容性API调用失败: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"AI缺陷识别失败: {str(e)}",
            "data": None,
            "errors": [str(e)]
        }

@compatibility_router.post("/ai-assistance/batch-defect-detection")
@api_performance_monitor("兼容性批量AI缺陷识别")
async def legacy_batch_detect_defects(
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    兼容性批量AI缺陷识别端点
    """
    try:
        logger.info("兼容性API调用 - 批量AI缺陷识别")
        
        # 转换请求格式
        batch_request = {
            "task_id": request_data.get("taskId"),
            "task_item_ids": request_data.get("taskItemIds", []),
            "batch_notes": request_data.get("batchNotes", "兼容性批量处理")
        }
        
        analysis_context = RequestTransformer.transform_ai_assistance_request(
            request_data.get("analysisContext", {})
        )["analysis_context"]
        
        # 调用增强版API
        from .enhanced_ai_assistance import enhanced_batch_detect_defects
        
        enhanced_response = await enhanced_batch_detect_defects(
            request=batch_request,
            analysis_context=analysis_context,
            use_cache=request_data.get("useCache", True),
            background_tasks=None,
            db=db,
            current_user=current_user,
            _=None
        )
        
        # 转换响应格式
        legacy_response = ResponseTransformer.transform_to_legacy_format(enhanced_response)
        
        return legacy_response
        
    except Exception as e:
        logger.error(f"兼容性批量API调用失败: {e}")
        return {
            "success": False,
            "message": f"批量AI缺陷识别失败: {str(e)}",
            "data": {},
            "errors": [str(e)]
        }

# 审核任务管理兼容性端点
@compatibility_router.post("/audit-tasks")
@api_performance_monitor("兼容性创建审核任务")
async def legacy_create_audit_task(
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    兼容性创建审核任务端点
    """
    try:
        logger.info(f"兼容性API调用 - 创建审核任务: {request_data.get('taskName')}")
        
        # 转换请求格式
        transformed_request = RequestTransformer.transform_audit_task_request(request_data)
        
        # 调用增强版API
        from .enhanced_audit_tasks import create_enhanced_audit_task
        
        enhanced_response = await create_enhanced_audit_task(
            request=transformed_request,
            background_tasks=None,
            db=db,
            current_user=current_user,
            _=None
        )
        
        # 转换响应格式
        legacy_response = ResponseTransformer.transform_to_legacy_format(enhanced_response)
        
        return legacy_response
        
    except Exception as e:
        logger.error(f"兼容性创建任务失败: {e}")
        return {
            "success": False,
            "message": f"创建审核任务失败: {str(e)}",
            "data": None,
            "errors": [str(e)]
        }

@compatibility_router.get("/audit-tasks")
@api_performance_monitor("兼容性获取审核任务列表")
async def legacy_get_audit_tasks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    兼容性获取审核任务列表端点
    """
    try:
        # 获取查询参数
        query_params = dict(request.query_params)
        
        # 转换参数格式
        page = int(query_params.get("page", 1))
        page_size = int(query_params.get("pageSize", 20))
        
        # 调用增强版API
        from .enhanced_audit_tasks import get_enhanced_audit_tasks
        
        enhanced_response = await get_enhanced_audit_tasks(
            page=page,
            page_size=page_size,
            task_type=query_params.get("taskType"),
            audit_level=query_params.get("auditLevel"),
            status=query_params.get("status"),
            created_by=query_params.get("createdBy"),
            search=query_params.get("search"),
            db=db,
            current_user=current_user
        )
        
        # 转换响应格式
        legacy_response = ResponseTransformer.transform_paginated_response(enhanced_response)
        
        return legacy_response
        
    except Exception as e:
        logger.error(f"兼容性获取任务列表失败: {e}")
        return {
            "success": False,
            "message": f"获取审核任务列表失败: {str(e)}",
            "data": {"items": [], "total": 0},
            "errors": [str(e)]
        }

# API重定向端点
@compatibility_router.get("/redirect-info")
async def get_api_redirect_info():
    """
    获取API重定向信息
    帮助客户端了解新的API端点
    """
    return create_success_response(
        data={
            "message": "API已升级到v2版本",
            "current_version": "v1",
            "latest_version": "v2",
            "migration_guide": "/docs/api-migration-guide",
            "endpoint_mappings": {
                "/api/v1/ai-assistance/*": "/api/v2/enhanced-ai-assistance/*",
                "/api/v1/audit-tasks/*": "/api/v2/enhanced-audit-tasks/*"
            },
            "deprecation_timeline": {
                "v1_sunset_date": "2025-06-01",
                "migration_deadline": "2025-05-01",
                "support_end_date": "2025-07-01"
            }
        },
        message="API重定向信息获取成功"
    )

# 健康检查端点
@compatibility_router.get("/health")
async def compatibility_health_check():
    """兼容性层健康检查"""
    try:
        # 检查增强版服务状态
        from .enhanced_ai_assistance import get_enhanced_ai_service_status
        from .enhanced_audit_tasks import enhanced_audit_service_health_check
        
        ai_health = await get_enhanced_ai_service_status()
        audit_health = await enhanced_audit_service_health_check()
        
        overall_status = "healthy"
        if (not ai_health.success or not audit_health.success):
            overall_status = "degraded"
        
        return create_success_response(
            data={
                "compatibility_layer": "healthy",
                "enhanced_services": {
                    "ai_assistance": ai_health.data.get("status", "unknown"),
                    "audit_tasks": audit_health.data.get("status", "unknown")
                },
                "overall_status": overall_status,
                "api_version": "v1_compatibility",
                "timestamp": datetime.utcnow().isoformat()
            },
            message="兼容性层运行正常"
        )
        
    except Exception as e:
        return create_error_response(
            message="兼容性层健康检查失败",
            error_code="COMPATIBILITY_HEALTH_CHECK_FAILED",
            debug_info={"error": str(e)}
        )

# 使用统计端点
@compatibility_router.get("/usage-stats")
async def get_compatibility_usage_stats():
    """获取兼容性层使用统计"""
    # 这里可以实现详细的使用统计跟踪
    return create_success_response(
        data={
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "most_used_endpoints": [],
            "migration_progress": {
                "clients_using_v1": 0,
                "clients_using_v2": 0,
                "migration_rate": 0.0
            }
        },
        message="兼容性层使用统计获取成功"
    )
