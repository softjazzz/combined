import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import uuid
from datetime import datetime

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id, ErrorCode, StatusCode
from ..services.records_ingest_service import get_classification_mapping
from ..services.qc_service import QCService
from ..core.security import get_current_user
from ..storage.memory import qc_results_db
from ..core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["medical-documents"])
qc_service = QCService()


# Pydantic models for request/response
class CreateDocumentRequest(BaseModel):
    title: str
    content: str
    document_type: str
    category_code: Optional[str] = None
    type_code: Optional[str] = None
    summary: Optional[str] = None


class DocumentTypeInfo(BaseModel):
    id: str
    category_id: str
    category_code: str
    category_name: str
    type_code: str
    type_name: str
    description: Optional[str] = None
    sort_order: int = 0


@router.get("/document-types")
async def get_document_types(request: Request):
    """获取所有文档类型列表，按分类分组"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail="数据库连接未初始化"
        )

    try:
        # 获取分类信息
        categories_resp = await async_execute(
            supabase.table("document_categories_test")
            .select("*")
            .eq("is_active", True)
            .order("sort_order")
        )
        categories = categories_resp.data or []

        # 获取类型信息
        types_resp = await async_execute(
            supabase.table("document_types_test")
            .select("*, document_categories_test!inner(category_code, category_name)")
            .eq("is_active", True)
            .order("sort_order")
        )
        types = types_resp.data or []

        # 按分类分组
        result = []
        for category in categories:
            category_types = [
                {
                    "id": doc_type["id"],
                    "category_id": doc_type["category_id"],
                    "category_code": category["category_code"],
                    "category_name": category["category_name"],
                    "type_code": doc_type["type_code"],
                    "type_name": doc_type["type_name"],
                    "description": doc_type.get("description"),
                    "sort_order": doc_type["sort_order"]
                }
                for doc_type in types
                if doc_type["category_id"] == category["id"]
            ]

            if category_types:  # 只包含有类型的分类
                result.append({
                    "category_id": category["id"],
                    "category_code": category["category_code"],
                    "category_name": category["category_name"],
                    "description": category.get("description"),
                    "types": category_types
                })

        return success_response(
            data={"categories": result},
            message="获取文档类型成功",
            trace_id=get_trace_id(request)
        )

    except Exception as e:
        logger.error(f"获取文档类型失败: {e}")
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取文档类型失败: {e}"
        )


@router.get("/medical-records/{record_id}")
async def get_medical_record_detail(record_id: str):
    supabase = get_supabase()
    settings = get_settings()
    if supabase:
        try:
            resp = await async_execute(supabase.table(settings.RECORDS_TABLE).select("*").eq("id", record_id))
            rows = resp.data or []
            if not rows:
                raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="医疗记录不存在")
            return rows[0]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取医疗记录失败: {e}")
    # fallback: 内存
    from ..storage.memory import medical_records_db
    rec = medical_records_db.get(record_id)
    if not rec:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="医疗记录不存在")
    return rec

@router.get("/medical-records/{record_id}/documents")
async def get_medical_record_documents(request: Request, record_id: str):
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
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")
    try:
        # 取文档
        resp = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).select("*").eq("record_id", record_id))
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
            # 生成更友好的默认标题：优先已有标题；否则用“日期 + 中文类型名”
            raw_title = d.get("title") or meta.get("title") or ""
            # 提取可用日期
            raw_dt = d.get("created_at") or d.get("updated_at") or meta.get("extracted_at") or ""
            dt_str: str = ""
            if isinstance(raw_dt, str) and raw_dt:
                # 兼容 2025-09-16T03:22:42.037663+00:00 / 2025-09-16 03:22:42 两种格式
                if "T" in raw_dt:
                    dt_str = raw_dt.split("T", 1)[0]
                else:
                    dt_str = raw_dt.split(" ", 1)[0]
            # 判定是否需要替换标题
            if not raw_title or raw_title in ("未命名文档", "未命名文书", "untitled", "unknown"):
                title = f"{dt_str} {type_name}".strip()
            else:
                code_like = str(raw_title).strip().lower().replace(" ", "_")
                if code_like == str(typ_code or "").strip().lower():
                    title = f"{dt_str} {type_name}".strip()
                else:
                    title = raw_title

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

        # 在每个分类内，为同名文档进行去重编号（同一天同类型可能多份）
        for cat_code, lst in grouped.items():
            try:
                lst.sort(key=lambda x: (x.get("created_at") or x.get("updated_at") or ""))
                title_counts: Dict[str, int] = {}
                for doc in lst:
                    base_title = doc.get("title") or "未命名文书"
                    title_counts[base_title] = title_counts.get(base_title, 0) + 1
                    if title_counts[base_title] > 1:
                        doc["title"] = f"{base_title}（{title_counts[base_title]}）"
            except Exception:
                pass

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

        return success_response(
            data={
                "record_id": record_id,
                "total_documents": len(docs),
                "categories": categories,
                "classification_summary": classification_summary,
            },
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        logger.error(f"获取文档失败: {e}")
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"获取文档失败: {e}")


@router.post("/medical-records/{record_id}/documents")
async def create_medical_document(req: Request, record_id: str, doc_request: CreateDocumentRequest):
    """为指定医疗记录创建新文档"""
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")

    try:
        # 验证医疗记录是否存在
        record_resp = await async_execute(
            supabase.table(settings.RECORDS_TABLE)
            .select("id")
            .eq("id", record_id)
        )
        if not record_resp.data:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="医疗记录不存在")

        # 获取分类映射以确定category_id和type_id
        mapping = await get_classification_mapping()
        categories = mapping.get("categories", {})
        types = mapping.get("types", {})

        # 确定category_id和type_id
        category_id = None
        type_id = None

        if doc_request.category_code and doc_request.type_code:
            # 使用提供的分类和类型代码
            category_id = categories.get(doc_request.category_code)
            composite_key = f"{doc_request.category_code}.{doc_request.type_code}"
            type_info = types.get(composite_key) or types.get(doc_request.type_code)
            if isinstance(type_info, dict):
                type_id = type_info.get("id")
            else:
                type_id = type_info
        elif doc_request.document_type:
            # 尝试从document_type解析
            if "." in doc_request.document_type:
                cat_code, type_code = doc_request.document_type.split(".", 1)
                category_id = categories.get(cat_code)
                type_info = types.get(doc_request.document_type)
                if isinstance(type_info, dict):
                    type_id = type_info.get("id")
                else:
                    type_id = type_info

        # 如果无法确定分类，使用默认值
        if not category_id or not type_id:
            # 获取第一个可用的分类和类型作为默认值
            if categories:
                first_cat = list(categories.values())[0]
                if isinstance(first_cat, dict):
                    category_id = first_cat.get("id")
                else:
                    category_id = first_cat
            if types:
                first_type = list(types.values())[0]
                if isinstance(first_type, dict):
                    type_id = first_type.get("id")
                else:
                    type_id = first_type

        # 确保有有效的category_id和type_id
        if not category_id or not type_id:
            raise HTTPException(status_code=StatusCode.BAD_REQUEST, detail="无法确定文档分类，请检查分类配置")

        # 创建文档数据 - 包含必需字段
        document_data = {
            "record_id": record_id,
            "category_id": category_id,
            "type_id": type_id,
            "title": doc_request.title,
            "content": doc_request.content,
            "ai_classified": False,
            "classification_confidence": 0.0,
            "manual_verified": True,  # 手动创建的文档标记为已验证
            "position_info": {},
            "sort_order": 0,
            "status": "active",
            "qc_status": "pending",
            "metadata": {
                "category_code": doc_request.category_code,
                "type_code": doc_request.type_code,
                "manually_created": True
            }
        }

        # 如果有摘要，添加
        if doc_request.summary:
            document_data["summary"] = doc_request.summary

        # 插入文档
        resp = await async_execute(
            supabase.table(settings.DOCUMENTS_TABLE)
            .insert(document_data)
        )

        if not resp.data:
            raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="文档创建失败")

        return success_response(
            data={"document": resp.data[0]},
            message="文档创建成功",
            trace_id=get_trace_id(req)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建文档失败: {e}")
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"创建文档失败: {e}")


@router.put("/medical-documents/{document_id}")
async def update_medical_document(request: Request, document_id: str, update_data: Dict[str, Any]):
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")
    try:
        resp = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).update(update_data).eq("id", document_id))
        return success_response(
            data={"updated": len(resp.data or [])},
            message="更新成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"更新失败: {e}")


@router.delete("/medical-documents/{document_id}")
async def delete_medical_document(
    request: Request,
    document_id: str,
    hard_delete: bool = False,
    # current_user: dict = Depends(get_current_user)  # 暂时注释掉认证
):
    """删除医疗文档，支持软删除和硬删除"""
    supabase = get_supabase()
    settings = get_settings()
    if not supabase:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")

    try:
        # 验证文档是否存在
        doc_resp = await async_execute(
            supabase.table(settings.DOCUMENTS_TABLE)
            .select("id, title, record_id")
            .eq("id", document_id)
        )
        if not doc_resp.data:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="文档不存在")

        document = doc_resp.data[0]

        if hard_delete:
            # 硬删除：直接从数据库删除
            resp = await async_execute(
                supabase.table(settings.DOCUMENTS_TABLE)
                .delete()
                .eq("id", document_id)
            )
            operation = "硬删除"
        else:
            # 软删除：标记为已删除状态
            resp = await async_execute(
                supabase.table(settings.DOCUMENTS_TABLE)
                .update({
                    "status": "deleted",
                    "updated_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        **document.get("metadata", {}),
                        "deleted_at": datetime.utcnow().isoformat(),
                        "deletion_reason": "user_deleted"
                    }
                })
                .eq("id", document_id)
            )
            operation = "软删除"

        return success_response(
            data={
                "deleted": len(resp.data or []),
                "operation": operation,
                "document_id": document_id,
                "document_title": document["title"],
            },
            message=f"文档已{operation}成功",
            trace_id=get_trace_id(request)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"删除失败: {e}")


@router.post("/medical-records/{record_id}/batch-qc-analysis")
async def batch_qc_analysis(request: Request, record_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")
    try:
        settings = get_settings()
        resp = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).select("id, content, title").eq("record_id", record_id))
        docs = resp.data or []
        started = []
        for d in docs:
            res = await qc_service.evaluate({"record_id": d["id"]})
            qc_results_db[d["id"]] = res
            started.append({"document_id": d["id"], "status": "started"})
        return success_response(
            data={"record_id": record_id, "started": started, "count": len(started)},
            message="批量质控已启动",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"批量质控启动失败: {e}")


@router.post("/medical-documents/{document_id}/qc-analysis")
async def analyze_medical_document(request: Request, document_id: str, current_user: dict = Depends(get_current_user)):
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail="数据库连接未初始化")
    try:
        settings = get_settings()
        resp = await async_execute(supabase.table(settings.DOCUMENTS_TABLE).select('id, content, title').eq('id', document_id))
        data = (resp.data or [])
        if not data:
            raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="文档不存在")
        res = await qc_service.evaluate({"record_id": document_id})
        qc_results_db[document_id] = res
        return success_response(
            data={"analysis_id": res.get("id"), "status": "started"},
            message="质控分析已启动",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=StatusCode.INTERNAL_SERVER_ERROR, detail=f"质控分析失败: {e}")


@router.get("/medical-documents/{document_id}/qc-results")
async def get_document_qc_results(request: Request, document_id: str):
    res = qc_results_db.get(document_id)
    if not res:
        raise HTTPException(status_code=StatusCode.NOT_FOUND, detail="质控结果不存在")
    return success_response(data=res, trace_id=get_trace_id(request))
