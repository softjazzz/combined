"""
通知管理 API（PG 版）

功能:
- 消息通知列表（质控结果推送、催办提醒、整改通知）
- 标记已读/全部已读
- 整改跟踪（已迁移至 remediation.py，保留路由兼容）

数据源：PostgreSQL notifications 表
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from starlette.concurrency import run_in_threadpool

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user
from ..services.doctor_notification_service import DoctorNotificationService, Notification
from ..services.defect_rectification_service import RectificationError

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)
service = DoctorNotificationService()

SHANGHAI_TZ = timezone(timedelta(hours=8))
BATCH_SUMMARY_ROLES = {"admin", "super_admin", "qc_manager", "qc_staff", "sync_admin"}


def _shanghai_day_utc_bounds(date_str: Optional[str]) -> tuple[str, datetime, datetime]:
    """将东八区自然日换算为库内无时区 UTC 查询边界 [start, end)。"""
    if date_str:
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="date 格式必须为 YYYY-MM-DD")
        local_start = datetime(
            parsed.year, parsed.month, parsed.day, tzinfo=SHANGHAI_TZ
        )
    else:
        local_start = datetime.now(SHANGHAI_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    local_end = local_start + timedelta(days=1)
    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return local_start.strftime("%Y-%m-%d"), utc_start, utc_end


async def _owned_call(user, method, *args, **kwargs):
    actor_id = user.get("id") or user.get("user_id")
    if not actor_id:
        raise HTTPException(403, "缺少持久账号")
    try:
        return await run_in_threadpool(method, str(actor_id), *args, **kwargs)
    except RectificationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("通知操作失败 error_type=%s", type(exc).__name__)
        raise HTTPException(503, "通知服务暂不可用，请刷新核对") from exc


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
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
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
    data = await _owned_call(current_user, service.list, type=type, is_read=is_read, page=page, page_size=page_size)
    return success_response(data=data, trace_id=get_trace_id(request))


@router.get("/overview")
async def list_notification_overview(
    request: Request,
    date: Optional[str] = Query(None, description="统计日期，格式 YYYY-MM-DD，默认当天"),
    current_user: dict = Depends(get_current_user),
):
    """按问题类型/严重度/科室/病历聚合当天通知集中点。"""
    try:
        summary_date, start_dt, end_dt = _shanghai_day_utc_bounds(date)

        rows = await _owned_call(current_user, service.overview_rows, start_dt, end_dt)

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
                    "interaction_target": row.get("interaction_target"),
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
                "date": summary_date,
                "items": items,
                "total": len(items),
            },
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("查询通知概览失败")
        raise HTTPException(status_code=500, detail="查询通知概览失败，请稍后重试")


def _load_ready_batch_result(job_id, actor_id):
    from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
    from .qc_sichuan import (
        LUXIAN_0609_RULE_SET_KEY,
        _hydrate_luxian_canonical_batch_job_or_409,
        _is_workspace_batch_job,
        _workspace_batch_response_item,
    )

    workspace = CustomQCWorkspaceService(readonly=True)
    job = workspace.get_batch_job(job_id=job_id, created_by=actor_id)
    if not _is_workspace_batch_job(job) or job.get("status") != "completed":
        raise RectificationError("结果通知已失效，请重新查询任务", 404)
    if (job.get("filters") or {}).get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY:
        job = _hydrate_luxian_canonical_batch_job_or_409(workspace=workspace, job=job)
    return _workspace_batch_response_item(job)


@router.get("/{notification_id}/qc-result")
async def get_notification_qc_result(
    notification_id: str, request: Request,
    current_user: dict = Depends(get_current_user),
):
    from .qc_sichuan import _is_restricted_demo_account, _trim_batch_job_for_demo_account

    data = await _owned_call(
        current_user, service.result_ready, notification_id, _load_ready_batch_result
    )
    if _is_restricted_demo_account(current_user) and isinstance(data, dict):
        data = _trim_batch_job_for_demo_account(data)
    return success_response(data=data, trace_id=get_trace_id(request))


def _upsert_qc_batch_summary_owned(
    actor_id: str,
    *,
    workflow_type: str,
    summary_date: str,
    notif_type: str,
    title: str,
    content: str,
    record_id: str,
    severity: str,
) -> Dict[str, Any]:
    notification_id = _stable_notification_id(
        "qc_batch_summary", actor_id, workflow_type, summary_date
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = Notification.__table__

    with service.sessions() as session, session.begin():
        actor = service.person(session, actor_id)
        if not (actor["roles"] & BATCH_SUMMARY_ROLES):
            raise RectificationError("仅管理员或质控人员可保存批量汇总消息", 403)

        bind = session.get_bind()
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        insert_fn = sqlite_insert if dialect_name == "sqlite" else pg_insert

        values = {
            "id": notification_id,
            "type": notif_type,
            "title": title,
            "content": content,
            "record_id": record_id,
            "severity": severity,
            "sender_id": actor_id,
            "recipient_id": actor_id,
            "related_type": "batch_summary",
            "related_id": None,
            "is_read": False,
            "read_at": None,
            "created_at": now,
        }
        update_values = {
            key: value
            for key, value in values.items()
            if key not in {"id", "created_at"}
        }
        upsert_stmt = insert_fn(table).values(**values).on_conflict_do_update(
            index_elements=[table.c.id],
            set_=update_values,
        )

        if dialect_name == "postgresql":
            inserted = bool(
                session.execute(
                    upsert_stmt.returning(literal_column("(xmax = 0)").label("inserted"))
                ).scalar_one()
            )
        else:
            existed = session.get(Notification, notification_id) is not None
            session.execute(upsert_stmt)
            inserted = not existed

    return {
        "id": notification_id,
        "created": inserted,
        "updated": not inserted,
        "workflow_type": workflow_type,
        "date": summary_date,
    }


@router.post("/qc-batch-summary")
async def upsert_qc_batch_summary(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """为当天批量执行生成或更新一条 workflow 级汇总消息。"""
    try:
        workflow_type = _pick_text(payload, ["workflow_type"]) or "general"
        target_date_raw = _pick_text(payload, ["date"])
        summary_date, _, _ = _shanghai_day_utc_bounds(target_date_raw or None)
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
        record_id = f"batch_summary::{workflow_type}::{summary_date}"
        notif_type = _workflow_batch_summary_type(workflow_type)

        data = await _owned_call(
            current_user,
            _upsert_qc_batch_summary_owned,
            workflow_type=workflow_type,
            summary_date=summary_date,
            notif_type=notif_type,
            title=title,
            content=content,
            record_id=record_id,
            severity=severity,
        )
        return success_response(
            data=data,
            message="批量汇总消息已保存",
            trace_id=get_trace_id(request),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("保存批量汇总消息失败")
        raise HTTPException(status_code=500, detail="保存批量汇总消息失败，请稍后重试")


@router.put("/{notification_id}/read")
async def mark_read(
    request: Request,
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    """标记消息为已读"""
    await _owned_call(current_user, service.mark_read, notification_id)
    return success_response(message="已标记为已读", trace_id=get_trace_id(request))


@router.put("/read-all")
async def mark_all_read(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """全部已读"""
    count = await _owned_call(current_user, service.mark_read)
    return success_response(data={"marked_count": count}, message=f"已标记 {count} 条为已读", trace_id=get_trace_id(request))
