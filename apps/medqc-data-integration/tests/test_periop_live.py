"""真实源验收边界的纯fake测试，无Caché或数据库连接。"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind, IngestError  # noqa: E402
from medqc_ingest.periop_live import (  # noqa: E402
    LIVE_PROFILE,
    StrictLiveCursor,
    known_vendor_failure,
    live_database_names,
    live_spec,
    source_settings,
    verify_baseline_evidence,
)
from medqc_ingest.periop_replay import load_profile  # noqa: E402

CONTRACT, SPECS = load_profile(ROOT / "contracts/periop-acceptance-contracts.json")
ITEMS = {item["interface"]: item for item in CONTRACT["interfaces"]}


def vendor_error(
    state="HY000",
    text="fictional-private-body [Native Code 400]",
    kind=ErrorKind.SOURCE_QUERY,
    location="odbc_call",
):
    try:
        try:
            raise RuntimeError(state, text)
        except RuntimeError:
            raise IngestError(kind, location) from None
    except IngestError as error:
        return error


class TestPeriopLive(unittest.TestCase):
    def test_baseline_evidence_must_be_real_pg16_and_fixed_databases(self):
        from medqc_ingest.periop_live import BASELINE_CDM, BASELINE_INGEST

        acceptance = {
            "status": "PERIOP_ARCHIVE_TAKEOVER_ACCEPTED",
            "synthetic": False,
            "postgres_major": 16,
            "raw_rows": 9365,
            "history_rows": 9365,
            "source_unchanged": True,
            "active_interfaces": 13,
        }
        plan = {"databases": {"ingest": BASELINE_INGEST, "cdm": BASELINE_CDM}}
        verify_baseline_evidence(acceptance, plan)
        for change in ({"synthetic": True}, {"postgres_major": 18}, {"raw_rows": 1}):
            with self.assertRaises(IngestError):
                verify_baseline_evidence(dict(acceptance, **change), plan)
        with self.assertRaises(IngestError):
            verify_baseline_evidence(acceptance, {"databases": {"ingest": "medqc"}})

    def test_real_odbc_adapter_still_uses_server_keyword_with_fake_driver(self):
        from medqc_ingest.adapters.cache import OdbcSourceAdapter
        from medqc_ingest.config import SourceSettings

        captured = []
        driver = SimpleNamespace(
            connect=lambda text, **kwargs: (
                captured.append(text) or SimpleNamespace(close=lambda: None)
            )
        )
        settings = SourceSettings(
            "odbc",
            "fictional-host",
            1972,
            "fictional-ns",
            "fictional-user",
            Path("unused"),
            "InterSystems ODBC35",
            None,
            None,
            (),
        )
        with (
            patch("medqc_ingest.adapters.cache.importlib.import_module", return_value=driver),
            patch.object(SourceSettings, "password", return_value="fictional-secret"),
        ):
            adapter = OdbcSourceAdapter(settings)
            adapter.open()
            adapter.close()
        self.assertIn("SERVER=fictional-host;", captured[0])
        self.assertNotIn("HOST=", captured[0])

    def test_known_window_requires_native_code_400(self):
        item = ITEMS["web.blood_application"]
        self.assertTrue(known_vendor_failure(vendor_error(), item, "2026-10-28"))
        for error in (
            vendor_error("28000"),
            vendor_error(text="[Native Code 417]"),
            IngestError(ErrorKind.SOURCE_QUERY, "odbc_call"),
        ):
            self.assertFalse(known_vendor_failure(error, item, "2026-10-28"))

    def test_success_window_or_other_interface_is_not_whitelisted(self):
        self.assertFalse(
            known_vendor_failure(vendor_error(), ITEMS["web.blood_application"], "2026-10-26")
        )
        self.assertFalse(
            known_vendor_failure(vendor_error(), ITEMS["web.nursing_record"], "2026-10-28")
        )

    def test_connect_fetch_and_permission_errors_are_not_accepted(self):
        item = ITEMS["web.blood_application"]
        for error in (
            vendor_error(kind=ErrorKind.SOURCE_CONNECT, location="odbc_connect"),
            vendor_error(location="source_fetchmany"),
            PermissionError("private"),
        ):
            self.assertFalse(known_vendor_failure(error, item, "2026-10-28"))

    def test_error_text_not_exposed(self):
        from prepare_periop_takeover import safe_exception_chain

        from medqc_ingest.periop_live import safe_odbc_diagnostic

        result = safe_exception_chain(vendor_error())
        self.assertNotIn("fictional-private-body", json.dumps(result))
        self.assertEqual(safe_odbc_diagnostic(vendor_error()), {"sqlstate": "HY000", "native": 400})

    def test_profile_does_not_expand_original_registry(self):
        self.assertEqual(len(INTERFACE_REGISTRY), 13)
        self.assertFalse(set(SPECS) & set(INTERFACE_REGISTRY))
        spec = next(iter(SPECS.values()))
        self.assertEqual(live_spec(spec).source_columns, spec.source_columns)
        self.assertEqual(live_spec(spec).publish, spec.publish)
        self.assertTrue(live_spec(spec).evidence_version.startswith(LIVE_PROFILE + ";"))

    def test_database_names_are_new_profile_only(self):
        names = live_database_names("20261101050001")
        self.assertEqual(len(set(names.values())), 4)
        self.assertTrue(all(value.startswith("medqc_periop_live_") for value in names.values()))
        for invalid in ("2026_11_01", "bad;DROP", "2026110105000", "202611010500011"):
            with self.assertRaises(IngestError):
                live_database_names(invalid)

    def test_cursor_preserves_whitespace_none_and_identifiers(self):
        values = [["000123", "  虚构正文\n保持空白  ", None]]
        inner = SimpleNamespace(
            columns=("id", "body", "sign"), source_types=("str",) * 3, fetchmany=lambda size: values
        )
        cursor = StrictLiveCursor(inner)
        self.assertEqual(cursor.fetchmany(500), values)

    def test_cursor_rejects_typed_or_shape_drift(self):
        for values in ([[123]], [["too", "many"]]):
            cursor = StrictLiveCursor(
                SimpleNamespace(
                    columns=("id",), source_types=("str",), fetchmany=lambda size, rows=values: rows
                )
            )
            with self.assertRaises(IngestError):
                cursor.fetchmany(500)

    def test_source_config_ignores_old_pg_and_never_reads_pg_secret(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            secret = folder / "source-password"
            secret.write_text("fictional-not-real", encoding="utf-8")
            doc = {
                "MEDQC_CACHE_HOST": "127.0.0.1",
                "MEDQC_CACHE_USER": "fictional",
                "MEDQC_CACHE_NAMESPACE": "fictional",
                "MEDQC_CACHE_PASSWORD_FILE": str(secret),
                "MEDQC_INGEST_PG_DATABASE": "medqc",
                "MEDQC_PG_PASSFILE": "missing.pgpass",
            }
            path = folder / "config.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            before = path.read_bytes()
            with patch("medqc_ingest.config.read_secret", side_effect=AssertionError("no read")):
                settings = source_settings(path)
            self.assertEqual(settings.user, "fictional")
            self.assertEqual(path.read_bytes(), before)

    def test_source_config_rejects_non_odbc_or_injected_fields(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            path = folder / "config.json"
            for doc in ({"MEDQC_SOURCE_ADAPTER": "jdbc"}, {"MEDQC_CACHE_HOST": 123}):
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(IngestError):
                    source_settings(path)

    def test_no_implicit_date_or_incremental_cli(self):
        import validate_periop_live as tool

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tool.main([])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / "reports").mkdir()
            prior = path / "reports/acceptance.json"
            prior.write_text("unchanged", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                rc = tool.main(
                    [
                        "--date",
                        "2026-10-28",
                        "--output",
                        str(path),
                        "--source-config",
                        "missing",
                        "--admin-passfile",
                        "missing",
                        "--runtime-passfile",
                        "missing",
                        "--pg-bin",
                        "missing",
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertEqual(prior.read_text(encoding="utf-8"), "unchanged")
            self.assertFalse((path / "reports/failure.json").exists())

    def test_original_or_business_database_connection_rejected_before_driver(self):
        import validate_periop_live as tool

        args = SimpleNamespace(databases=live_database_names("20261101050001"))
        with patch.object(tool.psycopg2, "connect") as driver:
            for database in ("medqc", "medqc_cache_poc", "medqc_ingest_takeover_20261030205035"):
                with self.assertRaises(IngestError):
                    tool.connect(args, database)
        driver.assert_not_called()

    def test_baseline_write_is_rejected_before_driver(self):
        import validate_periop_live as tool

        args = SimpleNamespace(databases=live_database_names("20261101050001"))
        with patch.object(tool.psycopg2, "connect") as driver, self.assertRaises(IngestError):
            tool.connect(args, tool.BASELINE_INGEST, readonly=False)
        driver.assert_not_called()

    def test_protection_keeps_archive_marker_map_checkpoint(self):
        import validate_periop_live as tool

        value = {
            "tables": {
                name: {"rows": 0}
                for name in (
                    "cache_raw.source_record",
                    "sync_ops.takeover_marker",
                    "takeover_archive.source_row",
                    "sync_ops.sync_checkpoint",
                )
            }
        }
        protected = tool.protected_ingest(value)
        self.assertNotIn("cache_raw.source_record", protected)
        self.assertEqual(len(protected), 3)


if __name__ == "__main__":
    unittest.main()
