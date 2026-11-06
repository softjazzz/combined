"""固定材料/临时目录测试，不加载app，不需要数据库或网络。"""
import hashlib
from importlib import metadata
import json
import io
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

import check_compat
import stage_upgrade
import make_package


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="medqc-upgrade-unit-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kit = self.base / "kit"
        self.kit.mkdir()
        self.build_id = "medqc-web-customer-20261104-235302"
        self.info = {"commit": "0" * 40, "build_id": self.build_id}
        (self.kit / "BUILD.json").write_text(json.dumps(self.info))
        (self.kit / "requirements-linux.lock").write_text("example==1.0 --hash=sha256:test\n")
        (self.kit / "application/backend").mkdir(parents=True)
        (self.kit / "application/backend/marker.py").write_text("# fixed fixture\n")
        self.seal()

    def seal(self):
        files = [path for path in sorted(self.kit.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
        (self.kit / "SHA256SUMS").write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(self.kit).as_posix() + "\n" for path in files))

    def test_integrity_success(self):
        self.assertEqual(check_compat.verify_package(self.kit), self.info)

    def test_integrity_changed_file(self):
        (self.kit / "BUILD.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "checksum"):
            check_compat.verify_package(self.kit)

    def test_integrity_extra_file(self):
        (self.kit / "extra").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "file_set"):
            check_compat.verify_package(self.kit)

    def test_path_traversal_rejected(self):
        (self.kit / "SHA256SUMS").write_text("0" * 64 + "  ../outside\n")
        with self.assertRaisesRegex(ValueError, "manifest"):
            check_compat.verify_package(self.kit)

    def test_duplicate_manifest_rejected(self):
        path = self.kit / "SHA256SUMS"
        path.write_text(path.read_text() * 2)
        with self.assertRaisesRegex(ValueError, "manifest"):
            check_compat.verify_package(self.kit)

    def test_release_name_escape_rejected(self):
        (self.kit / "BUILD.json").write_text(json.dumps({**self.info, "build_id": "../../outside"}))
        self.seal()
        with self.assertRaisesRegex(ValueError, "build_identity"):
            check_compat.verify_package(self.kit)

    def test_missing_dependency(self):
        def missing(name):
            raise metadata.PackageNotFoundError(name)
        self.assertIsNone(check_compat.version_differences(self.kit / "requirements-linux.lock", missing)[0]["installed"])

    def test_different_dependency(self):
        self.assertEqual(len(check_compat.version_differences(self.kit / "requirements-linux.lock", lambda _: "2.0")), 1)

    def test_matching_dependency(self):
        self.assertEqual(check_compat.version_differences(self.kit / "requirements-linux.lock", lambda _: "1.0"), [])

    def fixture_root(self):
        root = self.base / "business"
        for name in ("releases/old", "venvs/existing", "config", "state"):
            (root / name).mkdir(parents=True, exist_ok=True)
        (root / "config/business.env").write_text("UNCHANGED_CONFIGURATION")
        (root / "current").symlink_to(root / "releases/old", target_is_directory=True)
        (root / "venv").symlink_to(root / "venvs/existing", target_is_directory=True)
        return root

    def test_failed_check_cannot_stage(self):
        with patch.object(stage_upgrade, "check", return_value={"ok": False, "error": "dependency_mismatch"}):
            self.assertFalse(stage_upgrade.stage(self.kit, self.base / "absent", self.base / "absent")["ok"])
        self.assertFalse((self.base / "absent").exists())

    def source_archive(self):
        files = {"BUILD.json": json.dumps({**self.info, "source_base": "synthetic"}).encode(),
                 "requirements-linux.lock": b"example==1.0\n",
                 "application/backend/marker.py": b"# synthetic\n"}
        files["SHA256SUMS"] = "".join(hashlib.sha256(value).hexdigest() + "  " + key + "\n"
                                          for key, value in files.items()).encode()
        archive = self.base / "synthetic-full.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, value in files.items():
                info = tarfile.TarInfo("medqc-offline/" + name)
                info.size = len(value)
                tar.addfile(info, io.BytesIO(value))
        return archive

    def test_builder_requires_external_hash(self):
        with self.assertRaisesRegex(ValueError, "verified_source"):
            make_package.build(self.source_archive(), self.base / "output",
                source_sha256="0" * 64, application_commit=self.info["commit"])

    def test_builder_requires_application_identity(self):
        source = self.source_archive()
        with self.assertRaisesRegex(ValueError, "wrong_application"):
            make_package.build(source, self.base / "output", source_sha256=make_package.digest(source),
                               application_commit="1" * 40)

    def test_builder_matches_explicit_version_and_does_not_claim_no_migration(self):
        source = self.source_archive()
        with patch.object(make_package.subprocess, "check_output", return_value="1" * 40):
            make_package.build(source, self.base / "output", source_sha256=make_package.digest(source),
                               application_commit=self.info["commit"])
        kit = self.base / "output/medqc-app-upgrade"
        self.assertEqual(check_compat.verify_package(kit), {**self.info, "source_base": "synthetic"})
        package = json.loads((kit / "PACKAGE.json").read_text())
        self.assertIsNone(package["database_migrations_required"])
        self.assertEqual(package["application_commit"], self.info["commit"])

    @unittest.skipIf(__import__("os").name == "nt", "Linux symlink stage is exercised by Ubuntu isolation")
    def test_stage_preserves_current_venv_env_and_refuses_repeat(self):
        root = self.fixture_root()
        before = (root / "config/business.env").read_bytes()
        with patch.object(stage_upgrade, "check", return_value={"ok": True, **self.info}):
            result = stage_upgrade.stage(self.kit, root, root / "releases/old")
            self.assertTrue(result["staged"])
            self.assertFalse(result["activated"])
            self.assertEqual((root / "current").resolve(), root / "releases/old")
            self.assertEqual((root / "venv").resolve(), root / "venvs/existing")
            self.assertEqual((root / "config/business.env").read_bytes(), before)
            self.assertEqual((Path(result["release"]) / "backend/.env").resolve(), root / "config/business.env")
            with self.assertRaisesRegex(ValueError, "already_exists"):
                stage_upgrade.stage(self.kit, root, root / "releases/old")


if __name__ == "__main__":
    unittest.main()
