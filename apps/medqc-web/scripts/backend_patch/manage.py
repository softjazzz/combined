"""Single-file backend hotfix; API must be stopped for apply/rollback. No imports of app code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


TARGET = 'backend/app/routers/emr_render.py'
PATCH_ID = 'backend-emr-6cd06ff77'


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular_file_required')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    digest(path)
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def manage(kit, root, expected, action):
    kit, root = kit.resolve(strict=True), root.resolve(strict=True)
    meta = read(kit / 'PATCH.json')
    if meta['patch_id'] != PATCH_ID or meta['target'] != TARGET:
        raise ValueError('unexpected_patch_target')
    release = (root / 'current').resolve(strict=True)
    if (root / 'releases').is_symlink() or release.parent != root / 'releases' or release != expected.resolve(strict=True):
        raise ValueError('current_release_changed')
    for rel in ('backend', 'backend/app', 'backend/app/data', 'backend/app/routers'):
        path = release / rel
        if path.is_symlink() or not path.is_dir():
            raise ValueError('target_directory_symlink_or_missing')
    runtime = read(release / 'backend/app/data/runtime_build.json')
    if runtime['git_commit'] != meta['base_commit']:
        raise ValueError('backend_commit_mismatch')
    target = release / TARGET
    backup = target.with_name(target.name + '.before-' + PATCH_ID)
    stage = target.with_name(target.name + '.stage-' + PATCH_ID)
    receipt = release / 'backend' / (PATCH_ID + '.json')
    rollback = release / 'backend' / (PATCH_ID + '-rollback.json')
    payload = kit / 'emr_render.py'
    if digest(payload) != meta['after_sha256']:
        raise ValueError('payload_checksum_mismatch')
    if stage.exists() or stage.is_symlink():
        raise ValueError('staging_already_exists')
    if action == 'rollback':
        record = read(receipt)
        if record != {'patch_id': PATCH_ID, 'release': str(release), 'before': meta['before_sha256'], 'after': meta['after_sha256']}:
            raise ValueError('receipt_mismatch')
        if rollback.exists() or rollback.is_symlink():
            raise ValueError('already_rolled_back')
        # Receipt is written before atomic replacement; rollback also recovers an interrupted apply.
        if digest(target) not in (meta['after_sha256'], meta['before_sha256']) or digest(backup) != meta['before_sha256']:
            raise ValueError('target_or_backup_changed')
        shutil.copy2(backup, stage)
        os.replace(stage, target)
        write(rollback, {'patch_id': PATCH_ID, 'restored_sha256': digest(target)})
        return {'ok': True, 'action': action, 'backup_preserved': True}
    if digest(target) != meta['before_sha256']:
        raise ValueError('original_file_mismatch')
    for path in (backup, receipt, rollback):
        if path.exists() or path.is_symlink():
            raise ValueError('existing_patch_artifact_do_not_remove')
    # Check syntax with the server interpreter without importing the application or writing pyc.
    compile(payload.read_bytes(), TARGET, 'exec')
    if action == 'check':
        return {'ok': True, 'action': action, 'patch_id': PATCH_ID, 'database_connections': 0}
    shutil.copy2(target, backup)
    if digest(backup) != meta['before_sha256']:
        raise ValueError('backup_mismatch')
    shutil.copy2(payload, stage)
    os.chmod(stage, target.stat().st_mode & 0o777)
    if digest(stage) != meta['after_sha256']:
        raise ValueError('stage_mismatch')
    write(receipt, {'patch_id': PATCH_ID, 'release': str(release), 'before': meta['before_sha256'], 'after': meta['after_sha256']})
    os.replace(stage, target)
    return {'ok': True, 'action': action, 'patch_id': PATCH_ID, 'sha256': digest(target), 'runtime_build_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'apply', 'rollback'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--expected-current', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(manage(Path(__file__).parent, args.root, args.expected_current, args.action)))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        raise SystemExit(1)
