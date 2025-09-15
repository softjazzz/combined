import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Query

from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..storage.memory import qc_results_db, qc_rules_db
from ..core.supabase_client import get_supabase, async_execute

router = APIRouter(prefix="/api/qc", tags=["qc"])
service = QCService()


@router.post("/analyze/{record_id}")
async def analyze_record(record_id: str):
    result = await service.evaluate({"record_id": record_id})
    # store result
    qc_results_db[record_id] = result
    analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
    return {"analysis_id": analysis_id, "status": "started", "record_id": record_id}


@router.post("/analyze/batch")
async def analyze_batch(payload: Dict[str, Any]):
    record_ids: List[str] = payload.get("record_ids", [])
    started = []
    for rid in record_ids:
        res = await service.evaluate({"record_id": rid})
        qc_results_db[rid] = res
        started.append({"record_id": rid, "status": "started"})
    return {"started": started, "message": f"已为 {len(started)} 个文档启动质控分析"}


@router.get("/result/{record_id}", response_model=QCResult)
async def get_result(record_id: str):
    res = qc_results_db.get(record_id)
    if not res:
        raise HTTPException(status_code=404, detail="质控结果不存在")
    return res


@router.get("/progress/{analysis_id}")
async def get_progress(analysis_id: str):
    # Simplified: assume completed if any result exists
    return {"analysis_id": analysis_id, "status": "completed"}


 


@router.get("/rules")
async def list_rules(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    document_category: Optional[str] = Query(None, description="文书类别"),
    rule_type: Optional[str] = Query(None, description="规则类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取质控规则列表，支持文书类别筛选。
    - 首选使用 Supabase 后端筛选；
    - 当不支持 .or_ 等语法或客户端不可用时，回退为拉取小批量并在应用层筛选。
    """
    sb = get_supabase()
    if sb is None:
        # 数据库不可用时，返回空数据，避免与前端不一致
        return {"data": [], "total": 0, "page": page, "limit": limit}

    # 优先尝试后端筛选
    try:
        query = sb.table('qc_rules').select('*', count='exact')
        if keyword:
            # postgrest 的 or 语法
            if hasattr(query, 'or_'):
                query = query.or_(f"name.ilike.%{keyword}%,description.ilike.%{keyword}%,rule_code.ilike.%{keyword}%")
        if category:
            query = query.eq('category', category)
        if document_category:
            if hasattr(query, 'or_'):
                query = query.or_(
                    f"primary_document_category.eq.{document_category},document_categories.cs.{{{document_category}}}"
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

        # 兼容异步/同步执行
        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])
        total = getattr(resp, 'count', None)
        # 某些实现不返回 count
        if total is None:
            total = len(data)
        return {"data": data, "total": total, "page": page, "limit": limit}
    except Exception as e:
        # 兼容回退：拉取较小窗口数据到内存再筛选
        try:
            base = sb.table('qc_rules').select('*')
            if hasattr(base, 'limit'):
                base = base.limit(2000)
            resp2 = await async_execute(base)
            rules: List[Dict[str, Any]] = list(getattr(resp2, 'data', None) or [])
        except Exception:
            rules = []

        # 应用层筛选
        def includes_keyword(r: Dict[str, Any]) -> bool:
            if not keyword:
                return True
            s = str(keyword).lower()
            return s in str(r.get('name', '')).lower() or s in str(r.get('description', '')).lower() or s in str(r.get('rule_code', '')).lower()

        def matches_doc_cat(r: Dict[str, Any]) -> bool:
            if not document_category:
                return True
            primary = r.get('primary_document_category')
            cats = r.get('document_categories') or []
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
            and (is_active is None or bool(r.get('is_active')) == is_active)
        ]

        # 排序与分页
        try:
            filtered.sort(key=lambda x: (
                x.get('primary_document_category') or '',
                x.get('execution_order') or 0,
                x.get('name') or ''
            ))
        except Exception:
            pass
        total = len(filtered)
        offset = (page - 1) * limit
        paginated = filtered[offset: offset + limit]
        return {"data": paginated, "total": total, "page": page, "limit": limit}


@router.get("/rules/document-categories/stats")
async def get_document_category_stats():
    """获取文书类别统计信息"""
    try:
        sb = get_supabase()
        if sb is None:
            return {"data": {}}
        response = await async_execute(sb.table('qc_rules').select('primary_document_category'))
        rows = list(getattr(response, 'data', None) or [])
        stats: Dict[str, int] = {}
        for rule in rows:
            category = rule.get('primary_document_category')
            if category:
                stats[category] = stats.get(category, 0) + 1
        return {"data": stats}
    except Exception as e:
        print(f"获取文书类别统计失败: {e}")
        import traceback
        traceback.print_exc()
        return {"data": {}}

@router.get("/rules/document-categories/config")
async def get_document_category_config():
    """获取文书类别配置"""
    try:
        sb = get_supabase()
        if sb is None:
            return {"data": []}
        response = await async_execute(
            sb.table('document_category_config').select('*').eq('is_active', True).order('sort_order')
        )
        rows = list(getattr(response, 'data', None) or [])
        return {"data": rows}
    except Exception as e:
        print(f"获取文书类别配置失败: {e}")
        return {"data": []}

@router.post("/rules", response_model=QCRule)
async def create_rule(rule: QCRule):
    if rule.id in qc_rules_db:
        raise HTTPException(status_code=400, detail="质控规则已存在")
    qc_rules_db[rule.id] = rule.model_dump()
    return rule


@router.put("/rules/{rule_id}", response_model=QCRule)
async def update_rule(rule_id: str, rule: QCRule):
    if rule_id not in qc_rules_db:
        raise HTTPException(status_code=404, detail="质控规则不存在")
    qc_rules_db[rule_id] = rule.model_dump()
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    if rule_id not in qc_rules_db:
        raise HTTPException(status_code=404, detail="质控规则不存在")
    del qc_rules_db[rule_id]
    return {"message": "质控规则删除成功"}


@router.get("/history")
async def get_history():
    # Simplified history: return all results summary
    return {"items": list(qc_results_db.values()), "total": len(qc_results_db)}


@router.get("/poc/rules")
async def poc_rules():
    return {
        "rules": [
            {"id": "POC-001", "name": "主诉完整性（PoC）", "category": "基础", "severity": "minor"},
            {"id": "POC-002", "name": "诊断一致性（PoC）", "category": "诊断", "severity": "major"},
        ]
    }
