"""
整改跟踪管理路由

功能:
- 创建整改任务
- 查询整改任务列表
- 获取整改任务详情
- 更新整改任务
- 提交整改
- 验收整改
- 关闭整改任务
- 整改统计
- 责任人工作负载
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional
from datetime import datetime, timedelta
import logging

from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.supabase_client import get_supabase
from ..core.security import get_current_user
from ..schemas.remediation import (
    RemediationTaskCreate,
    RemediationTaskUpdate,
    RemediationSubmit,
    RemediationReview,
    RemediationClose,
    RemediationTaskResponse,
    RemediationTaskDetailResponse,
    RemediationTaskListQuery,
    RemediationStatistics,
    AssigneeWorkload,
    OverdueTaskAlert,
    RemediationStatus,
    RemediationPriority,
    HistoryAction,
)

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])
logger = logging.getLogger(__name__)


# ============================
# 整改任务管理
# ============================

@router.post("", response_model=dict)
async def create_remediation_task(
    request: Request,
    task: RemediationTaskCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建整改任务

    Args:
        task: 整改任务信息
        current_user: 当前用户

    Returns:
        创建的整改任务记录
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 验证质控结果是否存在
        qc_result = supabase.table("qc_results").select("id").eq("id", str(task.qc_result_id)).execute()
        if not qc_result.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"质控结果不存在: {task.qc_result_id}"
            )

        # 验证病历是否存在
        record = supabase.table("medical_records").select("id").eq("id", str(task.record_id)).execute()
        if not record.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"病历不存在: {task.record_id}"
            )

        # 创建整改任务
        task_data = {
            "qc_result_id": str(task.qc_result_id),
            "record_id": str(task.record_id),
            "defect_type": task.defect_type,
            "defect_description": task.defect_description,
            "defect_location": task.defect_location,
            "severity": task.severity.value,
            "remediation_requirement": task.remediation_requirement,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "assignee_id": str(task.assignee_id),
            "assignee_name": task.assignee_name,
            "assignee_department": task.assignee_department,
            "notes": task.notes,
            "status": RemediationStatus.PENDING.value,
        }

        result = supabase.table("qc_remediation_tasks").insert(task_data).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_ERROR,
                detail="创建整改任务失败"
            )

        # 记录历史
        history_data = {
            "task_id": result.data[0]["id"],
            "action": HistoryAction.CREATE.value,
            "actor_id": current_user["id"],
            "actor_name": current_user.get("name", current_user.get("email", "Unknown")),
            "new_status": RemediationStatus.PENDING.value,
            "comment": "创建整改任务"
        }
        supabase.table("qc_remediation_history").insert(history_data).execute()

        logger.info(
            f"Remediation task created: {result.data[0]['id']}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="整改任务创建成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create remediation task: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"创建整改任务失败: {str(e)}"
        )


@router.get("", response_model=dict)
async def list_remediation_tasks(
    request: Request,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    assignee_id: Optional[str] = None,
    defect_type: Optional[str] = None,
    is_overdue: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """
    获取整改任务列表

    Args:
        status: 整改状态
        severity: 严重程度
        assignee_id: 负责人ID
        defect_type: 缺陷类型
        is_overdue: 是否逾期
        start_date: 开始日期
        end_date: 结束日期
        page: 页码
        page_size: 每页数量
        current_user: 当前用户

    Returns:
        整改任务列表
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 构建查询
        query = supabase.table("qc_remediation_tasks").select("*", count="exact")

        # 应用过滤条件
        if status:
            query = query.eq("status", status)

        if severity:
            query = query.eq("severity", severity)

        if assignee_id:
            query = query.eq("assignee_id", assignee_id)

        if defect_type:
            query = query.ilike("defect_type", f"%{defect_type}%")

        if is_overdue:
            # 逾期任务：deadline < now AND status NOT IN (approved, closed)
            now = datetime.utcnow().isoformat()
            query = query.lt("deadline", now).in_("status", ["pending", "in_progress", "submitted", "rejected", "overdue"])

        if start_date:
            query = query.gte("created_at", start_date)

        if end_date:
            query = query.lte("created_at", end_date)

        # 分页
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)

        result = query.execute()

        return paginated_response(
            data=result.data or [],
            total=result.count or 0,
            page=page,
            page_size=page_size,
            request=request
        )

    except Exception as e:
        logger.error(
            f"Failed to list remediation tasks: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"获取整改任务列表失败: {str(e)}"
        )


