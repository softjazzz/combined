import pytest

from app.services.document_assembly.assembler import (
    assemble_document,
    build_document_select_columns,
)


@pytest.mark.parametrize(
    ("document_type", "payload", "expected_display_time"),
    [
        (
            "inpat_drug_order",
            {
                "generic_name": "注射用药品甲",
                "start_time": "2025-10-07 08:53:16",
                "prescribed_datetime": "2025-10-07 08:50:00",
            },
            "2025-10-07 08:53:16",
        ),
        (
            "inpat_nondrug_order",
            {
                "order_name": "临时检查医嘱",
                "order_time": "2025-10-07 09:10:00",
            },
            "2025-10-07 09:10:00",
        ),
        (
            "inpat_drug_order",
            {
                "generic_name": "口服药品乙",
                "prescribed_datetime": "2025-10-07 10:20:00",
            },
            "2025-10-07 10:20:00",
        ),
    ],
)
def test_order_document_should_project_business_time_for_display(
    document_type: str,
    payload: dict[str, str],
    expected_display_time: str,
) -> None:
    document = assemble_document(document_type, payload)

    assert document.record_time is None
    assert document.display_time == expected_display_time


def test_order_document_should_preserve_structured_display_fields() -> None:
    document = assemble_document(
        "inpat_drug_order",
        {
            "order_type": "长期",
            "generic_name": "注射用药品甲",
            "drug_specification": "1g/瓶",
            "single_dose": "1",
            "single_dose_unit": "瓶",
            "drug_frequency": "qd",
            "drug_apply_method": "静滴",
            "start_time": "2026-08-28 08:00:00",
            "stop_time": "2026-08-30 08:00:00",
            "prescribed_datetime": "2026-08-28 07:55:00",
            "prescribed_doctor": "张医生",
            "order_status": "执行中",
        },
    )

    fields = {field.source_field: field.raw_value_preview for field in document.source_fields}
    assert fields["order_type"] == "长期"
    assert fields["start_time"] == "2026-08-28 08:00:00"
    assert fields["stop_time"] == "2026-08-30 08:00:00"
    assert fields["drug_specification"] == "1g/瓶"


@pytest.mark.parametrize("document_type", ["inpat_drug_order", "inpat_nondrug_order"])
def test_order_document_should_use_order_id_as_stable_document_identity(
    document_type: str,
) -> None:
    document = assemble_document(
        document_type,
        {"order_id": "ORD-RED-1", "update_time": "2026-08-31 10:00:00"},
    )

    assert document.document_id == "ORD-RED-1"


@pytest.mark.parametrize("document_type", ["inpat_drug_order", "inpat_nondrug_order"])
def test_order_select_columns_should_include_order_id(document_type: str) -> None:
    columns = build_document_select_columns(document_type, {"order_id", "update_time"})

    assert "order_id" in columns


@pytest.mark.parametrize("document_type", ["inpat_drug_order", "inpat_nondrug_order"])
def test_order_plan_end_is_selected_and_preserved_as_separate_source_field(document_type):
    columns = build_document_select_columns(document_type, {"order_id", "planned_end_datetime"})
    assert "planned_end_datetime" in columns
    document = assemble_document(document_type, {
        "order_id": "safe-order", "planned_end_datetime": "2026-09-22T14:00:00+00:00",
    })
    fields = {field.source_field: field.raw_value_preview for field in document.source_fields}
    assert fields["planned_end_datetime"] == "2026-09-22T14:00:00+00:00"
    assert not fields.get("stop_time")


@pytest.mark.parametrize("document_type", ["inpat_drug_order", "inpat_nondrug_order"])
def test_order_plan_start_survives_select_assembly_and_render_without_changing_record_clock(document_type):
    from app.services.bundles.emr_view import build_documents_from_domain_bundles, build_render_view

    start = "2026-05-31T13:20:19+08:00"
    end = "2026-06-03T11:30:42+08:00"
    assert "planned_start_datetime" in build_document_select_columns(
        document_type, {"order_id", "planned_start_datetime", "planned_end_datetime"},
    )
    assembled = assemble_document(document_type, {
        "order_id": "safe-order", "order_name": "病危", "generic_name": "合成项目",
        "planned_start_datetime": start, "planned_end_datetime": end,
        "prescribed_datetime": "2026-05-31 13:21:54",
    })
    assert assembled.record_time is None
    assert assembled.display_time == "2026-05-31 13:21:54"
    fields = {field.source_field: field.raw_value_preview for field in assembled.source_fields}
    assert fields["planned_start_datetime"] == start
    assert not fields.get("stop_time")
    documents = build_documents_from_domain_bundles({"course": {"source_documents": [assembled.to_dict()]}})
    assert documents[0]["order_start_time"] == start
    assert documents[0]["order_planned_end_time"] == end
    assert not documents[0]["order_stop_time"]
    row = build_render_view(documents[0])["render_blocks"][0]["rows"][0]
    assert row["start_time"] == start
    assert row["planned_end_time"] == end
    assert not row["stop_time"]
