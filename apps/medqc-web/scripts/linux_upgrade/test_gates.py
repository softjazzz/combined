"""Synthetic gates only. Never runs systemctl or opens a database connection."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import safe_switch as s
import schema_preflight as db


class Gates(unittest.TestCase):
    def setUp(self):
        self.env={'ENV':'production','MEDQC_STARTUP_BACKGROUND_ENABLED':'false','MEDQC_RESUME_QC_TASKS':'0','QC_SC_RULE_SOURCE_MONITOR_ENABLED':'no'}

    def test_closed_defaults_daily_only(self): s.flags(self.env)
    def test_missing_master_is_rejected(self):
        self.env.pop('MEDQC_STARTUP_BACKGROUND_ENABLED')
        with self.assertRaises(ValueError): s.flags(self.env)
    def test_enabled_flags(self):
        for k in ('MEDQC_STARTUP_BACKGROUND_ENABLED','MEDQC_RESUME_QC_TASKS','QC_SC_RULE_SOURCE_MONITOR_ENABLED','QC_DAILY_SCHEDULER_ENABLED'):
            with self.subTest(key=k),self.assertRaises(ValueError): s.flags({**self.env,k:'true'})
    def test_other_modes(self):
        for k,v in [('ENV','development'),('MEDQC_STARTUP_MODE','acceptance'),('QC_TASK_DISPATCH_MODE','mq')]:
            with self.subTest(key=k),self.assertRaises(ValueError): s.flags({**self.env,k:v})

    def fixture(self):
        root=Path(tempfile.mkdtemp(prefix='gate-synthetic-'))
        release=root/'releases/old'; (release/'backend').mkdir(parents=True)
        (root/'config').mkdir(); config=root/'config/business.env'
        config.write_text('\n'.join(k+'='+v for k,v in self.env.items())+'\n'); config.chmod(0o600)
        (release/'backend/.env').symlink_to(config)
        (root/'venv/bin').mkdir(parents=True); (root/'venv/bin/python').symlink_to(sys.executable)
        proc=root/'proc/42'; proc.mkdir(parents=True); (proc/'cwd').symlink_to(release/'backend')
        (proc/'cmdline').write_bytes(('\0'.join([str(root/'venv/bin/python'),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--workers','1'])+'\0').encode())
        (proc/'environ').write_bytes(b'ENV=production\0')
        common={'User':'medqc-business','Group':'medqc-business','UMask':'0077','Environment':'ENV=production'}
        api={**common,'WorkingDirectory':str(root/'current/backend'),'ExecStart':'python -m uvicorn app.main:app'}
        web={**common,'WorkingDirectory':str(root/'current'),'ExecStart':str(root/'current/frontend/dist')}
        return root,release,proc,config,api,web

    def test_same_env_source(self):
        root,release,_,config,*_=self.fixture(); self.assertEqual(s.config_source(root,release),config)
    def test_regular_or_different_env_rejected(self):
        root,release,_,config,*_=self.fixture(); link=release/'backend/.env'; link.unlink(); link.write_bytes(config.read_bytes())
        with self.assertRaises(ValueError): s.config_source(root,release)
        link.unlink(); other=root/'other'; other.write_bytes(config.read_bytes()); link.symlink_to(other)
        with self.assertRaises(ValueError): s.config_source(root,release)
    def test_service_environment_proven(self):
        root,release,proc,config,api,web=self.fixture()
        with patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',return_value='42'):
            result=s.context(root,release,proc_root=root/'proc'); self.assertEqual(result['env']['MEDQC_STARTUP_BACKGROUND_ENABLED'],'false')

    def test_systemctl_omitted_empty_properties(self):
        output='User=medqc-business\nGroup=medqc-business\nUMask=0077\nWorkingDirectory=/synthetic\nExecStart=python\n'
        with patch.object(s,'command',return_value=output) as command:
            result=s.unit(s.API)
        self.assertIn('--all',command.call_args.args[0])
        for key in ('EnvironmentFiles','ExecStartPre','ExecStartPost','Environment','DropInPaths'):
            self.assertEqual(result[key],'')

    def test_missing_required_unit_properties_are_explicit(self):
        required={'User':'medqc-business','Group':'medqc-business','UMask':'0077','WorkingDirectory':'/synthetic','ExecStart':'python'}
        for key in required:
            for missing in (None,''):
                values=dict(required)
                if missing is None: values.pop(key)
                else: values[key]=missing
                with self.subTest(key=key,missing=missing),self.assertRaisesRegex(ValueError,'service_property_missing:'+key):
                    s.normalize_unit(values)

    def test_nonempty_environment_files_and_hooks_still_rejected(self):
        root,release,proc,config,api,web=self.fixture()
        for key in ('EnvironmentFiles','ExecStartPre','ExecStartPost'):
            with self.subTest(key=key),patch.object(s,'unit',return_value={**api,key:'unapproved'}),self.assertRaisesRegex(ValueError,'unverified_service_environment_or_hooks'):
                s.context(root,release,proc_root=root/'proc')

    def test_feedback_three_paths_use_compatible_context(self):
        import feedback_upgrade as feedback
        root,old,proc,config,api,web=self.fixture()
        (root/'current').symlink_to(old)
        real_context=s.context
        modes=[]
        def inspected(*args,**kwargs):
            modes.append(kwargs.get('offline',False))
            result=real_context(*args,**kwargs,proc_root=root/'proc')
            self.assertEqual(result['env']['MEDQC_STARTUP_BACKGROUND_ENABLED'],'false')
            raise ValueError('context_passed_stop_before_actions')
        for action in ('preflight','apply','rollback'):
            with self.subTest(action=action),patch.object(feedback,'check',return_value={'ok':True,'build_id':'new','commit':'synthetic'}),patch.object(feedback,'inspect'),patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',return_value='42'),patch.object(s,'context',side_effect=inspected),self.assertRaisesRegex(ValueError,'context_passed_stop_before_actions'):
                feedback.run(action,root,root,old,True,True,True)
        self.assertEqual(modes,[False,False,True])
    def test_unmanaged_process_override_rejected(self):
        root,release,proc,config,api,web=self.fixture(); (proc/'environ').write_bytes(b'ENV=production\0MEDQC_STARTUP_BACKGROUND_ENABLED=true\0')
        with patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',return_value='42'),self.assertRaises(ValueError): s.context(root,release,proc_root=root/'proc')
    def test_unit_override_true_rejected(self):
        root,release,proc,config,api,web=self.fixture(); api['Environment']+=' MEDQC_STARTUP_BACKGROUND_ENABLED=true'
        (proc/'environ').write_bytes(b'ENV=production\0MEDQC_STARTUP_BACKGROUND_ENABLED=true\0')
        with patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',return_value='42'),self.assertRaises(ValueError): s.context(root,release,proc_root=root/'proc')
    def test_unapplied_unit_rejected(self):
        root,release,proc,config,api,web=self.fixture(); api['Environment']='ENV=production MEDQC_RESUME_QC_TASKS=false'
        with patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',return_value='42'),self.assertRaises(ValueError): s.context(root,release,proc_root=root/'proc')
    def test_schema_or_config_failure_before_stop(self):
        root,old,proc,config,api,web=self.fixture(); (root/'current').symlink_to(old)
        for failure in ('config','schema'):
            with self.subTest(failure=failure),patch.object(s,'check',return_value={'ok':True,'build_id':'new','commit':'c3'}),patch.object(s,'inspect'),patch.object(s,'context',side_effect=ValueError('config') if failure=='config' else None,return_value={'env':{**self.env,'QC_DISPATCH_STATE_DIR':str(root/'state/dispatch')}}),patch.object(s,'config_source'),patch.object(s,'schema_gate',side_effect=ValueError('schema')),patch.object(s,'command') as command,patch.object(s,'replace_link') as switch,self.assertRaises(ValueError):
                try: s.run('apply',root,root,old,True,True)
                finally: command.assert_not_called(); switch.assert_not_called()
    def test_no_connection_without_opt_in(self):
        root,old,proc,config,api,web=self.fixture(); (root/'current').symlink_to(old)
        with patch.object(s,'check',return_value={'ok':True,'build_id':'new'}),patch.object(s,'inspect'),patch.object(s,'context',return_value={'env':{**self.env,'QC_DISPATCH_STATE_DIR':str(root/'state/dispatch')}}),patch.object(s,'config_source'),patch.object(s,'schema_gate') as connect,self.assertRaisesRegex(ValueError,'explicit_readonly_schema_opt_in_required'):
            try: s.run('preflight',root,root,old,False,False)
            finally: connect.assert_not_called()
    def test_actual_contract_loading_no_app_import(self):
        backend=Path(__file__).parent/'application/backend'
        required,tables,choose,refresh=db.contract(backend)
        self.assertIn('password_hash',required); self.assertEqual(len(tables),8)
        self.assertEqual(choose(search_path=['public','qc','sys'],schemas_with_user_table=['sys']),'sys')
        self.assertNotIn('app.main',sys.modules); self.assertNotIn('app.database.connection',sys.modules)
    def test_cross_identity_even_with_valid_checksums(self):
        import hashlib
        from check_compat import verify_package
        root=Path(tempfile.mkdtemp(prefix='identity-synthetic-'))
        commit='a'*40; build='medqc-web-customer-20261111-234500'
        values={'BUILD.json':{'commit':commit,'build_id':build},'PACKAGE.json':{'application_commit':commit,'build_id':build},'application/backend/app/data/runtime_build.json':{'git_commit':commit,'build_id':build},'application/frontend/dist/build-info.json':{'git_commit':commit,'build_id':build}}
        def write():
            for rel,value in values.items():
                path=root/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value))
            (root/'SHA256SUMS').write_text('\n'.join(hashlib.sha256((root/rel).read_bytes()).hexdigest()+'  '+rel for rel in values)+'\n')
        write(); self.assertEqual(verify_package(root)['commit'],commit)
        values['application/frontend/dist/build-info.json']['git_commit']='b'*40; write()
        with self.assertRaisesRegex(ValueError,'application_identity_disagrees'): verify_package(root)
        values['application/frontend/dist/build-info.json']['git_commit']=commit
        values['PACKAGE.json']['application_commit']='b'*40; write()
        with self.assertRaisesRegex(ValueError,'package_identity_disagrees'): verify_package(root)

    def schema_case(self,revision='20261106_000064',readonly='on',missing_table=False,missing_auth=False):
        import sqlalchemy as sa
        engine=MagicMock(); conn=engine.connect.return_value.__enter__.return_value
        statements=[]
        def execute(sql):
            text=str(sql); statements.append(text); result=MagicMock()
            result.scalar_one.return_value=readonly if 'transaction_read_only' in text else 'medqc_business'
            result.scalars.return_value.all.return_value=[revision]
            return result
        conn.execute.side_effect=execute
        inspector=MagicMock(); inspector.has_table.side_effect=lambda name,**kw: not missing_table or name=='sys_users'
        inspector.get_columns.return_value=[] if missing_auth else [{'name':'id'},{'name':'institute_id'}]
        refresh=MagicMock(); callbacks=[]
        def listener(*args):
            def decorate(fn): callbacks.append(fn); return fn
            return decorate
        env={'DATABASE_URL':'postgresql://synthetic:synthetic@127.0.0.1:1/medqc_business','DB_SCHEMA_MODE':'split'}
        with patch.object(sa,'create_engine',return_value=engine) as create,patch.object(sa,'inspect',return_value=inspector),patch.object(sa.event,'listens_for',side_effect=listener),patch.object(db,'contract',return_value=({'id'},('custom_qc_batch_jobs',),lambda **kw:'sys',refresh)):
            try: result=db.check(Path('.'),env)
            finally:
                conn.rollback.assert_called_once(); engine.dispose.assert_called_once()
                self.assertIn('default_transaction_read_only=on',create.call_args.kwargs['connect_args']['options'])
        self.assertIn('SELECT version_num FROM public.alembic_version',statements)
        with self.assertRaises(ValueError): callbacks[0](None,None,'DROP VIEW qc.anything',None,None,None)
        return result
    def test_readonly_064_and_no_ddl(self): self.assertTrue(self.schema_case()['ok'])
    def test_wrong_revision_rejected(self):
        with self.assertRaises(ValueError): self.schema_case(revision='20261105_000063')
    def test_readonly_not_effective_rejected(self):
        with self.assertRaises(ValueError): self.schema_case(readonly='off')
    def test_missing_table_rejected(self):
        with self.assertRaises(ValueError): self.schema_case(missing_table=True)
    def test_missing_auth_column_rejected(self):
        with self.assertRaises(ValueError): self.schema_case(missing_auth=True)
    def test_rollback_context_without_running_api(self):
        root,release,proc,config,api,web=self.fixture()
        with patch.object(s,'unit',side_effect=lambda n:api if n==s.API else web),patch.object(s,'command',side_effect=AssertionError('must not read live PID')):
            self.assertEqual(s.context(root,release,offline=True)['env']['ENV'],'production')
    def test_failed_start_can_rollback_without_live_api(self):
        if os.getuid()!=0: self.skipTest('root receipt ownership test requires isolated Linux root')
        root,old,proc,config,api,web=self.fixture(); (root/'current').symlink_to(old); (root/'state').mkdir()
        new=root/'releases/new'; (new/'backend').mkdir(parents=True); (new/'backend/.env').symlink_to(config)
        import hashlib
        ctx={'env':{**self.env,'QC_DISPATCH_STATE_DIR':str(root/'state/dispatch')},'units':(api,web),'config':config,'config_hash':hashlib.sha256(config.read_bytes()).hexdigest()}
        (root/'EXPECTED-SERVER.json').write_text(json.dumps({'frontend_identity':{},'backend_identity':{}}))
        calls=[]
        def failed_start(args):
            calls.append(args)
            if args[1]=='start': raise ValueError('synthetic startup failure')
            return ''
        with patch.object(s,'check',return_value={'ok':True,'build_id':'new','commit':'c3'}),patch.object(s,'inspect'),patch.object(s,'context',return_value=ctx) as context,patch.object(s,'schema_gate',return_value={'ok':True}),patch.object(s,'staged_integrity'),patch.object(s,'unchanged'),patch.object(s,'active',return_value=False),patch.object(s,'http_identity'),patch.object(s,'command',side_effect=failed_start):
            with self.assertRaises(ValueError): s.run('apply',root,root,old,True,True)
            self.assertEqual((root/'current').resolve(),new)
            with patch.object(s,'command',return_value=''):
                self.assertTrue(s.run('rollback',root,root,old,True,True)['ok'])
            self.assertTrue(context.call_args.kwargs['offline'])
            self.assertEqual((root/'current').resolve(),old)


if __name__=='__main__': unittest.main()
