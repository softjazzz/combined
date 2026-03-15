"""
缺陷操作管理路由

功能:
- 催办/撤回催办
- 标记已整改
- 审核通过/审核存疑
- 批量操作
- 导出缺陷列表 (Excel/CSV)
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import FileResponse

from ..schemas.defects import (
    DefectUrgeRequest,
    DefectCancelUrgeRequest,
    DefectMarkRemediatedRequest,
    DefectApproveRequest,
    DefectRejectRequest,
    DefectBatchActionRequest,
    DefectExportRequest,
    DefectStatus,
)
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode
from ..core.security import get_current_user
from ..core.permissions import (
    require_permission,
    require_role,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/qc/defects", tags=["defects"])
logger = logging.getLogger(__name__)


# ============================
# 辅助函数
# ============================

async def _get_defect(defect_id: str) -> Dict[str, Any]:
    """从数据库获取缺陷记录"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        resp = await async_execute(
            sb.table('qc_defects').select('*').eq('id', defect_id).single()
        )
        data = getattr(resp, 'data', None)
        if not data:
            raise HTTPException(status_code=404, detail=f"缺陷 {defect_id} 不存在")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缺陷失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取缺陷失败: {str(e)}")


async def _update_defect_status(defect_id: str, status: str, extra_fields: Dict = None) -> Dict:
    """更新缺陷状态"""
    update_data = {
        "id": defect_id,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }
    if extra_fields:
        update_data.update(extra_fields)

    sb = get_supabase()
    if sb is not None:
        try:
            resp = await async_execute(
                sb.table('qc_defects').update(update_data).eq('id', defect_id)
            )
            db_data = getattr(resp, 'data', None)
            if db_data:
                return db_data[0]
        except Exception as e:
            logger.error(f"更新缺陷状态失败: {e}")
            raise HTTPException(status_code=500, detail=f"更新缺陷状态失败: {str(e)}")

    raise HTTPException(status_code=503, detail="数据库不可用")


