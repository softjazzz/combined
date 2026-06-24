from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_admission_record_diagnosis_should_render_initial_diagnosis() -> None:
    document = assemble_document(
        "admission_record_diagnosis",
        {
            "document_id": "4415760||1",
            "diagnosis_id": "2",
            "diagnosis_type": "初步诊断",
            "diagnosis_name": "1、右侧肩袖损伤；2、疼痛",
            "diagnosis_main": "否",
            "update_time": "2026-03-13 19:19:56",
        },
    )

    assert document.document_title == "入院记录诊断-初步诊断-2"
    assert document.document_id == "4415760||1::diagnosis::2"
    assert document.assembly_status == "assembled"
    assert "诊断类型: 初步诊断" in document.assembled_text
    assert "诊断序号" not in document.assembled_text
    assert "诊断名称: 1、右侧肩袖损伤；2、疼痛" in document.assembled_text
    assert document.sections[0].section_label == "入院记录诊断"


def test_build_document_select_columns_should_include_admission_diagnosis_fields() -> None:
    columns = build_document_select_columns(
        "admission_record_diagnosis",
        {"document_id", "diagnosis_type", "diagnosis_name", "diagnosis_code", "v2_schema"},
    )

    assert columns == ["document_id", "diagnosis_type", "diagnosis_name", "diagnosis_code", "v2_schema"]


def test_discharge_record_diagnosis_should_render_discharge_diagnosis() -> None:
    document = assemble_document(
        "discharge_record_diagnosis",
        {
            "document_id": "4500001||8",
            "diagnosis_id": "3",
            "diagnosis_type": "出院诊断",
            "diagnosis_name": "急性阑尾炎",
            "diagnosis_code": "K35.900",
            "diagnosis_main": "是",
            "update_time": "2026-03-20 09:30:00",
        },
    )

    assert document.document_title == "出院记录诊断-出院诊断-3"
    assert document.document_id == "4500001||8::diagnosis::3"
    assert document.assembly_status == "assembled"
    assert "诊断类型: 出院诊断" in document.assembled_text
    assert "诊断序号" not in document.assembled_text
    assert "诊断名称: 急性阑尾炎" in document.assembled_text
    assert document.sections[0].section_label == "出院记录诊断"


def test_build_document_select_columns_should_include_discharge_diagnosis_fields() -> None:
    columns = build_document_select_columns(
        "discharge_record_diagnosis",
        {"document_id", "diagnosis_type", "diagnosis_name", "diagnosis_code", "v2_schema"},
    )

    assert columns == ["document_id", "diagnosis_type", "diagnosis_name", "diagnosis_code", "v2_schema"]
