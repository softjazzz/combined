"""Build from fixed git objects, never collect local env/data/dist."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path('C:/Users/Coldplay/Downloads/MedQC-backend-emr-fix-6cd06ff77-20261111')
KIT = OUT / 'medqc-backend-emr-fix'
SOURCE = 'apps/medqc-web/backend/app/routers/emr_render.py'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    if '--finalize' in sys.argv:
        assert json.loads((OUT / 'VALIDATION.json').read_text())['status'] == 'PASS'
        for name in ('VALIDATION.json', 'VALIDATION-REPORT.md'):
            shutil.copyfile(OUT / name, KIT / name)
        files = sorted(p for p in KIT.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
        assert {p.name for p in files} == {'emr_render.py', 'manage.py', 'PATCH.json', 'README-DSH.md', 'VALIDATION.json', 'VALIDATION-REPORT.md'}
        (KIT / 'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(KIT).as_posix()}\n' for p in files), encoding='utf-8')
        archive = OUT / 'MedQC-backend-emr-fix-6cd06ff77.tar.gz'
        with tarfile.open(archive, 'x:gz') as stream:
            stream.add(KIT, arcname=KIT.name)
        checksum = sha(archive.read_bytes())
        archive.with_name(archive.name + '.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='ascii')
        print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': checksum}))
        raise SystemExit(0)
    KIT.mkdir(parents=True, exist_ok=False)
    base = git('rev-parse', 'e1f65ffe7').decode().strip()
    commit = git('rev-parse', '6cd06ff77').decode().strip()
    before = git('show', f'{base}:{SOURCE}')
    after = git('show', f'{commit}:{SOURCE}')
    assert git('diff', '--name-only', base, commit, '--', 'apps/medqc-web/backend/app').decode().strip() == SOURCE
    compile(after, SOURCE, 'exec')
    (KIT / 'emr_render.py').write_bytes(after)
    (OUT / 'validation-baseline-emr_render.py').write_bytes(before)
    meta = dict(patch_id='backend-emr-6cd06ff77', base_commit=base, source_commit=commit,
                target='backend/app/routers/emr_render.py', before_sha256=sha(before), after_sha256=sha(after),
                dependencies_installed=False, database_migration=False, frontend_unchanged=True,
                automatic_activation=False, runtime_build_unchanged=True)
    (KIT / 'PATCH.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
    for name in ('manage.py', 'README-DSH.md'):
        shutil.copyfile(Path(__file__).parent / name, KIT / name)
    shutil.copyfile(KIT / 'README-DSH.md', OUT / 'README-DSH.md')
    print(OUT)
