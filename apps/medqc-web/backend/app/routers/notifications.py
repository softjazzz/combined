"""
通知与申诉 API

功能:
- 消息通知列表（质控结果推送、催办提醒、整改通知）
- 标记已读/全部已读
- 整改跟踪（整改任务列表/提交整改/审核整改）
- 问题闭环管理
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, Depends, Query

from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

# ==================== 内存存储 ====================
_notifications_db: List[dict] = []
_rectification_db: List[dict] = []


def _init_mock_data():
    global _notifications_db, _rectification_db
    if _notifications_db:
        return

    now = datetime.now()

    # 通知消息
    _notifications_db = [
        {
            "id": str(uuid.uuid4()),
            "type": "qc_result",
            "title": "质控结果通知",
            "content": "病历 MR-2026-001（张某某）质控完成，发现 3 个缺陷需整改",
            "record_id": "MR-2026-001",
            "severity": "error",
            "is_read": False,
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "type": "urge",
            "title": "催办提醒",
            "content": "病历 MR-2026-003（李某某）已超期 2 天未整改，请尽快处理",
            "record_id": "MR-2026-003",
            "severity": "warning",
            "is_read": False,
            "created_at": (now - timedelta(hours=3)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "type": "rectification",
            "title": "整改完成通知",
            "content": "病历 MR-2026-005（王某某）的 2 个缺陷已完成整改，请审核",
            "record_id": "MR-2026-005",
            "severity": "info",
            "is_read": True,
            "created_at": (now - timedelta(hours=5)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "type": "appeal",
            "title": "临床申诉",
            "content": "内科刘医生对病历 MR-2026-007 的缺陷「主诊断编码错误」提出申诉",
            "record_id": "MR-2026-007",
            "severity": "warning",
            "is_read": False,
            "created_at": (now - timedelta(hours=8)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "type": "system",
            "title": "系统通知",
            "content": "本月质控任务 TK-2026-003 即将于 3 天后截止",
            "record_id": None,
            "severity": "info",
            "is_read": False,
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "type": "qc_result",
            "title": "批量质控完成",
            "content": "批量质控任务 TK-2026-002 已完成，共 28 份病历，发现 45 个缺陷",
            "record_id": None,
            "severity": "info",
            "is_read": True,
            "created_at": (now - timedelta(days=2)).isoformat(),
        },
    ]

    # 整改任务
    _rectification_db = [
        {
            "id": str(uuid.uuid4()),
            "record_id": "MR-2026-001",
            "patient_name": "张某某",
            "department": "内科",
            "defect_description": "入院记录主诉与现病史不一致",
            "status": "pending",
            "assigned_to": "刘医生",
            "deadline": (now + timedelta(days=3)).isoformat(),
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "record_id": "MR-2026-003",
            "patient_name": "李某某",
            "department": "外科",
            "defect_description": "手术记录未在24小时内完成",
            "status": "overdue",
            "assigned_to": "王医生",
            "deadline": (now - timedelta(days=2)).isoformat(),
            "created_at": (now - timedelta(days=4)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "record_id": "MR-2026-005",
            "patient_name": "王某某",
            "department": "骨科",
            "defect_description": "知情同意书缺少患者签名",
            "status": "submitted",
            "assigned_to": "赵医生",
            "deadline": (now + timedelta(days=5)).isoformat(),
            "submitted_at": (now - timedelta(hours=5)).isoformat(),
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "record_id": "MR-2026-008",
            "patient_name": "陈某某",
            "department": "儿科",
            "defect_description": "主诊断编码与出院诊断不符",
            "status": "approved",
            "assigned_to": "钱医生",
            "deadline": (now + timedelta(days=1)).isoformat(),
            "approved_at": (now - timedelta(hours=2)).isoformat(),
            "created_at": (now - timedelta(days=5)).isoformat(),
        },
    ]


_init_mock_data()


# ==================== 通知 API ====================

@router.get("")
async def list_notifications(
    request: Request,
    type: Optional[str] = Query(None, description="消息类型: qc_result/urge/rectification/appeal/system"),
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """获取通知消息列表"""
    items = list(_notifications_db)

    if type:
        items = [n for n in items if n["type"] == type]
    if is_read is not None:
        items = [n for n in items if n["is_read"] == is_read]

    items.sort(key=lambda n: n["created_at"], reverse=True)
    total = len(items)
    items = items[(page - 1) * page_size : page * page_size]

    unread_count = sum(1 for n in _notifications_db if not n["is_read"])

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


@router.put("/{notification_id}/read")
async def mark_read(
    request: Request,
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    """标记消息为已读"""
    notif = next((n for n in _notifications_db if n["id"] == notification_id), None)
    if not notif:
        raise HTTPException(status_code=404, detail="通知不存在")

    notif["is_read"] = True
    return success_response(message="已标记为已读", trace_id=get_trace_id(request))


@router.put("/read-all")
async def mark_all_read(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """全部已读"""
    count = 0
    for n in _notifications_db:
        if not n["is_read"]:
            n["is_read"] = True
            count += 1
    return success_response(data={"marked_count": count}, message=f"已标记 {count} 条为已读", trace_id=get_trace_id(request))


# ==================== 整改跟踪 API ====================

@router.get("/rectifications")
async def list_rectifications(
    request: Request,
    status: Optional[str] = Query(None, description="状态: pending/overdue/submitted/approved/rejected"),
    current_user: dict = Depends(get_current_user),
):
    """获取整改任务列表"""
    items = list(_rectification_db)

    if status:
        items = [r for r in items if r["status"] == status]

    items.sort(key=lambda r: r["created_at"], reverse=True)

    # 统计
    stats = {
        "pending": sum(1 for r in _rectification_db if r["status"] == "pending"),
        "overdue": sum(1 for r in _rectification_db if r["status"] == "overdue"),
        "submitted": sum(1 for r in _rectification_db if r["status"] == "submitted"),
        "approved": sum(1 for r in _rectification_db if r["status"] == "approved"),
        "total": len(_rectification_db),
    }

    return success_response(
        data={"items": items, "stats": stats},
        trace_id=get_trace_id(request),
    )


@router.put("/rectifications/{rect_id}/submit")
async def submit_rectification(
    request: Request,
    rect_id: str,
    current_user: dict = Depends(get_current_user),
):
    """提交整改"""
    body = await request.json()
    rect = next((r for r in _rectification_db if r["id"] == rect_id), None)
    if not rect:
        raise HTTPException(status_code=404, detail="整改任务不存在")

    rect["status"] = "submitted"
    rect["submitted_at"] = datetime.now().isoformat()
    rect["rectification_note"] = body.get("note", "")

    return success_response(data=rect, message="整改已提交", trace_id=get_trace_id(request))


@router.put("/rectifications/{rect_id}/approve")
async def approve_rectification(
    request: Request,
    rect_id: str,
    current_user: dict = Depends(get_current_user),
):
    """审核通过整改"""
    rect = next((r for r in _rectification_db if r["id"] == rect_id), None)
    if not rect:
        raise HTTPException(status_code=404, detail="整改任务不存在")

    rect["status"] = "approved"
    rect["approved_at"] = datetime.now().isoformat()

    return success_response(data=rect, message="整改审核通过，问题已闭环", trace_id=get_trace_id(request))


@router.put("/rectifications/{rect_id}/reject")
async def reject_rectification(
    request: Request,
    rect_id: str,
    current_user: dict = Depends(get_current_user),
):
    """退回整改"""
    body = await request.json()
    rect = next((r for r in _rectification_db if r["id"] == rect_id), None)
    if not rect:
        raise HTTPException(status_code=404, detail="整改任务不存在")

    rect["status"] = "pending"
    rect["reject_reason"] = body.get("reason", "")

    return success_response(data=rect, message="已退回整改", trace_id=get_trace_id(request))
