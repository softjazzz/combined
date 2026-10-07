"""讨论记录证据的显式字段坐标不得由其他字段摘录冒充。"""

import pytest

from app.services.luxian_0609.customer_evidence_enrichment import enrich_customer_evidence


class Materials:
    def __init__(self, rows):
        self.data = rows

    def rows(self, source_type):
        assert source_type == "presurg_discussion"
        return self.data


@pytest.mark.parametrize("staff", [None, "医师乙"])
def test_explicit_discussion_field_controls_the_enriched_excerpt(staff):
    row = {"document_id": "synthetic-discussion", "host_summary": "主持人小结内容。"}
    if staff is not None:
        row["discuss_staff"] = staff
    original = {
        "source_type": "presurg_discussion",
        "source_document_id": "synthetic-discussion",
        "field_path": "discuss_staff",
    }
    result = enrich_customer_evidence([original], evidence_materials=Materials((row,)))[0]
    assert result["field_path"] == "discuss_staff"
    assert result.get("evidence_excerpt", "") == (staff or "")
    assert original.get("evidence_excerpt") is None

@pytest.mark.parametrize("value", ["", "   ", None, 123, ["医师乙"], {"text": "医师乙"}])
def test_explicit_empty_or_non_text_field_cannot_fall_back(value):
    evidence = {"source_type": "presurg_discussion", "source_document_id": "syn",
                "field_path": "discuss_staff"}
    result = enrich_customer_evidence([evidence], evidence_materials=Materials(({
        "document_id": "syn", "discuss_staff": value, "host_summary": "小结。",
    },)))[0]
    assert result == evidence


@pytest.mark.parametrize("field", ["document_title", "v2_schema.discuss_staff", "unknown_field"])
def test_explicit_non_content_coordinate_is_not_used_as_evidence(field):
    evidence = {"source_type": "presurg_discussion", "source_document_id": "syn", "field_path": field}
    result = enrich_customer_evidence([evidence], evidence_materials=Materials(({
        "document_id": "syn", "document_title": "术前讨论",
        "v2_schema": {"discuss_staff": "医师乙"}, "host_summary": "小结。",
    },)))[0]
    assert result == evidence


def test_ambiguous_explicit_field_keeps_reference_unfilled():
    evidence = {"source_type": "presurg_discussion", "source_document_id": "syn",
                "field_path": "discuss_staff"}
    result = enrich_customer_evidence([evidence], evidence_materials=Materials((
        {"document_id": "syn", "discuss_staff": "医师甲"},
        {"document_id": "syn", "discuss_staff": "医师乙"},
    )))[0]
    assert result == evidence


def test_explicit_field_takes_precedence_over_rule_preference():
    result = enrich_customer_evidence(
        [{"source_type": "presurg_discussion", "source_document_id": "syn", "field_path": "host_summary"}],
        evidence_materials=Materials(({
            "document_id": "syn", "host_summary": "小结。", "discuss_staff": "医师乙",
        },)),
        preferred_source_fields={"presurg_discussion": "discuss_staff"},
    )[0]
    assert result["field_path"] == "host_summary"
    assert result["evidence_excerpt"] == "小结。"


def test_existing_excerpt_and_its_kind_are_not_rewritten():
    evidence = {"source_type": "presurg_discussion", "source_document_id": "syn",
                "field_path": "host_summary", "evidence_excerpt": "原引用。", "excerpt_kind": "字段级依据"}
    result = enrich_customer_evidence([evidence], evidence_materials=Materials(({
        "document_id": "syn", "host_summary": "原引用。其余文字。", "discuss_staff": "医师乙",
    },)))[0]
    assert result == evidence


def test_mdt_preference_without_explicit_coordinate_keeps_legacy_behavior():
    result = enrich_customer_evidence(
        [{"source_type": "presurg_discussion", "source_document_id": "syn"}],
        evidence_materials=Materials(({"document_id": "syn", "host_summary": "小结。"},)),
        preferred_source_fields={"presurg_discussion": "discuss_staff"},
    )[0]
    assert result["field_path"] == "discuss_staff"
    assert result["evidence_excerpt"] == "参与人员字段为空或未取得"
    assert result["excerpt_kind"] == "字段级依据"


@pytest.mark.parametrize("staff", [None, "医师乙"])
def test_legacy_adapter_and_authorized_read_keep_the_explicit_source(staff):
    from app.services.document_assembly.assembler import assemble_document
    from app.services.custom_qc_workspace_service import _authorized_document_excerpt
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results

    rule = "LX0609-04-01-05"
    row = {"document_id": "synthetic-discussion", "host_summary": "主持人小结。"}
    if staff is not None:
        row["discuss_staff"] = staff
    evidence = {"source_type": "presurg_discussion", "source_document_id": row["document_id"],
                "field_path": "discuss_staff"}
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule}],
        execution_results=[{
            "rule_id": rule, "status": "compliant", "customer_evidence": [evidence],
            "metadata": {"execution_source": "lx0609_native", "executor_type": "program"},
        }],
        audit_context={"evidence_materials": Materials((row,))},
    )[0]
    assert result["status"] == "compliant"
    enriched = result["customer_evidence"][0]
    assert enriched["field_path"] == "discuss_staff"
    assert enriched.get("evidence_excerpt", "") == (staff or "")
    document = assemble_document("presurg_discussion", row).to_dict()
    excerpt, _ = _authorized_document_excerpt(document, field_path=enriched["field_path"])
    assert excerpt == (staff or "")
