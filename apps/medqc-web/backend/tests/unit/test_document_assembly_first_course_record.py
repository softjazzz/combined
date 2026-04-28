import json

from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_first_course_record_should_fallback_to_v2_record_content_when_structured_fields_empty() -> None:
    document = assemble_document(
        "first_course_record",
        {
            "document_id": "first-course-1",
            "record_time": "2026-04-28 09:30:00",
            "v2_schema": json.dumps(
                {
                    "case_characteristic": "",
                    "diagnose_based_on": "",
                    "differential_diagnosis": "",
                    "treatment_plan": "",
                    "record_content": "患者因胸痛1周入院，结合心电图改变考虑冠心病。",
                },
                ensure_ascii=False,
            ),
        },
    )

    assert document.assembly_status == "partial"
    assert document.assembled_text == "患者因胸痛1周入院，结合心电图改变考虑冠心病。"
    assert document.sections[0].source_field == "record_content"
    assert "empty_document" not in document.data_quality_flags


def test_build_document_select_columns_should_include_v2_schema_for_first_course_record() -> None:
    columns = build_document_select_columns(
        "first_course_record",
        {"document_id", "record_time", "v2_schema"},
    )

    assert columns == ["document_id", "record_time", "v2_schema"]
