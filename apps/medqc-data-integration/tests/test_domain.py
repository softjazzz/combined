from datetime import datetime, timezone

import pytest

from medqc_ingest.domain import (
    WEB_MR_SOURCE_COLUMNS,
    WEB_MR_TARGET_COLUMNS,
    IngestError,
    KeyTracker,
    advisory_lock_key,
    build_records,
    project_web_mr,
    resolve_interface,
    validate_interface_columns,
)


def test_only_web_mr_is_registered() -> None:
    assert resolve_interface("web.mr").key_fields == (
        "institute_id",
        "patient_id",
        "visit_id",
    )
    with pytest.raises(IngestError) as exc_info:
        resolve_interface("web.orders")
    assert exc_info.value.kind == "interface_not_registered"


def test_web_mr_contract_is_77_plus_one_columns() -> None:
    assert len(WEB_MR_SOURCE_COLUMNS) == 77
    assert len(WEB_MR_TARGET_COLUMNS) == 78
    assert "local_sync_completed_at" not in WEB_MR_SOURCE_COLUMNS


def test_schema_drift_is_rejected() -> None:
    spec = resolve_interface("web.mr")
    drifted = list(spec.source_columns)
    drifted[-1] = "renamed_record_content"
    with pytest.raises(IngestError) as exc_info:
        validate_interface_columns(spec, drifted)
    assert exc_info.value.kind == "schema_validation_error"
    assert exc_info.value.location == "source_contract_mismatch"


def test_key_tracker_detects_duplicate_across_chunks() -> None:
    tracker = KeyTracker()
    tracker.extend(["one", "two"])
    with pytest.raises(IngestError) as exc_info:
        tracker.extend(["three", "one"])
    assert exc_info.value.location == "duplicate_key"


def test_build_records_rejects_missing_key() -> None:
    columns = ("institute_id", "patient_id", "visit_id")
    with pytest.raises(IngestError) as exc_info:
        build_records(columns, (("I", "P", ""),), columns)
    assert exc_info.value.kind == "key_validation_error"


def test_projection_requires_full_source_contract() -> None:
    with pytest.raises(IngestError) as exc_info:
        project_web_mr({}, datetime.now(timezone.utc))
    assert exc_info.value.location == "source_columns_missing"


def test_advisory_lock_key_is_stable_and_scoped() -> None:
    assert advisory_lock_key("extract:web.mr") == advisory_lock_key("extract:web.mr")
    assert advisory_lock_key("extract:web.mr") != advisory_lock_key("publish:web.mr")
