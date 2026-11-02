"""真实源阶段续跑合同：仅fake驱动/计数，无真实连接或病历数据。"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from medqc_ingest.domain import INTERFACE_REGISTRY
from medqc_ingest.takeover import EXPECTED_COUNTS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def accepted_documents():
    verified = {
        "status": "verified",
        "raw_rows_equal": 87201,
        "history_rows_equal": 87201,
        "archives_verified": 5,
    }
    return {
        "resume-preflight.json": {"status": "passed"},
        "takeover-import.json": {"raw_counts": EXPECTED_COUNTS},
        "takeover-verify.json": verified,
        "takeover-verify-after.json": verified,
        "takeover-import-deployment-source-diagnostic.json": {"import_succeeded": True},
        "service-acceptance.json": {
            "rollback_recovery": {
                "rollback": "verified",
                "failure_audit": "verified",
                "recovery": "succeeded",
                "checkpoint_advanced": False,
            },
            "publish_rounds": [
                {"round": 2, "interface": name, "changed": 0} for name in INTERFACE_REGISTRY
            ],
            "field_equality": [
                {"interface": name, "rows": count, "all_fields_equal": count}
                for name, count in EXPECTED_COUNTS.items()
            ],
        },
    }


def plan():
    return {
        "source": "medqc_bundle_time_clone_20261029180906",
        "ingest": "medqc_ingest_takeover_20261030205035",
        "cdm": "medqc_cdm_takeover_20261030205035",
        "restore_ingest": "medqc_restore_takeover_20261030205035",
        "restore_cdm": "medqc_restore_takeover_20261030205036",
    }


class TestSourceValidationResume(unittest.TestCase):
    def test_formal_thirteen_source_dry_uses_server_keyword_and_never_connects_pg(self):
        configured = tool("run_configured_daily")
        calls, queries, closed = [], [], []

        class Cursor:
            description = ()

            def execute(self, sql, *arguments):
                name = re.search(r"CALL ([a-z_.]+)", sql).group(1)
                spec = INTERFACE_REGISTRY[name]
                self.description = tuple((column, str) for column in spec.source_columns)
                self.assert_arguments = ("2026-10-28",) * spec.argument_count
                if arguments != self.assert_arguments:
                    raise AssertionError("Wrong date arguments")
                queries.append(name)

            def fetchmany(self, size):
                return []

            def close(self):
                pass

        class Connection:
            def cursor(self):
                return Cursor()

            def close(self):
                closed.append(True)

        def connect(connection_string, **kwargs):
            if "SERVER=fixture-host;" not in connection_string or "HOST=" in connection_string:
                raise RuntimeError("Unsupported driver keyword")
            self.assertIn("DATABASE=fixture-namespace;", connection_string)
            self.assertEqual(kwargs, {"autocommit": True, "timeout": 30})
            calls.append(True)
            return Connection()

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            secret = root / "fixture-password"
            secret.write_text("fictional-password", encoding="utf-8")
            values = {
                "MEDQC_SOURCE_ADAPTER": "odbc",
                "MEDQC_CACHE_HOST": "fixture-host",
                "MEDQC_CACHE_NAMESPACE": "fixture-namespace",
                "MEDQC_CACHE_USER": "fixture-user",
                "MEDQC_CACHE_PASSWORD_FILE": str(secret),
                "MEDQC_PG_DRIVER": "psycopg2",
                "MEDQC_PG_PASSFILE": str(root / "must-not-be-read.pgpass"),
                "MEDQC_INGEST_PG_HOST": "127.0.0.1",
                "MEDQC_CDM_PG_HOST": "127.0.0.1",
                "MEDQC_INGEST_PG_DATABASE": plan()["ingest"],
                "MEDQC_CDM_PG_DATABASE": plan()["cdm"],
                "MEDQC_INGEST_PG_USER": "medqc_sync",
                "MEDQC_CDM_PG_USER": "medqc_sync",
            }
            config = root / "runtime.json"
            config.write_text(json.dumps(values), encoding="utf-8")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.dict(sys.modules, {"pyodbc": SimpleNamespace(connect=connect)}),
                patch(
                    "medqc_ingest.repositories.postgres._connect",
                    side_effect=AssertionError("PG connection forbidden"),
                ) as pg,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    configured.main(["--config", str(config), "--dry-date", "2026-10-28"]), 0
                )
                pg.assert_not_called()
        self.assertEqual(queries, list(INTERFACE_REGISTRY))
        self.assertEqual(len(calls), 13)
        self.assertEqual(len(closed), 13)

    def test_completed_import_publication_and_rollback_reports_are_required(self):
        module = tool("source_validation_preflight")
        module.validate_completed(accepted_documents())
        documents = accepted_documents()
        documents["takeover-import-deployment-source-diagnostic.json"]["import_succeeded"] = False
        with self.assertRaises(RuntimeError):
            module.validate_completed(documents)

    def test_non_idempotent_prior_publication_blocks_continuation(self):
        module = tool("source_validation_preflight")
        documents = accepted_documents()
        documents["service-acceptance.json"]["publish_rounds"][0]["changed"] = 1
        with self.assertRaises(RuntimeError):
            module.validate_completed(documents)

    def test_missing_interface_in_prior_field_verification_blocks_continuation(self):
        module = tool("source_validation_preflight")
        documents = accepted_documents()
        documents["service-acceptance.json"]["field_equality"].pop()
        with self.assertRaises(RuntimeError):
            module.validate_completed(documents)

    def test_live_guard_connects_only_existing_targets_readonly(self):
        module = tool("source_validation_preflight")
        calls = []

        class Connection:
            def __init__(self, database):
                self.database, self.sql = database, ""

            def cursor(self):
                return contextlib.nullcontext(self)

            def execute(self, sql):
                self.assert_readonly = sql.startswith("SELECT ")
                if not self.assert_readonly:
                    raise AssertionError("Write in preflight")
                self.sql = sql

            def fetchone(self):
                if "current_database" in self.sql:
                    return self.database, "on"
                if "takeover_marker" in self.sql:
                    return (plan()["source"],)
                if "source_record_version" in self.sql:
                    return (87201,)
                if self.database == plan()["cdm"]:
                    table = self.sql.split()[-1]
                    return (
                        next(
                            EXPECTED_COUNTS[s.name]
                            for s in INTERFACE_REGISTRY.values()
                            if s.publish_target == table
                        ),
                    )
                return (0,)

            def fetchall(self):
                return list(EXPECTED_COUNTS.items())

            def close(self):
                pass

        def connect(settings, *args, **kwargs):
            calls.append((settings, kwargs))
            return Connection(settings.database)

        with patch.object(module, "_connect", side_effect=connect):
            module.verify_live_state(plan(), Path("fixture"), "postgres", 5432)
        self.assertEqual(len(calls), 4)
        self.assertNotIn(plan()["source"], [settings.database for settings, _ in calls])
        for settings, kwargs in calls:
            self.assertTrue(kwargs["readonly"])
            self.assertEqual(
                settings.user, "postgres" if "restore" in settings.database else "medqc_sync"
            )

    def test_runtime_admin_identity_is_rejected(self):
        module = tool("source_validation_preflight")
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "secrets").mkdir()
            for name in ("runtime.pgpass", "deployment-admin.pgpass", "cache-password"):
                (run / "secrets" / name).touch()
            values = {
                "MEDQC_SOURCE_ADAPTER": "odbc",
                "MEDQC_INGEST_PG_DATABASE": plan()["ingest"],
                "MEDQC_CDM_PG_DATABASE": plan()["cdm"],
                "MEDQC_INGEST_PG_USER": "medqc_sync",
                "MEDQC_CDM_PG_USER": "medqc_sync",
                "MEDQC_INGEST_PG_PORT": "5432",
                "MEDQC_CDM_PG_PORT": "5432",
                "MEDQC_PG_PASSFILE": str(run / "secrets/runtime.pgpass"),
                "MEDQC_CACHE_PASSWORD_FILE": str(run / "secrets/cache-password"),
            }
            module.validate_runtime(values, plan(), run, 5432)
            for wrong in (
                {"MEDQC_INGEST_PG_USER": "postgres"},
                {"MEDQC_PG_PASSFILE": str(run / "secrets/deployment-admin.pgpass")},
            ):
                with self.assertRaises(RuntimeError):
                    module.validate_runtime({**values, **wrong}, plan(), run, 5432)

    def test_checkpoint_or_archive_change_is_detected(self):
        module = tool("source_validation_preflight")
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "reports").mkdir()
            (run / "runtime.json").write_text("{}", encoding="utf-8")
            saved = {
                "completed_reports_sha256": {},
                "runtime_sha256": hashlib.sha256(b"{}").hexdigest(),
            }
            (run / "reports/source-validation-preflight-0.3.2.json").write_text(
                json.dumps(saved), encoding="utf-8"
            )
            before = {table: {"rows": 0, "sha256": "fixture"} for table in module.PROTECTED_TABLES}
            (run / "reports/ingest-before-live-0.3.2.json").write_text(
                json.dumps({"tables": before}), encoding="utf-8"
            )
            with patch.object(module, "completed_hashes", return_value={}):
                for changed in (None, *module.PROTECTED_TABLES):
                    after = {**before}
                    if changed:
                        after[changed] = {"rows": 1, "sha256": "changed"}
                    (run / "reports/ingest-before-backup.json").write_text(
                        json.dumps({"tables": after}), encoding="utf-8"
                    )
                    if changed is None:
                        module.check_preserved(run)
                    else:
                        with self.assertRaises(RuntimeError):
                            module.check_preserved(run)


if __name__ == "__main__":
    unittest.main()
