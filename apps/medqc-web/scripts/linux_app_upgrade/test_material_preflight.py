"""仅合成配置和临时目录，不加载应用、连接数据库或访问网络。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import stage_upgrade


class MaterialPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="medqc-material-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "business"
        self.old = self.root / "releases/old"
        self.new = self.root / "releases/new"
        self.old.mkdir(parents=True)
        (self.root / "config").mkdir()
        self.config = self.root / "config/business.env"
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {}, clear=True).start()

    def preflight(self, content):
        self.config.write_text(content, encoding="utf-8")
        before = self.config.read_bytes()
        result = stage_upgrade.material_storage_preflight(self.config, self.root, self.old, self.new)
        self.assertEqual(self.config.read_bytes(), before)
        return result

    def test_missing_state_path_rejects_release_fallback(self):
        with self.assertRaisesRegex(ValueError, "material_storage_inside_release"):
            self.preflight("LLM_HTTP_PROXY=http://site-proxy:8080\n")

    def test_explicit_material_path_wins_and_uncreated_state_is_allowed(self):
        for material in (self.root / "state/case-materials", self.root / "persistent-app/data/materials"):
            with self.subTest(material=material):
                result = self.preflight(f"QC_CASE_MATERIAL_DIR='{material.as_posix()}'\nQC_DISPATCH_STATE_DIR=relative/ignored\n")
                self.assertEqual(result["material_storage_dir"], str(material.resolve()))
                self.assertEqual(result["material_storage_source"], "QC_CASE_MATERIAL_DIR")
                self.assertFalse(material.exists())

    def test_dispatch_derived_path_is_stable_across_release_changes(self):
        dispatch = self.root / "state/dispatch"
        result = self.preflight(f"QC_DISPATCH_STATE_DIR={dispatch.as_posix()}\n")
        self.assertEqual(result["material_storage_dir"], str((dispatch.parent / "case-materials").resolve()))
        self.assertFalse(dispatch.parent.exists())

    def test_relative_path_and_any_release_are_rejected(self):
        for content, error in (
            ("QC_CASE_MATERIAL_DIR=./state/case-materials\n", "absolute_material_storage_required"),
            ("QC_DISPATCH_STATE_DIR=state/dispatch\n", "absolute_material_storage_required"),
            (f"QC_CASE_MATERIAL_DIR={(self.root / 'releases/third/data').as_posix()}\n", "material_storage_inside_release"),
            (f"QC_CASE_MATERIAL_DIR={self.new.as_posix()}\n", "material_storage_inside_release"),
        ):
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, error):
                self.preflight(content)

    def test_process_environment_and_interpolation_match_load_dotenv(self):
        material = self.root / "state/case-materials"
        with patch.dict(os.environ, {"STATE_ROOT": str(material.parent)}):
            result = self.preflight("STATE_ROOT=relative/ignored\nQC_CASE_MATERIAL_DIR=${STATE_ROOT}/case-materials\n")
        self.assertEqual(result["material_storage_dir"], str(material.resolve()))
        with patch.dict(os.environ, {"QC_CASE_MATERIAL_DIR": "relative/process-override"}):
            with self.assertRaisesRegex(ValueError, "absolute_material_storage_required"):
                self.preflight(f"QC_CASE_MATERIAL_DIR={material.as_posix()}\n")

    def test_release_symlink_alias_is_rejected(self):
        alias = self.root / "material-alias"
        try:
            alias.symlink_to(self.old, target_is_directory=True)
        except OSError:
            self.skipTest("当前Windows无符号链接权限；需Ubuntu执行此定向用例")
        for content in (f"QC_CASE_MATERIAL_DIR={alias.as_posix()}/materials\n",
                        f"QC_DISPATCH_STATE_DIR={alias.as_posix()}/dispatch\n"):
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, "material_storage_inside_release"):
                self.preflight(content)

    def test_resolved_current_alias_is_rejected(self):
        alias = self.root / "current/materials"
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == alias:
                return self.old / "materials"
            return original_resolve(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve):
            with self.assertRaisesRegex(ValueError, "material_storage_inside_release"):
                self.preflight(f"QC_CASE_MATERIAL_DIR={alias.as_posix()}\n")

    def test_stage_and_code_rollback_preserve_materials_and_proxy_configuration(self):
        material = self.root / "state/case-materials"
        material.mkdir(parents=True)
        history = material / "synthetic-history.json"
        history.write_bytes(b'{"synthetic_history":"keep"}')
        before_history = history.read_bytes()
        content = f"QC_DISPATCH_STATE_DIR={(self.root / 'state/dispatch').as_posix()}\nLLM_HTTP_PROXY=http://site-proxy:8080\nLLM_HTTP_PROXY_HOSTS=site.invalid\n"
        self.config.write_text(content, encoding="utf-8")
        before_config = self.config.read_bytes()
        kit = self.root / "kit"
        (kit / "application/backend").mkdir(parents=True)
        (kit / "application/backend/marker.py").write_text("# synthetic\n")
        current = self.old
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == self.root / "current":
                return current.resolve()
            return original_resolve(path, *args, **kwargs)
        with patch.object(stage_upgrade, "check", return_value={"ok": True, "build_id": "new", "commit": "0" * 40}), \
             patch.object(Path, "resolve", resolve), \
             patch.object(Path, "is_symlink", lambda path: path == self.root / "current"), \
             patch.object(Path, "symlink_to"):
            result = stage_upgrade.stage(kit, self.root, self.old)
            self.assertFalse(result["activated"])
            for current in (self.new, self.old):
                self.assertEqual(stage_upgrade.material_storage_preflight(self.config, self.root, current, self.new)["material_storage_dir"], str(material.resolve()))
        self.assertEqual(history.read_bytes(), before_history)
        self.assertEqual(self.config.read_bytes(), before_config)

    def test_stage_rejects_unsafe_materials_before_copy(self):
        self.config.write_text("QC_CASE_MATERIAL_DIR=relative/materials\n", encoding="utf-8")
        original_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == self.root / "current":
                return self.old.resolve()
            return original_resolve(path, *args, **kwargs)
        with patch.object(stage_upgrade, "check", return_value={"ok": True, "build_id": "new", "commit": "0" * 40}), \
             patch.object(Path, "resolve", resolve), \
             patch.object(Path, "is_symlink", lambda path: path == self.root / "current"), \
             patch.object(stage_upgrade.shutil, "copytree", side_effect=AssertionError("unsafe material path reached application copy")) as copy:
            with self.assertRaisesRegex(ValueError, "absolute_material_storage_required"):
                stage_upgrade.stage(self.root / "kit", self.root, self.old)
        copy.assert_not_called()
        self.assertFalse((self.root / "state").exists())


if __name__ == "__main__":
    unittest.main()
