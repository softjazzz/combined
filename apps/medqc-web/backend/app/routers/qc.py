import uuid
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Query, Request, Depends
from starlette.concurrency import run_in_threadpool

from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.security import get_current_user, require_roles
from ..core.permissions import (
    require_permission,
    require_role,
    require_admin,
    ResourceType,
    PermissionAction,
    UserRole,
)
from ..services.qc_persistence_service import (
    VerifiedQCIdentity,
    default_qc_persistence_service,
)
from ..services.workflow_queue_state_service import default_workflow_queue_state_service
from ..services.llm_observability import llm_observation_context
from ..services.coding_rule_catalog import CODING_RULE_SET_KEY, load_coding_rule_catalog
from ..services.rule_set_version_service import current_version, resolve_rule_set_version
from ..services.sc_rule_launch_tier import (
    load_sc_intrinsic_launch_tier_map,
    resolve_sc_intrinsic_launch_tier,
)
from ..services.medical_records.errors import (
    MedicalRecordsConflictError,
    MedicalRecordsNotFoundError,
    MedicalRecordsSourceUnavailableError,
    MedicalRecordsStorageError,
    MedicalRecordsValidationError,
)
from ..services.medical_records.export_service import get_frontpage_sheet

router = APIRouter(prefix="/api/v1/qc", tags=["qc"])
service = QCService()

import logging as _logging
logger = _logging.getLogger(__name__)

