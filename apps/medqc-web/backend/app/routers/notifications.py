"""
通知管理 API（PG 版）

功能:
- 消息通知列表（质控结果推送、催办提醒、整改通知）
- 标记已读/全部已读
- 整改跟踪（已迁移至 remediation.py，保留路由兼容）

数据源：PostgreSQL notifications 表
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Query

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


def _ensure_db():
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    return sb


# ==================== 通知 API ====================

@router.get("")
async def list_notifications(
    request: Request,
    type: Optional[str] = Query(None, description="消息类型: defect_urge/task_assign/appeal_result/remediation/system"),
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """获取通知消息列表"""
    sb = _ensure_db()

    try:
        user_id = current_user.get("id") or current_user.get("user_id")

        query = sb.table('notifications').select('*', count='exact')
        if user_id:
            query = query.eq('recipient_id', user_id)
        if type:
            query = query.eq('type', type)
        if is_read is not None:
            query = query.eq('is_read', is_read)
        query = query.order('created_at', desc=True)

        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        resp = await async_execute(query)
        items = list(getattr(resp, 'data', None) or [])
        total = getattr(resp, 'count', None) or len(items)

        # 未读计数
        unread_query = sb.table('notifications').select('id', count='exact').eq('is_read', False)
        if user_id:
            unread_query = unread_query.eq('recipient_id', user_id)
        unread_resp = await async_execute(unread_query)
        unread_count = getattr(unread_resp, 'count', None) or 0

        return success_response(
            data={
                "items": items,
                "total": total,
                "unread_count": unread_count,
                "page": page,
                "page_size": page_size,
            },
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询通知失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询通知失败: {str(e)}")


@router.put("/{notification_id}/read")
async def mark_read(
    request: Request,
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    """标记消息为已读"""
    sb = _ensure_db()

    try:
        from datetime import datetime
        resp = await async_execute(
            sb.table('notifications')
            .update({"is_read": True, "read_at": datetime.now().isoformat()})
            .eq('id', notification_id)
            .select()
        )
        if not getattr(resp, 'data', None):
            raise HTTPException(status_code=404, detail="通知不存在")
        return success_response(message="已标记为已读", trace_id=get_trace_id(request))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记已读失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.put("/read-all")
async def mark_all_read(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """全部已读"""
    sb = _ensure_db()

    try:
        from datetime import datetime
        user_id = current_user.get("id") or current_user.get("user_id")

        query = sb.table('notifications').update({
            "is_read": True,
            "read_at": datetime.now().isoformat(),
        }).eq('is_read', False)
        if user_id:
            query = query.eq('recipient_id', user_id)

        resp = await async_execute(query.select())
        count = len(getattr(resp, 'data', None) or [])

        return success_response(
            data={"marked_count": count},
            message=f"已标记 {count} 条为已读",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"全部已读失败: {e}")
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
