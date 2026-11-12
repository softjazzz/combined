from app.services.document_assembly.assembler import assemble_document, build_document_select_columns
from app.services.bundles.assembly import _inventory_entry
from app.services.bundles.emr_view import build_documents_from_domain_bundles, build_render_view


def view(row):
    entry = _inventory_entry(table_name="surgery_record", row=row)
    doc = build_documents_from_domain_bundles({"surgery": {"source_documents": [entry]}})[0]
    return doc, build_render_view(doc)


def test_datetime_and_full_body():
    body = "step: incision\nfinding: normal\n" + ("suture. " * 200).strip()
    row = {"document_id": "s1", "surgery_process": body, "surgery_begin_datetime": "2026-11-01 09:00"}
    assert set(row) <= set(build_document_select_columns("surgery_record", set(row)))
    doc, result = view(row)
    fields = {f["key"]: f["value"] for b in result["render_blocks"] for f in b.get("fields", [])}
    assert fields["surgery_process"] == body
    assert fields["surgery_begin_datetime"] == row["surgery_begin_datetime"]
    assert doc["has_content"] is True
    source = next(f for f in assemble_document("surgery_record", row).source_fields if f.source_field == "surgery_process")
    assert source.source_table == "surgery_record"
    assert source.raw_value_preview == body


def test_modified_time_does_not_become_record_time():
    _, result = view({"document_id": "modified-only", "surgery_process": "synthetic", "last_modified_datetime": "2026-11-01 12:00"})
    assert result["document_meta"]["record_time_source"] == ""
    fields = {f["key"]: f["value"] for b in result["render_blocks"] for f in b.get("fields", [])}
    assert fields["last_modified_datetime"] == "2026-11-01 12:00"


def test_empty_template():
    doc, result = view({"document_id": "empty", "submit_datetime": "2026-11-01 10:00"})
    assert doc["has_content"] is False
    assert result["empty_reason"] == "document_empty"


def test_status_clock_source():
    doc, result = view({"document_id": "s2", "surgery_process": "synthetic", "document_status": "Save", "submit_datetime": "2026-11-01 10:00"})
    assert doc["document_status"] == "Save"
    assert result["document_meta"]["document_status"] == "Save"
    assert result["document_meta"]["record_time_source"] == "source_submit_time"
    text = assemble_document("surgery_record", {"surgery_process": "synthetic", "submit_datetime": "2026-11-01 10:00"}).assembled_text
    assert "\u8bb0\u5f55\u65f6\u95f4: 2026-11-01 10:00" not in text
    assert "\u63d0\u4ea4\u65f6\u95f4: 2026-11-01 10:00" in text


def test_time_alias_identity():
    doc = assemble_document("surgery_record", {"surgery_process": "synthetic", "surgery_begin_time": "2026-11-01 09:00", "surgery_begin_datetime": "2026-11-01 09:05"})
    fields = {f.source_field: f.raw_value_preview for f in doc.source_fields}
    assert fields["surgery_begin_time"] == "2026-11-01 09:00"
    assert fields["surgery_begin_datetime"] == "2026-11-01 09:05"


def test_distinct_ids():
    entries = [_inventory_entry(table_name="surgery_record", row={"document_id": key, "surgery_process": "same procedure"}) for key in ("one", "two")]
    docs = build_documents_from_domain_bundles({"surgery": {"source_documents": entries}})
    assert {d["document_id"] for d in docs} == {"one", "two"}
