from app.services.document_assembly.assembler import assemble_document, build_document_select_columns


def test_inpat_bill_item_should_assemble_execution_like_summary() -> None:
    document = assemble_document(
        "inpat_bill_item",
        {
            "bill_item_id": "B1",
            "order_id": "O1",
            "item_type": "康复治疗",
            "medical_catalog_name": "中频脉冲电治疗",
            "quantity": "1",
            "quantity_unit": "次",
            "billing_datetime": "2026-02-03 09:00:00",
            "executive_dept_name": "康复医学科",
        },
    )

    assert document.assembly_status in {"assembled", "partial"}
    assert "中频脉冲电治疗" in document.assembled_text
    assert "康复医学科" in document.assembled_text
    assert any(field.source_field == "medical_catalog_name" and field.used for field in document.source_fields)


def test_build_document_select_columns_should_include_inpat_bill_item_fields() -> None:
    columns = build_document_select_columns(
        "inpat_bill_item",
        {"bill_item_id", "order_id", "medical_catalog_name", "billing_datetime", "record_content"},
    )

    assert "bill_item_id" in columns
    assert "order_id" in columns
    assert "medical_catalog_name" in columns
    assert "billing_datetime" in columns
