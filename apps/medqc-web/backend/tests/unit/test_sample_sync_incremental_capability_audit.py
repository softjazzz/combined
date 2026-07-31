from __future__ import annotations

from backend.scripts.audit_sample_sync_incremental_capabilities import (
    REQUIRED_PRIMARY_VISIBILITY_TABLES,
    audit_table_capability,
    audit_tables,
    render_markdown_report,
)


def test_prefers_reliable_update_column_over_record_time() -> None:
    result = audit_table_capability(
        table_config={
            "name": "daily_course_record",
            "source_table": "daily_course_record",
            "key_fields": ["patient_id", "visit_id", "document_id"],
        },
        columns={"patient_id", "visit_id", "document_id", "record_time", "modify_time"},
        primary_keys=["patient_id", "visit_id", "document_id"],
    )

    assert result["incremental_strategy"] == "updated_at"
    assert result["watermark_column"] == "modify_time"
    assert result["record_time_column"] == "record_time"


def test_uses_record_time_only_for_append_only_table_with_stable_key() -> None:
    result = audit_table_capability(
        table_config={
            "name": "labtest_item_report",
            "key_fields": ["patient_id", "visit_id", "test_no", "item_no"],
            "incremental_strategy": "append_only_record_time",
        },
        columns={"patient_id", "visit_id", "test_no", "item_no", "report_datetime"},
        primary_keys=[],
    )

    assert result["incremental_strategy"] == "append_only_record_time"
    assert result["watermark_column"] == "report_datetime"
    assert result["stable_key"] is True


def test_record_time_without_explicit_append_only_contract_is_not_incremental() -> None:
    result = audit_table_capability(
        table_config={
            "name": "labtest_item_report",
            "key_fields": ["patient_id", "visit_id", "test_no", "item_no"],
        },
        columns={"patient_id", "visit_id", "test_no", "item_no", "report_datetime"},
        primary_keys=[],
    )

    assert result["incremental_strategy"] == "full_visit_reload"
    assert "需院方确认只增不改" in result["risks"]


def test_falls_back_to_full_visit_reload_without_reliable_change_signal() -> None:
    result = audit_table_capability(
        table_config={
            "name": "mr",
            "key_fields": ["patient_id", "visit_id"],
            "date_field": "update_time",
        },
        columns={"patient_id", "visit_id", "admission_datetime"},
        primary_keys=[],
    )

    assert result["incremental_strategy"] == "full_visit_reload"
    assert result["watermark_column"] == ""
    assert "配置声明的时间字段不存在" in result["risks"]


def test_audit_lists_missing_primary_visibility_table_as_contract_gap() -> None:
    results = audit_tables(
        table_configs=[{"name": "mr", "key_fields": ["patient_id", "visit_id"]}],
        schemas={"mr": {"columns": ["patient_id", "visit_id"], "primary_keys": []}},
    )

    registration = next(item for item in results if item["name"] == "inpat_registration")
    assert "inpat_registration" in REQUIRED_PRIMARY_VISIBILITY_TABLES
    assert registration["contract_status"] == "missing_from_sync_contract"
    assert registration["incremental_strategy"] == "full_visit_reload"


def test_markdown_report_never_exposes_connection_secrets() -> None:
    results = audit_tables(
        table_configs=[
            {
                "name": "daily_course_record",
                "source_table": "daily_course_record",
                "key_fields": ["patient_id", "visit_id", "document_id"],
            }
        ],
        schemas={
            "daily_course_record": {
                "columns": ["patient_id", "visit_id", "document_id", "update_time"],
                "primary_keys": ["patient_id", "visit_id", "document_id"],
            }
        },
    )

    report = render_markdown_report(
        results,
        source_summary={
            "mode": "schema_snapshot",
            "schema": "web",
            "dsn": "postgresql://audit_user:super-secret@192.0.2.10:5432/customer",
            "password": "super-secret",
        },
    )

    assert "super-secret" not in report
    assert "192.0.2.10" not in report
    assert "postgresql://" not in report
    assert "schema_snapshot" in report
