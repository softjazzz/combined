"""整改时点的只读文书快照，不冒充质控运行时输入或整改事实。"""

import json
from datetime import datetime, timezone

from .bundles.current_view import load_current_documents

MAX_DOCUMENTS = 200
MAX_BYTES = 2_000_000


def capture_documents(identity, *, loader=None):
    payload = (loader or load_current_documents)(**identity)
    metadata = payload.get("domain_projection")
    projection = metadata.get("domains") if isinstance(metadata, dict) else None
    if not isinstance(projection, dict) or not projection:
        raise ValueError("rectification_document_completeness_unknown")
    for domain in projection.values():
        sources = domain.get("per_source") if isinstance(domain, dict) else None
        if not isinstance(sources, dict) or not sources or any(
            not isinstance(source, dict) or source.get("has_more") is not False for source in sources.values()
        ):
            raise ValueError("rectification_document_source_truncated_or_unknown")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents or len(documents) > MAX_DOCUMENTS:
        raise ValueError("rectification_documents_empty_or_over_limit")
    saved, seen, duplicates, unavailable = [], set(), set(), 0
    for document in documents:
        key = tuple(str(document.get(field) or "").strip() for field in (
            "execution_domain", "doc_type", "document_id",
        ))
        # document_id 原始为空时，展示 id/doc_key 的序号回退不能用于版本配对。
        if not all(key) or document.get("projection_incomplete") is True or document.get("source_document_ids"):
            unavailable += 1
            continue
        if key in seen:
            duplicates.add(key)
            unavailable += 1
            continue
        seen.add(key)
        saved.append({"execution_domain": key[0], "doc_type": key[1], "document_id": key[2],
                      "label": str(document.get("label") or key[1]),
                      "content": str(document.get("content") or ""),
                      "sections": [
                          {"source_field": str(section.get("source_field") or ""),
                           "label": str(section.get("section_label") or "正文"),
                           "text": str(section.get("text") or "")}
                          for section in document.get("sections", []) if isinstance(section, dict)
                      ]})
    saved = [item for item in saved if (item["execution_domain"], item["doc_type"], item["document_id"]) not in duplicates]
    unavailable += len(duplicates)
    snapshot = {"identity": identity, "captured_at": datetime.now(timezone.utc).isoformat(),
                "documents": saved, "unavailable_documents": unavailable}
    encoded = json.dumps(snapshot, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("rectification_document_snapshot_over_limit")
    return encoded


def compare_documents(before, after, identity):
    if not before or not after:
        return {"available": False, "reason": "该整改缺少派发时或本次提交时正文快照", "documents": []}
    snapshots = [json.loads(value) for value in (before, after)]
    if any(snapshot.get("identity") != identity for snapshot in snapshots):
        raise ValueError("rectification_snapshot_identity_mismatch")
    def index(snapshot):
        return {(item["execution_domain"], item["doc_type"], item["document_id"]): item
                for item in snapshot["documents"]}
    old, new = (index(snapshot) for snapshot in snapshots)
    return {"available": bool(old or new), "reason": "无稳定完整文书可比较" if not old and not new else "",
            "before_at": snapshots[0]["captured_at"],
            "after_at": snapshots[1]["captured_at"],
            "unavailable_documents": sum(snapshot["unavailable_documents"] for snapshot in snapshots),
            "documents": [{"key": list(key), "state": "added" if key not in old else
                           "missing" if key not in new else "empty" if not old[key]["content"] or not new[key]["content"] else "matched",
                           "before": old.get(key), "after": new.get(key)} for key in sorted(old.keys() | new.keys())]}
