from __future__ import annotations

from importlib import import_module


def test_persistent_bundle_probe_should_report_distinct_and_surface_counts(monkeypatch):
    audit = import_module("scripts.audit_sample_source_coverage")

    def fake_bundle_rows_for_visit_ids(conn, *, bundle_table: str, **kwargs):
        payload = {
            "source_table_coverage": {"blood_application": {"row_count": 1}},
            "assembly_coverage": {"blood_application": {"assembled_count": 1}},
        }
        if bundle_table in {"running_record_bundle", "final_record_bundle"}:
            return [
                {
                    "visit_id": "V001",
                    "bundle_schema_version": audit.BUNDLE_SCHEMA_VERSION_CURRENT,
                    "structured_context": payload,
                }
            ]
        return []

    monkeypatch.setattr(audit, "_bundle_rows_for_visit_ids", fake_bundle_rows_for_visit_ids)

    result = audit._build_persistent_bundle_probe(
        object(),
        table_names=["blood_application"],
        visit_ids=["V001"],
        bundle_schema="public",
    )

    coverage = result["blood_application"]
    assert coverage["bundle_surface_hit_count"] == 2
    assert coverage["bundle_surface_assembled_count"] == 2
    assert coverage["distinct_bundle_hit_visit_count"] == 1
    assert coverage["distinct_bundle_assembled_visit_count"] == 1
    assert coverage["bundle_hit_visit_count"] == 1
    assert coverage["bundle_status"] == "covered"
