# 审核任务管理API端点
# 集成现有FastAPI应用的审核任务管理功能

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import asyncio
from datetime import datetime

from ..models.audit_models import (
    QCAuditTask, QCAuditTaskItem, CreateAuditTaskRequest,
    AuditTaskFilter, BatchAuditRequest, BatchAuditResult,
    APIResponse, PaginatedResponse
)
from ..services.audit_task_service import AuditTaskService
from ..database.database import get_db
from ..auth.dependencies import get_current_user, require_permissions
from ..core.config import settings

# 假设现有的三层质控引擎实例
from ..qc_engine.three_layer_engine import three_layer_qc_engine

router = APIRouter(prefix="/api/audit-tasks", tags=["审核任务管理"])

# 初始化审核任务服务
audit_task_service = AuditTaskService(three_layer_qc_engine)

@router.post("", response_model=APIResponse[QCAuditTask])
async def create_audit_task(
    request: CreateAuditTaskRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_create"]))
):
    """
    创建审核任务
    
    - 集成现有三层质控引擎进行风险评估
    - 执行智能抽样算法
    - 自动分配审核员
    """
    try:
        # 验证请求参数
        if request.planned_end_date <= request.planned_start_date:
            raise HTTPException(
                status_code=400,
                detail="计划结束日期必须晚于开始日期"
            )
        
        # 创建审核任务
        task = await audit_task_service.create_audit_task(
            request=request,
            created_by=current_user.id,
            db=db
        )
        
        # 后台任务：发送任务分配通知
        background_tasks.add_task(
            send_task_assignment_notifications,
            task.id,
            request.assigned_reviewers
        )
        
        return APIResponse(
            success=True,
            message="审核任务创建成功",
            data=task
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"创建审核任务失败: {str(e)}"
        )

@router.get("", response_model=APIResponse[PaginatedResponse[QCAuditTask]])
async def get_audit_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    task_type: Optional[str] = Query(None, description="任务类型"),
    audit_level: Optional[str] = Query(None, description="审核级别"),
    status: Optional[str] = Query(None, description="任务状态"),
    assigned_reviewer: Optional[str] = Query(None, description="分配的审核员"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取审核任务列表
    
    支持分页、筛选和搜索功能
    """
    try:
        # 构建过滤条件
        filter_params = AuditTaskFilter(
            task_type=task_type,
            audit_level=audit_level,
            status=status,
            assigned_reviewer=assigned_reviewer,
            search=search
        )
        
        # 查询任务列表
        tasks, total = await audit_task_service.get_audit_tasks(
            filter_params=filter_params,
            page=page,
            page_size=page_size,
            db=db
        )
        
        # 构建分页响应
        paginated_response = PaginatedResponse(
            items=tasks,
            total=total,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(
            success=True,
            message="获取任务列表成功",
            data=paginated_response
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取任务列表失败: {str(e)}"
        )

@router.get("/{task_id}", response_model=APIResponse[QCAuditTask])
async def get_audit_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取单个审核任务详情"""
    try:
        task = await audit_task_service.get_audit_task_by_id(task_id, db)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail="审核任务不存在"
            )
        
        return APIResponse(
            success=True,
            message="获取任务详情成功",
            data=task
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取任务详情失败: {str(e)}"
        )

