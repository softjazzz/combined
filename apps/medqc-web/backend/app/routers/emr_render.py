"""EMR 文书渲染 API（BundleOnly 结构化展示）"""

import json
import logging
from typing import Optional, List, Dict, Any, Tuple

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from starlette.concurrency import run_in_threadpool

from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, get_trace_id
from ..core.security import require_roles
from ..services.bundles.emr_view import (
    build_documents_tree,
    load_bundle_document,
    load_bundle_document_summaries,
    summarize_frozen_documents,
    load_bundle_documents,
    restore_frozen_exam_evidence_coordinates,
    pick_document,
    build_render_view,
)
from ..services.bundles.current_view import load_current_documents
from ..services.bundles import clinical_surgery_browse
from ..services import case_material_snapshot as case_material
from copy import deepcopy
from ..services.qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref

router = APIRouter(
    prefix="/api/v1/emr",
    tags=["emr"],
    dependencies=[
        Depends(require_roles("admin", "qc_manager", "sync_admin", "super_admin", "doctor"))
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
        source_document_id = str((document.get("doc_key") if document.get("version_id") else document.get("document_id")) or "").strip()
        if source_document_id:
            document["source_ref"] = source_ref(source_document_id)
        exam_coordinates = document.pop("exam_evidence_coordinates", None)
        if source_document_id and exam_coordinates and document.get("doc_type") == "exam_item_report":
            document["source_document_aliases"] = [
                {
                    "source_document_id": source_document_id,
                    "source_ref": source_ref(coordinate["source_document_id"]),
                    "source_document_type": coordinate["source_type"],
                }
                for coordinate in exam_coordinates
            ]
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


def _frozen_documents_payload(frozen: dict) -> dict:
    payload = deepcopy(frozen["documents"])
    restore_frozen_exam_evidence_coordinates(payload["documents"], frozen.get("tables") or {})
    return payload


def _load_documents_from_bundle(
    *,
    record_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    visit_id: Optional[str],
) -> Dict[str, Any]:
    frozen = case_material.current()
    if frozen is not None:
        case_material.identity_check(frozen, (str(institute_id or "").strip(), str(patient_id or "").strip(), _resolve_bundle_visit_id(record_id, visit_id)))
        return _project_customer_safe_source_refs(_frozen_documents_payload(frozen))
    current = _load_live_cdm_documents(record_id, institute_id, patient_id, visit_id)
    if current is not None:
        return _project_customer_safe_source_refs(current)
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
            include_exam_evidence_coordinates=True,
        )
        return _project_customer_safe_source_refs(payload)
    except Exception as exc:
        from ..database.clinical_connection import configured
        if configured():
            raise HTTPException(503, "clinical_source_read_unavailable") from None
        logger.warning("加载 bundle 文书失败: %s", exc)
        return _build_empty_documents_payload("bundle_load_failed")


def _load_document_summaries_from_bundle(
    *,
    record_id: str,
    institute_id: Optional[str],
    patient_id: Optional[str],
    visit_id: Optional[str],
    execution_domain: Optional[str] = None,
    document_scope: Optional[str] = None,
) -> Dict[str, Any]:
    frozen = case_material.current()
    if frozen is not None:
        case_material.identity_check(frozen, (str(institute_id or "").strip(), str(patient_id or "").strip(), _resolve_bundle_visit_id(record_id, visit_id)))
        payload = frozen["documents"]
        documents = [
            dict(document) for document in payload["documents"]
            if document_scope is None
            or (document.get("group_key") == "orders") == (document_scope == "orders")
        ]
        if document_scope != "orders":
            restore_frozen_exam_evidence_coordinates(documents, frozen.get("tables") or {})
        return _project_customer_safe_source_refs(summarize_frozen_documents(
            documents=documents, execution_domain=execution_domain,
            daily_material_status=payload.get("daily_material_status"),
            primary_material_status=payload.get("primary_material_status")))
    if document_scope is not None:
        raise HTTPException(409, "historical_material_snapshot_not_retained")
    current = _load_live_cdm_documents(record_id, institute_id, patient_id, visit_id)
    if current is not None:
        return _project_customer_safe_source_refs(summarize_frozen_documents(
            documents=current["documents"], execution_domain=execution_domain,
            daily_material_status=current.get("daily_material_status"),
            primary_material_status=current.get("primary_material_status")))
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
        from ..database.clinical_connection import configured
        if configured():
            raise HTTPException(503, "clinical_source_read_unavailable") from None
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
    frozen = case_material.current()
    if frozen is not None:
        case_material.identity_check(frozen, (str(institute_id or "").strip(), str(patient_id or "").strip(), _resolve_bundle_visit_id(record_id, visit_id)))
        if doc_id:
            matches = [
                doc for doc in frozen["documents"]["documents"]
                if (not doc_type or doc.get("doc_type") == doc_type)
                and doc_id in {str(doc.get(key) or "") for key in ("id", "doc_id", "document_id", "doc_key")}
            ]
            return deepcopy(matches[0]) if len(matches) == 1 else None
        documents = _project_customer_safe_source_refs(deepcopy(frozen["documents"]))["documents"]
        return pick_document(documents=documents, doc_type=doc_type, doc_id=doc_id)
    current = _load_live_cdm_documents(record_id, institute_id, patient_id, visit_id)
    if current is not None:
        documents = _project_customer_safe_source_refs(current)["documents"]
        return _pick_live_document(documents, execution_domain, doc_type, doc_id)
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


def _load_live_cdm_documents(record_id, institute_id, patient_id, visit_id):
    """普通 CDM 浏览不依赖已运行质控；历史快照由调用方优先处理。

    复用只读即时装配，不创建/刷新持久 Bundle。不能将读取失败或身份缺失
    转换成“没有文书”，也不能借用业务库的旧临床材料。
    """
    from ..database.clinical_connection import configured

    if not configured():
        return None
    identity = {
        "institute_id": str(institute_id or "").strip(),
        "patient_id": str(patient_id or "").strip(),
        "visit_id": _resolve_bundle_visit_id(record_id, visit_id),
    }
    if not all(identity.values()):
        raise HTTPException(422, "clinical_material_identity_unavailable")
    try:
        return load_current_documents(**identity, include_exam_evidence_coordinates=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("读取当前 CDM 文书失败: error_type=%s", type(exc).__name__)
        raise HTTPException(503, "clinical_source_read_unavailable") from None


def _pick_live_document(documents, domain, doc_type, doc_id):
    # 当前文书可能在两次请求间变化；指定文书不存在时不得显示另一份正文。
    candidates = [doc for doc in documents
                  if (not domain or doc.get("execution_domain") == domain)
                  and (not doc_type or doc.get("doc_type") == doc_type)
                  and (not doc_id or doc_id in {
                      str(doc.get(key) or "") for key in ("id", "doc_id", "document_id", "doc_key")})]
    return pick_document(documents=candidates, doc_type=doc_type, doc_id=doc_id)


@router.get("/{record_id}/documents")
async def get_record_documents(
    request: Request,
    record_id: str,
    patient_id: Optional[str] = Query(None, description="患者号（兼容工作台）"),
    visit_id: Optional[str] = Query(None, description="就诊号（兼容工作台）"),
    institute_id: Optional[str] = Query(None, description="机构号（兼容工作台）"),
    view: str = Query("full", pattern="^(full|summary)$", description="目录视图或完整文书"),
    source_view: str = Query("saved", pattern="^(saved|current)$", description="当前病历或已保存文书"),
    document_scope: Optional[str] = Query(None, pattern="^(clinical|orders)$", description="历史文书目录中的非医嘱或医嘱"),
    include_clinical_surgery: bool = False,
    execution_domain: Optional[str] = Query(
        None,
        description="摘要优先加载的文书领域；仅 view=summary 时生效",
    ),
):
    """获取病历文书列表（BundleOnly）。"""
    own_identity = getattr(request.state, "doctor_case_identity", None)
    if own_identity:
        institute_id, patient_id, visit_id = (own_identity[k] for k in ("institute_id", "patient_id", "visit_id"))
    if document_scope is not None and (source_view != "saved" or view != "summary"):
        raise HTTPException(422, "document_scope_requires_saved_summary")
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
        if include_clinical_surgery and record_id != identity["visit_id"]:
            raise HTTPException(422, "病历路径与住院身份不符")
        if include_clinical_surgery and request.query_params.get("job_id"):
            raise HTTPException(422, "当前病历目录不可指定历史任务")
        try:
            payload = await run_in_threadpool(
                load_current_documents, **identity, include_exam_evidence_coordinates=True,
            )
            if include_clinical_surgery:
                payload = await run_in_threadpool(
                    clinical_surgery_browse.supplement_directory, payload, tuple(identity.values()),
                )
        except Exception as exc:
            logger.warning("当前文书更新失败: error_type=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="文书更新失败，请稍后重试；本次未展示旧文书。") from exc
        payload = _project_customer_safe_source_refs(payload)
        return success_response(data=payload, message="已读取当前病历文书", trace_id=get_trace_id(request))
    loader = _load_document_summaries_from_bundle if view == "summary" else _load_documents_from_bundle
    loader_kwargs = {
        "record_id": record_id,
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
    }
    if view == "summary":
        loader_kwargs["execution_domain"] = execution_domain
        if document_scope is not None:
            loader_kwargs["document_scope"] = document_scope
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
    source_view: str = "saved",
    clinical_surgery_version: str | None = Query(None, pattern="^[a-f0-9]{64}$"),
):
    """获取文书内容 + 结构化渲染块 + 缺陷标注（BundleOnly）。"""
    own_identity = getattr(request.state, "doctor_case_identity", None)
    if own_identity:
        institute_id, patient_id, visit_id = (own_identity[k] for k in ("institute_id", "patient_id", "visit_id"))
    if clinical_surgery_version is not None:
        identity = tuple(str(value or "").strip() for value in (institute_id, patient_id, visit_id))
        if (
            source_view != "current" or case_material.current() is not None
            or request.query_params.get("job_id") or doc_type != "surgery_record"
            or not doc_id or not all(identity) or identity[2] != record_id
        ):
            raise HTTPException(422, "无法确认当前手术记录的住院身份和版本")
        selected, status = await run_in_threadpool(
            clinical_surgery_browse.read_document, identity, doc_id, clinical_surgery_version,
        )
        if selected is None:
            if status not in {"available", "not_applicable"}:
                raise HTTPException(503, "手术记录暂时无法验证，请刷新病历目录后重试。")
            raise HTTPException(409, "手术记录版本已变更或不可用，请刷新病历目录。")
        view = build_render_view(selected)
        metadata = view.pop("document_meta")
        return success_response(data={
            **view, "content": selected["content"],
            "metadata": {**metadata, "source": "clinical",
                         "clinical_surgery_version": selected["version_id"],
                         "generation": selected["generation"]},
            "defect_annotations": [], "total_annotations": 0,
        }, message="获取手术记录成功", trace_id=get_trace_id(request))
    current = None
    if case_material.current() is None:
        current = await run_in_threadpool(
            _load_live_cdm_documents, record_id, institute_id, patient_id, visit_id)
    if current is not None:
        current = _project_customer_safe_source_refs(current)
        selected = _pick_live_document(
            current["documents"], execution_domain,
            str(doc_type or "").strip(), str(doc_id or "").strip())
        documents_payload = {
            "documents_tree": build_documents_tree([selected] if selected else []),
            "empty_reason": "" if selected else "document_not_found",
        }
    elif execution_domain or (case_material.current() is not None and doc_id):
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
    if selected and selected.get("frontpage_display"):
        metadata["frontpage_display"] = selected["frontpage_display"]
    render_blocks = list(view_payload.get("render_blocks") or [])
    highlight_anchors = list(view_payload.get("highlight_anchors") or [])
    layout_version = str(view_payload.get("layout_version") or "bundle_struct_v1")
    empty_reason = str(view_payload.get("empty_reason") or documents_payload.get("empty_reason") or "")

    annotations, annotation_status = await _load_defect_annotations(record_id, content)

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
            # loaded / no_result / unavailable：unavailable 表示读取失败，前端需提示而不是当作“无缺陷”
            "annotation_status": annotation_status,
        },
        message="获取文书渲染数据成功",
        trace_id=get_trace_id(request),
    )


