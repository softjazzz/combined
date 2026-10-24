"""人工录入时点的可信文书锚点；不代表质控执行时的输入。"""

import json

from .custom_qc_workspace_service import build_customer_safe_source_ref
from .rectification_document_snapshot import capture_documents


def document_options(identity):
    snapshot = json.loads(capture_documents(identity))
    options = []
    source_keys = [
        (build_customer_safe_source_ref(item["document_id"]), item["doc_type"])
        for item in snapshot["documents"]
    ]
    for document in snapshot["documents"]:
        source_ref = build_customer_safe_source_ref(document["document_id"])
        if source_keys.count((source_ref, document["doc_type"])) != 1:
            continue
        content = document["content"]
        if not content or len(content) > 100_000:
            continue
        fields = document["sections"]
        names = [field["source_field"] for field in fields]
        fields = [
            field
            for field in fields
            if field["source_field"]
            and names.count(field["source_field"]) == 1
            and field["text"]
        ]
        if not fields:
            continue
        options.append(
            {
                "source_ref": source_ref,
                "source_type": document["doc_type"],
                "label": document["label"],
                "fields": fields,
                "content": content,
            }
        )
    keys = [(item["source_ref"], item["source_type"]) for item in options]
    return [
        item
        for item in options
        if keys.count((item["source_ref"], item["source_type"])) == 1
    ]


def freeze_anchor(identity, anchor):
    if anchor is None:
        return None
    if not isinstance(anchor, dict) or set(anchor) != {
        "source_ref",
        "source_type",
        "field_path",
        "quote",
    }:
        raise ValueError("人工文书锚点无效")
    if any(
        not isinstance(value, str) or not value.strip() for value in anchor.values()
    ):
        raise ValueError("人工文书锚点缺少来源、字段或完整摘录")
    quote = anchor["quote"]
    if len(quote) > 2000 or quote.rstrip().endswith(("…", "...")):
        raise ValueError("人工证据摘录无效或已截断")
    matches = [
        item
        for item in document_options(identity)
        if item["source_ref"] == anchor["source_ref"]
        and item["source_type"] == anchor["source_type"]
    ]
    if len(matches) != 1:
        raise ValueError("人工证据文书缺失、重复或不完整，无法定位")
    document = matches[0]
    fields = [
        item
        for item in document["fields"]
        if item["source_field"] == anchor["field_path"]
    ]

    def unique(text):
        index = text.find(quote)
        return index >= 0 and text.find(quote, index + 1) < 0

    if (
        len(fields) != 1
        or not unique(fields[0]["text"])
        or not unique(document["content"])
    ):
        raise ValueError("人工证据摘录与唯一文书字段不一致，无法定位")
    return {
        **anchor,
        "frozen_content": document["content"],
        "captured_at": "manual_create",
    }
