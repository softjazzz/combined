from app.services.document_assembly import assemble_document, build_document_select_columns


def test_exam_item_projection_preserves_report_linkage_and_display_name():
    available = {
        "exam_id",
        "item_id",
        "item_name",
        "item_code",
        "exam_zone",
        "report_time",
    }

    selected = set(build_document_select_columns("exam_item", available))

    assert selected == available


def test_exam_item_report_projection_preserves_linkage_and_result_fields():
    available = {
        "exam_id",
        "item_id",
        "description",
        "impression",
        "recommendation",
        "abnormal_sign",
        "report_status",
        "report_time",
        "record_content",
    }

    selected = set(build_document_select_columns("exam_item_report", available))

    assert available <= selected


def test_exam_master_with_structured_fields_is_a_readable_document():
    assembled = assemble_document(
        "exam_master",
        {
            "exam_id": "exam-001",
            "exam_type": "头颅CT平扫",
            "request_dept": "神经外科",
            "request_time": "2025-10-05 10:26:56+08",
            "report_time": "2025-10-05 11:08:29+08",
        },
    )

    assert assembled.document_id == "exam-001"
    assert assembled.display_time == "2025-10-05 11:08:29+08"
    assert assembled.assembly_status != "empty_document"
    assert "头颅CT平扫" in assembled.assembled_text
    assert any(section.source_field == "exam_type" for section in assembled.sections)


def test_labtest_master_with_structured_fields_is_a_readable_document():
    assembled = assemble_document(
        "labtest_master",
        {
            "test_id": "lab-001",
            "labtest_subject": "临检实验室",
            "specimen": "外周血",
            "report_datetime": "2025-10-05 12:00:00+08",
        },
    )

    assert assembled.document_id == "lab-001"
    assert assembled.display_time == "2025-10-05 12:00:00+08"
    assert assembled.assembly_status != "empty_document"
    assert "临检实验室" in assembled.assembled_text
    assert any(section.source_field == "specimen" for section in assembled.sections)
