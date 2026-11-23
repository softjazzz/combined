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

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, text

from ..core.response import (
    StatusCode,
    get_trace_id,
    paginated_response,
    success_response,
)
from ..core.security import get_current_user
from ..core.supabase_client import get_supabase  # noqa: F401
from ..database import connection as db_connection
from ..schemas.remediation import (
    HistoryAction,
    RemediationClose,
    RemediationReview,
    RemediationStatus,
    RemediationSubmit,
    RemediationTaskCreate,
    RemediationTaskUpdate,
)
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    configured_search_path,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/remediation", tags=["remediation"])
logger = logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_REVIEW_CLOSE_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})
_MANAGE_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_ALL_ALLOWED_ROLES = _MANAGE_ROLES | frozenset({"doctor"})
_TERMINAL_REMEDIATION_STATUSES = frozenset(
    {
        RemediationStatus.APPROVED.value,
        RemediationStatus.CLOSED.value,
    }
)
_SUBMITTABLE_STATUSES = frozenset(
    {
        RemediationStatus.PENDING.value,
        RemediationStatus.IN_PROGRESS.value,
        RemediationStatus.REJECTED.value,
        RemediationStatus.OVERDUE.value,
    }
)
_UPDATABLE_STATUSES = frozenset(
    {
        RemediationStatus.PENDING.value,
        RemediationStatus.REJECTED.value,
    }
)
_OVERDUE_ACTIVE_STATUSES = (
    RemediationStatus.PENDING.value,
    RemediationStatus.IN_PROGRESS.value,
    RemediationStatus.SUBMITTED.value,
    RemediationStatus.REJECTED.value,
    RemediationStatus.OVERDUE.value,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_utc_naive(value: Any) -> Optional[datetime]:
    """兼容 PostgreSQL datetime（naive/aware）与 ISO 字符串（含 Z 或偏移量），统一转为 UTC naive datetime。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    raise TypeError(f"Unsupported datetime value type: {type(value).__name__}")


def _get_session_factory():
    factory = db_connection.SessionLocal
    if factory is None:
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="数据库连接失败",
        )
    return factory


def _table_columns(session, table_name: str) -> Set[str]:
    bind = session.get_bind()
    inspector = sa_inspect(bind)
    if bind.dialect.name != "postgresql":
        if not inspector.has_table(table_name):
            return set()
        return {col["name"] for col in inspector.get_columns(table_name)}

    schemas = list(dict.fromkeys([*configured_search_path(), "qc", "public", "sys", "cdm"]))
    for schema in schemas:
        if inspector.has_table(table_name, schema=schema):
            return {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
    if inspector.has_table(table_name):
        return {col["name"] for col in inspector.get_columns(table_name)}
    return set()


def _user_table_ref(session) -> tuple[str, Set[str]]:
    owner_schema = resolve_user_owner_schema(session)
    inspector = sa_inspect(session.connection())
    if not inspector.has_table("sys_users", schema=owner_schema):
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="账号持久表不可用",
        )
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
        raise HTTPException(status_code=StatusCode.FORBIDDEN, detail="缺少可信账号身份")

    session_factory = _get_session_factory()
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
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="账号机构权限来源暂不可用",
        ) from None
    except Exception:
        logger.error("remediation_actor_lookup_failed", exc_info=True)
        raise HTTPException(
            status_code=StatusCode.SERVICE_UNAVAILABLE,
            detail="账号机构权限来源暂不可用",
        ) from None

    if row is None or not bool(row.get("is_active")):
        raise HTTPException(status_code=StatusCode.FORBIDDEN, detail="账号不可用")

    roles = _effective_persistent_roles(row.get("role"), row.get("roles_json"))
    if not roles:
        raise HTTPException(status_code=StatusCode.FORBIDDEN, detail="账号缺少可信持久角色")

    if not (roles & set(allowed_roles)):
        raise HTTPException(status_code=StatusCode.FORBIDDEN, detail=denied_detail)

    is_global = bool(roles & _GLOBAL_ROLES)
    institute_id = row.get("institute_id") if has_institute else None
    if not is_global:
        if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
            raise HTTPException(status_code=StatusCode.FORBIDDEN, detail="账号缺少可信机构范围")
    else:
        institute_id = None

    return {
        "id": str(row["id"]),
        "name": str(row.get("display_name") or current_user.get("display_name") or current_user.get("name") or ""),
        "department": row.get("department"),
        "roles": roles,
        "is_global": is_global,
        "is_manager": bool(roles & _MANAGE_ROLES),
        "institute_id": institute_id,
    }


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _resolve_task_institute(session, task_row: Dict[str, Any]) -> Optional[str]:
    institutes: Set[str] = set()

    qc_result_id = str(task_row.get("qc_result_id") or "").strip()
    if qc_result_id:
        qc_cols = _table_columns(session, "qc_results")
        if "institute_id" in qc_cols:
            qc_inst = session.execute(
                text("SELECT institute_id FROM qc_results WHERE id = :qid"),
                {"qid": qc_result_id},
            ).scalar_one_or_none()
            if isinstance(qc_inst, str) and qc_inst.strip():
                institutes.add(qc_inst.strip())

    assignee_id = str(task_row.get("assignee_id") or "").strip()
    if assignee_id:
        try:
            user_ref, user_cols = _user_table_ref(session)
            if "institute_id" in user_cols:
                u_inst = session.execute(
                    text(f"SELECT institute_id FROM {user_ref} WHERE id = :uid"),
                    {"uid": assignee_id},
                ).scalar_one_or_none()
                if isinstance(u_inst, str) and u_inst.strip():
                    institutes.add(u_inst.strip())
        except Exception:
            pass

    if len(institutes) == 1:
        return next(iter(institutes))
    return None


def _assert_task_institute_access(session, actor: Dict[str, Any], task_row: Dict[str, Any]) -> None:
    if actor["is_global"]:
        return
    task_inst = _resolve_task_institute(session, task_row)
    if not task_inst or task_inst != actor["institute_id"]:
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="无权访问或操作其他机构的整改任务",
        )


def _assert_assignee_in_actor_institute(session, actor: Dict[str, Any], assignee_id: str) -> None:
    if actor["is_global"]:
        return
    user_ref, user_cols = _user_table_ref(session)
    if "institute_id" not in user_cols:
        return
    u_inst = session.execute(
        text(f"SELECT institute_id FROM {user_ref} WHERE id = :uid"),
        {"uid": assignee_id},
    ).scalar_one_or_none()
    if u_inst is not None and (not isinstance(u_inst, str) or u_inst.strip() != actor["institute_id"]):
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="不能将整改任务指派给其他机构的人员",
        )


def _insert_row(session, table_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cols = _table_columns(session, table_name)
    insert_data: Dict[str, Any] = {}
    for k, v in payload.items():
        if k in cols:
            if isinstance(v, (dict, list)):
                insert_data[k] = json.dumps(v, ensure_ascii=False, default=str)
            else:
                insert_data[k] = v
    col_sql = ", ".join(f'"{k}"' for k in insert_data)
    val_sql = ", ".join(f":{k}" for k in insert_data)
    session.execute(
        text(f'INSERT INTO "{table_name}" ({col_sql}) VALUES ({val_sql})'),
        insert_data,
    )
    row = (
        session.execute(
            text(f'SELECT * FROM "{table_name}" WHERE id = :id'),
            {"id": payload["id"]},
        )
        .mappings()
        .one()
    )
    return _serialize_row(dict(row))


# ============================
# 整改任务管理
# ============================

@router.post("", response_model=dict)
async def create_remediation_task(
    request: Request,
    task: RemediationTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    """创建整改任务（仅质控人员/管理员，带 UUID 主键与院区校验）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_MANAGE_ROLES,
        denied_detail="仅质控人员或管理员可创建整改任务",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                qc_cols = _table_columns(session, "qc_results")
                qc_row = (
                    session.execute(
                        text("SELECT * FROM qc_results WHERE id = :qid"),
                        {"qid": str(task.qc_result_id)},
                    )
                    .mappings()
                    .one_or_none()
                )
                if qc_row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"质控结果不存在: {task.qc_result_id}",
                    )
                if not actor["is_global"]:
                    if "institute_id" not in qc_cols:
                        raise HTTPException(
                            status_code=StatusCode.FORBIDDEN,
                            detail="质控结果缺少机构归属信息",
                        )
                    qc_inst = qc_row.get("institute_id")
                    if not isinstance(qc_inst, str) or qc_inst.strip() != actor["institute_id"]:
                        raise HTTPException(
                            status_code=StatusCode.FORBIDDEN,
                            detail="无权为其他机构质控结果创建整改任务",
                        )

                mr_cols = _table_columns(session, "medical_records")
                if mr_cols:
                    mr_row = (
                        session.execute(
                            text("SELECT * FROM medical_records WHERE id = :rid"),
                            {"rid": str(task.record_id)},
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if mr_row is None:
                        raise HTTPException(
                            status_code=StatusCode.NOT_FOUND,
                            detail=f"病历不存在: {task.record_id}",
                        )
                    if not actor["is_global"] and "institute_id" in mr_cols:
                        mr_inst = mr_row.get("institute_id")
                        if isinstance(mr_inst, str) and mr_inst.strip() and mr_inst.strip() != actor["institute_id"]:
                            raise HTTPException(
                                status_code=StatusCode.FORBIDDEN,
                                detail="无权为其他机构病历创建整改任务",
                            )

                _assert_assignee_in_actor_institute(session, actor, str(task.assignee_id))

                now = _utc_now()
                task_id = str(uuid.uuid4())
                task_number = f"RM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                deadline_val = _to_utc_naive(task.deadline) if task.deadline else None
                task_data = {
                    "id": task_id,
                    "task_number": task_number,
                    "qc_result_id": str(task.qc_result_id),
                    "record_id": str(task.record_id),
                    "defect_type": task.defect_type,
                    "defect_description": task.defect_description,
                    "defect_location": task.defect_location,
                    "severity": task.severity.value,
                    "remediation_requirement": task.remediation_requirement,
                    "deadline": deadline_val,
                    "assignee_id": str(task.assignee_id),
                    "assignee_name": task.assignee_name,
                    "assignee_department": task.assignee_department,
                    "notes": task.notes,
                    "status": RemediationStatus.PENDING.value,
                    "created_at": now,
                    "updated_at": now,
                }
                created = _insert_row(session, "qc_remediation_tasks", task_data)

                history_data = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "action": HistoryAction.CREATE.value,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"] or current_user.get("email", "Unknown"),
                    "old_status": None,
                    "new_status": RemediationStatus.PENDING.value,
                    "comment": "创建整改任务",
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_remediation_history", history_data)

        logger.info(
            "Remediation task created: %s",
            created["id"],
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=created,
            message="整改任务创建成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create remediation task: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="创建整改任务失败",
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """获取整改任务列表（按角色与院区隔离）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看整改任务列表",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            where_clauses: List[str] = []
            params: Dict[str, Any] = {}

            if not actor["is_manager"]:
                where_clauses.append("assignee_id = :actor_id")
                params["actor_id"] = actor["id"]
            elif assignee_id:
                where_clauses.append("assignee_id = :assignee_id")
                params["assignee_id"] = assignee_id

            if status:
                where_clauses.append("status = :status")
                params["status"] = status
            if severity:
                where_clauses.append("severity = :severity")
                params["severity"] = severity
            if defect_type:
                where_clauses.append("LOWER(COALESCE(defect_type, '')) LIKE LOWER(:defect_type)")
                params["defect_type"] = f"%{defect_type}%"
            if is_overdue:
                where_clauses.append(
                    "deadline IS NOT NULL AND deadline < :now_dt "
                    "AND status IN ('pending', 'in_progress', 'submitted', 'rejected', 'overdue')"
                )
                params["now_dt"] = _utc_now()
            if start_date:
                where_clauses.append("created_at >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where_clauses.append("created_at <= :end_date")
                params["end_date"] = end_date

            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            sql = f"SELECT * FROM qc_remediation_tasks{where_sql} ORDER BY created_at DESC"
            rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]

            if not actor["is_global"]:
                rows = [
                    r for r in rows
                    if _resolve_task_institute(session, r) == actor["institute_id"]
                ]

            total = len(rows)
            offset = (page - 1) * page_size
            items = [_serialize_row(r) for r in rows[offset : offset + page_size]]

        return paginated_response(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to list remediation tasks: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取整改任务列表失败",
        )


# ============================
# 统计和报表（置于 /{task_id} 之前避免路由遮蔽）
# ============================

@router.get("/statistics/summary", response_model=dict)
async def get_remediation_statistics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """获取整改统计（按角色、院区与日期范围过滤）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看整改统计",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            where_clauses: List[str] = []
            params: Dict[str, Any] = {}
            if not actor["is_manager"]:
                where_clauses.append("assignee_id = :actor_id")
                params["actor_id"] = actor["id"]
            if start_date:
                where_clauses.append("created_at >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where_clauses.append("created_at <= :end_date")
                params["end_date"] = end_date

            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            rows = [
                dict(r)
                for r in session.execute(
                    text(f"SELECT * FROM qc_remediation_tasks{where_sql}"),
                    params,
                )
                .mappings()
                .all()
            ]
            if not actor["is_global"]:
                rows = [
                    r for r in rows
                    if _resolve_task_institute(session, r) == actor["institute_id"]
                ]

        stats: Dict[str, Any] = {
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
            "by_defect_type": {},
        }

        total_completion_seconds = 0.0
        completion_count = 0

        for row in rows:
            st = row.get("status")
            severity = row.get("severity")
            defect_type = row.get("defect_type")
            stats["total"] += 1
            if st in stats:
                stats[st] += 1
            if severity:
                stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
            if defect_type:
                stats["by_defect_type"][defect_type] = stats["by_defect_type"].get(defect_type, 0) + 1

            if st == RemediationStatus.APPROVED.value and row.get("created_at") and row.get("reviewed_at"):
                try:
                    c_dt = _to_utc_naive(row["created_at"])
                    r_dt = _to_utc_naive(row["reviewed_at"])
                    if c_dt and r_dt and r_dt >= c_dt:
                        total_completion_seconds += (r_dt - c_dt).total_seconds()
                        completion_count += 1
                except Exception:
                    pass

        if completion_count > 0:
            stats["avg_completion_time_hours"] = round(
                total_completion_seconds / completion_count / 3600.0, 2
            )

        return success_response(
            data=stats,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get remediation statistics: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取统计数据失败",
        )


@router.get("/statistics/workload", response_model=dict)
async def get_assignee_workload(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """获取责任人工作负载（按角色与院区隔离）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看工作负载统计",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            where_clauses = ["assignee_id IS NOT NULL", "assignee_id <> ''"]
            params: Dict[str, Any] = {}
            if not actor["is_manager"]:
                where_clauses.append("assignee_id = :actor_id")
                params["actor_id"] = actor["id"]
            rows = [
                dict(r)
                for r in session.execute(
                    text(f"SELECT * FROM qc_remediation_tasks WHERE {' AND '.join(where_clauses)}"),
                    params,
                )
                .mappings()
                .all()
            ]
            if not actor["is_global"]:
                rows = [
                    r for r in rows
                    if _resolve_task_institute(session, r) == actor["institute_id"]
                ]

        buckets: Dict[tuple, Dict[str, Any]] = {}
        for row in rows:
            key = (
                row.get("assignee_id") or "",
                row.get("assignee_name") or "",
                row.get("assignee_department") or "",
            )
            entry = buckets.setdefault(
                key,
                {
                    "assignee_id": key[0],
                    "assignee_name": key[1],
                    "assignee_department": key[2],
                    "total_tasks": 0,
                    "pending_tasks": 0,
                    "in_progress_tasks": 0,
                    "overdue_tasks": 0,
                    "avg_completion_days": 0.0,
                },
            )
            entry["total_tasks"] += 1
            st = row.get("status")
            if st == "pending":
                entry["pending_tasks"] += 1
            elif st == "in_progress":
                entry["in_progress_tasks"] += 1
            elif st == "overdue":
                entry["overdue_tasks"] += 1

        return success_response(
            data=list(buckets.values()),
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get assignee workload: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取工作负载失败",
        )


@router.get("/statistics/overdue", response_model=dict)
async def get_overdue_tasks(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """获取逾期任务告警（兼容 PG datetime 与 aware/naive ISO 字符串，按角色与院区隔离）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看逾期任务告警",
    )
    session_factory = _get_session_factory()

    try:
        now_utc = _utc_now()
        with session_factory() as session:
            where_clauses = [
                "deadline IS NOT NULL",
                "status IN ('pending', 'in_progress', 'submitted', 'rejected', 'overdue')",
            ]
            params: Dict[str, Any] = {}
            if not actor["is_manager"]:
                where_clauses.append("assignee_id = :actor_id")
                params["actor_id"] = actor["id"]
            rows = [
                dict(r)
                for r in session.execute(
                    text(f"SELECT * FROM qc_remediation_tasks WHERE {' AND '.join(where_clauses)}"),
                    params,
                )
                .mappings()
                .all()
            ]
            if not actor["is_global"]:
                rows = [
                    r for r in rows
                    if _resolve_task_institute(session, r) == actor["institute_id"]
                ]

        overdue_tasks = []
        for task in rows:
            raw_deadline = task.get("deadline")
            if not raw_deadline:
                continue
            deadline_dt = _to_utc_naive(raw_deadline)
            if deadline_dt is None or deadline_dt >= now_utc:
                continue
            overdue_days = (now_utc - deadline_dt).days
            overdue_tasks.append(
                {
                    "task_id": task["id"],
                    "task_number": task.get("task_number"),
                    "assignee_name": task.get("assignee_name"),
                    "defect_description": task.get("defect_description"),
                    "deadline": deadline_dt.isoformat(),
                    "overdue_days": overdue_days,
                    "severity": task.get("severity"),
                }
            )

        overdue_tasks.sort(key=lambda x: x["overdue_days"], reverse=True)

        return success_response(
            data=overdue_tasks,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get overdue tasks: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取逾期任务失败",
        )


@router.get("/{task_id}", response_model=dict)
async def get_remediation_task(
    request: Request,
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取整改任务详情"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看整改任务详情",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            row = (
                session.execute(
                    text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                    {"id": task_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise HTTPException(
                    status_code=StatusCode.NOT_FOUND,
                    detail=f"整改任务不存在: {task_id}",
                )
            task_dict = dict(row)
            _assert_task_institute_access(session, actor, task_dict)
            if not actor["is_manager"] and str(task_dict.get("assignee_id") or "") != actor["id"]:
                raise HTTPException(
                    status_code=StatusCode.FORBIDDEN,
                    detail="无权查看指派给他人的整改任务",
                )

            history = [
                _serialize_row(dict(h))
                for h in session.execute(
                    text(
                        "SELECT * FROM qc_remediation_history "
                        "WHERE task_id = :task_id ORDER BY created_at ASC"
                    ),
                    {"task_id": task_id},
                )
                .mappings()
                .all()
            ]
            result_data = _serialize_row(task_dict)
            result_data["history"] = history

        return success_response(
            data=result_data,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get remediation task: %s",
            str(e),
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取整改任务详情失败",
        )


@router.put("/{task_id}", response_model=dict)
async def update_remediation_task(
    request: Request,
    task_id: str,
    task: RemediationTaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    """更新整改任务（仅质控人员/管理员，带院区校验与事务 CAS）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_MANAGE_ROLES,
        denied_detail="仅质控人员或管理员可更新整改任务",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                        {"id": task_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"整改任务不存在: {task_id}",
                    )
                existing_task = dict(row)
                _assert_task_institute_access(session, actor, existing_task)

                current_status = str(existing_task.get("status") or "")
                if current_status not in _UPDATABLE_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail="只能更新待整改或已退回状态的任务",
                    )

                update_data: Dict[str, Any] = {}
                if task.defect_description is not None:
                    update_data["defect_description"] = task.defect_description
                if task.defect_location is not None:
                    update_data["defect_location"] = task.defect_location
                if task.severity is not None:
                    update_data["severity"] = task.severity.value
                if task.remediation_requirement is not None:
                    update_data["remediation_requirement"] = task.remediation_requirement
                if task.deadline is not None:
                    update_data["deadline"] = _to_utc_naive(task.deadline)
                if task.assignee_id is not None:
                    _assert_assignee_in_actor_institute(session, actor, str(task.assignee_id))
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
                        detail="没有提供要更新的数据",
                    )

                now = _utc_now()
                update_data["updated_at"] = now
                set_sql = ", ".join(f'"{k}" = :set_{k}' for k in update_data)
                params = {f"set_{k}": v for k, v in update_data.items()}
                params["id"] = task_id
                params["expected_status"] = current_status

                res = session.execute(
                    text(
                        f"UPDATE qc_remediation_tasks SET {set_sql} "
                        "WHERE id = :id AND status = :expected_status"
                    ),
                    params,
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="整改任务状态已变更，请刷新后重试",
                    )

                history_data = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "action": HistoryAction.UPDATE.value,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"] or current_user.get("email", "Unknown"),
                    "old_status": current_status,
                    "new_status": current_status,
                    "comment": "更新整改任务信息",
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_remediation_history", history_data)

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                            {"id": task_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Remediation task updated: %s",
            task_id,
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="整改任务更新成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update remediation task: %s",
            str(e),
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="更新整改任务失败",
        )


# ============================
# 整改流程
# ============================

@router.post("/{task_id}/submit", response_model=dict)
async def submit_remediation(
    request: Request,
    task_id: str,
    submit_data: RemediationSubmit,
    current_user: dict = Depends(get_current_user),
):
    """提交整改（仅负责人，带院区校验与事务 CAS）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权提交整改",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                        {"id": task_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"整改任务不存在: {task_id}",
                    )
                existing_task = dict(row)
                _assert_task_institute_access(session, actor, existing_task)

                if str(existing_task.get("assignee_id") or "") != actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="只有负责人可以提交整改",
                    )

                current_status = str(existing_task.get("status") or "")
                if current_status not in _SUBMITTABLE_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail="只能提交待整改、整改中、逾期或已退回的任务",
                    )

                now = _utc_now()
                evidence_json = json.dumps(
                    submit_data.remediation_evidence or [], ensure_ascii=False, default=str
                )
                res = session.execute(
                    text(
                        "UPDATE qc_remediation_tasks "
                        "SET status = :new_status, remediation_description = :desc, "
                        "remediation_evidence = :evidence, submitted_at = :submitted_at, "
                        "updated_at = :updated_at "
                        "WHERE id = :id AND status = :expected_status"
                    ),
                    {
                        "new_status": RemediationStatus.SUBMITTED.value,
                        "desc": submit_data.remediation_description,
                        "evidence": evidence_json,
                        "submitted_at": now,
                        "updated_at": now,
                        "id": task_id,
                        "expected_status": current_status,
                    },
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="整改任务状态已变更，请刷新后重试",
                    )

                history_data = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "action": HistoryAction.SUBMIT.value,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"] or current_user.get("email", "Unknown"),
                    "old_status": current_status,
                    "new_status": RemediationStatus.SUBMITTED.value,
                    "comment": "提交整改",
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_remediation_history", history_data)

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                            {"id": task_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Remediation submitted: %s",
            task_id,
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="整改提交成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to submit remediation: %s",
            str(e),
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="提交整改失败",
        )


@router.post("/{task_id}/review", response_model=dict)
async def review_remediation(
    request: Request,
    task_id: str,
    review_data: RemediationReview,
    current_user: dict = Depends(get_current_user),
):
    """验收整改（仅质控管理员/系统管理员，禁止自审自批，事务 CAS 终态保护）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_REVIEW_CLOSE_ROLES,
        denied_detail="仅质控管理员或系统管理员可验收整改任务",
    )
    if review_data.action not in {"approve", "reject"}:
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST,
            detail="验收动作必须为 approve 或 reject",
        )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                        {"id": task_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"整改任务不存在: {task_id}",
                    )
                existing_task = dict(row)
                _assert_task_institute_access(session, actor, existing_task)

                # 禁止整改负责人自审自批
                if str(existing_task.get("assignee_id") or "") == actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="整改责任人不能验收自己的整改任务",
                    )

                current_status = str(existing_task.get("status") or "")
                if current_status in _TERMINAL_REMEDIATION_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail=f"整改任务已处于终态（{current_status}），不可覆写",
                    )
                if current_status != RemediationStatus.SUBMITTED.value:
                    raise HTTPException(
                        status_code=409,
                        detail="只能验收已提交状态的整改任务",
                    )

                now = _utc_now()
                new_status = (
                    RemediationStatus.APPROVED.value
                    if review_data.action == "approve"
                    else RemediationStatus.REJECTED.value
                )
                update_data: Dict[str, Any] = {
                    "status": new_status,
                    "reviewer_id": actor["id"],
                    "reviewer_name": actor["name"] or current_user.get("email", "Unknown"),
                    "review_comment": review_data.review_comment,
                    "reviewed_at": now,
                    "updated_at": now,
                }
                if review_data.action == "approve":
                    update_data["closed_at"] = now

                set_sql = ", ".join(f'"{k}" = :set_{k}' for k in update_data)
                params = {f"set_{k}": v for k, v in update_data.items()}
                params["id"] = task_id
                params["expected_status"] = RemediationStatus.SUBMITTED.value

                res = session.execute(
                    text(
                        f"UPDATE qc_remediation_tasks SET {set_sql} "
                        "WHERE id = :id AND status = :expected_status"
                    ),
                    params,
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="整改任务状态已变更或存在并发冲突，请刷新后重试",
                    )

                action = (
                    HistoryAction.APPROVE.value
                    if review_data.action == "approve"
                    else HistoryAction.REJECT.value
                )
                history_data = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "action": action,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"] or current_user.get("email", "Unknown"),
                    "old_status": current_status,
                    "new_status": new_status,
                    "comment": review_data.review_comment,
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_remediation_history", history_data)

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                            {"id": task_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Remediation reviewed: %s, action: %s",
            task_id,
            review_data.action,
            extra={"trace_id": trace_id, "reviewer_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="验收成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to review remediation: %s",
            str(e),
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="验收整改失败",
        )


@router.post("/{task_id}/close", response_model=dict)
async def close_remediation_task(
    request: Request,
    task_id: str,
    close_data: RemediationClose,
    current_user: dict = Depends(get_current_user),
):
    """关闭整改任务（仅质控管理员/系统管理员，禁止自关与覆写终态）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_REVIEW_CLOSE_ROLES,
        denied_detail="仅质控管理员或系统管理员可关闭整改任务",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                        {"id": task_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"整改任务不存在: {task_id}",
                    )
                existing_task = dict(row)
                _assert_task_institute_access(session, actor, existing_task)

                if str(existing_task.get("assignee_id") or "") == actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="整改责任人不能直接关闭自己的整改任务",
                    )

                current_status = str(existing_task.get("status") or "")
                if current_status in _TERMINAL_REMEDIATION_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail=f"任务已处于终态（{current_status}），不可覆写关闭",
                    )

                now = _utc_now()
                update_data: Dict[str, Any] = {
                    "status": RemediationStatus.CLOSED.value,
                    "closed_at": now,
                    "updated_at": now,
                }
                if close_data.reason:
                    existing_notes = existing_task.get("notes") or ""
                    update_data["notes"] = f"{existing_notes}\n关闭原因: {close_data.reason}".strip()

                set_sql = ", ".join(f'"{k}" = :set_{k}' for k in update_data)
                params = {f"set_{k}": v for k, v in update_data.items()}
                params["id"] = task_id
                params["expected_status"] = current_status

                res = session.execute(
                    text(
                        f"UPDATE qc_remediation_tasks SET {set_sql} "
                        "WHERE id = :id AND status = :expected_status"
                    ),
                    params,
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="整改任务状态已变更或存在并发冲突，请刷新后重试",
                    )

                history_data = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "action": HistoryAction.CLOSE.value,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"] or current_user.get("email", "Unknown"),
                    "old_status": current_status,
                    "new_status": RemediationStatus.CLOSED.value,
                    "comment": close_data.reason or "关闭整改任务",
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_remediation_history", history_data)

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_remediation_tasks WHERE id = :id"),
                            {"id": task_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Remediation task closed: %s",
            task_id,
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="整改任务已关闭",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to close remediation task: %s",
            str(e),
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="关闭整改任务失败",
        )
