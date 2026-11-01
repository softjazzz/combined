"""部署模板/非PHI源码包/集中控制验收测试，不连接客户环境。"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

import accept_sync_control as acceptance  # noqa: E402
import build_sync_control_package as package  # noqa: E402

from medqc_ingest.control.memory import MemoryJobRepository  # noqa: E402
from medqc_ingest.control.profiles import ProfileCatalog  # noqa: E402


class TestControlDeployment(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"),
        "optional API dependencies are unavailable",
    )
    def test_actual_api_in_process_authorization_and_async_submit(self):
        repository = MemoryJobRepository()
        result = acceptance.run_http_scenario(repository, ProfileCatalog())
        self.assertTrue(result["in_process_app_verified"])
        self.assertFalse(result["external_listener_verified"])
        self.assertFalse(result["source_accessed"])
        self.assertFalse(result["token_values_exported"])

    def test_windows_templates_disabled_and_linux_template_only(self):
        result = acceptance.inspect_deployment_templates()
        for item in result["windows"].values():
            self.assertTrue(item["disabled"])
            self.assertFalse(item["registered"])
        for item in result["systemd"].values():
            self.assertFalse(item["enabled"])
            self.assertFalse(item["host_execution_verified"])

    def test_enabled_windows_template_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in (
                "deploy/windows/sync-worker.disabled.xml",
                "deploy/windows/sync-api.disabled.xml",
                "deploy/systemd/medqc-sync-worker.service",
                "deploy/systemd/medqc-sync-api.service",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            path = root / "deploy/windows/sync-worker.disabled.xml"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "<Enabled>false</Enabled>", "<Enabled>true</Enabled>", 1
                ),
                encoding="utf-8",
            )
            with self.assertRaises(acceptance.AcceptanceFailure):
                acceptance.inspect_deployment_templates(root)

    def test_fake_acceptance_runs_real_controller_without_data_source(self):
        repository = MemoryJobRepository()
        results = acceptance.run_scenarios(repository, ProfileCatalog())
        self.assertEqual(len(results), 7)
        self.assertTrue(all(row["passed"] for row in results))
        self.assertFalse(any(plan["enabled"] for plan in repository.list_schedules()))
        self.assertFalse(
            any(job["status"] in {"running", "recovery_required"} for job in repository.list_jobs())
        )

    def test_existing_control_jobs_not_consumed_by_acceptance(self):
        from medqc_ingest.control.admission import AdmissionService
        from medqc_ingest.control.models import Actor

        repository, catalog = MemoryJobRepository(), ProfileCatalog()
        actor = Actor("operator", frozenset({"run"}))
        job = AdmissionService(catalog, repository).submit(
            {
                "profile": "core13",
                "interfaces": ["web.mr"],
                "mode": "publish_only",
                "publish": True,
            },
            actor,
            "existing-job",
        )
        with self.assertRaises(acceptance.AcceptanceFailure):
            acceptance.run_scenarios(repository, catalog)
        self.assertEqual(repository.get_job(job["job_id"])["status"], "queued")

    def test_fake_cli_never_claims_full_real_acceptance(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder) / "reports"
            self.assertEqual(acceptance.main(["--mode", "fake", "--output", str(path)]), 0)
            result = json.loads((path / "acceptance.json").read_text(encoding="utf-8"))
            for key in (
                "cache_accessed",
                "ingest_or_cdm_accessed",
                "business_database_accessed",
                "live_pipeline_verified",
                "backup_restore_verified",
                "production_enabled",
                "scheduled_task_registered",
            ):
                self.assertIs(result[key], False)
            self.assertTrue(result["fake_executor"])

    def test_postgres_mode_requires_explicit_control_writes_before_config(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            path = Path(folder) / "reports"
            rc = acceptance.main(
                ["--mode", "postgres", "--config", "not-opened.json", "--output", str(path)]
            )
            self.assertEqual(rc, 1)
            self.assertFalse(path.exists())

    def test_existing_output_not_modified(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            root = Path(folder)
            marker = root / "acceptance.json"
            marker.write_text("prior-result", encoding="utf-8")
            self.assertEqual(acceptance.main(["--mode", "fake", "--output", str(root)]), 1)
            self.assertEqual(marker.read_text(encoding="utf-8"), "prior-result")
            self.assertFalse((root / "failure.json").exists())

    def test_unsafe_package_members_rejected(self):
        for name in (
            "../escape.py",
            "/absolute.py",
            "C:/escape.py",
            "src\\escape.py",
            ".env",
            "secrets/password.py",
            "backups/db.dump",
            "private-logs/error.txt",
            "worker.json",
            "runtime.json",
            "key.pem",
            "file\nname.py",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                package.validate_member_name(name)
        package.validate_member_name("examples/control-worker.example.json")

    def test_package_manifest_and_checksums_with_fixture_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "source"
            root.mkdir()
            for relative in package.REQUIRED_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# fictional source fixture\n", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project]\nversion = "0.4.0"\n', encoding="utf-8")
            output = Path(folder) / "package.zip"
            result = package.build(output, root=root)
            self.assertFalse(result["offline_dependency_closure_verified"])
            with zipfile.ZipFile(output) as archive:
                for line in archive.read("CHECKSUMS.txt").decode().splitlines():
                    digest, name = line.split(None, 1)
                    self.assertEqual(hashlib.sha256(archive.read(name.strip())).hexdigest(), digest)
                manifest = json.loads(archive.read("manifest.json"))
                self.assertFalse(manifest["customer_acceptance_executed"])
                self.assertFalse(manifest["production_enabled"])
                self.assertFalse(manifest["runtime_configuration_included"])
                self.assertEqual(manifest["source_version"], "0.4.0")
                examples = json.loads(archive.read("examples/control-worker.example.json"))
                self.assertFalse(examples["catalog"]["periop13"]["enabled"])
                self.assertNotIn("password", examples["postgres"])

    def test_missing_components_refuse_package_and_existing_output_stays(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                package.build(root / "missing.zip", root=root)
            output = root / "prior.zip"
            output.write_bytes(b"prior")
            with self.assertRaises(ValueError):
                package.build(output, root=root)
            self.assertEqual(output.read_bytes(), b"prior")

    def test_outside_root_file_is_never_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "root"
            root.mkdir()
            private = Path(folder) / "not-source.py"
            private.write_text("fictional-private-data", encoding="utf-8")
            with self.assertRaises(ValueError):
                package.protected_read(root, private)

    def test_dependency_attachment_requires_matching_installation_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wheels = root / "wheels"
            wheels.mkdir()
            wheel = wheels / "fixture-1.0-py3-none-any.whl"
            wheel.write_bytes(b"fictional wheel fixture")
            names = ("requirements-sync-control.lock", "requirements-sync-control-dev.lock")
            for name in names:
                (root / name).write_text("# fictional lock\n", encoding="utf-8")
            report = {
                "status": "verified",
                "target": {"implementation": "CPython", "python": "3.10",
                           "platform": "win_amd64"},
                "no_index_install": True, "require_hashes_install": True, "pip_check": True,
                "in_process_api": True, "control_tests_passed": True,
                "wheel_installed_independently": True,
                "wheel_hashes": {wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()},
                "lock_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in names},
                "private_path": "must not enter the archive",
            }
            proof = root / "proof.json"
            proof.write_text(json.dumps(report), encoding="utf-8")
            output = root / "deps.zip"
            result = package.build_dependencies(output, wheelhouse=wheels, verification=proof,
                                                root=root)
            self.assertTrue(result["offline_dependency_closure_verified"])
            with zipfile.ZipFile(output) as archive:
                exported = json.loads(archive.read("dependency-verification.json"))
                self.assertNotIn("private_path", exported)
                self.assertFalse(exported["customer_acceptance_executed"])
                for line in archive.read("CHECKSUMS.txt").decode().splitlines():
                    digest, name = line.split(None, 1)
                    self.assertEqual(hashlib.sha256(archive.read(name.strip())).hexdigest(), digest)
            for field in ("no_index_install", "wheel_hashes", "lock_hashes"):
                broken = dict(report, **{field: False if field == "no_index_install" else {}})
                proof.write_text(json.dumps(broken), encoding="utf-8")
                with self.subTest(field=field), self.assertRaises(ValueError):
                    package.build_dependencies(root / "invalid.zip", wheelhouse=wheels,
                                               verification=proof, root=root)
                self.assertFalse((root / "invalid.zip").exists())

    def test_fake_failure_reports_no_raw_exception_message(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            path = Path(folder) / "output"
            with patch.object(
                acceptance, "run_scenarios", side_effect=RuntimeError("fictional-private-message")
            ):
                self.assertEqual(acceptance.main(["--mode", "fake", "--output", str(path)]), 1)
            text = (path / "failure.json").read_text(encoding="utf-8")
            self.assertNotIn("fictional-private-message", text)
            self.assertIn("RuntimeError", text)


if __name__ == "__main__":
    unittest.main()
