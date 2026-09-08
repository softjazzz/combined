from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_admission_fields_preserve_time_and_full_special_exam():
    special = "专科检查内容。" * 40
    document = assemble_document("admission_record", {
        "admission_datetime": "2026-08-30 09:13:06",
        "record_datetime": "2026-08-30 10:00:00",
        "v2_schema": {"checkup_special": special},
    })
    sections = {s.section_label: s.text for s in document.sections}
    assert sections["入院时间"] == "2026-08-30 09:13:06"
    assert sections["专科检查"] == special
    assert special in document.assembled_text
    assert document.record_time == "2026-08-30 10:00:00"
    assert "admission_datetime" in build_document_select_columns(
        "admission_record", {"admission_datetime", "v2_schema", "record_content"}
    )


def test_admission_time_does_not_disable_full_text_fallback():
    document = assemble_document("admission_record", {
        "admission_datetime": "2026-08-30 09:13:06",
        "record_content": "入院记录完整正文",
    })
    assert "入院记录完整正文" in document.assembled_text
    assert any(s.text == "入院记录完整正文" for s in document.sections)


def test_missing_admission_time_is_not_replaced_with_record_time():
    document = assemble_document("admission_record", {"record_datetime": "2026-08-30 10:00:00"})
    assert not any(s.section_key == "admission_datetime" for s in document.sections)
