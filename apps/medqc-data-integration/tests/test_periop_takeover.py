"""第二批独立profile与快照重放合同；纯fake，无真实连接和病历数据。"""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from periop_transform import project_row  # noqa: E402

from medqc_ingest.domain import (  # noqa: E402
    INTERFACE_REGISTRY,
    IngestError,
    PublishRecord,
    canonical_json,
    project_record,
    schema_signature,
    sha256_hex,
)
from medqc_ingest.periop_replay import (  # noqa: E402
    DISABLED,
    EXPECTED_COUNTS,
    SnapshotCursor,
    SnapshotSource,
    VerifiedPublishCursor,
    decode_values,
    explicit_window,
    load_profile,
    select_spec,
    validate_database,
)

CONTRACT, SPECS = load_profile(ROOT / "contracts/periop-acceptance-contracts.json")


def payload_for(spec):
    payload = dict.fromkeys(spec.source_columns)
    for key in spec.key_fields:
        payload[key] = "fictional-" + key
    for mapping in spec.publish.mappings:
        if mapping.source in spec.source_columns:
            if mapping.target_type in {"datetime", "timestamptz"}:
                payload[mapping.source] = "2026-10-26 08:10:11"
            elif mapping.target_type == "date":
                payload[mapping.source] = "2026-10-26"
    return payload


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.closed = False

    def fetchmany(self, size):
        result, self.rows = self.rows[:size], self.rows[size:]
        return result

    def close(self):
        self.closed = True


