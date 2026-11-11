"""Fixed package, disposable Ubuntu runner only; no hospital credentials or data."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import time

TMP = Path(os.environ['RUNNER_TEMP']).resolve()
REPO = Path.cwd().resolve()
EVIDENCE = TMP / 'evidence'
FULL = TMP / 'full/medqc-offline'
KIT = TMP / 'input/new/medqc-app-upgrade'
OLDKIT = TMP / 'input/old/medqc-app-upgrade'
ROOT = TMP / 'isolated-business'
PG = Path('/usr/lib/postgresql/16/bin')
report = {'package_sha256': 'cc62a18e512b29eb5c1aa568de1730dad17cd449d1adbe2097b8cab4bbd6502d',
          'application_commit': 'e1f65ffe73f121842dfa997c41d1c9c517bd804e',
          'old_application_commit': 'fa314c6c251fc5dd02eda96a7d30d70642cc1eb0',
          'network': 'unshare net; loopback only; disposable runner',
          'existing_business_database_connections': 0, 'real_model_calls': 0,
          'qc_tasks': 0, 'blocked': []}
processes = []
pg_started = False


def run(args, name, *, cwd=None, env=None, required=True):
    with (EVIDENCE / (name + '.log')).open('w') as output:
        result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                stdout=output, stderr=subprocess.STDOUT)
    if required and result.returncode:
        raise RuntimeError(name + '_failed; see isolated log')
    return result.returncode


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql(statement):
    return subprocess.check_output([str(PG / 'psql'), '-h', '127.0.0.1', '-p', '55498',
        '-d', 'medqc_business', '-v', 'ON_ERROR_STOP=1', '-Atc', statement], text=True).strip()


def switch(target):
    link = ROOT / 'next-current'
    link.symlink_to(target)
    link.replace(ROOT / 'current')


def stop_processes():
    for process in processes:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    processes.clear()


def startup(label, expected_commit):
    backend = ROOT / 'current/backend'
    api_log = (EVIDENCE / (label + '-api.log')).open('w')
    web_log = (EVIDENCE / (label + '-web.log')).open('w')
    api = subprocess.Popen([str(PYTHON), '-B', '-m', 'uvicorn', 'app.main:app',
                            '--host', '127.0.0.1', '--port', '8001'], cwd=backend,
                           stdout=api_log, stderr=subprocess.STDOUT)
    web = subprocess.Popen([str(PYTHON), '-B', '../serve_dist_spa.py', '--host', '127.0.0.1',
                            '--port', '8080', '--dir', '../frontend/dist',
                            '--api-target', 'http://127.0.0.1:8001'], cwd=backend,
                           stdout=web_log, stderr=subprocess.STDOUT)
    processes.extend([api, web])
    api_log.close()
    web_log.close()
    for _ in range(120):
        if api.poll() is not None:
            stop_processes()
            return False
        try:
            for port in (8001, 8080):
                c = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                c.request('GET', '/api/v1/runtime-build')
                r = c.getresponse()
                body = r.read().decode()
                assert r.status == 200 and expected_commit in body
                c.close()
            c = http.client.HTTPConnection('127.0.0.1', 8080, timeout=2)
            c.request('GET', '/workstation-v5/login')
            r = c.getresponse()
            r.read()
            assert r.status == 200
            c.close()
            report[label] = {'api_and_proxy_build': True, 'login_page_200': True}
            return True
        except (OSError, AssertionError, http.client.HTTPException):
            time.sleep(0.5)
    stop_processes()
    return False


try:
    assert platform.freedesktop_os_release()['VERSION_ID'] == '22.04'
    assert sys.version_info[:2] == (3, 10)
    report['platform'] = {'os': 'Ubuntu22.04', 'python': platform.python_version()}
    assert (KIT / 'requirements-linux.lock').read_bytes() == (FULL / 'requirements-linux.lock').read_bytes()
    ROOT.mkdir()
    for name in ('venvs', 'releases', 'config', 'state/case-materials/objects', 'state/case-materials/tasks', 'backups', 'logs'):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    VENV = ROOT / 'venvs/existing'
    run([sys.executable, '-m', 'venv', '--without-pip', VENV], 'prepare-fixture-venv')
    PYTHON = VENV / 'bin/python'
    pip_wheel = next((FULL / 'wheelhouse').glob('pip-*.whl'))
    run([PYTHON, '-m', 'pip', 'install', '--no-index', '--no-deps', pip_wheel],
        'prepare-fixture-pip', env={**os.environ, 'PYTHONPATH': str(pip_wheel)})
    run([PYTHON, '-m', 'pip', 'install', '--no-index', '--require-hashes', '--no-cache-dir',
         '--find-links', FULL / 'wheelhouse', '-r', KIT / 'requirements-linux.lock'], 'prepare-fixture-locked-dependencies')
    # No pip install occurs after this fixture-preparation boundary.
    before_freeze = subprocess.check_output([str(PYTHON), '-m', 'pip', 'freeze'], text=True)
    report['fixture_dependencies_from_existing_wheelhouse'] = True
    (ROOT / 'venv').symlink_to(VENV)
    (ROOT / 'tools').symlink_to(FULL / 'tools')
    old = ROOT / 'releases/old-fa314c6c2'
    shutil.copytree(OLDKIT / 'application', old)
    (ROOT / 'current').symlink_to(old)
    config = ROOT / 'config/business.env'
    config.write_text('\n'.join([
        'ENV=production', 'DATA_SOURCE=pg', 'DB_SCHEMA_MODE=split', 'DB_SEARCH_PATH=sys,qc,cdm,public,legacy',
        'DATABASE_URL=postgresql://medqc_business_app@127.0.0.1:55498/medqc_business',
        'JWT_SECRET=' + secrets.token_hex(32), 'MEDQC_STARTUP_MODE=normal',
        'MEDQC_STARTUP_BACKGROUND_ENABLED=false', 'MEDQC_RESUME_QC_TASKS=false',
        'QC_SC_RULE_SOURCE_MONITOR_ENABLED=false', 'QC_DAILY_SCHEDULER_ENABLED=false',
        'QC_TASK_DISPATCH_MODE=legacy', 'MEDQC_CLINICAL_SOURCE_MODE=fixed_donghua_cdm',
        'QC_CASE_MATERIAL_DIR=' + str(ROOT / 'state/case-materials'),
        'QC_DISPATCH_STATE_DIR=' + str(ROOT / 'state/dispatch'),
        'PRODUCT_ACTIVATION_REQUIRED=false', 'TZ=Asia/Shanghai', 'LLM_API_KEY=',
    ]) + '\n')
    config.chmod(0o600)
    (old / 'backend/.env').symlink_to(config)
    before_config = digest(config)
    for name in ('objects/synthetic-marker', 'tasks/synthetic-marker'):
        (ROOT / 'state/case-materials' / name).write_text('synthetic retained bytes; not a patient snapshot')
    run([PG / 'initdb', '-D', ROOT / 'pg', '-A', 'trust', '--no-locale', '-E', 'UTF8'], 'init-owned-pg16')
    run([PG / 'pg_ctl', '-D', ROOT / 'pg', '-l', EVIDENCE / 'pg16.log', '-o',
         '-h 127.0.0.1 -p 55498 -k ' + str(ROOT) + ' -c max_connections=20', '-w', 'start'], 'start-owned-pg16')
    pg_started = True
    run([PG / 'psql', '-h', '127.0.0.1', '-p', '55498', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
         '-c', 'CREATE ROLE medqc_business_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
         '-c', 'CREATE DATABASE medqc_business OWNER medqc_business_app'], 'prepare-owned-db')
    # The old validated full kit supplies complete migration helpers for the synthetic old fixture.
    run([PYTHON, '-B', FULL / 'deploy/db-admin.py', 'migrate', '--root', ROOT], 'initialize-old-062')
    assert sql('SELECT version_num FROM public.alembic_version') == '20261102_000062'
    sql("CREATE TABLE public.synthetic_retention (kind text PRIMARY KEY, value text); INSERT INTO public.synthetic_retention VALUES ('materials','retained'),('history','retained')")
    sql('ALTER TABLE public.synthetic_retention OWNER TO medqc_business_app')
    before_rows = sql('SELECT kind,value FROM public.synthetic_retention ORDER BY kind')
    assert startup('old_before_upgrade', report['old_application_commit'])
    stop_processes()
    run([PYTHON, '-B', KIT / 'check_compat.py', '--root', ROOT], 'exact-package-check-compat')
    run([PYTHON, '-B', KIT / 'cdm-preflight.py'], 'offline-cdm-contract-import')
    run([PYTHON, '-B', KIT / 'stage_upgrade.py', '--root', ROOT, '--expected-current', old], 'exact-package-stage')
    build = json.loads((KIT / 'BUILD.json').read_text())
    staged = ROOT / 'releases' / build['build_id']
    assert (ROOT / 'current').resolve() == old
    report['stage_does_not_activate'] = True
    for source in (KIT / 'application').rglob('*'):
        if source.is_file():
            assert source.read_bytes() == (staged / source.relative_to(KIT / 'application')).read_bytes()
    switch(staged)
    # Exercise the exact delivered migration command rather than hiding missing helper files.
    migration_rc = run([PYTHON, '-B', KIT / 'deploy/db-admin.py', 'migrate', '--root', ROOT],
                       'exact-package-migration', required=False)
    report['delivered_migration_command_passed'] = migration_rc == 0
    if migration_rc:
        report['blocked'].append('delivered_migration_command_failed')
        # Continue diagnosis only, using unchanged tracked helpers from the exact application base.
        # This is not counted as the delivered package migration passing.
        run([PYTHON, '-B', REPO / 'apps/medqc-web/scripts/linux_offline/deploy/db-admin.py',
             'migrate', '--root', ROOT], 'diagnostic-complete-helper-migration')
    assert sql('SELECT version_num FROM public.alembic_version') == '20261106_000064'
    report['synthetic_migration_063_064'] = True
    assert startup('new_after_upgrade', report['application_commit'])
    stop_processes()
    switch(old)
    rollback_started = startup('old_after_rollback_on_064', report['old_application_commit'])
    report['code_rollback_old_runtime_starts_with_retained_064'] = rollback_started
    if not rollback_started:
        report['blocked'].append('old_fa314c6c2_cannot_start_on_retained_064')
    stop_processes()
    assert sql('SELECT kind,value FROM public.synthetic_retention ORDER BY kind') == before_rows
    assert sql('SELECT version_num FROM public.alembic_version') == '20261106_000064'
    assert digest(config) == before_config
    assert (ROOT / 'venv').resolve() == VENV
    assert subprocess.check_output([str(PYTHON), '-m', 'pip', 'freeze'], text=True) == before_freeze
    for name in ('objects/synthetic-marker', 'tasks/synthetic-marker'):
        assert (ROOT / 'state/case-materials' / name).read_text() == 'synthetic retained bytes; not a patient snapshot'
    report['dependencies_installed_during_upgrade'] = 0
    report['config_venv_synthetic_history_material_bytes_retained'] = True
    switch(staged)
    assert startup('new_recovery_after_rollback_probe', report['application_commit'])
    stop_processes()
    report['status'] = 'PASS' if not report['blocked'] else 'BLOCKED'
except Exception as error:
    report['status'] = 'BLOCKED'
    report['harness_or_execution_error'] = str(error)
finally:
    private_log = ROOT / 'logs/migration-private.log'
    if private_log.exists():
        # Synthetic fixture only; no hospital configuration or real material is ever loaded.
        shutil.copyfile(private_log, EVIDENCE / 'synthetic-migration-detail.log')
    stop_processes()
    if pg_started:
        run([PG / 'pg_ctl', '-D', ROOT / 'pg', '-m', 'fast', '-w', 'stop'], 'stop-owned-pg16', required=False)
    (EVIDENCE / 'VALIDATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
sys.exit(0 if report['status'] == 'PASS' else 1)
