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
from functools import partial
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Dict, Any, List, Literal

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from starlette.concurrency import run_in_threadpool

from ..schemas.tasks import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskAssignRequest,
    TaskStatus,
)
from ..core.supabase_client import get_supabase, async_execute
from ..core.audit import audit_event
from ..core.response import success_response, paginated_response, get_trace_id
from ..core.security import get_current_user
from ..services.qc_rule_sets import get_sichuan_rule_set
from ..services.detached_task_runner import submit_detached_task
from ..services.product_activation import require_product_activation
from ..services.sichuan_qc_service import SichuanQCService
from ..services.task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunDispatchError,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    create_task_qc_run,
    list_task_qc_runs,
)
from ..services.task_assignment_service import (
    AssignmentConflict,
    AssignmentForbidden,
    AssignmentNotFound,
    assign_task_records,
    list_qc_assignee_options,
)
from ..services.task_start_service import (
    TaskStartConflict,
    TaskStartForbidden,
    TaskStartNotFound,
    start_assigned_task,
)
from .qc_sichuan import get_qc_service, _run_sichuan_workspace_batch_job, _sichuan_workspace_service
from ..core.permissions import (
    has_any_role,
    require_permission,
    require_role,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)
SHANGHAI_TZ = timezone(timedelta(hours=8))
TaskSceneFilter = Literal["running", "final", "outpatient", "unclassified"]



def _generate_task_number() -> str:
    """生成任务编号: QC-YYYYMMDD-XXXX"""
    date_str = datetime.now().strftime("%Y%m%d")
    seq = random.randint(1000, 9999)
    return f"QC-{date_str}-{seq}"


def _get_task_scope_user_id(current_user: dict) -> str:
    """读取任务个人范围身份；真实认证字段 id 优先，兼容历史 user_id。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(user_id)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_todo_as_of(value: Optional[str]) -> datetime:
    if value is None:
        return _utc_now()
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise HTTPException(status_code=422, detail="as_of 必须是带时区的 ISO 时间")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HTTPException(status_code=422, detail="as_of 必须包含时区")
    try:
        as_of = parsed.astimezone(timezone.utc)
        as_of + timedelta(hours=24)
    except (OverflowError, ValueError):
        raise HTTPException(status_code=422, detail="as_of 超出支持范围")
    return as_of


def _parse_task_deadline(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 10:
        try:
            return datetime.combine(date.fromisoformat(text), time.max, SHANGHAI_TZ).astimezone(
                timezone.utc
            )
        except (OverflowError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _task_matches_todo(task: dict, todo: str, as_of: datetime) -> bool:
    status = task.get("status")
    if todo in {"assigned", "in_progress"}:
        return status == todo
    if status not in {"assigned", "in_progress"}:
        return False
    deadline = _parse_task_deadline(task.get("deadline"))
    return deadline is not None and as_of < deadline <= as_of + timedelta(hours=24)


def _task_todo_counts(rows: List[dict], as_of: datetime) -> Dict[str, int]:
    return {
        "assigned": sum(row.get("status") == "assigned" for row in rows),
        "in_progress": sum(row.get("status") == "in_progress" for row in rows),
        "due_soon": sum(_task_matches_todo(row, "due_soon", as_of) for row in rows),
    }


async def _apply_task_tab_scope(sb, query, tab: str, current_user: dict):
    """让任务列表与统计复用同一 created/received 数据范围。"""
    if tab == "all":
        if not has_any_role(current_user, [UserRole.ADMIN, UserRole.QC_MANAGER]):
            raise HTTPException(status_code=403, detail="仅管理员和质控主管可查看全部任务")
        return query

    if tab not in {"created", "received"}:
        raise HTTPException(status_code=422, detail="无效的任务标签")

    user_id = _get_task_scope_user_id(current_user)
    if tab == "created":
        return query.eq("creator_id", user_id)

    if tab == "received":
        assigned_resp = await async_execute(
            sb.table("qc_task_records")
            .select("task_id")
            .eq("assignee_id", user_id)
        )
        assigned_task_ids = list(dict.fromkeys(
            row.get("task_id")
            for row in (getattr(assigned_resp, "data", None) or [])
            if row.get("task_id")
        ))
        if not assigned_task_ids:
            return None
        return query.in_("id", assigned_task_ids)


def _apply_task_scene_scope(query, scene: Optional[str]):
    """按任务创建意图筛选；历史空值只属于 unclassified。"""
    # 单元测试和内部调用可能绕过 FastAPI，此时参数仍是 Query(None)。
    if not isinstance(scene, str):
        scene = getattr(scene, "default", scene)
    if scene is None:
        return query
    if scene == "unclassified":
        return query.is_("scene", None)
    if scene in {"running", "final", "outpatient"}:
        return query.eq("scene", scene)
    raise HTTPException(status_code=422, detail="无效的任务场景")

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
    creator_id = _get_task_scope_user_id(current_user)
    rule_set = get_sichuan_rule_set(task_data.rule_set_key)
    if rule_set is None:
        raise HTTPException(status_code=422, detail="规则集不存在或不可用")
    if rule_set.scope != task_data.scene.value:
        raise HTTPException(status_code=422, detail="规则集与任务场景不匹配")
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
        "creator_id": creator_id,
        "creator_name": current_user.get("display_name", ""),
        "deadline": task_data.deadline,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    task["scene"] = task_data.scene.value
    task["rule_set_key"] = rule_set.key
    if task_data.record_refs:
        task["record_refs"] = [record_ref.model_dump() for record_ref in task_data.record_refs]

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(sb.table('qc_tasks').insert(task))
        rows = getattr(resp, 'data', None)
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or rows[0].get("id") != task["id"]
        ):
            raise RuntimeError("task_insert_returned_no_rows")
        task = rows[0]
    except Exception as e:
        logger.error("创建任务失败: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="创建任务失败，请稍后重试")

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
    tab: Literal["all", "created", "received"] = Query(
        "all", description="标签: all=全部 | created=我创建 | received=我收到"
    ),
    status: Optional[str] = Query(None, description="任务状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    scene: Optional[TaskSceneFilter] = Query(None, description="任务病历场景"),
    todo: Optional[Literal["assigned", "in_progress", "due_soon"]] = Query(
        None, description="个人待办范围"
    ),
    as_of: Optional[str] = Query(None, description="待办判断时点（带时区 ISO 时间）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务列表（支持按标签/状态/关键词筛选）
    """
    if todo and tab != "received":
        raise HTTPException(status_code=422, detail="todo 仅支持 received 标签")
    todo_as_of = _parse_todo_as_of(as_of) if todo or as_of is not None else None

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        if todo:
            query = sb.table('qc_tasks').select('*')
        else:
            query = sb.table('qc_tasks').select('*', count='exact')

        query = await _apply_task_tab_scope(sb, query, tab, current_user)
        if query is None:
            return paginated_response(
                items=[], total=0, page=page, page_size=page_size,
                message="暂无收到的任务", trace_id=get_trace_id(request),
            )
        query = _apply_task_scene_scope(query, scene)

        if status:
            query = query.eq('status', status)
        if keyword:
            query = query.or_(
                f"task_name.ilike.%{keyword}%,task_number.ilike.%{keyword}%"
            )

        query = query.order('created_at', desc=True)
        offset = (page - 1) * page_size
        if not todo:
            query = query.range(offset, offset + page_size - 1)

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        if todo:
            data = [
                row for row in data
                if _task_matches_todo(row, todo, todo_as_of)
            ]
            total = len(data)
            data = data[offset:offset + page_size]
        else:
            total = getattr(resp, 'count', None) or len(data)

        return paginated_response(
            items=data, total=total, page=page, page_size=page_size,
            message="获取任务列表成功", trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}")
        raise HTTPException(status_code=500, detail="查询任务列表失败，请稍后重试")


