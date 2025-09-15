"""
质控引擎 API 接口
提供 RESTful API 用于规则评估
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from .evaluator import engine, EvaluationResult
from .repository import repository
from .audit import audit_logger
from .metrics import metrics_collector
from .dsl import TriggerEvent


# API 模型定义
class EvaluateRequest(BaseModel):
    """评估请求"""
    event_type: Optional[str] = Field(None, description="触发事件类型")
    context: Dict[str, Any] = Field(..., description="评估上下文")
    rule_ids: Optional[List[int]] = Field(None, description="指定规则ID列表")


class BatchEvaluateRequest(BaseModel):
    """批量评估请求"""
    event_type: Optional[str] = Field(None, description="触发事件类型")
    contexts: List[Dict[str, Any]] = Field(..., description="评估上下文列表")
    rule_ids: Optional[List[int]] = Field(None, description="指定规则ID列表")


class EvaluateResponse(BaseModel):
    """评估响应"""
    decision: str = Field(..., description="决策结果: pass/warn/block")
    hits: List[Dict[str, Any]] = Field(default_factory=list, description="命中的规则")
    execution_time_ms: float = Field(..., description="执行时间（毫秒）")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class BatchEvaluateResponse(BaseModel):
    """批量评估响应"""
    results: List[EvaluateResponse] = Field(..., description="评估结果列表")
    total_execution_time_ms: float = Field(..., description="总执行时间（毫秒）")


class ReloadResponse(BaseModel):
    """重载响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    stats: Optional[Dict[str, Any]] = Field(None, description="统计信息")


# 创建路由器
router = APIRouter(prefix="/api/engine", tags=["QC Engine"])

