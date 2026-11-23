"""
工作台 Dashboard 统计聚合 API

功能:
- 待办统计（任务/缺陷/病历三维度）
- 场景分类统计（门急诊/运行/终末）
- 工作表现排名（缺陷排名/病历排名）
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Literal, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect as sa_inspect, text

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..core.supabase_client import async_execute, get_supabase
from ..database import connection as db_connection
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    configured_search_path,
    resolve_user_owner_schema,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)
_DB_STATS_TIMEOUT_SECONDS = float(os.getenv("DASHBOARD_DB_STATS_TIMEOUT_SECONDS", "2.0"))
DashboardScene = Literal["all", "outpatient_emergency", "running", "final"]

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_DASHBOARD_READ_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})

OUTPATIENT_EMERGENCY_TYPES = {
    "outpatient",
    "emergency",
    "outpatient_emergency",
    "门诊",
    "急诊",
    "门急诊",
}
RUNNING_STATUSES = {"running", "in_progress", "pending", "pending_review", "processing", "在院"}
FINAL_STATUSES = {"final", "completed", "discharged", "archived", "已出院", "终末"}


def _record_identity(record: Dict[str, Any]) -> str:
    """提取病历关联标识。

    优先读取外键 `record_id` / `medical_record_id` / `visit_id`，
    最后回退到主表 `id`，避免子表（qc_results / qc_appeals / qc_remediation_tasks）
    误用自身主键 `id` 导致按病历过滤全部归零。
    """
    return str(
        record.get("record_id")
        or record.get("medical_record_id")
        or record.get("visit_id")
        or record.get("id")
        or ""
    ).strip()


def _safe_lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _record_matches_scene(record: Dict[str, Any], scene: DashboardScene) -> bool:
    if scene == "all":
        return True

    record_type = _safe_lower(record.get("record_type") or record.get("visit_type"))
    status = _safe_lower(record.get("status"))

    if scene == "outpatient_emergency":
        # 仅在明确识别为门急诊时归入本场景，避免与住院场景重叠。
        return bool(record_type) and record_type in OUTPATIENT_EMERGENCY_TYPES

    if scene == "running":
        if record_type in OUTPATIENT_EMERGENCY_TYPES:
            return False
        if not status:
            return False
        return status in RUNNING_STATUSES

    if scene == "final":
        if record_type in OUTPATIENT_EMERGENCY_TYPES:
            return False
        if not status:
            return False
        return status in FINAL_STATUSES

    return True


def _resolve_table_ref(session, table_name: str) -> Optional[Tuple[str, Set[str]]]:
    bind = session.get_bind()
    inspector = sa_inspect(bind)
    if bind.dialect.name != "postgresql":
        if not inspector.has_table(table_name):
            return None
        cols = {col["name"] for col in inspector.get_columns(table_name)}
        return f'"{table_name}"', cols

    schemas = list(dict.fromkeys([*configured_search_path(), "cdm", "qc", "public", "sys"]))
    for schema in schemas:
        if inspector.has_table(table_name, schema=schema):
            cols = {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
            return f'"{schema}"."{table_name}"', cols
    return None


def _table_has_column(table_name: str, column_name: str) -> bool:
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return False
    try:
        with session_factory() as session:
            resolved = _resolve_table_ref(session, table_name)
            return resolved is not None and column_name in resolved[1]
    except Exception:
        return False


def _resolve_dashboard_actor(
    current_user: Dict[str, Any],
    *,
    allowed_roles: Iterable[str] = _DASHBOARD_READ_ROLES,
    denied_detail: str = "当前角色无权查看工作台统计数据",
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
        logger.error("dashboard_actor_lookup_failed", exc_info=True)
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


def _load_institute_record_ids(institute_id: str) -> Set[str]:
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return set()

    allowed: Set[str] = set()
    try:
        with session_factory() as session:
            table_specs = (
                ("medical_records", ("id", "record_id", "visit_id")),
                ("medical_record_frontpages", ("visit_id", "record_id")),
                ("medical_documents", ("record_id",)),
            )
            for table_name, id_cols in table_specs:
                resolved = _resolve_table_ref(session, table_name)
                if resolved is None:
                    continue
                table_ref, cols = resolved
                if "institute_id" not in cols:
                    continue
                present_ids = [col for col in id_cols if col in cols]
                if not present_ids:
                    continue
                select_sql = ", ".join(f'"{col}"' for col in present_ids)
                rows = (
                    session.execute(
                        text(f"SELECT {select_sql} FROM {table_ref} WHERE institute_id = :inst"),
                        {"inst": institute_id},
                    )
                    .mappings()
                    .all()
                )
                for row in rows:
                    for col in present_ids:
                        val = str(row.get(col) or "").strip()
                        if val:
                            allowed.add(val)
    except Exception:
        logger.warning("dashboard_institute_record_lookup_failed", exc_info=True)
        return set()
    return allowed


def _load_institute_user_identities(institute_id: str) -> Set[str]:
    """查询归属指定院区的用户 id / username / display_name，用于质控员维度院区过滤。"""
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return set()
    identities: Set[str] = set()
    try:
        with session_factory() as session:
            owner_schema = resolve_user_owner_schema(session)
            inspector = sa_inspect(session.connection())
            if not inspector.has_table("sys_users", schema=owner_schema):
                return set()
            cols = {col["name"] for col in inspector.get_columns("sys_users", schema=owner_schema)}
            if "institute_id" not in cols:
                return set()
            table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
            select_cols = [col for col in ("id", "username", "display_name") if col in cols]
            if not select_cols:
                return set()
            rows = (
                session.execute(
                    text(
                        f"SELECT {', '.join(select_cols)} FROM {table_ref} WHERE institute_id = :inst"
                    ),
                    {"inst": institute_id},
                )
                .mappings()
                .all()
            )
            for row in rows:
                for col in select_cols:
                    val = str(row.get(col) or "").strip()
                    if val:
                        identities.add(val)
    except Exception:
        logger.warning("dashboard_institute_user_lookup_failed", exc_info=True)
        return set()
    return identities


def _filter_rows_by_institute(
    rows: List[Dict[str, Any]],
    institute_id: Optional[str],
    *,
    allowed_record_ids: Optional[Set[str]] = None,
    allowed_user_identities: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if institute_id is None:
        return rows
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if "institute_id" in row and row.get("institute_id") is not None:
            row_inst = row.get("institute_id")
            if isinstance(row_inst, str) and row_inst.strip() == institute_id:
                filtered.append(row)
            continue
        rid = _record_identity(row)
        if rid and allowed_record_ids is not None and rid in allowed_record_ids:
            filtered.append(row)
            continue
        if allowed_user_identities is not None:
            actor_key = str(row.get("analyzed_by") or row.get("created_by") or "").strip()
            if actor_key and actor_key in allowed_user_identities:
                filtered.append(row)
    return filtered


def _extract_defect_count(row: Dict[str, Any]) -> int:
    raw_count = row.get("defect_count")
    if raw_count is not None and not isinstance(raw_count, bool):
        try:
            return max(0, int(raw_count))
        except (TypeError, ValueError):
            pass
    issues = row.get("issues")
    if isinstance(issues, list):
        return len(issues)
    return 0


def _resolve_performance_period(
    period: str,
    now: Optional[datetime] = None,
) -> Tuple[datetime, Optional[datetime], str]:
    """计算绩效统计时间窗口（起点归零至当日 00:00:00，上周带精确上界）。"""
    today_start = (now or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    this_week_start = today_start - timedelta(days=today_start.weekday())
    if period == "this_week":
        return this_week_start, None, "本周"
    if period == "last_week":
        return this_week_start - timedelta(days=7), this_week_start, "上周"
    if period == "this_month":
        return today_start.replace(day=1), None, "本月"
    return today_start - timedelta(days=7), None, "最近7天"


def _row_within_period(row: Dict[str, Any], start: datetime, end: Optional[datetime]) -> bool:
    raw_created = row.get("created_at")
    if raw_created is None:
        return True
    parsed: Optional[datetime] = None
    if isinstance(raw_created, datetime):
        parsed = raw_created
    elif isinstance(raw_created, str) and raw_created.strip():
        try:
            parsed = datetime.fromisoformat(raw_created.strip().replace("Z", "+00:00"))
        except ValueError:
            return True
    if parsed is None:
        return True
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    if parsed < start:
        return False
    if end is not None and parsed >= end:
        return False
    return True


async def _query_with_column_fallbacks(
    sb,
    table_name: str,
    select_candidates: Iterable[str],
    *,
    institute_id: Optional[str] = None,
    gte_filter: Optional[Tuple[str, str]] = None,
    lt_filter: Optional[Tuple[str, str]] = None,
    count: Optional[str] = None,
) -> List[Dict[str, Any]]:
    last_error: Optional[Exception] = None
    push_inst = institute_id is not None and _table_has_column(table_name, "institute_id")
    for cols in select_candidates:
        try:
            if count:
                query = sb.table(table_name).select(cols, count=count)
            else:
                query = sb.table(table_name).select(cols)
            if push_inst:
                query = query.eq("institute_id", institute_id)
            if gte_filter is not None:
                query = query.gte(gte_filter[0], gte_filter[1])
            if lt_filter is not None:
                query = query.lt(lt_filter[0], lt_filter[1])
            resp = await async_execute(query)
            return list(getattr(resp, "data", None) or [])
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return []


async def _collect_db_stats(
    sb,
    scene: DashboardScene,
    *,
    institute_id: Optional[str] = None,
) -> Dict[str, Any]:
    """从数据库获取真实统计数据（支持 scene 与持久院区隔离）。"""
    stats: Dict[str, Any] = {}
    allowed_inst_record_ids: Optional[Set[str]] = (
        _load_institute_record_ids(institute_id) if institute_id is not None else None
    )

    # 1. 病历统计
    records = await _query_with_column_fallbacks(
        sb,
        "medical_records",
        (
            "id,status,department,record_type,institute_id",
            "id,status,department,record_type",
            "id,status,department",
        ),
        institute_id=institute_id,
        count="exact",
    )
    records = _filter_rows_by_institute(
        records,
        institute_id,
        allowed_record_ids=allowed_inst_record_ids,
    )
    if institute_id is not None:
        inst_record_ids = set(allowed_inst_record_ids or set()) | {
            _record_identity(r) for r in records if _record_identity(r)
        }
    else:
        inst_record_ids = None

    filtered_records = [r for r in records if _record_matches_scene(r, scene)]
    total_records = len(filtered_records)
    allowed_scene_record_ids = {
        _record_identity(r) for r in filtered_records if _record_identity(r)
    }

    status_counts: Dict[str, int] = {}
    dept_counts: Dict[str, int] = {}
    for r in filtered_records:
        st = r.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
        dept = r.get("department", "未分类")
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    stats["records"] = {
        "total": total_records,
        "by_status": status_counts,
        "by_department": dept_counts,
    }

    # 2. 质控结果统计
    qc_results = await _query_with_column_fallbacks(
        sb,
        "qc_results",
        (
            "id,record_id,medical_record_id,visit_id,overall_score,grade,record_type,visit_type,status,institute_id",
            "id,record_id,medical_record_id,visit_id,overall_score,grade,record_type,visit_type,status",
            "id,record_id,overall_score,grade",
        ),
        institute_id=institute_id,
    )
    qc_results = _filter_rows_by_institute(
        qc_results,
        institute_id,
        allowed_record_ids=inst_record_ids,
    )
    if scene != "all":
        if records:
            qc_results = [
                qr for qr in qc_results if _record_identity(qr) in allowed_scene_record_ids
            ]
        else:
            qc_results = [qr for qr in qc_results if _record_matches_scene(qr, scene)]
    total_qc = len(qc_results)

    grade_counts: Dict[str, int] = {}
    scores: List[float] = []
    for qr in qc_results:
        grade = qr.get("grade", "unknown")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        score = qr.get("overall_score")
        if score is not None:
            scores.append(float(score))

    stats["qc"] = {
        "total": total_qc,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "by_grade": grade_counts,
    }

    # 3. 申诉统计
    try:
        appeals = await _query_with_column_fallbacks(
            sb,
            "qc_appeals",
            (
                "id,status,record_id,medical_record_id,visit_id,institute_id",
                "id,status,record_id,medical_record_id,visit_id",
                "id,status,record_id",
            ),
            institute_id=institute_id,
            count="exact",
        )
        appeals = _filter_rows_by_institute(
            appeals,
            institute_id,
            allowed_record_ids=inst_record_ids,
        )
        if scene != "all":
            appeals = [
                a for a in appeals if _record_identity(a) in allowed_scene_record_ids
            ]
        appeal_status: Dict[str, int] = {}
        for a in appeals:
            st = a.get("status", "unknown")
            appeal_status[st] = appeal_status.get(st, 0) + 1
        stats["appeals"] = {
            "total": len(appeals),
            "by_status": appeal_status,
        }
    except Exception:
        stats["appeals"] = {"total": 0, "by_status": {}}

    # 4. 整改任务统计
    try:
        tasks = await _query_with_column_fallbacks(
            sb,
            "qc_remediation_tasks",
            (
                "id,status,severity,record_id,medical_record_id,visit_id,institute_id",
                "id,status,severity,record_id,medical_record_id,visit_id",
                "id,status,severity,record_id",
            ),
            institute_id=institute_id,
            count="exact",
        )
        tasks = _filter_rows_by_institute(
            tasks,
            institute_id,
            allowed_record_ids=inst_record_ids,
        )
        if scene != "all":
            tasks = [
                t for t in tasks if _record_identity(t) in allowed_scene_record_ids
            ]
        task_status: Dict[str, int] = {}
        for t in tasks:
            st = t.get("status", "unknown")
            task_status[st] = task_status.get(st, 0) + 1
        stats["remediation"] = {
            "total": len(tasks),
            "by_status": task_status,
        }
    except Exception:
        stats["remediation"] = {"total": 0, "by_status": {}}

    return stats


async def _get_db_stats(
    user_id: Optional[str] = None,
    institute_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """从数据库获取统计数据，超时或不可用时返回 None（由调用方显式报错，不伪造数据）。"""
    return await _get_db_stats_by_scene(scene="all", user_id=user_id, institute_id=institute_id)


async def _get_db_stats_by_scene(
    scene: DashboardScene = "all",
    user_id: Optional[str] = None,
    institute_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """从数据库获取统计数据（支持 scene 与持久院区隔离），超时后返回 None。"""
    sb = get_supabase()
    if sb is None:
        return None

    try:
        return await asyncio.wait_for(
            _collect_db_stats(sb, scene, institute_id=institute_id),
            timeout=_DB_STATS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Dashboard DB stats timed out after %.1fs (user_id=%s, institute_id=%s)",
            _DB_STATS_TIMEOUT_SECONDS,
            user_id or "",
            institute_id or "*",
        )
        return None
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        return None


# ============================
# 待办统计
# ============================

@router.get("/todo-stats")
async def get_todo_stats(
    request: Request,
    scene: DashboardScene = Query("all", description="场景: all | outpatient_emergency | running | final"),
    current_user: dict = Depends(get_current_user),
):
    """获取待办统计（三维度：任务/缺陷/病历），严格校验角色与持久院区，不伪造回退 KPI。"""
    actor = _resolve_dashboard_actor(
        current_user,
        allowed_roles=_DASHBOARD_READ_ROLES,
        denied_detail="当前角色无权查看工作台待办统计",
    )

    db_stats = await _get_db_stats_by_scene(
        scene=scene,
        user_id=actor["id"],
        institute_id=actor["institute_id"],
    )
    if db_stats is None:
        raise HTTPException(status_code=503, detail="工作台统计数据源暂不可用")

    records = db_stats.get("records", {})
    qc = db_stats.get("qc", {})
    appeals = db_stats.get("appeals", {})
    remediation = db_stats.get("remediation", {})

    record_status = records.get("by_status", {})
    appeal_status = appeals.get("by_status", {})
    remediation_status = remediation.get("by_status", {})
    qc_total = int(qc.get("total", 0) or 0)
    grade_a = int(qc.get("by_grade", {}).get("A", 0) or 0)

    todo_data = {
        "task_stats": {
            "countdown": remediation_status.get("pending", 0) + remediation_status.get("overdue", 0),
            "in_progress": remediation_status.get("in_progress", 0),
            "not_started": record_status.get("pending", 0),
        },
        "defect_stats": {
            "clinical_appeals": appeal_status.get("pending", 0) + appeal_status.get("reviewing", 0),
            "pending_review": remediation_status.get("submitted", 0),
            "urged": remediation_status.get("pending", 0),
        },
        "record_stats": {
            "pending_review": record_status.get("pending_review", 0),
            "pending_recheck": record_status.get("pending_recheck", 0),
            "total": records.get("total", 0),
        },
        "overview": {
            "total_records": records.get("total", 0),
            "avg_score": qc.get("avg_score", 0.0),
            "pass_rate": round((grade_a / qc_total) * 100, 1) if qc_total > 0 else 0.0,
            "total_defects": remediation.get("total", 0),
            "grade_a": grade_a,
            "grade_b": qc.get("by_grade", {}).get("B", 0),
            "grade_c": qc.get("by_grade", {}).get("C", 0),
        },
        "department_breakdown": records.get("by_department", {}),
        "scene": scene,
    }

    return success_response(
        data=todo_data,
        message="获取待办统计成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 工作表现排名
# ============================

@router.get("/performance")
async def get_performance_ranking(
    request: Request,
    period: str = Query("this_week", description="时间段: this_week | last_week | this_month"),
    scene: DashboardScene = Query("all", description="场景: all | outpatient_emergency | running | final"),
    current_user: dict = Depends(get_current_user),
):
    """获取工作表现排名（真实缺陷数排名 + 病历审查数排名，无数据时返回空列表，不伪造假人名）。"""
    actor = _resolve_dashboard_actor(
        current_user,
        allowed_roles=_DASHBOARD_READ_ROLES,
        denied_detail="当前角色无权查看工作台表现排名",
    )

    start, end, label = _resolve_performance_period(period)

    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="工作台统计数据源暂不可用")

    institute_id = actor["institute_id"]
    allowed_inst_record_ids: Optional[Set[str]] = (
        _load_institute_record_ids(institute_id) if institute_id is not None else None
    )
    allowed_user_identities: Optional[Set[str]] = (
        _load_institute_user_identities(institute_id) if institute_id is not None else None
    )

    try:
        results = await _query_with_column_fallbacks(
            sb,
            "qc_results",
            (
                "analyzed_by,created_by,id,record_id,medical_record_id,visit_id,defect_count,issues,record_type,status,visit_type,created_at,institute_id",
                "analyzed_by,created_by,id,record_id,defect_count,issues,record_type,status,visit_type,created_at",
                "analyzed_by,id,record_id,defect_count,status,created_at",
                "created_by,id,record_id,defect_count,created_at",
            ),
            institute_id=institute_id,
            gte_filter=("created_at", start.isoformat()),
            lt_filter=("created_at", end.isoformat()) if end is not None else None,
        )
    except Exception as e:
        logger.warning(f"获取工作表现排名失败: {e}")
        raise HTTPException(status_code=503, detail="工作台表现排名数据源暂不可用") from None

    results = [r for r in results if _row_within_period(r, start, end)]
    results = _filter_rows_by_institute(
        results,
        institute_id,
        allowed_record_ids=allowed_inst_record_ids,
        allowed_user_identities=allowed_user_identities,
    )

    if scene != "all":
        try:
            records = await _query_with_column_fallbacks(
                sb,
                "medical_records",
                (
                    "id,status,record_type,institute_id",
                    "id,status,record_type",
                    "id,status",
                ),
                institute_id=institute_id,
            )
            records = _filter_rows_by_institute(
                records,
                institute_id,
                allowed_record_ids=allowed_inst_record_ids,
            )
        except Exception:
            records = []

        if records:
            allowed_scene_ids = {
                _record_identity(r) for r in records if _record_matches_scene(r, scene) and _record_identity(r)
            }
            results = [r for r in results if _record_identity(r) in allowed_scene_ids]
        else:
            results = [r for r in results if _record_matches_scene(r, scene)]

    user_defects: Dict[str, int] = {}
    user_records: Dict[str, int] = {}
    for r in results:
        user = str(r.get("analyzed_by") or r.get("created_by") or "").strip()
        if not user:
            continue
        user_records[user] = user_records.get(user, 0) + 1
        defect_count = _extract_defect_count(r)
        if defect_count > 0:
            user_defects[user] = user_defects.get(user, 0) + defect_count

    defect_ranking = sorted(
        [{"name": k, "count": v} for k, v in user_defects.items()],
        key=lambda x: (-x["count"], x["name"]),
    )[:10]
    for i, item in enumerate(defect_ranking):
        item["rank"] = i + 1

    record_ranking = sorted(
        [{"name": k, "count": v} for k, v in user_records.items()],
        key=lambda x: (-x["count"], x["name"]),
    )[:10]
    for i, item in enumerate(record_ranking):
        item["rank"] = i + 1

    return success_response(
        data={
            "defect_ranking": defect_ranking,
            "record_ranking": record_ranking,
            "period": period,
            "period_label": label,
            "scene": scene,
        },
        message="获取工作表现排名成功",
        trace_id=get_trace_id(request),
    )


# ============================
# 概览数据
# ============================

@router.get("/overview")
async def get_overview(
    request: Request,
    scene: DashboardScene = Query("all", description="场景: all | outpatient_emergency | running | final"),
    current_user: dict = Depends(get_current_user),
):
    """获取仪表板概览数据（总数/平均分/通过率），严格校验角色与持久院区，不伪造回退 KPI。"""
    actor = _resolve_dashboard_actor(
        current_user,
        allowed_roles=_DASHBOARD_READ_ROLES,
        denied_detail="当前角色无权查看工作台概览数据",
    )

    db_stats = await _get_db_stats_by_scene(
        scene=scene,
        user_id=actor["id"],
        institute_id=actor["institute_id"],
    )
    if db_stats is None:
        raise HTTPException(status_code=503, detail="工作台统计数据源暂不可用")

    records = db_stats.get("records", {})
    qc = db_stats.get("qc", {})
    qc_total = int(qc.get("total", 0) or 0)
    grade_a = int(qc.get("by_grade", {}).get("A", 0) or 0)

    overview = {
        "total_records": records.get("total", 0),
        "avg_score": qc.get("avg_score", 0.0),
        "grade_distribution": qc.get("by_grade", {}),
        "department_stats": records.get("by_department", {}),
        "pass_rate": round((grade_a / qc_total) * 100, 1) if qc_total > 0 else 0.0,
        "scene": scene,
    }

    return success_response(
        data=overview,
        message="获取概览数据成功",
        trace_id=get_trace_id(request),
    )
