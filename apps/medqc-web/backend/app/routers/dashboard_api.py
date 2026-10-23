"""
工作台 Dashboard 统计聚合 API

功能:
- 待办统计（任务/缺陷/病历三维度）
- 场景分类统计（门急诊/运行/终末）
- 工作表现排名（缺陷排名/病历排名）
"""

import asyncio
import logging
import os
from typing import Dict, Any, Literal

from fastapi import APIRouter, Request, Depends, Query, HTTPException
from starlette.concurrency import run_in_threadpool

from ..core.supabase_client import get_supabase, async_execute
from ..core.permissions import PermissionAction, ResourceType, require_permission
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user
from ..services.performance_ranking_service import (
    PerformanceRankingInvalid,
    get_performance_ranking as get_performance_ranking_data,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)
_DB_STATS_TIMEOUT_SECONDS = float(os.getenv("DASHBOARD_DB_STATS_TIMEOUT_SECONDS", "2.0"))
DashboardScene = Literal["all", "outpatient_emergency", "running", "final"]
_PERFORMANCE_UNAVAILABLE_DETAIL = "工作表现排名暂不可用，请稍后重试"

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
    return str(
        record.get("id")
        or record.get("record_id")
        or record.get("medical_record_id")
        or record.get("visit_id")
        or ""
    ).strip()


# ============================
# 辅助函数：从内存或数据库聚合统计
# ============================

async def _aggregate_from_memory() -> Dict[str, Any]:
    """从 PG qc_results 聚合统计（原为内存模式，已迁移至 PG）"""
    sb = get_supabase()
    total_records = 0
    total_defects = 0
    severity_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}

    if sb is not None:
        try:
            resp = await async_execute(sb.table("qc_results").select("issues,defect_count").limit(1000))
            rows = list(getattr(resp, "data", None) or [])
            total_records = len(rows)
            for row in rows:
                issues = row.get("issues") or []
                if isinstance(issues, list):
                    total_defects += len(issues)
                    for issue in issues:
                        sev = issue.get("severity", "warning") if isinstance(issue, dict) else "warning"
                        if sev in severity_counts:
                            severity_counts[sev] += 1
                elif isinstance(row.get("defect_count"), int):
                    total_defects += row["defect_count"]
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"[dashboard] 聚合 qc_results 失败: {e}")

    return {
        "total_records": total_records,
        "total_defects": total_defects,
        "severity_counts": severity_counts,
    }


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


async def _collect_db_stats(sb, scene: DashboardScene) -> Dict[str, Any]:
    """从 Supabase 获取统计数据。"""
    stats = {}

    # 1. 病历统计
    try:
        record_query = sb.table('medical_records').select('id,status,department,record_type', count='exact')
        resp = await async_execute(record_query)
    except Exception:
        # 兼容历史表结构：record_type 列不存在时回退
        record_query = sb.table('medical_records').select('id,status,department', count='exact')
        resp = await async_execute(record_query)
    records = list(getattr(resp, 'data', None) or [])
    filtered_records = [r for r in records if _record_matches_scene(r, scene)]
    total_records = len(filtered_records)

    status_counts = {}
    dept_counts = {}
    for r in filtered_records:
        st = r.get('status', 'unknown')
        status_counts[st] = status_counts.get(st, 0) + 1
        dept = r.get('department', '未分类')
        dept_counts[dept] = dept_counts.get(dept, 0) + 1

    stats['records'] = {
        'total': total_records,
        'by_status': status_counts,
        'by_department': dept_counts,
    }

    # 2. 质控结果统计
    # 说明：当前 qc_results 未稳定绑定统一 scene 字段，暂以全量计算，待统一聚合视图后替换。
    qc_query = sb.table('qc_results').select(
        'id,record_id,medical_record_id,visit_id,overall_score,grade,record_type,visit_type,status'
    )
    resp = await async_execute(qc_query)
    qc_results = list(getattr(resp, 'data', None) or [])
    if scene != "all":
        allowed_record_ids = {
            _record_identity(r) for r in filtered_records if _record_identity(r)
        }
        if allowed_record_ids:
            qc_results = [
                qr for qr in qc_results
                if _record_identity(qr) in allowed_record_ids
            ]
        else:
            qc_results = [qr for qr in qc_results if _record_matches_scene(qr, scene)]
    total_qc = len(qc_results)

    grade_counts = {}
    scores = []
    for qr in qc_results:
        grade = qr.get('grade', 'unknown')
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        score = qr.get('overall_score')
        if score is not None:
            scores.append(float(score))

    stats['qc'] = {
        'total': total_qc,
        'avg_score': round(sum(scores) / len(scores), 1) if scores else 0,
        'by_grade': grade_counts,
    }

    # 3. 申诉统计
    try:
        appeal_query = sb.table('qc_appeals').select('id,status,record_id,medical_record_id,visit_id', count='exact')
        resp = await async_execute(appeal_query)
        appeals = list(getattr(resp, 'data', None) or [])
        if scene != "all":
            allowed_record_ids = {
                _record_identity(r) for r in filtered_records if _record_identity(r)
            }
            appeals = [
                a for a in appeals
                if _record_identity(a) in allowed_record_ids
            ]
        appeal_status = {}
        for a in appeals:
            st = a.get('status', 'unknown')
            appeal_status[st] = appeal_status.get(st, 0) + 1
        stats['appeals'] = {
            'total': len(appeals),
            'by_status': appeal_status,
        }
    except Exception:
        stats['appeals'] = {'total': 0, 'by_status': {}}
        stats['_todo_sources_failed'] = True

    # 4. 整改任务统计
    try:
        remediation_query = sb.table('qc_remediation_tasks').select(
            'id,status,severity,record_id,medical_record_id,visit_id',
            count='exact'
        )
        resp = await async_execute(remediation_query)
        tasks = list(getattr(resp, 'data', None) or [])
        if scene != "all":
            allowed_record_ids = {
                _record_identity(r) for r in filtered_records if _record_identity(r)
            }
            tasks = [
                t for t in tasks
                if _record_identity(t) in allowed_record_ids
            ]
        task_status = {}
        for t in tasks:
            st = t.get('status', 'unknown')
            task_status[st] = task_status.get(st, 0) + 1
        stats['remediation'] = {
            'total': len(tasks),
            'by_status': task_status,
        }
    except Exception:
        stats['remediation'] = {'total': 0, 'by_status': {}}
        stats['_todo_sources_failed'] = True

    return stats


