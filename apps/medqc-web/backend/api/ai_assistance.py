# AI辅助功能API端点
# 集成现有三层质控引擎的AI辅助功能

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import asyncio

from ..models.audit_models import (
    QCAuditTaskItem, AIDefectSuggestion, DefectAnalysisContext,
    QCDefect, APIResponse, BatchAuditRequest
)
from ..services.ai_defect_service import AIDefectDetectionService
from ..database.database import get_db
from ..auth.dependencies import get_current_user, require_permissions

# 假设现有的三层质控引擎和LLM服务实例
from ..qc_engine.three_layer_engine import three_layer_qc_engine
from ..llm_service.llm_client import llm_service

router = APIRouter(prefix="/api/ai-assistance", tags=["AI辅助功能"])

# 初始化AI缺陷检测服务
ai_defect_service = AIDefectDetectionService(three_layer_qc_engine, llm_service)

@router.post("/defect-detection/{task_item_id}", response_model=APIResponse[List[AIDefectSuggestion]])
async def detect_defects_for_task_item(
    task_item_id: str,
    analysis_context: DefectAnalysisContext,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    为单个审核任务项进行AI辅助缺陷识别
    
    - 集成现有三层质控引擎进行深度分析
    - 使用LLM增强缺陷描述和整改建议
    - 支持多种分析焦点和上下文配置
    """
    try:
        # 获取任务项信息
        task_item = await get_task_item_by_id(task_item_id, db)
        if not task_item:
            raise HTTPException(
                status_code=404,
                detail="审核任务项不存在"
            )
        
        # 执行AI缺陷识别
        defect_suggestions = await ai_defect_service.suggest_defects(
            task_item=task_item,
            context=analysis_context,
            db=db
        )
        
        # 后台任务：记录AI分析日志
        background_tasks.add_task(
            log_ai_analysis,
            task_item_id,
            len(defect_suggestions),
            current_user.id
        )
        
        return APIResponse(
            success=True,
            message=f"AI识别完成，发现 {len(defect_suggestions)} 个潜在缺陷",
            data=defect_suggestions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI缺陷识别失败: {str(e)}"
        )

@router.post("/batch-defect-detection", response_model=APIResponse[Dict[str, List[AIDefectSuggestion]]])
async def batch_detect_defects(
    request: BatchAuditRequest,
    analysis_context: DefectAnalysisContext,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    批量AI缺陷识别
    
    - 支持批量处理多个审核任务项
    - 优化的批量分析算法，提高处理效率
    - 自动负载均衡和错误处理
    """
    try:
        # 获取任务项列表
        task_items = await get_task_items_by_ids(request.task_item_ids, db)
        
        if not task_items:
            raise HTTPException(
                status_code=404,
                detail="未找到有效的审核任务项"
            )
        
        # 执行批量AI缺陷识别
        batch_results = await ai_defect_service.batch_suggest_defects(
            task_items=task_items,
            context=analysis_context,
            db=db
        )
        
        # 统计结果
        total_suggestions = sum(len(suggestions) for suggestions in batch_results.values())
        
        # 后台任务：记录批量分析日志
        background_tasks.add_task(
            log_batch_ai_analysis,
            request.task_id,
            len(task_items),
            total_suggestions,
            current_user.id
        )
        
        return APIResponse(
            success=True,
            message=f"批量AI识别完成，处理 {len(task_items)} 个项目，发现 {total_suggestions} 个潜在缺陷",
            data=batch_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"批量AI缺陷识别失败: {str(e)}"
        )

@router.post("/rectification-plan", response_model=APIResponse[Dict[str, Any]])
async def generate_rectification_plan(
    defects_data: List[Dict[str, Any]],
    medical_record_id: str,
    context: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    生成AI辅助整改计划
    
    - 基于识别的缺陷生成详细整改计划
    - 包含时间估算、优先级排序、资源需求
    - 提供质量检查点和验收标准
    """
    try:
        # 转换缺陷数据为QCDefect对象
        defects = [convert_dict_to_defect(defect_data) for defect_data in defects_data]
        
        # 获取医疗记录数据
        medical_record_data = await get_medical_record_data(medical_record_id, db)
        if not medical_record_data:
            raise HTTPException(
                status_code=404,
                detail="医疗记录不存在"
            )
        
        # 生成整改计划
        rectification_plan = await ai_defect_service.generate_rectification_plan(
            defects=defects,
            medical_record_data=medical_record_data,
            context=context or {}
        )
        
        return APIResponse(
            success=True,
            message="整改计划生成成功",
            data=rectification_plan
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成整改计划失败: {str(e)}"
        )

@router.post("/smart-analysis/{medical_record_id}", response_model=APIResponse[Dict[str, Any]])
async def smart_medical_record_analysis(
    medical_record_id: str,
    analysis_config: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    智能医疗记录分析
    
    - 使用现有三层质控引擎进行全面分析
    - 提供多维度的质量评估
    - 生成详细的分析报告
    """
    try:
        # 获取医疗记录数据
        medical_record_data = await get_medical_record_data(medical_record_id, db)
        if not medical_record_data:
            raise HTTPException(
                status_code=404,
                detail="医疗记录不存在"
            )
        
        # 使用三层质控引擎进行智能分析
        analysis_result = await three_layer_qc_engine.deep_analyze_for_defects(
            record_data=medical_record_data,
            focus_areas=analysis_config.get("focus_areas", []),
            analysis_config=analysis_config
        )
        
        # 增强分析结果
        enhanced_result = await enhance_analysis_result(
            analysis_result, medical_record_data, analysis_config
        )
        
        return APIResponse(
            success=True,
            message="智能分析完成",
            data=enhanced_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能分析失败: {str(e)}"
        )

@router.post("/quality-score-prediction", response_model=APIResponse[Dict[str, Any]])
async def predict_quality_score(
    medical_record_id: str,
    prediction_config: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_ai_assistance"]))
):
    """
    AI质量评分预测
    
    - 基于历史数据和模式识别预测质量评分
    - 提供评分置信区间和影响因素分析
    - 支持多种评分模型和权重配置
    """
    try:
        # 获取医疗记录数据
        medical_record_data = await get_medical_record_data(medical_record_id, db)
        if not medical_record_data:
            raise HTTPException(
                status_code=404,
                detail="医疗记录不存在"
            )
        
        # 使用质控引擎进行评分预测
        prediction_result = await three_layer_qc_engine.predict_quality_score(
            record_data=medical_record_data,
            config=prediction_config
        )
        
        return APIResponse(
            success=True,
            message="质量评分预测完成",
            data=prediction_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"质量评分预测失败: {str(e)}"
        )

@router.get("/analysis-history/{task_item_id}", response_model=APIResponse[List[Dict[str, Any]]])
async def get_ai_analysis_history(
    task_item_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取AI分析历史记录"""
    try:
        history = await get_analysis_history_from_db(task_item_id, limit, db)
        
        return APIResponse(
            success=True,
            message="获取分析历史成功",
            data=history
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取分析历史失败: {str(e)}"
        )

@router.post("/feedback", response_model=APIResponse[Dict[str, Any]])
async def submit_ai_feedback(
    feedback_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    提交AI分析反馈
    
    - 收集用户对AI分析结果的反馈
    - 用于持续改进AI模型性能
    - 支持多种反馈类型和评分
    """
    try:
        # 保存反馈数据
        feedback_result = await save_ai_feedback(
            feedback_data, current_user.id, db
        )
        
        return APIResponse(
            success=True,
            message="反馈提交成功",
            data=feedback_result
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"提交反馈失败: {str(e)}"
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

async def get_medical_record_data(medical_record_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """获取医疗记录数据"""
    # 实现数据库查询逻辑
    pass

def convert_dict_to_defect(defect_data: Dict[str, Any]) -> QCDefect:
    """将字典转换为QCDefect对象"""
    # 实现转换逻辑
    pass

async def enhance_analysis_result(
    analysis_result: Dict[str, Any],
    medical_record_data: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """增强分析结果"""
    # 添加额外的分析维度和可视化数据
    enhanced = {
        **analysis_result,
        "enhanced_insights": {
            "risk_factors": [],
            "improvement_suggestions": [],
            "compliance_status": {},
            "trend_analysis": {}
        }
    }
    return enhanced

async def get_analysis_history_from_db(
    task_item_id: str, 
    limit: int, 
    db: AsyncSession
) -> List[Dict[str, Any]]:
    """从数据库获取分析历史"""
    # 实现数据库查询逻辑
    return []

async def save_ai_feedback(
    feedback_data: Dict[str, Any],
    user_id: str,
    db: AsyncSession
) -> Dict[str, Any]:
    """保存AI反馈"""
    # 实现反馈保存逻辑
    return {"feedback_id": "generated_id"}

# 后台任务函数
async def log_ai_analysis(
    task_item_id: str,
    suggestions_count: int,
    user_id: str
):
    """记录AI分析日志"""
    print(f"AI分析日志: 任务项 {task_item_id}, 建议数 {suggestions_count}, 用户 {user_id}")

async def log_batch_ai_analysis(
    task_id: str,
    items_count: int,
    suggestions_count: int,
    user_id: str
):
    """记录批量AI分析日志"""
    print(f"批量AI分析日志: 任务 {task_id}, 项目数 {items_count}, 建议数 {suggestions_count}, 用户 {user_id}")

# 健康检查端点
@router.get("/health", response_model=APIResponse[Dict[str, Any]])
async def ai_service_health_check():
    """AI辅助服务健康检查"""
    try:
        # 检查三层质控引擎状态
        qc_engine_status = await three_layer_qc_engine.health_check()
        
        # 检查LLM服务状态
        llm_service_status = await llm_service.health_check()
        
        return APIResponse(
            success=True,
            message="AI辅助服务运行正常",
            data={
                "service": "ai_assistance_service",
                "status": "healthy",
                "qc_engine_status": qc_engine_status,
                "llm_service_status": llm_service_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        return APIResponse(
            success=False,
            message="AI辅助服务异常",
            data={
                "service": "ai_assistance_service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
