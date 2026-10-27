"""当前病历查看：从 CDM 现组装，不读取或覆盖任务使用的持久化 Bundle。"""
from __future__ import annotations

from concurrent.futures import Future
from copy import deepcopy
from threading import Lock
from typing import Any

from . import assembly, emr_view
from .frontpage_view import load_frontpage_document
from ..luxian_0609.basic_timeliness_facts import extract_admission_anchor
from ..validation_material_source import (
    material_pg_preference_reviews, material_original_document_ids, material_review_documents, material_source_schema,
)
from ..validation_material_display import attach_pdf_material_sources, prefer_pg_documents

# 查看当前病历时医嘱逐条列出，质控 Bundle 的上限（药品700/非药品1500）会让医嘱多的病例
# 静默少显示（1016 样本最多 788/2156 条）。只读展示路径单独放宽；仍超出时由
# projection_incomplete 标出，不能当成完整。
CURRENT_VIEW_PROJECTION_LIMITS = {
    "inpat_drug_order": 5000,
    "inpat_nondrug_order": 5000,
}

# 仅合并进行中的同病例请求，结束立即移除；不缓存已完成的临床数据。
_pending: dict[tuple[str, str, str], Future] = {}
_pending_lock = Lock()


def _assemble_current_documents(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, Any]:
    identity = dict(institute_id=institute_id, patient_id=patient_id, visit_id=visit_id)
    source_schema = material_source_schema(default_schema=assembly._default_source_schema(), **identity)
    limits = assembly._material_limits_for_variants(scenes=(), domains=emr_view._DOMAIN_LOAD_ORDER)
    limits["inpat_registration"] = 2
    for table_name, limit in CURRENT_VIEW_PROJECTION_LIMITS.items():
        # 多取 1 行用于判断是否仍有未展示的医嘱。
        limits[table_name] = max(limits.get(table_name, 0), limit + 1)
    snapshot = assembly._build_material_snapshot(source_schema=source_schema, table_limits=limits, **identity)
    # 读取失败不能冒充没有文书，更不能回退旧 Bundle。
    if snapshot.errors_by_table:
        raise RuntimeError("current_document_source_read_failed")
    bundles = {
        domain: assembly.assemble_domain_bundle(
            execution_domain=domain, source_schema=source_schema,
            material_snapshot=snapshot, projection_limits=CURRENT_VIEW_PROJECTION_LIMITS, **identity,
        )
        for domain in emr_view._DOMAIN_LOAD_ORDER
    }
    documents = emr_view.build_documents_from_domain_bundles(bundles)
    pdf_candidates = material_review_documents(**identity)
    frontpage = load_frontpage_document(**identity) if snapshot.rows_by_table.get("mr") else None
    if frontpage is not None:
        # 仅替换当前查看的首页条目；历史 Bundle 和规则输入仍由原有 owner 读取。
        documents = [document for document in documents if document.get("doc_type") != "mr"]
        documents.append(frontpage)
    original_document_ids = material_original_document_ids(**identity)
    pg_reviews = material_pg_preference_reviews(**identity)
    documents = attach_pdf_material_sources(
        documents, original_document_ids=original_document_ids, reviews=pg_reviews,
    )
    # 活动文书已在共享取数入口按复核决定筛选；目录不再单独删行造成与规则不一致。
    if pdf_candidates:
        documents.extend(prefer_pg_documents(
            pdf_candidates, documents, original_document_ids=original_document_ids, reviews=pg_reviews,
        ))
    anchor = extract_admission_anchor(
        registration_rows=snapshot.rows_by_table.get("inpat_registration", []),
        admission_rows=snapshot.rows_by_table.get("admission_record", []),
        discharge_rows=(), allow_date_fallback=False,
    )
    return {
        "layout_version": "bundle_struct_v1",
        "visit_id": visit_id,
        "documents": documents,
        "documents_tree": emr_view.build_documents_tree(documents),
        "domain_projection": emr_view._build_domain_projection_summary(bundles),
        "domain_bundle_hits": {},
        "empty_reason": "" if documents else "current_documents_empty",
        "current_record": {
            "admission_time": anchor.anchor_time.isoformat() if anchor.anchor_time else "",
            "admission_time_source": anchor.source_key or "",
            "admission_time_state": anchor.state.value,
        },
    }


def load_current_documents(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, Any]:
    key = (institute_id.strip(), patient_id.strip(), visit_id.strip())
    if not all(key):
        raise ValueError("missing_current_record_identity")
    with _pending_lock:
        future = _pending.get(key)
        owner = future is None
        if owner:
            future = Future()
            _pending[key] = future
    if owner:
        try:
            future.set_result(_assemble_current_documents(
                institute_id=key[0], patient_id=key[1], visit_id=key[2],
            ))
        except Exception as exc:
            future.set_exception(exc)
        finally:
            with _pending_lock:
                _pending.pop(key, None)
    # 返回独立对象，后续脱敏/前端投影不能污染同一请求结果。
    return deepcopy(future.result())
