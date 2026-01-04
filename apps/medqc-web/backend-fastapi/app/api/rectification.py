"""
整改管理 API
Rectification Management API
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime

try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.schemas.rectification import (
    RectificationTaskCreate, RectificationTaskUpdate,
    TaskAssignment, TaskSubmission, TaskReview,
    RectificationTaskResponse, RectificationTaskListResponse,
    TaskFilters, TaskStats
)
from app.services.rectification_service import rectification_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/rectifications", tags=["整改管理"])


@router.post(
    "",
    response_model=RectificationTaskResponse,
    summary="创建整改任务",
    description="质控专员创建整改任务"
)
async def create_rectification_task(
    task_data: RectificationTaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建整改任务
    
    质控专员可以为质控问题创建整改任务，分配给对应的医务人员。
    
    **示例请求**:
    ```json
    {
      "qc_result_id": "qc_xxx",
      "defect_id": "DEF-001",
      "record_id": "record_xxx",
      "task_title": "病程记录时间不准确",
      "task_description": "请核对并修改第3页病程记录时间",
      "defect_type": "timing_error",
      "severity": "major",
      "assignee_id": "doctor_001",
      "assignee_name": "张医生",
      "due_date": "2026-01-10T00:00:00Z"
    }
    ```
    """
    try:
        # TODO: 检查用户权限（需要质控专员权限）
        
        result = await rectification_service.create_task(
            task_data=task_data,
            assigner_id=current_user['id'],
            assigner_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="创建整改任务失败")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建整改任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get(
    "",
    response_model=RectificationTaskListResponse,
    summary="查询整改任务列表",
    description="查询整改任务列表，支持多种筛选条件"
)
async def list_rectification_tasks(
    status: Optional[str] = Query(None, description="任务状态"),
    severity: Optional[str] = Query(None, description="严重程度"),
    assignee_id: Optional[str] = Query(None, description="指派人ID"),
    assigner_id: Optional[str] = Query(None, description="分配人ID"),
    department_id: Optional[str] = Query(None, description="科室ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    overdue_only: bool = Query(False, description="仅显示逾期任务"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    查询整改任务列表
    
    支持的筛选条件：
    - status: pending, in_progress, submitted, approved, rejected
    - severity: critical, major, minor
    - 分配人/指派人
    - 科室
    - 日期范围
    - 逾期任务
    """
    try:
        from app.schemas.rectification import TaskStatus, TaskSeverity
        
        filters = TaskFilters(
            status=TaskStatus(status) if status else None,
            severity=TaskSeverity(severity) if severity else None,
            assignee_id=assignee_id,
            assigner_id=assigner_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            overdue_only=overdue_only,
            page=page,
            page_size=page_size
        )
        
        return await rectification_service.list_tasks(filters)
    
    except Exception as e:
        logger.error(f"查询整改任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get(
    "/my-tasks",
    response_model=list[RectificationTaskResponse],
    summary="获取我的整改任务",
    description="获取当前用户的整改任务"
)
async def get_my_tasks(
    status: Optional[str] = Query(None, description="任务状态"),
    current_user: dict = Depends(get_current_user)
):
    """获取我的整改任务"""
    try:
        from app.schemas.rectification import TaskStatus
        
        tasks = await rectification_service.get_my_tasks(
            user_id=current_user['id'],
            status_filter=TaskStatus(status) if status else None
        )
        return tasks
    
    except Exception as e:
        logger.error(f"获取我的整改任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get(
    "/{task_id}",
    response_model=RectificationTaskResponse,
    summary="获取整改任务详情"
)
async def get_rectification_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取整改任务详情"""
    try:
        result = await rectification_service.get_task(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="整改任务不存在")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取整改任务详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.put(
    "/{task_id}",
    response_model=RectificationTaskResponse,
    summary="更新整改任务"
)
async def update_rectification_task(
    task_id: str,
    updates: RectificationTaskUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新整改任务"""
    try:
        # TODO: 检查用户权限
        
        result = await rectification_service.update_task(
            task_id=task_id,
            updates=updates,
            user_id=current_user['id']
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="整改任务不存在")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新整改任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post(
    "/{task_id}/assign",
    response_model=RectificationTaskResponse,
    summary="分配/重新分配整改任务",
    description="质控专员可以分配或重新分配整改任务"
)
async def assign_task(
    task_id: str,
    assignment: TaskAssignment,
    current_user: dict = Depends(get_current_user)
):
    """
    分配/重新分配整改任务
    
    **示例请求**:
    ```json
    {
      "assignee_id": "doctor_002",
      "assignee_name": "李医生",
      "comment": "原医生已调离，重新分配"
    }
    ```
    """
    try:
        # TODO: 检查用户权限（需要质控专员权限）
        
        result = await rectification_service.assign_task(
            task_id=task_id,
            assignment=assignment,
            assigner_id=current_user['id'],
            assigner_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="整改任务不存在")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分配整改任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分配失败: {str(e)}")


@router.post(
    "/{task_id}/submit",
    response_model=RectificationTaskResponse,
    summary="提交整改",
    description="医务人员完成整改后提交"
)
async def submit_rectification(
    task_id: str,
    submission: TaskSubmission,
    current_user: dict = Depends(get_current_user)
):
    """
    提交整改
    
    医务人员完成整改后，提交整改说明和证据文件。
    
    **示例请求**:
    ```json
    {
      "rectification_content": "已核对并修改病程记录时间...",
      "rectification_files": ["https://example.com/modified1.pdf"]
    }
    ```
    """
    try:
        result = await rectification_service.submit_rectification(
            task_id=task_id,
            submission=submission,
            user_id=current_user['id'],
            user_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="整改任务不存在或无权提交")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交整改失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post(
    "/{task_id}/review",
    response_model=RectificationTaskResponse,
    summary="验收整改",
    description="质控专员验收整改结果（通过/不通过）"
)
async def review_rectification(
    task_id: str,
    review: TaskReview,
    current_user: dict = Depends(get_current_user)
):
    """
    验收整改
    
    质控专员对提交的整改进行验收，可以选择：
    - pass: 验收通过（问题闭环）
    - fail: 验收不通过（需要重新整改）
    
    **示例请求**:
    ```json
    {
      "review_result": "pass",
      "review_comment": "整改质量良好，验收通过"
    }
    ```
    """
    try:
        # TODO: 检查用户权限（需要质控专员权限）
        
        result = await rectification_service.review_rectification(
            task_id=task_id,
            review=review,
            reviewer_id=current_user['id'],
            reviewer_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="整改任务不存在或状态不正确")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验收整改失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"验收失败: {str(e)}")


@router.get(
    "/stats",
    response_model=TaskStats,
    summary="整改任务统计",
    description="获取整改任务统计数据"
)
async def get_rectification_statistics(
    department_id: Optional[str] = Query(None, description="科室ID"),
    assignee_id: Optional[str] = Query(None, description="指派人ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user)
):
    """获取整改任务统计数据"""
    try:
        return await rectification_service.get_task_statistics(
            department_id=department_id,
            assignee_id=assignee_id,
            start_date=start_date,
            end_date=end_date
        )
    
    except Exception as e:
        logger.error(f"获取整改统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
