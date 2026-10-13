"""Replay only 13 explicitly synthetic historical antimicrobial cases at fixed SHA.
No pytest execution, Worker, API, persistence, PG, dotenv or model client.
"""
from pathlib import Path
import asyncio
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import sys
import time
import traceback
import types

# Cache only standard-library Windows platform detection before I/O guard.
# This avoids subprocess opening nul inside imports; no project/env file read.
platform.uname()
platform.machine()

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
MANIFEST = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
CASES = json.loads((ROOT / 'cases.json').read_text(encoding='utf-8'))
assert len(CASES) == 13
assert hashlib.sha256((ROOT / 'cases.json').read_bytes()).hexdigest() == MANIFEST['cases_sha256']
for row in MANIFEST['source_files']:
    relative = row['path'].removeprefix('apps/medqc-web/backend/')
    assert hashlib.sha256((SOURCE / relative).read_bytes()).hexdigest() == row['sha256']

BOUNDARY_ATTEMPTS = []


def deny_database(*args, **kwargs):
    BOUNDARY_ATTEMPTS.append('database')
    raise AssertionError('ANTIBIOTIC_DATABASE_DENIED')


def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0]))
        if path.name.lower().startswith('.env'):
            BOUNDARY_ATTEMPTS.append('dotenv_read')
            raise AssertionError('ANTIBIOTIC_DOTENV_READ_DENIED')
        mode = args[1] if len(args) > 1 else ''
        flags = args[2] if len(args) > 2 else 0
        writing = (isinstance(mode, str) and any(char in mode for char in 'wax+')) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        )
        if writing:
            resolved = path.resolve()
            if not resolved.is_relative_to(ROOT) or resolved.is_relative_to(SOURCE):
                BOUNDARY_ATTEMPTS.append('write_outside_artifact_outputs')
                raise AssertionError('ANTIBIOTIC_WRITE_SCOPE_DENIED')
    if event == 'socket.getaddrinfo':
        BOUNDARY_ATTEMPTS.append('network_dns')
        raise AssertionError('ANTIBIOTIC_NETWORK_DENIED')
    if event == 'socket.connect':
        # Windows asyncio self-pipe only; no ordinary loopback allowance.
        internal_socketpair = any(
            frame.name == 'socketpair' and Path(frame.filename).name == 'socket.py'
            for frame in traceback.extract_stack()
        )
        if not internal_socketpair:
            BOUNDARY_ATTEMPTS.append('network_connect')
            raise AssertionError('ANTIBIOTIC_NETWORK_DENIED')


sys.addaudithook(audit)
# Synthetic values exist only in this child process. No deployment env consumed.
os.environ.clear()
os.environ.update(
    DATABASE_URL='', JWT_SECRET='synthetic-antibiotic-evidence-only',
    DB_SCHEMA_MODE='single', DB_SEARCH_PATH='',
    SystemRoot='C:/Windows', WINDIR='C:/Windows', PYTHONUTF8='1',
)
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
dotenv.dotenv_values = lambda *args, **kwargs: {}
for driver_name in ('psycopg', 'psycopg2', 'asyncpg'):
    if importlib.util.find_spec(driver_name):
        driver = importlib.import_module(driver_name)
        driver.connect = deny_database
        if driver_name == 'asyncpg':
            driver.create_pool = deny_database
        if driver_name == 'psycopg' and hasattr(driver, 'AsyncConnection'):
            driver.AsyncConnection.connect = deny_database

os.chdir(SOURCE)
sys.path.insert(0, str(SOURCE))
# Suppress package startup only. All dependency implementation modules are real.
for name, folder in (
    ('app', SOURCE / 'app'),
    ('app.services', SOURCE / 'app/services'),
    ('app.services.luxian_0609', SOURCE / 'app/services/luxian_0609'),
):
    package = types.ModuleType(name)
    package.__path__ = [str(folder)]
    sys.modules[name] = package
import sqlalchemy as sa
sa.engine.Engine.connect = deny_database

from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result

