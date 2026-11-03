"""构建独立DSH验收包：只取已提交源码、已审查交付和显式Runtime。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

APP = Path(__file__).resolve().parents[1]
REPO = APP.parents[1]


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', '-C', str(REPO), *args], text=True, encoding='utf-8').strip()


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def allowed_backend(relative):
    path = Path(relative)
    if any(p in {'__pycache__', 'sessions', 'uploads', 'manual_qc_runs',
                 'sample_pool_uploads', 'vector', 'logs'} for p in path.parts):
        return False
    if path.parts[:3] == ('app', 'storage', 'qc_diagnostics'):
        return False
    if '.backup' in path.name or path.name.startswith(('tmp_', 'debug_')):
        return False
    if path.parts[:2] == ('app', 'data'):
        return (path.name.startswith(('luxian_0609_', 'sichuan_rules_', 'customer_rules_', 'sc_rule_',
                'sc146_intrinsic_', 'custom_rules_', 'surgery_procedure_', 'coding_rules', 'department_rules_',
                'drg_weights', 'luzhou_dip_')) and path.suffix in {'.json', '.csv'}
                or path.name == 'product_activation_public_key.pem')
    if path.parts[0] == 'data':
        return path.name.startswith('icd') and path.suffix == '.json'
    return (path.parts[0] in {'app', 'alembic', 'config'} and path.suffix in {'.py', '.json', '.csv', '.yaml', '.yml', '.ini', '.txt'}
            or relative in {'requirements.txt', 'alembic.ini', '.env.example'}
            or relative in {'services/__init__.py', 'services/pdf_parser.py'}
            or relative == 'scripts/p9d_isolated_smoke.py')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', required=True)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if git('status', '--porcelain'):
        raise SystemExit('必须先本地提交；不打包混杂未提交源码')
    commit = git('rev-parse', 'HEAD')
    out = Path(args.output).resolve()
    if out.exists():
        raise SystemExit('输出目录必须全新，不覆盖已有包或现场部署')
    runtime = Path(args.runtime).resolve(strict=True)
    if not (runtime / 'python.exe').is_file() or not (runtime / 'python310._pth').is_file():
        raise SystemExit('需要已隔离且不引用开发机路径的Windows Runtime')
    # 前端必须重新构建，不能复用开发机旧dist。
    import os
    build_id = 'DSH-P9D-' + commit[:9]
    env = {**{key: value for key, value in os.environ.items() if not key.startswith('VITE_')},
           'VITE_MEDQC_BUILD_ID': build_id, 'VITE_MEDQC_GIT_COMMIT': commit}
    subprocess.run(['cmd', '/c', 'npx', 'vite', 'build', '--mode', 'customer', '--config',
                    'vite.customer.config.mjs', '--configLoader', 'native'], cwd=APP, env=env, check=True)
    identity = json.loads((APP / 'dist/build-info.json').read_text(encoding='utf-8'))
    if identity['git_commit'] != commit or identity['build_id'] != build_id:
        raise SystemExit('前端构建身份不匹配')
    manifest = json.loads((APP / 'backend/config/strata-qwen36-p9c-approved.json').read_text(encoding='utf-8'))
    handoff = Path(args.handoff).resolve(strict=True)
    for relative, digest in manifest['files'].items():
        source = (handoff / relative).resolve(strict=True)
        if handoff not in source.parents or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise SystemExit('交付文件哈希不匹配')
    out.mkdir(parents=True, exist_ok=False)
    for file in git('ls-files', 'apps/medqc-web/backend').splitlines():
        relative = file.removeprefix('apps/medqc-web/backend/')
        if allowed_backend(relative):
            copy(REPO / file, out / 'backend' / relative)
    for relative in manifest['files']:
        copy(handoff / relative, out / 'provider-handoff' / relative)
    shutil.copytree(runtime, out / 'runtime', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
    shutil.copytree(APP / 'dist', out / 'frontend/dist')
    for name in ('serve_dist_spa.py', 'p9d-isolated.ps1', 'p9d-runtime-selftest.py'):
        copy(APP / 'scripts' / name, out / 'tools' / name)
    copy(APP / 'docs/plans/2026-11-03-strata-p9d-delivery.md', out / 'DSH-GUIDE.md')
    (out / 'build-info.json').write_text(json.dumps({'commit': commit, 'build_id': build_id,
        'source_base': 'd063761e544b4bb6d95892c9802f2edf84f47203', 'p9b_dependency': 'ce79c401a',
        'isolated_test_only': True, 'live_api_verified_by_developer': False}, indent=2) + '\n', encoding='utf-8')
    # 在包内真正的Runtime验证真实Counter向量，不用开发机解释器代替。
    subprocess.run([str(out / 'runtime/python.exe'), '-B',
        str(out / 'backend/scripts/p9d_isolated_smoke.py'), 'verify', '--handoff',
        str(out / 'provider-handoff'), '--state', str(out.parent / (out.name + '-runtime-validation'))],
        cwd=out / 'backend', check=True)
    # 同一解释器强制阻断socket，再次同步装配；不能用开发机向量通过代替包内验证。
    check = """import socket,sys,json
from pathlib import Path
def deny(*a,**k): raise RuntimeError('package_counter_validation_offline')
socket.socket.connect=deny
socket.create_connection=deny
from app.services.strata_handoff import runtime_for,close_runtimes
r=runtime_for(sys.argv[1]); r.ensure_counter()
assert r._counter.validated_vectors==17
assert sys.flags.isolated==1 and sys.flags.no_site==1
package_root=Path(sys.executable).resolve().parents[1]
assert all(package_root==Path(p).resolve() or package_root in Path(p).resolve().parents for p in sys.path)
print(json.dumps({'offline_package_vectors':17,'isolated_runtime':True,'python':sys.version}))
close_runtimes()
"""
    subprocess.run([str(out / 'runtime/python.exe'), '-B', '-c', check, str(out / 'provider-handoff')],
                   cwd=out / 'backend', check=True)
    subprocess.run([str(out / 'runtime/python.exe'), '-B', str(out / 'tools/p9d-runtime-selftest.py'),
        str(out.parent / (out.name + '-formal-validation'))], cwd=out / 'backend', check=True)
    lock = subprocess.check_output([str(out / 'runtime/python.exe'), '-B', '-c',
        "import importlib.metadata as m; print('\\n'.join(sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())))"],
        cwd=out / 'backend', text=True, encoding='utf-8')
    (out / 'requirements-runtime-lock.txt').write_text(lock, encoding='utf-8')
    files = {p.relative_to(out).as_posix(): digest_file(p)
             for p in out.rglob('*') if p.is_file()}
    (out / 'MANIFEST-SHA256.json').write_text(json.dumps(files, indent=2) + '\n', encoding='utf-8')
    archive = out.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as target:
        for file in out.rglob('*'):
            if file.is_file():
                target.write(file, out.name + '/' + file.relative_to(out).as_posix())
    digest = digest_file(archive)
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps({'package': str(archive), 'sha256': digest, 'commit': commit}))


if __name__ == '__main__':
    main()
