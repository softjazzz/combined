"""Deployment gate and guarded switch. No action without explicit CLI opt-in."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import urllib.request

from check_compat import check
from release_guard import inspect

API = 'medqc-business-api'
WEB = 'medqc-business-web'
FALSE = {'0', 'false', 'no'}
PROPERTIES = ['User','Group','UMask','WorkingDirectory','ExecStart','ExecStartPre','ExecStartPost','Environment','EnvironmentFiles','FragmentPath','DropInPaths']


def command(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if p.returncode: raise ValueError('command_failed:' + args[0])
    return p.stdout


def unit(name):
    lines = command(['systemctl','show',name,'--no-pager','--all',*['--property='+p for p in PROPERTIES]])
    return normalize_unit(dict(line.split('=',1) for line in lines.splitlines() if '=' in line))


def normalize_unit(properties):
    # systemd 249可省略空数组。仅可为空的属性补空；身份和启动合同缺失仍拒绝。
    for key in ('User','Group','UMask','WorkingDirectory','ExecStart'):
        if not properties.get(key, '').strip():
            raise ValueError('service_property_missing:' + key)
    return {key: properties.get(key, '') for key in PROPERTIES}


def flags(env):
    for key in ('MEDQC_STARTUP_BACKGROUND_ENABLED','MEDQC_RESUME_QC_TASKS','QC_SC_RULE_SOURCE_MONITOR_ENABLED'):
        if str(env.get(key, '')).strip().lower() not in FALSE:
            raise ValueError('startup_gate_not_closed:' + key)
    if str(env.get('QC_DAILY_SCHEDULER_ENABLED','false')).strip().lower() not in FALSE:
        raise ValueError('daily_scheduler_not_closed')
    if env.get('MEDQC_STARTUP_MODE','normal').strip().lower() not in ('','normal'):
        raise ValueError('unexpected_startup_mode')
    if env.get('QC_TASK_DISPATCH_MODE','legacy').strip() != 'legacy':
        raise ValueError('unexpected_dispatch_mode')
    if env.get('ENV','').lower() != 'production': raise ValueError('production_environment_required')


def config_source(root, release):
    config = root / 'config/business.env'
    link = release / 'backend/.env'
    if config.is_symlink() or not config.is_file() or not link.is_symlink() or link.resolve(strict=True) != config.resolve(strict=True):
        raise ValueError('old_new_env_source_not_identical')
    if config.stat().st_mode & 0o077: raise ValueError('config_permissions_not_private')
    return config


def persistent_paths(root, env):
    dispatch=env.get('QC_DISPATCH_STATE_DIR','').strip()
    values=[env.get('QC_CASE_MATERIAL_DIR') or (str(Path(dispatch).parent/'case-materials') if dispatch else ''),env.get('LLM_ENDPOINT_CONFIG_DIR') or (str(Path(dispatch).parent/'llm-endpoints') if dispatch else '')]
    values += [v for k,v in env.items() if k.endswith('FREEZE_DIR') and v]
    for value in values:
        path=Path(value)
        if not value or not path.is_absolute() or path.resolve()==(root/'releases').resolve() or (root/'releases').resolve() in path.resolve().parents:
            raise ValueError('effective_persistent_path_not_external')


def context(root, current, offline=False, proc_root=Path('/proc')):
    from dotenv.main import DotEnv
    api, web = normalize_unit(unit(API)), normalize_unit(unit(WEB))
    for u in (api,web):
        if u['User'] != 'medqc-business' or u['Group'] != 'medqc-business' or u['UMask'] != '0077': raise ValueError('service_identity_or_umask_changed')
        if u['EnvironmentFiles'] or u['ExecStartPre'] or u['ExecStartPost']: raise ValueError('unverified_service_environment_or_hooks')
    if api['WorkingDirectory'] != str(root/'current/backend') or 'app.main:app' not in api['ExecStart'] or '--env-file' in api['ExecStart']:
        raise ValueError('api_launch_contract_changed')
    if web['WorkingDirectory'] != str(root/'current') or str(root/'current/frontend/dist') not in web['ExecStart']:
        raise ValueError('web_launch_contract_changed')
    configured_unit = dict(x.split('=',1) for x in shlex.split(api['Environment']) if '=' in x)
    config = config_source(root,current)
    saved = dict(os.environ)
    try:
        os.environ.clear(); os.environ.update(configured_unit)
        canonical = DotEnv(config, override=False, encoding='utf-8').dict()
    finally:
        os.environ.clear(); os.environ.update(saved)
    if offline:
        env={k:v for k,v in {**canonical,**configured_unit}.items() if v is not None}
        flags(env)
        return {'units': (api,web), 'config': config, 'config_hash': hashlib.sha256(config.read_bytes()).hexdigest(), 'env': env}
    pid = int(command(['systemctl','show',API,'--property=MainPID','--value']).strip())
    if pid <= 0: raise ValueError('running_api_required_for_environment_proof')
    proc = proc_root / str(pid)
    if (proc/'cwd').resolve(strict=True) != current/'backend': raise ValueError('running_api_cwd_mismatch')
    args = (proc/'cmdline').read_bytes().split(b'\0')
    args=[os.fsdecode(x) for x in args if x]
    if args[1:] != ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--workers','1'] or Path(args[0]).resolve() != (root/'venv/bin/python').resolve():
        raise ValueError('running_api_command_mismatch')
    process = dict(os.fsdecode(x).split('=',1) for x in (proc/'environ').read_bytes().split(b'\0') if b'=' in x)
    if any(process.get(k) != v for k,v in configured_unit.items()): raise ValueError('unit_not_applied_to_running_process')
    if process.get('PYTHONPATH') or process.get('PYTHONHOME'): raise ValueError('unverified_python_path_override')
    # DotEnv expansion uses os.environ: substitute the actual service's initial
    # environment temporarily, never the operator shell environment.
    saved = dict(os.environ)
    try:
        os.environ.clear(); os.environ.update(process)
        values = DotEnv(config, override=False, encoding='utf-8').dict()
    finally:
        os.environ.clear(); os.environ.update(saved)
    env = {k:v for k,v in {**values,**process}.items() if v is not None}
    if values != canonical: raise ValueError('dotenv_depends_on_unmanaged_process_environment')
    for k,v in process.items():
        if k in canonical or k.startswith(('MEDQC_','QC_','LLM_','DATABASE','DB_','CDM_')) or k=='ENV':
            if v != configured_unit.get(k,canonical.get(k)):
                raise ValueError('unmanaged_application_environment_override')
    flags(env)
    return {'units': (api,web), 'config': config, 'config_hash': hashlib.sha256(config.read_bytes()).hexdigest(), 'env': env}


def unchanged(ctx):
    if (unit(API),unit(WEB)) != ctx['units'] or hashlib.sha256(ctx['config'].read_bytes()).hexdigest() != ctx['config_hash']:
        raise ValueError('service_or_config_changed_after_preflight')


def schema_gate(kit, root, env):
    clean = {k:v for k,v in env.items() if not k.startswith('PG')}
    clean['PYTHONDONTWRITEBYTECODE']='1'
    p = subprocess.run([str(root/'venv/bin/python'),'-B',str(kit/'schema_preflight.py'),'--allow-readonly-db'], env=clean, capture_output=True, text=True, timeout=60)
    if p.returncode: raise ValueError('readonly_schema_gate_failed')
    try: result=json.loads(p.stdout)
    except ValueError: raise ValueError('invalid_schema_gate_response') from None
    if result.get('ok') is not True or result.get('revision') != '20261106_000064': raise ValueError('schema_gate_not_passed')
    return result


def staged_integrity(kit, destination):
    expected={p.relative_to(kit/'application').as_posix():p for p in (kit/'application').rglob('*') if p.is_file()}
    actual={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file() and p.relative_to(destination).as_posix() != 'backend/.env'}
    if actual != set(expected): raise ValueError('staged_file_set_changed')
    for rel,p in expected.items():
        target=destination/rel
        if target.is_symlink() or target.read_bytes()!=p.read_bytes(): raise ValueError('staged_file_changed')


def replace_link(root,target):
    link=root/'current.safe-switch-next'
    if link.exists() or link.is_symlink(): raise ValueError('switch_temp_already_exists')
    link.symlink_to(target,target_is_directory=True); os.replace(link,root/'current')


def active(name):
    return subprocess.run(['systemctl','is-active','--quiet',name],capture_output=True,timeout=10).returncode==0


def http_identity(front,back):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(15):
        try:
            values=[]
            for url in ('http://127.0.0.1/build-info.json','http://127.0.0.1:8001/api/v1/runtime-build'):
                with opener.open(url,timeout=2) as response: values.append(json.load(response))
            if all(all(v.get(k)==expected[k] for k in ('git_commit','build_id')) for v,expected in zip(values,(front,back))): return
        except Exception: pass
        time.sleep(1)
    raise ValueError('post_start_identity_failed')


def run(action,kit,root,old,execute,allow_db):
    build=check(kit,root)
    if not build.get('ok'): raise ValueError('compatibility_gate_failed')
    root=root.resolve(strict=True); old=old.resolve(strict=True)
    new=root/'releases'/build['build_id']
    current=(root/'current').resolve(strict=True)
    allowed={old,new} if action=='rollback' else {old}
    if current not in allowed or old.parent != root/'releases': raise ValueError('unexpected_current')
    # Verify the original release, even when it is inactive during rollback.
    inspect(root,old,require_current=action!='rollback')
    ctx=context(root,current,offline=action=='rollback')
    persistent_paths(root,ctx['env'])
    config_source(root,old)
    if action in ('apply','rollback'):
        config_source(root,new)
        if not execute: raise ValueError('execute_opt_in_required')
    if not allow_db: raise ValueError('explicit_readonly_schema_opt_in_required; no_switch')
    schema=schema_gate(kit,root,ctx['env'])
    if action=='preflight': return {'ok':True,'startup_gates_closed':True,'configuration_source_identical':True,'schema':schema,'switched':False}
    if action=='apply': staged_integrity(kit,new)
    receipt=root/'state'/('switch-gate-'+build['build_id']+'.json')
    proof={'units_digest':hashlib.sha256(json.dumps(ctx['units'],sort_keys=True).encode()).hexdigest(),'config_hash':ctx['config_hash'],'old':str(old),'new':str(new),'package_commit':build['commit']}
    if action=='rollback':
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_uid != 0 or receipt.stat().st_mode & 0o077:
            raise ValueError('private_root_gate_receipt_required')
        if json.loads(receipt.read_text()) != proof: raise ValueError('rollback_configuration_or_unit_changed')
    target=old if action=='rollback' else new
    unchanged(ctx)
    if action=='apply':
        fd=os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: json.dump(proof,f)
    command(['systemctl','stop',WEB,API])
    if active(API) or active(WEB): raise ValueError('services_not_stopped')
    # No switch if configuration/unit changed while stopping. Do not restart an
    # unverified configuration automatically.
    unchanged(ctx)
    inspect(root,old,require_current=action!='rollback')
    replace_link(root,target)
    command(['systemctl','start',API,WEB])
    baseline=json.loads((kit/'EXPECTED-SERVER.json').read_text())
    identity={'git_commit':build['commit'],'build_id':build['build_id']}
    http_identity(baseline['frontend_identity'] if action=='rollback' else identity,baseline['backend_identity'] if action=='rollback' else identity)
    if action=='rollback': inspect(root,old)
    return {'ok':True,'action':action,'switched':True,'configuration_preserved':True,'database_migration':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['preflight','apply','rollback']); p.add_argument('--root',type=Path,required=True)
    p.add_argument('--expected-old',type=Path,required=True); p.add_argument('--execute',action='store_true'); p.add_argument('--allow-readonly-db',action='store_true')
    a=p.parse_args()
    try: result=run(a.action,Path(__file__).parent,a.root,a.expected_old,a.execute,a.allow_readonly_db)
    except Exception as e:
        result={'ok':False,'error':str(e) if isinstance(e,ValueError) and type(e) is ValueError else type(e).__name__,'instruction':'stop; do not bypass gates; inspect current and services; never restore database'}
    print(json.dumps(result)); raise SystemExit(0 if result['ok'] else 1)
