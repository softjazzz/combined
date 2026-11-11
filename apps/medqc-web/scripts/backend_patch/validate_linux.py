"""Actual payload replacement/rollback in a disposable fixture; never starts app or reads env."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

kit, baseline, report = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location('patch_manager', kit / 'manage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
meta = m.read(kit / 'PATCH.json')
checks = []


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError('expected rejection: ' + expected)
    checks.append(expected)


with tempfile.TemporaryDirectory(prefix='medqc-backend-patch-') as temp:
    root = Path(temp)
    release = root / 'releases' / 'synthetic'
    target = release / m.TARGET
    target.parent.mkdir(parents=True)
    target.write_bytes(baseline.read_bytes())
    (release / 'backend/app/data').mkdir()
    runtime = release / 'backend/app/data/runtime_build.json'
    runtime.write_text(json.dumps({'git_commit': meta['base_commit']}))
    (root / 'current').symlink_to(release, target_is_directory=True)
    markers = [release / 'frontend/dist/synthetic-marker', root / 'config/marker', root / 'state/case-materials/marker']
    for path in markers:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'synthetic-preserve')
    old_runtime = runtime.read_bytes()
    assert m.manage(kit, root, release, 'check')['ok']
    assert not list(target.parent.glob('*.before-*'))
    checks.append('check_readonly')
    target.write_bytes(b'# changed')
    reject(lambda: m.manage(kit, root, release, 'apply'), 'original_file_mismatch')
    target.write_bytes(baseline.read_bytes())
    reject(lambda: m.manage(kit, root, root, 'apply'), 'current_release_changed')
    assert m.manage(kit, root, release, 'apply')['ok']
    assert m.digest(target) == meta['after_sha256']
    compile(target.read_bytes(), str(target), 'exec')
    checks.append('actual_payload_apply_and_compile')
    reject(lambda: m.manage(kit, root, release, 'apply'), 'original_file_mismatch')
    target.write_bytes(b'# changed after apply')
    reject(lambda: m.manage(kit, root, release, 'rollback'), 'target_or_backup_changed')
    target.write_bytes((kit / 'emr_render.py').read_bytes())
    assert m.manage(kit, root, release, 'rollback')['ok']
    assert target.read_bytes() == baseline.read_bytes()
    assert target.with_name(target.name + '.before-' + m.PATCH_ID).read_bytes() == baseline.read_bytes()
    checks.append('byte_exact_rollback_backup_preserved')
    assert runtime.read_bytes() == old_runtime
    assert all(path.read_bytes() == b'synthetic-preserve' for path in markers)
    checks.append('runtime_frontend_configuration_snapshot_unchanged')
report.write_text(json.dumps(dict(status='PASS', checks=checks, python=sys.version,
    os_release=Path('/etc/os-release').read_text(), database_connections=0, model_calls=0,
    application_started=False), indent=2)+'\n')
print(report.read_text())
