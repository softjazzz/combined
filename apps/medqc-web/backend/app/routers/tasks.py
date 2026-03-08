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

# 内存存储（Supabase 不可用时的回退）
_tasks_memory: Dict[str, Dict] = {}
_task_records_memory: Dict[str, List[Dict]] = {}


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
    if sb is not None:
        try:
            resp = await async_execute(sb.table('qc_tasks').insert(task))
            task = (getattr(resp, 'data', None) or [task])[0]
        except Exception as e:
            logger.warning(f"Supabase 插入任务失败，回退到内存: {e}")
            _tasks_memory[task_id] = task
    else:
        _tasks_memory[task_id] = task

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
    if sb is not None:
        try:
            query = sb.table('qc_tasks').select('*', count='exact')

            if tab == "created":
                query = query.eq('creator_id', user_id)
            elif tab == "received":
                # 收到的任务：在 qc_task_records 中有分配记录
                # 先查出分配给当前用户的 task_id
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
            logger.warning(f"Supabase 查询任务失败: {e}")

    # 回退到内存
    tasks = list(_tasks_memory.values())
    if tab == "created":
        tasks = [t for t in tasks if t.get("creator_id") == user_id]
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if keyword:
        kw = keyword.lower()
        tasks = [t for t in tasks if kw in t.get("task_name", "").lower() or kw in t.get("task_number", "").lower()]

    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(tasks)
    offset = (page - 1) * page_size
    items = tasks[offset:offset + page_size]

    return paginated_response(
        items=items, total=total, page=page, page_size=page_size,
        message="获取任务列表成功", trace_id=get_trace_id(request),
    )


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
    status_counts = {}

    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_tasks').select('status', count='exact')
            )
            rows = list(getattr(resp, 'data', None) or [])
            for r in rows:
                st = r.get('status', 'unknown')
                status_counts[st] = status_counts.get(st, 0) + 1
        except Exception as e:
            logger.warning(f"获取任务统计失败: {e}")

    if not status_counts:
        # 从内存聚合
        for task in _tasks_memory.values():
            st = task.get("status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1

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
    task = None
    records = []

    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_tasks').select('*').eq('id', task_id).single()
            )
            task = getattr(resp, 'data', None)
        except Exception:
            pass

        if task:
            try:
                resp = await async_execute(
                    sb.table('qc_task_records')
                    .select('*')
                    .eq('task_id', task_id)
                    .order('created_at')
                )
                records = list(getattr(resp, 'data', None) or [])
            except Exception:
                pass

    if task is None:
        task = _tasks_memory.get(task_id)
        records = _task_records_memory.get(task_id, [])

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
    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_tasks').update(update_fields).eq('id', task_id)
            )
            data = (getattr(resp, 'data', None) or [{}])[0]
            return success_response(data=data, message="任务更新成功", trace_id=get_trace_id(request))
        except Exception as e:
            logger.warning(f"Supabase 更新失败: {e}")

    if task_id in _tasks_memory:
        _tasks_memory[task_id].update(update_fields)
        return success_response(
            data=_tasks_memory[task_id],
            message="任务更新成功",
            trace_id=get_trace_id(request),
        )

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


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
    task = None

    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_tasks').select('*').eq('id', task_id).single()
            )
            task = getattr(resp, 'data', None)
        except Exception:
            pass

    if task is None:
        task = _tasks_memory.get(task_id)

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
    if sb is not None and task_records:
        try:
            await async_execute(sb.table('qc_task_records').insert(task_records))
        except Exception as e:
            logger.warning(f"保存任务病历关联失败: {e}")
            _task_records_memory[task_id] = task_records
    else:
        _task_records_memory[task_id] = task_records

    # 更新任务状态
    update_data = {
        "status": TaskStatus.SAMPLING.value,
        "total_records": len(task_records),
        "updated_at": datetime.now().isoformat(),
    }

    if sb is not None:
        try:
            await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
        except Exception:
            pass
    if task_id in _tasks_memory:
        _tasks_memory[task_id].update(update_data)

    return success_response(
        data={
            "task_id": task_id,
            "sampled_count": len(task_records),
            "records": task_records[:20],  # 只返回前20条预览
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

    # 获取任务下所有待分配病历
    records = []
    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_task_records')
                .select('*')
                .eq('task_id', task_id)
                .eq('status', 'pending')
            )
            records = list(getattr(resp, 'data', None) or [])
        except Exception:
            pass

    if not records:
        records = [r for r in _task_records_memory.get(task_id, []) if r.get('status') == 'pending']

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
    if sb is not None:
        for update in updates:
            try:
                await async_execute(
                    sb.table('qc_task_records')
                    .update({"assignee_id": update["assignee_id"], "assignee_name": update["assignee_name"]})
                    .eq('id', update["id"])
                )
            except Exception:
                pass

    # 更新任务状态为已分配
    status_update = {
        "status": TaskStatus.ASSIGNED.value,
        "updated_at": datetime.now().isoformat(),
    }
    if sb is not None:
        try:
            await async_execute(sb.table('qc_tasks').update(status_update).eq('id', task_id))
        except Exception:
            pass
    if task_id in _tasks_memory:
        _tasks_memory[task_id].update(status_update)

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

    if sb is not None:
        try:
            # 使用视图
            resp = await async_execute(
                sb.table('v_qc_task_progress').select('*').eq('task_id', task_id).single()
            )
            data = getattr(resp, 'data', None)
            if data:
                return success_response(data=data, message="获取进度成功", trace_id=get_trace_id(request))
        except Exception as e:
            logger.warning(f"查询任务进度视图失败: {e}")

    # 回退：从内存计算
    task = _tasks_memory.get(task_id)
    records = _task_records_memory.get(task_id, [])

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    total = len(records)
    done = sum(1 for r in records if r.get("status") == "completed")
    working = sum(1 for r in records if r.get("status") == "in_progress")
    pending = sum(1 for r in records if r.get("status") == "pending")
    scores = [r.get("score") for r in records if r.get("score") is not None]
    total_defects = sum(r.get("defect_count", 0) for r in records)

    return success_response(
        data={
            "task_id": task_id,
            "task_name": task.get("task_name", ""),
            "total_records": total,
            "completed_records": done,
            "progress_pct": round(done / max(total, 1) * 100, 1),
            "pending_count": pending,
            "working_count": working,
            "done_count": done,
            "avg_score": round(sum(scores) / max(len(scores), 1), 1) if scores else None,
            "total_defects": total_defects,
        },
        message="获取进度成功",
        trace_id=get_trace_id(request),
    )


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
    records = []

    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_task_records').select('record_id').eq('task_id', task_id)
            )
            records = list(getattr(resp, 'data', None) or [])
        except Exception:
            pass

    if not records:
        records = _task_records_memory.get(task_id, [])

    record_ids = [r.get("record_id") for r in records if r.get("record_id")]

    if not record_ids:
        raise HTTPException(status_code=400, detail="任务中没有病历")

    # 触发批量质控（异步，通过已有的 QC 服务）
    from ..services.qc_service import QCService
    qc_service = QCService()

    started = []
    for rid in record_ids[:50]:  # 限制单次最多50条
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
    if sb is not None:
        try:
            await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
        except Exception:
            pass
    if task_id in _tasks_memory:
        _tasks_memory[task_id].update(update_data)

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

    if sb is not None:
        try:
            await async_execute(sb.table('qc_tasks').delete().eq('id', task_id))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    else:
        if task_id in _tasks_memory:
            del _tasks_memory[task_id]
            _task_records_memory.pop(task_id, None)
        else:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

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
    if sb is not None:
        try:
            await async_execute(sb.table('qc_tasks').update(update_data).eq('id', task_id))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"取消失败: {str(e)}")
    else:
        if task_id in _tasks_memory:
            _tasks_memory[task_id].update(update_data)
        else:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return success_response(
        data={"task_id": task_id, "status": TaskStatus.CANCELLED.value},
        message="任务已取消",
        trace_id=get_trace_id(request),
    )
