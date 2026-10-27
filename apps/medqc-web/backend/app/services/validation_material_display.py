"""PDF材料的只读展示关联；不更改候选状态、临床正文或质控材料。"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

from .validation_material_source import reviewed_pdf_document_exclusions


def _valid_pg_review(review: dict[str, Any], documents: list[dict[str, Any]],
                     original_document_ids: set[str] | None) -> bool:
    ids = review.get("original_pg_ids") or []
    available = {str(document.get("document_id") or "") for document in documents}
    return bool(ids) and all(
        identity in available and (original_document_ids is None or identity in original_document_ids)
        for identity in ids
    )


def prefer_pg_active_documents(
    documents: list[dict[str, Any]], *, original_document_ids: set[str] | None,
    reviews: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """只移除已逐份复核、且当前原PG仍存在的重复PDF展示。"""
    removed = reviewed_pdf_document_exclusions(
        reviews=reviews, original_document_ids=original_document_ids,
        available_document_ids={str(document.get("document_id") or "") for document in documents},
    )
    return [document for document in documents if document.get("document_id") not in removed]


def attach_pdf_material_sources(
    documents: list[dict[str, Any]], *, original_document_ids: set[str] | None,
    reviews: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """保留活动PDF来源；原PG实体仅在用户明确选择PDF版本时附加来源。"""
    if original_document_ids is None:
        return documents
    sources = {(review.get("pdf_document_type"), review.get("pdf_document_id")): review
               for review in reviews.values() if review.get("pdf_document_id")}
    result = []
    for document in documents:
        source = sources.get((document.get("doc_type"), document.get("document_id")))
        if source and (document.get("document_id") not in original_document_ids or source.get("decision") == "prefer_pdf"):
            result.append({**document, "source_file_id": source["source_file_id"],
                           "source_pages": list(source["source_pages"]),
                           "validation_material_state": "new_candidate"})
        else:
            result.append(document)
    return result


def prefer_pg_documents(
    candidates: list[dict[str, Any]], current_documents: list[dict[str, Any]],
    *, original_document_ids: set[str] | None = None,
    reviews: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """原PG优先以逐文书复核为准，旧模糊匹配不能直接作为删除依据。"""
    reviews = reviews or {}
    originals = [document for document in current_documents
                 if original_document_ids is None or str(document.get("document_id") or "") in original_document_ids]
    remaining = []
    for candidate in candidates:
        review = reviews.get(str(candidate.get("document_id") or ""), {})
        if review.get("decision") == "remove_pdf_duplicate" and _valid_pg_review(review, originals, original_document_ids):
            continue
        document = dict(candidate)
        if review:
            # 独有、歧义及原PG已缺失的候选都单列，不能继续挂到旧的错配文书下。
            document["_review_reference"] = {}
        remaining.append(document)
    return project_pdf_review_links(remaining, originals)


def _clinical_text(value: str, title: str = "") -> str:
    lines = str(value or "").strip().splitlines()
    if lines and lines[0].strip() == title:
        lines.pop(0)
    if lines and re.fullmatch(r"\s*20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:" + re.escape(title) + r")?\s*", lines[0]):
        lines.pop(0)
    text = "\n".join(lines)
    labels = list(re.finditer(r"(?:医生|医师)签名\s*[:：]", text))
    if len(labels) == 1:
        text = text[:labels[0].start()]
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lstrip(":")


def project_pdf_review_links(
    candidates: list[dict[str, Any]], current_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """只关联持久来源已明确对应、且当前目录中唯一存在的原文书。"""
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for document in current_documents:
        by_identity[(str(document.get("doc_type") or ""), str(document.get("document_id") or ""))].append(document)
    result = []
    for candidate in candidates:
        document = dict(candidate)
        reference = document.pop("_review_reference", {})
        parents = by_identity.get((reference.get("target_table", ""), reference.get("target_document_id", "")), [])
        document["pdf_review_relation"] = "unmatched"
        document["pdf_review_parent_key"] = ""
        document["pdf_review_notes"] = ["PDF候选尚未确认对应文书，未纳入质控。"]
        if len(parents) == 1 and parents[0].get("doc_key"):
            parent = parents[0]
            original = _clinical_text(parent.get("content", ""), parent.get("document_title", ""))
            pdf = _clinical_text(document.get("content", ""), reference.get("original_title", ""))
            equivalent = len(original) >= 30 and original == pdf
            differences = reference.get("differences") or []
            notes = ["正文一致；PDF原件保留供对照。" if equivalent else "PDF正文与当前文书不同，请对照原文核对。"]
            if any("time" in value for value in differences):
                notes.append("记录时间存在差异或来源待核对，两侧时间分别保留。")
            notes.append("仅供PDF文本对照，未纳入质控。")
            document.update(
                pdf_review_parent_key=parent["doc_key"],
                pdf_review_relation="same_content" if equivalent else "version_difference",
                pdf_review_notes=notes,
            )
            title = str(reference.get("original_title") or "PDF文书")
            display_title = title + ("（PDF对照文本）" if equivalent else "（PDF差异版本，待核对）")
            document.update(doc_name=display_title, document_title=display_title, label=display_title)
        result.append(document)
    return result
