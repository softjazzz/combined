"""
申诉管理 API
Appeal Management API
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime

try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.schemas.appeal import (
    AppealCreate, AppealUpdate, AppealReview,
    AppealResponse, AppealListResponse,
    AppealFilters, AppealStats
)
from app.services.appeal_service import appeal_service
from app.api.auth import get_current_user

router = APIRouter(prefix="/appeals", tags=["申诉管理"])


@router.post(
    "",
    response_model=AppealResponse,
    summary="创建申诉",
    description="医务人员对质控问题提交申诉"
)
async def create_appeal(
    appeal_data: AppealCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建申诉
    
    医务人员可以对认为不合理的质控问题提交申诉，包括：
    - 规则判定有误
    - 特殊情况
    - 其他原因
    
    **示例请求**:
    ```json
    {
      "qc_result_id": "qc_xxx",
      "defect_id": "DEF-001",
      "record_id": "record_xxx",
      "appeal_reason": "该患者为特殊情况...",
      "appeal_type": "special_case",
      "evidence_urls": ["https://example.com/evidence1.pdf"]
    }
    ```
    """
    try:
        logger.info(f"用户 {current_user.get('id')} 创建申诉")
        
        result = await appeal_service.create_appeal(
            appeal_data=appeal_data,
            user_id=current_user['id'],
            user_name=current_user.get('display_name', ''),
            department_id=current_user.get('department')
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="创建申诉失败")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建申诉失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建申诉失败: {str(e)}")


@router.get(
    "",
    response_model=AppealListResponse,
    summary="查询申诉列表",
    description="查询申诉列表，支持多种筛选条件"
)
async def list_appeals(
    status: Optional[str] = Query(None, description="申诉状态"),
    appeal_type: Optional[str] = Query(None, description="申诉类型"),
    appellant_id: Optional[str] = Query(None, description="申诉人ID"),
    department_id: Optional[str] = Query(None, description="科室ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """
    查询申诉列表
    
    支持的筛选条件：
    - status: pending, approved, rejected, withdrawn
    - appeal_type: incorrect_rule, special_case, other
    - appellant_id: 申诉人ID
    - department_id: 科室ID
    - 日期范围
    """
    try:
        from app.schemas.appeal import AppealStatus, AppealType
        
        filters = AppealFilters(
            status=AppealStatus(status) if status else None,
            appeal_type=AppealType(appeal_type) if appeal_type else None,
            appellant_id=appellant_id,
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )
        
        return await appeal_service.list_appeals(filters)
    
    except Exception as e:
        logger.error(f"查询申诉列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get(
    "/{appeal_id}",
    response_model=AppealResponse,
    summary="获取申诉详情"
)
async def get_appeal(
    appeal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取申诉详情"""
    try:
        result = await appeal_service.get_appeal(appeal_id)
        if not result:
            raise HTTPException(status_code=404, detail="申诉不存在")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取申诉详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.put(
    "/{appeal_id}",
    response_model=AppealResponse,
    summary="更新申诉",
    description="申诉人可以更新待审核的申诉内容"
)
async def update_appeal(
    appeal_id: str,
    updates: AppealUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新申诉（仅申诉人可更新待审核的申诉）"""
    try:
        result = await appeal_service.update_appeal(
            appeal_id=appeal_id,
            updates=updates,
            user_id=current_user['id']
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="申诉不存在或无权修改")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新申诉失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post(
    "/{appeal_id}/review",
    response_model=AppealResponse,
    summary="审核申诉",
    description="质控专员审核申诉（通过/驳回）"
)
async def review_appeal(
    appeal_id: str,
    review: AppealReview,
    current_user: dict = Depends(get_current_user)
):
    """
    审核申诉
    
    质控专员对申诉进行审核，可以选择：
    - approve: 通过申诉（取消该质控问题）
    - reject: 驳回申诉（分配整改任务）
    
    **示例请求**:
    ```json
    {
      "decision": "approve",
      "comment": "经审核，该患者确为特殊情况，申诉理由成立"
    }
    ```
    """
    try:
        # TODO: 检查用户权限（需要质控专员权限）
        
        result = await appeal_service.review_appeal(
            appeal_id=appeal_id,
            review=review,
            reviewer_id=current_user['id'],
            reviewer_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="申诉不存在")
        
        # 如果驳回，自动创建整改任务
        if review.decision == 'reject':
            from app.services.rectification_service import rectification_service
            from app.schemas.rectification import RectificationTaskCreate, TaskSeverity
            
            appeal = await appeal_service.get_appeal(appeal_id)
            if appeal:
                task_data = RectificationTaskCreate(
                    qc_result_id=appeal.qc_result_id,
                    defect_id=appeal.defect_id,
                    record_id=appeal.record_id,
                    appeal_id=appeal_id,
                    task_title=f"整改任务：{appeal.defect_id}",
                    task_description=f"申诉被驳回，需要整改。\n\n驳回原因：{review.comment}",
                    defect_type=appeal.appeal_type.value,
                    severity=TaskSeverity.MAJOR,
                    assignee_id=appeal.appellant_id,
                    assignee_name=appeal.appellant_name
                )
                
                await rectification_service.create_task(
                    task_data=task_data,
                    assigner_id=current_user['id'],
                    assigner_name=current_user.get('display_name', '')
                )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核申诉失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")


@router.post(
    "/{appeal_id}/withdraw",
    response_model=AppealResponse,
    summary="撤销申诉",
    description="申诉人主动撤销待审核的申诉"
)
async def withdraw_appeal(
    appeal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """撤销申诉"""
    try:
        result = await appeal_service.withdraw_appeal(
            appeal_id=appeal_id,
            user_id=current_user['id'],
            user_name=current_user.get('display_name', '')
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="申诉不存在或无权撤销")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤销申诉失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"撤销失败: {str(e)}")


@router.get(
    "/stats",
    response_model=AppealStats,
    summary="申诉统计",
    description="获取申诉统计数据"
)
async def get_appeal_statistics(
    department_id: Optional[str] = Query(None, description="科室ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user)
):
    """获取申诉统计数据"""
    try:
        return await appeal_service.get_appeal_statistics(
            department_id=department_id,
            start_date=start_date,
            end_date=end_date
        )
    
    except Exception as e:
        logger.error(f"获取申诉统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
