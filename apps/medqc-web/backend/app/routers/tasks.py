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

from fastapi import APIRouter, Request, HTTPException, Depends, Query, Body
from starlette.concurrency import run_in_threadpool

from ..schemas.tasks import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskAssignRequest,
    TaskBatchAssignRequest,
    TaskRecordCompleteRequest,
    TaskManualDefectCreateRequest,
    TaskManualDefectResponse,
    TaskTemplateCreateRequest,
    TaskTemplateUpdateRequest,
    AssignMethod,
    TaskStatus,
)
from ..core.supabase_client import get_supabase, async_execute
from ..core.audit import audit_event
from ..core.response import success_response, paginated_response, get_trace_id
from ..core.security import get_current_user
from ..services.qc_rule_sets import get_sichuan_rule_set
from ..services.rule_set_version_service import (
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    current_version,
)
from ..services.detached_task_runner import submit_detached_task
from ..services.product_activation import require_product_activation
from ..services.sichuan_qc_service import SichuanQCService
from ..services.task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunDispatchError,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    create_task_qc_run,
    get_task_qc_run_record_result,
    list_task_qc_runs,
)
from ..services.task_record_sync_service import (
    TaskRecordSyncConflict,
    TaskRecordSyncForbidden,
    TaskRecordSyncNotFound,
)
from ..services.task_record_sync_job_service import (
    TaskRecordSyncRateLimited,
    TaskRecordSyncUnavailable,
    enqueue_task_record_sync,
    get_latest_task_record_sync_job,
    get_task_record_sync_job,
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
    start_assigned_task_record,
)
from ..services.task_record_completion_service import (
    TaskRecordCompletionConflict,
    TaskRecordCompletionForbidden,
    TaskRecordCompletionNotFound,
    TaskRecordCompletionUnavailable,
    complete_assigned_task_record,
)
from ..services.task_manual_defect_service import (
    TaskManualDefectConflict,
    TaskManualDefectForbidden,
    TaskManualDefectNotFound,
    TaskManualDefectUnavailable,
    create_task_manual_defect,
    list_task_manual_defects,
)
from ..services.task_cancel_service import (
    TaskCancelConflict,
    TaskCancelForbidden,
    TaskCancelNotFound,
    cancel_task as cancel_task_transaction,
)
from ..services.task_delete_service import (
    TaskDeleteConflict,
    TaskDeleteNotFound,
    delete_empty_draft_task,
)
from ..services.task_sampling_service import (
    validate_active_running_date_range,
    validate_scoped_sampling_config,
)
from ..services.task_template_service import (
    TaskTemplateConflict,
    TaskTemplateInvalid,
    TaskTemplateNotFound,
    TaskTemplateUnavailable,
    create_task_template,
    delete_task_template,
    list_task_templates,
    update_task_template,
)
from ..services.task_list_filter_service import (
    TaskDepartmentScopeInvalid,
    TaskListFilter,
    TaskListFilterInvalid,
    parse_saved_departments,
    parse_task_list_filter,
    postgres_timestamp,
    task_matches_department,
)
from .qc_sichuan import get_qc_service, _run_sichuan_workspace_batch_job, _sichuan_workspace_service
from ..core.permissions import (
    has_any_role,
    require_permission,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)
SHANGHAI_TZ = timezone(timedelta(hours=8))
TaskSceneFilter = Literal["running", "final", "outpatient", "unclassified"]
_TODO_READ_PAGE_SIZE = 500
_TODO_TASK_ID_CHUNK_SIZE = 200
_TODO_MAX_ASSIGNMENTS = 50000
_TASK_FILTER_READ_PAGE_SIZE = 500



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


async def _received_task_ids(sb, current_user: dict) -> List[str]:
    """完整读取受领关系；超出本接口可处理规模时显式失败。"""
    user_id = _get_task_scope_user_id(current_user)
    ids: Dict[str, None] = {}
    offset = 0
    expected_count = None
    while True:
        resp = await async_execute(
            sb.table("qc_task_records")
            .select("task_id", count="exact")
            .eq("assignee_id", user_id)
            .order("id")
            .range(offset, offset + _TODO_READ_PAGE_SIZE - 1)
        )
        page = list(getattr(resp, "data", None) or [])
        count = getattr(resp, "count", None)
        if not isinstance(count, int) or count < offset + len(page):
            raise HTTPException(status_code=503, detail="任务受领关系总数不可验证")
        if expected_count is not None and count != expected_count:
            raise HTTPException(status_code=503, detail="任务受领关系读取期间发生变化，请重试")
        expected_count = count
        if not page and offset < count:
            raise HTTPException(status_code=503, detail="任务受领关系读取不完整，请稍后重试")
        offset += len(page)
        if count > _TODO_MAX_ASSIGNMENTS:
            raise HTTPException(status_code=503, detail="任务受领关系超出待办查询上限")
        for row in page:
            if row.get("task_id"):
                ids[row["task_id"]] = None
        if offset >= count:
            break
    return list(ids)


