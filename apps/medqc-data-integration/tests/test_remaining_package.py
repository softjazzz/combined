"""集中包白名单、正式迁移链与作用域测试；不连接数据库/Caché。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_remaining_package", ROOT / "tools/build_remaining_acceptance_package.py"
)
assert spec is not None and spec.loader is not None
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def fixture(base):
    root, backend = base / "source", base / "backend"
    for folder, names in ((root, package.REQUIRED_SERVICE), (backend, package.BACKEND_FILES)):
        for name in names:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fictional source\n", encoding="utf-8")
    versions = backend / "alembic/versions"
    versions.mkdir(parents=True)
    (versions / "000001.py").write_text(
        "revision = 'first'\ndown_revision = None\n", encoding="utf-8"
    )
    (versions / "000002.py").write_text(
        "revision: str = 'second'\ndown_revision = 'first'\n", encoding="utf-8"
    )
    (backend / "scripts/bootstrap_cache_sync_database.py").write_text(
        "TARGET_REVISION = 'second'\n", encoding="utf-8"
    )
    return root, backend


class TestRemainingPackage(unittest.TestCase):
    def test_complete_wheelhouse_is_bound_to_lock_and_evidence_without_extra_wheels(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, backend = fixture(base)
            wheels = base / "complete"
            wheels.mkdir()
            wheel = wheels / "fixture-1.0-py3-none-any.whl"
            wheel.write_bytes(b"fictional wheel")
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            names = (
                "requirements-remaining-acceptance.lock", "requirements-remaining-bootstrap.lock"
            )
            for name in names:
                (root / name).write_text(
                    f"fixture==1.0 --hash=sha256:{digest}\n", encoding="utf-8"
                )
            report = {
                "status": "verified", "target": {"implementation": "CPython", "python": "3.10",
                                                    "platform": "win_amd64"},
                "base_wheel_hashes": {wheel.name: digest}, "supplement_wheel_hashes": {},
                "lock_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in names},
                "complete_locked_distribution_count": 1,
                "no_index_install": True, "require_hashes_install": True, "pip_check": True,
                "official_bootstrap_import": True, "official_orm_import": True,
                "alembic_head_verified": True, "remaining_fake_tests_passed": True,
            }
            proof = root / "docs/remaining-offline-dependencies.json"
            proof.write_text(json.dumps(report), encoding="utf-8")
            result = package.build(base / "complete.zip", root=root, backend=backend,
                                   complete_wheelhouse=wheels)
            self.assertTrue(result["standalone_offline_dependency_closure_verified"])
            with zipfile.ZipFile(base / "complete.zip") as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["wheel_hashes"], {wheel.name: digest})
                self.assertTrue(manifest["standalone_offline_dependency_closure_verified"])
            wheel.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                package.complete_dependencies(root, wheels)
            wheel.write_bytes(b"fictional wheel")
            (wheels / "extra-1-py3-none-any.whl").write_bytes(b"extra")
            with self.assertRaises(ValueError):
                package.complete_dependencies(root, wheels)

    def test_supplement_requires_exact_wheel_and_lock_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wheels = root / "wheels"
            wheels.mkdir()
            wheel = wheels / "fixture-1.0-py3-none-any.whl"
            wheel.write_bytes(b"fictional wheel")
            names = (
                "requirements-remaining-acceptance.lock", "requirements-remaining-bootstrap.lock"
            )
            for name in names:
                (root / name).write_text("# fictional lock\n", encoding="utf-8")
            report = {
                "status": "verified", "target": {"implementation": "CPython", "python": "3.10",
                                                    "platform": "win_amd64"},
                "supplement_wheel_hashes": {
                    wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()
                },
                "base_wheel_hashes": {"fixture-base.whl": "0" * 64},
                "lock_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in names},
                "no_index_install": True, "require_hashes_install": True, "pip_check": True,
                "official_bootstrap_import": True, "official_orm_import": True,
                "alembic_head_verified": True, "remaining_fake_tests_passed": True,
                "private_path": "not exported",
            }
            proof = root / "proof.json"
            proof.write_text(json.dumps(report), encoding="utf-8")
            output = root / "deps.zip"
            result = package.build_dependencies(output, wheelhouse=wheels, verification=proof,
                                                root=root)
            self.assertFalse(result["standalone_dependency_closure_verified"])
            self.assertTrue(result["complete_dependency_closure_verified_with_base"])
            with zipfile.ZipFile(output) as archive:
                exported = json.loads(archive.read("dependency-verification.json"))
                self.assertNotIn("private_path", exported)
                self.assertFalse(exported["customer_acceptance_executed"])
            report["supplement_wheel_hashes"] = {}
            proof.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(ValueError):
                package.build_dependencies(root / "bad.zip", wheelhouse=wheels,
                                           verification=proof, root=root)
            self.assertFalse((root / "bad.zip").exists())

    def test_source_package_scope_and_verbatim_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, backend = fixture(base)
            (root / "tools/run_remaining_acceptance.py").write_text(
                "def preflight():\n    from fixture_acl_helper import check_acl\n",
                encoding="utf-8",
            )
            (root / "tools/fixture_acl_helper.py").write_text(
                "def check_acl():\n    return True\n", encoding="utf-8"
            )
            private = root / "secrets/password.py"
            private.parent.mkdir()
            private.write_text("fictional-private", encoding="utf-8")
            output = base / "release.zip"
            result = package.build(output, root=root, backend=backend)
            self.assertGreater(result["files"], len(package.REQUIRED_SERVICE))
            with zipfile.ZipFile(output) as archive:
                self.assertNotIn("secrets/password.py", archive.namelist())
                self.assertIn("tools/fixture_acl_helper.py", archive.namelist())
                for name in package.BACKEND_FILES:
                    self.assertEqual(archive.read("backend/" + name), (backend / name).read_bytes())
                for line in archive.read("CHECKSUMS.txt").decode().splitlines():
                    digest, name = line.split(None, 1)
                    self.assertEqual(hashlib.sha256(archive.read(name.strip())).hexdigest(), digest)
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["interface_inventory"], 55)
                self.assertEqual(manifest["prior_evidence_reused_without_calls"], 13)
                self.assertEqual(manifest["execution_scope"], {"remaining": 25, "periop": 17})
                self.assertEqual(manifest["official_alembic_heads"], ["second"])
                self.assertFalse(manifest["customer_acceptance_executed"])
                self.assertFalse(manifest["automatic_incremental"])
                self.assertFalse(manifest["scheduled_tasks_enabled"])
                self.assertFalse(manifest["standalone_offline_dependency_closure_verified"])

    def test_missing_components_and_existing_package_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, backend = fixture(base)
            output = base / "release.zip"
            output.write_bytes(b"prior")
            with self.assertRaises(ValueError):
                package.build(output, root=root, backend=backend)
            self.assertEqual(output.read_bytes(), b"prior")
            with self.assertRaises(ValueError):
                package.build(base / "missing.zip", root=base, backend=backend)

    def test_incomplete_chain_or_initializer_head_mismatch_prevents_output(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, backend = fixture(base)
            initializer = backend / "scripts/bootstrap_cache_sync_database.py"
            initializer.write_text("TARGET_REVISION = 'wrong'\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                package.build(base / "wrong.zip", root=root, backend=backend)
            self.assertFalse((base / "wrong.zip").exists())
            (backend / "alembic/versions/000002.py").write_text(
                "revision='second'\ndown_revision='absent'\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                package.migration_heads(backend)

    def test_archive_paths_and_outside_root_are_rejected(self):
        for name in ("../escape.py", "/escape.py", "C:/escape.py", "x\\file.py", ".env",
                     "secrets/a.py", "backups/db.dump", "private-logs/error.txt", "runtime.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                package.validate_name(name)
        package.validate_name("backend/app/database/models/cdm.py")
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / "root"
            root.mkdir()
            outside = base / "outside.py"
            outside.write_text("fictional private", encoding="utf-8")
            with self.assertRaises(ValueError):
                package.read_member(root, outside)


if __name__ == "__main__":
    unittest.main()
