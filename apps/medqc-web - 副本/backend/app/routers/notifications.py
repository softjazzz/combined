"""
通知管理 API（PG 版）

功能:
- 消息通知列表（质控结果推送、催办提醒、整改通知）
- 标记已读/全部已读
- 整改跟踪（已迁移至 remediation.py，保留路由兼容）

数据源：PostgreSQL notifications 表
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from uuid import NAMESPACE_URL, uuid5

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


def _to_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _pick_text(item: dict, keys: list[str]) -> str:
    for key in keys:
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _extract_department(item: dict) -> str:
    direct = _pick_text(item, ["department", "dept_name", "department_name"])
    if direct:
        return direct
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        nested = _pick_text(metadata, ["department", "dept_name", "department_name"])
        if nested:
            return nested
    payload = item.get("payload")
    if isinstance(payload, dict):
        nested = _pick_text(payload, ["department", "dept_name", "department_name"])
        if nested:
            return nested
    return "未分科室"


def _extract_severity(item: dict) -> str:
    severity = _pick_text(item, ["severity", "level", "priority"])
    return severity or "info"


def _severity_weight(level: str) -> int:
    mapping = {
        "critical": 4,
        "high": 3,
        "warning": 2,
        "medium": 2,
        "low": 1,
        "info": 1,
    }
    return mapping.get(str(level).lower(), 1)


def _stable_notification_id(*parts: object) -> str:
    normalized = "|".join(str(part or "") for part in parts)
    return str(uuid5(NAMESPACE_URL, normalized))


def _workflow_batch_label(workflow_type: str) -> str:
    labels = {
        "frontpage_generate": "首页生成",
        "frontpage_qc": "首页质控",
        "coding_qc": "编码质控",
        "settlement_qc": "结算清单质控",
    }
    return labels.get(str(workflow_type or "").strip(), "批量质控")


def _workflow_batch_summary_type(workflow_type: str) -> str:
    labels = {
        "frontpage_generate": "frontpage_batch_summary",
        "frontpage_qc": "frontpage_qc_batch_summary",
        "coding_qc": "coding_qc_batch_summary",
        "settlement_qc": "settlement_qc_batch_summary",
    }
    return labels.get(str(workflow_type or "").strip(), "general_batch_summary")


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


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


@router.get("/overview")
async def list_notification_overview(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期，格式 YYYY-MM-DD，默认当天"),
    current_user: dict = Depends(get_current_user),
):
    """按问题类型/严重度/科室/病历聚合当天通知集中点。"""
    sb = _ensure_db()
    try:
        user_id = current_user.get("id") or current_user.get("user_id")

        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=422, detail="date 格式必须为 YYYY-MM-DD")
        else:
            target_date = datetime.now()
        start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)

        query = sb.table("notifications").select("*")
        if user_id:
            query = query.eq("recipient_id", user_id)
        query = query.gte("created_at", start_dt.isoformat()).lt("created_at", end_dt.isoformat())
        query = query.order("created_at", desc=True).limit(500)

        resp = await async_execute(query)
        rows = list(getattr(resp, "data", None) or [])

        groups: dict[str, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            notif_type = _pick_text(row, ["type", "category"]) or "general"
            severity = _extract_severity(row)
            department = _extract_department(row)
            record_id = _pick_text(row, ["record_id", "recordId", "visit_id", "visitId"]) or ""
            key = f"{notif_type}|{severity}|{department}|{record_id}"
            created_at = _pick_text(row, ["created_at", "createdAt"])

            entry = groups.get(key)
            if entry is None:
                entry = {
                    "overview_id": key,
                    "type": notif_type,
                    "severity": severity,
                    "department": department,
                    "record_id": record_id,
                    "title": _pick_text(row, ["title", "subject", "type_label"]) or "病案问题提醒",
                    "summary": _pick_text(row, ["content", "message", "body"]) or "暂无描述",
                    "occurrence_count": 0,
                    "unread_count": 0,
                    "latest_created_at": created_at,
                    "source_notification_ids": [],
                }
                groups[key] = entry

            entry["occurrence_count"] += 1
            if not bool(row.get("is_read")):
                entry["unread_count"] += 1
            source_id = _pick_text(row, ["id", "notification_id"])
            if source_id:
                entry["source_notification_ids"].append(source_id)

            existing_time = _to_datetime(entry.get("latest_created_at"))
            incoming_time = _to_datetime(created_at)
            if incoming_time and (existing_time is None or incoming_time > existing_time):
                entry["latest_created_at"] = created_at
                if _pick_text(row, ["content", "message", "body"]):
                    entry["summary"] = _pick_text(row, ["content", "message", "body"])

        items = list(groups.values())
        items.sort(
            key=lambda item: (
                int(item.get("unread_count") or 0),
                _severity_weight(str(item.get("severity") or "")),
                int(item.get("occurrence_count") or 0),
                _to_datetime(item.get("latest_created_at")) or datetime.min,
            ),
            reverse=True,
        )

        return success_response(
            data={
                "date": start_dt.strftime("%Y-%m-%d"),
                "items": items,
                "total": len(items),
            },
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询通知概览失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询通知概览失败: {str(e)}")


@router.post("/qc-batch-summary")
async def upsert_qc_batch_summary(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """为当天批量执行生成或更新一条 workflow 级汇总消息。"""
    sb = _ensure_db()
    try:
        user_id = str(current_user.get("id") or current_user.get("user_id") or "")
        workflow_type = _pick_text(payload, ["workflow_type"]) or "general"
        target_date_raw = _pick_text(payload, ["date"])
        if target_date_raw:
            try:
                target_date = datetime.strptime(target_date_raw, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=422, detail="date 格式必须为 YYYY-MM-DD")
        else:
            target_date = datetime.now()
        summary_date = target_date.strftime("%Y-%m-%d")
        total_count = _safe_int(payload.get("total_count"))
        success_count = _safe_int(payload.get("success_count"))
        failed_count = _safe_int(payload.get("failed_count"))
        high_risk_count = _safe_int(payload.get("high_risk_count"))
        if total_count <= 0:
            raise HTTPException(status_code=422, detail="total_count 必须大于 0")

        workflow_label = _workflow_batch_label(workflow_type)
        severity = "warning" if failed_count > 0 or high_risk_count > 0 else "info"
        title = f"{summary_date} {workflow_label}批量汇总"
        content = (
            f"当日{workflow_label}批量执行共 {total_count} 条，"
            f"成功 {success_count} 条，失败 {failed_count} 条，"
            f"高风险 {high_risk_count} 条。"
        )
        notification_id = _stable_notification_id("qc_batch_summary", user_id or "anonymous", workflow_type, summary_date)
        record_id = f"batch_summary::{workflow_type}::{summary_date}"
        notif_type = _workflow_batch_summary_type(workflow_type)

        existing_resp = await async_execute(
            sb.table("notifications").select("id, created_at").eq("id", notification_id).limit(1)
        )
        existing_rows = list(getattr(existing_resp, "data", None) or [])
        created_at = None
        if existing_rows:
            created_at = existing_rows[0].get("created_at")

        payload_row = {
            "id": notification_id,
            "type": notif_type,
            "title": title,
            "content": content,
            "record_id": record_id,
            "severity": severity,
            "sender_id": user_id or None,
            "recipient_id": user_id or None,
            "related_type": "batch_summary",
            "related_id": None,
            "is_read": False,
            "read_at": None,
            "created_at": created_at or datetime.now().isoformat(),
        }

        if existing_rows:
            await async_execute(
                sb.table("notifications")
                .update({key: value for key, value in payload_row.items() if key != "id"})
                .eq("id", notification_id)
            )
            created = False
            updated = True
        else:
            await async_execute(sb.table("notifications").insert(payload_row))
            created = True
            updated = False

        return success_response(
            data={
                "id": notification_id,
                "created": created,
                "updated": updated,
                "workflow_type": workflow_type,
                "date": summary_date,
            },
            message="批量汇总消息已保存",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存批量汇总消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存批量汇总消息失败: {str(e)}")


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