fixture_path = SOURCE / 'tests/unit/test_luxian_0609_native_extended_document_execution.py'
fixture_spec = importlib.util.spec_from_file_location('antibiotic_fixed_fixture', fixture_path)
fixture = importlib.util.module_from_spec(fixture_spec)
sys.modules[fixture_spec.name] = fixture
fixture_spec.loader.exec_module(fixture)


def loaded_source_provenance():
    expected = {
        (SOURCE / row['path'].removeprefix('apps/medqc-web/backend/')).resolve(): row['sha256']
        for row in MANIFEST['source_files']
    }
    package_substitutes = {'app', 'app.services', 'app.services.luxian_0609'}
    loaded = []
    errors = []
    for name, module in sorted(sys.modules.copy().items()):
        if name != 'app' and not name.startswith('app.'):
            continue
        if name in package_substitutes:
            loaded.append({'module': name, 'kind': 'declared_package_initializer_suppression'})
            continue
        filename = getattr(module, '__file__', None)
        path = Path(filename).resolve() if filename else None
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path and path.is_file() else None
        matched = path in expected and digest == expected.get(path)
        loaded.append({'module': name, 'source_path': str(path), 'sha256': digest, 'manifest_match': matched})
        if not matched:
            errors.append(name)
    changed = []
    for path, digest in expected.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            changed.append(str(path))
    return loaded, errors, changed


async def main():
    started = time.monotonic()
    rows = []
    for case in CASES:
        row = {key: case[key] for key in ('original_index', 'id', 'rule', 'expected', 'prior_observed')}
        try:
            snapshot, materials = fixture._session(case['rows'])
            raw = await execute_luxian_0609_native_extended_document_rules(
                rule_ids=(case['rule'],), evidence_snapshot=snapshot,
                evidence_materials=materials, decision_rule_ids=(case['rule'],),
                llm_client=None,
            )
            reduced = bind_and_reduce_luxian_0609_rule_decisions(
                decisions=raw.decisions, expected_rule_ids=(case['rule'],),
                snapshot=snapshot, evidence_materials=materials,
            )[0]
            final = finalize_luxian_0609_reduced_customer_result(
                decision=reduced,
                raw_customer_display_facts=dict(raw.customer_display_facts).get(case['rule']),
                evidence_snapshot=snapshot, evidence_materials=materials,
            )
            assert raw.llm_call_count == 0
            row.update(observed=final['status'], reason_code=final.get('reason_code'),
                       expected_match=final['status'] == case['expected'],
                       prior_observation_match=final['status'] == case['prior_observed'],
                       llm_call_count=raw.llm_call_count, final=final)
        except Exception as error:
            row.update(observed='exception', expected_match=False,
                       prior_observation_match=False,
                       exception=type(error).__name__ + ': ' + str(error))
        rows.append(row)
        print(json.dumps({key: value for key, value in row.items() if key != 'final'}, ensure_ascii=False))
    loaded, source_errors, changed_sources = loaded_source_provenance()
    result = {
        'sha': MANIFEST['sha'], 'case_count': len(rows),
        'completed_without_exception': sum(row['observed'] != 'exception' for row in rows),
        'expected_matches': sum(row['expected_match'] for row in rows),
        'prior_observation_matches': sum(row['prior_observation_match'] for row in rows),
        'boundary_attempts': BOUNDARY_ATTEMPTS,
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'cases_sha256': MANIFEST['cases_sha256'],
        'pytest_execution': False, 'real_model_calls': 0,
        'production_edits': False, 'cases': rows,
        'loaded_app_modules': loaded,
        'source_provenance_errors': source_errors,
        'post_execution_changed_sources': changed_sources,
        'method': MANIFEST['method'],
        'scope_limit': 'Synthetic fixture -> real executor/binding/finalizer only; no real source collector, Worker, Store or API',
    }
    (ROOT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in result.items() if key not in {'cases', 'loaded_app_modules'}}, ensure_ascii=False))
    # Status mismatches are observations, not fixture errors and not automatically defects.
    assert not BOUNDARY_ATTEMPTS
    assert not source_errors and not changed_sources
    assert result['completed_without_exception'] == 13


if __name__ == '__main__':
    asyncio.run(main())
