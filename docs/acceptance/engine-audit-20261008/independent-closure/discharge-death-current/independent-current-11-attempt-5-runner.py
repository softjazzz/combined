"""Exactly 11 original synthetic nodes; execution requires parent-owned test slot."""
from pathlib import Path
from datetime import datetime
import hashlib
import ast
import types
import json
import os
import platform
import subprocess
import sys
import traceback

ROOT = Path('F:/MedQC-worktrees/qc-integration-20261008').resolve()
OUT = Path('F:/MedQC-worktrees/review-artifacts/dd-evidence-current').resolve()
FIXED = '56322bcffa32ac33b5069975f1dbf3af18b597ac'
ALLOWED_HEADS = {FIXED, '21f4a93e103a34002a1f9d36f9d895f226c0122f'}
FREEZE_SHA = '966242f69656a3b37435bcfe2ecaf2be498dacdceaec8ba0431f2591941cedb3'
MANIFEST_SHA = 'f51cbc2edb5ded6315add0db6ac693784073bce21ce37082c4dcce29153b0303'
IDS = [f'DD-{i:03d}' for i in [1, 2, 3, 4, 5, 6, 7, 28, 29, 30, 31]]
RULES = {'LX0609-08-01-01', 'LX0609-08-02-02'}
BACKEND = ROOT / 'apps/medqc-web/backend'
OLD = ROOT / '.tmp/engine-audit-20261008/discharge-death'
DATA_NAMES = {
    'luxian_0609_rules_v1.json', 'luxian_0609_phase1_rules_extension_v1.json',
    'luxian_0609_rule_contracts_v1.json', 'luxian_0609_phase1_rule_contracts_extension_v1.json',
    'luxian_0609_rule_master_v1.json',
}
sys.dont_write_bytecode = True
sys.pycache_prefix = str(OUT / 'unused-bytecode-cache')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def decode(value):
    if isinstance(value, dict) and '__frozen_type__' in value:
        kind = value['__frozen_type__']
        if kind == 'datetime':
            return datetime.fromisoformat(value['value'])
        if kind == 'tuple':
            return tuple(decode(x) for x in value['value'])
        if kind == 'frozenset':
            return frozenset(decode(x) for x in value['value'])
        raise ValueError('Unexpected frozen type')
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value

def verify_sources(manifest):
    for rel, expected in manifest['responsibility_source_blobs'].items():
        blob = git('show', FIXED + ':' + rel)
        assert digest(blob) == expected['sha256'], 'Fixed source blob SHA mismatch: ' + rel
        assert git('rev-parse', FIXED + ':' + rel).decode().strip() == expected['git_blob_oid']
        assert (ROOT / rel).read_bytes() == blob, 'Working source differs from fixed source: ' + rel

stats = {'blocked_env_reads': 0, 'blocked_network_operations': 0, 'blocked_db_operations': 0,
         'blocked_external_writes': 0, 'blocked_non_git_processes': 0, 'blocked_non_source_reads': 0, 'dotenv_noop_calls': 0}
repository_reads = set()
blocked_repository_read_paths = []
allowed_git_command_lines = set()

def under(path, parent):
    return path == parent or parent in path.parents

