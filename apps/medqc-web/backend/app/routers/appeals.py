"""
申诉流程管理路由

功能:
- 创建申诉
- 查询申诉列表
- 获取申诉详情
- 更新申诉
- 撤回申诉
- 审核申诉
- 申诉统计
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional
from datetime import datetime
import logging

from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.supabase_client import get_supabase
from ..core.security import get_current_user
from ..schemas.appeals import (
    AppealCreate,
    AppealUpdate,
    AppealWithdraw,
    AppealReviewCreate,
    AppealResponse,
    AppealDetailResponse,
    AppealListQuery,
    AppealStatistics,
    AppealStatus,
    AppealPriority,
    AppealType,
    ReviewAction,
)

router = APIRouter(prefix="/api/v1/appeals", tags=["appeals"])
logger = logging.getLogger(__name__)


def _legacy_only(query):
    # 只使用旧版已有列，兼容旧库；现代申诉的两个旧主键必须为 NULL。
    return query.is_not("qc_result_id", None).is_not("record_id", None)


# ============================
# 申诉管理
# ============================

@router.post("", response_model=dict)
async def create_appeal(
    request: Request,
    appeal: AppealCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建申诉

    Args:
        appeal: 申诉信息
        current_user: 当前用户

    Returns:
        创建的申诉记录
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 验证质控结果是否存在
        qc_result = supabase.table("qc_results").select("id").eq("id", str(appeal.qc_result_id)).execute()
        if not qc_result.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"质控结果不存在: {appeal.qc_result_id}"
            )

        # 验证病历是否存在
        record = supabase.table("medical_records").select("id").eq("id", str(appeal.record_id)).execute()
        if not record.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"病历不存在: {appeal.record_id}"
            )

        # 创建申诉记录
        appeal_data = {
            "qc_result_id": str(appeal.qc_result_id),
            "record_id": str(appeal.record_id),
            "appeal_type": appeal.appeal_type.value,
            "defect_item": appeal.defect_item,
            "reason": appeal.reason,
            "evidence": appeal.evidence,
            "priority": appeal.priority.value,
            "appellant_id": current_user["id"],
            "appellant_name": current_user.get("name", current_user.get("email", "Unknown")),
            "appellant_department": appeal.appellant_department,
            "notes": appeal.notes,
            "status": AppealStatus.PENDING.value,
        }

        result = supabase.table("qc_appeals").insert(appeal_data).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="创建申诉失败"
            )

        logger.info(
            f"Appeal created: {result.data[0]['id']}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="申诉创建成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create appeal: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"创建申诉失败: {str(e)}"
        )


@router.get("", response_model=dict)
async def list_appeals(
    request: Request,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    appeal_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    获取申诉列表

    Args:
        status: 申诉状态
        priority: 优先级
        appeal_type: 申诉类型
        start_date: 开始日期
        end_date: 结束日期
        page: 页码
        page_size: 每页数量
        current_user: 当前用户

    Returns:
        申诉列表
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 构建查询
        query = _legacy_only(supabase.table("qc_appeals").select("*", count="exact"))

        # 应用过滤条件
        if status:
            query = query.eq("status", status)

        if priority:
            query = query.eq("priority", priority)

        if appeal_type:
            query = query.eq("appeal_type", appeal_type)

        if start_date:
            query = query.gte("created_at", start_date)

        if end_date:
            query = query.lte("created_at", end_date)

        # 分页
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

        result = query.execute()

        return paginated_response(
            items=result.data or [],
            total=result.count or 0,
            page=page,
            page_size=page_size,
            trace_id=trace_id,
        )

    except Exception as e:
        logger.error(
            f"Failed to list appeals: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取申诉列表失败: {str(e)}"
        )


@router.get("/{appeal_id}", response_model=dict)
async def get_appeal(
    request: Request,
    appeal_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取申诉详情

    Args:
        appeal_id: 申诉ID
        current_user: 当前用户

    Returns:
        申诉详情
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 获取申诉记录
        appeal_result = _legacy_only(supabase.table("qc_appeals").select("*").eq("id", appeal_id)).execute()

        if not appeal_result.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"申诉不存在: {appeal_id}"
            )

        appeal = appeal_result.data[0]

        # 获取审核历史
        reviews_result = supabase.table("qc_appeal_reviews").select("*").eq("appeal_id", appeal_id).order("created_at", desc=False).execute()

        appeal["reviews"] = reviews_result.data or []

        return success_response(
            data=appeal,
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get appeal: {str(e)}",
            extra={"trace_id": trace_id, "appeal_id": appeal_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取申诉详情失败: {str(e)}"
        )


@router.put("/{appeal_id}", response_model=dict)
async def update_appeal(
    request: Request,
    appeal_id: str,
    appeal: AppealUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    更新申诉

    Args:
        appeal_id: 申诉ID
        appeal: 更新的申诉信息
        current_user: 当前用户

    Returns:
        更新后的申诉记录
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 验证申诉是否存在且属于当前用户
        existing = _legacy_only(supabase.table("qc_appeals").select("*").eq("id", appeal_id)).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"申诉不存在: {appeal_id}"
            )

        existing_appeal = existing.data[0]

        # 只有申诉人可以更新（且状态为 pending）
        if existing_appeal["appellant_id"] != current_user["id"]:
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="只有申诉人可以更新申诉"
            )

        if existing_appeal["status"] != AppealStatus.PENDING.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能更新待审核状态的申诉"
            )

        # 构建更新数据
        update_data = {}
        if appeal.reason is not None:
            update_data["reason"] = appeal.reason
        if appeal.evidence is not None:
            update_data["evidence"] = appeal.evidence
        if appeal.priority is not None:
            update_data["priority"] = appeal.priority.value
        if appeal.notes is not None:
            update_data["notes"] = appeal.notes

        if not update_data:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="没有提供要更新的数据"
            )

        # 更新申诉
        result = _legacy_only(supabase.table("qc_appeals").update(update_data).eq("id", appeal_id)).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="更新申诉失败"
            )

        logger.info(
            f"Appeal updated: {appeal_id}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="申诉更新成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update appeal: {str(e)}",
            extra={"trace_id": trace_id, "appeal_id": appeal_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"更新申诉失败: {str(e)}"
        )


@router.post("/{appeal_id}/withdraw", response_model=dict)
async def withdraw_appeal(
    request: Request,
    appeal_id: str,
    withdraw: AppealWithdraw,
    current_user: dict = Depends(get_current_user)
):
    """
    撤回申诉

    Args:
        appeal_id: 申诉ID
        withdraw: 撤回信息
        current_user: 当前用户

    Returns:
        撤回后的申诉记录
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 验证申诉是否存在且属于当前用户
        existing = _legacy_only(supabase.table("qc_appeals").select("*").eq("id", appeal_id)).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"申诉不存在: {appeal_id}"
            )

        existing_appeal = existing.data[0]

        # 只有申诉人可以撤回
        if existing_appeal["appellant_id"] != current_user["id"]:
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="只有申诉人可以撤回申诉"
            )

        # 只能撤回待审核或审核中的申诉
        if existing_appeal["status"] not in [AppealStatus.PENDING.value, AppealStatus.REVIEWING.value]:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能撤回待审核或审核中的申诉"
            )

        # 更新状态为已撤回
        update_data = {
            "status": AppealStatus.WITHDRAWN.value,
            "resolution": withdraw.reason or "申诉人主动撤回",
            "resolution_date": datetime.utcnow().isoformat()
        }

        result = _legacy_only(supabase.table("qc_appeals").update(update_data).eq("id", appeal_id)).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="撤回申诉失败"
            )

        logger.info(
            f"Appeal withdrawn: {appeal_id}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="申诉已撤回",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to withdraw appeal: {str(e)}",
            extra={"trace_id": trace_id, "appeal_id": appeal_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"撤回申诉失败: {str(e)}"
        )


# ============================
# 审核管理
# ============================

@router.post("/{appeal_id}/review", response_model=dict)
async def review_appeal(
    request: Request,
    appeal_id: str,
    review: AppealReviewCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    审核申诉

    Args:
        appeal_id: 申诉ID
        review: 审核信息
        current_user: 当前用户

    Returns:
        审核后的申诉记录
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 验证申诉是否存在
        existing = _legacy_only(supabase.table("qc_appeals").select("*").eq("id", appeal_id)).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"申诉不存在: {appeal_id}"
            )

        existing_appeal = existing.data[0]

        # 验证状态
        if existing_appeal["status"] == AppealStatus.WITHDRAWN.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="无法审核已撤回的申诉"
            )

        # 创建审核记录
        review_data = {
            "appeal_id": appeal_id,
            "reviewer_id": current_user["id"],
            "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
            "reviewer_role": current_user.get("role", "reviewer"),
            "action": review.action.value,
            "comment": review.comment,
            "metadata": {}
        }

        review_result = supabase.table("qc_appeal_reviews").insert(review_data).execute()

        # 更新申诉状态
        update_data = {
            "reviewer_id": current_user["id"],
            "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
            "review_date": datetime.utcnow().isoformat()
        }

        if review.action == ReviewAction.APPROVE:
            update_data["status"] = AppealStatus.APPROVED.value
            update_data["resolution"] = review.resolution or "申诉已批准"
            update_data["resolution_date"] = datetime.utcnow().isoformat()
        elif review.action == ReviewAction.REJECT:
            update_data["status"] = AppealStatus.REJECTED.value
            update_data["resolution"] = review.resolution or "申诉已拒绝"
            update_data["resolution_date"] = datetime.utcnow().isoformat()
        elif review.action == ReviewAction.REQUEST_INFO:
            update_data["status"] = AppealStatus.REVIEWING.value
        else:
            update_data["status"] = AppealStatus.REVIEWING.value

        update_data["review_result"] = review.comment

        appeal_result = _legacy_only(supabase.table("qc_appeals").update(update_data).eq("id", appeal_id)).execute()

        if not appeal_result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_SERVER_ERROR,
                detail="更新申诉状态失败"
            )

        logger.info(
            f"Appeal reviewed: {appeal_id}, action: {review.action.value}",
            extra={"trace_id": trace_id, "reviewer_id": current_user["id"]}
        )

        return success_response(
            data=appeal_result.data[0],
            message="审核成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to review appeal: {str(e)}",
            extra={"trace_id": trace_id, "appeal_id": appeal_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"审核申诉失败: {str(e)}"
        )


# ============================
# 统计
# ============================

@router.get("/statistics/summary", response_model=dict)
async def get_appeal_statistics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    获取申诉统计

    Args:
        start_date: 开始日期
        end_date: 结束日期
        current_user: 当前用户

    Returns:
        统计数据
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败"
        )

    try:
        # 查询统计视图
        query = supabase.table("qc_appeals_statistics").select("*")
        result = query.execute()

        # 计算总览统计
        stats = {
            "total": 0,
            "pending": 0,
            "reviewing": 0,
            "approved": 0,
            "rejected": 0,
            "withdrawn": 0,
            "avg_resolution_time_hours": 0.0,
            "by_type": {},
            "by_priority": {}
        }

        total_resolution_time = 0
        resolution_count = 0

        for row in result.data or []:
            status = row.get("status")
            appeal_type = row.get("appeal_type")
            priority = row.get("priority")
            count = row.get("count", 0)
            avg_time = row.get("avg_resolution_time_seconds", 0)

            stats["total"] += count

            # 按状态统计
            if status in stats:
                stats[status] += count

            # 按类型统计
            if appeal_type:
                stats["by_type"][appeal_type] = stats["by_type"].get(appeal_type, 0) + count

            # 按优先级统计
            if priority:
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + count

            # 平均处理时间
            if avg_time:
                total_resolution_time += avg_time * count
                resolution_count += count

        if resolution_count > 0:
            stats["avg_resolution_time_hours"] = round(total_resolution_time / resolution_count / 3600, 2)

        return success_response(
            data=stats,
            request=request
        )

    except Exception as e:
        logger.error(
            f"Failed to get appeal statistics: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}"
        )