async def _record_defect_action(
    defect_id: str,
    action: str,
    actor_id: str,
    actor_name: str,
    details: Dict = None
):
    """记录缺陷操作历史"""
    sb = get_supabase()
    if sb is None:
        return

    history_record = {
        "id": str(uuid.uuid4()),
        "defect_id": defect_id,
        "action": action,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "details": details or {},
        "created_at": datetime.now().isoformat(),
    }

    try:
        await async_execute(
            sb.table('qc_defect_history').insert(history_record)
        )
    except Exception as e:
        logger.warning(f"记录缺陷操作历史失败（非阻塞）: {e}")


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
    """
    获取缺陷列表（支持多条件筛选和分页）
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        query = sb.table('qc_defects').select('*', count='exact')
        if record_id:
            query = query.eq('record_id', record_id)
        if department:
            query = query.eq('department', department)
        if severity:
            query = query.eq('severity', severity)
        if category:
            query = query.eq('category', category)
        if status:
            query = query.eq('status', status)
        if start_date:
            query = query.gte('created_at', start_date)
        if end_date:
            query = query.lte('created_at', end_date)
        if keyword:
            query = query.or_(
                f"rule_name.ilike.%{keyword}%,"
                f"description.ilike.%{keyword}%"
            )

        offset = (page - 1) * page_size
        query = query.order('created_at', desc=True).range(offset, offset + page_size - 1)

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        total = getattr(resp, 'count', None) or len(data)

        return paginated_response(
            items=data,
            total=total,
            page=page,
            page_size=page_size,
            message=f"获取缺陷列表成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        logger.error(f"查询缺陷列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


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
    """
    催办缺陷 — 向医生端推送催办消息
    """
    result = await _update_defect_status(
        defect_id,
        DefectStatus.URGED.value,
        extra_fields={
            "urged_at": datetime.now().isoformat(),
            "urged_by": current_user.get("user_id", ""),
            "urged_message": urge_data.message,
            "urged_deadline": urge_data.deadline,
        }
    )

    # 记录操作历史
    await _record_defect_action(
        defect_id=defect_id,
        action="urge",
        actor_id=current_user.get("user_id", ""),
        actor_name=current_user.get("display_name", ""),
        details={"message": urge_data.message, "deadline": urge_data.deadline},
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
    """
    撤回催办
    """
    result = await _update_defect_status(
        defect_id,
        DefectStatus.PENDING.value,
        extra_fields={
            "urged_at": None,
            "urged_by": None,
            "urged_message": None,
            "urged_deadline": None,
        }
    )

    await _record_defect_action(
        defect_id=defect_id,
        action="cancel_urge",
        actor_id=current_user.get("user_id", ""),
        actor_name=current_user.get("display_name", ""),
        details={"reason": cancel_data.reason},
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
    """
    标记缺陷已整改 — 人工核销缺陷
    """
    result = await _update_defect_status(
        defect_id,
        DefectStatus.REMEDIATED.value,
        extra_fields={
            "remediated_at": datetime.now().isoformat(),
            "remediated_by": current_user.get("user_id", ""),
            "remediation_note": remediation_data.remediation_note,
            "remediation_evidence": remediation_data.evidence,
        }
    )

    await _record_defect_action(
        defect_id=defect_id,
        action="mark_remediated",
        actor_id=current_user.get("user_id", ""),
        actor_name=current_user.get("display_name", ""),
        details={
            "remediation_note": remediation_data.remediation_note,
            "evidence_count": len(remediation_data.evidence),
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
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def approve_defect(
    request: Request,
    defect_id: str,
    approve_data: DefectApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    审核通过 — 确认缺陷已正确整改
    """
    result = await _update_defect_status(
        defect_id,
        DefectStatus.APPROVED.value,
        extra_fields={
            "approved_at": datetime.now().isoformat(),
            "approved_by": current_user.get("user_id", ""),
            "approve_comment": approve_data.comment,
        }
    )

    await _record_defect_action(
        defect_id=defect_id,
        action="approve",
        actor_id=current_user.get("user_id", ""),
        actor_name=current_user.get("display_name", ""),
        details={"comment": approve_data.comment},
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
@require_permission(ResourceType.QC_RESULTS, PermissionAction.UPDATE)
async def reject_defect(
    request: Request,
    defect_id: str,
    reject_data: DefectRejectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    审核存疑（退回）— 需要进一步修改
    """
    result = await _update_defect_status(
        defect_id,
        DefectStatus.REJECTED.value,
        extra_fields={
            "rejected_at": datetime.now().isoformat(),
            "rejected_by": current_user.get("user_id", ""),
            "reject_reason": reject_data.reason,
            "reject_suggestion": reject_data.suggestion,
        }
    )

    await _record_defect_action(
        defect_id=defect_id,
        action="reject",
        actor_id=current_user.get("user_id", ""),
        actor_name=current_user.get("display_name", ""),
        details={
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
    """
    批量操作缺陷（批量审核通过/退回/催办）
    """
    action_map = {
        "approve": DefectStatus.APPROVED.value,
        "reject": DefectStatus.REJECTED.value,
        "urge": DefectStatus.URGED.value,
    }

    if batch_data.action not in action_map:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的操作类型: {batch_data.action}，支持: {list(action_map.keys())}"
        )

    new_status = action_map[batch_data.action]
    results = []

    for defect_id in batch_data.defect_ids:
        try:
            await _update_defect_status(defect_id, new_status)
            await _record_defect_action(
                defect_id=defect_id,
                action=f"batch_{batch_data.action}",
                actor_id=current_user.get("user_id", ""),
                actor_name=current_user.get("display_name", ""),
                details={"message": batch_data.message, "batch": True},
            )
            results.append({
                "defect_id": defect_id,
                "success": True,
                "new_status": new_status,
            })
        except Exception as e:
            results.append({
                "defect_id": defect_id,
                "success": False,
                "error": str(e),
            })

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
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def export_defects(
    request: Request,
    format: str = Query("xlsx", description="导出格式: xlsx | csv"),
    max_rows: int = Query(10000, le=10000, description="最大导出行数"),
    record_id: Optional[str] = Query(None, description="病历ID"),
    department: Optional[str] = Query(None, description="科室"),
    severity: Optional[str] = Query(None, description="严重程度"),
    category: Optional[str] = Query(None, description="缺陷分类"),
    status: Optional[str] = Query(None, description="缺陷状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    current_user: dict = Depends(get_current_user),
):
    """
    导出缺陷列表为 Excel 或 CSV 文件（最多 1 万条）
    """
    from ..services.defect_export_service import DefectExportService

    export_service = DefectExportService()

    filters = {
        "record_id": record_id,
        "department": department,
        "severity": severity,
        "category": category,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
    }
    # 移除 None 值
    filters = {k: v for k, v in filters.items() if v is not None}

    try:
        result = await export_service.export(
            format=format,
            max_rows=max_rows,
            filters=filters,
        )

        return FileResponse(
            path=result["file_path"],
            filename=result["file_name"],
            media_type=result["media_type"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"导出缺陷列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


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
    """
    获取缺陷统计数据
    """
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        query = sb.table('qc_defects').select('severity,category,status')
        if record_id:
            query = query.eq('record_id', record_id)
        if department:
            query = query.eq('department', department)
        if start_date:
            query = query.gte('created_at', start_date)
        if end_date:
            query = query.lte('created_at', end_date)

        resp = await async_execute(query)
        all_defects = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        logger.error(f"查询缺陷统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

    # 按严重程度统计
    severity_stats = {}
    for d in all_defects:
        sev = d.get("severity", "unknown")
        severity_stats[sev] = severity_stats.get(sev, 0) + 1

    # 按分类统计
    category_stats = {}
    for d in all_defects:
        cat = d.get("category", "other")
        category_stats[cat] = category_stats.get(cat, 0) + 1

    # 按状态统计
    status_stats = {}
    for d in all_defects:
        st = d.get("status", "unknown")
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