@router.get("/{task_id}", response_model=dict)
async def get_remediation_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取整改任务详情

    Args:
        task_id: 整改任务ID
        current_user: 当前用户

    Returns:
        整改任务详情
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 获取整改任务
        task_result = supabase.table("qc_remediation_tasks").select("*").eq("id", task_id).execute()

        if not task_result.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"整改任务不存在: {task_id}"
            )

        task = task_result.data[0]

        # 获取历史记录
        history_result = supabase.table("qc_remediation_history").select("*").eq("task_id", task_id).order("created_at", desc=False).execute()

        task["history"] = history_result.data or []

        return success_response(
            data=task,
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get remediation task: {str(e)}",
            extra={"trace_id": trace_id, "task_id": task_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"获取整改任务详情失败: {str(e)}"
        )


@router.put("/{task_id}", response_model=dict)
async def update_remediation_task(
    request: Request,
    task_id: str,
    task: RemediationTaskUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    更新整改任务

    Args:
        task_id: 整改任务ID
        task: 更新的任务信息
        current_user: 当前用户

    Returns:
        更新后的整改任务
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 验证任务是否存在
        existing = supabase.table("qc_remediation_tasks").select("*").eq("id", task_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"整改任务不存在: {task_id}"
            )

        existing_task = existing.data[0]

        # 只能更新待整改或已退回的任务
        if existing_task["status"] not in [RemediationStatus.PENDING.value, RemediationStatus.REJECTED.value]:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能更新待整改或已退回状态的任务"
            )

        # 构建更新数据
        update_data = {}
        if task.defect_description is not None:
            update_data["defect_description"] = task.defect_description
        if task.defect_location is not None:
            update_data["defect_location"] = task.defect_location
        if task.severity is not None:
            update_data["severity"] = task.severity.value
        if task.remediation_requirement is not None:
            update_data["remediation_requirement"] = task.remediation_requirement
        if task.deadline is not None:
            update_data["deadline"] = task.deadline.isoformat()
        if task.assignee_id is not None:
            update_data["assignee_id"] = str(task.assignee_id)
        if task.assignee_name is not None:
            update_data["assignee_name"] = task.assignee_name
        if task.assignee_department is not None:
            update_data["assignee_department"] = task.assignee_department
        if task.notes is not None:
            update_data["notes"] = task.notes

        if not update_data:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="没有提供要更新的数据"
            )

        # 更新任务
        result = supabase.table("qc_remediation_tasks").update(update_data).eq("id", task_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_ERROR,
                detail="更新整改任务失败"
            )

        # 记录历史
        history_data = {
            "task_id": task_id,
            "action": HistoryAction.UPDATE.value,
            "actor_id": current_user["id"],
            "actor_name": current_user.get("name", current_user.get("email", "Unknown")),
            "comment": "更新整改任务信息"
        }
        supabase.table("qc_remediation_history").insert(history_data).execute()

        logger.info(
            f"Remediation task updated: {task_id}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="整改任务更新成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update remediation task: {str(e)}",
            extra={"trace_id": trace_id, "task_id": task_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"更新整改任务失败: {str(e)}"
        )


# ============================
# 整改流程
# ============================

@router.post("/{task_id}/submit", response_model=dict)
async def submit_remediation(
    request: Request,
    task_id: str,
    submit_data: RemediationSubmit,
    current_user: dict = Depends(get_current_user)
):
    """
    提交整改

    Args:
        task_id: 整改任务ID
        submit_data: 提交数据
        current_user: 当前用户

    Returns:
        更新后的整改任务
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 验证任务是否存在
        existing = supabase.table("qc_remediation_tasks").select("*").eq("id", task_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"整改任务不存在: {task_id}"
            )

        existing_task = existing.data[0]

        # 验证状态
        if existing_task["status"] not in [RemediationStatus.PENDING.value, RemediationStatus.IN_PROGRESS.value, RemediationStatus.REJECTED.value]:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能提交待整改、整改中或已退回的任务"
            )

        # 验证是否为负责人
        if existing_task["assignee_id"] != current_user["id"]:
            raise HTTPException(
                status_code=StatusCode.FORBIDDEN,
                detail="只有负责人可以提交整改"
            )

        # 更新状态为已提交
        update_data = {
            "status": RemediationStatus.SUBMITTED.value,
            "remediation_description": submit_data.remediation_description,
            "remediation_evidence": submit_data.remediation_evidence,
            "submitted_at": datetime.utcnow().isoformat()
        }

        result = supabase.table("qc_remediation_tasks").update(update_data).eq("id", task_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_ERROR,
                detail="提交整改失败"
            )

        # 记录历史
        history_data = {
            "task_id": task_id,
            "action": HistoryAction.SUBMIT.value,
            "actor_id": current_user["id"],
            "actor_name": current_user.get("name", current_user.get("email", "Unknown")),
            "old_status": existing_task["status"],
            "new_status": RemediationStatus.SUBMITTED.value,
            "comment": "提交整改"
        }
        supabase.table("qc_remediation_history").insert(history_data).execute()

        logger.info(
            f"Remediation submitted: {task_id}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="整改提交成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to submit remediation: {str(e)}",
            extra={"trace_id": trace_id, "task_id": task_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"提交整改失败: {str(e)}"
        )


@router.post("/{task_id}/review", response_model=dict)
async def review_remediation(
    request: Request,
    task_id: str,
    review_data: RemediationReview,
    current_user: dict = Depends(get_current_user)
):
    """
    验收整改

    Args:
        task_id: 整改任务ID
        review_data: 验收数据
        current_user: 当前用户

    Returns:
        验收后的整改任务
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 验证任务是否存在
        existing = supabase.table("qc_remediation_tasks").select("*").eq("id", task_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"整改任务不存在: {task_id}"
            )

        existing_task = existing.data[0]

        # 验证状态
        if existing_task["status"] != RemediationStatus.SUBMITTED.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="只能验收已提交的任务"
            )

        # 验证动作
        if review_data.action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="验收动作必须为 approve 或 reject"
            )

        # 更新状态
        new_status = RemediationStatus.APPROVED.value if review_data.action == "approve" else RemediationStatus.REJECTED.value

        update_data = {
            "status": new_status,
            "reviewer_id": current_user["id"],
            "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
            "review_comment": review_data.review_comment,
            "reviewed_at": datetime.utcnow().isoformat()
        }

        # 如果通过，设置关闭时间
        if review_data.action == "approve":
            update_data["closed_at"] = datetime.utcnow().isoformat()

        result = supabase.table("qc_remediation_tasks").update(update_data).eq("id", task_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_ERROR,
                detail="验收整改失败"
            )

        # 记录历史
        action = HistoryAction.APPROVE.value if review_data.action == "approve" else HistoryAction.REJECT.value
        history_data = {
            "task_id": task_id,
            "action": action,
            "actor_id": current_user["id"],
            "actor_name": current_user.get("name", current_user.get("email", "Unknown")),
            "old_status": existing_task["status"],
            "new_status": new_status,
            "comment": review_data.review_comment
        }
        supabase.table("qc_remediation_history").insert(history_data).execute()

        logger.info(
            f"Remediation reviewed: {task_id}, action: {review_data.action}",
            extra={"trace_id": trace_id, "reviewer_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="验收成功",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to review remediation: {str(e)}",
            extra={"trace_id": trace_id, "task_id": task_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"验收整改失败: {str(e)}"
        )


@router.post("/{task_id}/close", response_model=dict)
async def close_remediation_task(
    request: Request,
    task_id: str,
    close_data: RemediationClose,
    current_user: dict = Depends(get_current_user)
):
    """
    关闭整改任务

    Args:
        task_id: 整改任务ID
        close_data: 关闭数据
        current_user: 当前用户

    Returns:
        关闭后的整改任务
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 验证任务是否存在
        existing = supabase.table("qc_remediation_tasks").select("*").eq("id", task_id).execute()

        if not existing.data:
            raise HTTPException(
                status_code=StatusCode.NOT_FOUND,
                detail=f"整改任务不存在: {task_id}"
            )

        existing_task = existing.data[0]

        # 已关闭的任务不能再次关闭
        if existing_task["status"] == RemediationStatus.CLOSED.value:
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST,
                detail="任务已关闭"
            )

        # 更新状态为已关闭
        update_data = {
            "status": RemediationStatus.CLOSED.value,
            "closed_at": datetime.utcnow().isoformat()
        }

        if close_data.reason:
            update_data["notes"] = f"{existing_task.get('notes', '')}\n关闭原因: {close_data.reason}".strip()

        result = supabase.table("qc_remediation_tasks").update(update_data).eq("id", task_id).execute()

        if not result.data:
            raise HTTPException(
                status_code=StatusCode.INTERNAL_ERROR,
                detail="关闭整改任务失败"
            )

        # 记录历史
        history_data = {
            "task_id": task_id,
            "action": HistoryAction.CLOSE.value,
            "actor_id": current_user["id"],
            "actor_name": current_user.get("name", current_user.get("email", "Unknown")),
            "old_status": existing_task["status"],
            "new_status": RemediationStatus.CLOSED.value,
            "comment": close_data.reason or "关闭整改任务"
        }
        supabase.table("qc_remediation_history").insert(history_data).execute()

        logger.info(
            f"Remediation task closed: {task_id}",
            extra={"trace_id": trace_id, "user_id": current_user["id"]}
        )

        return success_response(
            data=result.data[0],
            message="整改任务已关闭",
            request=request
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to close remediation task: {str(e)}",
            extra={"trace_id": trace_id, "task_id": task_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"关闭整改任务失败: {str(e)}"
        )


# ============================
# 统计和报表
# ============================

@router.get("/statistics/summary", response_model=dict)
async def get_remediation_statistics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    获取整改统计

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
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 查询统计视图
        query = supabase.table("qc_remediation_statistics").select("*")
        result = query.execute()

        # 计算总览统计
        stats = {
            "total": 0,
            "pending": 0,
            "in_progress": 0,
            "submitted": 0,
            "approved": 0,
            "rejected": 0,
            "overdue": 0,
            "closed": 0,
            "avg_completion_time_hours": 0.0,
            "by_severity": {},
            "by_defect_type": {}
        }

        total_completion_time = 0
        completion_count = 0

        for row in result.data or []:
            status = row.get("status")
            severity = row.get("severity")
            defect_type = row.get("defect_type")
            count = row.get("count", 0)
            avg_time = row.get("avg_completion_time_seconds", 0)

            stats["total"] += count

            # 按状态统计
            if status in stats:
                stats[status] += count

            # 按严重程度统计
            if severity:
                stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + count

            # 按缺陷类型统计
            if defect_type:
                stats["by_defect_type"][defect_type] = stats["by_defect_type"].get(defect_type, 0) + count

            # 平均完成时间
            if avg_time and status == "approved":
                total_completion_time += avg_time * count
                completion_count += count

        if completion_count > 0:
            stats["avg_completion_time_hours"] = round(total_completion_time / completion_count / 3600, 2)

        return success_response(
            data=stats,
            request=request
        )

    except Exception as e:
        logger.error(
            f"Failed to get remediation statistics: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"获取统计数据失败: {str(e)}"
        )


@router.get("/statistics/workload", response_model=dict)
async def get_assignee_workload(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    获取责任人工作负载

    Args:
        current_user: 当前用户

    Returns:
        工作负载数据
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 查询工作负载视图
        result = supabase.table("qc_assignee_workload").select("*").execute()

        workload_list = result.data or []

        return success_response(
            data=workload_list,
            request=request
        )

    except Exception as e:
        logger.error(
            f"Failed to get assignee workload: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"获取工作负载失败: {str(e)}"
        )


@router.get("/statistics/overdue", response_model=dict)
async def get_overdue_tasks(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    获取逾期任务告警

    Args:
        current_user: 当前用户

    Returns:
        逾期任务列表
    """
    trace_id = get_trace_id(request)
    supabase = get_supabase()

    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail="数据库连接失败"
        )

    try:
        # 查询逾期任务
        now = datetime.utcnow().isoformat()
        result = supabase.table("qc_remediation_tasks").select("id, task_number, assignee_name, defect_description, deadline, severity").lt("deadline", now).in_("status", ["pending", "in_progress", "submitted", "rejected", "overdue"]).execute()

        overdue_tasks = []
        for task in result.data or []:
            if task.get("deadline"):
                deadline = datetime.fromisoformat(task["deadline"].replace("Z", "+00:00"))
                overdue_days = (datetime.utcnow() - deadline).days

                overdue_tasks.append({
                    "task_id": task["id"],
                    "task_number": task["task_number"],
                    "assignee_name": task["assignee_name"],
                    "defect_description": task["defect_description"],
                    "deadline": task["deadline"],
                    "overdue_days": overdue_days,
                    "severity": task["severity"]
                })

        # 按逾期天数排序
        overdue_tasks.sort(key=lambda x: x["overdue_days"], reverse=True)

        return success_response(
            data=overdue_tasks,
            request=request
        )

    except Exception as e:
        logger.error(
            f"Failed to get overdue tasks: {str(e)}",
            extra={"trace_id": trace_id}
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_ERROR,
            detail=f"获取逾期任务失败: {str(e)}"
        )
