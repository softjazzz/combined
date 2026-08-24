"""EMR 文书渲染 API（BundleOnly 结构化展示）"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Request, Query
from starlette.concurrency import run_in_threadpool

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import require_roles
from ..services.bundles.emr_view import (
    build_documents_tree,
    load_bundle_document,
    load_bundle_document_summaries,
    load_bundle_documents,
    pick_document,
    build_render_view,
)
from ..services.custom_qc_workspace_service import build_customer_safe_source_ref

router = APIRouter(
    prefix="/api/v1/emr",
    tags=["emr"],
    dependencies=[
        Depends(require_roles("admin", "qc_manager", "sync_admin", "super_admin"))
    ],
)
logger = logging.getLogger(__name__)


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
    for document in list(payload.get("documents") or []):
        if not isinstance(document, dict):
            continue
        source_document_id = str(document.get("document_id") or "").strip()
        if source_document_id:
            document["source_ref"] = build_customer_safe_source_ref(source_document_id)
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
        logger.warning("加载 bundle 文书失败: %s", exc)
        return _build_empty_documents_payload("bundle_load_failed")


def _load_document_summaries_from_bundle(
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
        return _project_customer_safe_source_refs(
            load_bundle_document_summaries(
                institute_id=normalized_institute_id,
                patient_id=normalized_patient_id,
                visit_id=normalized_visit_id,
                bundle_schema="public",
            )
        )
    except Exception as exc:
        logger.warning("加载 bundle 文书目录失败: error_type=%s", type(exc).__name__)
        return _build_empty_documents_payload("bundle_load_failed")


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
):
    """获取病历文书列表（BundleOnly）。"""
    loader = _load_document_summaries_from_bundle if view == "summary" else _load_documents_from_bundle
    payload = await run_in_threadpool(
        loader,
        record_id=record_id,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
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
    if execution_domain:
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

    annotations: List[Dict[str, Any]] = []
    sb = get_supabase()
    if sb is not None:
        try:
            qc_resp = await async_execute(
                sb.table("qc_results")
                .select("issues,evaluation_results")
                .eq("record_id", record_id)
                .order("created_at", desc=True)
                .limit(1)
            )
            qc_data = list(getattr(qc_resp, "data", None) or [])
            if qc_data:
                issues = qc_data[0].get("issues", []) or []
                eval_results = qc_data[0].get("evaluation_results", []) or []
                for i, issue in enumerate(issues):
                    annotation = _build_annotation_from_issue(content, issue, i)
                    if annotation:
                        annotations.append(annotation)
                for result in eval_results:
                    if result.get("status") == "non_compliant" or not result.get("is_compliant", True):
                        annotation = _build_annotation_from_result(content, result, len(annotations))
                        if annotation:
                            annotations.append(annotation)
        except Exception as exc:
            logger.warning("获取缺陷标注失败: %s", exc)

    return success_response(
        data={
            "layout_version": layout_version,
            "content": content,
            "content_type": content_type,
            "defect_annotations": annotations,
            "metadata": metadata,
            "documents_tree": list(documents_payload.get("documents_tree") or []),
            "render_blocks": render_blocks,
            "highlight_anchors": highlight_anchors,
            "empty_reason": empty_reason,
            "total_annotations": len(annotations),
        },
        message="获取文书渲染数据成功",
        trace_id=get_trace_id(request),
    )


def _build_annotation_from_issue(
    content: str, issue: Dict[str, Any], index: int
) -> Optional[Dict[str, Any]]:
    """从质控 issue 构建缺陷标注"""
    description = issue.get("description", "")
    evidence = issue.get("evidence", "")
    severity = issue.get("severity", "warning")
    location = issue.get("location", "")
    rule_name = issue.get("rule_name", "")

    start_offset = -1
    end_offset = -1
    search_text = evidence or description

    if content:
        # 候选搜索词（按优先级）
        candidates = []
        if evidence:
            candidates.append(evidence[:30])
        if description:
            candidates.append(description[:30])
        # 从 location / rule_name 提取病历章节关键词
        _section_keywords = [
            "主诉", "现病史", "既往史", "个人史", "家族史",
            "体格检查", "辅助检查", "初步诊断", "诊疗计划",
            "入院记录", "出院记录", "病程记录", "手术记录",
            "医嘱", "过敏史", "预防接种", "诊断",
        ]
        for text in [location, rule_name]:
            if text:
                for kw in _section_keywords:
                    if kw in text:
                        candidates.append(kw)
        for candidate in candidates:
            pos = content.find(candidate)
            if pos >= 0:
                start_offset = pos
                end_offset = pos + len(candidate)
                search_text = candidate
                break

    return {
        "defect_id": issue.get("id", f"issue_{index}"),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "keyword": search_text[:50] if search_text else "",
        "description": description,
        "evidence": evidence,
        "severity": severity,
        "rule_name": rule_name,
        "category": issue.get("category", ""),
        "suggestion": issue.get("suggestion", ""),
    }


def _build_annotation_from_result(
    content: str, result: Dict[str, Any], index: int
) -> Optional[Dict[str, Any]]:
    """从评估结果构建缺陷标注"""
    findings = result.get("findings", "")
    evidence = result.get("evidence", "")

    search_text = evidence or findings
    start_offset = -1
    end_offset = -1

    if search_text and content:
        pos = content.find(search_text[:30])
        if pos >= 0:
            start_offset = pos
            end_offset = pos + min(len(search_text), 50)

    return {
        "defect_id": result.get("rule_id", f"result_{index}"),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "keyword": search_text[:50] if search_text else "",
        "description": findings,
        "evidence": evidence,
        "severity": "error",
        "rule_name": result.get("rule_name", ""),
        "category": "语义质控",
        "suggestion": result.get("suggestion", ""),
    }
