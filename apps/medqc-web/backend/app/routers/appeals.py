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
from ..schemas.appeals import (
    AppealCreate,
    AppealReviewCreate,
    AppealStatus,
    AppealUpdate,
    AppealWithdraw,
    ReviewAction,
)
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    configured_search_path,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/appeals", tags=["appeals"])
logger = logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_REVIEW_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})
_STAFF_READ_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_ALL_ALLOWED_ROLES = _STAFF_READ_ROLES | frozenset({"doctor"})
_TERMINAL_APPEAL_STATUSES = frozenset(
    {
        AppealStatus.APPROVED.value,
        AppealStatus.REJECTED.value,
        AppealStatus.WITHDRAWN.value,
    }
)
_OPEN_APPEAL_STATUSES = frozenset(
    {
        AppealStatus.PENDING.value,
        AppealStatus.REVIEWING.value,
    }
)


def _legacy_only(query):
    # 只使用旧版已有列，兼容旧库；现代申诉的两个旧主键必须为 NULL。
    return query.is_not("qc_result_id", None).is_not("record_id", None)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        logger.error("appeals_actor_lookup_failed", exc_info=True)
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

    institute_id = row.get("institute_id") if has_institute else None
    is_global = ("sync_admin" in roles) or (
        bool(roles & {"admin", "super_admin"}) and not institute_id
    )
    if not is_global:
        if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
            raise HTTPException(status_code=StatusCode.FORBIDDEN, detail="账号缺少可信机构范围")
    else:
        institute_id = None

    primary_role = (
        "admin"
        if "admin" in roles
        else (
            "super_admin"
            if "super_admin" in roles
            else ("qc_manager" if "qc_manager" in roles else sorted(roles)[0])
        )
    )
    return {
        "id": str(row["id"]),
        "name": str(row.get("display_name") or current_user.get("display_name") or current_user.get("name") or ""),
        "department": row.get("department"),
        "roles": roles,
        "primary_role": primary_role,
        "is_global": is_global,
        "is_staff": bool(roles & _STAFF_READ_ROLES),
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


def _resolve_appeal_institute(session, appeal_row: Dict[str, Any]) -> Optional[str]:
    """根据关联质控结果与申诉人持久账号解析旧申诉归属机构（兼容 ck_qc_appeals_modern_source）。"""
    institutes: Set[str] = set()

    qc_result_id = str(appeal_row.get("qc_result_id") or "").strip()
    if qc_result_id:
        qc_cols = _table_columns(session, "qc_results")
        if "institute_id" in qc_cols:
            qc_inst = session.execute(
                text("SELECT institute_id FROM qc_results WHERE id = :qid"),
                {"qid": qc_result_id},
            ).scalar_one_or_none()
            if isinstance(qc_inst, str) and qc_inst.strip():
                institutes.add(qc_inst.strip())

    appellant_id = str(appeal_row.get("appellant_id") or "").strip()
    if appellant_id:
        try:
            user_ref, user_cols = _user_table_ref(session)
            if "institute_id" in user_cols:
                u_inst = session.execute(
                    text(f"SELECT institute_id FROM {user_ref} WHERE id = :uid"),
                    {"uid": appellant_id},
                ).scalar_one_or_none()
                if isinstance(u_inst, str) and u_inst.strip():
                    institutes.add(u_inst.strip())
        except Exception:
            pass

    if len(institutes) == 1:
        return next(iter(institutes))
    return None


def _assert_appeal_institute_access(session, actor: Dict[str, Any], appeal_row: Dict[str, Any]) -> None:
    if actor["is_global"]:
        return
    appeal_inst = _resolve_appeal_institute(session, appeal_row)
    if not appeal_inst or appeal_inst != actor["institute_id"]:
        raise HTTPException(
            status_code=StatusCode.FORBIDDEN,
            detail="无权访问或操作其他机构的申诉",
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
# 申诉管理
# ============================

@router.post("", response_model=dict)
async def create_appeal(
    request: Request,
    appeal: AppealCreate,
    current_user: dict = Depends(get_current_user),
):
    """创建旧版申诉（带 UUID 主键与院区归属校验）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权创建申诉",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                qc_cols = _table_columns(session, "qc_results")
                qc_row = (
                    session.execute(
                        text("SELECT * FROM qc_results WHERE id = :qid"),
                        {"qid": str(appeal.qc_result_id)},
                    )
                    .mappings()
                    .one_or_none()
                )
                if qc_row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"质控结果不存在: {appeal.qc_result_id}",
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
                            detail="无权对其他机构质控结果发起申诉",
                        )

                mr_cols = _table_columns(session, "medical_records")
                if mr_cols:
                    mr_row = (
                        session.execute(
                            text("SELECT * FROM medical_records WHERE id = :rid"),
                            {"rid": str(appeal.record_id)},
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if mr_row is None:
                        raise HTTPException(
                            status_code=StatusCode.NOT_FOUND,
                            detail=f"病历不存在: {appeal.record_id}",
                        )
                    if not actor["is_global"] and "institute_id" in mr_cols:
                        mr_inst = mr_row.get("institute_id")
                        if isinstance(mr_inst, str) and mr_inst.strip() and mr_inst.strip() != actor["institute_id"]:
                            raise HTTPException(
                                status_code=StatusCode.FORBIDDEN,
                                detail="无权对其他机构病历发起申诉",
                            )

                now = _utc_now()
                appeal_id = str(uuid.uuid4())
                appeal_number = f"AP-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                # 严禁为旧申诉写入 institute_id 等现代列，避免破坏 ck_qc_appeals_modern_source
                appeal_data = {
                    "id": appeal_id,
                    "appeal_number": appeal_number,
                    "qc_result_id": str(appeal.qc_result_id),
                    "record_id": str(appeal.record_id),
                    "appeal_type": appeal.appeal_type.value,
                    "defect_item": appeal.defect_item,
                    "reason": appeal.reason,
                    "evidence": appeal.evidence,
                    "priority": appeal.priority.value,
                    "appellant_id": actor["id"],
                    "appellant_name": actor["name"] or current_user.get("email", "Unknown"),
                    "appellant_department": appeal.appellant_department or actor.get("department"),
                    "notes": appeal.notes,
                    "status": AppealStatus.PENDING.value,
                    "created_at": now,
                    "updated_at": now,
                }
                created = _insert_row(session, "qc_appeals", appeal_data)

        logger.info(
            "Appeal created: %s",
            created["id"],
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=created,
            message="申诉创建成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create appeal: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="创建申诉失败",
        )


@router.get("", response_model=dict)
async def list_appeals(
    request: Request,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    appeal_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """获取旧版申诉列表（排除现代申诉，按角色与院区隔离）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看申诉列表",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            where_clauses = ["qc_result_id IS NOT NULL", "record_id IS NOT NULL"]
            params: Dict[str, Any] = {}

            if not actor["is_staff"]:
                where_clauses.append("appellant_id = :actor_id")
                params["actor_id"] = actor["id"]
            if status:
                where_clauses.append("status = :status")
                params["status"] = status
            if priority:
                where_clauses.append("priority = :priority")
                params["priority"] = priority
            if appeal_type:
                where_clauses.append("appeal_type = :appeal_type")
                params["appeal_type"] = appeal_type
            if start_date:
                where_clauses.append("created_at >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where_clauses.append("created_at <= :end_date")
                params["end_date"] = end_date

            sql = (
                f"SELECT * FROM qc_appeals WHERE {' AND '.join(where_clauses)} "
                f"ORDER BY created_at DESC"
            )
            rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]

            if not actor["is_global"]:
                scoped_rows: List[Dict[str, Any]] = []
                for row in rows:
                    inst = _resolve_appeal_institute(session, row)
                    if inst == actor["institute_id"]:
                        scoped_rows.append(row)
                rows = scoped_rows

            total = len(rows)
            offset = (page - 1) * page_size
            page_items = [_serialize_row(r) for r in rows[offset : offset + page_size]]

        return paginated_response(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to list appeals: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取申诉列表失败",
        )


@router.get("/statistics/summary", response_model=dict)
async def get_appeal_statistics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """获取旧版申诉统计（排除现代申诉，支持日期与院区隔离）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看申诉统计",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            where_clauses = ["qc_result_id IS NOT NULL", "record_id IS NOT NULL"]
            params: Dict[str, Any] = {}
            if not actor["is_staff"]:
                where_clauses.append("appellant_id = :actor_id")
                params["actor_id"] = actor["id"]
            if start_date:
                where_clauses.append("created_at >= :start_date")
                params["start_date"] = start_date
            if end_date:
                where_clauses.append("created_at <= :end_date")
                params["end_date"] = end_date

            sql = f"SELECT * FROM qc_appeals WHERE {' AND '.join(where_clauses)}"
            rows = [dict(r) for r in session.execute(text(sql), params).mappings().all()]
            if not actor["is_global"]:
                rows = [
                    r for r in rows
                    if _resolve_appeal_institute(session, r) == actor["institute_id"]
                ]

        stats: Dict[str, Any] = {
            "total": 0,
            "pending": 0,
            "reviewing": 0,
            "approved": 0,
            "rejected": 0,
            "withdrawn": 0,
            "avg_resolution_time_hours": 0.0,
            "by_type": {},
            "by_priority": {},
        }

        for row in rows:
            st = row.get("status")
            appeal_type = row.get("appeal_type")
            priority = row.get("priority")
            stats["total"] += 1
            if st in stats:
                stats[st] += 1
            if appeal_type:
                stats["by_type"][appeal_type] = stats["by_type"].get(appeal_type, 0) + 1
            if priority:
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

        return success_response(
            data=stats,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get appeal statistics: %s",
            str(e),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取统计数据失败",
        )


@router.get("/{appeal_id}", response_model=dict)
async def get_appeal(
    request: Request,
    appeal_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取旧版申诉详情"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权查看申诉详情",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            row = (
                session.execute(
                    text(
                        "SELECT * FROM qc_appeals "
                        "WHERE id = :id AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                    ),
                    {"id": appeal_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise HTTPException(
                    status_code=StatusCode.NOT_FOUND,
                    detail=f"申诉不存在: {appeal_id}",
                )
            appeal_dict = dict(row)
            _assert_appeal_institute_access(session, actor, appeal_dict)
            if not actor["is_staff"] and str(appeal_dict.get("appellant_id") or "") != actor["id"]:
                raise HTTPException(
                    status_code=StatusCode.FORBIDDEN,
                    detail="无权查看他人的申诉",
                )

            reviews = [
                _serialize_row(dict(r))
                for r in session.execute(
                    text(
                        "SELECT * FROM qc_appeal_reviews "
                        "WHERE appeal_id = :appeal_id ORDER BY created_at ASC"
                    ),
                    {"appeal_id": appeal_id},
                )
                .mappings()
                .all()
            ]
            result_data = _serialize_row(appeal_dict)
            result_data["reviews"] = reviews

        return success_response(
            data=result_data,
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get appeal: %s",
            str(e),
            extra={"trace_id": trace_id, "appeal_id": appeal_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="获取申诉详情失败",
        )


@router.put("/{appeal_id}", response_model=dict)
async def update_appeal(
    request: Request,
    appeal_id: str,
    appeal: AppealUpdate,
    current_user: dict = Depends(get_current_user),
):
    """更新申诉（仅申诉人在 pending 态可更新，带 CAS 保护）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权更新申诉",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text(
                            "SELECT * FROM qc_appeals "
                            "WHERE id = :id AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                        ),
                        {"id": appeal_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"申诉不存在: {appeal_id}",
                    )
                existing_appeal = dict(row)
                _assert_appeal_institute_access(session, actor, existing_appeal)

                if str(existing_appeal.get("appellant_id") or "") != actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="只有申诉人可以更新申诉",
                    )
                if existing_appeal.get("status") != AppealStatus.PENDING.value:
                    raise HTTPException(
                        status_code=409,
                        detail="只能更新待审核状态的申诉",
                    )

                appeal_cols = _table_columns(session, "qc_appeals")
                update_data: Dict[str, Any] = {}
                if appeal.reason is not None:
                    update_data["reason"] = appeal.reason
                if appeal.evidence is not None and "evidence" in appeal_cols:
                    update_data["evidence"] = json.dumps(appeal.evidence, ensure_ascii=False, default=str)
                if appeal.priority is not None:
                    update_data["priority"] = appeal.priority.value
                if appeal.notes is not None:
                    update_data["notes"] = appeal.notes

                if not update_data:
                    raise HTTPException(
                        status_code=StatusCode.BAD_REQUEST,
                        detail="没有提供要更新的数据",
                    )

                update_data["updated_at"] = _utc_now()
                set_sql = ", ".join(f'"{k}" = :set_{k}' for k in update_data)
                params = {f"set_{k}": v for k, v in update_data.items()}
                params["id"] = appeal_id
                params["expected_status"] = AppealStatus.PENDING.value

                res = session.execute(
                    text(
                        f"UPDATE qc_appeals SET {set_sql} "
                        "WHERE id = :id AND status = :expected_status "
                        "AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                    ),
                    params,
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="申诉状态已变更，无法更新",
                    )

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_appeals WHERE id = :id"),
                            {"id": appeal_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Appeal updated: %s",
            appeal_id,
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="申诉更新成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update appeal: %s",
            str(e),
            extra={"trace_id": trace_id, "appeal_id": appeal_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="更新申诉失败",
        )


@router.post("/{appeal_id}/withdraw", response_model=dict)
async def withdraw_appeal(
    request: Request,
    appeal_id: str,
    withdraw: AppealWithdraw,
    current_user: dict = Depends(get_current_user),
):
    """撤回申诉（仅申诉人可撤回，带事务 CAS 与终态保护）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_ALL_ALLOWED_ROLES,
        denied_detail="无权撤回申诉",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text(
                            "SELECT * FROM qc_appeals "
                            "WHERE id = :id AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                        ),
                        {"id": appeal_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"申诉不存在: {appeal_id}",
                    )
                existing_appeal = dict(row)
                _assert_appeal_institute_access(session, actor, existing_appeal)

                if str(existing_appeal.get("appellant_id") or "") != actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="只有申诉人可以撤回申诉",
                    )

                current_status = str(existing_appeal.get("status") or "")
                if current_status not in _OPEN_APPEAL_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail="只能撤回待审核或审核中的申诉，终态申诉不可撤回",
                    )

                now = _utc_now()
                res = session.execute(
                    text(
                        "UPDATE qc_appeals "
                        "SET status = :new_status, resolution = :resolution, "
                        "resolution_date = :resolution_date, updated_at = :updated_at "
                        "WHERE id = :id AND status = :expected_status "
                        "AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                    ),
                    {
                        "new_status": AppealStatus.WITHDRAWN.value,
                        "resolution": withdraw.reason or "申诉人主动撤回",
                        "resolution_date": now,
                        "updated_at": now,
                        "id": appeal_id,
                        "expected_status": current_status,
                    },
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="申诉状态已变更或并发冲突，无法撤回",
                    )

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_appeals WHERE id = :id"),
                            {"id": appeal_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Appeal withdrawn: %s",
            appeal_id,
            extra={"trace_id": trace_id, "user_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="申诉已撤回",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to withdraw appeal: %s",
            str(e),
            extra={"trace_id": trace_id, "appeal_id": appeal_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="撤回申诉失败",
        )


# ============================
# 审核管理
# ============================

@router.post("/{appeal_id}/review", response_model=dict)
async def review_appeal(
    request: Request,
    appeal_id: str,
    review: AppealReviewCreate,
    current_user: dict = Depends(get_current_user),
):
    """审核申诉（仅质控管理员/系统管理员，禁止自审自批，事务 CAS 终态保护）"""
    trace_id = get_trace_id(request)
    actor = _resolve_actor(
        current_user,
        allowed_roles=_REVIEW_ROLES,
        denied_detail="仅质控管理员或系统管理员可审核申诉",
    )
    session_factory = _get_session_factory()

    try:
        with session_factory() as session:
            with session.begin():
                row = (
                    session.execute(
                        text(
                            "SELECT * FROM qc_appeals "
                            "WHERE id = :id AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                        ),
                        {"id": appeal_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(
                        status_code=StatusCode.NOT_FOUND,
                        detail=f"申诉不存在: {appeal_id}",
                    )

                existing_appeal = dict(row)
                _assert_appeal_institute_access(session, actor, existing_appeal)

                # 禁止申请人自审自批
                if str(existing_appeal.get("appellant_id") or "") == actor["id"]:
                    raise HTTPException(
                        status_code=StatusCode.FORBIDDEN,
                        detail="申诉人不能审核自己的申诉",
                    )

                current_status = str(existing_appeal.get("status") or "")
                if current_status in _TERMINAL_APPEAL_STATUSES or current_status not in _OPEN_APPEAL_STATUSES:
                    raise HTTPException(
                        status_code=409,
                        detail=f"申诉当前处于终态（{current_status}），不可重复审核或覆写",
                    )

                now = _utc_now()
                update_data: Dict[str, Any] = {
                    "reviewer_id": actor["id"],
                    "reviewer_name": actor["name"] or current_user.get("email", "Unknown"),
                    "review_date": now,
                    "review_result": review.comment,
                    "updated_at": now,
                }
                if review.action == ReviewAction.APPROVE:
                    update_data["status"] = AppealStatus.APPROVED.value
                    update_data["resolution"] = review.resolution or "申诉已批准"
                    update_data["resolution_date"] = now
                elif review.action == ReviewAction.REJECT:
                    update_data["status"] = AppealStatus.REJECTED.value
                    update_data["resolution"] = review.resolution or "申诉已拒绝"
                    update_data["resolution_date"] = now
                else:
                    update_data["status"] = AppealStatus.REVIEWING.value

                # 先 CAS 更新主表，再在同事务内写审核流水，防止并发竞态污染审核记录
                set_sql = ", ".join(f'"{k}" = :set_{k}' for k in update_data)
                params = {f"set_{k}": v for k, v in update_data.items()}
                params["id"] = appeal_id
                params["expected_status"] = current_status

                res = session.execute(
                    text(
                        f"UPDATE qc_appeals SET {set_sql} "
                        "WHERE id = :id AND status = :expected_status "
                        "AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
                    ),
                    params,
                )
                if (res.rowcount or 0) != 1:
                    raise HTTPException(
                        status_code=409,
                        detail="申诉状态已变更或存在并发冲突，请刷新后重试",
                    )

                review_data = {
                    "id": str(uuid.uuid4()),
                    "appeal_id": appeal_id,
                    "reviewer_id": actor["id"],
                    "reviewer_name": actor["name"] or current_user.get("email", "Unknown"),
                    "reviewer_role": actor["primary_role"],
                    "action": review.action.value,
                    "comment": review.comment,
                    "metadata": {},
                    "created_at": now,
                }
                _insert_row(session, "qc_appeal_reviews", review_data)

                updated = _serialize_row(
                    dict(
                        session.execute(
                            text("SELECT * FROM qc_appeals WHERE id = :id"),
                            {"id": appeal_id},
                        )
                        .mappings()
                        .one()
                    )
                )

        logger.info(
            "Appeal reviewed: %s, action: %s",
            appeal_id,
            review.action.value,
            extra={"trace_id": trace_id, "reviewer_id": actor["id"]},
        )

        return success_response(
            data=updated,
            message="审核成功",
            trace_id=trace_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to review appeal: %s",
            str(e),
            extra={"trace_id": trace_id, "appeal_id": appeal_id},
        )
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="审核申诉失败",
        )
