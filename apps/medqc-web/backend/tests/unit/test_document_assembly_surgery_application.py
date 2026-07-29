from app.services.document_assembly.assembler import assemble_document


def test_surgery_application_should_assemble_structured_fields_without_record_content() -> None:
    document = assemble_document(
        "surgery_application",
        {
            "application_id": "apply-2496813-01",
            "order_id": "order-ignored-when-application-id-exists",
            "request_datetime": "2026-07-07 15:20:00",
            "request_physician": "韩平",
            "request_dept": "重症医学科（ICU）",
            "request_surgery_datetime": "2026-07-07 16:30:00",
            "surgery_name": "颅内血肿清除术",
            "surgery_code": "01.2300",
            "surgery_level": "四级",
            "anesthesia_method": "静吸复合全麻",
            "surgeon": "韩平",
            "record_content": "",
        },
    )

    assert document.document_id == "apply-2496813-01"
    assert document.document_title == "手术申请单"
    assert document.display_time == "2026-07-07 15:20:00"
    assert document.assembly_status == "partial"
    assert [(section.section_label, section.text) for section in document.sections] == [
        ("申请时间", "2026-07-07 15:20:00"),
        ("申请医师", "韩平"),
        ("申请科室", "重症医学科（ICU）"),
        ("申请手术时间", "2026-07-07 16:30:00"),
        ("手术名称", "颅内血肿清除术"),
        ("手术编码", "01.2300"),
        ("手术等级", "四级"),
        ("麻醉方式", "静吸复合全麻"),
        ("手术医师", "韩平"),
    ]


def test_surgery_application_should_fall_back_to_order_id() -> None:
    document = assemble_document(
        "surgery_application",
        {
            "order_id": "order-2496813-01",
            "surgery_name": "眼球破裂修补术",
        },
    )

    assert document.document_id == "order-2496813-01"
    assert document.document_title == "手术申请单"
    assert document.assembled_text == "眼球破裂修补术"
