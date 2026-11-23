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

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, text

from ..core.audit import audit_event
from ..core.permissions import (
    PermissionAction,
    ResourceType,
    UserRole,
    require_permission,
    require_role,
)
from ..core.response import get_trace_id, paginated_response, success_response
from ..core.security import get_current_user
from ..core.supabase_client import async_execute, get_supabase
from ..database import connection as db_connection
from ..schemas.tasks import (
    TaskAssignRequest,
    TaskCreateRequest,
    TaskRecordStatus,
    TaskStatus,
    TaskUpdateRequest,
)
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_MANAGER_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})
_TASK_ROLES = _MANAGER_ROLES | frozenset({"qc_staff"})
_READ_ROLES = _TASK_ROLES | frozenset({"doctor"})
_TERMINAL_TASK_STATUSES = frozenset({TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _generate_task_number() -> str:
    """生成任务编号: QC-YYYYMMDD-XXXX"""
    date_str = datetime.now().strftime("%Y%m%d")
    seq = random.randint(1000, 9999)
    return f"QC-{date_str}-{seq}"


def _user_table_ref(session) -> tuple[str, Set[str]]:
    owner_schema = resolve_user_owner_schema(session)
    inspector = sa_inspect(session.connection())
    if not inspector.has_table("sys_users", schema=owner_schema):
        raise HTTPException(status_code=503, detail="账号持久表不可用")
    cols = {col["name"] for col in inspector.get_columns("sys_users", schema=owner_schema)}
    table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
    return table_ref, cols


def _resolve_actor(
    current_user: Dict[str, Any],
    *,
    allowed_roles: Iterable[str],
    denied_detail: str = "权限不足",
) -> Dict[str, Any]:
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id:
        raise HTTPException(status_code=403, detail="缺少可信账号身份")

    session_factory = db_connection.SessionLocal
    if session_factory is None:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用")

    try:
        with session_factory() as session:
            table_ref, user_cols = _user_table_ref(session)
            has_institute = "institute_id" in user_cols
            select_cols = (
                "id, display_name, role, roles_json, is_active, department"
                + (", institute_id" if has_institute else "")
            )
            row = (
                session.execute(
                    text(f"SELECT {select_cols} FROM {table_ref} WHERE id = :uid"),
                    {"uid": actor_id},
                )
                .mappings()
                .one_or_none()
            )
    except HTTPException:
        raise
    except UserOwnerUnavailable:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None
    except Exception:
        logger.error("tasks_actor_lookup_failed", exc_info=True)
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None

    if row is None or not bool(row.get("is_active")):
        raise HTTPException(status_code=403, detail="账号不可用")

    roles = _effective_persistent_roles(row.get("role"), row.get("roles_json"))
    if not roles:
        raise HTTPException(status_code=403, detail="账号缺少可信持久角色")

    if not (roles & set(allowed_roles)):
        raise HTTPException(status_code=403, detail=denied_detail)

    is_global = bool(roles & _GLOBAL_ROLES)
    institute_id = row.get("institute_id") if has_institute else None
    if not is_global:
        if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
            raise HTTPException(status_code=403, detail="账号缺少可信机构范围")
    else:
        institute_id = None

    return {
        "id": str(row["id"]),
        "name": str(row.get("display_name") or current_user.get("display_name") or ""),
        "roles": roles,
        "is_global": is_global,
        "is_manager": bool(roles & _MANAGER_ROLES),
        "institute_id": institute_id,
    }


def _lookup_user_institutes(user_ids: Iterable[str]) -> Dict[str, Optional[str]]:
    ids = sorted({str(uid).strip() for uid in user_ids if str(uid or "").strip()})
    if not ids:
        return {}
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return {}
    try:
        with session_factory() as session:
            table_ref, user_cols = _user_table_ref(session)
            if "institute_id" not in user_cols:
                return {}
            placeholders = ", ".join(f":u{i}" for i in range(len(ids)))
            params = {f"u{i}": uid for i, uid in enumerate(ids)}
            rows = (
                session.execute(
                    text(f"SELECT id, institute_id FROM {table_ref} WHERE id IN ({placeholders})"),
                    params,
                )
                .mappings()
                .all()
            )
            return {
                str(r["id"]): (str(r["institute_id"]).strip() if r.get("institute_id") else None)
                for r in rows
            }
    except Exception:
        logger.warning("tasks_user_institute_lookup_failed", exc_info=True)
        return {}


def _extract_task_institutes(
    task: Dict[str, Any],
    *,
    creator_institute_map: Optional[Dict[str, Optional[str]]] = None,
    task_records: Optional[List[Dict[str, Any]]] = None,
) -> Set[str]:
    institutes: Set[str] = set()
    direct_inst = task.get("institute_id")
    if isinstance(direct_inst, str) and direct_inst.strip():
        institutes.add(direct_inst.strip())

    creator_id = str(task.get("creator_id") or "").strip()
    if creator_id:
        if creator_institute_map is None:
            creator_institute_map = _lookup_user_institutes([creator_id])
        c_inst = creator_institute_map.get(creator_id)
        if isinstance(c_inst, str) and c_inst.strip():
            institutes.add(c_inst.strip())

    raw_refs = task.get("record_refs")
    if isinstance(raw_refs, str) and raw_refs.strip():
        try:
            raw_refs = json.loads(raw_refs)
        except Exception:
            raw_refs = None
    if isinstance(raw_refs, list):
        for ref in raw_refs:
            if isinstance(ref, dict):
                r_inst = ref.get("institute_id")
                if isinstance(r_inst, str) and r_inst.strip():
                    institutes.add(r_inst.strip())

    for rec in task_records or []:
        r_inst = rec.get("institute_id")
        if isinstance(r_inst, str) and r_inst.strip():
            institutes.add(r_inst.strip())

    return institutes


def _task_belongs_to_actor_institute(
    actor: Dict[str, Any],
    task: Dict[str, Any],
    *,
    creator_institute_map: Optional[Dict[str, Optional[str]]] = None,
    task_records: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    if actor["is_global"]:
        return True
    institutes = _extract_task_institutes(
        task,
        creator_institute_map=creator_institute_map,
        task_records=task_records,
    )
    return bool(institutes) and institutes == {actor["institute_id"]}


async def _fetch_task_or_404(sb, task_id: str) -> Dict[str, Any]:
    try:
        resp = await async_execute(
            sb.table("qc_tasks").select("*").eq("id", task_id)
        )
        data = getattr(resp, "data", None)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("查询任务失败: %s", e)
        raise HTTPException(status_code=500, detail="查询任务失败")
    raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


async def _assert_task_access(
    sb,
    actor: Dict[str, Any],
    task: Dict[str, Any],
    *,
    require_write: bool,
    task_records: Optional[List[Dict[str, Any]]] = None,
) -> None:
    if actor["is_global"]:
        return

    if not _task_belongs_to_actor_institute(actor, task, task_records=task_records):
        raise HTTPException(status_code=403, detail="无权访问或操作其他机构的任务")

    if actor["is_manager"]:
        return

    creator_id = str(task.get("creator_id") or "").strip()
    if creator_id == actor["id"]:
        return

    if not require_write:
        if task_records is None:
            rec_resp = await async_execute(
                sb.table("qc_task_records").select("assignee_id").eq("task_id", task["id"])
            )
            task_records = list(getattr(rec_resp, "data", None) or [])
        if any(str(r.get("assignee_id") or "").strip() == actor["id"] for r in task_records):
            return

    raise HTTPException(status_code=403, detail="无权访问或操作他人创建的任务")


# ============================
# 创建任务
# ============================

@router.post("")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.CREATE)
async def create_task(
    request: Request,
    task_data: TaskCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建质控抽查任务"""
    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权创建质控任务")
    task_id = str(uuid.uuid4())
    task_number = _generate_task_number()
    now_iso = _utc_now_iso()

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
        "creator_id": actor["id"],
        "creator_name": actor["name"],
        "deadline": task_data.deadline,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(sb.table("qc_tasks").insert(task))
        task = (getattr(resp, "data", None) or [task])[0]
    except Exception as e:
        logger.error("创建任务失败: %s", e)
        raise HTTPException(status_code=500, detail="创建任务失败")

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
    """获取任务列表（修正 creator_id 取值，并强制按院区/创建人/受派归属隔离）"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看任务列表")
    user_id = actor["id"]

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        assigned_task_ids: Optional[Set[str]] = None
        if tab == "received" or (not actor["is_manager"]):
            assigned_resp = await async_execute(
                sb.table("qc_task_records")
                .select("task_id")
                .eq("assignee_id", user_id)
            )
            assigned_task_ids = {
                str(r.get("task_id"))
                for r in (getattr(assigned_resp, "data", None) or [])
                if r.get("task_id")
            }
            if tab == "received" and not assigned_task_ids:
                return paginated_response(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    message="暂无收到的任务",
                    trace_id=get_trace_id(request),
                )

        query = sb.table("qc_tasks").select("*")
        if tab == "created":
            query = query.eq("creator_id", user_id)
        elif tab == "received" and assigned_task_ids is not None:
            query = query.in_("id", sorted(assigned_task_ids))
        if status:
            query = query.eq("status", status)
        query = query.order("created_at", desc=True)

        resp = await async_execute(query)
        rows = list(getattr(resp, "data", None) or [])

        # 关键词过滤在内存安全匹配，避免 .or_() 拼接触发 SQL 注入
        if keyword:
            kw_lower = keyword.lower()
            rows = [
                r
                for r in rows
                if kw_lower in str(r.get("task_name") or "").lower()
                or kw_lower in str(r.get("task_number") or "").lower()
            ]

        if not actor["is_global"]:
            creator_map = _lookup_user_institutes(
                str(r.get("creator_id") or "") for r in rows
            )
            scoped_rows = []
            for r in rows:
                if not _task_belongs_to_actor_institute(
                    actor, r, creator_institute_map=creator_map
                ):
                    continue
                if not actor["is_manager"]:
                    is_creator = str(r.get("creator_id") or "").strip() == user_id
                    is_assignee = str(r.get("id") or "") in (assigned_task_ids or set())
                    if not (is_creator or is_assignee):
                        continue
                scoped_rows.append(r)
            rows = scoped_rows

        total = len(rows)
        offset = (page - 1) * page_size
        page_items = rows[offset : offset + page_size]

        return paginated_response(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            message="获取任务列表成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("查询任务列表失败: %s", e)
        raise HTTPException(status_code=500, detail="查询任务列表失败")


# ============================
# 任务统计
# ============================

@router.get("/stats")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_task_stats(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """获取任务统计数据（各状态数量，按院区/归属隔离）"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看任务统计")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    status_counts: Dict[str, int] = {}
    try:
        assigned_task_ids: Set[str] = set()
        if not actor["is_manager"]:
            assigned_resp = await async_execute(
                sb.table("qc_task_records")
                .select("task_id")
                .eq("assignee_id", actor["id"])
            )
            assigned_task_ids = {
                str(r.get("task_id"))
                for r in (getattr(assigned_resp, "data", None) or [])
                if r.get("task_id")
            }

        resp = await async_execute(sb.table("qc_tasks").select("*"))
        rows = list(getattr(resp, "data", None) or [])
        if not actor["is_global"]:
            creator_map = _lookup_user_institutes(
                str(r.get("creator_id") or "") for r in rows
            )
            filtered = []
            for r in rows:
                if not _task_belongs_to_actor_institute(
                    actor, r, creator_institute_map=creator_map
                ):
                    continue
                if not actor["is_manager"]:
                    if (
                        str(r.get("creator_id") or "").strip() != actor["id"]
                        and str(r.get("id") or "") not in assigned_task_ids
                    ):
                        continue
                filtered.append(r)
            rows = filtered

        for r in rows:
            st = r.get("status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取任务统计失败: %s", e)
        raise HTTPException(status_code=500, detail="获取任务统计失败")

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
    """获取任务详情 + 包含的病历列表"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看任务详情")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)

    try:
        resp = await async_execute(
            sb.table("qc_task_records")
            .select("*")
            .eq("task_id", task_id)
            .order("created_at")
        )
        records = list(getattr(resp, "data", None) or [])
    except Exception as e:
        logger.error("查询任务记录失败: %s", e)
        raise HTTPException(status_code=500, detail="查询任务记录失败")

    await _assert_task_access(
        sb, actor, task, require_write=False, task_records=records
    )

    task_out = dict(task)
    task_out["records"] = records

    return success_response(
        data=task_out,
        message="获取任务详情成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 更新任务
# ============================

@router.put("/{task_id}")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def update_task(
    request: Request,
    task_id: str,
    update_data: TaskUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新任务基本信息"""
    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权更新任务")
    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    for key in ["assign_method", "status"]:
        if key in update_fields and hasattr(update_fields[key], "value"):
            update_fields[key] = update_fields[key].value

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    current_status = str(task.get("status") or "")
    if current_status in _TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=409, detail="已完成或已取消的任务不可修改")

    update_fields["updated_at"] = _utc_now_iso()

    try:
        resp = await async_execute(
            sb.table("qc_tasks")
            .update(update_fields)
            .eq("id", task_id)
            .eq("status", current_status)
        )
        rows = list(getattr(resp, "data", None) or [])
        if not rows:
            raise HTTPException(status_code=409, detail="任务状态已变更，请刷新后重试")
        return success_response(
            data=rows[0],
            message="任务更新成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新任务失败: %s", e)
        raise HTTPException(status_code=500, detail="更新任务失败")


# ============================
# 执行抽样
# ============================

@router.post("/{task_id}/sample")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def execute_sampling(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """执行抽样 — 根据任务配置从病历库中抽取病历（含幂等与状态守卫）"""
    from ..services.task_sampling_service import TaskSamplingService

    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权执行任务抽样")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    current_status = str(task.get("status") or "")
    if current_status != TaskStatus.DRAFT.value:
        raise HTTPException(
            status_code=409,
            detail=f"当前任务状态（{current_status}）不允许重复抽样，仅草稿态可执行抽样",
        )

    existing_resp = await async_execute(
        sb.table("qc_task_records").select("id").eq("task_id", task_id)
    )
    if getattr(existing_resp, "data", None):
        raise HTTPException(status_code=409, detail="任务已存在抽样病历，禁止重复抽样")

    sampling_service = TaskSamplingService()
    sampled_records = await sampling_service.sample(task)
    if not actor["is_global"]:
        sampled_records = [
            rec
            for rec in sampled_records
            if not rec.get("institute_id")
            or str(rec.get("institute_id")).strip() == actor["institute_id"]
        ]

    now_iso = _utc_now_iso()
    seen_record_ids: Set[str] = set()
    task_records = []
    for record in sampled_records:
        rid = str(record.get("id") or record.get("record_id") or "").strip()
        if not rid or rid in seen_record_ids:
            continue
        seen_record_ids.add(rid)
        tr = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "record_id": rid,
            "assignee_id": None,
            "assignee_name": None,
            "status": TaskRecordStatus.PENDING.value,
            "defect_count": 0,
            "created_at": now_iso,
        }
        task_records.append(tr)

    if task_records:
        try:
            await async_execute(sb.table("qc_task_records").insert(task_records))
        except Exception as e:
            logger.error("保存任务病历关联失败: %s", e)
            raise HTTPException(status_code=500, detail="保存抽样结果失败")

    update_data = {
        "status": TaskStatus.SAMPLING.value,
        "total_records": len(task_records),
        "updated_at": _utc_now_iso(),
    }
    try:
        resp = await async_execute(
            sb.table("qc_tasks")
            .update(update_data)
            .eq("id", task_id)
            .eq("status", TaskStatus.DRAFT.value)
        )
        if not getattr(resp, "data", None):
            raise HTTPException(status_code=409, detail="任务状态已变更，抽样状态更新冲突")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("更新任务抽样状态失败: %s", e)

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
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def assign_task(
    request: Request,
    task_id: str,
    assign_data: TaskAssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """分配任务 — 将抽样好的病历分配给质控员"""
    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权分配任务")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    current_status = str(task.get("status") or "")
    if current_status in _TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=409, detail="已完成或已取消的任务不可分配")

    assignees = assign_data.assignees
    if not assignees:
        raise HTTPException(status_code=400, detail="请提供分配人员列表")

    if not actor["is_global"]:
        assignee_ids = [str(a.get("user_id") or "").strip() for a in assignees if a.get("user_id")]
        assignee_insts = _lookup_user_institutes(assignee_ids)
        for uid, u_inst in assignee_insts.items():
            if u_inst != actor["institute_id"]:
                raise HTTPException(status_code=403, detail=f"不能将任务分配给其他机构的人员: {uid}")

    try:
        resp = await async_execute(
            sb.table("qc_task_records")
            .select("*")
            .eq("task_id", task_id)
            .eq("status", "pending")
        )
        records = list(getattr(resp, "data", None) or [])
    except Exception as e:
        logger.error("查询待分配病历失败: %s", e)
        raise HTTPException(status_code=500, detail="查询待分配病历失败")

    if not records:
        raise HTTPException(status_code=400, detail="没有待分配的病历，请先执行抽样")

    batch_size = len(records) // len(assignees)
    remainder = len(records) % len(assignees)

    idx = 0
    updates = []
    for i, assignee in enumerate(assignees):
        count = batch_size + (1 if i < remainder else 0)
        for _ in range(count):
            if idx < len(records):
                records[idx]["assignee_id"] = assignee.get("user_id", "")
                records[idx]["assignee_name"] = assignee.get("user_name", "")
                updates.append(
                    {
                        "id": records[idx]["id"],
                        "assignee_id": assignee.get("user_id", ""),
                        "assignee_name": assignee.get("user_name", ""),
                    }
                )
                idx += 1

    fail_count = 0
    for update in updates:
        try:
            await async_execute(
                sb.table("qc_task_records")
                .update(
                    {
                        "assignee_id": update["assignee_id"],
                        "assignee_name": update["assignee_name"],
                    }
                )
                .eq("id", update["id"])
            )
        except Exception as e:
            fail_count += 1
            logger.warning("分配记录 %s 更新失败: %s", update["id"], e)
    if fail_count:
        logger.error("分配任务时 %s/%s 条记录更新失败", fail_count, len(updates))

    status_update = {
        "status": TaskStatus.ASSIGNED.value,
        "updated_at": _utc_now_iso(),
    }
    try:
        await async_execute(
            sb.table("qc_tasks")
            .update(status_update)
            .eq("id", task_id)
            .eq("status", current_status)
        )
    except Exception as e:
        logger.warning("更新任务分配状态失败（非阻塞）: %s", e)

    assignment_summary = {}
    for assignee in assignees:
        name = assignee.get("user_name", "")
        count = sum(1 for u in updates if u["assignee_id"] == assignee.get("user_id"))
        assignment_summary[name] = count

    audit_event(
        request,
        action="tasks.assignment.update",
        resource="/api/v1/tasks/{task_id}/assign",
        outcome="success" if fail_count == 0 else "partial",
        current_user=current_user,
        details={
            "task_id": task_id,
            "pending_records": len(records),
            "total_assigned": len(updates),
            "assignees_count": len(assignees),
            "failed_updates": fail_count,
            "assignment_summary": assignment_summary,
        },
    )

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
    """获取任务执行进度（含院区/归属校验）"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看任务进度")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=False)

    try:
        resp = await async_execute(
            sb.table("v_qc_task_progress").select("*").eq("task_id", task_id).single()
        )
        data = getattr(resp, "data", None)
        if data:
            return success_response(
                data=data,
                message="获取进度成功",
                trace_id=get_trace_id(request),
            )
    except Exception as e:
        logger.warning("查询任务进度视图失败: %s", e)

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
    """对任务内所有病历重新执行质控分析（先置 in_progress，执行完毕后按实际结果收口为 completed/进度）"""
    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权重新质控任务")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    current_status = str(task.get("status") or "")
    if current_status == TaskStatus.CANCELLED.value:
        raise HTTPException(status_code=409, detail="已取消的任务不可重新质控")

    try:
        resp = await async_execute(
            sb.table("qc_task_records").select("id, record_id").eq("task_id", task_id)
        )
        records = list(getattr(resp, "data", None) or [])
    except Exception as e:
        logger.error("查询任务病历失败: %s", e)
        raise HTTPException(status_code=500, detail="查询任务病历失败")

    record_entries = [r for r in records if r.get("record_id")]
    if not record_entries:
        raise HTTPException(status_code=400, detail="任务中没有病历")

    # 1. 开始前先将任务置为 in_progress（带 CAS 防并发取消覆盖）
    start_update = {
        "status": TaskStatus.IN_PROGRESS.value,
        "completed_records": 0,
        "progress": 0.0,
        "updated_at": _utc_now_iso(),
    }
    start_resp = await async_execute(
        sb.table("qc_tasks")
        .update(start_update)
        .eq("id", task_id)
        .eq("status", current_status)
    )
    if not getattr(start_resp, "data", None):
        raise HTTPException(status_code=409, detail="任务状态已变更，无法启动重新质控")

    from ..services.qc_service import QCService

    qc_service = QCService()
    batch = record_entries[:50]
    started = []
    succeeded_count = 0
    failed_count = 0

    for rec in batch:
        rid = str(rec["record_id"])
        try:
            result = await qc_service.evaluate({"record_id": rid})
            succeeded_count += 1
            started.append({"record_id": rid, "status": "completed"})
            if rec.get("id"):
                try:
                    rec_update = {
                        "status": TaskRecordStatus.COMPLETED.value,
                        "score": result.get("overall_score") if isinstance(result, dict) else None,
                        "defect_count": len(result.get("issues") or []) if isinstance(result, dict) else 0,
                        "completed_at": _utc_now_iso(),
                    }
                    await async_execute(
                        sb.table("qc_task_records").update(rec_update).eq("id", rec["id"])
                    )
                except Exception as rec_exc:
                    logger.warning("更新任务病历重分析结果失败（非阻塞）: %s", rec_exc)
        except Exception as e:
            failed_count += 1
            started.append({"record_id": rid, "status": "failed", "error": str(e)})

    total_records = len(record_entries)
    progress = round(succeeded_count * 100.0 / total_records, 1) if total_records else 0.0
    final_status = (
        TaskStatus.COMPLETED.value
        if failed_count == 0 and succeeded_count == total_records
        else TaskStatus.IN_PROGRESS.value
    )

    # 2. 执行完毕后按实际完成度收口，不再把已跑完任务覆写回 in_progress/0
    finish_update = {
        "status": final_status,
        "completed_records": succeeded_count,
        "progress": progress,
        "updated_at": _utc_now_iso(),
    }
    try:
        await async_execute(
            sb.table("qc_tasks")
            .update(finish_update)
            .eq("id", task_id)
            .eq("status", TaskStatus.IN_PROGRESS.value)
        )
    except Exception as e:
        logger.warning("更新任务重新质控终态失败: %s", e)

    return success_response(
        data={
            "task_id": task_id,
            "status": final_status,
            "total": total_records,
            "started": len(started),
            "completed_records": succeeded_count,
            "failed": failed_count,
            "progress": progress,
            "results": started,
        },
        message=f"重新质控完成：成功 {succeeded_count}/{total_records} 条病历",
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
    """删除任务（仅限管理员和本院区质控主管）"""
    actor = _resolve_actor(
        current_user,
        allowed_roles=_MANAGER_ROLES,
        denied_detail="仅质控管理员或系统管理员可删除任务",
    )
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    try:
        await async_execute(sb.table("qc_tasks").delete().eq("id", task_id))
    except Exception as e:
        logger.error("删除任务失败: %s", e)
        raise HTTPException(status_code=500, detail="删除任务失败")

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
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def cancel_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """取消任务（带院区/归属校验与终态 CAS 保护）"""
    actor = _resolve_actor(current_user, allowed_roles=_TASK_ROLES, denied_detail="无权取消任务")
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    task = await _fetch_task_or_404(sb, task_id)
    await _assert_task_access(sb, actor, task, require_write=True)

    current_status = str(task.get("status") or "")
    if current_status in _TERMINAL_TASK_STATUSES:
        raise HTTPException(status_code=409, detail="已完成或已取消的任务不可取消")

    update_data = {
        "status": TaskStatus.CANCELLED.value,
        "updated_at": _utc_now_iso(),
    }

    try:
        resp = await async_execute(
            sb.table("qc_tasks")
            .update(update_data)
            .eq("id", task_id)
            .eq("status", current_status)
        )
        if not getattr(resp, "data", None):
            raise HTTPException(status_code=409, detail="任务状态已变更，无法取消")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("取消任务失败: %s", e)
        raise HTTPException(status_code=500, detail="取消任务失败")

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
