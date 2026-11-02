from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medqc_ingest.contracts import SOURCE_COLUMN_CONTRACTS, contract_export_document
from medqc_ingest.domain import (
    IngestError,
    PublishRecord,
    build_records,
    project_record,
    resolve_interface,
    validate_interface_columns,
)
from medqc_ingest.service import PublishService

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "major-document-contracts.json"
TRANSFORM_PATH = ROOT / "tools" / "major_document_transform.py"


def _standalone() -> ModuleType:
    spec = importlib.util.spec_from_file_location("standalone_major_document", TRANSFORM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _raw_row(interface: str, document_id: str = "D1") -> dict[str, Any]:
    spec = resolve_interface(interface)
    values: dict[str, Any] = dict.fromkeys(spec.source_columns, "")
    values.update(institute_id="I", patient_id="P", visit_id="V")
    document_field = spec.key_fields[-1] if len(spec.key_fields) == 4 else "document_id"
    if document_field in values:
        values[document_field] = document_id
    assert spec.publish is not None
    for mapping in spec.publish.mappings:
        if mapping.source is None:
            continue
        if mapping.target_type == "text" and not values[mapping.source]:
            values[mapping.source] = f"value-{mapping.source}"
        elif mapping.target_type == "date":
            values[mapping.source] = "2026-10-28"
        elif mapping.target_type in {"datetime", "timestamptz"}:
            values[mapping.source] = "2026-10-28 09:30:00"
    values["institute_id"] = "I"
    values["patient_id"] = "P"
    values["visit_id"] = "V"
    if document_field in values:
        values[document_field] = document_id
    return values


def test_committed_json_matches_module_contract_and_source_counts() -> None:
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert committed == contract_export_document()
    assert committed["contains_phi"] is False
    assert committed["contract_version"] == 2
    counts = {
        item["interface"]: item["source_column_count"]
        for item in committed["interfaces"]
    }
    assert counts == {
        "web.mr": 148,
        "web.admission_record": 25,
        "web.first_course_record": 29,
        "web.daily_course_record": 34,
        "web.senior_course_record": 24,
        "web.consultation_record": 24,
        "web.discharge_record": 29,
    }


def test_web_mr_accepts_real_148_order_and_rejects_drift() -> None:
    spec = resolve_interface("web.mr")
    assert validate_interface_columns(spec, spec.source_columns) == list(spec.source_columns)
    reordered = list(spec.source_columns)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(IngestError) as exc_info:
        validate_interface_columns(spec, reordered)
    assert exc_info.value.location == "source_contract_mismatch"


@pytest.mark.parametrize(
    ("interface", "source_field"),
    [
        ("web.admission_record", "recordcontent"),
        ("web.first_course_record", "recordcontent"),
        ("web.daily_course_record", "record_content"),
        ("web.senior_course_record", "recordcontent"),
        ("web.consultation_record", "recordcontent"),
        ("web.discharge_record", "record_content"),
    ],
)
def test_six_document_alias_projections_preserve_full_text(
    interface: str, source_field: str
) -> None:
    content = "全文" * 200_000
    payload = _raw_row(interface)
    payload[source_field] = content
    projected = project_record(
        resolve_interface(interface),
        payload,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert projected["record_content"] == content
    assert projected["document_id"] == "D1"
    assert projected["submit_datetime"] == datetime(2026, 10, 28, 9, 30)


def test_raw_record_keeps_every_source_field_and_full_text() -> None:
    spec = resolve_interface("web.admission_record")
    row = _raw_row(spec.name)
    content = "正文" * 300_000
    row["recordcontent"] = content
    record = build_records(
        spec.source_columns,
        [tuple(row[column] for column in spec.source_columns)],
        spec.key_fields,
    )[0]
    assert tuple(record.payload) == spec.source_columns
    assert record.payload["recordcontent"] == content


def test_dates_use_shanghai_rules_empty_is_null_and_1840_is_rejected() -> None:
    daily = _raw_row("web.daily_course_record")
    daily["physician_sign_datetime"] = "2026-10-28T01:30:00Z"
    projected = project_record(
        resolve_interface("web.daily_course_record"),
        daily,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert projected["physician_sign_datetime"].utcoffset() == timedelta(hours=8)
    assert projected["physician_sign_datetime"].hour == 9

    discharge = _raw_row("web.discharge_record")
    discharge["discharge_date"] = ""
    projected = project_record(
        resolve_interface("web.discharge_record"),
        discharge,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert projected["discharge_date"] is None
    assert projected["record_content"] != ""
    discharge["admission_date"] = "1840-01-01"
    with pytest.raises(IngestError) as exc_info:
        project_record(
            resolve_interface("web.discharge_record"),
            discharge,
            datetime(2026, 10, 28, tzinfo=timezone.utc),
        )
    assert exc_info.value.location == "abnormal_clinical_date"


def test_submit_is_not_promoted_to_signature() -> None:
    admission = project_record(
        resolve_interface("web.admission_record"),
        _raw_row("web.admission_record"),
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert "physician_sign" not in admission
    assert "physician_sign_datetime" not in admission

    empty_core_values = _raw_row("web.admission_record")
    empty_core_values["recordcontent"] = ""
    empty_core_values["submitdatetime"] = None
    projected = project_record(
        resolve_interface("web.admission_record"),
        empty_core_values,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert projected["record_content"] == ""
    assert projected["submit_datetime"] is None
    assert "physician_sign" not in projected


@pytest.mark.parametrize("interface", ["web.admission_record", "web.discharge_record"])
def test_document_id_required_even_when_target_key_has_only_case_fields(interface: str) -> None:
    spec = resolve_interface(interface)
    row = _raw_row(interface)
    row[spec.key_fields[-1]] = ""
    with pytest.raises(IngestError) as error:
        project_record(spec, row, datetime(2026, 10, 28, tzinfo=timezone.utc))
    assert error.value.location == "missing_source_key"


def test_first_course_maps_existing_structured_location_fields() -> None:
    raw = _raw_row("web.first_course_record")
    raw.update(
        dept_name="dept",
        ward_name="ward",
        ward_no="ward-no",
        bed_no="bed-no",
        age="42",
    )
    projected = project_record(
        resolve_interface("web.first_course_record"),
        raw,
        datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert {
        field: projected[field]
        for field in ("dept_name", "ward_name", "ward_no", "bed_no", "age")
    } == {
        "dept_name": "dept",
        "ward_name": "ward",
        "ward_no": "ward-no",
        "bed_no": "bed-no",
        "age": "42",
    }


def test_daily_record_time_is_projected_without_using_other_clocks() -> None:
    raw = _raw_row("web.daily_course_record")
    raw.update(
        record_datetime="2026-10-26 09:00:00",
        submit_datetime="2026-10-27 10:00:00",
        physician_sign_datetime="2026-10-28 11:00:00+08:00",
    )
    spec = resolve_interface("web.daily_course_record")
    projected = project_record(spec, raw, datetime(2026, 10, 29, tzinfo=timezone.utc))
    assert projected["record_datetime"] == datetime(2026, 10, 26, 9)
    assert projected["submit_datetime"] == datetime(2026, 10, 27, 10)
    raw["record_datetime"] = ""
    empty_record_time = project_record(spec, raw, datetime(2026, 10, 29, tzinfo=timezone.utc))
    assert empty_record_time["record_datetime"] is None


def test_standalone_catalog_preflight_allows_optional_051_gaps() -> None:
    transform = _standalone()
    contract = transform.load_contract(CONTRACT_PATH)
    item = transform.get_interface(contract, "web.daily_course_record")
    sql_types = {
        "text": "text",
        "date": "date",
        "datetime": "timestamp without time zone",
        "timestamptz": "timestamp with time zone",
    }
    catalog = {
        mapping["target"]: sql_types[mapping["target_type"]]
        for mapping in item["field_mappings"]
        if mapping["target"] != "physician_sign_datetime"
    }
    result = transform.preflight_target_catalog(
        contract,
        "web.daily_course_record",
        catalog,
        item["target_primary_key"],
    )
    assert result.unavailable_optional_targets == ("physician_sign_datetime",)
    assert "physician_sign_datetime" not in result.writable_target_columns
    assert "record_content" in result.writable_target_columns
    raw = _raw_row("web.daily_course_record")
    raw["record_content"] = "完整正文" * 10_000
    transformed = transform.transform_row(
        contract,
        "web.daily_course_record",
        raw,
        result.writable_target_columns,
    )
    assert transformed["record_content"] == raw["record_content"]
    assert transformed["document_id"] == "D1"
    assert "physician_sign_datetime" not in transformed
    del catalog["record_content"]
    with pytest.raises(transform.ContractError) as exc_info:
        transform.preflight_target_catalog(
            contract,
            "web.daily_course_record",
            catalog,
            item["target_primary_key"],
        )
    assert exc_info.value.location == "target_required_columns_missing"


class _PublishCursor:
    schema_hash = "a" * 64
    source_columns = SOURCE_COLUMN_CONTRACTS["web.admission_record"]

    def __init__(self, records: list[PublishRecord]) -> None:
        self.records = records

    def fetchmany(self, size: int) -> list[PublishRecord]:
        del size
        records, self.records = self.records, []
        return records

    def close(self) -> None:
        pass


class _Audit:
    def __init__(self, records: list[PublishRecord]) -> None:
        self.cursor = _PublishCursor(records)
        self.rolled_back = False

    def connect_control(self) -> None: pass
    def acquire_lock(self, scope: str) -> bool: return True
    def release_lock(self, scope: str) -> None: pass
    def start_publish(self, interface: str, evidence_version: str) -> int: return 1
    def open_verified_raw(self, interface: str, target_key_fields: Any) -> _PublishCursor:
        return self.cursor
    def begin_publish_data(self) -> None: pass
    def write_publish_lineage(self, publish_batch_id: int, rows: Any) -> None: pass
    def commit_publish_data(self) -> None: pass
    def rollback_publish_data(self) -> None: self.rolled_back = True
    def drop_publish_data(self) -> None: pass
    def mark_publish_succeeded(self, *args: Any) -> None: pass
    def mark_publish_failed(self, *args: Any) -> None: pass
    def close(self) -> None: pass


class _Cdm:
    def __init__(self) -> None:
        self.upsert_count = 0
        self.rolled_back = False

    def begin(self) -> None: pass
    def prepare_target_contract(self, target: Any) -> Any: return target
    def upsert_target(self, target: Any, rows: Any) -> int:
        self.upsert_count += len(rows)
        return len(rows)
    def commit(self) -> None: pass
    def rollback(self) -> None: self.rolled_back = True
    def close(self) -> None: pass


def _publish_record(document_id: str) -> PublishRecord:
    return PublishRecord(
        payload=_raw_row("web.admission_record", document_id),
        completed_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        source_batch_id=1,
        source_key_hash=document_id.ljust(64, "0"),
        row_hash=document_id.ljust(64, "1"),
    )


def test_admission_multiple_documents_for_one_case_fail_before_upsert() -> None:
    audit = _Audit([_publish_record("D1"), _publish_record("D2")])
    cdm = _Cdm()
    with pytest.raises(IngestError) as exc_info:
        PublishService(audit, cdm, 100).run(resolve_interface("web.admission_record"))
    assert exc_info.value.location == "duplicate_key"
    assert cdm.upsert_count == 0
    assert cdm.rolled_back and audit.rolled_back
