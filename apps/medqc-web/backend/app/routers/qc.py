import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Query, Request, Depends

from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.security import get_current_user
from ..core.permissions import (
    require_permission,
    require_role,
    require_admin,
    ResourceType,
    PermissionAction,
    UserRole,
)

router = APIRouter(prefix="/api/v1/qc", tags=["qc"])
service = QCService()

import logging as _logging
logger = _logging.getLogger(__name__)


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


async def _save_qc_result(record_id: str, result: Dict[str, Any]) -> None:
    """将质控分析结果写入 PG qc_results 表。失败时记录日志但不阻塞主流程。"""
    sb = get_supabase()
    if sb is None:
        logger.warning(f"[qc] 数据库不可用，qc_results 未持久化: record_id={record_id}")
        return
    try:
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        raw_output = json.dumps(result, ensure_ascii=False)
        metadata = result.get("metadata")
        payload = {
            "record_id": record_id,
            "overall_score": result.get("overall_score") or result.get("score"),
            "grade": result.get("overall_grade") or result.get("grade"),
            "status": result.get("status", "completed"),
            "analysis_date": result.get("analysis_date"),
            "analysis_engine": (metadata or {}).get("engine") if isinstance(metadata, dict) else "demo-qc-engine",
            "issues": issues,
            "defect_count": len(issues),
            "metadata": metadata if isinstance(metadata, dict) else {},
            "raw_output": raw_output,
        }
        # 移除 None 值
        payload = {k: v for k, v in payload.items() if v is not None}
        await async_execute(sb.table("qc_results").insert(payload))
    except Exception as e:
        logger.warning(f"[qc] 写入 qc_results 失败（非阻塞）: {e}")


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
            await _save_qc_result(rid, res)
            started.append({"record_id": rid, "status": "completed", "analysis_id": res.get("id")})
    else:
        record_ids: List[str] = payload.get("record_ids", [])
        for rid in record_ids:
            res = await service.evaluate({"record_id": rid})
            await _save_qc_result(rid, res)
            started.append({"record_id": rid, "status": "completed", "analysis_id": res.get("id")})

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
    await _save_qc_result(record_id, result)
    analysis_id = result.get("id") or f"analysis-{uuid.uuid4().hex[:8]}"

    return success_response(
        data={
            "analysis_id": analysis_id,
            "status": "completed",
            "record_id": record_id,
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
    if not data:
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
            query = query.order('primary_document_category').order('execution_order').order('name')

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        total = getattr(resp, 'count', None)
        if total is None:
            total = len(data)

        return paginated_response(
            items=data,
            total=total,
            page=page,
            page_size=limit,
            message="获取规则列表成功",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询 qc_rules 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询规则失败: {str(e)}")


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
async def get_history(request: Request):
    """获取质控历史，从 PG qc_results 表读取"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        resp = await async_execute(
            sb.table('qc_results').select('*').order('created_at', desc=True).limit(100)
        )
        items = list(getattr(resp, 'data', None) or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询历史失败: {str(e)}")
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


@router.post("/formal-qc/validate")
async def validate_frontpage_formal(
    request: Request,
    payload: Dict[str, Any],
):
    """
    对病案首页执行形式质控校验。

    POST body:
    {
        "frontpage": { ... 首页数据字典 ... },
        "categories": ["required", "format"],  // 可选，按类别过滤
        "severities": ["error"]                // 可选，按严重度过滤
    }
    """
    frontpage = payload.get("frontpage") or payload
    categories = None
    severities = None

    if "categories" in payload and payload["categories"]:
        categories = [FQCategory(c) for c in payload["categories"]]
    if "severities" in payload and payload["severities"]:
        severities = [FQSeverity(s) for s in payload["severities"]]

    report = _formal_qc_engine.validate(frontpage, categories=categories, severities=severities)

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
        },
        message=f"形式质控完成：{report.passed}/{report.total_rules} 通过",
        trace_id=get_trace_id(request),
    )


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


# ==================== 编码质控规则管理 API ====================

import os as _os

def _load_coding_rules() -> list:
    """从 JSON 文件加载编码质控规则数据。"""
    json_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)),
        "data", "coding_rules.json"
    )
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载编码质控规则失败: {e}")
        return []


@router.get("/coding-rules")
async def list_coding_rules(
    request: Request,
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    severity: Optional[str] = Query(None, description="严重程度"),
    source: Optional[str] = Query(None, description="规则来源"),
):
    """获取编码质控规则列表（从 JSON 文件加载）。"""
    rules = _load_coding_rules()

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
    all_rules = _load_coding_rules()
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

import logging as _logging
logger = _logging.getLogger(__name__)

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


@router.post("/coding-qc/check")
async def check_coding_qc(
    request: Request,
    payload: Dict[str, Any],
):
    """
    对病案首页执行编码规范质控。

    POST body 支持两种模式：
    1. visit_id 模式（推荐）：直接从 PG 数据库读取诊断/手术数据
       {"visit_id": "xxx", "patient_id": "xxx"}
    2. frontpage 模式（兼容旧版）：前端手动传入首页数据
       {"frontpage": { ... 首页数据字典 ... }}
    """
    visit_id = payload.get("visit_id")
    patient_id = payload.get("patient_id")
    skip_llm = payload.get("skip_llm", False)

    if visit_id:
        # === 从 PG 直接读取诊断和手术数据 ===
        frontpage = _load_frontpage_from_pg(patient_id, visit_id)
        if not frontpage:
            return success_response(
                data={"total_issues": 0, "errors": 0, "warnings": 0, "infos": 0,
                      "rule_issues": [], "llm_issues": [], "overall_assessment": "通过"},
                message="编码质控完成：该患者无诊断/手术编码数据",
                trace_id=get_trace_id(request),
            )
    else:
        # === 兼容旧版：从请求体读取 ===
        frontpage = payload.get("frontpage") or payload

    engine = _get_coding_qc_engine()

    if skip_llm:
        temp_engine = CodingQCEngine(llm_client=None)
        report = await temp_engine.run_all(frontpage)
    else:
        report = await engine.run_all(frontpage)

    return success_response(
        data=report.to_dict(),
        message=f"编码质控完成：{report.overall_assessment}（{report.total_issues} 个问题）",
        trace_id=get_trace_id(request),
    )


def _load_frontpage_from_pg(patient_id: Optional[str], visit_id: str) -> Optional[Dict[str, Any]]:
    """从 PG 数据库直接读取诊断和手术编码数据，组装为质控引擎所需的 frontpage 格式。"""
    from sqlalchemy.orm import Session
    from ..database.connection import engine as db_engine
    from ..database.models.cdm import (
        MedicalRecordFrontpage, Diagnosis, MrSurgery
    )

    try:
        with Session(db_engine) as session:
            # 查询首页基本信息
            fp_query = session.query(MedicalRecordFrontpage).filter_by(visit_id=visit_id)
            if patient_id:
                fp_query = fp_query.filter_by(patient_id=patient_id)
            fp = fp_query.first()

            # 查询诊断列表
            diag_query = session.query(Diagnosis).filter_by(visit_id=visit_id)
            if patient_id:
                diag_query = diag_query.filter_by(patient_id=patient_id)
            diag_rows = diag_query.all()

            # 查询手术列表
            surg_query = session.query(MrSurgery).filter_by(visit_id=visit_id)
            if patient_id:
                surg_query = surg_query.filter_by(patient_id=patient_id)
            surg_rows = surg_query.all()

            if not fp and not diag_rows and not surg_rows:
                return None

            # 组装诊断（出院主诊断排第一）
            def _parse_diag_no(v: Any) -> int:
                try:
                    return int(str(v).strip())
                except Exception:
                    return 9999

            def _diag_sort_key(row: Any) -> tuple[int, int]:
                diag_type = str(getattr(row, "diagnosis_type", "") or "").strip()
                diag_type_l = diag_type.lower()
                diag_no = _parse_diag_no(getattr(row, "diagnosis_no", None))

                is_discharge = ("出院" in diag_type) or ("discharge" in diag_type_l)
                is_main = (
                    ("主诊断" in diag_type)
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
                    return (0, diag_no)
                if diag_no == 1 and is_main:
                    return (1, diag_no)
                if diag_no == 1:
                    return (2, diag_no)
                if is_main:
                    return (3, diag_no)
                if is_discharge and diag_no == 1:
                    return (4, diag_no)
                if is_discharge and is_other:
                    return (5, diag_no)
                if is_discharge:
                    return (6, diag_no)
                return (7, diag_no)

            sorted_diag_rows = sorted(diag_rows, key=_diag_sort_key)

            diagnoses = []
            for d in sorted_diag_rows:
                diagnoses.append({
                    "code": d.diagnosis_code or "",
                    "name": d.diagnosis_name or "",
                    "type": d.diagnosis_type or "",
                })

            # 组装手术（主手术排第一）
            def _is_main_surgery_flag(v: Any) -> bool:
                text = str(v or "").strip().lower()
                return text in {"1", "是", "y", "yes", "true", "t", "main", "主"}

            surgeries = []
            main_surgeries = [s for s in surg_rows if _is_main_surgery_flag(s.main_surgery_sign)]
            other_surgeries = [s for s in surg_rows if not _is_main_surgery_flag(s.main_surgery_sign)]
            for s in main_surgeries + other_surgeries:
                surgeries.append({
                    "code": s.surgery_code or "",
                    "name": s.surgery_name or "",
                })

            return {
                "sex": fp.sex if fp else "",
                "age": fp.age_year if fp else "",
                "diagnoses": diagnoses,
                "surgeries": surgeries,
                "clinical_summary": "",
            }

    except Exception as e:
        logger.warning(f"从 PG 读取编码质控数据失败: {e}")
        return None
