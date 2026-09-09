"""只读探针失败语义、关联对照与文件完整性回归。"""
import importlib.util
import json
import hashlib
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[2] / 'scripts/source_sample_export/probe_source_schema.py'
SPEC = importlib.util.spec_from_file_location('source_schema_probe', PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def dictionary():
    return {'tables': [{'name': 'admission_record', 'fields': [{'name': 'visit_id'}]}]}


def relation(**updates):
    return dict(schema_name='public', table_name='admission_record', relkind='r',
                schema_usage=True, table_select=False, row_security_active=False, **updates)


def test_catalog_failure_is_unknown_not_missing():
    result = probe.compare_dictionary(dictionary(), {'relations': {'status': 'permission_denied'}})
    assert result[0]['status'] == 'catalog_unavailable'
    assert result[0]['matches'] is None


def test_catalog_absence_is_scoped_not_permission_failure():
    result = probe.compare_dictionary(dictionary(), {'relations': {'status': 'ok', 'rows': []}})
    assert result[0]['status'] == 'not_found_in_selected_catalog'


def test_all_actual_columns_and_column_privileges():
    result = probe.compare_dictionary(dictionary(), {
        'relations': {'status': 'ok', 'rows': [relation()]},
        'columns': {'status': 'ok', 'rows': [
            {'schema_name': 'public', 'table_name': 'admission_record',
             'column_name': name, 'column_select': name == 'visit_id'}
            for name in ['visit_id', 'extra_full_text']]},
    })[0]['matches'][0]
    assert result['access_status'] == 'insufficient_select_privilege'
    assert result['actual_field_count'] == 2
    assert result['fields_not_in_dictionary'] == ['extra_full_text']


class Denied(Exception):
    pgcode = '42501'


class Cursor:
    description = [('column',)]
    def __init__(self):
        self.commands = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, sql, params=None):
        self.commands.append(sql)
        if sql == 'denied':
            raise Denied()
    def fetchall(self):
        return [(None,), ('',), ('  \r\n  ',)]


class Connection:
    def __init__(self):
        self.cur = Cursor()
    def cursor(self):
        return self.cur


def test_failed_section_rolls_back_and_next_query_survives():
    conn = Connection()
    result = probe.query_section(conn, 'denied', {})
    assert result == {'status': 'permission_denied', 'sqlstate': '42501',
                      'message': 'Denied', 'rows': None}
    assert 'ROLLBACK TO SAVEPOINT probe_section' in conn.cur.commands
    next_result = probe.query_section(conn, 'ok', {})
    assert next_result['rows'] == [{'column': None}, {'column': ''}, {'column': '  \r\n  '}]


def make_package(tmp_path):
    path = tmp_path / 'columns.json'
    probe.write_json(path, {'value': '  \r\n尾部  ', 'null': None, 'empty': ''})
    raw = path.read_bytes()
    manifest = {'files': [{'name': path.name, 'bytes': len(raw),
                           'sha256': hashlib.sha256(raw).hexdigest()}]}
    probe.write_json(tmp_path / 'manifest.json', manifest)
    return path


def test_file_verification_and_exact_strings(tmp_path):
    path = make_package(tmp_path)
    assert probe.verify(tmp_path) == 0
    assert b'\r\n' not in path.read_bytes()
    assert json.loads(path.read_text(encoding='utf-8'))['value'] == '  \r\n尾部  '
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='checksum'):
        probe.verify(tmp_path)


def test_manifest_traversal_is_rejected(tmp_path):
    make_package(tmp_path)
    probe.write_json(tmp_path / 'manifest.json', {
        'files': [{'name': '../secret', 'bytes': 0, 'sha256': ''}]})
    with pytest.raises(ValueError, match='Unsafe'):
        probe.verify(tmp_path)


def test_duplicate_table_names_are_not_silently_resolved():
    first = relation()
    second = {**first, 'schema_name': 'cdm'}
    result = probe.compare_dictionary(dictionary(), {
        'relations': {'status': 'ok', 'rows': [first, second]},
        'columns': {'status': 'failed', 'rows': None},
    })[0]
    assert result['status'] == 'multiple_schemas'
    assert len(result['matches']) == 2
    assert all(m['actual_field_count'] is None for m in result['matches'])


def test_missing_dictionary_sheet_does_not_mark_all_columns_as_new():
    data = dictionary()
    data['tables'][0]['sheet_status'] = 'missing'
    result = probe.compare_dictionary(data, {
        'relations': {'status': 'ok', 'rows': [relation()]},
        'columns': {'status': 'ok', 'rows': []},
    })[0]['matches'][0]
    assert result['field_comparison_status'] == 'unavailable'
    assert result['dictionary_fields_not_in_actual'] is None