# 安全认证（可选）
security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户（简化版，实际应验证 token）"""
    if credentials:
        # 这里应该验证 token 并返回用户信息
        # 暂时返回 None，表示匿名用户
        return None
    return None


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    request: EvaluateRequest,
    current_user=Depends(get_current_user)
):
    """
    执行单次规则评估
    
    Args:
        request: 评估请求
        current_user: 当前用户（可选）
    
    Returns:
        评估结果
    """
    try:
        # 解析事件类型
        event_type = None
        if request.event_type:
            try:
                event_type = TriggerEvent(request.event_type)
            except ValueError:
                # 无效的事件类型，忽略
                pass
        
        # 执行评估
        result = engine.evaluate(
            event_type=event_type,
            context=request.context,
            rule_ids=request.rule_ids
        )
        
        # 记录审计日志
        visit_id = request.context.get('visit', {}).get('id')
        user_id = getattr(current_user, 'id', None) if current_user else None
        audit_logger.log_evaluation(
            event_type=event_type,
            context=request.context,
            result=result,
            visit_id=visit_id,
            user_id=user_id
        )
        
        # 记录性能指标
        metrics_collector.record_execution(
            event_type=request.event_type,
            execution_time_ms=result.execution_time_ms,
            rules_evaluated=result.metadata.get('total_rules_evaluated', 0),
            rules_hit=len(result.hits),
            decision=result.decision.value
        )
        
        # 构建响应
        return EvaluateResponse(
            decision=result.decision.value,
            hits=[
                {
                    'rule_id': hit.rule_id,
                    'rule_code': hit.rule_code,
                    'rule_name': hit.rule_name,
                    'severity': hit.severity.value,
                    'messages': hit.messages,
                    'metadata': hit.metadata
                }
                for hit in result.hits
            ],
            execution_time_ms=result.execution_time_ms,
            metadata=result.metadata
        )
        
    except Exception as e:
        metrics_collector.record_error()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-evaluate", response_model=BatchEvaluateResponse)
async def batch_evaluate(
    request: BatchEvaluateRequest,
    current_user=Depends(get_current_user)
):
    """
    执行批量规则评估
    
    Args:
        request: 批量评估请求
        current_user: 当前用户（可选）
    
    Returns:
        批量评估结果
    """
    try:
        import time
        start_time = time.perf_counter()
        
        # 解析事件类型
        event_type = None
        if request.event_type:
            try:
                event_type = TriggerEvent(request.event_type)
            except ValueError:
                pass
        
        # 执行批量评估
        results = engine.batch_evaluate(
            event_type=event_type,
            contexts=request.contexts,
            rule_ids=request.rule_ids
        )
        
        # 记录审计日志
        user_id = getattr(current_user, 'id', None) if current_user else None
        audit_logger.log_batch_evaluation(
            event_type=event_type,
            contexts=request.contexts,
            results=results,
            user_id=user_id
        )
        
        # 记录性能指标（汇总）
        total_rules_evaluated = sum(
            r.metadata.get('total_rules_evaluated', 0) for r in results
        )
        total_rules_hit = sum(len(r.hits) for r in results)
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        metrics_collector.record_execution(
            event_type=request.event_type,
            execution_time_ms=total_time,
            rules_evaluated=total_rules_evaluated,
            rules_hit=total_rules_hit,
            decision='batch'
        )
        
        # 构建响应
        response_results = []
        for result in results:
            response_results.append(
                EvaluateResponse(
                    decision=result.decision.value,
                    hits=[
                        {
                            'rule_id': hit.rule_id,
                            'rule_code': hit.rule_code,
                            'rule_name': hit.rule_name,
                            'severity': hit.severity.value,
                            'messages': hit.messages,
                            'metadata': hit.metadata
                        }
                        for hit in result.hits
                    ],
                    execution_time_ms=result.execution_time_ms,
                    metadata=result.metadata
                )
            )
        
        return BatchEvaluateResponse(
            results=response_results,
            total_execution_time_ms=total_time
        )
        
    except Exception as e:
        metrics_collector.record_error()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload", response_model=ReloadResponse)
async def reload_rules(
    force_json: bool = Body(False, description="是否强制从JSON加载"),
    current_user=Depends(get_current_user)
):
    """
    重新加载规则
    
    Args:
        force_json: 是否强制从 JSON 加载
        current_user: 当前用户（需要管理员权限）
    
    Returns:
        重载结果
    """
    try:
        # TODO: 检查管理员权限
        # if not current_user or not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="需要管理员权限")
        
        # 重新加载规则（load_rules 内部会清理并预编译）
        rule_set = repository.load(force_json=force_json)
        engine.load_rules(rule_set)
        
        # 获取统计信息
        stats = {
            'repository': repository.get_stats(),
            'engine': engine.get_stats()
        }
        
        return ReloadResponse(
            success=True,
            message=f"成功加载 {len(rule_set.rules)} 条规则",
            stats=stats
        )
        
    except Exception as e:
        return ReloadResponse(
            success=False,
            message=str(e),
            stats=None
        )


@router.get("/stats")
async def get_stats():
    """
    获取引擎统计信息
    
    Returns:
        统计信息
    """
    return {
        'repository': repository.get_stats(),
        'engine': engine.get_stats(),
        'metrics': {
            'summary': metrics_collector.get_stats(),
            'percentiles': metrics_collector.get_percentiles(),
            'recent_5min': metrics_collector.get_recent_stats(5),
            'by_event_type': metrics_collector.get_by_event_type()
        }
    }


@router.get("/health")
async def health_check():
    """
    健康检查
    
    Returns:
        健康状态
    """
    try:
        stats = repository.get_stats()
        return {
            'status': 'healthy',
            'rules_loaded': stats['total_rules'],
            'active_rules': stats['active_rules']
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


# 初始化引擎（在应用启动时调用）
def initialize_engine(supabase_client=None):
    """
    初始化引擎
    
    Args:
        supabase_client: Supabase 客户端（可选）
    """
    # 设置 Supabase 客户端
    if supabase_client:
        repository.supabase = supabase_client
        audit_logger.supabase = supabase_client
    
    # 加载规则
    rule_set = repository.load()
    engine.load_rules(rule_set)
    
    print(f"QC Engine initialized with {len(rule_set.rules)} rules")


# 导出
__all__ = [
    'router',
    'initialize_engine',
    'EvaluateRequest',
    'EvaluateResponse',
    'BatchEvaluateRequest',
    'BatchEvaluateResponse'
]