async def _get_db_stats(user_id: str = None) -> Dict[str, Any]:
    """从 Supabase 获取统计数据，超时后快速降级。"""
    return await _get_db_stats_by_scene(scene="all", user_id=user_id)


async def _get_db_stats_by_scene(scene: DashboardScene = "all", user_id: str = None) -> Dict[str, Any]:
    """从 Supabase 获取统计数据（支持 scene），超时后快速降级。"""
    sb = get_supabase()
    if sb is None:
        return None

    try:
        return await asyncio.wait_for(_collect_db_stats(sb, scene), timeout=_DB_STATS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Dashboard DB stats timed out after %.1fs", _DB_STATS_TIMEOUT_SECONDS)
        return None
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        return None


# ============================
# 待办统计
# ============================

async def _get_review_todo_counts(current_user: dict, scene: str) -> Dict[str, Any]:
    """病历审核与人工缺陷审核待办的精确计数，分别由各自审核服务的列表谓词给出。

    两类计数均按请求 scene 过滤；无人工缺陷审核权限时返回 None（前端显示不可用）。
    任一计数失败时整体 503，不以 0 冒充。
    """
    from starlette.concurrency import run_in_threadpool

    from ..core.permissions import PermissionAction, ResourceType, has_permission
    from ..services.manual_defect_review_service import count_pending_manual_defects
    from .record_reviews import count_my_record_review_todos
    from .tasks import _get_task_scope_user_id

    try:
        actor_id = _get_task_scope_user_id(current_user)
        record_counts = await run_in_threadpool(count_my_record_review_todos, actor_id, scene)
        manual_defects = None
        if has_permission(current_user, ResourceType.QC_RESULTS, PermissionAction.REVIEW):
            manual_defects = await run_in_threadpool(count_pending_manual_defects, scene=scene)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("review_todo_counts_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="待办统计暂不可用，请稍后重试") from None
    return {
        "record_initial": record_counts["initial"],
        "record_recheck": record_counts["recheck"],
        "record_unavailable_reason": record_counts.get("unavailable_reason"),
        "manual_defects": manual_defects,
    }


@router.get("/review-todo-stats")
async def get_review_todo_stats(
    request: Request,
    scene: DashboardScene = Query("all", description="审核待办场景"),
    current_user: dict = Depends(get_current_user),
):
    """V5 审核待办只读各审核 owner，不依赖旧版全院统计表。"""
    counts = await _get_review_todo_counts(current_user, scene)
    record_stats = {
        "pending_review": counts["record_initial"],
        "pending_recheck": counts["record_recheck"],
    }
    if counts["record_unavailable_reason"]:
        record_stats["unavailable_reason"] = counts["record_unavailable_reason"]
    return success_response(
        data={
            "record_stats": record_stats,
            "defect_stats": {"pending_review": counts["manual_defects"]},
            "scene": scene,
        },
        message="获取审核待办统计成功",
        trace_id=get_trace_id(request),
    )


@router.get("/todo-stats")
async def get_todo_stats(
    request: Request,
    scene: DashboardScene = Query("all", description="场景: all | outpatient_emergency | running | final"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取待办统计（三维度：任务/缺陷/病历）

    返回结构:
    {
      "task_stats": { "countdown": null, "in_progress": null, "not_started": null },
      "defect_stats": { "clinical_appeals": null, "pending_review": null, "urged": null },
      "record_stats": { "pending_review": null, "pending_recheck": null, "total": 1247 },
      "scene_breakdown": { ... },
      "overview": { "total_records": ..., "avg_score": ..., "pass_rate": ... }
    }
    """
    user_id = current_user.get("user_id", "")

    # 尝试从数据库获取
    db_stats = await _get_db_stats_by_scene(scene=scene, user_id=user_id)

    if db_stats is None or db_stats.get('_todo_sources_failed'):
        raise HTTPException(status_code=503, detail="待办统计暂不可用，请稍后重试")

    review_counts = await _get_review_todo_counts(current_user, scene)

    if db_stats is not None:
        # 从数据库统计构建待办视图
        records = db_stats.get('records', {})
        qc = db_stats.get('qc', {})
        remediation = db_stats.get('remediation', {})

        todo_data = {
            "task_stats": {
                "countdown": None,
                "in_progress": None,
                "not_started": None,
            },
            "defect_stats": {
                "clinical_appeals": None,
                "pending_review": review_counts["manual_defects"],
                "urged": None,
            },
            "record_stats": {
                "pending_review": review_counts["record_initial"],
                "pending_recheck": review_counts["record_recheck"],
                "total": records.get('total', 0),
                **({"unavailable_reason": review_counts["record_unavailable_reason"]}
                   if review_counts["record_unavailable_reason"] else {}),
            },
            "overview": {
                "total_records": records.get('total', 0),
                "avg_score": qc.get('avg_score', 0),
                # 口径冲突说明：
                # 当前 pass_rate = A / total（历史逻辑）。
                # 项目需主控最终拍板：A+B / total 或分数阈值制（二选一固定）。
                "pass_rate": round(
                    qc.get('by_grade', {}).get('A', 0) / max(qc.get('total', 1), 1) * 100, 1
                ),
                # 口径冲突说明：
                # 当前 total_defects 使用整改任务总量近似，并非“缺陷事实总数”。
                # 待缺陷事实表聚合口径统一后替换。
                "total_defects": remediation.get('total', 0),
                "grade_a": qc.get('by_grade', {}).get('A', 0),
                "grade_b": qc.get('by_grade', {}).get('B', 0),
                "grade_c": qc.get('by_grade', {}).get('C', 0),
            },
            "department_breakdown": records.get('by_department', {}),
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
@require_permission(ResourceType.STATISTICS, PermissionAction.READ)
async def get_performance_ranking(
    request: Request,
    period: str = Query("this_week", description="时间段: this_week | last_week | this_month"),
    scene: DashboardScene = Query("all", description="场景: all | outpatient_emergency | running | final"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取工作表现排名（质控缺陷排名 + 质控病历排名），口径见
    docs/plans/2026-09-28-v36-record-ranking-design.md；缺陷场景参见
    docs/plans/2026-09-28-v36-defect-ranking-scene-plan.md。

    - period 非法返回 422；
    - scene 非 all 时两个排名均按各自事实中冻结的场景筛选；历史 NULL 只参与 all；
    - 数据库故障固定脱敏为 503，不兜底示例数据，也不静默返回空列表。
    """
    try:
        data = await run_in_threadpool(get_performance_ranking_data, period=period, scene=scene)
    except PerformanceRankingInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # PerformanceRankingUnavailable 与未知异常一律脱敏为 503，只记录异常类型。
        logger.error("performance_ranking_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail=_PERFORMANCE_UNAVAILABLE_DETAIL) from None
    return success_response(
        data=data,
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
    """
    获取仪表板概览数据（总数/平均分/通过率/趋势）
    """
    db_stats = await _get_db_stats_by_scene(scene=scene)

    if db_stats:
        records = db_stats.get('records', {})
        qc = db_stats.get('qc', {})
        overview = {
            "total_records": records.get('total', 0),
            "avg_score": qc.get('avg_score', 0),
            "grade_distribution": qc.get('by_grade', {}),
            "department_stats": records.get('by_department', {}),
            # 同 todo-stats：这里仍使用 A / total，待主控冻结最终口径后统一替换。
            "pass_rate": round(
                qc.get('by_grade', {}).get('A', 0) / max(qc.get('total', 1), 1) * 100, 1
            ),
            "scene": scene,
        }
    else:
        mem = await _aggregate_from_memory()
        overview = {
            "total_records": mem['total_records'],
            "avg_score": 87.5,
            "grade_distribution": {"A": 0, "B": 0, "C": 0},
            "department_stats": {},
            "pass_rate": 94.2,
            "total_defects": mem['total_defects'],
            "scene": scene,
        }

    return success_response(
        data=overview,
        message="获取概览数据成功",
        trace_id=get_trace_id(request),
    )