class TestPeriopTakeover(unittest.TestCase):
    def test_registry_is_independent_and_original_unchanged(self):
        self.assertEqual(len(SPECS), 13)
        self.assertEqual(set(SPECS), set(EXPECTED_COUNTS))
        self.assertEqual(len(INTERFACE_REGISTRY), 13)
        self.assertFalse(set(SPECS) & set(INTERFACE_REGISTRY))
        self.assertEqual(sum(EXPECTED_COUNTS.values()), 9365)

    def test_disabled_and_original_interfaces_rejected(self):
        for name in (*DISABLED, *INTERFACE_REGISTRY, "web.not_real"):
            with self.subTest(name=name), self.assertRaises(IngestError):
                select_spec(SPECS, name)

    def test_modified_contract_rejected_before_creating_specs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "contract.json"
            path.write_text(canonical_json(CONTRACT) + " ", encoding="utf-8")
            with self.assertRaises(IngestError) as caught:
                load_profile(path)
        self.assertEqual(caught.exception.location, "periop_frozen_contract_hash")

    def test_diagnostic_chain_preserves_type_not_private_exception_message(self):
        import prepare_periop_takeover as tool

        try:
            try:
                raise PermissionError("fictional-password-and-body-must-not-export")
            except PermissionError:
                raise IngestError("ingest_write_error", "static_location") from None
        except IngestError as error:
            result = tool.safe_exception_chain(error)
        self.assertEqual(
            [row["exception_type"] for row in result], ["IngestError", "PermissionError"]
        )
        self.assertNotIn("fictional-password", canonical_json(result))

    def test_all_active_conversions_equal_previously_accepted_converter(self):
        for spec in SPECS.values():
            with self.subTest(name=spec.name):
                payload = payload_for(spec)
                expected = project_row(CONTRACT, spec.name, payload)
                self.assertEqual(project_record(spec, payload, datetime.now()), expected)

    def test_risk_technical_key_is_stable_and_not_timestamp_dependent(self):
        spec = SPECS["web.surgery_risk_assessment"]
        payload = payload_for(spec)
        a = project_record(spec, payload, datetime(2026, 10, 26))
        b = project_record(spec, payload, datetime(2026, 10, 28))
        self.assertEqual(a["document_id"], b["document_id"])
        self.assertTrue(a["document_id"].startswith("cache-risk-v1:"))

    def test_target_key_grain_keeps_surgery_and_blood_detail(self):
        for name, expected in (
            ("web.mr_surgery", "surgery_id"),
            ("web.mr_bloodtrans", "bloodtrans_id"),
        ):
            spec = SPECS[name]
            self.assertIn(expected, spec.publish.primary_key)
            self.assertTrue(set(spec.publish.source_key_fields).issubset(spec.key_fields))

    def test_date_is_explicit_complete_shanghai_day(self):
        start, end = explicit_window("2026-10-26")
        self.assertEqual(start.utcoffset().total_seconds(), 28800)
        self.assertEqual((end - start).total_seconds(), 86400)
        for value in ("2026-1-1", "bad", "2100-01-01", "1840-12-31"):
            with self.subTest(value=value), self.assertRaises(IngestError):
                explicit_window(value)

    def test_database_names_reject_old_or_business_databases(self):
        for role in ("ingest", "cdm", "restore_ingest", "restore_cdm"):
            self.assertTrue(validate_database(f"medqc_periop_{role}_takeover_20261031235959", role))
            for value in (
                "medqc",
                "postgres",
                "medqc_cache_poc",
                "medqc_ingest_takeover_20261030205035",
            ):
                with self.assertRaises(IngestError):
                    validate_database(value, role)

    def test_array_hash_and_str_none_contract(self):
        spec = SPECS["web.nursing_record"]
        values = list(payload_for(spec).values())
        digest = sha256_hex(canonical_json(values))
        schema = schema_signature(spec.source_columns)[0]
        self.assertEqual(decode_values(spec, values, digest, schema), values)
        for altered in (values[:-1], [123, *values[1:]], ["different", *values[1:]]):
            with self.assertRaises(IngestError):
                decode_values(spec, altered, digest, schema)
        with self.assertRaises(IngestError):
            decode_values(spec, values, digest, "0" * 64)

    def test_snapshot_cursor_preserves_text_and_counts(self):
        spec = SPECS["web.nursing_record"]
        values = list(payload_for(spec).values())
        record = {
            "values_json": values,
            "row_hash": sha256_hex(canonical_json(values)),
            "schema_hash": schema_signature(spec.source_columns)[0],
        }
        inner = Cursor([(record, sha256_hex(canonical_json(record)))])
        cursor = SnapshotCursor(inner, spec, 1)
        self.assertEqual(cursor.fetchmany(500), [values])
        self.assertEqual(cursor.fetchmany(500), [])
        cursor.close()
        self.assertTrue(inner.closed)

    def test_truncated_or_tampered_archive_stops(self):
        spec = SPECS["web.nursing_record"]
        with self.assertRaises(IngestError):
            SnapshotCursor(Cursor([]), spec, 1).fetchmany(500)
        with self.assertRaises(IngestError):
            SnapshotCursor(Cursor([({}, "0" * 64)]), spec, 1).fetchmany(500)

    def test_known_vendor_failure_is_not_empty_success(self):
        spec = SPECS["web.blood_application"]
        source = SnapshotSource(
            lambda: None,
            {"interface_name": spec.name, "source_date": "2026-10-28", "status": "failed"},
        )
        with self.assertRaises(IngestError) as caught:
            source.query(spec, ["2026-10-28"])
        self.assertEqual(caught.exception.location, "periop_preserved_vendor_failure")

    def test_bad_arguments_rejected_before_archive_read(self):
        spec = SPECS["web.blood_application"]
        source = SnapshotSource(
            lambda: None,
            {"interface_name": spec.name, "source_date": "2026-10-28", "status": "failed"},
        )
        with self.assertRaises(IngestError) as caught:
            source.query(spec, ["2026-10-27"])
        self.assertEqual(caught.exception.location, "periop_snapshot_arguments")

    def test_publish_checks_row_hash_and_key_hash(self):
        spec = SPECS["web.nursing_record"]
        payload = payload_for(spec)
        record = PublishRecord(
            payload,
            datetime.now(),
            1,
            sha256_hex(canonical_json({f: payload[f] for f in spec.key_fields})),
            sha256_hex(canonical_json(payload)),
        )
        for changed in (
            record,
            replace(record, row_hash="0" * 64),
            replace(record, source_key_hash="0" * 64),
        ):
            inner = SimpleNamespace(fetchmany=lambda size, row=changed: [row])
            wrapper = VerifiedPublishCursor(inner, spec)
            if changed == record:
                self.assertEqual(wrapper.fetchmany(10), [record])
            else:
                with self.assertRaises(IngestError):
                    wrapper.fetchmany(10)

    def test_cli_rejects_disabled_before_reading_runtime_or_connecting(self):
        import run_periop_replay as tool

        with patch.object(tool, "read_runtime") as read:
            rc = tool.main(
                [
                    "--config",
                    "does-not-exist.json",
                    "--interface",
                    "web.surgery_record",
                    "--date",
                    "2026-10-28",
                ]
            )
        self.assertEqual(rc, 1)
        read.assert_not_called()

    def test_cli_has_no_automatic_or_incremental_switch(self):
        import run_periop_replay as tool

        with self.assertRaises(SystemExit) as caught:
            tool.main(
                [
                    "--config",
                    "unused",
                    "--interface",
                    "web.nursing_record",
                    "--date",
                    "2026-10-28",
                    "--incremental",
                ]
            )
        self.assertEqual(caught.exception.code, 2)

    def test_acl_rejects_similar_names_not_actual_sids(self):
        import prepare_periop_takeover as tool

        # 模拟仅只读ACL查询，绝不读取实际凭据。
        good = {
            "protected": True,
            "rules": [
                {"sid": sid, "rights": 2032127, "inherited": False, "type": 0}
                for sid in ("S-1-5-18", "S-1-5-32-544")
            ],
        }
        for kind in ("valid", "foreign", "readonly", "inherited"):
            doc = copy.deepcopy(good)
            if kind == "foreign":
                doc["rules"][1]["sid"] = "EVILDOMAIN\\Administrators"
            if kind == "readonly":
                doc["rules"][1]["rights"] = 1179817
            if kind == "inherited":
                doc["rules"][0]["inherited"] = True
            with patch.object(
                tool.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout=canonical_json(doc).encode()),
            ):
                if kind == "valid":
                    tool.check_acl(ROOT)
                else:
                    with self.assertRaises(IngestError):
                        tool.check_acl(ROOT)


if __name__ == "__main__":
    unittest.main()