def _current_user_id(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not current_user:
        return None
    value = current_user.get("id") or current_user.get("user_id")
    return str(value) if value else None


def _extract_frontpage_value(frontpage: Dict[str, Any], *paths: tuple[str, ...] | str) -> str:
    for path in paths:
        keys = (path,) if isinstance(path, str) else path
        current: Any = frontpage
        for key in keys:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return str(current)
    return ""


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"


def _coding_issue_to_persistence_issue(issue: Dict[str, Any], fallback_category: str) -> Dict[str, Any]:
    return {
        "rule_code": str(issue.get("rule_id") or issue.get("code") or issue.get("dimension") or "coding_rule"),
        "rule_name": str(issue.get("rule_name") or issue.get("dimension") or "编码质控规则"),
        "description": str(issue.get("description") or ""),
        "severity": str(issue.get("severity") or "warning"),
        "category": str(issue.get("dimension") or fallback_category or "coding"),
        "location": str(issue.get("location") or issue.get("field_name") or "病案首页编码区"),
        "suggestion": str(issue.get("suggestion") or issue.get("recommendation") or "请复核相关编码"),
        "evidence": issue.get("evidence"),
        "legacy_rule_id": str(issue.get("legacy_rule_id") or "") or None,
    }


def _build_formal_qc_persistence_result(
    sheet: Dict[str, Any],
    report: Any,
    payload: Dict[str, Any],
    identity: VerifiedQCIdentity,
) -> Dict[str, Any]:
    """把首页形式质控报告装配成现代落库载荷。

    三坐标只取服务端核实的身份（``VerifiedQCIdentity``），不再从请求体或客户端
    正文推断；结果顶层坐标与 metadata 必须与身份逐项一致，否则持久化层会拒绝现代写入。
    机构名等科室事实取自服务端读到的首页 ``basic``，客户端 ``frontpage`` 正文不参与装配。
    """
    department = _extract_frontpage_value(
        sheet,
        ("basic", "admission_dept_name"),
        ("basic", "discharge_dept_name"),
    )
    score = round(report.passed / report.total_rules * 100, 1) if report.total_rules else 0.0
    issues = [
        {
            "rule_code": r.rule_id,
            "rule_name": r.rule_name,
            "description": r.message,
            "severity": r.severity.value,
            "category": r.category.value,
            "location": r.field_name or "病案首页",
            "suggestion": r.message,
            "evidence": r.field_name,
        }
        for r in report.results
        if not r.passed
    ]
    metadata = {
        "workflow_type": "frontpage",
        "patient_id": identity.patient_id,
        "visit_id": identity.visit_id,
        "institute_id": identity.institute_id,
        "department": department,
        "data_source": identity.source_key,
        "trigger_source": "workstation_v4",
        "categories": payload.get("categories") or [],
        "severities": payload.get("severities") or [],
        "executed_defect_scope": {
            "kind": "rule_codes",
            "values": [result.rule_id for result in report.results],
        },
    }
    return {
        "record_id": f"frontpage::{identity.visit_id}",
        "workflow_type": "frontpage",
        "patient_id": identity.patient_id,
        "visit_id": identity.visit_id,
        "overall_score": score,
        "overall_grade": _grade_from_score(score),
        "defect_count": len(issues),
        "issues": issues,
        "metadata": metadata,
        "analysis_engine": "frontpage-formal-qc",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "raw_report": {
            "total_rules": report.total_rules,
            "passed": report.passed,
            "failed": report.failed,
        },
    }


def _build_coding_qc_persistence_result(
    payload: Dict[str, Any],
    report: Dict[str, Any],
    semantic_completed: bool = False,
    identity: Optional["CodingQcIdentity"] = None,
) -> Dict[str, Any]:
    if identity is not None:
        # 现代身份：结果与 metadata 一律回填服务端解析出的三坐标，与 verified_identity 一致。
        patient_id = identity.patient_id
        visit_id = identity.visit_id
    else:
        # 旧手工 frontpage 模式：沿用请求体坐标，且不构成已验证身份。
        patient_id = str(payload.get("patient_id") or "")
        visit_id = str(payload.get("visit_id") or "")
        frontpage = payload.get("frontpage") if isinstance(payload.get("frontpage"), dict) else {}
        if not patient_id:
            patient_id = _extract_frontpage_value(frontpage, ("basic_info", "patient_id"), "patient_id")
    total_issues = int(report.get("total_issues") or 0)
    issues = [
        _coding_issue_to_persistence_issue(item, "coding_rule")
        for item in (report.get("rule_issues") or [])
        if isinstance(item, dict)
    ]
    issues.extend(
        _coding_issue_to_persistence_issue(item, "coding_llm")
        for item in (report.get("llm_issues") or [])
        if isinstance(item, dict)
    )
    overall_score = max(0.0, 100.0 - min(total_issues, 20) * 5.0)
    metadata = {
        "workflow_type": "coding",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "department": "",
        "data_source": "coding_qc",
        "trigger_source": "workstation_v4",
    }
    if identity is not None:
        metadata["institute_id"] = identity.institute_id
    rule_set_key = str(report.get("rule_set_key") or "").strip()
    rule_set_version = str(report.get("rule_set_version") or "").strip()
    rule_set_content_digest = str(report.get("rule_set_content_digest") or "").strip()
    active_rule_ids = [str(value) for value in report.get("active_rule_ids") or []]
    executed_rule_ids = [str(value) for value in report.get("executed_rule_ids") or []]
    if rule_set_key and rule_set_version:
        metadata.update({
            "rule_set_key": rule_set_key,
            "rule_set_version": rule_set_version,
            "rule_set_content_digest": rule_set_content_digest,
            "active_rule_ids": active_rule_ids,
            "executed_rule_ids": executed_rule_ids,
        })
    if executed_rule_ids:
        metadata["executed_defect_scope"] = {
            "kind": "rule_codes",
            "values": executed_rule_ids,
        }
    return {
        "record_id": f"coding::{visit_id or patient_id or uuid.uuid4().hex[:8]}",
        "workflow_type": "coding",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "overall_score": overall_score,
        "overall_grade": _grade_from_score(overall_score),
        "defect_count": len(issues),
        "issues": issues,
        "metadata": metadata,
        "analysis_engine": "coding-qc",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
    }


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None
    return None


def _normalize_issue(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "id": str(item.get("id") or f"issue-{uuid.uuid4().hex[:8]}"),
        "rule_name": str(item.get("rule_name") or item.get("ruleName") or "未知规则"),
        "description": str(item.get("description") or ""),
        "severity": str(item.get("severity") or "warning"),
        "category": str(item.get("category") or "general"),
        "location": str(item.get("location") or "病历正文"),
        "suggestion": str(item.get("suggestion") or "请补充相关记录"),
        "evidence": item.get("evidence"),
    }


def _normalize_rule_result(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "rule_id": str(item.get("rule_id") or item.get("ruleId") or f"rule-{uuid.uuid4().hex[:8]}"),
        "rule_name": str(item.get("rule_name") or item.get("ruleName") or "未知规则"),
        "passed": bool(item.get("passed", False)),
        "score": int(item.get("score", 0) or 0),
        "details": str(item.get("details") or ""),
        "max_score": item.get("max_score"),
        "execution_time": item.get("execution_time"),
        "confidence": item.get("confidence"),
    }


def _normalize_suggestion(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "id": str(item.get("id") or f"sug-{uuid.uuid4().hex[:8]}"),
        "category": str(item.get("category") or "general"),
        "title": str(item.get("title") or "整改建议"),
        "description": str(item.get("description") or ""),
        "priority": str(item.get("priority") or "medium"),
    }


def _row_to_qc_result(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_payload = _parse_json_field(row.get("raw_output")) or {}
    metadata = _parse_json_field(row.get("metadata")) or {}
    issues_src = row.get("issues")
    issues_parsed = _parse_json_field(issues_src)
    if not isinstance(issues_parsed, list):
        issues_parsed = raw_payload.get("issues", [])
    suggestions_src = raw_payload.get("suggestions", [])
    rule_results_src = raw_payload.get("rule_results", [])
    analysis_steps_src = raw_payload.get("analysis_steps", [])

    issues = [_normalize_issue(x) for x in issues_parsed if x is not None]
    suggestions = [_normalize_suggestion(x) for x in suggestions_src if x is not None]
    rule_results = [_normalize_rule_result(x) for x in rule_results_src if x is not None]
    analysis_steps = analysis_steps_src if isinstance(analysis_steps_src, list) else []

    overall_score = row.get("overall_score")
    if overall_score is None:
        overall_score = raw_payload.get("overall_score", 0)
    grade = row.get("grade") or raw_payload.get("overall_grade") or "C"
    analysis_date = row.get("analysis_date") or row.get("created_at") or datetime.utcnow().isoformat() + "Z"

    return {
        "id": str(row.get("id") or raw_payload.get("id") or f"analysis-{uuid.uuid4().hex[:8]}"),
        "record_id": str(row.get("record_id") or raw_payload.get("record_id") or ""),
        "overall_score": int(overall_score or 0),
        "overall_grade": str(grade),
        "analysis_date": str(analysis_date),
        "issues": issues,
        "suggestions": suggestions,
        "rule_results": rule_results,
        "analysis_steps": analysis_steps,
        "metadata": metadata,
    }


async def _save_qc_result(record_id: str, result: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """将分析结果持久化到 qc_results/qc_defects/notifications。"""
    try:
        normalized = dict(result)
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        metadata.setdefault("workflow_type", normalized.get("workflow_type") or "analysis")
        metadata.setdefault("trigger_source", "workstation_v4")
        normalized["metadata"] = metadata
        normalized["record_id"] = record_id
        return await default_qc_persistence_service.persist_analysis(normalized, actor=actor)
    except Exception as e:
        logger.warning(f"[qc] 写入质控持久化结果失败（非阻塞）: {e}")
        return {
            "qc_result_id": None,
            "defects_created": 0,
            "defects_updated": 0,
            "defects_resolved": 0,
            "notification_created": False,
            "notification_updated": False,
            "notification_id": None,
        }


@router.post("/analyze/batch")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def analyze_batch(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """批量分析病案记录"""
    started = []
    records_payload: List[Dict[str, Any]] = payload.get("records", [])
    if records_payload:
        for entry in records_payload:
            rid = entry.get("record_id") or entry.get("id")
            if not rid:
                continue
            entry_payload = dict(entry)
            entry_payload["record_id"] = rid
            res = await service.evaluate(entry_payload)
            persistence = await _save_qc_result(rid, res, actor=current_user)
            started.append({"record_id": rid, "status": "completed", "analysis_id": persistence.get("qc_result_id") or res.get("id"), "persistence": persistence})
    else:
        record_ids: List[str] = payload.get("record_ids", [])
        for rid in record_ids:
            res = await service.evaluate({"record_id": rid})
            persistence = await _save_qc_result(rid, res, actor=current_user)
            started.append({"record_id": rid, "status": "completed", "analysis_id": persistence.get("qc_result_id") or res.get("id"), "persistence": persistence})

    return success_response(
        data={
            "started": started,
            "count": len(started),
        },
        message=f"已完成 {len(started)} 个文档的质控分析",
        trace_id=get_trace_id(request)
    )


@router.post("/analyze/{record_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def analyze_record(
    request: Request,
    record_id: str,
    payload: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(get_current_user)
):
    """分析单个病案记录"""
    request_payload = dict(payload or {})
    request_payload["record_id"] = record_id
    result = await service.evaluate(request_payload)
    persistence = await _save_qc_result(record_id, result, actor=current_user)
    analysis_id = persistence.get("qc_result_id") or result.get("id") or f"analysis-{uuid.uuid4().hex[:8]}"

    return success_response(
        data={
            "analysis_id": analysis_id,
            "status": "completed",
            "record_id": record_id,
            "persistence": persistence,
        },
        message="质控分析完成",
        trace_id=get_trace_id(request)
    )


@router.get("/result/{record_id}", response_model=QCResult)
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_result(record_id: str, current_user: dict = Depends(get_current_user)):
    """获取质控结果，从 PG qc_results 表读取"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        resp = await async_execute(
            sb.table('qc_results').select('*').eq('record_id', record_id).order('created_at', desc=True).limit(1)
        )
        data = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询质控结果失败: {str(e)}")
    if not data or data[0].get("identity_version") is not None:
        # 现代结果按三坐标身份落库，旧单坐标端点不得认领，避免跨身份读取。
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="质控结果不存在"
        )
    return _row_to_qc_result(data[0])


@router.get("/progress/{analysis_id}")
async def get_progress(request: Request, analysis_id: str):
    """获取分析进度"""
    # Simplified: assume completed if any result exists
    return success_response(
        data={
            "analysis_id": analysis_id,
            "status": "completed"
        },
        message="获取进度成功",
        trace_id=get_trace_id(request)
    )


 


@router.get("/rules")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def list_rules(
    request: Request,
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    document_category: Optional[str] = Query(None, description="文书类别"),
    rule_type: Optional[str] = Query(None, description="规则类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取质控规则列表（仅从 PG 加载，不再回退 JSON）。"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        launch_tier_map = load_sc_intrinsic_launch_tier_map()
        query = sb.table('qc_rules').select('*', count='exact')
        if keyword:
            if hasattr(query, 'or_'):
                query = query.or_(f"name.ilike.%{keyword}%,description.ilike.%{keyword}%,rule_code.ilike.%{keyword}%")
        if category:
            query = query.eq('category', category)
        if document_category:
            if hasattr(query, 'or_'):
                query = query.or_(
                    f"applicable_documents.cs.{{{document_category}}},"
                    f"applicable_documents.is.null,"
                    f"applicable_documents.eq.{{}},"
                    f"primary_document_category.eq.{document_category},"
                    f"document_categories.cs.{{{document_category}}}"
                )
        if rule_type:
            query = query.eq('rule_type', rule_type)
        if severity:
            query = query.eq('severity', severity)
        if is_active is not None:
            query = query.eq('is_active', is_active)
        offset = (page - 1) * limit
        if hasattr(query, 'range'):
            query = query.range(offset, offset + limit - 1)
        if hasattr(query, 'order'):
            query = query.order('primary_document_category').order('name')

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        tier_label_map = {
            "A": "默认启用",
            "B": "灰度",
            "C": "观察",
            "UNKNOWN": "未分层",
        }
        enriched_data = []
        for item in data:
            normalized = dict(item)
            rule_id = str(normalized.get('rule_id') or normalized.get('rule_code') or '').strip()
            tier = resolve_sc_intrinsic_launch_tier(rule_id, launch_tier_map=launch_tier_map)
            normalized['launch_tier'] = tier
            normalized['launch_tier_label'] = tier_label_map.get(tier, '未分层')
            enriched_data.append(normalized)
        total = getattr(resp, 'count', None)
        if total is None:
            total = len(enriched_data)

        return paginated_response(
            items=enriched_data,
            total=total,
            page=page,
            page_size=limit,
            message="获取规则列表成功",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("qc_rules_query_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="查询规则失败") from exc


@router.get("/rules/document-categories/stats")
async def get_document_category_stats(request: Request):
    """获取文书类别统计信息"""
    try:
        sb = get_supabase()
        if sb is None:
            return success_response(
                data={},
                message="数据库不可用",
                trace_id=get_trace_id(request)
            )
        response = await async_execute(sb.table('qc_rules').select('primary_document_category'))
        rows = list(getattr(response, 'data', None) or [])
        stats: Dict[str, int] = {}
        for rule in rows:
            category = rule.get('primary_document_category')
            if category:
                stats[category] = stats.get(category, 0) + 1
        return success_response(
            data=stats,
            message="获取统计信息成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        print(f"获取文书类别统计失败: {e}")
        import traceback
        traceback.print_exc()
        return success_response(
            data={},
            message="获取统计信息失败",
            trace_id=get_trace_id(request)
        )

@router.get("/rules/document-categories/config")
async def get_document_category_config(request: Request):
    """获取文书类别配置"""
    try:
        sb = get_supabase()
        if sb is None:
            return success_response(
                data=[],
                message="数据库不可用",
                trace_id=get_trace_id(request)
            )
        response = await async_execute(
            sb.table('document_category_config').select('*').eq('is_active', True).order('sort_order')
        )
        rows = list(getattr(response, 'data', None) or [])
        return success_response(
            data=rows,
            message="获取配置成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        print(f"获取文书类别配置失败: {e}")
        return success_response(
            data=[],
            message="获取配置失败",
            trace_id=get_trace_id(request)
        )

@router.post("/rules", response_model=QCRule)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def create_rule(rule: QCRule, request: Request, current_user: dict = Depends(get_current_user)):
    """创建质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        body = rule.model_dump(exclude_none=True)
        body.setdefault("is_active", True)
        resp = sb.table("qc_rules").insert(body).execute()
        data = (resp.data or [body])[0]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建规则失败: {str(e)}")


@router.put("/rules/{rule_id}", response_model=QCRule)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def update_rule(rule_id: str, rule: QCRule, current_user: dict = Depends(get_current_user)):
    """更新质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        body = rule.model_dump(exclude_none=True)
        resp = sb.table("qc_rules").update(body).eq("id", rule_id).execute()
        data = resp.data or []
        if not data:
            resp2 = sb.table("qc_rules").update(body).eq("rule_code", rule_id).execute()
            data = resp2.data or []
        if not data:
            raise HTTPException(status_code=404, detail="规则不存在")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")


@router.delete("/rules/{rule_id}")
@require_admin()
async def delete_rule(request: Request, rule_id: str, current_user: dict = Depends(get_current_user)):
    """删除质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        resp = sb.table("qc_rules").delete().eq("id", rule_id).execute()
        rows = resp.data or []
        if not rows:
            resp2 = sb.table("qc_rules").delete().eq("rule_code", rule_id).execute()
            rows = resp2.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="规则不存在")
        return success_response(
            data={"rule_id": rule_id},
            message="质控规则删除成功",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除规则失败: {str(e)}")


@router.get("/history")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_history(request: Request, current_user: dict = Depends(get_current_user)):
    """获取质控历史，从 PG qc_results 表读取"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        resp = await async_execute(
            sb.table('qc_results').select('*').order('created_at', desc=True).limit(100)
        )
        rows = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询历史失败: {str(e)}")
    # 旧历史端点不返回现代三坐标结果；旧表无 identity_version 列时按旧行保留。
    items = [row for row in rows if row.get("identity_version") is None]
    return success_response(
        data={
            "items": items,
            "total": len(items)
        },
        message="获取历史记录成功",
        trace_id=get_trace_id(request)
    )


@router.get("/poc/rules")
async def poc_rules(request: Request):
    """获取 PoC 规则（演示用）"""
    return success_response(
        data={
            "rules": [
                {"id": "POC-001", "name": "主诉完整性（PoC）", "category": "基础", "severity": "minor"},
                {"id": "POC-002", "name": "诊断一致性（PoC）", "category": "诊断", "severity": "major"},
            ]
        },
        message="获取 PoC 规则成功",
        trace_id=get_trace_id(request)
    )


# ==================== 形式质控 API ====================

from ..services.frontpage_formal_qc import FrontpageFormalQC, Category as FQCategory, Severity as FQSeverity

_formal_qc_engine = FrontpageFormalQC()

# 首页形式质控是现代质控结果来源之一（见 docs/plans/2026-09-24-v36-qc-case-identity-source-design.md）。
_FORMAL_QC_SOURCE_KEY = "frontpage_formal_qc"
_FORMAL_QC_WORKFLOW_TYPE = "frontpage_qc"
# 本批临时限定：尚无用户-机构绑定，服务端按请求机构读取任意机构病例只能收窄到两个管理角色。
# 与现代病例快照读取同边界；POST 不因 GET 已受限而放宽自身权限。
_FORMAL_QC_VALIDATE_ROLES = ("admin", "qc_manager")
_FORMAL_QC_INVALID_IDENTITY_DETAIL = "首页质控身份参数不合法，请核对机构号后重试"
_FORMAL_QC_NOT_FOUND_DETAIL = "未找到该就诊的病案首页，无法执行首页质控"
_FORMAL_QC_AMBIGUOUS_DETAIL = "病案首页身份无法唯一确定，请核对机构号后重试"
_FORMAL_QC_SOURCE_UNAVAILABLE_DETAIL = "病案首页数据读取失败，请稍后重试"
_FORMAL_QC_FAILURE_DETAIL = "首页质控执行或结果保存失败，请稍后重试"
# 零规则不得以“通过”收尾：用户筛选致空按 422 明确告知，引擎未产出规则按 503 失败关闭。
_FORMAL_QC_EMPTY_SCOPE_DETAIL = "所选筛选条件未匹配任何首页质控规则，未产生质控结果"
_FORMAL_QC_PARTIAL_SCOPE_DETAIL = "正式首页质控需执行全部规则，局部筛选不能保存为病例结果"
# 队列失败态只记录固定文案，不回显模型/数据库异常文本。
_FORMAL_QC_QUEUE_FAILURE_MESSAGE = "frontpage_formal_qc_failed"


class FormalQcIdentityError(RuntimeError):
    """服务端读到的首页三坐标缺失或与请求坐标冲突。"""


def _require_runnable_formal_report(report: Any, *, scope_filtered: bool) -> None:
    """零规则或非预期报告结构不得继续落库，避免把“未执行任何规则”报告成通过。

    - 报告结构不符合 ``total_rules/passed/failed/results`` 语义：固定 503；
    - 用户筛选致零规则：固定 422（这是调用方参数问题，不是通过）；
    - 引擎在未筛选时零规则：固定 503 失败关闭。
    """

    counts = [getattr(report, name, None) for name in ("total_rules", "passed", "failed")]
    results = getattr(report, "results", None)
    if any(not isinstance(value, int) for value in counts) or not isinstance(results, list):
        logger.error("首页形式质控报告结构异常")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FORMAL_QC_FAILURE_DETAIL,
        )
    if counts[0] > 0:
        return
    if scope_filtered:
        # 用户筛选致零规则是调用方参数问题，明确 422，不当作通过。
        raise HTTPException(
            status_code=422,
            detail=_FORMAL_QC_EMPTY_SCOPE_DETAIL,
        )
    logger.error("首页形式质控未产出任何规则")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_FORMAL_QC_FAILURE_DETAIL,
    )


def _verified_formal_qc_identity(
    sheet: Any,
    *,
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str],
) -> VerifiedQCIdentity:
    """在服务端读到的首页 ``basic`` 上核实三坐标。

    - 请求里的 patient/visit（以及显式机构）只用于核对，不构成身份来源；
    - ``basic`` 三坐标任一缺失说明该行无法安全归属；
    - 与请求坐标不一致说明读到的不只是被请求的那一份首页，一律拒绝而不是按客户端坐标改写。
    """

    basic = sheet.get("basic") if isinstance(sheet, dict) else None
    if not isinstance(basic, dict):
        raise FormalQcIdentityError("frontpage sheet missing basic section")
    resolved = {
        name: str(basic.get(name) or "").strip()
        for name in ("institute_id", "patient_id", "visit_id")
    }
    if not all(resolved.values()):
        raise FormalQcIdentityError("frontpage sheet case identity is incomplete")
    for name, requested in (
        ("patient_id", patient_id),
        ("visit_id", visit_id),
        ("institute_id", institute_id),
    ):
        expected = str(requested or "").strip()
        if expected and resolved[name] != expected:
            raise FormalQcIdentityError(f"frontpage sheet {name} conflicts with request")
    try:
        return VerifiedQCIdentity(
            resolved["institute_id"],
            resolved["patient_id"],
            resolved["visit_id"],
            _FORMAL_QC_SOURCE_KEY,
        )
    except ValueError as exc:
        raise FormalQcIdentityError("frontpage sheet case identity is not usable") from exc


async def _read_verified_frontpage_sheet(
    *,
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str],
) -> tuple[Dict[str, Any], VerifiedQCIdentity]:
    """服务端直接读取病案首页并把三坐标钉在 ``basic`` 上。

    不经过 HTTP，也不采信请求体正文；域错误按固定脱敏文案映射到
    400（显式空机构）/ 404（病例缺失）/ 409（身份歧义或漂移）/ 503（取数不可用）。
    """

    try:
        sheet = await run_in_threadpool(
            get_frontpage_sheet,
            patient_id,
            visit_id,
            institute_id=institute_id,
        )
    except MedicalRecordsValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_FORMAL_QC_INVALID_IDENTITY_DETAIL,
        ) from exc
    except MedicalRecordsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_FORMAL_QC_NOT_FOUND_DETAIL,
        ) from exc
    except MedicalRecordsConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_FORMAL_QC_AMBIGUOUS_DETAIL,
        ) from exc
    except (MedicalRecordsSourceUnavailableError, MedicalRecordsStorageError) as exc:
        logger.warning("首页形式质控取数失败: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FORMAL_QC_SOURCE_UNAVAILABLE_DETAIL,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        # 不回显 str(exc)：底层异常可能带连接串或患者标识。
        logger.warning("首页形式质控取数异常: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FORMAL_QC_SOURCE_UNAVAILABLE_DETAIL,
        ) from exc

    if not isinstance(sheet, dict) or not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_FORMAL_QC_NOT_FOUND_DETAIL,
        )
    try:
        identity = _verified_formal_qc_identity(
            sheet,
            patient_id=patient_id,
            visit_id=visit_id,
            institute_id=institute_id,
        )
    except FormalQcIdentityError as exc:
        logger.warning("首页形式质控身份核对失败: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_FORMAL_QC_AMBIGUOUS_DETAIL,
        ) from exc
    return sheet, identity


@router.post("/formal-qc/validate")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.CREATE)
async def validate_frontpage_formal(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(require_roles(*_FORMAL_QC_VALIDATE_ROLES)),
):
    """
    对病案首页执行形式质控校验。

    POST body:
    {
        "patient_id": "...", "visit_id": "...",   // 必需：服务端据此读取正式首页
        "institute_id": "...",                    // 可选：省略时仅在 patient+visit 唯一时推断
        "frontpage": { ... }                       // 兼容接收，但不参与取数与判定
    }

    服务端以 ``get_frontpage_sheet(patient_id, visit_id, institute_id?)`` 读取正式首页，
    并以读到的 ``basic`` 三坐标作为唯一权威身份执行 FrontpageFormalQC；客户端正文不再被信任。
    队列 start/finish 与结果落库共用该核实身份及 ``source_key=frontpage_formal_qc``。
    失败语义（固定脱敏文案）：身份参数不合法 400、病例缺失 404、身份歧义/漂移 409、取数或落库不可用 503；
    正式落库不接受局部规则筛选（422）；引擎零规则或报告结构异常返回 503。
    任一步失败都不写结果、不进队列成功态。结果已落库后队列收尾失败不改变“已保存”事实。
    """
    patient_id = str(payload.get("patient_id") or "").strip()
    visit_id = str(payload.get("visit_id") or "").strip()
    raw_institute_id = payload.get("institute_id")
    if raw_institute_id is not None and not str(raw_institute_id).strip():
        # 显式空机构不猜：机构坐标必须来自请求或唯一推断。
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_FORMAL_QC_INVALID_IDENTITY_DETAIL,
        )
    institute_id = str(raw_institute_id).strip() if raw_institute_id is not None else None
    if not patient_id or not visit_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_FORMAL_QC_INVALID_IDENTITY_DETAIL,
        )
    raw_categories = payload.get("categories", [])
    raw_severities = payload.get("severities", [])
    if not all(
        isinstance(value, list) and all(isinstance(item, str) for item in value)
        for value in (raw_categories, raw_severities)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_FORMAL_QC_INVALID_IDENTITY_DETAIL,
        )
    try:
        categories = [FQCategory(c) for c in raw_categories] or None
        severities = [FQSeverity(s) for s in raw_severities] or None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_FORMAL_QC_INVALID_IDENTITY_DETAIL,
        ) from exc
    if categories or severities:
        raise HTTPException(status_code=422, detail=_FORMAL_QC_PARTIAL_SCOPE_DETAIL)

    user_id = _current_user_id(current_user)
    run_id: Optional[str] = None
    persisted = False

    # 取数与身份核实先于任何队列/落库动作：身份不成立时不产生任何副作用。
    sheet, identity = await _read_verified_frontpage_sheet(
        patient_id=patient_id,
        visit_id=visit_id,
        institute_id=institute_id,
    )

    try:
        # 队列以现代身份启动：source_key + 三坐标，不再用请求体 visit 落 legacy。
        run_id = default_workflow_queue_state_service.start_run(
            workflow_type=_FORMAL_QC_WORKFLOW_TYPE,
            visit_id=identity.visit_id,
            patient_id=identity.patient_id,
            institute_id=identity.institute_id,
            source_key=_FORMAL_QC_SOURCE_KEY,
            user_id=user_id,
        )

        report = _formal_qc_engine.validate(sheet, categories=categories, severities=severities)
        # 零规则报告不是“通过”：筛选致空 422、引擎零规则 503，一律不落现代结果。
        _require_runnable_formal_report(
            report, scope_filtered=bool(categories or severities)
        )
        persistence_result = _build_formal_qc_persistence_result(sheet, report, payload, identity)
        persistence = await default_qc_persistence_service.persist_analysis(
            persistence_result,
            actor=current_user,
            verified_identity=identity,
        )
        persisted = True

        try:
            default_workflow_queue_state_service.finish_success(
                workflow_type=_FORMAL_QC_WORKFLOW_TYPE,
                visit_id=identity.visit_id,
                run_id=run_id,
                source_key=_FORMAL_QC_SOURCE_KEY,
                patient_id=identity.patient_id,
                institute_id=identity.institute_id,
                user_id=user_id,
            )
        except Exception:
            # 结果已落库：队列收尾失败只记日志，不能把已保存的质控谎报成未保存。
            logger.warning("首页形式质控队列成功收尾失败（结果已保存）")

        return success_response(
            data={
                "total_rules": report.total_rules,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": round(report.passed / report.total_rules * 100, 1) if report.total_rules else 0,
                "results": [
                    {
                        "rule_id": r.rule_id,
                        "field_name": r.field_name,
                        "rule_name": r.rule_name,
                        "passed": r.passed,
                        "message": r.message,
                        "severity": r.severity.value,
                        "category": r.category.value,
                    }
                    for r in report.results
                    if not r.passed  # 只返回失败项
                ],
                "persistence": persistence,
            },
            message=f"形式质控完成：{report.passed}/{report.total_rules} 通过",
            trace_id=get_trace_id(request),
        )
    except Exception as exc:
        if run_id and not persisted:
            try:
                default_workflow_queue_state_service.finish_failed(
                    workflow_type=_FORMAL_QC_WORKFLOW_TYPE,
                    visit_id=identity.visit_id,
                    run_id=run_id,
                    source_key=_FORMAL_QC_SOURCE_KEY,
                    patient_id=identity.patient_id,
                    institute_id=identity.institute_id,
                    error_message=_FORMAL_QC_QUEUE_FAILURE_MESSAGE,
                    user_id=user_id,
                )
            except Exception:
                logger.warning("首页形式质控队列失败收尾异常")
        if isinstance(exc, HTTPException):
            raise
        # 缺迁移列、取数不可用等底层异常一律回固定文案，不把连接串或患者标识带出接口。
        logger.error("首页形式质控执行失败: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FORMAL_QC_FAILURE_DETAIL,
        ) from exc


@router.get("/formal-qc/stats")
async def get_formal_qc_stats(request: Request):
    """获取形式质控规则统计。"""
    stats = _formal_qc_engine.get_stats()
    return success_response(
        data=stats,
        message="获取形式质控规则统计成功",
        trace_id=get_trace_id(request),
    )


@router.get("/formal-qc/rules")
async def list_formal_qc_rules(request: Request):
    """获取全部形式质控规则列表（用于前端展示规则说明）。"""
    rules_data = [
        {
            "rule_id": r.rule_id,
            "field_name": r.field_name,
            "rule_name": r.rule_name,
            "description": r.description,
            "severity": r.severity.value,
            "category": r.category.value,
        }
        for r in _formal_qc_engine.rules
    ]
    return success_response(
        data=rules_data,
        message=f"共 {len(rules_data)} 条形式质控规则",
        trace_id=get_trace_id(request),
    )


@router.get("/formal-qc/rule-coverage")
async def get_formal_qc_rule_coverage(request: Request):
    """获取首页与医保结算清单正式质控规则覆盖审计报告。"""
    from ..services.qc_rule_coverage import build_rule_coverage_report

    report = build_rule_coverage_report()
    return success_response(
        data=report,
        message="获取正式质控规则覆盖审计成功",
        trace_id=get_trace_id(request),
    )


# ==================== 编码质控规则管理 API ====================

def _load_coding_rules() -> list:
    """从正式目录 owner 加载编码质控点。"""
    return [dict(item) for item in load_coding_rule_catalog()]


@router.get("/coding-rules")
async def list_coding_rules(
    request: Request,
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    severity: Optional[str] = Query(None, description="严重程度"),
    source: Optional[str] = Query(None, description="规则来源"),
):
    """获取编码质控规则列表，并叠加当前发布版本的启停状态。"""
    version = await run_in_threadpool(current_version, CODING_RULE_SET_KEY)
    resolution = await run_in_threadpool(resolve_rule_set_version, CODING_RULE_SET_KEY, version)
    state_by_id = {
        rule_id: state
        for state, key in (("active", "active_rule_ids"), ("paused", "paused_rule_ids"),
                           ("offline", "excluded_rule_ids"), ("deleted", "deleted_rule_ids"))
        for rule_id in resolution.get(key, [])
    }
    rules = [
        {
            **rule,
            "state": state_by_id.get(rule["rule_id"], "paused"),
            "is_active": state_by_id.get(rule["rule_id"]) == "active",
        }
        for rule in _load_coding_rules()
    ]

    # 筛选
    if keyword:
        kw = keyword.lower()
        rules = [r for r in rules if kw in r.get("name", "").lower()
                 or kw in r.get("description", "").lower()
                 or kw in r.get("rule_id", "").lower()]
    if category:
        rules = [r for r in rules if r.get("category") == category]
    if severity:
        rules = [r for r in rules if r.get("severity") == severity]
    if source:
        rules = [r for r in rules if r.get("source") == source]

    # 统计信息
    all_rules = [
        {
            **rule,
            "state": state_by_id.get(rule["rule_id"], "paused"),
            "is_active": state_by_id.get(rule["rule_id"]) == "active",
        }
        for rule in _load_coding_rules()
    ]
    total_rule_count = sum(r.get("rule_count", 0) for r in all_rules)
    categories_set = set(r.get("category") for r in all_rules)
    severity_counts = {}
    source_counts = {}
    for r in all_rules:
        s = r.get("severity", "info")
        severity_counts[s] = severity_counts.get(s, 0) + 1
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return success_response(
        data={
            "items": rules,
            "total": len(rules),
            "rule_set_key": CODING_RULE_SET_KEY,
            "rule_set_version": version,
            "statistics": {
                "total_types": len(all_rules),
                "total_rule_count": total_rule_count,
                "categories": len(categories_set),
                "severity_counts": severity_counts,
                "source_counts": source_counts,
            }
        },
        message=f"获取编码质控规则成功（{len(rules)} 条）",
        trace_id=get_trace_id(request),
    )


# ==================== 编码质控 API ====================

from ..services.coding_qc_service import CodingQCEngine

# 编码质控引擎（LLM 客户端延迟初始化）
_coding_qc_engine: Optional[CodingQCEngine] = None


def _get_coding_qc_engine() -> CodingQCEngine:
    """获取或初始化编码质控引擎。"""
    global _coding_qc_engine
    if _coding_qc_engine is None:
        try:
            from ..services.qc_llm_client import SichuanQCLLMClient
            llm_client = SichuanQCLLMClient()
            _coding_qc_engine = CodingQCEngine(llm_client=llm_client)
            logger.info("编码质控引擎初始化完成（规则层 + LLM 层）")
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败，编码质控仅使用规则层: {e}")
            _coding_qc_engine = CodingQCEngine(llm_client=None)
    return _coding_qc_engine


class CodingQcIdentityAmbiguousError(RuntimeError):
    """同一就诊在三坐标上存在多个候选，无法确定唯一病例身份。"""


class CodingQcSourceUnavailableError(RuntimeError):
    """编码质控取数依赖的数据库不可用或读取失败。"""


@dataclass(frozen=True)
class CodingQcIdentity:
    """编码质控被分析数据的唯一三坐标。"""

    institute_id: str
    patient_id: str
    visit_id: str


def _has_evaluable_coding_data(frontpage: Dict[str, Any]) -> bool:
    """是否存在可供规则层判定的诊断/手术编码数据。"""
    diagnoses = frontpage.get("diagnoses")
    surgeries = frontpage.get("surgeries")
    if isinstance(diagnoses, list) and diagnoses:
        return True
    if isinstance(surgeries, list) and surgeries:
        return True
    return False


def _resolve_coding_qc_identity(
    patient_id: Optional[str],
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Optional[CodingQcIdentity]:
    """
    在编码质控唯一权威表 ``cdm.mr`` 上确立被分析数据的三坐标。

    - 权威来源只有 cdm.mr，与落库侧的“唯一 cdm.mr 行”合同一致；诊断/手术/费用表不参与定身份。
    - 显式限定 ``cdm.mr`` 并参数化，不经 search_path 解析，避免把 public.mr 当成权威表。
    - 显式机构：按机构精确匹配，只在候选为空时判定缺失。
    - 未给机构：只允许唯一候选推断；多个机构同时命中时报歧义，不猜机构。
    - 同一三坐标出现重复行、或候选三坐标不完整（缺机构/缺患者）时一律拒绝，不降级猜测。
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from ..database.connection import engine as db_engine

    visit_key = str(visit_id or "").strip()
    if not visit_key:
        return None
    patient_key = str(patient_id or "").strip()
    institute_key = str(institute_id or "").strip()

    sql = "SELECT institute_id, patient_id FROM cdm.mr WHERE visit_id = :visit_id"
    params: Dict[str, Any] = {"visit_id": visit_key}
    if patient_key:
        sql += " AND patient_id = :patient_id"
        params["patient_id"] = patient_key
    if institute_key:
        sql += " AND institute_id = :institute_id"
        params["institute_id"] = institute_key
    # LIMIT 2 保留“同三坐标重复行也算歧义”的判定，不需要 DISTINCT。
    sql += " LIMIT 2"

    try:
        with Session(db_engine) as session:
            rows = session.execute(text(sql), params).all()
    except Exception as exc:
        # 不把底层 DSN/驱动细节暴露给调用方与队列状态。
        logger.warning("编码质控三坐标解析失败: 编码来源读取异常")
        raise CodingQcSourceUnavailableError("编码质控数据读取失败") from exc

    candidates = [
        (str(row[0] or "").strip(), str(row[1] or "").strip())
        for row in rows
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        # 同 visit 命中不同病例（或同三坐标重复行）时拒绝，交由调用方要求显式机构。
        raise CodingQcIdentityAmbiguousError("编码质控病例身份不唯一")
    resolved_institute_id, resolved_patient_id = candidates[0]
    if not resolved_institute_id or not resolved_patient_id:
        # 三坐标缺一不可：空机构/空患者无法构成可核验身份，禁止当作可写入身份。
        raise CodingQcIdentityAmbiguousError("编码质控病例身份不完整")
    return CodingQcIdentity(resolved_institute_id, resolved_patient_id, visit_key)


@router.post("/coding-qc/check")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def check_coding_qc(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """
    对病案首页执行编码规范质控。

    POST body 支持两种模式：
    1. visit_id 模式（推荐）：直接从 PG 数据库读取诊断/手术数据
       {"visit_id": "xxx", "patient_id": "xxx"}
    2. frontpage 模式（兼容旧版）：前端手动传入首页数据
       {"frontpage": { ... 首页数据字典 ... }}

    visit_id 模式下取数、队列状态、结果写入与模型观测共用同一个服务端解析身份
    （唯一权威表 cdm.mr）；客户端坐标不作为身份依据。
    """
    visit_id = payload.get("visit_id")
    patient_id = payload.get("patient_id")
    skip_llm = payload.get("skip_llm", False)
    user_id = _current_user_id(current_user)
    run_id: Optional[str] = None
    identity: Optional[CodingQcIdentity] = None

    try:
        frozen_version = await run_in_threadpool(current_version, CODING_RULE_SET_KEY)
        frozen_resolution = await run_in_threadpool(
            resolve_rule_set_version, CODING_RULE_SET_KEY, frozen_version,
        )
        frozen_active_rule_ids = list(frozen_resolution["active_rule_ids"])
        if visit_id:
            # === 1) 服务端以 cdm.mr 为唯一权威确立三坐标 ===
            try:
                identity = _resolve_coding_qc_identity(
                    patient_id, visit_id, payload.get("institute_id")
                )
            except CodingQcIdentityAmbiguousError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="编码质控病例身份无法唯一确定，请核对机构号后重试",
                ) from exc
            except CodingQcSourceUnavailableError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="编码质控数据读取失败，请稍后重试",
                ) from exc
            if identity is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="未找到该就诊的编码数据，无法执行编码质控",
                )

            # === 2) 队列以现代身份启动：source_key + 三坐标，不再用请求体 visit ===
            run_id = default_workflow_queue_state_service.start_run(
                workflow_type="coding_qc",
                visit_id=identity.visit_id,
                patient_id=identity.patient_id,
                institute_id=identity.institute_id,
                source_key="coding_qc",
                user_id=user_id,
            )

            # === 3) 取数与后续判定一律使用同一解析身份 ===
            try:
                frontpage = _load_frontpage_from_pg(identity)
            except CodingQcSourceUnavailableError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="编码质控数据读取失败，请稍后重试",
                ) from exc
            if not frontpage:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="未找到该就诊的编码数据，无法执行编码质控",
                )
            if not _has_evaluable_coding_data(frontpage):
                # 没有可判定的编码事实时，不允许以“通过”结束。
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="该就诊无可评估的诊断/手术编码数据，无法执行编码质控",
                )
        else:
            # === 兼容旧版：从请求体读取（客户端自带数据不构成已验证身份） ===
            frontpage = payload.get("frontpage") or payload

        engine = _get_coding_qc_engine()

        # 观测上下文记录的是服务端解析身份；旧手工模式无已验证身份，才退回请求体坐标。
        observation_identity = (
            identity
            if identity is not None
            else CodingQcIdentity(
                str(payload.get("institute_id") or ""),
                str(patient_id or ""),
                str(visit_id or ""),
            )
        )
        with llm_observation_context(
            business_scene="coding_qc",
            root_job_id=run_id or get_trace_id(request),
            record_identity=(
                observation_identity.institute_id,
                observation_identity.patient_id,
                observation_identity.visit_id,
            ),
            executor_key="coding_qc_engine",
        ):
            if skip_llm:
                temp_engine = CodingQCEngine(llm_client=None)
                report = await temp_engine.run_all(
                    frontpage,
                    rule_set_version=frozen_version,
                    rule_set_content_digest=str(frozen_resolution["content_digest"]),
                    active_rule_ids=frozen_active_rule_ids,
                )
            else:
                report = await engine.run_all(
                    frontpage,
                    rule_set_version=frozen_version,
                    rule_set_content_digest=str(frozen_resolution["content_digest"]),
                    active_rule_ids=frozen_active_rule_ids,
                )
        report_dict = report.to_dict()
        persistence_result = _build_coding_qc_persistence_result(
            payload,
            report_dict,
            semantic_completed=report.semantic_completed,
            identity=identity,
        )
        persistence = await default_qc_persistence_service.persist_analysis(
            persistence_result,
            actor=current_user,
            verified_identity=(
                VerifiedQCIdentity(
                    identity.institute_id,
                    identity.patient_id,
                    identity.visit_id,
                    "coding_qc",
                )
                if identity is not None
                else None
            ),
        )

        if run_id and identity is not None:
            default_workflow_queue_state_service.finish_success(
                workflow_type="coding_qc",
                visit_id=identity.visit_id,
                run_id=run_id,
                source_key="coding_qc",
                patient_id=identity.patient_id,
                institute_id=identity.institute_id,
                user_id=user_id,
            )

        return success_response(
            data={
                **report_dict,
                "persistence": persistence,
            },
            message=f"编码质控完成：{report.overall_assessment}（{report.total_issues} 个问题）",
            trace_id=get_trace_id(request),
        )
    except Exception as exc:
        public_error = (
            exc
            if isinstance(exc, HTTPException)
            else HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="编码质控执行或结果保存失败，请稍后重试",
            )
        )
        if run_id and identity is not None:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="coding_qc",
                visit_id=identity.visit_id,
                run_id=run_id,
                source_key="coding_qc",
                patient_id=identity.patient_id,
                institute_id=identity.institute_id,
                error_message=str(public_error.detail),
                user_id=user_id,
            )
        if isinstance(exc, HTTPException):
            raise
        raise public_error from exc


