"""合成文书核验：不读取业务数据库或患者原文。"""

import json

import pytest

from app.services import manual_document_anchor as service


@pytest.fixture
def document(monkeypatch):
    doc = {"document_id": "doc-1", "doc_type": "course_record", "execution_domain": "emr",
           "label": "合成病程", "content": "完整正文合成摘录结束",
           "sections": [{"source_field": "text", "label": "正文", "text": "完整正文合成摘录结束"}]}
    monkeypatch.setattr(service, "capture_documents", lambda _: json.dumps({"documents": [doc]}))
    monkeypatch.setattr(service, "build_customer_safe_source_ref", lambda _: "src_" + "a" * 24)
    return doc


def anchor(**overrides):
    return {"source_ref": "src_" + "a" * 24, "source_type": "course_record",
            "field_path": "text", "quote": "合成摘录", **overrides}


def test_freezes_full_selected_document(document):
    result = service.freeze_anchor({}, anchor())
    assert result["frozen_content"] == document["content"]
    assert result["captured_at"] == "manual_create"


@pytest.mark.parametrize("values", [
    {"field_path": "unknown"}, {"source_type": "other_source"},
    {"source_ref": "src_" + "b" * 24}, {"quote": "缺源摘录"}, {"quote": "合成摘录…"},
])
def test_rejects_untrusted_source_field_and_excerpt(document, values):
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor(**values))


def test_repeated_field_is_not_locatable(document):
    document["sections"].append(dict(document["sections"][0]))
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor())


def test_repeated_quote_rejected(document):
    document["content"] += "合成摘录"
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor())


def test_overlapping_quote_rejected(document):
    document["content"] = "aaaa"
    document["sections"][0]["text"] = "aaaa"
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor(quote="aaa"))


def test_same_id_and_type_across_domains_is_not_first_match(document, monkeypatch):
    other = {**document, "execution_domain": "other-domain"}
    monkeypatch.setattr(service, "capture_documents", lambda _: json.dumps({"documents": [document, other]}))
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor())


def test_oversize_document_rejected(document):
    document["content"] = "文" * 100_001
    with pytest.raises(ValueError):
        service.freeze_anchor({}, anchor())
