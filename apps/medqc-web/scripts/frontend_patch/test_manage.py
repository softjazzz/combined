import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('patch_manager', Path(__file__).with_name('manage.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'business'
        self.release = self.root / 'releases/synthetic'
        self.kit = Path(self.temp.name) / 'kit'
        for folder in (self.release / 'frontend/dist', self.release / 'backend/app/data', self.kit / 'dist', self.root / 'state/case-materials', self.root / 'config'):
            folder.mkdir(parents=True)
        (self.root / 'current').symlink_to(self.release, target_is_directory=True)
        (self.release / 'backend/app/data/runtime_build.json').write_text(json.dumps({'git_commit': 'backend'}))
        (self.root / 'config/business.env').write_text('synthetic-config')
        (self.root / 'state/case-materials/marker').write_text('synthetic-snapshot')
        old = {'git_commit': 'backend', 'build_id': 'old'}
        new = {'git_commit': 'frontend', 'build_id': 'new'}
        for folder, identity, content in [(self.release / 'frontend/dist', old, 'old page'), (self.kit / 'dist', new, 'new page')]:
            (folder / 'build-info.json').write_text(json.dumps(identity))
            (folder / 'index.html').write_text(content)
        self.meta = {'patch_id': 'synthetic-patch', 'backend_commit': 'backend',
                     'previous_frontend_identity': old, 'frontend_identity': new, 'files': module.hashes(self.kit / 'dist')}
        (self.kit / 'PATCH.json').write_text(json.dumps(self.meta))

    def call(self, action):
        return module.manage(self.kit, self.root, self.release, action)

    def test_apply_and_rollback_preserve_backend_config_and_snapshot(self):
        protected = [self.release / 'backend/app/data/runtime_build.json', self.root / 'config/business.env', self.root / 'state/case-materials/marker']
        before = [path.read_bytes() for path in protected]
        original = module.hashes(self.release / 'frontend/dist')
        self.assertTrue(self.call('check')['ok'])
        self.assertFalse((self.release / 'frontend/synthetic-patch.json').exists())
        self.assertTrue(self.call('apply')['ok'])
        self.assertEqual(module.hashes(self.release / 'frontend/dist'), self.meta['files'])
        self.assertTrue(self.call('rollback')['ok'])
        self.assertEqual(module.hashes(self.release / 'frontend/dist'), original)
        self.assertEqual([path.read_bytes() for path in protected], before)

    def test_tampered_payload_rejected_before_changes(self):
        (self.kit / 'dist/index.html').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'payload_checksum'):
            self.call('apply')
        self.assertEqual((self.release / 'frontend/dist/index.html').read_text(), 'old page')

    def test_wrong_backend_rejected(self):
        (self.release / 'backend/app/data/runtime_build.json').write_text('{"git_commit":"other"}')
        with self.assertRaisesRegex(ValueError, 'backend_commit_mismatch'):
            self.call('check')

    def test_reapply_and_changed_backup_refused(self):
        self.call('apply')
        with self.assertRaises(ValueError):
            self.call('apply')
        (self.release / 'frontend/dist-before-synthetic-patch/index.html').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'frontend_or_backup_changed'):
            self.call('rollback')
        self.assertEqual((self.release / 'frontend/dist/index.html').read_text(), 'new page')


if __name__ == '__main__':
    unittest.main()
