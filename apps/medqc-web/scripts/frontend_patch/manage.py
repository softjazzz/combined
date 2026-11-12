"""Offline frontend-only patch. Run as the business service user, with Web stopped."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def hashes(root):
    result = {}
    if root.is_symlink() or not root.is_dir():
        raise ValueError('regular_directory_required')
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink_not_allowed')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def read(path):
    if path.is_symlink():
        raise ValueError('metadata_symlink_not_allowed')
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    # Exclusive receipts; never overwrite audit records or an earlier backup.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def manage(kit, root, expected, action):
    kit, root = kit.resolve(strict=True), root.resolve(strict=True)
    meta = read(kit / 'PATCH.json')
    patch_id = meta['patch_id']
    if not patch_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in patch_id):
        raise ValueError('invalid_patch_id')
    release = (root / 'current').resolve(strict=True)
    if (root / 'releases').is_symlink() or release.parent != root / 'releases' or release != expected.resolve(strict=True):
        raise ValueError('current_release_changed_or_outside_root')
    runtime = read(release / 'backend/app/data/runtime_build.json')
    if runtime['git_commit'] != meta['backend_commit']:
        raise ValueError('backend_commit_mismatch')
    parent = release / 'frontend'
    if parent.is_symlink():
        raise ValueError('frontend_parent_symlink_forbidden')
    dist = parent / 'dist'
    stage = parent / ('.staged-' + patch_id)
    backup = parent / ('dist-before-' + patch_id)
    retired = parent / ('dist-rolled-back-' + patch_id)
    receipt = parent / (patch_id + '.json')
    done = parent / (patch_id + '-applied.json')
    rolled = parent / (patch_id + '-rollback.json')
    if action == 'rollback':
        record = read(receipt)
        if record['release'] != str(release) or record['patch_id'] != patch_id or not done.is_file():
            raise ValueError('receipt_mismatch_or_incomplete_apply')
        if retired.exists() or retired.is_symlink() or rolled.exists():
            raise ValueError('rollback_destination_exists')
        if hashes(dist) != record['after'] or hashes(backup) != record['before']:
            raise ValueError('frontend_or_backup_changed')
        dist.rename(retired)
        try:
            backup.rename(dist)
        except BaseException:
            retired.rename(dist)
            raise
        write(rolled, {'patch_id': patch_id, 'restored': True})
        return {'ok': True, 'action': action, 'backend_unchanged': True}
    if hashes(kit / 'dist') != meta['files']:
        raise ValueError('payload_checksum_mismatch')
    if read(kit / 'dist/build-info.json') != meta['frontend_identity']:
        raise ValueError('frontend_identity_mismatch')
    old_identity = read(dist / 'build-info.json')
    if old_identity != meta['previous_frontend_identity']:
        raise ValueError('previous_frontend_mismatch')
    before = hashes(dist)
    for path in (stage, backup, retired, receipt, done, rolled):
        if path.exists() or path.is_symlink():
            raise ValueError('patch_destination_exists; do_not_delete_existing_backup')
    if action == 'check':
        return {'ok': True, 'action': action, 'backend_commit': runtime['git_commit'], 'files': len(meta['files'])}
    shutil.copytree(kit / 'dist', stage)
    if hashes(stage) != meta['files']:
        raise ValueError('staged_checksum_mismatch')
    write(receipt, {'patch_id': patch_id, 'release': str(release), 'before': before, 'after': meta['files']})
    dist.rename(backup)
    try:
        stage.rename(dist)
    except BaseException:
        backup.rename(dist)
        raise
    write(done, {'patch_id': patch_id, 'applied': True})
    return {'ok': True, 'action': action, 'backup': str(backup), 'backend_unchanged': True}


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
