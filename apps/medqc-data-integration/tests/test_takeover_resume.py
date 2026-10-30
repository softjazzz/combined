"""续跑身份边界与只读现场闸门，不连接真实数据库。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def load_tool(name):
    if name == "run_takeover":
        # 小修正包不复制原包代码；客户机测试从PYTHONPATH绑定的原包读取真实入口。
        import medqc_ingest

        tool_root = Path(medqc_ingest.__file__).resolve().parents[2]
    else:
        tool_root = ROOT
    spec = importlib.util.spec_from_file_location(name, tool_root / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan():
    return {
        "source": "medqc_bundle_time_clone_20261029180906",
        "ingest": "medqc_ingest_takeover_20261030205035",
        "cdm": "medqc_cdm_takeover_20261030205035",
        "restore_ingest": "medqc_restore_takeover_20261030205035",
        "restore_cdm": "medqc_restore_takeover_20261030205036",
    }


class Connection:
    def __init__(self, database, contaminated=False):
        self.database, self.contaminated = database, contaminated
        self.query = ""

    def cursor(self):
        return contextlib.nullcontext(self)

    def execute(self, sql):
        self.query = sql
        if not sql.startswith("SELECT "):
            raise AssertionError("Database write attempted")

    def fetchone(self):
        if "current_database" in self.query:
            return self.database, "on"
        if self.database.startswith("medqc_cdm_"):
            return (87201 if "source_record" in self.query else 78,)
        return (int(self.contaminated),)

    def close(self):
        pass


class TestTakeoverResume(unittest.TestCase):
    def test_plan_rejects_original_business_and_aliased_databases(self):
        module = load_tool("takeover_resume_preflight")
        module.validate_plan(plan())
        for key, value in (
            ("source", "medqc"),
            ("ingest", "medqc"),
            ("cdm", "medqc"),
            ("restore_cdm", plan()["restore_ingest"]),
        ):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                module.validate_plan({**plan(), key: value})

    def run_preflight(self, contaminated=False):
        module = load_tool("takeover_resume_preflight")
        calls = []

        def connect(settings, *args, **kwargs):
            calls.append((settings, kwargs))
            return Connection(
                settings.database, contaminated and settings.database == plan()["ingest"]
            )

        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "reports").mkdir()
            (run / "reports/database-plan.json").write_text(json.dumps(plan()), encoding="utf-8")
            with (
                patch.object(module, "verify_frozen_package"),
                patch("medqc_ingest.repositories.postgres._connect", side_effect=connect),
                patch("medqc_ingest.takeover._preflight_source") as source_preflight,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = module.main(["--package-root", str(ROOT), "--run-root", str(run)])
            return result, calls, source_preflight.call_count

    def test_preflight_all_five_connections_are_admin_readonly(self):
        status, calls, source_checks = self.run_preflight()
        self.assertEqual(status, 0)
        self.assertEqual(len(calls), 5)
        self.assertEqual(source_checks, 1)
        for settings, kwargs in calls:
            self.assertEqual(settings.user, "postgres")
            self.assertTrue(kwargs["readonly"])
            self.assertEqual(settings.password_file.name, "deployment-admin.pgpass")

    def test_nonempty_ingest_stops_before_cdm_or_restore_connections(self):
        status, calls, _ = self.run_preflight(contaminated=True)
        self.assertEqual(status, 1)
        self.assertEqual(len(calls), 2)

    def test_original_import_accepts_admin_source_and_enforces_readonly(self):
        module = load_tool("run_takeover")
        connections = [Mock(), Mock()]
        with (
            patch.object(module, "_connect", side_effect=connections) as connect,
            patch.object(module, "import_legacy", return_value={}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = module.main(
                [
                    "import",
                    "--database",
                    plan()["ingest"],
                    "--user",
                    "postgres",
                    "--passfile",
                    str(ROOT / "fixture-admin.pgpass"),
                    "--source-user",
                    "postgres",
                    "--source-passfile",
                    str(ROOT / "fixture-admin.pgpass"),
                ]
            )
        self.assertEqual(status, 0)
        self.assertFalse(connect.call_args_list[0].kwargs["readonly"])
        source = connect.call_args_list[1]
        self.assertEqual(source.args[0].database, plan()["source"])
        self.assertEqual(source.args[0].user, "postgres")
        self.assertTrue(source.kwargs["readonly"])

    def test_runtime_verification_remains_runtime_readonly(self):
        module = load_tool("run_takeover")
        with (
            patch.object(module, "_connect") as connect,
            patch.object(module, "verify_takeover", return_value={}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = module.main(
                [
                    "verify",
                    "--database",
                    plan()["ingest"],
                    "--user",
                    "medqc_sync",
                    "--passfile",
                    str(ROOT / "fixture-runtime.pgpass"),
                ]
            )
        self.assertEqual(status, 0)
        self.assertEqual(connect.call_args.args[0].user, "medqc_sync")
        self.assertTrue(connect.call_args.kwargs["readonly"])

    def test_admin_source_observer_preserves_prior_diagnostic_and_selects_admin_passfile(self):
        module = load_tool("diagnose_takeover_import")
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            (run / "reports").mkdir()
            (run / "secrets").mkdir()
            (run / "reports/database-plan.json").write_text(json.dumps(plan()), encoding="utf-8")
            old = run / "reports/takeover-import-diagnostic.json"
            old.write_text("prior-diagnostic", encoding="utf-8")
            for name in ("deployment-admin.pgpass", "runtime.pgpass"):
                (run / "secrets" / name).touch()
            frozen = Mock()
            frozen.main.return_value = 0
            with (
                patch.object(module, "verify_frozen_package"),
                patch.object(module.importlib.util, "spec_from_file_location"),
                patch.object(module.importlib.util, "module_from_spec", return_value=frozen),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = module.main(
                    [
                        "--package-root",
                        str(ROOT),
                        "--run-root",
                        str(run),
                        "--deployment-source",
                    ]
                )
            self.assertEqual(status, 0)
            arguments = frozen.main.call_args.args[0]
            self.assertEqual(arguments[arguments.index("--source-user") + 1], "postgres")
            self.assertEqual(
                arguments[arguments.index("--source-passfile") + 1],
                str(run / "secrets/deployment-admin.pgpass"),
            )
            self.assertEqual(old.read_text(encoding="utf-8"), "prior-diagnostic")
            report = json.loads(
                (run / "reports/takeover-import-deployment-source-diagnostic.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["source_authentication"], "deployment_readonly")


if __name__ == "__main__":
    unittest.main()
