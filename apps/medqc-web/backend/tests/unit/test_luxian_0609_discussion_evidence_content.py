from app.services.luxian_0609.customer_evidence_enrichment import enrich_customer_evidence


class Materials:
    def __init__(self, rows):
        self.data = rows

    def rows(self, source_type):
        return self.data


def enrich(**fields):
    return enrich_customer_evidence(
        [{"source_type": "presurg_discussion", "source_document_id": "syn-disc"}],
        evidence_materials=Materials(({"document_id": "syn-disc", **fields},)),
    )[0]


def test_structured_summary_is_locatable_content_not_title():
    result = enrich(record_content="", document_title="术前讨论", host_summary="计划手术，准备已完成。")
    assert result["field_path"] == "host_summary"
    assert result["evidence_excerpt"] == "计划手术，准备已完成。"
    assert result["excerpt_kind"] == "字段级依据"


def test_title_alone_stays_document_reference_without_content_claim():
    result = enrich(document_title="术前讨论")
    assert "evidence_excerpt" not in result
    assert "field_path" not in result


def test_nested_schema_is_not_exported_without_a_supported_field_location():
    result = enrich(v2_schema={"discuss_suggestion": "same content", "private": "private"})
    assert "evidence_excerpt" not in result


def test_participant_content_is_not_relabelled_as_discussion_opinions():
    result = enrich(discuss_staff="医师甲、医师乙")
    assert result["field_path"] == "discuss_staff"
    assert result["evidence_excerpt"] == "医师甲、医师乙"
    assert result["excerpt_kind"] == "字段级依据"


def test_body_keeps_priority_and_original_evidence_not_replaced():
    result = enrich(record_content="具体病情。", host_summary="其他内容。")
    assert result["field_path"] == "record_content"
    assert result["evidence_excerpt"] == "具体病情。"


def test_empty_or_malformed_schema_does_not_create_evidence():
    for schema in ("{", [], {"discuss_suggestion": {"text": "不接受对象"}}):
        result = enrich(document_title="术前讨论", v2_schema=schema)
        assert "evidence_excerpt" not in result


def test_ambiguous_document_identity_is_not_filled():
    result = enrich_customer_evidence(
        [{"source_type": "presurg_discussion", "source_document_id": "syn-disc"}],
        evidence_materials=Materials((
            {"document_id": "syn-disc", "host_summary": "内容甲"},
            {"document_id": "syn-disc", "host_summary": "内容乙"},
        )),
    )
    assert "evidence_excerpt" not in result[0]


def test_assembled_source_field_is_preserved_by_authorized_read():
    from app.services.document_assembly.assembler import assemble_document
    from app.services.custom_qc_workspace_service import _authorized_document_excerpt
    row = {"document_id": "syn-disc", "document_title": "术前讨论",
           "record_content": "", "host_summary": "计划手术，准备已完成。", "discuss_staff": "医师甲"}
    document = assemble_document("presurg_discussion", row).to_dict()
    result = enrich(**{k:v for k,v in row.items() if k != "document_id"})
    text, kind = _authorized_document_excerpt(document, field_path=result["field_path"])
    assert text == result["evidence_excerpt"]
    assert kind == result["excerpt_kind"]
    assert _authorized_document_excerpt(document, field_path="missing_field") == ("", "")
    duplicate = dict(document, sections=document["sections"] * 2)
    assert _authorized_document_excerpt(duplicate, field_path="host_summary") == ("", "")


def test_non_string_source_never_becomes_authorized_excerpt_through_assembly():
    from app.services.document_assembly.assembler import assemble_document
    from app.services.custom_qc_workspace_service import _authorized_document_excerpt
    for invalid in ({"text": "nested content"}, ["nested content"], 123):
        row = {"document_id": "syn-disc", "host_summary": invalid}
        evidence = enrich(host_summary=invalid)
        assert "field_path" not in evidence
        document = assemble_document("presurg_discussion", row).to_dict()
        assert _authorized_document_excerpt(document, field_path=evidence.get("field_path", "")) == ("", "")
        assert _authorized_document_excerpt(document, field_path="host_summary") == ("", "")


def test_legacy_nested_body_remains_visible_but_is_not_an_exact_source_field():
    from app.services.document_assembly.assembler import assemble_document
    from app.services.custom_qc_workspace_service import _authorized_document_excerpt
    row = {"document_id": "syn-disc", "record_time": "2026-01-01 08:00:00",
           "v2_schema": {"host_summary": "Legacy body must stay visible."}}
    document = assemble_document("presurg_discussion", row).to_dict()
    assert "Legacy body must stay visible." in document["assembled_text"]
    assert any("Legacy body must stay visible." in s["text"] for s in document["sections"])
    assert _authorized_document_excerpt(document, field_path="host_summary") == ("", "")
    assert _authorized_document_excerpt(document, field_path="presurg_discussion_template") == ("", "")
    assert _authorized_document_excerpt(document) == ("", "")