# ============================
# 任务统计
# ============================

@router.get("/stats")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_stats(
    request: Request,
    tab: Literal["all", "created", "received"] = Query(
        "all", description="标签: all=全部 | created=我创建 | received=我收到"
    ),
    scene: Optional[TaskSceneFilter] = Query(None, description="任务病历场景"),
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
        query = sb.table("qc_tasks").select("status", count="exact")
        query = await _apply_task_tab_scope(sb, query, tab, current_user)
        if query is not None:
            query = _apply_task_scene_scope(query, scene)
            resp = await async_execute(query)
            rows = list(getattr(resp, "data", None) or [])
            for row in rows:
                status = row.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取任务统计失败，请稍后重试")

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


@router.get("/todo-stats")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_todo_stats(
    request: Request,
    scene: Optional[TaskSceneFilter] = Query(None, description="任务病历场景"),
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户收到任务的待办计数。"""
    _get_task_scope_user_id(current_user)
    as_of = _utc_now()
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        query = sb.table("qc_tasks").select("id,status,deadline")
        query = await _apply_task_tab_scope(sb, query, "received", current_user)
        rows = []
        if query is not None:
            query = _apply_task_scene_scope(query, scene)
            resp = await async_execute(query)
            rows = list(getattr(resp, "data", None) or [])
        counts = _task_todo_counts(rows, as_of)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取任务待办统计失败: {exc}")
        raise HTTPException(status_code=500, detail="获取任务待办统计失败，请稍后重试") from exc

    return success_response(
        data={"as_of": as_of.isoformat(), **counts},
        message="获取任务待办统计成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 任务详情
# ============================

@router.get("/assignee-options")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def get_assignee_options(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        options = await run_in_threadpool(list_qc_assignee_options)
    except Exception as exc:
        logger.exception("读取质控员候选目录失败")
        raise HTTPException(status_code=503, detail="质控员目录暂不可用") from exc
    return success_response(data=options, trace_id=get_trace_id(request))


@router.get("/{task_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_detail(
    request: Request,
    task_id: str,
    tab: Literal["all", "created", "received"] = Query(
        "all", description="详情范围: all=全部 | created=我创建 | received=我收到"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务详情 + 包含的病历列表
    """
    scope_user_id = _get_task_scope_user_id(current_user) if tab != "all" else None
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = None
    records = []

    try:
        query = sb.table('qc_tasks').select('*').eq('id', task_id)
        query = await _apply_task_tab_scope(sb, query, tab, current_user)
        if query is not None:
            resp = await async_execute(query.single())
            task = getattr(resp, 'data', None)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务失败: {e}")
        raise HTTPException(status_code=500, detail="查询任务失败，请稍后重试")

    if task:
        try:
            query = (
                sb.table('qc_task_records')
                .select('*')
                .eq('task_id', task_id)
                .order('created_at')
                .order('id')
            )
            if tab == "received":
                query = query.eq('assignee_id', scope_user_id)
            resp = await async_execute(query)
            records = list(getattr(resp, 'data', None) or [])
        except Exception as e:
            logger.error(f"查询任务记录失败: {e}")
            raise HTTPException(status_code=500, detail="查询任务记录失败，请稍后重试")

    # 分配在两次读取之间可能被撤销，不能把空的个人关联当作仍有任务范围。
    if task is None or (tab == "received" and not records):
        raise HTTPException(status_code=404, detail="任务不存在或不在当前范围")

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
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def update_task(
    request: Request,
    task_id: str,
    update_data: TaskUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """仅允许已受领该任务的用户开始任务。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(start_assigned_task, task_id=task_id, actor_id=actor_id)
    except TaskStartNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStartForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskStartConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("开始任务失败 task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="数据库不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.start",
        resource="qc_task",
        outcome="success",
        details={"task_id": task_id, "idempotent": data.get("idempotent", False)},
        current_user=current_user,
    )
    return success_response(data=data, message="任务已开始", trace_id=get_trace_id(request))


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
    from anyio import to_thread
    from ..services.task_sampling_service import TaskSamplingService
    from ..services.task_sampling_persistence import (
        SamplingConflict,
        SamplingForbidden,
        SamplingTaskNotFound,
        save_task_sample,
    )

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
    except Exception as exc:
        logger.warning("抽样前查询任务失败", exc_info=True)
        raise HTTPException(status_code=503, detail="任务数据源不可用，请稍后重试") from exc

    if task is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    actor_id = _get_task_scope_user_id(current_user)
    if not task.get("creator_id") or task["creator_id"] != actor_id:
        raise HTTPException(status_code=403, detail="仅任务创建人可执行抽样")

    if task.get("status") not in {TaskStatus.DRAFT.value, TaskStatus.SAMPLING.value}:
        raise HTTPException(status_code=409, detail="当前任务状态不允许抽样")

    # 已保存的抽样结果由事务层重放，不能再次查询候选或生成新随机样本。
    sampled_records = []
    if task.get("status") == TaskStatus.DRAFT.value:
        sampling_service = TaskSamplingService()
        try:
            sampled_records = await sampling_service.sample(task)
        except NotImplementedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="候选病历数据源不可用，请稍后重试") from exc

    # 保存只调用一次；不能使用会在异常后重试 execute 的兼容适配器。
    try:
        saved_sample = await to_thread.run_sync(
            partial(save_task_sample, task, sampled_records, actor_id=actor_id)
        )
    except SamplingTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except SamplingForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SamplingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("原子保存抽样结果失败", exc_info=True)
        raise HTTPException(status_code=503, detail="保存抽样结果失败，请刷新任务后重试") from exc

    return success_response(
        data=saved_sample,
        message=f"抽样完成，共抽取 {saved_sample['sampled_count']} 条病历",
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
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            assign_task_records,
            task_id=task_id,
            actor_id=actor_id,
            assignees=[person.model_dump(exclude_none=True) for person in assign_data.assignees],
            method=assign_data.method.value,
        )
    except AssignmentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssignmentForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AssignmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("任务分配事务失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务分配暂不可用") from exc

    audit_event(
        request,
        action="tasks.assignment.update",
        resource="/api/v1/tasks/{task_id}/assign",
        outcome="success",
        current_user=current_user,
        details={
            "task_id": task_id,
            "total_assigned": result["total_assigned"],
            "assignees_count": len(assign_data.assignees),
            "idempotent": result["idempotent"],
            "assignment_summary": result["assignment_summary"],
            "assignment_details": result["assignment_details"],
        },
    )

    return success_response(
        data=result,
        message=f"分配完成，共分配 {result['total_assigned']} 条病历给 {len(assign_data.assignees)} 名质控员",
        trace_id=get_trace_id(request),
    )


# ============================
# 进度查看
# ============================

@router.post("/{task_id}/qc-runs")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def start_task_qc_run(
    request: Request,
    task_id: str,
    current_user: dict = Depends(require_product_activation),
    qc_service: SichuanQCService = Depends(get_qc_service),
):
    actor_id = _get_task_scope_user_id(current_user)

    def dispatch(job_id: str) -> None:
        submit_detached_task("sichuan_workspace_batch_job", _run_sichuan_workspace_batch_job, job_id)

    try:
        result = await run_in_threadpool(
            create_task_qc_run,
            task_id=task_id,
            actor_id=actor_id,
            current_user=current_user,
            workspace_factory=_sichuan_workspace_service,
            qc_service=qc_service,
            dispatch=dispatch,
        )
    except TaskQCRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskQCRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskQCRunDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("启动任务质控失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务质控服务不可用，请稍后重试") from exc
    return success_response(data=result, message="已启动任务质控", trace_id=get_trace_id(request))


@router.get("/{task_id}/qc-runs")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_qc_runs(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    actor_id = _get_task_scope_user_id(current_user)
    try:
        runs = await run_in_threadpool(list_task_qc_runs, task_id=task_id, actor_id=actor_id)
    except TaskQCRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("查询任务质控运行历史失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务运行历史不可用，请稍后重试") from exc
    return success_response(data=runs, message="获取任务质控运行历史成功", trace_id=get_trace_id(request))


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
    actor_id = _get_task_scope_user_id(current_user)
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        task_response = await async_execute(
            sb.table('qc_tasks').select('*').eq('id', task_id).single()
        )
        task = getattr(task_response, 'data', None)
    except Exception as exc:
        logger.warning("重新质控前查询任务失败", exc_info=True)
        raise HTTPException(status_code=503, detail="任务数据源不可用，请稍后重试") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.get("creator_id") or task["creator_id"] != actor_id:
        raise HTTPException(status_code=403, detail="仅任务创建人可重新质控")
    if task.get("scene") is not None:
        raise HTTPException(status_code=409, detail="场景任务尚未接通真实批量质控，请勿使用旧重新质控入口")

    records = []
    try:
        resp = await async_execute(
            sb.table('qc_task_records').select('record_id').eq('task_id', task_id)
        )
        records = list(getattr(resp, 'data', None) or [])
    except Exception as exc:
        logger.warning("重新质控前查询任务病历失败", exc_info=True)
        raise HTTPException(status_code=503, detail="任务病历数据源不可用，请稍后重试") from exc

    record_ids = [r.get("record_id") for r in records if r.get("record_id")]

    if not record_ids:
        raise HTTPException(status_code=400, detail="任务中没有病历")

    # 触发批量质控
    from ..services.qc_service import QCService
    qc_service = QCService()

    batch_ids = record_ids[:50]
    results = []
    succeeded = 0
    for rid in batch_ids:
        try:
            await qc_service.evaluate({"record_id": rid})
            results.append({"record_id": rid, "status": "started"})
            succeeded += 1
        except Exception as exc:
            logger.warning("旧任务重新质控单条失败: task_id=%s, type=%s", task_id, type(exc).__name__)
            results.append({"record_id": rid, "status": "failed", "error": "质控分析失败"})

    attempted = len(batch_ids)
    failed = attempted - succeeded
    not_attempted = len(record_ids) - attempted
    if succeeded == 0:
        raise HTTPException(status_code=503, detail=f"本次尝试 {attempted} 条病历，均质控失败，请稍后重试")

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
            "attempted": attempted,
            "started": succeeded,
            "failed": failed,
            "not_attempted": not_attempted,
            "partial": failed > 0 or not_attempted > 0,
            "results": results,
        },
        message=(
            f"重新质控部分完成：本次尝试 {attempted} 条，成功 {succeeded} 条，"
            f"失败 {failed} 条，未尝试 {not_attempted} 条"
            if failed or not_attempted else f"已启动重新质控，本次成功 {succeeded} 条"
        ),
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

    audit_event(
        request,
        action="tasks.lifecycle.delete",
        resource="/api/v1/tasks/{task_id}",
        outcome="success",
        current_user=current_user,
        details={"task_id": task_id},
    )

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

    audit_event(
        request,
        action="tasks.lifecycle.cancel",
        resource="/api/v1/tasks/{task_id}/cancel",
        outcome="success",
        current_user=current_user,
        details={"task_id": task_id, "status": TaskStatus.CANCELLED.value},
    )

    return success_response(
        data={"task_id": task_id, "status": TaskStatus.CANCELLED.value},
        message="任务已取消",
        trace_id=get_trace_id(request),
    )