async def _received_todo_rows(
    sb, current_user: dict, scene: Optional[str], *,
    columns: str, status: Optional[str] = None, keyword: Optional[str] = None,
    task_filter: TaskListFilter | None = None,
) -> List[dict]:
    task_filter = task_filter or parse_task_list_filter()
    task_ids = await _received_task_ids(sb, current_user)
    rows: List[dict] = []
    for start in range(0, len(task_ids), _TODO_TASK_ID_CHUNK_SIZE):
        chunk = task_ids[start:start + _TODO_TASK_ID_CHUNK_SIZE]
        offset = 0
        expected_count = None
        while True:
            query = sb.table("qc_tasks").select(columns, count="exact").in_("id", chunk)
            query = _apply_task_scene_scope(query, scene)
            if status:
                query = query.eq("status", status)
            query = _apply_task_keyword_scope(query, keyword)
            query = _apply_task_created_scope(query, task_filter)
            resp = await async_execute(
                query.order("id").range(offset, offset + _TODO_TASK_ID_CHUNK_SIZE - 1)
            )
            page = list(getattr(resp, "data", None) or [])
            count = getattr(resp, "count", None)
            if not isinstance(count, int) or count > len(chunk) or count < offset + len(page):
                raise HTTPException(status_code=503, detail="任务待办总数不可验证")
            if expected_count is not None and count != expected_count:
                raise HTTPException(status_code=503, detail="任务待办读取期间发生变化，请重试")
            expected_count = count
            if not page and offset < count:
                raise HTTPException(status_code=503, detail="任务待办读取不完整，请稍后重试")
            rows.extend(
                row for row in page
                if task_matches_department(row.get("department_filter"), task_filter.department)
            )
            offset += len(page)
            if offset >= count:
                break
    return rows


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


def _apply_task_keyword_scope(query, keyword: Optional[str]):
    """任务名称/编号关键词只作为绑定值，不解析为 PostgREST 条件。"""
    if not keyword:
        return query
    structured_or = getattr(query, "or_ilike", None)
    if not callable(structured_or):
        raise HTTPException(status_code=503, detail="任务关键词筛选暂不可用")
    return structured_or(("task_name", "task_number"), f"%{keyword}%")


def _apply_task_created_scope(query, task_filter: TaskListFilter):
    if task_filter.utc_start is not None:
        query = query.gte("created_at", postgres_timestamp(task_filter.utc_start))
    if task_filter.utc_end_exclusive is not None:
        query = query.lt("created_at", postgres_timestamp(task_filter.utc_end_exclusive))
    return query


async def _read_all_task_filter_rows(
    sb,
    *,
    tab: str,
    current_user: dict,
    scene: Optional[str],
    status: Optional[str],
    keyword: Optional[str],
    task_filter: TaskListFilter,
    columns: str = "*",
    apply_department: bool = True,
) -> List[dict]:
    """稳定分页读取全部候选任务；科室精确匹配必须先于计数和分页。"""
    query = sb.table("qc_tasks").select(columns, count="exact")
    query = await _apply_task_tab_scope(sb, query, tab, current_user)
    if query is None:
        return []
    query = _apply_task_scene_scope(query, scene)
    if status:
        query = query.eq("status", status)
    query = _apply_task_keyword_scope(query, keyword)
    query = _apply_task_created_scope(query, task_filter)
    query = query.order("created_at", desc=True).order("id", desc=True)

    rows: List[dict] = []
    offset = 0
    expected_count: Optional[int] = None
    while True:
        resp = await async_execute(
            query.range(offset, offset + _TASK_FILTER_READ_PAGE_SIZE - 1)
        )
        page = list(getattr(resp, "data", None) or [])
        count = getattr(resp, "count", None)
        if type(count) is not int or count < offset + len(page):
            raise HTTPException(status_code=503, detail="任务列表总数不可验证")
        if expected_count is not None and count != expected_count:
            raise HTTPException(status_code=503, detail="任务列表读取期间发生变化，请重试")
        expected_count = count
        if not page and offset < count:
            raise HTTPException(status_code=503, detail="任务列表读取不完整，请稍后重试")
        rows.extend(page)
        offset += len(page)
        if offset >= count:
            break

    if not apply_department:
        return rows
    return [
        row for row in rows
        if task_matches_department(row.get("department_filter"), task_filter.department)
    ]

