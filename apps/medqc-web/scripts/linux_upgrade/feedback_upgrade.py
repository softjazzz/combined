"""反馈PG专用维护入口。原SQLite保留；兼容回滚继续读取PG，禁止降库。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import safe_switch as gates
from check_compat import check
from release_guard import inspect
from stage_upgrade import stage

OVERLAYS=('app/database/demo_db.py','app/models/demo.py',
          'app/database/demo_feedback_transfer.py','app/core/server_startup.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_manifest(directory):
    result={}
    for p in directory.rglob('*'):
        if p.is_symlink():
            if p.relative_to(directory).as_posix()!='backend/.env': raise ValueError('unexpected_release_symlink')
        elif p.is_file(): result[p.relative_to(directory).as_posix()]=digest(p)
    return result


def private_json(path, value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(value,f,sort_keys=True)


def release_permissions(directory):
    import pwd
    account=pwd.getpwnam('medqc-business')
    for p in [directory,*directory.rglob('*')]:
        if p.is_symlink(): continue
        os.chown(p,account.pw_uid,account.pw_gid)
        p.chmod(0o750 if p.is_dir() else 0o640)


def snapshot_sqlite(old, backup):
    """停服后先逐字复制DB/WAL/SHM；SQLite仅打开副本，不碰原库。"""
    base=old/'backend/data/demo_feedbacks.db'
    names=[Path(str(base)+s) for s in ('','-wal','-shm')]
    before={p.name:digest(p) for p in names if p.is_file()}
    if not base.is_file():
        if before: raise ValueError('orphan_sqlite_sidecar')
        return None,{},hashlib.sha256(b'no_legacy_feedback').hexdigest()
    backup.mkdir(mode=0o700)
    pristine=backup/'original'; pristine.mkdir(mode=0o700)
    working=backup/'working'; working.mkdir(mode=0o700)
    for p in names:
        if p.exists():
            if p.is_symlink(): raise ValueError('unsafe_sqlite_source')
            shutil.copy2(p,pristine/p.name); shutil.copy2(p,working/p.name)
    if before!={p.name:digest(p) for p in names if p.is_file()}:
        raise ValueError('legacy_feedback_changed_while_copying')
    for name,h in before.items():
        if digest(pristine/name)!=h: raise ValueError('sqlite_backup_mismatch')
    snapshot=backup/'feedback-snapshot.db'
    source=sqlite3.connect((working/base.name).as_uri()+'?mode=ro',uri=True)
    target=sqlite3.connect(snapshot)
    try:
        source.execute('PRAGMA query_only=ON'); source.backup(target)
        if target.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise ValueError('sqlite_snapshot_invalid')
    finally: target.close(); source.close()
    return snapshot,before,hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()


def compatible_release(kit,root,old,build):
    destination=root/'releases'/(build['build_id']+'-rollback-compatible')
    if destination.exists(): raise ValueError('rollback_target_exists')
    def ignored(directory,names):
        rel=Path(directory).relative_to(old).as_posix()
        return [n for n in names if n=='__pycache__' or (rel=='backend' and n=='.env') or
                (rel=='backend/data' and n in ('demo_feedbacks.db','demo_feedbacks.db-wal','demo_feedbacks.db-shm'))]
    shutil.copytree(old,destination,ignore=ignored)
    for relative in OVERLAYS:
        (destination/'backend'/relative).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(kit/'application/backend'/relative,destination/'backend'/relative)
    (destination/'backend/.env').symlink_to(root/'config/business.env')
    return destination,file_manifest(destination)


def schema(kit,root,env,revision):
    # 不导入应用；独立子进程避免维护者环境或已加载模块污染配置。
    clean={k:v for k,v in env.items() if not k.startswith('PG')}
    clean['PYTHONDONTWRITEBYTECODE']='1'
    script="import json,os,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from schema_preflight import check;print(json.dumps(check(Path(sys.argv[1])/'application/backend',dict(os.environ),sys.argv[2])))"
    p=subprocess.run([str(root/'venv/bin/python'),'-B','-c',script,str(kit),revision],env=clean,capture_output=True,text=True,timeout=60)
    if p.returncode: raise ValueError('readonly_schema_gate_failed')
    return json.loads(p.stdout)


def archive_failed(kit,root,old,build,ctx,receipt,execute):
    """仅接管064、原版本仍运行且尚无SQLite备份的失败暂存。只归档，不删除。"""
    if (root/'current').resolve(strict=True)!=old or not gates.active(gates.API) or not gates.active(gates.WEB):
        raise ValueError('archive_requires_original_services_running')
    schema(kit,root,ctx['env'],'20261106_000064')
    backup=root/'state'/('feedback-backup-'+build['build_id'])
    if backup.exists() or backup.is_symlink(): raise ValueError('backup_exists_manual_recovery_required')
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_uid!=0 or receipt.stat().st_mode & 0o077:
        raise ValueError('private_root_receipt_required')
    proof=json.loads(receipt.read_text())
    new=root/'releases'/build['build_id']
    rollback=root/'releases'/(build['build_id']+'-rollback-compatible')
    if proof['old']!=str(old) or proof['rollback']!=str(rollback) or proof['commit']!=build['commit'] or proof['config_hash']!=ctx['config_hash']:
        raise ValueError('failed_attempt_identity_changed')
    if [gates.normalize_unit(u) for u in proof['units']] != [gates.normalize_unit(u) for u in ctx['units']]:
        raise ValueError('failed_attempt_service_configuration_changed')
    gates.config_source(root,new); gates.config_source(root,rollback)
    gates.staged_integrity(kit,new)
    if file_manifest(rollback)!=proof['rollback_files']: raise ValueError('rollback_files_changed')
    staged=root/'state'/('app-upgrade-'+build['build_id']+'.json')
    record=json.loads(staged.read_text())
    if record.get('previous_current')!=str(old) or record.get('staged_current')!=str(new) or record.get('application_commit')!=build['commit'] or record.get('activated') is not False:
        raise ValueError('stage_receipt_mismatch')
    paths=(new,rollback,receipt,staged)
    for path in paths:
        if path.is_symlink() or root not in path.resolve(strict=True).parents:
            raise ValueError('unsafe_recovery_path')
    archive=root/'state'/('failed-feedback-'+build['build_id'])
    if archive.exists() or archive.is_symlink(): raise ValueError('archive_exists_inspect_plan_do_not_retry')
    if not execute: return {'ok':True,'archive_ready':True,'objects':4,'archived':False,'database_writes':0}
    gates.unchanged(ctx)
    archive.mkdir(mode=0o700)
    private_json(archive/'PLAN.json',{'sources':[str(p) for p in paths],'original_current':str(old),'revision':'20261106_000064'})
    for path in paths:
        os.rename(path,archive/path.name)
    return {'ok':True,'archived':True,'objects':4,'archive':str(archive),'switched':False,'database_writes':0}


def run(action,kit,root,old,execute=False,allow_db=False,allow_write=False):
    if action not in ('preflight','apply','rollback','archive-failed'): raise ValueError('unknown_action')
    if action!='preflight' and (not hasattr(os,'geteuid') or os.geteuid()!=0):
        raise ValueError('root_maintenance_required')
    build=check(kit,root)
    if not build.get('ok'): raise ValueError('compatibility_failed')
    root=root.resolve(strict=True); old=old.resolve(strict=True)
    inspect(root,old,require_current=action!='rollback',feedback_pg_plan=True)
    if not allow_db: raise ValueError('readonly_preflight_opt_in_required')
    current=(root/'current').resolve(strict=True)
    ctx=gates.context(root,current,offline=action=='rollback')
    gates.persistent_paths(root,ctx['env']); gates.config_source(root,old)
    receipt=root/'state'/('feedback-upgrade-'+build['build_id']+'.json')
    if action=='archive-failed':
        return archive_failed(kit,root,old,build,ctx,receipt,execute)
    if action=='rollback':
        if not execute: raise ValueError('execute_required')
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_uid!=0 or receipt.stat().st_mode & 0o077:
            raise ValueError('private_root_receipt_required')
        proof=json.loads(receipt.read_text())
        target=Path(proof['rollback'])
        if proof['old']!=str(old) or proof['commit']!=build['commit'] or proof['config_hash']!=ctx['config_hash'] or [gates.normalize_unit(u) for u in proof['units']]!=[gates.normalize_unit(u) for u in ctx['units']]:
            raise ValueError('rollback_identity_or_configuration_changed')
        if target.parent!=root/'releases' or target.is_symlink() or current not in (root/'releases'/build['build_id'],old,target):
            raise ValueError('unexpected_rollback_path')
        if file_manifest(target)!=proof['rollback_files']: raise ValueError('rollback_files_changed')
        gates.config_source(root,target)
        schema(kit,root,ctx['env'],'20261112_000065')
        gates.unchanged(ctx)
        gates.command(['systemctl','stop',gates.WEB,gates.API])
        if gates.active(gates.API) or gates.active(gates.WEB): raise ValueError('services_not_stopped')
        gates.unchanged(ctx)
        gates.replace_link(root,target); gates.command(['systemctl','start',gates.API,gates.WEB])
        baseline=json.loads((kit/'EXPECTED-SERVER.json').read_text())
        gates.http_identity(baseline['frontend_identity'],baseline['backend_identity'])
        return {'ok':True,'compatible_rollback':True,'pg_feedback_preserved':True,'database_downgrade':False}
    schema(kit,root,ctx['env'],'20261106_000064')
    if action=='preflight': return {'ok':True,'revision':'20261106_000064','sqlite_preservation_plan':'immutable_backup_then_pg_import','switched':False}
    if not execute or not allow_write: raise ValueError('execute_and_feedback_migration_opt_in_required')
    if receipt.exists(): raise ValueError('maintenance_already_started_inspect_receipt')
    new=root/'releases'/build['build_id']
    stage(kit,root,old,feedback_pg_plan=True)
    rollback,rollback_files=compatible_release(kit,root,old,build)
    release_permissions(new); release_permissions(rollback)
    # 回滚程序须先就位，迁移失败不改current；迁移成功后只能用兼容回滚。
    proof={'old':str(old),'rollback':str(rollback),'rollback_files':rollback_files,'commit':build['commit'],
           'config_hash':ctx['config_hash'],'units':list(ctx['units'])}
    private_json(receipt,proof)
    gates.unchanged(ctx)
    gates.command(['systemctl','stop',gates.WEB,gates.API])
    if gates.active(gates.API) or gates.active(gates.WEB): raise ValueError('services_not_stopped')
    gates.unchanged(ctx)
    inspect(root,old,feedback_pg_plan=True)
    snapshot,original_files,source_digest=snapshot_sqlite(old,root/'state'/('feedback-backup-'+build['build_id']))
    clean={k:v for k,v in ctx['env'].items() if not k.startswith('PG')}
    clean['PYTHONDONTWRITEBYTECODE']='1'
    args=[str(root/'venv/bin/python'),'-B',str(kit/'feedback_pg.py'),'--execute','--source-digest',source_digest]
    if snapshot: args+=['--snapshot',str(snapshot)]
    p=subprocess.run(args,env=clean,capture_output=True,text=True,timeout=120)
    if p.returncode: raise ValueError('migration_failed_services_stopped_no_switch_inspect_before_restart')
    result=json.loads(p.stdout)
    if not result.get('ok'): raise ValueError('migration_not_confirmed')
    if original_files!={name:digest(old/'backend/data'/name) for name in original_files}:
        raise ValueError('original_sqlite_changed')
    schema(kit,root,ctx['env'],'20261112_000065')
    gates.unchanged(ctx); gates.staged_integrity(kit,new)
    gates.replace_link(root,new); gates.command(['systemctl','start',gates.API,gates.WEB])
    identity={'git_commit':build['commit'],'build_id':build['build_id']}
    gates.http_identity(identity,identity)
    return {'ok':True,'migration':result,'original_sqlite_preserved':True,'switched':True}


if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['preflight','apply','rollback','archive-failed'])
    p.add_argument('--root',type=Path,required=True); p.add_argument('--expected-old',type=Path,required=True)
    p.add_argument('--execute',action='store_true'); p.add_argument('--allow-readonly-db',action='store_true')
    p.add_argument('--allow-feedback-migration',action='store_true')
    a=p.parse_args()
    try: result=run(a.action,Path(__file__).parent,a.root,a.expected_old,a.execute,a.allow_readonly_db,a.allow_feedback_migration)
    except Exception as e:
        result={'ok':False,'error':str(e) if type(e) is ValueError else type(e).__name__,
                'instruction':'stop; preserve original SQLite and PG; no downgrade; after065 use compatible rollback only'}
    print(json.dumps(result)); raise SystemExit(0 if result['ok'] else 1)
