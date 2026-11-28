"""
缺陷操作管理路由

功能:
- 催办/撤回催办
- 标记已整改
- 审核通过/审核存疑
- 批量操作
- 导出缺陷列表 (Excel/CSV)
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import inspect as sa_inspect, text

from ..core.audit import audit_event
from ..core.permissions import (
    PermissionAction,
    ResourceType,
    require_permission,
)
from ..core.response import (
    get_trace_id,
    paginated_response,
    success_response,
)
from ..core.roles import effective_persistent_roles as _effective_persistent_roles
from ..core.security import get_current_user
from ..core.supabase_client import async_execute, get_supabase  # noqa: F401
from ..database import connection as db_connection
from ..database.schema_introspection import get_table_columns as _table_columns
from ..schemas.defects import (
    DefectApproveRequest,
    DefectBatchActionRequest,
    DefectCancelUrgeRequest,
    DefectMarkRemediatedRequest,
    DefectRejectRequest,
    DefectStatus,
    DefectUrgeRequest,
)
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/qc/defects", tags=["defects"])
logger = logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_READ_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_OPERATIONAL_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_REVIEW_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})
_EXPORT_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager"})

# 合法状态流转守卫：终态 approved 不可被任何操作覆写
_ALLOWED_TRANSITIONS: Dict[str, Tuple[Set[str], str]] = {
    "urge": (
        {DefectStatus.PENDING.value, DefectStatus.REJECTED.value},
        DefectStatus.URGED.value,
    ),
    "cancel_urge": (
        {DefectStatus.URGED.value},
        DefectStatus.PENDING.value,
    ),
    "mark_remediated": (
        {
            DefectStatus.PENDING.value,
            DefectStatus.URGED.value,
            DefectStatus.REJECTED.value,
        },
        DefectStatus.REMEDIATED.value,
    ),
    "approve": (
        {DefectStatus.REMEDIATED.value},
        DefectStatus.APPROVED.value,
    ),
    "reject": (
        {DefectStatus.REMEDIATED.value},
        DefectStatus.REJECTED.value,
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_session_factory():
    factory = db_connection.SessionLocal
    if factory is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    return factory


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
            owner_schema = resolve_user_owner_schema(session)
            inspector = sa_inspect(session.connection())
            if not inspector.has_table("sys_users", schema=owner_schema):
                raise HTTPException(status_code=503, detail="账号持久表不可用")
            user_cols = {
                col["name"]
                for col in inspector.get_columns("sys_users", schema=owner_schema)
            }
            has_institute = "institute_id" in user_cols
            table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
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
        logger.error("defects_actor_lookup_failed", exc_info=True)
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
        "institute_id": institute_id,
    }


def _legacy_defect_where(
    defect_cols: Set[str],
    actor: Dict[str, Any],
    params: Dict[str, Any],
) -> List[str]:
    clauses: List[str] = []
    if "origin" in defect_cols:
        clauses.append("(origin IS NULL OR origin != 'manual')")
    if not actor["is_global"]:
        if "institute_id" not in defect_cols:
            raise HTTPException(status_code=403, detail="缺陷数据缺少机构隔离字段")
        clauses.append("institute_id = :actor_institute_id")
        params["actor_institute_id"] = actor["institute_id"]
    return clauses


def _serialize_row_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _serialize_row_value(v) for k, v in row.items()}


def _transition_defect_sync(
    *,
    defect_id: str,
    action: str,
    actor: Dict[str, Any],
    extra_fields: Dict[str, Any],
    history_action: Optional[str] = None,
    history_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """在单事务内校验现代人工缺陷隔离、院区隔离、状态机与 CAS 更新，并同事务落历史。"""
    if action not in _ALLOWED_TRANSITIONS:
        raise HTTPException(status_code=400, detail=f"不支持的缺陷操作: {action}")

    allowed_from, target_status = _ALLOWED_TRANSITIONS[action]
    session_factory = _get_session_factory()

    with session_factory() as session:
        with session.begin():
            defect_cols = _table_columns(session, "qc_defects")
            if not defect_cols:
                raise HTTPException(status_code=503, detail="缺陷表不可用")

            has_origin = "origin" in defect_cols
            has_institute = "institute_id" in defect_cols

            row = (
                session.execute(
                    text("SELECT * FROM qc_defects WHERE id = :defect_id"),
                    {"defect_id": defect_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise HTTPException(status_code=404, detail=f"缺陷 {defect_id} 不存在")

            if has_origin and row.get("origin") == "manual":
                raise HTTPException(
                    status_code=409,
                    detail="现代人工缺陷请通过人工缺陷复核与整改闭环处理，禁止通过旧缺陷接口修改",
                )

            if not actor["is_global"]:
                if not has_institute:
                    raise HTTPException(status_code=403, detail="缺陷数据缺少机构隔离字段")
                row_inst = row.get("institute_id")
                if not isinstance(row_inst, str) or row_inst.strip() != actor["institute_id"]:
                    raise HTTPException(status_code=403, detail="无权操作其他机构缺陷")

            current_status = str(row.get("status") or "").strip()
            if current_status == DefectStatus.APPROVED.value:
                raise HTTPException(
                    status_code=409,
                    detail="缺陷已审核通过（终态），不可覆写状态",
                )
            if current_status not in allowed_from:
                raise HTTPException(
                    status_code=409,
                    detail=f"当前状态 '{current_status}' 不允许执行 '{action}' 操作",
                )

            if action == "approve":
                remediated_by = str(row.get("remediated_by") or "").strip()
                if remediated_by and remediated_by == actor["id"]:
                    raise HTTPException(
                        status_code=403,
                        detail="整改标记人与审核人不能为同一人",
                    )

            now = _utc_now()
            update_payload: Dict[str, Any] = {
                "status": target_status,
                "updated_at": now,
            }
            for key, val in extra_fields.items():
                if key in defect_cols:
                    if isinstance(val, (dict, list)):
                        update_payload[key] = json.dumps(val, ensure_ascii=False, default=str)
                    else:
                        update_payload[key] = val

            set_clauses = [f'"{col}" = :set_{col}' for col in update_payload]
            params: Dict[str, Any] = {f"set_{col}": val for col, val in update_payload.items()}
            where_clauses = ["id = :defect_id", "status = :expected_status"]
            params["defect_id"] = defect_id
            params["expected_status"] = current_status

            if has_origin:
                where_clauses.append("(origin IS NULL OR origin != 'manual')")
            if not actor["is_global"]:
                where_clauses.append("institute_id = :actor_institute_id")
                params["actor_institute_id"] = actor["institute_id"]

            update_sql = (
                f"UPDATE qc_defects SET {', '.join(set_clauses)} "
                f"WHERE {' AND '.join(where_clauses)}"
            )
            update_res = session.execute(text(update_sql), params)
            if (update_res.rowcount or 0) != 1:
                raise HTTPException(
                    status_code=409,
                    detail="缺陷状态已变更或存在并发冲突，请刷新后重试",
                )

            history_cols = _table_columns(session, "qc_defect_history")
            if history_cols:
                history_record = {
                    "id": str(uuid.uuid4()),
                    "defect_id": defect_id,
                    "action": history_action or action,
                    "actor_id": actor["id"],
                    "actor_name": actor["name"],
                    "details": json.dumps(history_details or {}, ensure_ascii=False, default=str),
                    "created_at": now,
                }
                insert_cols = [c for c in history_record if c in history_cols]
                col_sql = ", ".join(f'"{c}"' for c in insert_cols)
                val_sql = ", ".join(f":{c}" for c in insert_cols)
                session.execute(
                    text(f"INSERT INTO qc_defect_history ({col_sql}) VALUES ({val_sql})"),
                    {c: history_record[c] for c in insert_cols},
                )

            updated_row = (
                session.execute(
                    text("SELECT * FROM qc_defects WHERE id = :defect_id"),
                    {"defect_id": defect_id},
                )
                .mappings()
                .one()
            )
            return _serialize_row(dict(updated_row))


def _query_defects_sync(
    *,
    actor: Dict[str, Any],
    record_id: Optional[str] = None,
    department: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    with_count: bool = False,
    select_columns: str = "*",
) -> Tuple[List[Dict[str, Any]], int]:
    session_factory = _get_session_factory()
    with session_factory() as session:
        defect_cols = _table_columns(session, "qc_defects")
        if not defect_cols:
            return [], 0

        params: Dict[str, Any] = {}
        where_clauses = _legacy_defect_where(defect_cols, actor, params)

        if record_id:
            where_clauses.append("record_id = :record_id")
            params["record_id"] = record_id
        if department:
            where_clauses.append("department = :department")
            params["department"] = department
        if severity:
            where_clauses.append("severity = :severity")
            params["severity"] = severity
        if category:
            where_clauses.append("category = :category")
            params["category"] = category
        if status:
            where_clauses.append("status = :status")
            params["status"] = status
        if start_date:
            where_clauses.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            where_clauses.append("created_at <= :end_date")
            params["end_date"] = end_date
        if keyword:
            where_clauses.append(
                "(LOWER(COALESCE(rule_name, '')) LIKE LOWER(:kw) "
                "OR LOWER(COALESCE(description, '')) LIKE LOWER(:kw))"
            )
            params["kw"] = f"%{keyword}%"

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        total = 0
        if with_count:
            total = int(
                session.execute(
                    text(f"SELECT COUNT(*) FROM qc_defects{where_sql}"),
                    params,
                ).scalar()
                or 0
            )

        sql = f"SELECT {select_columns} FROM qc_defects{where_sql} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT :limit_val OFFSET :offset_val"
            params["limit_val"] = int(limit)
            params["offset_val"] = int(offset)

        rows = [
            _serialize_row(dict(r))
            for r in session.execute(text(sql), params).mappings().all()
        ]
        if not with_count:
            total = len(rows)
        return rows, total


# ============================
# 缺陷列表查询
# ============================

@router.get("")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def list_defects(
    request: Request,
    record_id: Optional[str] = Query(None, description="病历ID"),
    department: Optional[str] = Query(None, description="科室"),
    severity: Optional[str] = Query(None, description="严重程度"),
    category: Optional[str] = Query(None, description="缺陷分类"),
    status: Optional[str] = Query(None, description="缺陷状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """获取缺陷列表（强制排除现代人工缺陷并按院区隔离）"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看缺陷列表")

    try:
        offset = (page - 1) * page_size
        data, total = _query_defects_sync(
            actor=actor,
            record_id=record_id,
            department=department,
            severity=severity,
            category=category,
            status=status,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            limit=page_size,
            offset=offset,
            with_count=True,
        )

        return paginated_response(
            items=data,
            total=total,
            page=page,
            page_size=page_size,
            message="获取缺陷列表成功",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询缺陷列表失败: {e}")
        raise HTTPException(status_code=500, detail="查询缺陷列表失败")


# ============================
# 缺陷操作
# ============================

@router.post("/{defect_id}/urge")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def urge_defect(
    request: Request,
    defect_id: str,
    urge_data: DefectUrgeRequest,
    current_user: dict = Depends(get_current_user),
):
    """催办缺陷 — 向医生端推送催办消息"""
    actor = _resolve_actor(current_user, allowed_roles=_OPERATIONAL_ROLES, denied_detail="无权催办缺陷")
    now = _utc_now()
    _transition_defect_sync(
        defect_id=defect_id,
        action="urge",
        actor=actor,
        extra_fields={
            "urged_at": now,
            "urged_by": actor["id"],
            "urged_message": urge_data.message,
            "urged_deadline": urge_data.deadline,
        },
        history_details={"message": urge_data.message, "deadline": urge_data.deadline},
    )

    return success_response(
        data={
            "defect_id": defect_id,
            "action": "urge",
            "new_status": DefectStatus.URGED.value,
            "message": urge_data.message,
        },
        message="催办成功",
        trace_id=get_trace_id(request),
    )


@router.post("/{defect_id}/cancel-urge")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def cancel_urge_defect(
    request: Request,
    defect_id: str,
    cancel_data: DefectCancelUrgeRequest,
    current_user: dict = Depends(get_current_user),
):
    """撤回催办"""
    actor = _resolve_actor(current_user, allowed_roles=_OPERATIONAL_ROLES, denied_detail="无权撤回催办")
    _transition_defect_sync(
        defect_id=defect_id,
        action="cancel_urge",
        actor=actor,
        extra_fields={
            "urged_at": None,
            "urged_by": None,
            "urged_message": None,
            "urged_deadline": None,
        },
        history_details={"reason": cancel_data.reason},
    )

    return success_response(
        data={
            "defect_id": defect_id,
            "action": "cancel_urge",
            "new_status": DefectStatus.PENDING.value,
        },
        message="已撤回催办",
        trace_id=get_trace_id(request),
    )


@router.post("/{defect_id}/mark-remediated")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def mark_defect_remediated(
    request: Request,
    defect_id: str,
    remediation_data: DefectMarkRemediatedRequest,
    current_user: dict = Depends(get_current_user),
):
    """标记缺陷已整改 — 人工核销缺陷"""
    actor = _resolve_actor(current_user, allowed_roles=_OPERATIONAL_ROLES, denied_detail="无权标记缺陷已整改")
    now = _utc_now()
    evidence = remediation_data.evidence or []
    _transition_defect_sync(
        defect_id=defect_id,
        action="mark_remediated",
        actor=actor,
        extra_fields={
            "remediated_at": now,
            "remediated_by": actor["id"],
            "remediation_note": remediation_data.remediation_note,
            "remediation_evidence": evidence,
        },
        history_details={
            "remediation_note": remediation_data.remediation_note,
            "evidence_count": len(evidence),
        },
    )

    return success_response(
        data={
            "defect_id": defect_id,
            "action": "mark_remediated",
            "new_status": DefectStatus.REMEDIATED.value,
        },
        message="已标记为已整改",
        trace_id=get_trace_id(request),
    )


@router.post("/{defect_id}/approve")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.REVIEW)
async def approve_defect(
    request: Request,
    defect_id: str,
    approve_data: DefectApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """审核通过 — 确认缺陷已正确整改（仅限质控主管与管理员）"""
    actor = _resolve_actor(
        current_user,
        allowed_roles=_REVIEW_ROLES,
        denied_detail="仅质控管理员或系统管理员可审核通过缺陷",
    )
    now = _utc_now()
    _transition_defect_sync(
        defect_id=defect_id,
        action="approve",
        actor=actor,
        extra_fields={
            "approved_at": now,
            "approved_by": actor["id"],
            "approve_comment": approve_data.comment,
        },
        history_details={"comment": approve_data.comment},
    )

    return success_response(
        data={
            "defect_id": defect_id,
            "action": "approve",
            "new_status": DefectStatus.APPROVED.value,
        },
        message="审核通过",
        trace_id=get_trace_id(request),
    )


@router.post("/{defect_id}/reject")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.REVIEW)
async def reject_defect(
    request: Request,
    defect_id: str,
    reject_data: DefectRejectRequest,
    current_user: dict = Depends(get_current_user),
):
    """审核存疑（退回）— 需要进一步修改（仅限质控主管与管理员）"""
    actor = _resolve_actor(
        current_user,
        allowed_roles=_REVIEW_ROLES,
        denied_detail="仅质控管理员或系统管理员可退回缺陷",
    )
    now = _utc_now()
    _transition_defect_sync(
        defect_id=defect_id,
        action="reject",
        actor=actor,
        extra_fields={
            "rejected_at": now,
            "rejected_by": actor["id"],
            "reject_reason": reject_data.reason,
            "reject_suggestion": reject_data.suggestion,
        },
        history_details={
            "reason": reject_data.reason,
            "suggestion": reject_data.suggestion,
        },
    )

    return success_response(
        data={
            "defect_id": defect_id,
            "action": "reject",
            "new_status": DefectStatus.REJECTED.value,
        },
        message="已退回（审核存疑）",
        trace_id=get_trace_id(request),
    )


