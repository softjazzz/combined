"""PDF版本只读关联与当前目录同源，不触碰临床或规则材料。"""
from copy import deepcopy

import pytest

from app.services.validation_material_display import (
    attach_pdf_material_sources, prefer_pg_active_documents, prefer_pg_documents, project_pdf_review_links,
)


def source(document_id="SYN-1", doc_type="consultation_record"):
    return dict(doc_type=doc_type, document_id=document_id, doc_key=doc_type+"::"+document_id,
                document_title="会诊记录", content="合成会诊正文，需核对的相关情况已经记录完整，后续请遵医嘱处理病情变化是否持续？医生签名：合成甲")


def candidate(**changes):
    value = dict(doc_type="pdf_candidate", document_id="PDF-1", content="请会诊执行记录\n2026-08-10 18:21\n合成会诊正文，需核对的相关情况已经记录完整，后续请遵医嘱处理病情变化是否持续?医生签名：",
                 _review_reference=dict(target_table="consultation_record", target_document_id="SYN-1",
                                        original_title="请会诊执行记录", differences=["body_version_difference"]))
    value.update(changes)
    return value


def test_typographic_duplicate_links_without_changing_original_material():
    rows, active = [candidate()], [source()]
    before = deepcopy((rows, active))
    result = project_pdf_review_links(rows, active)[0]
    assert result["pdf_review_relation"] == "same_content"
    assert result["document_title"] == "请会诊执行记录（PDF对照文本）"
    assert result["pdf_review_parent_key"] == "consultation_record::SYN-1"
    assert result["content"] == rows[0]["content"]
    assert "_review_reference" not in result
    assert (rows, active) == before
    assert any("未纳入质控" in note for note in result["pdf_review_notes"])


def test_dose_change_remains_linked_as_a_different_version():
    pdf = candidate()
    pdf["content"] = pdf["content"].replace("病情变化", "剂量增加")
    result = project_pdf_review_links([pdf], [source()])[0]
    assert result["pdf_review_relation"] == "version_difference"
    assert result["pdf_review_parent_key"] == "consultation_record::SYN-1"


def test_missing_or_ambiguous_parent_stays_unmatched():
    for active in ([], [source(), source()], [source(doc_type="daily_course_record")]):
        result = project_pdf_review_links([candidate()], active)[0]
        assert result["pdf_review_relation"] == "unmatched"
        assert not result["pdf_review_parent_key"]


def test_no_inference_from_equal_title_or_date_when_no_persisted_relation():
    result = project_pdf_review_links([candidate(_review_reference={})], [source()])[0]
    assert result["pdf_review_relation"] == "unmatched"


def test_metadata_differences_are_preserved_even_for_equal_body():
    pdf = candidate()
    pdf["_review_reference"]["differences"] += ["record_time_conflict", "signature_conflict"]
    result = project_pdf_review_links([pdf], [source()])[0]
    assert result["pdf_review_relation"] == "same_content"
    assert any("记录时间" in note for note in result["pdf_review_notes"])
    assert pdf["_review_reference"]["differences"][-1] == "signature_conflict"


def test_reviewed_pg_priority_removes_version_without_mutating_either_source():
    pdf, pg = candidate(), source()
    pdf["record_time"] = "2026-05-31T13:47+08:00"
    pg["record_time"] = "2026-06-01 19:56:26"
    before = deepcopy((pdf, pg))
    reviews = {"PDF-1": {"decision": "remove_pdf_duplicate", "original_pg_ids": ["SYN-1"]}}
    assert prefer_pg_documents([pdf], [pg], reviews=reviews) == []
    assert (pdf, pg) == before


