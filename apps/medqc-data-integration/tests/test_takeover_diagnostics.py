"""异常消息可能包含病历值；诊断只能提取类型、SQLSTATE和受信任代码位置。"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class TestTakeoverDiagnostics(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location(
            "takeover_diagnostic_test", ROOT / "tools/diagnose_takeover_import.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_suppressed_context_retains_sqlstate_without_exception_message(self):
        module = self.module()

        class DatabaseFailure(Exception):
            pgcode = "42703"

        try:
            try:
                raise DatabaseFailure("private patient and SQL values")
            except Exception:
                raise RuntimeError("ingest_write_error") from None
        except RuntimeError as error:
            report = module.safe_exception_chain(error, ROOT)
        self.assertEqual(
            [item["exception_type"] for item in report], ["RuntimeError", "DatabaseFailure"]
        )
        self.assertEqual(report[1]["sqlstate"], "42703")
        self.assertNotIn("private patient", json.dumps(report))
        self.assertNotIn("SQL values", json.dumps(report))

    def test_missing_legacy_field_does_not_export_key_value(self):
        module = self.module()
        try:
            {}["sensitive_unknown_key"]
        except KeyError as error:
            report = module.safe_exception_chain(error, ROOT)
        self.assertEqual(report[0]["exception_type"], "KeyError")
        self.assertNotIn("sensitive_unknown_key", json.dumps(report))

    def test_sqlstate_is_controlled_and_external_frames_are_omitted(self):
        module = self.module()
        error = RuntimeError("private")
        error.pgcode = "private arbitrary text"
        report = module.safe_exception_chain(error, ROOT)
        self.assertIsNone(report[0]["sqlstate"])
        self.assertEqual(report[0]["frames"], [])

    def test_exception_cycle_is_bounded(self):
        module = self.module()
        error = RuntimeError("private")
        error.__context__ = error
        self.assertEqual(len(module.safe_exception_chain(error, ROOT)), 1)

    def test_observer_preserves_original_exception_and_records_suppressed_context(self):
        module = self.module()
        report = {}
        original = RuntimeError("private")
        original.__context__ = KeyError("private column")

        def fail(*args, **kwargs):
            raise original

        observed = module.observe_import(fail, report, ROOT)
        with self.assertRaises(RuntimeError) as caught:
            observed("connection", target="connection")
        self.assertIs(caught.exception, original)
        self.assertTrue(report["import_called"])
        self.assertEqual(report["exception_chain"][-1]["exception_type"], "KeyError")
        self.assertNotIn("private column", json.dumps(report))

    def test_observer_success_returns_same_result_and_does_not_retry(self):
        module = self.module()
        from unittest.mock import Mock

        result = {"rows": 87201}
        function = Mock(return_value=result)
        report = {}
        observed = module.observe_import(function, report, ROOT)
        self.assertIs(observed("source", "target"), result)
        function.assert_called_once_with("source", "target")
        self.assertTrue(report["import_succeeded"])

    def test_psycopg_three_sqlstate_is_supported(self):
        module = self.module()
        error = RuntimeError("private")
        error.sqlstate = "23503"
        self.assertEqual(module.safe_exception_chain(error, ROOT)[0]["sqlstate"], "23503")

    def test_real_import_wrapper_keeps_rollback_and_recovers_hidden_sqlstate(self):
        from unittest.mock import Mock, patch

        from medqc_ingest import takeover
        from medqc_ingest.domain import IngestError

        module = self.module()

        class DatabaseFailure(Exception):
            pgcode = "42703"

        report = {}
        target = Mock()
        observed = module.observe_import(takeover.import_legacy, report, ROOT)
        with (
            patch.object(takeover, "_preflight_source", side_effect=DatabaseFailure("private")),
            self.assertRaises(IngestError),
        ):
            observed(Mock(), target, "medqc_ingest_takeover_20261030205035")
        target.rollback.assert_called_once()
        target.commit.assert_not_called()
        self.assertEqual(report["exception_chain"][0]["exception_type"], "IngestError")
        self.assertEqual(report["exception_chain"][1]["sqlstate"], "42703")
        self.assertNotIn("private", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