# ============================
# 批量操作
# ============================

@router.post("/batch-action")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def batch_defect_action(
    request: Request,
    batch_data: DefectBatchActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """批量操作缺陷（批量审核通过/退回/催办）"""
    action_map = {
        "approve": DefectStatus.APPROVED.value,
        "reject": DefectStatus.REJECTED.value,
        "urge": DefectStatus.URGED.value,
    }

    if batch_data.action not in action_map:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的操作类型: {batch_data.action}，支持: {list(action_map.keys())}",
        )

    required_roles = _REVIEW_ROLES if batch_data.action in {"approve", "reject"} else _OPERATIONAL_ROLES
    actor = _resolve_actor(
        current_user,
        allowed_roles=required_roles,
        denied_detail="权限不足，无法执行批量操作",
    )

    new_status = action_map[batch_data.action]
    results = []

    for defect_id in batch_data.defect_ids:
        now = _utc_now()
        if batch_data.action == "approve":
            extra_fields = {
                "approved_at": now,
                "approved_by": actor["id"],
                "approve_comment": batch_data.message,
            }
        elif batch_data.action == "reject":
            extra_fields = {
                "rejected_at": now,
                "rejected_by": actor["id"],
                "reject_reason": batch_data.message or "批量退回",
            }
        else:
            extra_fields = {
                "urged_at": now,
                "urged_by": actor["id"],
                "urged_message": batch_data.message or "请尽快完成整改",
            }

        try:
            _transition_defect_sync(
                defect_id=defect_id,
                action=batch_data.action,
                actor=actor,
                extra_fields=extra_fields,
                history_action=f"batch_{batch_data.action}",
                history_details={"message": batch_data.message, "batch": True},
            )
            results.append(
                {
                    "defect_id": defect_id,
                    "success": True,
                    "new_status": new_status,
                }
            )
        except HTTPException as exc:
            results.append(
                {
                    "defect_id": defect_id,
                    "success": False,
                    "error": str(exc.detail),
                }
            )
        except Exception:
            logger.error("batch_defect_action_failed defect_id=%s", defect_id, exc_info=True)
            results.append(
                {
                    "defect_id": defect_id,
                    "success": False,
                    "error": "批量操作执行失败",
                }
            )

    success_count = sum(1 for r in results if r["success"])

    return success_response(
        data={
            "results": results,
            "total": len(batch_data.defect_ids),
            "success_count": success_count,
            "fail_count": len(batch_data.defect_ids) - success_count,
        },
        message=f"批量{batch_data.action}完成：{success_count}/{len(batch_data.defect_ids)} 成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 导出
# ============================

@router.get("/export")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.EXPORT)
async def export_defects(
    request: Request,
    format: str = Query("xlsx", description="导出格式: xlsx | csv"),
    max_rows: int = Query(10000, ge=1, le=10000, description="最大导出行数"),
    record_id: Optional[str] = Query(None, description="病历ID"),
    department: Optional[str] = Query(None, description="科室"),
    severity: Optional[str] = Query(None, description="严重程度"),
    category: Optional[str] = Query(None, description="缺陷分类"),
    status: Optional[str] = Query(None, description="缺陷状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user),
):
    """导出缺陷列表为 Excel 或 CSV 文件（强制排除人工缺陷并按院区隔离，仅限管理员/质控主管）"""
    from ..services.defect_export_service import DefectExportService

    actor = _resolve_actor(
        current_user,
        allowed_roles=_EXPORT_ROLES,
        denied_detail="仅质控管理员或系统管理员可导出缺陷列表",
    )

    if format not in {"xlsx", "csv"}:
        raise HTTPException(status_code=400, detail="导出格式仅支持 xlsx 或 csv")

    filters = {
        k: v
        for k, v in {
            "record_id": record_id,
            "department": department,
            "severity": severity,
            "category": category,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        }.items()
        if v is not None
    }

    try:
        defects, _ = _query_defects_sync(
            actor=actor,
            record_id=record_id,
            department=department,
            severity=severity,
            category=category,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=max_rows,
            offset=0,
            with_count=False,
        )

        export_service = DefectExportService()
        translated_rows = [export_service._translate_row(d) for d in defects]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "downloads",
        )
        os.makedirs(export_dir, exist_ok=True)
        if format == "csv":
            result = await export_service._export_csv(translated_rows, export_dir, timestamp)
        else:
            result = await export_service._export_xlsx(translated_rows, export_dir, timestamp)

        audit_event(
            request,
            action="defects.export",
            resource="/api/v1/qc/defects/export",
            outcome="success",
            current_user=current_user,
            details={
                "format": format,
                "max_rows": max_rows,
                "filters": filters,
                "institute_scope": actor["institute_id"],
                "total_rows": int(result.get("total_rows") or 0),
                "file_name": result.get("file_name"),
            },
        )

        return FileResponse(
            path=result["file_path"],
            filename=result["file_name"],
            media_type=result["media_type"],
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"导出缺陷列表失败: {e}")
        raise HTTPException(status_code=500, detail="导出缺陷列表失败")