# ============================
# 创建任务
# ============================

_CREATABLE_ASSIGN_METHODS = frozenset({
    AssignMethod.BY_RATIO, AssignMethod.BY_ORIGINAL_REVIEWER, AssignMethod.BY_DEPARTMENT,
})


def _validate_creation_assign_method(task_data: TaskCreateRequest) -> None:
    """创建时只接受可执行的分配方式；按原质控员须在 assignee_config.fallback 给出处理方式。"""
    method = task_data.assign_method
    if method == AssignMethod.BY_RECORD_TYPE:
        raise HTTPException(status_code=422, detail={
            "code": "method_unavailable",
            "message": "按病历类型分配暂不可用",
            "reason": "当前可抽样场景内病历类型相同，没有可区分的权威事实",
        })
    if method not in _CREATABLE_ASSIGN_METHODS:
        raise HTTPException(status_code=422, detail="新建任务不支持该分配方式")
    if method == AssignMethod.BY_ORIGINAL_REVIEWER:
        fallback = (task_data.assignee_config or {}).get("fallback")
        if fallback not in {"by_ratio", "reject"}:
            raise HTTPException(
                status_code=422,
                detail="按原质控员分配须在 assignee_config.fallback 指定 by_ratio 或 reject",
            )


def _task_template_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaskTemplateNotFound):
        return HTTPException(status_code=404, detail={
            "code": "template_not_found", "message": "任务模板不存在",
        })
    if isinstance(exc, TaskTemplateConflict):
        return HTTPException(status_code=409, detail={
            "code": exc.code, "message": str(exc),
        })
    if isinstance(exc, TaskTemplateInvalid):
        return HTTPException(status_code=422, detail={
            "code": exc.code, "message": str(exc),
        })
    return HTTPException(status_code=503, detail={
        "code": "template_unavailable", "message": "任务模板服务暂不可用，请稍后重试",
    })


