"""Verify deployed patch bytes, without importing application or connecting to services."""
import argparse
import hashlib
import json
from pathlib import Path


def inspect(root: Path, expected: Path, require_current=True, feedback_pg_plan=False):
    root = root.resolve(strict=True)
    current = root / 'current'
    old = expected.resolve(strict=True)
    if not current.is_symlink() or (require_current and current.resolve(strict=True) != old) or old.parent != root / 'releases' or (root / 'releases').is_symlink():
        raise ValueError('unexpected_current_release')
    contract = json.loads((Path(__file__).parent / 'EXPECTED-SERVER.json').read_text())
    for label, relative in [('backend', 'backend/app/data/runtime_build.json'), ('frontend', 'frontend/dist/build-info.json')]:
        identity = json.loads((old / relative).read_text())
        if any(identity.get(k) != v for k, v in contract[label + '_identity'].items()):
            raise ValueError(label + '_identity_mismatch')
    for relative, digest in contract['files'].items():
        path = old / relative
        if path.is_symlink() or old not in path.resolve().parents or not path.is_file():
            raise ValueError('missing_or_unsafe_baseline_file: ' + relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('baseline_file_changed: ' + relative)
    # Do not traverse configuration symlinks or cache bytes. Unknown executable
    # backend sources are not allowed to hide outside backend/data.
    for path in (old/'backend').rglob('*'):
        rel=path.relative_to(old).as_posix()
        if path.is_symlink() and rel!='backend/.env': raise ValueError('unknown_backend_symlink')
        if path.is_file() and rel not in contract['files'] and rel!='backend/.env':
            if feedback_pg_plan and rel in {'backend/data/demo_feedbacks.db', 'backend/data/demo_feedbacks.db-wal', 'backend/data/demo_feedbacks.db-shm'}:
                continue  # 原文件保留；仅反馈PG专用维护流程可以接管。
            if '__pycache__' in path.parts and path.suffix=='.pyc': continue
            if rel==contract.get('emr_backup_path') and hashlib.sha256(path.read_bytes()).hexdigest()==contract['emr_before_sha256']: continue
            if rel==contract.get('emr_receipt_path'):
                receipt=json.loads(path.read_text())
                if receipt=={'patch_id':contract['emr_patch_id'],'release':str(old),'before':contract['emr_before_sha256'],'after':contract['files']['backend/app/routers/emr_render.py']}: continue
            raise ValueError('unknown_backend_file')
    actual = {p.relative_to(old / 'frontend/dist').as_posix() for p in (old / 'frontend/dist').rglob('*') if p.is_file()}
    if actual != set(contract['frontend_files']):
        raise ValueError('frontend_file_set_changed')
    local_state = old / 'backend/data'
    if local_state.exists():
        for path in local_state.rglob('*'):
            if feedback_pg_plan and not path.is_symlink() and path.is_file() and path.name in {'demo_feedbacks.db','demo_feedbacks.db-wal','demo_feedbacks.db-shm'} and path.parent == local_state:
                continue
            # The shipped ICD dictionaries and synthetic templates are immutable
            # package resources, already hash-checked above, not runtime state.
            if path.is_symlink() or (path.is_file() and path.relative_to(old).as_posix() not in contract['files']):
                raise ValueError('release_local_state_requires_preservation_plan; do_not_move_or_delete')
    return {'ok': True, 'current': str(old), 'known_files_verified': len(contract['files']), 'database_connections': 0, 'model_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--expected-current', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.root, args.expected_current)
    except Exception as error:
        report = {'ok': False, 'error': str(error) if isinstance(error, ValueError) else type(error).__name__}
    print(json.dumps(report))
    raise SystemExit(0 if report['ok'] else 1)
