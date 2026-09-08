import pytest

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


@pytest.mark.parametrize("canonical", [{}, {"admission_datetime": None}, {"admission_datetime": ""}])
@pytest.mark.parametrize("via_v2", [False, True])
def test_admission_time_alias_preserves_source_and_document_times(canonical, via_v2):
    admission = {"admission_time": "2025-08-12 17:24:13"}
    payload = {
        **canonical,
        **({"v2_schema": admission} if via_v2 else admission),
        "record_time": "2025-08-12 17:42:11",
        "submit_time": "2025-08-20 20:15:36",
        "record_content": "入院记录完整正文",
    }
    document = assemble_document("admission_record", payload)
    section = next(s for s in document.sections if s.section_key == "admission_datetime")
    assert section.text == "2025-08-12 17:24:13"
    assert section.source_field == "admission_time"
    assert any(f.source_field == "admission_time" and f.used for f in document.source_fields)
    assert document.record_time == "2025-08-12 17:42:11"
    assert document.submit_time == "2025-08-20 20:15:36"
    assert "入院记录完整正文" in document.assembled_text


@pytest.mark.parametrize("via_v2", [False, True])
def test_admission_datetime_has_priority_over_alias(via_v2):
    canonical = {"admission_datetime": "2025-08-12 17:24:13"}
    document = assemble_document("admission_record", {
        **({"v2_schema": canonical} if via_v2 else canonical),
        "admission_time": "2025-08-11 10:00:00",
    })
    section = next(s for s in document.sections if s.section_key == "admission_datetime")
    assert section.text == "2025-08-12 17:24:13"
    assert section.source_field == "admission_datetime"


def test_admission_select_retains_both_available_time_fields():
    columns = build_document_select_columns("admission_record", {
        "admission_datetime", "admission_time", "record_time", "submit_time",
    })
    assert {"admission_datetime", "admission_time", "record_time", "submit_time"} <= set(columns)
