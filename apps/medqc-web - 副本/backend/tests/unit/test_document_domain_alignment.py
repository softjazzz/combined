from app.services.document_domain_alignment import (
    align_document_domain_fields,
    normalize_document_label,
    normalize_applicable_doc_codes,
)


def test_normalize_document_label_should_handle_legacy_names():
    assert normalize_document_label("病程记录") == "日常病程记录"
    assert normalize_document_label("上级医师查房记录") == "上级查房记录"
    assert normalize_document_label("unknown") == "日常病程记录"


def test_normalize_applicable_doc_codes_should_return_standard_codes():
    assert normalize_applicable_doc_codes(["病程记录", "术前讨论"], "病程记录") == [
        "daily_course_record",
        "presurg_discussion",
    ]


def test_align_document_domain_fields_should_fill_execution_meta():
    document_type, applicable_documents, check_logic = align_document_domain_fields(
        document_type="病程记录",
        applicable_documents=["术前讨论"],
        check_logic={},
    )

    assert document_type == "日常病程记录"
    assert applicable_documents == ["presurg_discussion"]
    assert check_logic["execution_domain"] == "surgery"
    assert check_logic["doc_scope"] == "primary"
