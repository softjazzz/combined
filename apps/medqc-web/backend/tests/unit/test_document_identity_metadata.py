from app.services.bundles.assembly import _inventory_entry
from app.services.bundles.emr_view import _normalize_source_document
from app.services.document_assembly.assembler import (
    build_document_select_columns,
    extract_document_identity_metadata,
)
from app.services.luxian_0609.source_evidence_reader import _NATIVE_SOURCE_FIELDS


def test_document_select_columns_keep_authors_signatures_and_participants() -> None:
    available = {
        "document_id",
        "submitter",
        "submitter_id",
        "last_modifier",
        "last_modifier_id",
        "physician_sign",
        "physician_sign_datetime",
        "attending_physician_sign",
        "surgeon",
        "surgeon_physician_code",
        "discuss_staff",
    }

    columns = build_document_select_columns("presurg_discussion", available)

    assert set(available).issubset(columns)


def test_identity_metadata_separates_audit_authors_signatures_and_participants() -> None:
    metadata = extract_document_identity_metadata(
        {
            "submitter": "张医生",
            "submitter_id": "D001",
            "last_modifier": "李医生",
            "last_modifier_id": "D002",
            "physician_sign": "王医生",
            "physician_sign_datetime": "2026-07-07 15:30:00",
            "surgeon": "赵医生",
            "surgeon_physician_code": "D003",
            "discuss_staff": "赵医生、周医生",
        }
    )

    assert metadata["authors"] == [
        {"role": "submitter", "name": "张医生", "code": "D001"},
        {"role": "last_modifier", "name": "李医生", "code": "D002"},
    ]
    assert metadata["signatures"] == [
        {
            "role": "physician",
            "name": "王医生",
            "signed_at": "2026-07-07 15:30:00",
            "source_field": "physician_sign",
        }
    ]
    assert metadata["participants"] == [
        {"role": "surgeon", "name": "赵医生", "code": "D003"},
        {"role": "discussion_staff", "name": "赵医生、周医生"},
    ]


def test_bundle_inventory_keeps_document_identity_metadata() -> None:
    entry = _inventory_entry(
        table_name="presurg_discussion",
        row={
            "document_id": "discussion-1",
            "document_title": "术前讨论记录",
            "record_time": "2026-07-07 15:00:00",
            "record_content": "讨论手术方案。",
            "submitter": "张医生",
            "submitter_id": "D001",
            "physician_sign": "张医生",
            "physician_sign_datetime": "2026-07-07 15:10:00",
            "host_name": "李医生",
            "discuss_staff": "张医生、李医生",
        },
    )

    assert entry["authors"][0]["name"] == "张医生"
    assert entry["signatures"][0]["name"] == "张医生"
    assert entry["participants"] == [
        {"role": "discussion_host", "name": "李医生"},
        {"role": "discussion_staff", "name": "张医生、李医生"},
    ]

    normalized = _normalize_source_document(
        raw_doc=entry,
        index=0,
        execution_domain="running_record",
    )
    assert normalized["authors"] == entry["authors"]
    assert normalized["signatures"] == entry["signatures"]
    assert normalized["participants"] == entry["participants"]


def test_lx0609_source_reader_keeps_surgeon_and_discussion_identities() -> None:
    assert {
        "surgeon",
        "surgeon_physician_code",
        "surgeon_sign",
    }.issubset(_NATIVE_SOURCE_FIELDS["surgery_record"])
    assert {
        "surgeon",
        "surgeon_physician_code",
    }.issubset(_NATIVE_SOURCE_FIELDS["mr_surgery"])
    assert {
        "submitter",
        "submitter_id",
        "physician_sign",
        "physician_sign_datetime",
        "discuss_staff",
        "host_name",
    }.issubset(_NATIVE_SOURCE_FIELDS["presurg_discussion"])