def _load_frontpage_from_pg(
    identity: CodingQcIdentity,
) -> Optional[Dict[str, Any]]:
    """
    从 PG 数据库直接读取诊断和手术编码数据，组装为质控引擎所需的 frontpage 格式。

    只接受调用方已解析的唯一三坐标（见 ``_resolve_coding_qc_identity``），本函数不再二次定身份。
    首页、诊断（含 mr_diagnosis 兜底）、手术、费用一律按同一三坐标读取，避免跨机构混读；
    所有编码来源表都显式限定 ``cdm`` 并参数化，不经 search_path 解析，避免读到 public 同名表；
    数据库读取失败按“取数不可用”抛出，绝不返回 None 让调用方按“通过”收尾。
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from ..database.connection import engine as db_engine

    coordinates = {
        "institute_id": identity.institute_id,
        "patient_id": identity.patient_id,
        "visit_id": identity.visit_id,
    }

    try:
        with Session(db_engine) as session:
            # 查询首页基本信息
            fp = session.execute(
                text(
                    "SELECT * FROM cdm.mr "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id "
                    "AND visit_id = :visit_id "
                    "LIMIT 1"
                ),
                coordinates,
            ).mappings().first()

            # 查询诊断列表
            diag_rows = [
                dict(row)
                for row in session.execute(
                    text(
                        "SELECT * FROM cdm.diagnosis "
                        "WHERE institute_id = :institute_id "
                        "AND patient_id = :patient_id "
                        "AND visit_id = :visit_id"
                    ),
                    coordinates,
                ).mappings().all()
            ]

            if not diag_rows:
                mr_diag_sql = (
                    "SELECT * FROM cdm.mr_diagnosis "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id "
                    "AND visit_id = :visit_id "
                    "AND COALESCE(is_deleted, '0') <> '1' "
                    "ORDER BY diagnosis_id"
                )
                diag_rows = [
                    dict(row)
                    for row in session.execute(text(mr_diag_sql), coordinates).mappings().all()
                ]

            # 查询手术列表
            surg_rows = [
                dict(row)
                for row in session.execute(
                    text(
                        "SELECT * FROM cdm.mr_surgery "
                        "WHERE institute_id = :institute_id "
                        "AND patient_id = :patient_id "
                        "AND visit_id = :visit_id"
                    ),
                    coordinates,
                ).mappings().all()
            ]

            # 查询费用信息，供病理诊断费一致性规则使用
            cost = session.execute(
                text(
                    "SELECT * FROM cdm.mr_cost "
                    "WHERE institute_id = :institute_id "
                    "AND patient_id = :patient_id "
                    "AND visit_id = :visit_id "
                    "LIMIT 1"
                ),
                coordinates,
            ).mappings().first()

            if not fp and not diag_rows and not surg_rows:
                return None

            # 组装诊断（出院主诊断排第一）
            def _row_value(row: Any, key: str) -> Any:
                if isinstance(row, dict):
                    return row.get(key)
                return getattr(row, key, None)

            def _parse_diag_no(v: Any) -> int:
                text_value = str(v or "").strip()
                if not text_value:
                    return 9999
                text_value = text_value.rsplit("||", 1)[-1]
                match = re.search(r"\d+", text_value)
                if match:
                    return int(match.group(0))
                try:
                    return int(text_value)
                except Exception:
                    return 9999

            def _diag_sort_key(row: Any) -> tuple[int, int, str]:
                diag_type = str(_row_value(row, "diagnosis_type") or "").strip()
                diag_type_l = diag_type.lower()
                diag_no = _parse_diag_no(_row_value(row, "diagnosis_no"))
                diag_main = str(_row_value(row, "diagnosis_main") or "").strip().lower()
                diagnosis_code = str(_row_value(row, "diagnosis_code") or "").strip().upper()
                diagnosis_id = str(_row_value(row, "diagnosis_id") or "")

                is_discharge = ("出院" in diag_type) or ("discharge" in diag_type_l)
                is_pathology = (
                    ("病理" in diag_type)
                    or ("pathology" in diag_type_l)
                    or diagnosis_code.startswith("M")
                )
                is_main = (
                    diag_main in {"是", "1", "y", "yes", "true", "t", "main"}
                    or ("主诊断" in diag_type)
                    or ("主要诊断" in diag_type)
                    or ("出院主要" in diag_type)
                    or ("discharge_main" in diag_type_l)
                    or ("main_discharge" in diag_type_l)
                    or (diag_type_l in {"main", "primary"})
                )
                is_other = (
                    ("其他" in diag_type)
                    or ("次诊断" in diag_type)
                    or ("other" in diag_type_l)
                    or ("secondary" in diag_type_l)
                )

                if is_discharge and is_main:
                    return (0, diag_no, diagnosis_id)
                if is_discharge and is_other:
                    return (1, diag_no, diagnosis_id)
                if is_discharge:
                    return (2, diag_no, diagnosis_id)
                if is_pathology:
                    return (3, diag_no, diagnosis_id)
                if diag_no == 1 and is_main:
                    return (4, diag_no, diagnosis_id)
                if diag_no == 1:
                    return (5, diag_no, diagnosis_id)
                if is_main:
                    return (6, diag_no, diagnosis_id)
                return (7, diag_no, diagnosis_id)

            sorted_diag_rows = sorted(diag_rows, key=_diag_sort_key)
            has_discharge_diagnosis = any(
                "出院" in str(_row_value(row, "diagnosis_type") or "")
                or "discharge" in str(_row_value(row, "diagnosis_type") or "").lower()
                for row in sorted_diag_rows
            )
            if has_discharge_diagnosis:
                sorted_diag_rows = [
                    row
                    for row in sorted_diag_rows
                    if (
                        "出院" in str(_row_value(row, "diagnosis_type") or "")
                        or "discharge" in str(_row_value(row, "diagnosis_type") or "").lower()
                        or "病理" in str(_row_value(row, "diagnosis_type") or "")
                        or str(_row_value(row, "diagnosis_code") or "").strip().upper().startswith("M")
                    )
                ]

            diagnoses = []
            for d in sorted_diag_rows:
                diagnoses.append({
                    "code": _row_value(d, "diagnosis_code") or "",
                    "name": _row_value(d, "diagnosis_name") or "",
                    "type": _row_value(d, "diagnosis_type") or "",
                    "admission_condition": _row_value(d, "admission_condition") or "",
                })

            # 组装手术（主手术排第一）
            def _is_main_surgery_flag(v: Any) -> bool:
                text = str(v or "").strip().lower()
                return text in {"1", "是", "y", "yes", "true", "t", "main", "主"}

            surgeries = []
            main_surgeries = [
                s for s in surg_rows if _is_main_surgery_flag(_row_value(s, "main_surgery_sign"))
            ]
            other_surgeries = [
                s for s in surg_rows if not _is_main_surgery_flag(_row_value(s, "main_surgery_sign"))
            ]
            for s in main_surgeries + other_surgeries:
                surgeries.append({
                    "code": _row_value(s, "surgery_code") or "",
                    "name": _row_value(s, "surgery_name") or "",
                })

            return {
                "sex": _row_value(fp, "sex") if fp else "",
                "age": _row_value(fp, "age_year") if fp else "",
                "diagnoses": diagnoses,
                "surgeries": surgeries,
                "fees": {
                    "pathology_diagnostic_fee": (
                        _row_value(cost, "pathological_diagnostic_fee") if cost else ""
                    ),
                },
                "clinical_summary": "",
            }

    except Exception as exc:
        # 取数失败按不可用上报（调用方转 503），不返回 None 让上层误判为“通过”。
        logger.warning("从 PG 读取编码质控数据失败: 编码来源读取异常")
        raise CodingQcSourceUnavailableError("编码质控数据读取失败") from exc
