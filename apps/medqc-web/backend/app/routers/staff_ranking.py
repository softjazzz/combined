"""
质控员工作量排名 API（PG 版）

功能:
- 人均质控病历数排名
- 复审病历数排名
- 人工发现缺陷数排名
- 综合工作量统计

数据源：PostgreSQL v_qc_coder_ranking 视图
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, text

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..core.supabase_client import async_execute, get_supabase
from ..database import connection as db_connection
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/staff-ranking", tags=["staff-ranking"])
logger = logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_RANKING_READ_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})


def _get_period_start(period: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """返回统计周期起点，时分秒微秒统一归零至当日 00:00:00。"""
    base = (now or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "this_week":
        return base - timedelta(days=base.weekday())
    if period == "this_month":
        return base.replace(day=1)
    if period == "this_quarter":
        quarter_start_month = ((base.month - 1) // 3) * 3 + 1
        return base.replace(month=quarter_start_month, day=1)
    return None


def _resolve_ranking_actor(
    current_user: Dict[str, Any],
    *,
    allowed_roles: Iterable[str] = _RANKING_READ_ROLES,
    denied_detail: str = "当前角色无权查看质控员工作量排名",
) -> Dict[str, Any]:
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id or actor_id == "anonymous":
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
        logger.error("staff_ranking_actor_lookup_failed", exc_info=True)
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
        "roles": roles,
        "is_global": is_global,
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
            owner_schema = resolve_user_owner_schema(session)
            inspector = sa_inspect(session.connection())
            if not inspector.has_table("sys_users", schema=owner_schema):
                return {}
            cols = {col["name"] for col in inspector.get_columns("sys_users", schema=owner_schema)}
            if "institute_id" not in cols:
                return {}
            table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
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
        logger.warning("staff_ranking_user_institute_lookup_failed", exc_info=True)
        return {}


def _filter_rankings_by_actor_institute(
    rows: List[Dict[str, Any]],
    actor: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if actor["is_global"]:
        return rows

    target_inst = actor["institute_id"]
    need_lookup_ids = [
        str(r.get("user_id") or r.get("coder_id") or "").strip()
        for r in rows
        if "institute_id" not in r or r.get("institute_id") is None
    ]
    user_inst_map = _lookup_user_institutes(need_lookup_ids)

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if "institute_id" in row and row.get("institute_id") is not None:
            row_inst = row.get("institute_id")
            if isinstance(row_inst, str) and row_inst.strip() == target_inst:
                filtered.append(row)
            continue
        uid = str(row.get("user_id") or row.get("coder_id") or "").strip()
        if uid and user_inst_map.get(uid) == target_inst:
            filtered.append(row)
    return filtered


@router.get("")
async def get_staff_ranking(
    request: Request,
    period: str = Query("this_month", description="统计周期: this_week/this_month/this_quarter"),
    sort_by: str = Query("qc_count", description="排序字段: qc_count/recheck_count/defect_found/pass_rate"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取质控员工作量排名

    返回每个质控员的:
    - qc_count: 质控病历数
    - recheck_count: 复审病历数
    - defect_found: 发现缺陷数
    - pass_rate: 通过率
    - avg_daily: 日均质控量
    """
    actor = _resolve_ranking_actor(current_user)

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        period_start = _get_period_start(period)
        rows: List[Dict[str, Any]] = []
        period_filter_field = None

        if period_start is not None:
            # 兼容不同视图字段命名；若缺失时间列则回退到全量并显式返回标记。
            for candidate in ("stat_date", "created_at", "updated_at", "date"):
                try:
                    resp = await async_execute(
                        sb.table("v_qc_coder_ranking").select("*").gte(candidate, period_start.isoformat())
                    )
                    rows = list(getattr(resp, "data", None) or [])
                    period_filter_field = candidate
                    break
                except Exception:
                    continue

        if period_filter_field is None:
            resp = await async_execute(sb.table("v_qc_coder_ranking").select("*"))
            rows = list(getattr(resp, "data", None) or [])

        rows = _filter_rankings_by_actor_institute(rows, actor)

        # 合法排序字段
        valid_sort = {"qc_count", "recheck_count", "defect_found", "pass_rate", "avg_daily"}
        sort_key = sort_by if sort_by in valid_sort else "qc_count"

        rankings = sorted(rows, key=lambda r: float(r.get(sort_key, 0) or 0), reverse=True)

        summary = {
            "total_qc": sum(int(r.get("qc_count", 0) or 0) for r in rankings),
            "total_recheck": sum(int(r.get("recheck_count", 0) or 0) for r in rankings),
            "total_defects": sum(int(r.get("defect_found", 0) or 0) for r in rankings),
            "avg_pass_rate": round(
                sum(float(r.get("pass_rate", 0) or 0) for r in rankings) / max(len(rankings), 1), 1
            ),
            "staff_count": len(rankings),
        }

        return success_response(
            data={
                "rankings": rankings,
                "summary": summary,
                "period": period,
                "sort_by": sort_by,
                "period_filter_field": period_filter_field,
            },
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("获取工作量排名失败", exc_info=True)
        # 视图不存在或查询异常时返回安全空态，不向客户端泄露内部异常细节。
        return success_response(
            data={
                "rankings": [],
                "summary": {
                    "total_qc": 0,
                    "total_recheck": 0,
                    "total_defects": 0,
                    "avg_pass_rate": 0,
                    "staff_count": 0,
                },
                "period": period,
                "sort_by": sort_by,
                "period_filter_field": None,
            },
            message="暂无排名数据",
            trace_id=get_trace_id(request),
        )