# ============================
# 统计
# ============================

@router.get("/stats")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_defect_stats(
    request: Request,
    record_id: Optional[str] = Query(None, description="病历ID"),
    department: Optional[str] = Query(None, description="科室"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user),
):
    """获取缺陷统计数据（强制排除现代人工缺陷并按院区隔离）"""
    actor = _resolve_actor(current_user, allowed_roles=_READ_ROLES, denied_detail="无权查看缺陷统计")

    try:
        all_defects, _ = _query_defects_sync(
            actor=actor,
            record_id=record_id,
            department=department,
            start_date=start_date,
            end_date=end_date,
            select_columns="severity, category, status",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询缺陷统计失败: {e}")
        raise HTTPException(status_code=500, detail="查询缺陷统计失败")

    severity_stats: Dict[str, int] = {}
    category_stats: Dict[str, int] = {}
    status_stats: Dict[str, int] = {}
    for d in all_defects:
        sev = d.get("severity") or "unknown"
        severity_stats[sev] = severity_stats.get(sev, 0) + 1
        cat = d.get("category") or "other"
        category_stats[cat] = category_stats.get(cat, 0) + 1
        st = d.get("status") or "unknown"
        status_stats[st] = status_stats.get(st, 0) + 1

    return success_response(
        data={
            "total": len(all_defects),
            "by_severity": severity_stats,
            "by_category": category_stats,
            "by_status": status_stats,
        },
        message="获取缺陷统计成功",
        trace_id=get_trace_id(request),
    )
