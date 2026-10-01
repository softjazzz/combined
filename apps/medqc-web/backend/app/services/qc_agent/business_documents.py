"""具体保存证据到当前文书的精确定位；不重判质控事实。"""
from __future__ import annotations

from fastapi import HTTPException


def locate_document(evidence: dict, payload: dict) -> dict:
    source_ref = str(evidence.get("source_ref") or "")
    source_type = str(evidence.get("source_type") or "")
    quote = str(evidence.get("evidence_excerpt") or "")
    result = {"source_view": "current", "quote": quote, "title": "对应文书原文"}
    candidates = []
    for doc in payload.get("documents", []):
        bindings = [{"source_ref": doc.get("source_ref"), "source_document_type": doc.get("document_type") or doc.get("doc_type") or doc.get("source_table")}]
        bindings.extend(doc.get("source_document_aliases") or [])
        hits = [binding for binding in bindings if source_ref and binding.get("source_ref") == source_ref]
        if hits:
            candidates.append((doc, hits))
    if not candidates:
        return {**result, "state": "source_not_found", "note": "当前文书中未找到保存证据的来源，未按标题或相似文字猜测。"}
    if len(candidates) != 1:
        return {**result, "state": "source_ambiguous", "note": "同一来源对应多份文书，无法确认具体文书。"}
    doc, bindings = candidates[0]
    if source_type and not any(binding.get("source_document_type") == source_type for binding in bindings):
        return {**result, "state": "source_type_mismatch", "note": "当前文书类别与保存证据来源不一致，未展示未确认的原文。"}
    content = str(doc.get("content") or "")
    result.update(title=doc.get("doc_name") or doc.get("label") or "对应文书原文", content=content, record_time=doc.get("record_time") or doc.get("sort_time") or "")
    positions = []
    offset = 0
    while quote:
        start = content.find(quote, offset)
        if start < 0:
            break
        positions.append(start)
        if len(positions) > 1:
            break
        offset = start + 1
    if not positions:
        return {**result, "state": "quote_not_found", "note": "已确认来源文书，但保存摘录与当前原文未直接匹配，未伪造具体位置。"}
    if len(positions) != 1:
        return {**result, "state": "quote_ambiguous", "note": "保存摘录在当前文书中出现多次，已打开确认的文书，未猜测具体位置。"}
    return {**result, "state": "located", "start": positions[0], "end": positions[0] + len(quote), "offset_unit": "unicode_code_points", "note": "高亮当前文书中的相同文字。保存摘录另列，匹配不代表文书版本未变化。"}


def read_evidence_document(identity: dict[str, str], evidence: dict) -> dict:
    from app.services.bundles.current_view import load_current_documents
    from app.routers.emr_render import _project_customer_safe_source_refs
    try:
        payload = _project_customer_safe_source_refs(load_current_documents(**identity))
    except Exception as exc:
        raise HTTPException(503, "当前文书读取失败，本次未回退到旧文书") from exc
    return locate_document(evidence, payload)
