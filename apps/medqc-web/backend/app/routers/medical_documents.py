import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends

from ..core.supabase_client import get_supabase
from ..services.records_ingest_service import get_classification_mapping
from ..services.qc_service import QCService
from ..core.security import get_current_user
from ..storage.memory import qc_results_db
from ..core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["medical-documents"])
qc_service = QCService()


@router.get("/medical-records/{record_id}")
async def get_medical_record_detail(record_id: str):
    supabase = get_supabase()
    settings = get_settings()
    if supabase:
        try:
            resp = supabase.table(settings.RECORDS_TABLE).select("*").eq("id", record_id).execute()
            rows = resp.data or []
            if not rows:
                raise HTTPException(status_code=404, detail="医疗记录不存在")
            return rows[0]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取医疗记录失败: {e}")
    # fallback: 内存
    from ..storage.memory import medical_records_db
    rec = medical_records_db.get(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="医疗记录不存在")
    return rec

@router.get("/medical-records/{record_id}/documents")
async def get_medical_record_documents(record_id: str):
    """
    返回与前端期望对齐的结构：
    {
      record_id,
      total_documents,
      categories: [{
        category_code, category_name, category_description, document_count, documents: [...]
      }],
      classification_summary: {
        [category_code]: { name, count, types: { [type_code]: { name, count } } }
      }
    }
    """
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=500, detail="数据库连接未初始化")
    try:
        # 取文档
        resp = supabase.table(settings.DOCUMENTS_TABLE).select("*").eq("record_id", record_id).execute()
        raw_docs: List[Dict[str, Any]] = resp.data or []

        # 分类/类型名称映射
        mapping = await get_classification_mapping()
        cat_map: Dict[str, Any] = mapping.get("categories", {}) or {}
        type_map: Dict[str, Any] = mapping.get("types", {}) or {}

        # 规范化文档字段，补充 title / content_preview 等
        docs: List[Dict[str, Any]] = []
        for d in raw_docs:
            meta = (d.get("metadata") or {})
            cat_code = meta.get("category_code") or d.get("category_code") or "unknown"
            typ_code = meta.get("type_code") or d.get("type_code") or "unknown"

            # 标题优先级：title -> metadata.title -> type_name -> "未命名文书"
            # 兼容两种类型映射结构：
            # - { types: { "cat.type": { type_code, type_name, ... } } }
            # - { types: { "cat.type": "type_id" } }
            composite_key = f"{cat_code}.{typ_code}" if cat_code and typ_code else typ_code
            type_info_candidate = type_map.get(composite_key) or type_map.get(typ_code) or {}
            if isinstance(type_info_candidate, dict):
                resolved_type_info: Dict[str, Any] = type_info_candidate
            else:
                resolved_type_info = {}
            type_name = (resolved_type_info or {}).get("type_name") or typ_code or "未分类"
            title = d.get("title") or meta.get("title") or type_name or "未命名文书"

            content = d.get("content") or ""
            content_preview = (content[:180] + ("…" if len(content) > 180 else "")) if content else ""

            safe_type_info = resolved_type_info if isinstance(resolved_type_info, dict) else {}
            docs.append({
                **d,
                "title": title,
                "content_preview": d.get("content_preview") or content_preview,
                "classification_confidence": d.get("classification_confidence") or meta.get("confidence") or 0,
                "ai_classified": d.get("ai_classified", True if meta else False),
                "type_info": (safe_type_info if safe_type_info else {"type_code": typ_code, "type_name": type_name}),
                "category_code": cat_code,
            })

        # 按分类聚合
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            grouped.setdefault(d["category_code"], []).append(d)

        # 构建分类与汇总
        categories: List[Dict[str, Any]] = []
        classification_summary: Dict[str, Any] = {}
        for cat_code, lst in grouped.items():
            cat_info_raw = cat_map.get(cat_code) or {}
            cat_info = cat_info_raw if isinstance(cat_info_raw, dict) else {}
            categories.append({
                "category_id": cat_info.get("category_id") if isinstance(cat_info, dict) else (cat_info_raw if not isinstance(cat_info_raw, dict) else None),
                "category_code": cat_code,
                "category_name": cat_info.get("category_name") or cat_code or "未分类",
                "category_description": cat_info.get("description", ""),
                "document_count": len(lst),
                "documents": lst,
            })

            # 统计 types
            type_counts: Dict[str, Any] = {}
            for d in lst:
                t_code = (d.get("type_info") or {}).get("type_code") or "unknown"
                t_name = (d.get("type_info") or {}).get("type_name") or t_code
                if t_code not in type_counts:
                    type_counts[t_code] = {"name": t_name, "count": 0}
                type_counts[t_code]["count"] += 1

            classification_summary[cat_code] = {
                "name": cat_info.get("category_name") or cat_code,
                "count": len(lst),
                "types": type_counts,
            }

        # 分类稳定排序：按 document_count DESC
        categories.sort(key=lambda x: (-x["document_count"], x["category_name"]))

        return {
            "record_id": record_id,
            "total_documents": len(docs),
            "categories": categories,
            "classification_summary": classification_summary,
        }
    except Exception as e:
        logger.error(f"获取文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档失败: {e}")


@router.put("/medical-documents/{document_id}")
async def update_medical_document(document_id: str, update_data: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=500, detail="数据库连接未初始化")
    try:
        resp = supabase.table(settings.DOCUMENTS_TABLE).update(update_data).eq("id", document_id).execute()
        return {"success": True, "updated": len(resp.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")


@router.delete("/medical-documents/{document_id}")
async def delete_medical_document(document_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=500, detail="数据库连接未初始化")
    try:
        resp = supabase.table(settings.DOCUMENTS_TABLE).delete().eq("id", document_id).execute()
        return {"success": True, "deleted": len(resp.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.post("/medical-records/{record_id}/batch-qc-analysis")
async def batch_qc_analysis(record_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(status_code=500, detail="数据库连接未初始化")
    try:
        settings = get_settings()
        resp = supabase.table(settings.DOCUMENTS_TABLE).select("id, content, title").eq("record_id", record_id).execute()
        docs = resp.data or []
        started = []
        for d in docs:
            res = await qc_service.evaluate({"record_id": d["id"]})
            qc_results_db[d["id"]] = res
            started.append({"document_id": d["id"], "status": "started"})
        return {"record_id": record_id, "started": started, "count": len(started)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量质控启动失败: {e}")


@router.post("/medical-documents/{document_id}/qc-analysis")
async def analyze_medical_document(document_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(status_code=500, detail="数据库连接未初始化")
    try:
        settings = get_settings()
        resp = supabase.table(settings.DOCUMENTS_TABLE).select('id, content, title').eq('id', document_id).execute()
        data = (resp.data or [])
        if not data:
            raise HTTPException(status_code=404, detail="文档不存在")
        res = await qc_service.evaluate({"record_id": document_id})
        qc_results_db[document_id] = res
        return {"analysis_id": res.get("id"), "status": "started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"质控分析失败: {e}")


@router.get("/medical-documents/{document_id}/qc-results")
async def get_document_qc_results(document_id: str):
    res = qc_results_db.get(document_id)
    if not res:
        raise HTTPException(status_code=404, detail="质控结果不存在")
    return res
