from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_pathology_exam_master_should_assemble_specimen_and_request_fields() -> None:
    document = assemble_document(
        "pathology_exam_master",
        {
            "pathology_exam_id": "PEM1",
            "pathology_id": "P2026001",
            "clinical_history": "结肠肿物术后送检。",
            "surgery_name": "结肠肿物切除术",
            "specimen_name": "结肠肿物标本",
            "request_dept": "普外科",
            "request_physician": "李医生",
            "request_datetime": "2026-02-03 10:00:00",
        },
    )

    assert document.document_title == "病理检查申请单"
    assert document.document_id == "PEM1"
    assert document.assembly_status in {"assembled", "partial"}
    assert "结肠肿物标本" in document.assembled_text
    assert "结肠肿物切除术" in document.assembled_text
    assert any(field.source_field == "specimen_name" and field.used for field in document.source_fields)


def test_pathology_exam_report_should_assemble_diagnosis_and_findings() -> None:
    document = assemble_document(
        "pathology_exam_report",
        {
            "pathology_exam_id": "PER1",
            "pathology_id": "P2026001",
            "specimen_name": "阑尾标本",
            "eye_findings": "灰白组织一块。",
            "microscope_findings": "阑尾壁急性炎症细胞浸润。",
            "diagnosis": "急性化脓性阑尾炎。",
            "report_status": "已审核",
            "report_datetime": "2026-02-05 09:00:00",
            "reporter": "王医生",
        },
    )

    assert document.document_title == "病理检查报告"
    assert document.document_id == "PER1"
    assert document.assembly_status in {"assembled", "partial"}
    assert "阑尾标本" in document.assembled_text
    assert "急性化脓性阑尾炎" in document.assembled_text
    assert any(field.source_field == "diagnosis" and field.used for field in document.source_fields)


def test_build_document_select_columns_should_include_pathology_fields() -> None:
    columns = build_document_select_columns(
        "pathology_exam_report",
        {"pathology_exam_id", "specimen_name", "diagnosis", "report_datetime", "record_content"},
    )

    assert "pathology_exam_id" in columns
    assert "specimen_name" in columns
    assert "diagnosis" in columns
    assert "report_datetime" in columns
