"""EMR 文书渲染 API（BundleOnly 结构化展示）"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from starlette.concurrency import run_in_threadpool

from ..core.response import success_response, get_trace_id
from ..core.security import get_current_user
from ..services.task_document_access import (
    TaskDocumentAccessDenied,
    require_assigned_task_document,
)
from ..services.bundles.emr_view import (
    build_documents_tree,
    load_bundle_document,
    load_bundle_document_summaries,
    load_bundle_documents,
    pick_document,
    build_render_view,
)
from ..services.bundles.current_view import load_current_documents
from ..services.qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref

logger = logging.getLogger(__name__)
_PRIVILEGED_ROLES = {"admin", "qc_manager", "sync_admin", "super_admin"}


async def _authorize_emr_read(
    record_id: str,
    institute_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    visit_id: Optional[str] = Query(None),
    source_view: str = Query("saved"),
    task_id: Optional[str] = Query(None),
    task_record_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
) -> None:
    roles = {str(role) for role in current_user.get("roles", [])}
    if roles & _PRIVILEGED_ROLES:
        return
    if "qc_staff" not in roles or source_view != "saved":
        raise HTTPException(status_code=403, detail="无权读取该病历文书")
    identity = (institute_id, patient_id, visit_id)
    if not task_id or not task_record_id or any(not value for value in identity) or record_id != visit_id:
        raise HTTPException(status_code=403, detail="无权读取该病历文书")
    actor_id = current_user.get("id") or current_user.get("user_id")
    try:
        await run_in_threadpool(
            require_assigned_task_document,
            task_id=task_id,
            task_record_id=task_record_id,
            actor_id=actor_id,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
        )
    except TaskDocumentAccessDenied as exc:
        raise HTTPException(status_code=403, detail="无权读取该病历文书") from exc
    except Exception as exc:
        logger.warning("任务文书授权校验失败: error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="文书授权暂不可用，请稍后重试") from exc


router = APIRouter(
    prefix="/api/v1/emr",
    tags=["emr"],
    dependencies=[Depends(_authorize_emr_read)],
)


def _resolve_bundle_visit_id(record_id: str, visit_id: Optional[str]) -> str:
    return str(visit_id or record_id or "").strip()


def _build_empty_documents_payload(reason: str) -> Dict[str, Any]:
    return {
        "layout_version": "bundle_struct_v1",
        "documents": [],
        "documents_tree": [
            {"key": "all", "label": "全部", "count": 0, "children": []},
            {"key": "frontpage", "label": "病案首页(临床医生)", "count": 0, "children": []},
            {"key": "admission", "label": "入院记录", "count": 0, "children": []},
            {"key": "course", "label": "病程记录", "count": 0, "children": []},
            {"key": "surgery", "label": "手术相关单据", "count": 0, "children": []},
            {"key": "terminal", "label": "出院记录", "count": 0, "children": []},
            {"key": "orders", "label": "医嘱", "count": 0, "children": []},
        ],
        "domain_bundle_hits": {},
        "empty_reason": reason,
    }


def _project_customer_safe_source_refs(payload: Dict[str, Any]) -> Dict[str, Any]:
    hmac_key = None

    def source_ref(value: str) -> str:
        nonlocal hmac_key
        # 同一批引用复用配置；只在本次请求内保留，下一次请求重新读取。
        if hmac_key is None:
            hmac_key = customer_safe_projection_key()
        return keyed_ref("src", value, hmac_key=hmac_key)

    for document in list(payload.get("documents") or []):
        if not isinstance(document, dict):
            continue
        source_document_id = str(document.get("document_id") or "").strip()
        if source_document_id:
            document["source_ref"] = source_ref(source_document_id)
        source_document_ids = document.get("source_document_ids")
        if isinstance(source_document_ids, list):
            source_document_type = str(
                document.get("document_type")
                or document.get("doc_type")
                or document.get("source_table")
                or ""
            ).strip()
            aliases = []
            for raw_id in source_document_ids:
                alias_id = str(raw_id or "").strip()
                if not alias_id:
                    continue
                alias = {
                    "source_document_id": alias_id,
                    "source_ref": source_ref(alias_id),
                }
                if source_document_type:
                    alias["source_document_type"] = source_document_type
                aliases.append(alias)
            if aliases:
                document["source_document_aliases"] = aliases
    return payload


def _load_documents_from_bundle(
    *,
    record_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    visit_id: Optional[str],
) -> Dict[str, Any]:
    normalized_visit_id = _resolve_bundle_visit_id(record_id, visit_id)
    normalized_institute_id = str(institute_id or "").strip()
    normalized_patient_id = str(patient_id or "").strip()
    if not (normalized_institute_id and normalized_patient_id and normalized_visit_id):
        return _build_empty_documents_payload("missing_bundle_identity")

    try:
        payload = load_bundle_documents(
            institute_id=normalized_institute_id,
            patient_id=normalized_patient_id,
            visit_id=normalized_visit_id,
            bundle_schema="public",
        )
        return _project_customer_safe_source_refs(payload)
    except Exception as exc:
        logger.warning("加载 bundle 文书失败: error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="已保存文书暂不可用，请稍后重试。") from exc


def _load_document_summaries_from_bundle(
    *,
    record_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    visit_id: Optional[str],
    execution_domain: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_visit_id = _resolve_bundle_visit_id(record_id, visit_id)
    normalized_institute_id = str(institute_id or "").strip()
    normalized_patient_id = str(patient_id or "").strip()
    if not (normalized_institute_id and normalized_patient_id and normalized_visit_id):
        return _build_empty_documents_payload("missing_bundle_identity")
    try:
        return _project_customer_safe_source_refs(
            load_bundle_document_summaries(
                institute_id=normalized_institute_id,
                patient_id=normalized_patient_id,
                visit_id=normalized_visit_id,
                bundle_schema="public",
                execution_domain=execution_domain,
            )
        )
    except Exception as exc:
        logger.warning("加载 bundle 文书目录失败: error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="已保存文书暂不可用，请稍后重试。") from exc


def _load_document_from_bundle(
    *,
    record_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    visit_id: Optional[str],
    execution_domain: str,
    doc_type: str,
    doc_id: str,
) -> Dict[str, Any] | None:
    normalized_visit_id = _resolve_bundle_visit_id(record_id, visit_id)
    normalized_institute_id = str(institute_id or "").strip()
    normalized_patient_id = str(patient_id or "").strip()
    if not (normalized_institute_id and normalized_patient_id and normalized_visit_id):
        return None
    return load_bundle_document(
        institute_id=normalized_institute_id,
        patient_id=normalized_patient_id,
        visit_id=normalized_visit_id,
        execution_domain=str(execution_domain or "").strip(),
        doc_type=str(doc_type or "").strip(),
        doc_id=str(doc_id or "").strip(),
        bundle_schema="public",
    )


@router.get("/{record_id}/documents")
async def get_record_documents(
    request: Request,
    record_id: str,
    patient_id: Optional[str] = Query(None, description="患者号（兼容工作台）"),
    visit_id: Optional[str] = Query(None, description="就诊号（兼容工作台）"),
    institute_id: Optional[str] = Query(None, description="机构号（兼容工作台）"),
    view: str = Query("full", pattern="^(full|summary)$", description="目录视图或完整文书"),
    source_view: str = Query("saved", pattern="^(saved|current)$", description="当前病历或已保存文书"),
    execution_domain: Optional[str] = Query(
        None,
        description="摘要优先加载的文书领域；仅 view=summary 时生效",
    ),
):
    """获取病历文书列表（BundleOnly）。"""
    from .qc_sichuan import _cdm_bundle_read_guard

    if source_view == "current":
        if view != "full":
            raise HTTPException(status_code=422, detail="当前病历查看需使用完整文书视图")
        identity = {
            "institute_id": str(institute_id or "").strip(),
            "patient_id": str(patient_id or "").strip(),
            "visit_id": _resolve_bundle_visit_id(record_id, visit_id),
        }
        if not all(identity.values()):
            raise HTTPException(status_code=422, detail="缺少完整住院身份，无法读取当前病历")
        async with _cdm_bundle_read_guard():
            try:
                payload = await run_in_threadpool(load_current_documents, **identity)
            except Exception as exc:
                logger.warning("当前文书更新失败: error_type=%s", type(exc).__name__)
                raise HTTPException(status_code=503, detail="文书更新失败，请稍后重试；本次未展示旧文书。") from exc
            payload = _project_customer_safe_source_refs(payload)
            return success_response(data=payload, message="已读取当前病历文书", trace_id=get_trace_id(request))
    if not (str(institute_id or "").strip() and str(patient_id or "").strip() and _resolve_bundle_visit_id(record_id, visit_id)):
        raise HTTPException(status_code=422, detail="缺少完整住院身份，无法读取已保存文书")
    loader = _load_document_summaries_from_bundle if view == "summary" else _load_documents_from_bundle
    loader_kwargs = {
        "record_id": record_id,
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
    }
    if view == "summary":
        loader_kwargs["execution_domain"] = execution_domain
    async with _cdm_bundle_read_guard():
        payload = await run_in_threadpool(
            loader,
            **loader_kwargs,
        )
        documents = list(payload.get("documents") or [])
        return success_response(
            data=payload,
            message=f"获取到 {len(documents)} 份文书",
            trace_id=get_trace_id(request),
        )


@router.get("/{record_id}/render")
async def render_document(
    request: Request,
    record_id: str,
    doc_type: Optional[str] = Query(None, description="文书类型"),
    doc_id: Optional[str] = Query(None, description="文书ID"),
    patient_id: Optional[str] = Query(None, description="患者号（兼容工作台）"),
    visit_id: Optional[str] = Query(None, description="就诊号（兼容工作台）"),
    institute_id: Optional[str] = Query(None, description="机构号（兼容工作台）"),
    execution_domain: str = Query("", description="目录返回的文书领域"),
):
    """获取文书内容 + 结构化渲染块 + 缺陷标注（BundleOnly）。"""
    if not (str(institute_id or "").strip() and str(patient_id or "").strip() and _resolve_bundle_visit_id(record_id, visit_id)):
        raise HTTPException(status_code=422, detail="缺少完整住院身份，无法读取已保存文书")
    from .qc_sichuan import _cdm_bundle_read_guard

    async with _cdm_bundle_read_guard():
        if execution_domain:
            try:
                selected = await run_in_threadpool(
                    _load_document_from_bundle,
                    record_id=record_id,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    execution_domain=execution_domain,
                    doc_type=str(doc_type or "").strip(),
                    doc_id=str(doc_id or "").strip(),
                )
            except Exception as exc:
                logger.warning("加载 bundle 文书失败: error_type=%s", type(exc).__name__)
                raise HTTPException(status_code=503, detail="已保存文书暂不可用，请稍后重试。") from exc
            documents_payload = {
                "documents_tree": build_documents_tree([selected] if selected else []),
                "empty_reason": "" if selected else "document_not_found",
            }
        else:
            documents_payload = await run_in_threadpool(
                _load_documents_from_bundle,
                record_id=record_id,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
            )
            documents = list(documents_payload.get("documents") or [])
            selected = pick_document(
                documents=documents,
                doc_type=str(doc_type or "").strip(),
                doc_id=str(doc_id or "").strip(),
            )
    view_payload = build_render_view(selected)

    content = str(view_payload.get("content") or "")
    content_type = str(view_payload.get("content_type") or "text")
    metadata = dict(view_payload.get("document_meta") or {})
    render_blocks = list(view_payload.get("render_blocks") or [])
    highlight_anchors = list(view_payload.get("highlight_anchors") or [])
    layout_version = str(view_payload.get("layout_version") or "bundle_struct_v1")
    empty_reason = str(view_payload.get("empty_reason") or documents_payload.get("empty_reason") or "")

    # 旧 qc_results 只有 record_id，无法证明它与 Bundle 的三坐标属于同一病例。
    annotations_status = "no_document" if selected is None else "unavailable_unscoped_source"

    return success_response(
        data={
            "layout_version": layout_version,
            "content": content,
            "content_type": content_type,
            "defect_annotations": [],
            "annotations_status": annotations_status,
            "metadata": metadata,
            "documents_tree": list(documents_payload.get("documents_tree") or []),
            "render_blocks": render_blocks,
            "highlight_anchors": highlight_anchors,
            "empty_reason": empty_reason,
            "total_annotations": 0,
        },
        message="获取文书渲染数据成功",
        trace_id=get_trace_id(request),
    )