def _decode_json_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except ValueError:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_qc_findings(row: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """从 qc_results 行取出 issues / evaluation_results。

    当前 alembic 表结构只有 raw_output（完整结果 JSON 文本），没有 issues、
    evaluation_results 列；旧库可能另有 issues 列。优先用独立列，缺失时回退 raw_output。
    """
    raw_output: Dict[str, Any] = {}
    raw_value = row.get("raw_output")
    if isinstance(raw_value, dict):
        raw_output = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except ValueError:
            logger.warning("qc_results.raw_output 不是合法 JSON，无法还原缺陷标注")
        else:
            if isinstance(parsed, dict):
                raw_output = parsed
    issues = _decode_json_list(row.get("issues")) if "issues" in row else []
    if not issues:
        issues = _decode_json_list(raw_output.get("issues"))
    eval_results = _decode_json_list(row.get("evaluation_results")) if "evaluation_results" in row else []
    if not eval_results:
        eval_results = _decode_json_list(raw_output.get("evaluation_results"))
    return issues, eval_results


async def _load_defect_annotations(record_id: str, content: str) -> Tuple[List[Dict[str, Any]], str]:
    """读取最近一次质控结果的缺陷标注，返回 (标注列表, 状态)。"""
    from ..database.clinical_connection import configured
    if configured():
        return [], "unavailable_for_source"
    sb = get_supabase()
    if sb is None:
        return [], "unavailable"
    try:
        # 用 * 而不是点名列：qc_results 在新旧库中的列不一致，点名不存在的列会直接 UndefinedColumn
        qc_resp = await async_execute(
            sb.table("qc_results")
            .select("*")
            .eq("record_id", record_id)
            .order("created_at", desc=True)
            .limit(1)
        )
    except Exception as exc:
        logger.error("获取缺陷标注失败: record_id=%s error_type=%s", record_id, type(exc).__name__)
        return [], "unavailable"
    qc_data = list(getattr(qc_resp, "data", None) or [])
    if not qc_data:
        return [], "no_result"
    issues, eval_results = _extract_qc_findings(qc_data[0])
    annotations: List[Dict[str, Any]] = []
    for i, issue in enumerate(issues):
        annotation = _build_annotation_from_issue(content, issue, i)
        if annotation:
            annotations.append(annotation)
    for result in eval_results:
        if result.get("status") == "non_compliant" or not result.get("is_compliant", True):
            annotation = _build_annotation_from_result(content, result, len(annotations))
            if annotation:
                annotations.append(annotation)
    return annotations, "loaded"


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
