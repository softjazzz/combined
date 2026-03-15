"""
任务管理完整路由

功能:
- 创建任务（单次/定时）
- 任务列表（我创建/我收到）
- 任务详情 + 包含的病历
- 执行抽样
- 分配任务
- 进度查看
- 重新质控
- 取消/删除任务
"""

import uuid
import logging
import random
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, HTTPException, Depends, Query

from ..schemas.tasks import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskAssignRequest,
    TaskRecordUpdateRequest,
    TaskStatus,
    TaskRecordStatus,
)
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id
from ..core.security import get_current_user
from ..core.permissions import (
    require_permission,
    require_role,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)



def _generate_task_number() -> str:
    """生成任务编号: QC-YYYYMMDD-XXXX"""
    date_str = datetime.now().strftime("%Y%m%d")
    seq = random.randint(1000, 9999)
    return f"QC-{date_str}-{seq}"


# ============================
# 创建任务
# ============================

@router.post("")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
async def create_task(
    request: Request,
    task_data: TaskCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    创建质控抽查任务
    """
    task_id = str(uuid.uuid4())
    task_number = _generate_task_number()

    task = {
        "id": task_id,
        "task_number": task_number,
        "task_name": task_data.task_name,
        "task_type": task_data.task_type.value,
        "schedule_config": task_data.schedule_config,
        "date_range": task_data.date_range,
        "department_filter": task_data.department_filter or [],
        "record_ids": task_data.record_ids or [],
        "sampling_method": task_data.sampling_method.value,
        "sampling_config": task_data.sampling_config or {},
        "assign_method": task_data.assign_method.value,
        "assignee_config": task_data.assignee_config or {},
        "status": TaskStatus.DRAFT.value,
        "progress": 0,
        "total_records": 0,
        "completed_records": 0,
        "creator_id": current_user.get("user_id", ""),
        "creator_name": current_user.get("display_name", ""),
        "deadline": task_data.deadline,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(sb.table('qc_tasks').insert(task))
        task = (getattr(resp, 'data', None) or [task])[0]
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

    return success_response(
        data=task,
        message=f"任务 {task_number} 创建成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 任务列表
# ============================

@router.get("")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def list_tasks(
    request: Request,
    tab: str = Query("all", description="标签: all=全部 | created=我创建 | received=我收到"),
    status: Optional[str] = Query(None, description="任务状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务列表（支持按标签/状态/关键词筛选）
    """
    user_id = current_user.get("user_id", "")

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        query = sb.table('qc_tasks').select('*', count='exact')

        if tab == "created":
            query = query.eq('creator_id', user_id)
        elif tab == "received":
            assigned_resp = await async_execute(
                sb.table('qc_task_records')
                .select('task_id')
                .eq('assignee_id', user_id)
            )
            assigned_task_ids = list(set(
                r.get('task_id') for r in (getattr(assigned_resp, 'data', None) or [])
                if r.get('task_id')
            ))
            if assigned_task_ids:
                query = query.in_('id', assigned_task_ids)
            else:
                return paginated_response(
                    items=[], total=0, page=page, page_size=page_size,
                    message="暂无收到的任务", trace_id=get_trace_id(request),
                )

        if status:
            query = query.eq('status', status)
        if keyword:
            query = query.or_(
                f"task_name.ilike.%{keyword}%,task_number.ilike.%{keyword}%"
            )

        offset = (page - 1) * page_size
        query = query.order('created_at', desc=True).range(offset, offset + page_size - 1)

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        total = getattr(resp, 'count', None) or len(data)

        return paginated_response(
            items=data, total=total, page=page, page_size=page_size,
            message="获取任务列表成功", trace_id=get_trace_id(request),
        )
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ============================
# 任务统计
# ============================

@router.get("/stats")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务统计数据（各状态数量）
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    status_counts = {}
    try:
        resp = await async_execute(
            sb.table('qc_tasks').select('status', count='exact')
        )
        rows = list(getattr(resp, 'data', None) or [])
        for r in rows:
            st = r.get('status', 'unknown')
            status_counts[st] = status_counts.get(st, 0) + 1
    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务统计失败: {str(e)}")

    total = sum(status_counts.values())

    return success_response(
        data={
            "total": total,
            "by_status": status_counts,
            "draft": status_counts.get("draft", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "completed": status_counts.get("completed", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
        message="获取任务统计成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 任务详情
# ============================

@router.get("/{task_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_detail(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务详情 + 包含的病历列表
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = None
    records = []

    try:
        resp = await async_execute(
            sb.table('qc_tasks').select('*').eq('id', task_id).single()
        )
        task = getattr(resp, 'data', None)
    except Exception as e:
        logger.error(f"查询任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询任务失败: {str(e)}")

    if task:
        try:
            resp = await async_execute(
                sb.table('qc_task_records')
                .select('*')
                .eq('task_id', task_id)
                .order('created_at')
            )
            records = list(getattr(resp, 'data', None) or [])
        except Exception as e:
            logger.error(f"查询任务记录失败: {e}")
            raise HTTPException(status_code=500, detail=f"查询任务记录失败: {str(e)}")

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    task["records"] = records

    return success_response(
        data=task,
        message="获取任务详情成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 更新任务
# ============================

@router.put("/{task_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def update_task(
    request: Request,
    task_id: str,
    update_data: TaskUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新任务基本信息"""
    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    update_fields["updated_at"] = datetime.now().isoformat()

    # 枚举转字符串
    for key in ["assign_method", "status"]:
        if key in update_fields and hasattr(update_fields[key], 'value'):
            update_fields[key] = update_fields[key].value

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(
            sb.table('qc_tasks').update(update_fields).eq('id', task_id)
        )
        data = (getattr(resp, 'data', None) or [{}])[0]
        return success_response(data=data, message="任务更新成功", trace_id=get_trace_id(request))
    except Exception as e:
        logger.error(f"更新任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


# ============================
# 执行抽样
# ============================

@router.post("/{task_id}/sample")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def execute_sampling(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    执行抽样 — 根据任务配置从病历库中抽取病历
    """
    from ..services.task_sampling_service import TaskSamplingService

    # 获取任务信息
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = None
    try:
        resp = await async_execute(
            sb.table('qc_tasks').select('*').eq('id', task_id).single()
        )
        task = getattr(resp, 'data', None)
    except Exception as e:
        logger.warning(f"查询任务失败: {e}")

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 执行抽样
    sampling_service = TaskSamplingService()
    sampled_records = await sampling_service.sample(task)

    # 创建任务-病历关联
    task_records = []
    for record in sampled_records:
        tr = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "record_id": record.get("id", record.get("record_id", "")),
            "assignee_id": None,
            "assignee_name": None,
            "status": TaskRecordStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
        }
        task_records.append(tr)

    # 保存到数据库
    if task_records:
        try:
            await async_execute(sb.table('qc_task_records').insert(task_records))
        except Exception as e:
            logger.error(f"保存任务病历关联失败: {e}")
            raise HTTPException(status_code=500, detail=f"保存抽样结果失败: {str(e)}")

    # 更新任务状态
    update_data = {
        "status": TaskStatus.SAMPLING.value,
        "total_records": len(task_records),
        "updated_at": datetime.now().isoformat(),
    }
    try:
        await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
    except Exception as e:
        logger.warning(f"更新任务抽样状态失败（非阻塞）: {e}")

    return success_response(
        data={
            "task_id": task_id,
            "sampled_count": len(task_records),
            "records": task_records[:20],
        },
        message=f"抽样完成，共抽取 {len(task_records)} 条病历",
        trace_id=get_trace_id(request),
    )


# ============================
# 分配任务
# ============================

@router.post("/{task_id}/assign")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def assign_task(
    request: Request,
    task_id: str,
    assign_data: TaskAssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    分配任务 — 将抽样好的病历分配给质控员
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    # 获取任务下所有待分配病历
    records = []
    try:
        resp = await async_execute(
            sb.table('qc_task_records')
            .select('*')
            .eq('task_id', task_id)
            .eq('status', 'pending')
        )
        records = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        logger.error(f"查询待分配病历失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询待分配病历失败: {str(e)}")

    if not records:
        raise HTTPException(status_code=400, detail="没有待分配的病历，请先执行抽样")

    # 按比例分配
    assignees = assign_data.assignees
    if not assignees:
        raise HTTPException(status_code=400, detail="请提供分配人员列表")

    batch_size = len(records) // len(assignees)
    remainder = len(records) % len(assignees)

    idx = 0
    updates = []
    for i, assignee in enumerate(assignees):
        count = batch_size + (1 if i < remainder else 0)
        for j in range(count):
            if idx < len(records):
                records[idx]["assignee_id"] = assignee.get("user_id", "")
                records[idx]["assignee_name"] = assignee.get("user_name", "")
                updates.append({
                    "id": records[idx]["id"],
                    "assignee_id": assignee.get("user_id", ""),
                    "assignee_name": assignee.get("user_name", ""),
                })
                idx += 1

    # 更新数据库
    fail_count = 0
    for update in updates:
        try:
            await async_execute(
                sb.table('qc_task_records')
                .update({"assignee_id": update["assignee_id"], "assignee_name": update["assignee_name"]})
                .eq('id', update["id"])
            )
        except Exception as e:
            fail_count += 1
            logger.warning(f"分配记录 {update['id']} 更新失败: {e}")
    if fail_count:
        logger.error(f"分配任务时 {fail_count}/{len(updates)} 条记录更新失败")

    # 更新任务状态为已分配
    status_update = {
        "status": TaskStatus.ASSIGNED.value,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        await async_execute(sb.table('qc_tasks').update(status_update).eq('id', task_id))
    except Exception as e:
        logger.warning(f"更新任务分配状态失败（非阻塞）: {e}")

    # 汇总分配结果
    assignment_summary = {}
    for assignee in assignees:
        name = assignee.get("user_name", "")
        count = sum(1 for u in updates if u["assignee_id"] == assignee.get("user_id"))
        assignment_summary[name] = count

    return success_response(
        data={
            "task_id": task_id,
            "total_assigned": len(updates),
            "assignment_summary": assignment_summary,
        },
        message=f"分配完成，共分配 {len(updates)} 条病历给 {len(assignees)} 名质控员",
        trace_id=get_trace_id(request),
    )


# ============================
# 进度查看
# ============================

@router.get("/{task_id}/progress")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_progress(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取任务执行进度"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(
            sb.table('v_qc_task_progress').select('*').eq('task_id', task_id).single()
        )
        data = getattr(resp, 'data', None)
        if data:
            return success_response(data=data, message="获取进度成功", trace_id=get_trace_id(request))
    except Exception as e:
        logger.warning(f"查询任务进度视图失败: {e}")

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 进度不存在")


# ============================
# 重新质控
# ============================

@router.post("/{task_id}/re-analyze")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def re_analyze_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    对任务内所有病历重新执行质控分析
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    records = []
    try:
        resp = await async_execute(
            sb.table('qc_task_records').select('record_id').eq('task_id', task_id)
        )
        records = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        logger.error(f"查询任务病历失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询任务病历失败: {str(e)}")

    record_ids = [r.get("record_id") for r in records if r.get("record_id")]

    if not record_ids:
        raise HTTPException(status_code=400, detail="任务中没有病历")

    # 触发批量质控
    from ..services.qc_service import QCService
    qc_service = QCService()

    started = []
    for rid in record_ids[:50]:
        try:
            result = await qc_service.evaluate({"record_id": rid})
            started.append({"record_id": rid, "status": "started"})
        except Exception as e:
            started.append({"record_id": rid, "status": "failed", "error": str(e)})

    # 更新任务状态
    update_data = {
        "status": TaskStatus.IN_PROGRESS.value,
        "completed_records": 0,
        "progress": 0,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
    except Exception as e:
        logger.warning(f"更新任务重新质控状态失败（非阻塞）: {e}")

    return success_response(
        data={
            "task_id": task_id,
            "total": len(record_ids),
            "started": len(started),
            "results": started,
        },
        message=f"已启动重新质控，共 {len(started)} 条病历",
        trace_id=get_trace_id(request),
    )


# ============================
# 取消/删除任务
# ============================

@router.delete("/{task_id}")
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def delete_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除任务（仅限管理员和质控主管）"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        await async_execute(sb.table('qc_tasks').delete().eq('id', task_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

    return success_response(
        data={"task_id": task_id},
        message="任务已删除",
        trace_id=get_trace_id(request),
    )


@router.post("/{task_id}/cancel")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def cancel_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """取消任务"""
    update_data = {
        "status": TaskStatus.CANCELLED.value,
        "updated_at": datetime.now().isoformat(),
    }

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")

    return success_response(
        data={"task_id": task_id, "status": TaskStatus.CANCELLED.value},
        message="任务已取消",
        trace_id=get_trace_id(request),
    )
