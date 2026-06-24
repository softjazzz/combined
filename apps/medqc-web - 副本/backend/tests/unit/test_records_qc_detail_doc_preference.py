from app.routers.records import _apply_document_payload, _should_prefer_bundle_documents


def test_should_prefer_bundle_documents_when_bundle_has_more_unique_docs():
    existing_docs = [
        {"id": "admission-1", "document_type": "admission_record"},
        {"id": "course-1", "document_type": "daily_course_record"},
    ]
    bundle_docs = [
        {"document_id": "admission-1", "source_table": "admission_record"},
        {"document_id": "course-1", "source_table": "daily_course_record"},
        {"document_id": "presurg-1", "source_table": "presurg_summary"},
        {"document_id": "anes-1", "source_table": "anesthesia_record"},
    ]

    assert _should_prefer_bundle_documents(existing_docs, bundle_docs) is True


def test_should_not_prefer_bundle_documents_when_bundle_is_not_richer():
    existing_docs = [
        {"id": "admission-1", "document_type": "admission_record"},
        {"id": "course-1", "document_type": "daily_course_record"},
    ]
    bundle_docs = [
        {"document_id": "admission-1", "source_table": "admission_record"},
        {"document_id": "course-1", "source_table": "daily_course_record"},
    ]

    assert _should_prefer_bundle_documents(existing_docs, bundle_docs) is False


def test_apply_document_payload_should_fill_document_notes_and_tree():
    target = {}
    docs = [
        {"document_type": "admission_record", "content": "入院情况", "document_id": "1", "document_title": "入院记录"},
        {"document_type": "daily_course_record", "content": "病程记录", "document_id": "2", "document_title": "病程记录"},
        {"document_type": "anesthesia_record", "content": "麻醉记录正文", "document_id": "3", "document_title": "麻醉记录"},
    ]
    tree = [{"key": "surgery", "children": [{"id": "3", "doc_type": "anesthesia_record"}]}]

    _apply_document_payload(target, docs, tree)

    assert target["raw_documents"] == docs
    assert target["documents_tree"] == tree
    assert target["admissionNote"] == "入院情况"
    assert target["progressNote"] == "病程记录"
    assert target["surgeryNote"] == "麻醉记录正文"
