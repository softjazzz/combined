"""固定材料/临时目录测试，不加载app，不需要数据库或网络。"""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_compat
import stage_upgrade
import apply_proxy


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

    def test_proxy_profile_changes_only_two_keys_and_keeps_backup(self):
        env = self.base / "business.env"
        original = b"JWT_SECRET=synthetic\nLLM_HTTP_PROXY=\nQC_TASK_DISPATCH_MODE=legacy\n"
        env.write_bytes(original)
        result = apply_proxy.apply(env, self.base / "backups")
        self.assertTrue(result["proxy_enabled"])
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        updated = env.read_text()
        self.assertIn("JWT_SECRET=synthetic\n", updated)
        self.assertIn("QC_TASK_DISPATCH_MODE=legacy\n", updated)
        self.assertIn("LLM_HTTP_PROXY_HOSTS=dashscope.aliyuncs.com\n", updated)
        env.write_bytes(Path(result["backup"]).read_bytes())
        self.assertEqual(env.read_bytes(), original)

    def test_duplicate_proxy_configuration_refused_before_write(self):
        env = self.base / "business.env"
        original = b"LLM_HTTP_PROXY=\nLLM_HTTP_PROXY=\n"
        env.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "duplicate_proxy"):
            apply_proxy.apply(env, self.base / "backups")
        self.assertEqual(env.read_bytes(), original)

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
