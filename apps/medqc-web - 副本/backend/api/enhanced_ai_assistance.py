# 增强版AI辅助功能API端点
# 完全替代TypeScript AI服务的Python FastAPI实现

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

from ..models.audit_models import (
    QCAuditTaskItem, AIDefectSuggestion, DefectAnalysisContext,
    QCDefect, APIResponse, BatchAuditRequest
)
from ..services.ai_defect_service import EnhancedAIDefectDetectionService, BatchProcessingConfig, CacheStrategy
from ..database.database import get_db
from ..auth.dependencies import get_current_user, require_permissions

# 假设现有的三层质控引擎和LLM服务实例
from ..qc_engine.three_layer_engine import three_layer_qc_engine
from ..llm_service.llm_client import llm_service

router = APIRouter(prefix="/api/enhanced-ai-assistance", tags=["增强版AI辅助功能"])

# 初始化增强版AI缺陷检测服务
enhanced_ai_service = EnhancedAIDefectDetectionService(
    qc_engine=three_layer_qc_engine,
    llm_service=llm_service,
    config=BatchProcessingConfig(
        batch_size=50,
        max_concurrency=5,
        timeout_seconds=300,
        retry_attempts=2,
        enable_cache=True
    ),
    cache_strategy=CacheStrategy.HYBRID
)

logger = logging.getLogger(__name__)

@router.post("/defect-detection/{task_item_id}", response_model=APIResponse[List[AIDefectSuggestion]])
async def enhanced_detect_defects_for_task_item(
    task_item_id: str,
    analysis_context: DefectAnalysisContext,
    use_cache: bool = Query(True, description="是否使用缓存"),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    增强版AI辅助缺陷识别（单个任务项）
    
    - 完全替代TypeScript实现
    - 多层缓存策略
    - 性能监控和统计
    - 智能错误处理
    """
    try:
        # 获取任务项信息
        task_item = await get_task_item_by_id(task_item_id, db)
        if not task_item:
            raise HTTPException(
                status_code=404,
                detail="审核任务项不存在"
            )
        
        # 执行增强版AI缺陷识别
        defect_suggestions = await enhanced_ai_service.suggest_defects(
            task_item=task_item,
            context=analysis_context,
            db=db,
            use_cache=use_cache
        )
        
        # 后台任务：记录详细的分析日志
        background_tasks.add_task(
            log_enhanced_ai_analysis,
            task_item_id,
            len(defect_suggestions),
            current_user.id,
            use_cache
        )
        
        return APIResponse(
            success=True,
            message=f"增强版AI识别完成，发现 {len(defect_suggestions)} 个潜在缺陷",
            data=defect_suggestions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"增强版AI缺陷识别失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"AI缺陷识别失败: {str(e)}"
        )

@router.post("/batch-defect-detection", response_model=APIResponse[Dict[str, List[AIDefectSuggestion]]])
async def enhanced_batch_detect_defects(
    request: BatchAuditRequest,
    analysis_context: DefectAnalysisContext,
    use_cache: bool = Query(True, description="是否使用缓存"),
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    增强版批量AI缺陷识别
    
    - 优化的批量处理算法
    - 智能分批和并发控制
    - 自动错误恢复
    - 详细的性能统计
    """
    try:
        # 获取任务项列表
        task_items = await get_task_items_by_ids(request.task_item_ids, db)
        
        if not task_items:
            raise HTTPException(
                status_code=404,
                detail="未找到有效的审核任务项"
            )
        
        # 执行增强版批量AI缺陷识别
        batch_results = await enhanced_ai_service.batch_suggest_defects(
            task_items=task_items,
            context=analysis_context,
            db=db,
            use_cache=use_cache
        )
        
        # 统计结果
        total_suggestions = sum(len(suggestions) for suggestions in batch_results.values())
        
        # 后台任务：记录批量分析统计
        background_tasks.add_task(
            log_enhanced_batch_analysis,
            request.task_id,
            len(task_items),
            total_suggestions,
            current_user.id,
            use_cache
        )
        
        return APIResponse(
            success=True,
            message=f"增强版批量AI识别完成，处理 {len(task_items)} 个项目，发现 {total_suggestions} 个潜在缺陷",
            data=batch_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"增强版批量AI缺陷识别失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"批量AI缺陷识别失败: {str(e)}"
        )

@router.get("/performance-stats", response_model=APIResponse[Dict[str, Any]])
async def get_ai_performance_stats(
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """获取AI服务性能统计"""
    try:
        stats = enhanced_ai_service.get_cache_stats()
        
        return APIResponse(
            success=True,
            message="获取性能统计成功",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取性能统计失败: {str(e)}"
        )

@router.post("/clear-cache", response_model=APIResponse[Dict[str, Any]])
async def clear_ai_cache(
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_admin"]))
):
    """清理AI分析缓存"""
    try:
        enhanced_ai_service.clear_cache()
        
        return APIResponse(
            success=True,
            message="AI分析缓存已清理",
            data={"cleared_at": datetime.utcnow().isoformat()}
        )
        
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理缓存失败: {str(e)}"
        )

@router.get("/service-status", response_model=APIResponse[Dict[str, Any]])
async def get_enhanced_ai_service_status():
    """获取增强版AI服务状态"""
    try:
        stats = enhanced_ai_service.get_cache_stats()
        
        # 检查服务健康状态
        health_status = "healthy"
        if stats["performance_stats"]["error_count"] > 10:
            health_status = "degraded"
        
        return APIResponse(
            success=True,
            message="获取服务状态成功",
            data={
                "service": "enhanced_ai_defect_detection",
                "status": health_status,
                "version": "2.0.0",
                "cache_stats": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        return APIResponse(
            success=False,
            message="获取服务状态失败",
            data={
                "service": "enhanced_ai_defect_detection",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# 辅助函数
async def get_task_item_by_id(task_item_id: str, db: AsyncSession) -> Optional[QCAuditTaskItem]:
    """根据ID获取任务项"""
    # 实现数据库查询逻辑
    pass

async def get_task_items_by_ids(task_item_ids: List[str], db: AsyncSession) -> List[QCAuditTaskItem]:
    """根据ID列表获取任务项"""
    # 实现批量数据库查询逻辑
    pass

# 后台任务函数
async def log_enhanced_ai_analysis(
    task_item_id: str,
    suggestions_count: int,
    user_id: str,
    used_cache: bool
):
    """记录增强版AI分析日志"""
    logger.info(
        f"增强版AI分析完成 - 任务项: {task_item_id}, "
        f"建议数: {suggestions_count}, 用户: {user_id}, "
        f"使用缓存: {used_cache}"
    )

async def log_enhanced_batch_analysis(
    task_id: str,
    items_count: int,
    suggestions_count: int,
    user_id: str,
    used_cache: bool
):
    """记录增强版批量AI分析日志"""
    logger.info(
        f"增强版批量AI分析完成 - 任务: {task_id}, "
        f"项目数: {items_count}, 建议数: {suggestions_count}, "
        f"用户: {user_id}, 使用缓存: {used_cache}"
    )

# 服务生命周期管理
@router.on_event("startup")
async def startup_enhanced_ai_service():
    """启动增强版AI服务"""
    logger.info("增强版AI辅助服务已启动")

@router.on_event("shutdown")
async def shutdown_enhanced_ai_service():
    """关闭增强版AI服务"""
    await enhanced_ai_service.cleanup()
    logger.info("增强版AI辅助服务已关闭")