@pytest.mark.parametrize("decision", ["keep_pdf_only", "needs_review"])
def test_reviewed_independent_or_uncertain_pdf_does_not_keep_old_false_parent(decision):
    pdf, pg = candidate(), source()
    reviews = {"PDF-1": {"decision": decision, "original_pg_ids": []}}
    result = prefer_pg_documents([pdf], [pg], reviews=reviews)
    assert len(result) == 1
    assert result[0]["pdf_review_relation"] == "unmatched"
    assert result[0]["content"] == pdf["content"]
    assert not result[0]["pdf_review_parent_key"]


@pytest.mark.parametrize("ids,active", [(["MISSING"], [source()]), (["SYN-1"], []), ([], [source()])])
def test_removal_is_rejected_when_current_pg_parent_cannot_be_verified(ids, active):
    reviews = {"PDF-1": {"decision": "remove_pdf_duplicate", "original_pg_ids": ids}}
    assert len(prefer_pg_documents([candidate()], active, reviews=reviews)) == 1


def test_imported_pdf_cannot_be_used_as_original_pg_parent():
    reviews = {"PDF-1": {"decision": "remove_pdf_duplicate", "original_pg_ids": ["SYN-1"]}}
    assert len(prefer_pg_documents([candidate()], [source()], original_document_ids=set(), reviews=reviews)) == 1


def test_active_removal_requires_review_not_just_same_day_title():
    pg = source()
    pg["record_time"] = "2026-08-10 09:00:00"
    pdf = {**pg, "document_id": "PDF-NEW", "doc_key": "PDF-NEW"}
    pdf_only = {**pdf, "document_id": "PDF-ONLY", "doc_key": "PDF-ONLY"}
    rows = [pg, pdf, pdf_only]
    before = deepcopy(rows)
    reviews = {"PDF-REVIEW": {"decision": "remove_pdf_duplicate", "original_pg_ids": ["SYN-1"], "pdf_document_id": "PDF-NEW"}}
    result = prefer_pg_active_documents(rows, original_document_ids={"SYN-1"}, reviews=reviews)
    assert [d["document_id"] for d in result] == ["SYN-1", "PDF-ONLY"]
    assert rows == before
    assert prefer_pg_active_documents(rows, original_document_ids={"SYN-1"}, reviews={}) == rows


def test_active_pdf_has_file_and_pages_without_changing_original_pg_or_body():
    pg = source()
    pdf = {**pg, "document_id": "PDF-NEW", "content": "独立PDF原文", "record_time": "2026-08-10T18:21+08:00"}
    rows = [pg, pdf]
    before = deepcopy(rows)
    reviews = {"PDF-CANDIDATE": {"pdf_document_type": "consultation_record", "pdf_document_id": "PDF-NEW",
                                  "source_file_id": "SYN-PDF", "source_pages": [4, 5]}}
    result = attach_pdf_material_sources(rows, original_document_ids={"SYN-1"}, reviews=reviews)
    assert result[0] == pg
    assert result[1]["source_file_id"] == "SYN-PDF"
    assert result[1]["source_pages"] == [4, 5]
    assert result[1]["content"] == pdf["content"] and result[1]["record_time"] == pdf["record_time"]
    assert rows == before
    assert attach_pdf_material_sources(rows, original_document_ids=None, reviews=reviews) == rows


def test_original_entity_has_pdf_source_only_after_explicit_pdf_precedence():
    pg = source()
    rows = [pg]
    review = {"pdf_document_type": "consultation_record", "pdf_document_id": "SYN-1",
              "source_file_id": "SYN-PDF", "source_pages": [40, 40], "decision": "keep_pdf_only"}
    assert attach_pdf_material_sources(rows, original_document_ids={"SYN-1"}, reviews={"candidate": review}) == rows
    preferred = {**review, "decision": "prefer_pdf"}
    result = attach_pdf_material_sources(rows, original_document_ids={"SYN-1"}, reviews={"candidate": preferred})
    assert result[0]["source_file_id"] == "SYN-PDF"
    assert result[0]["source_pages"] == [40, 40]
    assert result[0]["content"] == pg["content"] and result[0]["document_id"] == "SYN-1"
    assert "source_file_id" not in pg
