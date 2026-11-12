"""Linux真实文件/链接，systemd、PG及HTTP固定替身；绝不访问现场。"""
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import feedback_upgrade as f


class Switch(unittest.TestCase):
    def fixture(self):
        directory=tempfile.TemporaryDirectory(prefix='feedback-switch-synthetic-')
        self.addCleanup(directory.cleanup)
        root=Path(directory.name); old=root/'releases/old'; kit=root/'kit'
        for p in (old/'backend/data',root/'state',root/'config',kit/'application/backend'):
            p.mkdir(parents=True)
        config=root/'config/business.env'; config.write_text('SYNTHETIC_ONLY=1\n'); config.chmod(0o600)
        (old/'backend/.env').symlink_to(config); (root/'current').symlink_to(old)
        (old/'backend/existing.py').write_text('# old application\n')
        for relative in f.OVERLAYS:
            p=kit/'application/backend'/relative; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('# compatible PG code\n')
        with sqlite3.connect(old/'backend/data/demo_feedbacks.db') as db:
            db.execute('CREATE TABLE feedbacks (id text)'); db.execute("INSERT INTO feedbacks VALUES ('synthetic')")
        (kit/'EXPECTED-SERVER.json').write_text(json.dumps({'backend_identity':{},'frontend_identity':{}}))
        ctx={'config_hash':f.digest(config),'config':config,'env':{},'units':[{},{}]}
        return root,old,kit,ctx

    def mocks(self,root,old,kit,ctx,fail=False):
        stack=ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(f,'check',return_value={'ok':True,'build_id':'new','commit':'synthetic'}))
        stack.enter_context(patch.object(f,'inspect'))
        stack.enter_context(patch.object(f.gates,'context',return_value=ctx))
        stack.enter_context(patch.object(f.gates,'persistent_paths'))
        stack.enter_context(patch.object(f.gates,'unchanged'))
        stack.enter_context(patch.object(f,'schema',return_value={'ok':True}))
        stack.enter_context(patch.object(f,'release_permissions'))
        command=stack.enter_context(patch.object(f.gates,'command'))
        stack.enter_context(patch.object(f.gates,'active',return_value=False))
        stack.enter_context(patch.object(f.gates,'http_identity'))
        def stage(*args,**kwargs):
            shutil.copytree(kit/'application',root/'releases/new')
            (root/'releases/new/backend/.env').symlink_to(root/'config/business.env')
        staging=stack.enter_context(patch.object(f,'stage',side_effect=stage))
        proc=stack.enter_context(patch.object(f.subprocess,'run'))
        proc.return_value.returncode=1 if fail else 0
        proc.return_value.stdout='{"ok":true,"revision":"20261112_000065"}'
        return command,staging,proc

    def test_preflight_and_explicit_write_gate(self):
        root,old,kit,ctx=self.fixture(); command,staging,proc=self.mocks(root,old,kit,ctx)
        self.assertTrue(f.run('preflight',kit,root,old,allow_db=True)['ok'])
        with self.assertRaisesRegex(ValueError,'migration_opt_in'):
            f.run('apply',kit,root,old,True,True,False)
        command.assert_not_called(); staging.assert_not_called(); proc.assert_not_called()

    def test_switch_and_compatible_rollback_keep_original(self):
        root,old,kit,ctx=self.fixture(); self.mocks(root,old,kit,ctx)
        raw=old/'backend/data/demo_feedbacks.db'; before=raw.read_bytes()
        self.assertTrue(f.run('apply',kit,root,old,True,True,True)['ok'])
        self.assertEqual((root/'current').resolve(),root/'releases/new')
        self.assertTrue(f.run('rollback',kit,root,old,True,True)['ok'])
        self.assertEqual((root/'current').resolve(),root/'releases/new-rollback-compatible')
        self.assertEqual(raw.read_bytes(),before)
        self.assertFalse((root/'current/backend/data/demo_feedbacks.db').exists())
        self.assertEqual((root/'current/backend/.env').resolve(),root/'config/business.env')

    def test_migration_failure_does_not_switch(self):
        root,old,kit,ctx=self.fixture(); command,_,_=self.mocks(root,old,kit,ctx,fail=True)
        with self.assertRaisesRegex(ValueError,'migration_failed'):
            f.run('apply',kit,root,old,True,True,True)
        self.assertEqual((root/'current').resolve(),old)
        self.assertEqual(command.call_args_list[-1].args[0][1],'stop')
        self.assertTrue((root/'releases/new-rollback-compatible').is_dir())

    def test_tampered_rollback_rejected_before_stop(self):
        root,old,kit,ctx=self.fixture(); command,_,_=self.mocks(root,old,kit,ctx)
        f.run('apply',kit,root,old,True,True,True)
        command.reset_mock()
        (root/'releases/new-rollback-compatible/backend/existing.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'rollback_files_changed'):
            f.run('rollback',kit,root,old,True,True)
        command.assert_not_called()


if __name__=='__main__': unittest.main()