def guard(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.name.lower().startswith('.env'):
            stats['blocked_env_reads'] += 1
            raise RuntimeError('Offline guard forbids environment file reads')
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        if writing and not under(path, OUT):
            stats['blocked_external_writes'] += 1
            raise RuntimeError('Offline guard forbids writes outside artifact directory')
        if not writing and under(path, ROOT):
            if path.suffix in {'.py', '.pyc'}:
                repository_reads.add(str(path))
            elif path.parent == BACKEND / 'app/data' and path.name in DATA_NAMES:
                repository_reads.add(str(path))
            else:
                stats['blocked_non_source_reads'] += 1
                relative = path.relative_to(ROOT).as_posix()
                blocked_repository_read_paths.append(relative)
                raise RuntimeError('Offline guard forbids non-source repository file reads: ' + relative)
    if event in {'socket.__new__', 'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'socket.sendto'}:
        stats['blocked_network_operations'] += 1
        raise RuntimeError('Offline guard forbids network operations')
    if event == 'subprocess.Popen':
        argv = args[1]
        command_line = subprocess.list2cmdline(argv) if isinstance(argv, (list, tuple)) else argv
        allowed = isinstance(command_line, str) and command_line in allowed_git_command_lines
        if not allowed:
            stats['blocked_non_git_processes'] += 1
            raise RuntimeError('Offline guard permits only fixed-source read-only git commands')
    if event in {'os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.chmod', 'os.truncate'}:
        candidates = args[:2] if event == 'os.rename' else args[:1]
        for candidate in candidates:
            if not isinstance(candidate, (str, bytes, os.PathLike)):
                continue
            path = Path(os.fsdecode(candidate)).resolve()
            if not under(path, OUT) and not (event == 'os.mkdir' and path.is_dir()):
                stats['blocked_external_writes'] += 1
                raise RuntimeError('Offline guard forbids filesystem mutation outside artifacts')

def forbid_db(*args, **kwargs):
    stats['blocked_db_operations'] += 1
    raise RuntimeError('Offline guard forbids database engine/connection/SQL operations')

def no_dotenv(*args, **kwargs):
    stats['dotenv_noop_calls'] += 1
    return False

def drive(coro):
    try:
        yielded = coro.send(None)
    except StopIteration as complete:
        return complete.value
    finally:
        coro.close()
    raise RuntimeError('Offline coroutine unexpectedly yielded; no I/O event loop is permitted')

async def execute_one(entry, timecheck, evaluate, canonical_result):
    expected = entry['original_expectation']
    rule = expected['rule_id']
    inp = decode(entry['input'])
    assert rule in RULES
    if inp['mode'] == 'pure_timeliness':
        assert rule == 'LX0609-08-01-01'
        actual = timecheck(**inp['kwargs'])
        return {'actual_status': actual.final_state, 'reason_code': actual.reason_code,
                'display_facts': actual.display_facts, 'finding': '', 'stub_call_count': 0}
    assert inp['mode'] == 'native_binding_canonical' and rule == 'LX0609-08-02-02'
    snapshot, materials, execution, reduced = await evaluate(
        (rule,), inp['rows_by_source'], unavailable_sources=inp['unavailable_sources'], llm_client=None)
    final = canonical_result(rule_id=rule, snapshot=snapshot, materials=materials, result=execution, reduced=reduced)
    assert execution.llm_call_count == execution.total_tokens == 0, 'Original None-client node attempted model use'
    return {'actual_status': final['status'], 'reason_code': final['reason_code'],
            'finding': final['findings'], 'display_facts': final.get('customer_display_facts'),
            'customer_evidence': final.get('customer_evidence'), 'stub_call_count': execution.llm_call_count}

def repository_manifest():
    paths = set()
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if under(path, ROOT) and path.suffix == '.py':
                paths.add(path)
    paths.update(Path(p) for p in repository_reads if Path(p).suffix != '.pyc')
    records = {}
    for path in sorted(paths, key=str):
        rel = path.relative_to(ROOT).as_posix()
        blob = git('show', FIXED + ':' + rel)
        assert path.read_bytes() == blob, 'Loaded/read source differs from fixed commit: ' + rel
        records[rel] = {'sha256': digest(blob), 'git_blob_oid': git('rev-parse', FIXED + ':' + rel).decode().strip()}
    return records

def main():
    report = {'source_commit': FIXED, 'historical_execution_manifest_reconstructed': False,
              'original_medical_expectations_changed': False, 'scope_case_ids': IDS,
              'freeze_sha256': FREEZE_SHA, 'source_manifest_sha256': MANIFEST_SHA,
              'runner_sha256': digest(Path(__file__).read_bytes()), 'results': [], 'guard_statistics': stats}
    try:
        freeze_bytes = (OUT / 'frozen-11-original-inputs-expectations.json').read_bytes()
        manifest_bytes = (OUT / 'current-responsibility-source-manifest.json').read_bytes()
        assert digest(freeze_bytes) == FREEZE_SHA and digest(manifest_bytes) == MANIFEST_SHA
        freeze, manifest = json.loads(freeze_bytes), json.loads(manifest_bytes)
        assert freeze['current_commit'] == manifest['current_commit'] == FIXED
        assert [e['original_expectation']['case_id'] for e in freeze['entries']] == IDS
        assert len(freeze['entries']) == 11
        for entry in freeze['entries']:
            assert digest(canonical(entry['input'])) == entry['input_sha256']
            assert digest(canonical(entry['original_expectation'])) == entry['original_expectation_sha256']
        assert digest((OLD / 'frozen-expectations.json').read_bytes()) == freeze['original_frozen_sha256']
        assert digest((OLD / 'probe.py').read_bytes()) == freeze['original_probe_sha256']
        head_before = git('rev-parse', 'HEAD').decode().strip()
        assert head_before in ALLOWED_HEADS, 'Unapproved execution HEAD; no nodes executed'
        report['execution_head'] = head_before
        assert git('rev-parse', FIXED + '^{tree}').decode().strip() == manifest['current_tree']
        verify_sources(manifest)
        data_manifest_bytes = (OUT / 'attempt-3-static-data-source-manifest.json').read_bytes()
        assert digest(data_manifest_bytes) == 'f2f8d1e0f49485d68fb7388a4d61af8d6b7088bf452441cc8351c89aa1e03f7a'
        data_manifest = json.loads(data_manifest_bytes)
        verify_sources(data_manifest)
        report['static_data_source_manifest_sha256'] = digest(data_manifest_bytes)
        declaration_bytes = (OUT / 'attempt-5-declarative-module-source-manifest.json').read_bytes()
        assert digest(declaration_bytes) == '412c1f878f9c0f0cd11bd4e859c259223745aa70ed4329ef1f1650cbaf33de36'
        declaration_manifest = json.loads(declaration_bytes)
        verify_sources(declaration_manifest)
        report['declarative_module_manifest_sha256'] = digest(declaration_bytes)
        report['module_initialization_substitute'] = 'customer_rule_package: only fixed AST.literal_eval RULE_FAMILY_DEFINITIONS; all other exports/initialization absent'
        report['execution_layers'] = {'pure_timeliness_function': 7, 'native_execution_binding_canonical': 4}
        report['full_module_import_or_endpoint_integration_claimed'] = False
        # Freeze exact read-only git command lines before installing the Windows audit hook.
        tracked_sources = git('ls-tree', '-r', '--name-only', FIXED,
                              'apps/medqc-web/backend/app',
                              'apps/medqc-web/backend/tests/__init__.py',
                              'apps/medqc-web/backend/tests/unit/test_luxian_0609_native_extended_document_execution.py').decode().splitlines()
        permitted_source_paths = {rel for rel in tracked_sources if rel.endswith('.py')}
        permitted_source_paths.update(data_manifest['responsibility_source_blobs'])
        permitted_source_paths.update(manifest['responsibility_source_blobs'])
        exact_commands = [('rev-parse', 'HEAD'), ('rev-parse', FIXED + '^{tree}')]
        exact_commands.extend((op, FIXED + ':' + rel) for rel in sorted(permitted_source_paths) for op in ['show', 'rev-parse'])
        allowed_git_command_lines.update(subprocess.list2cmdline(['git', '-C', str(ROOT), *command]) for command in exact_commands)
        report['git_process_permission'] = 'Exact list2cmdline membership of frozen read-only commands only'
        report['blocked_repository_read_paths'] = blocked_repository_read_paths
        # Root-approved stdlib-only Windows platform cache warmup, before project imports.
        platform.uname()
        report['stdlib_platform_cache_warmed_before_project_guard'] = True
        sys.addaudithook(guard)
        os.environ.pop('DATABASE_URL', None)
        import dotenv
        dotenv.load_dotenv = no_dotenv
        dotenv.dotenv_values = lambda *a, **k: {}
        from dotenv import main as dotenv_main
        dotenv_main.load_dotenv = no_dotenv
        dotenv_main.dotenv_values = lambda *a, **k: {}
        import sqlalchemy
        from sqlalchemy.engine import Engine
        from sqlalchemy.pool import Pool
        from sqlalchemy.orm import Session
        sqlalchemy.create_engine = forbid_db
        Engine.connect = forbid_db
        Engine.raw_connection = forbid_db
        Pool.connect = forbid_db
        Session.execute = forbid_db
        sys.path[:0] = [str(BACKEND), str(BACKEND / 'tests/unit')]
        declaration_rel = next(iter(declaration_manifest['responsibility_source_blobs']))
        declaration_path = ROOT / declaration_rel
        declaration_tree = ast.parse(declaration_path.read_text(encoding='utf-8'))
        declarations = [n for n in declaration_tree.body if isinstance(n, ast.AnnAssign)
                        and isinstance(n.target, ast.Name) and n.target.id == 'RULE_FAMILY_DEFINITIONS']
        assert len(declarations) == 1
        declaration_value = ast.literal_eval(declarations[0].value)
        assert isinstance(declaration_value, tuple)
        assert digest(canonical(declaration_value)) == declaration_manifest['constant_value_canonical_sha256']
        static_module = types.ModuleType('app.services.luxian_0609.customer_rule_package')
        static_module.RULE_FAMILY_DEFINITIONS = declaration_value
        sys.modules[static_module.__name__] = static_module
        from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate_selected, _canonical_extended_result
        from app.services.luxian_0609.extended_document.discharge_documentation import evaluate_discharge_documentation_timeliness
        for entry in freeze['entries']:
            node = {**entry['original_expectation'], 'input_sha256': entry['input_sha256'],
                    'original_expectation_sha256': entry['original_expectation_sha256']}
            try:
                node.update(drive(execute_one(entry, evaluate_discharge_documentation_timeliness,
                                             _evaluate_selected, _canonical_extended_result)))
                node['passed'] = node['actual_status'] == node['expected_status']
            except Exception as error:
                node.update(actual_status='probe_error', passed=False, error_type=type(error).__name__, error=str(error), infrastructure_traceback=traceback.format_exc())
            report['results'].append(node)
        assert len(report['results']) == 11
        verify_sources(manifest)
        verify_sources(data_manifest)
        verify_sources(declaration_manifest)
        assert git('rev-parse', 'HEAD').decode().strip() == head_before, 'Execution HEAD moved during replay'
        report['loaded_and_read_repository_sources'] = repository_manifest()
        report['loaded_and_read_repository_sources'][declaration_rel]['read_mode'] = 'AST_literal_declaration_only; production_module_initialization_not_executed'
        assert not any(v for k, v in stats.items() if k.startswith('blocked_')), 'An offline protection was triggered'
        report['source_binding_verified_before_and_after'] = True
    except Exception as error:
        report.update(infrastructure_error_type=type(error).__name__, infrastructure_error=str(error),
                      infrastructure_traceback=traceback.format_exc(), source_binding_verified_before_and_after=False)
    report['count'] = len(report['results'])
    report['passed'] = sum(n['passed'] for n in report['results'])
    report['completed'] = report['count'] == 11 and report['source_binding_verified_before_and_after']
    destination = OUT / 'current-fixed-56322-attempt-5-results.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'source_commit': FIXED, 'execution_head': report.get('execution_head'),
                     'count': report['count'], 'passed': report['passed'], 'completed': report['completed'],
                     'failed': [n['case_id'] for n in report['results'] if not n['passed']],
                     'infrastructure_error': report.get('infrastructure_error'),
                     'results_sha256': digest(destination.read_bytes())}, ensure_ascii=False))
    return 0 if report['completed'] and report['passed'] == 11 else 1

if __name__ == '__main__':
    raise SystemExit(main())