@router.get("/{task_id}/items", response_model=APIResponse[PaginatedResponse[QCAuditTaskItem]])
async def get_task_items(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="审核状态"),
    risk_level: Optional[str] = Query(None, description="风险等级"),
    assigned_reviewer: Optional[str] = Query(None, description="分配的审核员"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取审核任务的明细项目"""
    try:
        # 验证任务存在
        task = await audit_task_service.get_audit_task_by_id(task_id, db)
        if not task:
            raise HTTPException(status_code=404, detail="审核任务不存在")
        
        # 查询任务项目
        items, total = await audit_task_service.get_task_items(
            task_id=task_id,
            page=page,
            page_size=page_size,
            status=status,
            risk_level=risk_level,
            assigned_reviewer=assigned_reviewer,
            db=db
        )
        
        paginated_response = PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(
            success=True,
            message="获取任务项目成功",
            data=paginated_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取任务项目失败: {str(e)}"
        )

@router.post("/{task_id}/start", response_model=APIResponse[QCAuditTask])
async def start_audit_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_manage"]))
):
    """启动审核任务"""
    try:
        task = await audit_task_service.start_audit_task(
            task_id=task_id,
            started_by=current_user.id,
            db=db
        )
        
        # 后台任务：通知审核员任务已启动
        background_tasks.add_task(
            notify_task_started,
            task_id
        )
        
        return APIResponse(
            success=True,
            message="审核任务已启动",
            data=task
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"启动审核任务失败: {str(e)}"
        )

@router.post("/{task_id}/complete", response_model=APIResponse[QCAuditTask])
async def complete_audit_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_manage"]))
):
    """完成审核任务"""
    try:
        task = await audit_task_service.complete_audit_task(
            task_id=task_id,
            completed_by=current_user.id,
            db=db
        )
        
        # 后台任务：生成任务完成报告
        background_tasks.add_task(
            generate_task_completion_report,
            task_id
        )
        
        return APIResponse(
            success=True,
            message="审核任务已完成",
            data=task
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"完成审核任务失败: {str(e)}"
        )

@router.post("/{task_id}/intelligent-sampling", response_model=APIResponse[List[QCAuditTaskItem]])
async def perform_intelligent_sampling(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_manage"]))
):
    """
    执行智能抽样
    
    基于现有三层质控引擎的分析结果进行智能抽样
    """
    try:
        # 获取任务信息
        task = await audit_task_service.get_audit_task_by_id(task_id, db)
        if not task:
            raise HTTPException(status_code=404, detail="审核任务不存在")
        
        # 执行智能抽样
        sampled_items = await audit_task_service.perform_intelligent_sampling(
            task_id=task_id,
            db=db
        )
        
        # 后台任务：更新任务统计
        background_tasks.add_task(
            update_task_sampling_statistics,
            task_id
        )
        
        return APIResponse(
            success=True,
            message=f"智能抽样完成，共选中 {len(sampled_items)} 条记录",
            data=sampled_items
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"智能抽样失败: {str(e)}"
        )

@router.post("/{task_id}/batch-assign", response_model=APIResponse[dict])
async def batch_assign_reviewers(
    task_id: str,
    reviewer_assignments: dict,  # {item_id: reviewer_id}
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_manage"]))
):
    """批量分配审核员"""
    try:
        result = await audit_task_service.batch_assign_reviewers(
            task_id=task_id,
            assignments=reviewer_assignments,
            assigned_by=current_user.id,
            db=db
        )
        
        return APIResponse(
            success=True,
            message="批量分配审核员成功",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"批量分配失败: {str(e)}"
        )

@router.get("/{task_id}/statistics", response_model=APIResponse[dict])
async def get_task_statistics(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取任务统计信息"""
    try:
        statistics = await audit_task_service.get_task_statistics(task_id, db)
        
        return APIResponse(
            success=True,
            message="获取统计信息成功",
            data=statistics
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.delete("/{task_id}", response_model=APIResponse[dict])
async def delete_audit_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["audit_task_delete"]))
):
    """删除审核任务"""
    try:
        await audit_task_service.delete_audit_task(
            task_id=task_id,
            deleted_by=current_user.id,
            db=db
        )
        
        return APIResponse(
            success=True,
            message="审核任务已删除",
            data={"task_id": task_id}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除审核任务失败: {str(e)}"
        )

# 后台任务函数
async def send_task_assignment_notifications(task_id: str, reviewer_ids: List[str]):
    """发送任务分配通知"""
    try:
        # 这里集成消息通知服务
        print(f"发送任务分配通知: 任务 {task_id}, 审核员 {reviewer_ids}")
        # 实际实现中会调用通知服务
    except Exception as e:
        print(f"发送任务分配通知失败: {e}")

async def notify_task_started(task_id: str):
    """通知任务已启动"""
    try:
        print(f"通知任务已启动: {task_id}")
        # 实际实现中会调用通知服务
    except Exception as e:
        print(f"通知任务启动失败: {e}")

async def generate_task_completion_report(task_id: str):
    """生成任务完成报告"""
    try:
        print(f"生成任务完成报告: {task_id}")
        # 实际实现中会生成详细的完成报告
    except Exception as e:
        print(f"生成完成报告失败: {e}")

async def update_task_sampling_statistics(task_id: str):
    """更新任务抽样统计"""
    try:
        print(f"更新任务抽样统计: {task_id}")
        # 实际实现中会更新相关统计信息
    except Exception as e:
        print(f"更新抽样统计失败: {e}")

# 健康检查端点
@router.get("/health", response_model=APIResponse[dict])
async def health_check():
    """审核任务服务健康检查"""
    return APIResponse(
        success=True,
        message="审核任务服务运行正常",
        data={
            "service": "audit_task_service",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
