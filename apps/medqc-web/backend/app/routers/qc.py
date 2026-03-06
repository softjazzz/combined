import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Query, Request, Depends

from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..storage.memory import qc_results_db, qc_rules_db
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
            qc_results_db[rid] = res
            started.append({"record_id": rid, "status": "completed", "analysis_id": res.get("id")})
    else:
        record_ids: List[str] = payload.get("record_ids", [])
        for rid in record_ids:
            res = await service.evaluate({"record_id": rid})
            qc_results_db[rid] = res
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
    qc_results_db[record_id] = result
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
    """获取质控结果"""
    res = qc_results_db.get(record_id)
    if not res:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="质控结果不存在"
        )
    return res


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
    """获取质控规则列表。
    - 首选使用 Supabase；
    - Supabase 不可用或为空时，回退到 JSON 文件。
    """
    rules: List[Dict[str, Any]] = []

    # ── 1. 尝试从 Supabase 加载 ──
    sb = get_supabase()
    if sb is not None:
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

            if data:
                return paginated_response(
                    items=data,
                    total=total,
                    page=page,
                    page_size=limit,
                    message="获取规则列表成功",
                    trace_id=get_trace_id(request)
                )
            # Supabase 返回空，继续回退到 JSON
        except Exception as e:
            import traceback
            traceback.print_exc()

    # ── 2. 回退：从 JSON 文件加载 ──
    try:
        import json, os
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "sichuan_rules_146.json"
        )
        with open(json_path, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except Exception:
        rules = []

    # 应用层筛选
    def includes_keyword(r: Dict[str, Any]) -> bool:
        if not keyword:
            return True
        s = str(keyword).lower()
        return s in str(r.get('name', '')).lower() or s in str(r.get('description', '')).lower() or s in str(r.get('rule_code', '') or r.get('rule_id', '')).lower()

    def matches_doc_cat(r: Dict[str, Any]) -> bool:
        if not document_category:
            return True
        primary = r.get('primary_document_category')
        cats = r.get('document_categories') or r.get('applicable_documents') or []
        try:
            return primary == document_category or (isinstance(cats, list) and document_category in cats)
        except Exception:
            return primary == document_category

    filtered = [
        r for r in rules
        if includes_keyword(r)
        and (category is None or r.get('category') == category)
        and matches_doc_cat(r)
        and (rule_type is None or r.get('rule_type') == rule_type)
        and (severity is None or r.get('severity') == severity)
        and (is_active is None or bool(r.get('is_active', True)) == is_active)
    ]

    # 排序与分页
    try:
        filtered.sort(key=lambda x: (
            x.get('primary_document_category') or x.get('rule_id') or '',
            x.get('execution_order') or 0,
            x.get('name') or ''
        ))
    except Exception:
        pass
    total = len(filtered)
    offset = (page - 1) * limit
    paginated = filtered[offset: offset + limit]
    return paginated_response(
        items=paginated,
        total=total,
        page=page,
        page_size=limit,
        message="获取规则列表成功（从JSON文件加载）",
        trace_id=get_trace_id(request)
    )


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
async def create_rule(rule: QCRule, current_user: dict = Depends(get_current_user)):
    """创建质控规则"""
    if rule.id in qc_rules_db:
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST,
            detail="质控规则已存在"
        )
    qc_rules_db[rule.id] = rule.model_dump()
    return rule


@router.put("/rules/{rule_id}", response_model=QCRule)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def update_rule(rule_id: str, rule: QCRule, current_user: dict = Depends(get_current_user)):
    """更新质控规则"""
    if rule_id not in qc_rules_db:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="质控规则不存在"
        )
    qc_rules_db[rule_id] = rule.model_dump()
    return rule


@router.delete("/rules/{rule_id}")
@require_admin()
async def delete_rule(request: Request, rule_id: str, current_user: dict = Depends(get_current_user)):
    """删除质控规则"""
    if rule_id not in qc_rules_db:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="质控规则不存在"
        )
    del qc_rules_db[rule_id]
    return success_response(
        data={"rule_id": rule_id},
        message="质控规则删除成功",
        trace_id=get_trace_id(request)
    )


@router.get("/history")
async def get_history(request: Request):
    """获取质控历史"""
    # Simplified history: return all results summary
    return success_response(
        data={
            "items": list(qc_results_db.values()),
            "total": len(qc_results_db)
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

