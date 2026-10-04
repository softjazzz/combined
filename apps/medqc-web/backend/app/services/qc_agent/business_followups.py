"""提醒与整改的只读投影：先限定账号，再由关联结果证明病例身份。"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import HTTPException

from .business_access import BusinessAccess
from .business_reads import require_record
from .business_schemas import BusinessContext
from .business_store import owner_id


def _result_identity(result: dict, record_id: str) -> dict[str, str] | None:
    """只接受保存结果的明确三坐标，禁止从住院号或病历字符串猜院区。"""
    if not record_id or result.get("record_id") != record_id:
        return None
    raw = result.get("raw_output")
    try:
        raw = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    metadata = raw.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    identity = {}
    for key in ("institute_id", "patient_id", "visit_id"):
        values = [part[key] for part in (raw, metadata) if part.get(key) not in (None, "")]
        if not values or any(not isinstance(value, str) or value != value.strip() or not value or value == "*" for value in values):
            return None
        if len(set(values)) != 1:
            return None
        identity[key] = values[0]
    if raw.get("record_id") not in (None, "", record_id):
        return None
    return identity


def read_followups(*, user: dict, context: BusinessContext, access: BusinessAccess,
                   kind: Literal["notifications", "remediations"], page: int = 1,
                   page_size: int = 5, db=None) -> dict:
    """按源列表分页扫描，再逐条授权；排除项不补造为零，也不泄露内容。"""
    access.require_context(user, context)
    if kind not in ("notifications", "remediations") or not 1 <= page <= 100 or not 1 <= page_size <= 10:
        raise HTTPException(422, "提醒查询类型或分页无效")
    uid = owner_id(user)
    if db is None:
        from app.core.supabase_client import get_supabase
        db = get_supabase()
    if db is None:
        raise HTTPException(503, "提醒与整改数据源不可用")
    try:
        if kind == "notifications":
            query = db.table("notifications").select("id,type,title,content,record_id,severity,recipient_id,related_type,related_id,is_read,created_at").eq("recipient_id", uid)
        else:
            query = db.table("qc_remediation_tasks").select("id,record_id,qc_result_id,defect_type,severity,remediation_requirement,deadline,assignee_id,assignee_department,status,created_at")
            query = query.eq("assignee_id", uid) if context.view == "doctor" else query.eq("assignee_department", context.department)
        offset = (page - 1) * page_size
        rows = query.order("created_at", desc=True).order("id").range(offset, offset + page_size).execute().data or []
        items = []
        excluded = False
        for row in rows[:page_size]:
            if kind == "notifications":
                owner_matches = row.get("recipient_id") == uid
                result_id = row.get("related_id") if row.get("related_type") == "qc_result" else None
            else:
                owner_matches = row.get("assignee_id") == uid if context.view == "doctor" else row.get("assignee_department") == context.department
                result_id = row.get("qc_result_id")
            if not owner_matches or not result_id:
                excluded = True
                continue
            results = db.table("qc_results").select("id,record_id,raw_output").eq("id", result_id).limit(1).execute().data or []
            identity = _result_identity(results[0], row.get("record_id")) if len(results) == 1 and results[0].get("id") == result_id else None
            if identity is None:
                excluded = True
                continue
            if context.view == "doctor" and any(identity[key] != getattr(context, key) for key in identity):
                excluded = True
                continue
            if context.view == "manager" and identity["institute_id"] != context.institute_id:
                excluded = True
                continue
            try:
                require_record(access, user, identity, context.view, context.department)
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                excluded = True
                continue
            keys = ("id", "type", "title", "content", "severity", "is_read", "created_at") if kind == "notifications" else ("id", "defect_type", "severity", "remediation_requirement", "deadline", "status", "created_at")
            items.append({**{key: row.get(key) for key in keys}, "identity": identity})
        source_has_more = len(rows) > page_size
        scan_limit_reached = page == 100 and source_has_more
        coverage_note = "按源列表分页，仅展示当前账号及病例/科室授权可核验的条目；缺少完整身份或关联的条目排除。空页不代表没有提醒或整改。"
        if scan_limit_reached:
            coverage_note += "已达第100页扫描上限，仍有未扫描条目，不能继续翻页或声称当前范围已查完。"
        elif source_has_more:
            coverage_note += "源列表仍有未扫描条目，可继续下一页；本页为空或排除条目不表示当前范围已查完。"
        else:
            coverage_note += "已到源列表末页；本次仅核验当前页，不能据此报告完整范围总量。"
        return {"kind": kind, "items": items, "state": "partial" if excluded or scan_limit_reached else "ready",
                "page": page, "page_size": page_size, "has_more": source_has_more and not scan_limit_reached,
                "scan_limit_reached": scan_limit_reached,
                "coverage_note": coverage_note,
                "status_note": "已读与整改状态仅搬运保存值；未重新判断逾期、关闭或复检。管理统计的质控完成时间不作为消息创建/整改期限筛选。"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "提醒与整改读取失败，未取得完整有效数据") from exc