@router.get("/templates")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def list_templates(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    owner_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(list_task_templates, owner_id=owner_id)
    except (TaskTemplateNotFound, TaskTemplateConflict, TaskTemplateInvalid, TaskTemplateUnavailable) as exc:
        raise _task_template_error(exc) from exc
    except Exception as exc:
        logger.warning("任务模板列表读取失败: type=%s", type(exc).__name__)
        raise _task_template_error(TaskTemplateUnavailable()) from exc
    return success_response(data=result, trace_id=get_trace_id(request))


@router.post("/templates")
@require_permission(ResourceType.QC_TASKS, PermissionAction.CREATE)
async def create_template(
    request: Request,
    payload: TaskTemplateCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    owner_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            create_task_template,
            owner_id=owner_id,
            name=payload.name,
            config=payload.config,
        )
    except (TaskTemplateNotFound, TaskTemplateConflict, TaskTemplateInvalid, TaskTemplateUnavailable) as exc:
        raise _task_template_error(exc) from exc
    except Exception as exc:
        logger.warning("任务模板创建失败: type=%s", type(exc).__name__)
        raise _task_template_error(TaskTemplateUnavailable()) from exc
    audit_event(
        request,
        action="tasks.template.create",
        resource="/api/v1/tasks/templates",
        outcome="success",
        current_user=current_user,
        details={"template_id": result["id"], "version": result["version"]},
    )
    return success_response(data=result, message="任务模板已保存", trace_id=get_trace_id(request))


@router.put("/templates/{template_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def update_template(
    request: Request,
    template_id: str,
    payload: TaskTemplateUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    owner_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            update_task_template,
            owner_id=owner_id,
            template_id=template_id,
            version=payload.version,
            name=payload.name,
            config=payload.config,
        )
    except (TaskTemplateNotFound, TaskTemplateConflict, TaskTemplateInvalid, TaskTemplateUnavailable) as exc:
        raise _task_template_error(exc) from exc
    except Exception as exc:
        logger.warning("任务模板更新失败: type=%s", type(exc).__name__)
        raise _task_template_error(TaskTemplateUnavailable()) from exc
    audit_event(
        request,
        action="tasks.template.update",
        resource="/api/v1/tasks/templates/{template_id}",
        outcome="success",
        current_user=current_user,
        details={"template_id": result["id"], "version": result["version"]},
    )
    return success_response(data=result, message="任务模板已更新", trace_id=get_trace_id(request))


@router.delete("/templates/{template_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.DELETE)
async def remove_template(
    request: Request,
    template_id: str,
    version: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
):
    owner_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            delete_task_template,
            owner_id=owner_id,
            template_id=template_id,
            version=version,
        )
    except (TaskTemplateNotFound, TaskTemplateConflict, TaskTemplateInvalid, TaskTemplateUnavailable) as exc:
        raise _task_template_error(exc) from exc
    except Exception as exc:
        logger.warning("任务模板删除失败: type=%s", type(exc).__name__)
        raise _task_template_error(TaskTemplateUnavailable()) from exc
    audit_event(
        request,
        action="tasks.template.delete",
        resource="/api/v1/tasks/templates/{template_id}",
        outcome="success",
        current_user=current_user,
        details={"template_id": template_id, "version": version},
    )
    return success_response(data=result, message="任务模板已删除", trace_id=get_trace_id(request))


@router.post("")
@require_permission(ResourceType.QC_TASKS, PermissionAction.CREATE)
async def create_task(
    request: Request,
    task_data: TaskCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    创建质控抽查任务
    """
    creator_id = _get_task_scope_user_id(current_user)
    if task_data.task_type.value != "one_time":
        raise HTTPException(status_code=422, detail="定时任务请通过定时计划入口创建")
    if task_data.schedule_config is not None:
        raise HTTPException(status_code=422, detail="单次任务不能携带定时计划配置")
    rule_set = get_sichuan_rule_set(task_data.rule_set_key)
    if rule_set is None:
        raise HTTPException(status_code=422, detail="规则集不存在或不可用")
    if rule_set.scope != task_data.scene.value:
        raise HTTPException(status_code=422, detail="规则集与任务场景不匹配")
    _validate_creation_assign_method(task_data)
    if task_data.scene.value == "outpatient" or (
        task_data.scene.value == "running"
        and (task_data.sampling_config or {}).get("case_scope") == "active"
    ):
        try:
            validate_scoped_sampling_config(
                task_data.scene.value,
                task_data.sampling_method.value,
                task_data.sampling_config or {},
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if task_data.scene.value == "running" and (task_data.sampling_config or {}).get("case_scope") == "active":
        try:
            validate_active_running_date_range(task_data.date_range)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    # 任务冻结创建时的当前规则集版本（最近一次发布；未发布时为内置版本）。
    try:
        frozen_rule_set_version = await run_in_threadpool(current_version, rule_set.key)
    except RuleSetVersionNotFound as exc:
        raise HTTPException(status_code=422, detail="规则集不存在或不可用") from exc
    except RuleSetVersionUnavailable as exc:
        raise HTTPException(status_code=503, detail="规则集版本暂不可读取，请稍后重试") from exc
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
        "attempt_count": 0,
        "creator_id": creator_id,
        "creator_name": current_user.get("display_name", ""),
        "deadline": task_data.deadline,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    task["scene"] = task_data.scene.value
    task["rule_set_key"] = rule_set.key
    task["rule_set_version"] = frozen_rule_set_version
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def list_tasks(
    request: Request,
    tab: Literal["all", "created", "received"] = Query(
        "all", description="标签: all=全部 | created=我创建 | received=我收到"
    ),
    status: Optional[str] = Query(None, description="任务状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    scene: Optional[TaskSceneFilter] = Query(None, description="任务病历场景"),
    department: Optional[str] = Query(None, description="任务保存范围中的精确科室名称"),
    created_start: Optional[str] = Query(None, description="创建日期起始（医院日历 YYYY-MM-DD）"),
    created_end: Optional[str] = Query(None, description="创建日期结束（医院日历 YYYY-MM-DD）"),
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
    try:
        task_filter = parse_task_list_filter(
            department=department,
            created_start=created_start,
            created_end=created_end,
        )
    except TaskListFilterInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        if todo:
            data = await _received_todo_rows(
                sb, current_user, scene, columns="*", status=status, keyword=keyword,
                task_filter=task_filter,
            )
            data = [row for row in data if _task_matches_todo(row, todo, todo_as_of)]
            data.sort(
                key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")),
                reverse=True,
            )
            offset = (page - 1) * page_size
            total = len(data)
            data = data[offset:offset + page_size]
        elif task_filter.department is not None:
            data = await _read_all_task_filter_rows(
                sb,
                tab=tab,
                current_user=current_user,
                scene=scene,
                status=status,
                keyword=keyword,
                task_filter=task_filter,
            )
            offset = (page - 1) * page_size
            total = len(data)
            data = data[offset:offset + page_size]
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
            query = _apply_task_keyword_scope(query, keyword)
            query = _apply_task_created_scope(query, task_filter)

            query = query.order('created_at', desc=True).order('id', desc=True)
            offset = (page - 1) * page_size
            query = query.range(offset, offset + page_size - 1)
            resp = await async_execute(query)
            data = list(getattr(resp, 'data', None) or [])
            total = getattr(resp, 'count', None)
            if type(total) is not int or total < len(data):
                raise HTTPException(status_code=503, detail="任务列表总数不可验证")

        return paginated_response(
            items=data, total=total, page=page, page_size=page_size,
            message="获取任务列表成功", trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except TaskDepartmentScopeInvalid as exc:
        logger.warning("任务科室范围无法解析: error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="任务科室范围暂不可筛选") from exc
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}")
        raise HTTPException(status_code=500, detail="查询任务列表失败，请稍后重试")


# ============================
# 任务统计
# ============================

@router.get("/stats")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_stats(
    request: Request,
    tab: Literal["all", "created", "received"] = Query(
        "all", description="标签: all=全部 | created=我创建 | received=我收到"
    ),
    scene: Optional[TaskSceneFilter] = Query(None, description="任务病历场景"),
    status: Optional[str] = Query(None, description="任务状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    department: Optional[str] = Query(None, description="任务保存范围中的精确科室名称"),
    created_start: Optional[str] = Query(None, description="创建日期起始（医院日历 YYYY-MM-DD）"),
    created_end: Optional[str] = Query(None, description="创建日期结束（医院日历 YYYY-MM-DD）"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取任务统计数据（各状态数量）
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        task_filter = parse_task_list_filter(
            department=department,
            created_start=created_start,
            created_end=created_end,
        )
    except TaskListFilterInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    status_counts = {}
    department_options: set[str] = set()
    try:
        candidates = await _read_all_task_filter_rows(
            sb,
            tab=tab,
            current_user=current_user,
            scene=scene,
            status=status,
            keyword=keyword,
            task_filter=task_filter,
            columns="status,department_filter,created_at,id",
            apply_department=False,
        )
        for row in candidates:
            try:
                saved_departments = parse_saved_departments(row.get("department_filter"))
            except TaskDepartmentScopeInvalid:
                if task_filter.department is not None:
                    raise
                continue
            department_options.update(saved_departments)
        rows = [
            row for row in candidates
            if task_matches_department(row.get("department_filter"), task_filter.department)
        ]
        for row in rows:
            row_status = row.get("status", "unknown")
            status_counts[row_status] = status_counts.get(row_status, 0) + 1
    except HTTPException:
        raise
    except TaskDepartmentScopeInvalid as exc:
        logger.warning("任务科室范围无法解析: error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="任务科室范围暂不可筛选") from exc
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
            "department_options": sorted(department_options),
        },
        message="获取任务统计成功",
        trace_id=get_trace_id(request),
    )


@router.get("/todo-stats")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
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
        rows = await _received_todo_rows(
            sb, current_user, scene, columns="id,status,deadline"
        )
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
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


@router.post("/{task_id}/records/{task_record_id}/start")
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
async def start_task_record(
    request: Request,
    task_id: str,
    task_record_id: str,
    body: Optional[dict] = Body(None),
    current_user: dict = Depends(get_current_user),
):
    """受领人开始任务中的单份病历，状态由服务端决定。"""
    if body is not None or await request.body():
        raise HTTPException(status_code=422, detail="此操作不接受请求体")
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            start_assigned_task_record,
            task_id=task_id,
            task_record_id=task_record_id,
            actor_id=actor_id,
        )
    except TaskStartNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskStartForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskStartConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("开始任务病历失败 task_id=%s task_record_id=%s", task_id, task_record_id)
        raise HTTPException(status_code=503, detail="数据库不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.records.start",
        resource="qc_task_record",
        outcome="success",
        details={
            "task_id": task_id,
            "task_record_id": task_record_id,
            "idempotent": data["idempotent"],
        },
        current_user=current_user,
    )
    return success_response(data=data, message="病历已开始", trace_id=get_trace_id(request))


@router.post("/{task_id}/records/{task_record_id}/complete")
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
async def complete_task_record(
    request: Request,
    task_id: str,
    task_record_id: str,
    body: TaskRecordCompleteRequest,
    current_user: dict = Depends(get_current_user),
):
    """质控员显式完成病历；执行完成和病历审核均不能代替此操作。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            complete_assigned_task_record,
            task_id=task_id,
            task_record_id=task_record_id,
            actor_id=actor_id,
            run_number=body.run_number,
            workspace_factory=_sichuan_workspace_service,
        )
    except TaskRecordCompletionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskRecordCompletionForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskRecordCompletionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskRecordCompletionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("完成任务病历失败 task_id=%s task_record_id=%s", task_id, task_record_id)
        raise HTTPException(status_code=503, detail="任务病历完成暂不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.records.complete",
        resource="qc_task_record",
        outcome="success",
        details={
            "task_id": task_id,
            "task_record_id": task_record_id,
            "run_number": body.run_number,
            "idempotent": data["idempotent"],
        },
        current_user=current_user,
    )
    return success_response(data=data, message="病历已完成", trace_id=get_trace_id(request))


@router.post("/{task_id}/records/{task_record_id}/manual-defects")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.CREATE)
async def create_task_record_manual_defect(
    request: Request,
    task_id: str,
    task_record_id: str,
    body: TaskManualDefectCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """仅受领人可为已核实的本次任务质控结果补录缺陷。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            create_task_manual_defect,
            task_id=task_id,
            task_record_id=task_record_id,
            actor_id=actor_id,
            defect_id=str(body.defect_id),
            run_number=body.run_number,
            rule_name=body.rule_name,
            description=body.description,
            severity=body.severity,
            suggestion=body.suggestion,
            evidence=body.evidence,
            workspace_factory=_sichuan_workspace_service,
        )
        result = TaskManualDefectResponse.model_validate(data).model_dump(mode="json")
    except TaskManualDefectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskManualDefectForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskManualDefectConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskManualDefectUnavailable as exc:
        raise HTTPException(status_code=503, detail="人工缺陷服务暂不可用，请稍后重试") from exc
    except Exception as exc:
        logger.exception("新增任务人工缺陷失败 task_id=%s task_record_id=%s", task_id, task_record_id)
        raise HTTPException(status_code=503, detail="人工缺陷服务暂不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.records.manual_defects.create",
        resource="qc_defect",
        outcome="success",
        details={
            "task_id": task_id,
            "task_record_id": task_record_id,
            "defect_id": result["id"],
            "run_number": body.run_number,
            "idempotent": result.get("idempotent", False),
        },
        current_user=current_user,
    )
    return success_response(data=result, message="人工缺陷已保存", trace_id=get_trace_id(request))


@router.get("/{task_id}/records/{task_record_id}/manual-defects")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_record_manual_defects(
    request: Request,
    task_id: str,
    task_record_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """只读取当前受领任务病历的人工缺陷。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        data = await run_in_threadpool(
            list_task_manual_defects,
            task_id=task_id,
            task_record_id=task_record_id,
            actor_id=actor_id,
            limit=limit,
            offset=offset,
        )
        result = {
            "items": [
                TaskManualDefectResponse.model_validate(item).model_dump(
                    mode="json", exclude={"idempotent"}
                )
                for item in data["items"]
            ],
            "total": data["total"],
            "limit": data["limit"],
            "offset": data["offset"],
        }
    except TaskManualDefectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskManualDefectForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskManualDefectConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskManualDefectUnavailable as exc:
        raise HTTPException(status_code=503, detail="人工缺陷服务暂不可用，请稍后重试") from exc
    except Exception as exc:
        logger.exception("读取任务人工缺陷失败 task_id=%s task_record_id=%s", task_id, task_record_id)
        raise HTTPException(status_code=503, detail="人工缺陷服务暂不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.records.manual_defects.read",
        resource="qc_defect",
        outcome="success",
        details={"task_id": task_id, "task_record_id": task_record_id},
        current_user=current_user,
    )
    return success_response(data=result, trace_id=get_trace_id(request))


# ============================
# 执行抽样
# ============================

@router.post("/{task_id}/sample")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
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

@router.post("/{task_id}/sync-records")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def sync_saved_task_records(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """显式同步已保存的三坐标病历，不启动质控。"""
    if await request.body():
        raise HTTPException(status_code=422, detail="此操作不接受请求体")
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            enqueue_task_record_sync,
            task_id=task_id,
            actor_id=actor_id,
            is_admin=has_any_role(current_user, [UserRole.ADMIN]),
        )
    except TaskRecordSyncNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskRecordSyncForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskRecordSyncConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskRecordSyncRateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except TaskRecordSyncUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("任务病历同步入队失败 task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="病历资料同步入队失败，请稍后重试") from exc
    audit_event(
        request,
        action="tasks.records.sync",
        resource="qc_task",
        outcome="success",
        details={
            "task_id": task_id,
            "job_id": result["job_id"],
            "reused": result["reused"],
        },
        current_user=current_user,
    )
    return success_response(data=result, message="病历资料同步已受理", trace_id=get_trace_id(request))


@router.get("/{task_id}/sync-records/latest")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def latest_saved_task_record_sync(
    request: Request, task_id: str, current_user: dict = Depends(get_current_user),
):
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            get_latest_task_record_sync_job, task_id=task_id, actor_id=actor_id,
            is_admin=has_any_role(current_user, [UserRole.ADMIN]),
        )
    except TaskRecordSyncNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskRecordSyncForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("读取任务病历同步作业失败 task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="同步作业状态暂不可用") from exc
    return success_response(data=result, trace_id=get_trace_id(request))


@router.get("/{task_id}/sync-records/{job_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_saved_task_record_sync(
    request: Request, task_id: str, job_id: str,
    current_user: dict = Depends(get_current_user),
):
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            get_task_record_sync_job, task_id=task_id, job_id=job_id, actor_id=actor_id,
            is_admin=has_any_role(current_user, [UserRole.ADMIN]),
        )
    except TaskRecordSyncNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskRecordSyncForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("读取任务病历同步作业失败 task_id=%s job_id=%s", task_id, job_id)
        raise HTTPException(status_code=503, detail="同步作业状态暂不可用") from exc
    return success_response(data=result, trace_id=get_trace_id(request))

@router.post("/batch-assign")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def batch_assign_tasks(
    request: Request,
    assign_data: TaskBatchAssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """逐项分配所选任务；每项独立提交，响应明确列出成功与失败。"""
    actor_id = _get_task_scope_user_id(current_user)
    assignees = [person.model_dump(exclude_none=True) for person in assign_data.assignees]
    items: list[dict[str, Any]] = []
    for target in assign_data.tasks:
        try:
            result = await run_in_threadpool(
                assign_task_records,
                task_id=target.task_id,
                actor_id=actor_id,
                assignees=assignees,
                method=target.method.value,
                fallback=target.fallback.value if target.fallback else None,
            )
            items.append({"task_id": target.task_id, "success": True, "result": result})
        except AssignmentNotFound as exc:
            items.append({
                "task_id": target.task_id, "success": False, "status": 404,
                "message": str(exc),
            })
        except AssignmentForbidden as exc:
            items.append({
                "task_id": target.task_id, "success": False, "status": 403,
                "message": str(exc),
            })
        except AssignmentConflict as exc:
            failure: dict[str, Any] = {
                "task_id": target.task_id,
                "success": False,
                "status": 409,
                "message": str(exc),
            }
            if exc.code:
                failure["code"] = exc.code
                failure["details"] = exc.details
            items.append(failure)
        except Exception:
            logger.error("批量任务分配单项失败 code=assignment_unavailable task_id=%s", target.task_id)
            items.append({
                "task_id": target.task_id, "success": False, "status": 503,
                "message": "任务分配暂不可用",
            })

    success_count = sum(1 for item in items if item["success"])
    failed_count = len(items) - success_count
    audit_event(
        request,
        action="tasks.assignment.batch_update",
        resource="/api/v1/tasks/batch-assign",
        outcome="success" if failed_count == 0 else ("failed" if success_count == 0 else "partial"),
        current_user=current_user,
        details={
            "task_ids": [target.task_id for target in assign_data.tasks],
            "assignees_count": len(assign_data.assignees),
            "success_count": success_count,
            "failed_count": failed_count,
        },
    )
    return success_response(
        data={
            "total": len(items),
            "success_count": success_count,
            "failed_count": failed_count,
            "items": items,
            "atomic": False,
        },
        message=(
            f"批量分配完成：成功 {success_count} 个，失败 {failed_count} 个"
            if failed_count
            else f"批量分配完成，共处理 {success_count} 个任务"
        ),
        trace_id=get_trace_id(request),
    )


@router.post("/{task_id}/assign")
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
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
            fallback=assign_data.fallback.value if assign_data.fallback else None,
        )
    except AssignmentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssignmentForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AssignmentConflict as exc:
        detail = (
            {"code": exc.code, "message": str(exc), **exc.details} if exc.code else str(exc)
        )
        raise HTTPException(status_code=409, detail=detail) from exc
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
async def start_task_qc_run(
    request: Request,
    task_id: str,
    scope: Literal["all", "assigned"] = Query("all"),
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
            run_scope=scope,
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_qc_runs(
    request: Request,
    task_id: str,
    scope: Literal["all", "assigned"] = Query("all"),
    current_user: dict = Depends(get_current_user),
):
    actor_id = _get_task_scope_user_id(current_user)
    try:
        runs = await run_in_threadpool(
            list_task_qc_runs, task_id=task_id, actor_id=actor_id, run_scope=scope,
        )
    except TaskQCRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskQCRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("查询任务质控运行历史失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务运行历史不可用，请稍后重试") from exc
    return success_response(data=runs, message="获取任务质控运行历史成功", trace_id=get_trace_id(request))


@router.get("/{task_id}/qc-runs/{run_number}/records/{task_record_id}")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_qc_run_record(
    request: Request,
    task_id: str,
    run_number: int,
    task_record_id: str,
    scope: Literal["all", "assigned"] = Query("all"),
    current_user: dict = Depends(get_current_user),
):
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            get_task_qc_run_record_result,
            task_id=task_id, run_number=run_number, task_record_id=task_record_id,
            actor_id=actor_id, workspace_factory=_sichuan_workspace_service,
            run_scope=scope,
        )
    except TaskQCRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskQCRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("查询任务病历质控结果失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务病历结果暂不可用，请稍后重试") from exc
    return success_response(data=result, message="获取任务病历质控结果成功", trace_id=get_trace_id(request))


@router.get("/{task_id}/progress")
@require_permission(ResourceType.QC_TASKS, PermissionAction.READ)
async def get_task_progress(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取任务执行进度"""
    actor_id = _get_task_scope_user_id(current_user)
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        task_resp = await async_execute(
            sb.table("qc_tasks").select("id,creator_id").eq("id", task_id).single()
        )
        task = getattr(task_resp, "data", None)
    except Exception as exc:
        logger.exception("查询任务进度前读取任务失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务数据源不可用，请稍后重试") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("creator_id") != actor_id and not has_any_role(
        current_user, [UserRole.ADMIN, UserRole.QC_MANAGER]
    ):
        raise HTTPException(status_code=403, detail="仅任务创建人或管理员可查看整任务进度")

    try:
        resp = await async_execute(
            sb.table('v_qc_task_progress').select('*').eq('task_id', task_id).single()
        )
        data = getattr(resp, 'data', None)
        if data:
            return success_response(data=data, message="获取进度成功", trace_id=get_trace_id(request))
    except Exception as exc:
        logger.exception("查询任务进度视图失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务进度服务不可用，请稍后重试") from exc

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 进度不存在")


# ============================
# 重新质控
# ============================

@router.post("/{task_id}/re-analyze")
@require_permission(ResourceType.QC_TASKS, PermissionAction.ANALYZE)
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
@require_permission(ResourceType.QC_TASKS, PermissionAction.DELETE)
async def delete_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """仅管理员和质控主管可删除无关联的草稿任务。"""
    try:
        await run_in_threadpool(delete_empty_draft_task, task_id=task_id)
    except TaskDeleteNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskDeleteConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("删除任务失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务删除服务不可用，请稍后重试") from exc

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
@require_permission(ResourceType.QC_TASKS, PermissionAction.UPDATE)
async def cancel_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """取消尚未开始且没有质控运行记录的任务。"""
    actor_id = _get_task_scope_user_id(current_user)
    try:
        result = await run_in_threadpool(
            cancel_task_transaction,
            task_id=task_id,
            actor_id=actor_id,
            is_manager=has_any_role(current_user, [UserRole.ADMIN, UserRole.QC_MANAGER]),
        )
    except TaskCancelNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TaskCancelForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TaskCancelConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("取消任务失败: task_id=%s", task_id)
        raise HTTPException(status_code=503, detail="任务取消服务不可用，请稍后重试") from exc

    audit_event(
        request,
        action="tasks.lifecycle.cancel",
        resource="/api/v1/tasks/{task_id}/cancel",
        outcome="success",
        current_user=current_user,
        details={
            "task_id": task_id,
            "status": TaskStatus.CANCELLED.value,
            "idempotent": result["idempotent"],
        },
    )

    return success_response(
        data=result,
        message="任务已取消",
        trace_id=get_trace_id(request),
    )
