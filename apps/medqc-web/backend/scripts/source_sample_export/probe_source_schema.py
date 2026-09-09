"""阶段1：只查系统目录；不读取业务记录，不导出样本数据。"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import sys
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# 所有标识符来自固定SQL，schema条件使用绑定参数；不执行源库视图或函数定义。
SCOPE = """n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
AND (%(schemas)s::text[] IS NULL OR n.nspname = ANY(%(schemas)s::text[]))"""
RELATIONS = f"""SELECT c.oid::bigint AS oid, n.nspname AS schema_name,
c.relname AS table_name, c.relkind, c.relpersistence, c.relowner::regrole::text AS owner,
c.relrowsecurity, c.relforcerowsecurity, c.relispopulated,
pg_catalog.has_schema_privilege(n.oid, 'USAGE') AS schema_usage,
pg_catalog.has_table_privilege(c.oid, 'SELECT') AS table_select,
pg_catalog.has_any_column_privilege(c.oid, 'SELECT') AS any_column_select,
pg_catalog.row_security_active(c.oid) AS row_security_active,
c.reloptions,
pg_catalog.obj_description(c.oid, 'pg_class') AS comment
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE {SCOPE} AND c.relkind IN ('r','p','v','m','f') ORDER BY n.nspname,c.relname"""
QUERIES = {
    'connection': """SELECT current_database() AS database_name, current_user AS role_name,
session_user AS session_role, version() AS server_version,
current_setting('server_version_num') AS server_version_num,
current_setting('server_encoding') AS server_encoding,
current_setting('client_encoding') AS client_encoding,
current_setting('TimeZone') AS timezone,
current_setting('DateStyle') AS datestyle,
current_setting('IntervalStyle') AS intervalstyle,
current_setting('transaction_read_only') AS transaction_read_only,
current_setting('transaction_isolation') AS transaction_isolation,
pg_catalog.txid_current_snapshot()::text AS snapshot,
pg_catalog.pg_is_in_recovery() AS in_recovery,
(SELECT rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=current_user) AS bypass_rls,
(SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user) AS superuser""",
    'schemas': f"""SELECT n.oid::bigint AS oid, n.nspname AS schema_name,
pg_catalog.has_schema_privilege(n.oid, 'USAGE') AS schema_usage
FROM pg_catalog.pg_namespace n WHERE {SCOPE} ORDER BY n.nspname""",
    'relations': RELATIONS,
    'columns': f"""SELECT n.nspname AS schema_name, c.relname AS table_name,
a.attnum AS ordinal, a.attname AS column_name, a.atttypid::bigint AS type_oid,
tn.nspname AS type_schema, t.typname AS type_name, t.typtype AS type_kind,
pg_catalog.format_type(a.atttypid,a.atttypmod) AS formatted_type,
a.atttypmod, a.attndims, a.attnotnull AS not_null, a.attidentity,
to_jsonb(a)->>'attgenerated' AS generated_kind,
pg_catalog.pg_get_expr(d.adbin,d.adrelid) AS default_expression,
coll.collname AS collation_name, cn.nspname AS collation_schema,
pg_catalog.has_column_privilege(c.oid,a.attnum,'SELECT') AS column_select,
pg_catalog.col_description(c.oid,a.attnum) AS comment
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace
LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
LEFT JOIN pg_catalog.pg_collation coll ON coll.oid=a.attcollation
LEFT JOIN pg_catalog.pg_namespace cn ON cn.oid=coll.collnamespace
WHERE {SCOPE} AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped
ORDER BY n.nspname,c.relname,a.attnum""",
    'constraints': f"""SELECT n.nspname AS schema_name, c.relname AS table_name,
con.conname AS constraint_name, con.contype AS constraint_type,
con.condeferrable, con.condeferred, con.convalidated,
pg_catalog.pg_get_constraintdef(con.oid,true) AS definition,
ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(num,ord)
JOIN pg_catalog.pg_attribute a ON a.attrelid=con.conrelid AND a.attnum=k.num
ORDER BY k.ord) AS columns,
pn.nspname AS parent_schema, pc.relname AS parent_table,
ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(num,ord)
JOIN pg_catalog.pg_attribute a ON a.attrelid=con.confrelid AND a.attnum=k.num
ORDER BY k.ord) AS parent_columns,
con.contypid::bigint AS domain_type_oid
FROM pg_catalog.pg_constraint con JOIN pg_catalog.pg_namespace n ON n.oid=con.connamespace
LEFT JOIN pg_catalog.pg_class c ON c.oid=con.conrelid
LEFT JOIN pg_catalog.pg_class pc ON pc.oid=con.confrelid
LEFT JOIN pg_catalog.pg_namespace pn ON pn.oid=pc.relnamespace
WHERE {SCOPE} ORDER BY n.nspname,c.relname,con.conname""",
    'indexes': f"""SELECT n.nspname AS schema_name,c.relname AS table_name,
ic.relname AS index_name,i.indisunique,i.indisprimary,i.indisvalid,
pg_catalog.pg_get_indexdef(i.indexrelid) AS definition
FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class c ON c.oid=i.indrelid
JOIN pg_catalog.pg_class ic ON ic.oid=i.indexrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE {SCOPE}
ORDER BY n.nspname,c.relname,ic.relname""",
    'views': f"""SELECT n.nspname AS schema_name,c.relname AS table_name,c.relkind,
pg_catalog.pg_get_viewdef(c.oid,false) AS definition
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE {SCOPE} AND c.relkind IN ('v','m') ORDER BY n.nspname,c.relname""",
    'view_dependencies': f"""SELECT DISTINCT n.nspname AS schema_name,c.relname AS table_name,
pn.nspname AS parent_schema,pc.relname AS parent_table,d.refobjsubid AS parent_column_ordinal,
pc.relkind AS parent_kind
FROM pg_catalog.pg_rewrite rw JOIN pg_catalog.pg_class c ON c.oid=rw.ev_class
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
JOIN pg_catalog.pg_depend d ON d.classid='pg_catalog.pg_rewrite'::regclass AND d.objid=rw.oid
JOIN pg_catalog.pg_class pc ON d.refclassid='pg_catalog.pg_class'::regclass AND pc.oid=d.refobjid
JOIN pg_catalog.pg_namespace pn ON pn.oid=pc.relnamespace
WHERE {SCOPE} AND c.relkind IN ('v','m') AND pc.oid<>c.oid
ORDER BY 1,2,3,4,5""",
    'inheritance': f"""SELECT n.nspname AS schema_name,c.relname AS table_name,
pn.nspname AS parent_schema,pc.relname AS parent_table,
pg_catalog.pg_get_expr(c.relpartbound,c.oid) AS partition_bound
FROM pg_catalog.pg_inherits inh JOIN pg_catalog.pg_class c ON c.oid=inh.inhrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
JOIN pg_catalog.pg_class pc ON pc.oid=inh.inhparent
JOIN pg_catalog.pg_namespace pn ON pn.oid=pc.relnamespace
WHERE {SCOPE} ORDER BY 1,2,3,4""",
    'types': f"""SELECT t.oid::bigint AS oid,n.nspname AS schema_name,t.typname,
t.typtype,t.typcategory,t.typbasetype::bigint AS base_type_oid,t.typtypmod,
t.typelem::bigint AS element_type_oid,t.typarray::bigint AS array_type_oid,
t.typrelid::bigint AS composite_relation_oid,t.typnotnull,t.typdefault,
pg_catalog.format_type(t.typbasetype,t.typtypmod) AS base_type,
ARRAY(SELECT e.enumlabel FROM pg_catalog.pg_enum e WHERE e.enumtypid=t.oid
ORDER BY e.enumsortorder) AS enum_labels
FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace
WHERE {SCOPE} ORDER BY n.nspname,t.typname""",
    'row_security_policies': f"""SELECT n.nspname AS schema_name,c.relname AS table_name,
p.polname,p.polcmd,p.polpermissive,p.polroles::text AS role_oids,
pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using_expression,
pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check_expression
FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE {SCOPE} ORDER BY 1,2,3""",
    'extensions': """SELECT e.extname,e.extversion,n.nspname AS schema_name
FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace
ORDER BY e.extname""",
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def error_info(exc: Exception, password: str = '') -> dict:
    state = getattr(exc, 'pgcode', None)
    # 不保存异常SQL、连接串、DETAIL或上下文；主错误已经足够区分权限/超时/连接失败。
    diag = getattr(exc, 'diag', None)
    message = getattr(diag, 'message_primary', None) or type(exc).__name__
    if password:
        message = message.replace(password, '[REDACTED]')
    result = {'status': 'permission_denied' if state == '42501' else 'failed',
              'sqlstate': state, 'message': message}
    if not state:
        # libpq连接错误常无SQLSTATE，只归类，不把可能含连接信息的全文写出。
        text = str(exc).lower()
        categories = {
            'authentication_failed': ('password authentication failed', '密码验证失败', 'no password supplied'),
            'connection_refused': ('connection refused', '拒绝连接'),
            'connection_timeout': ('timeout expired', 'connection timed out', '超时'),
            'name_resolution_failed': ('could not translate host name',),
            'ssl_error': ('ssl error', 'certificate verify failed',),
        }
        result['failure_kind'] = next(
            (key for key, phrases in categories.items() if any(p in text for p in phrases)),
            'unclassified_connection_or_runtime_error',
        )
    return result


def query_section(conn, query: str, params: dict) -> dict:
    with conn.cursor() as cur:
        cur.execute('SAVEPOINT probe_section')
        try:
            cur.execute(query, params)
            keys = [x[0] for x in cur.description]
            rows = [dict(zip(keys, row)) for row in cur.fetchall()]
        except Exception as exc:
            failure = error_info(exc)
            cur.execute('ROLLBACK TO SAVEPOINT probe_section')
            cur.execute('RELEASE SAVEPOINT probe_section')
            return {**failure, 'rows': None}
        cur.execute('RELEASE SAVEPOINT probe_section')
        return {'status': 'ok', 'rows': rows}


def compare_dictionary(dictionary: dict, sections: dict) -> list[dict]:
    relations = sections.get('relations', {})
    columns = sections.get('columns', {})
    result = []
    for expected in dictionary['tables']:
        item = {'dictionary_table': expected['name'], 'sheet': expected.get('sheet'),
                'directory_row': expected.get('directory_row')}
        if relations.get('status') != 'ok':
            result.append({**item, 'status': 'catalog_unavailable', 'matches': None})
            continue
        matches = [r for r in relations['rows'] if r['table_name'] == expected['name']]
        if not matches:
            result.append({**item, 'status': 'not_found_in_selected_catalog', 'matches': []})
            continue
        details = []
        for rel in matches:
            fields = None if columns.get('status') != 'ok' else [
                f for f in columns['rows'] if f['schema_name'] == rel['schema_name']
                and f['table_name'] == rel['table_name']]
            actual = {f['column_name'] for f in fields} if fields is not None else None
            defined = {f['name'] for f in expected['fields']}
            comparable = actual is not None and expected.get('sheet_status', 'found') == 'found'
            can_read = rel['schema_usage'] and (rel['table_select'] or (
                fields is not None and bool(fields) and all(f['column_select'] for f in fields)))
            details.append({
                'schema': rel['schema_name'], 'table': rel['table_name'], 'kind': rel['relkind'],
                'access_status': ('no_schema_usage' if not rel['schema_usage'] else
                                  'select_privilege_present_not_executed' if can_read else
                                  'column_catalog_unavailable' if fields is None and not rel['table_select']
                                  else 'insufficient_select_privilege'),
                'row_security_active': rel['row_security_active'],
                'actual_field_count': None if fields is None else len(fields),
                'field_comparison_status': 'compared' if comparable else 'unavailable',
                'fields_not_in_dictionary': sorted(actual - defined) if comparable else None,
                'dictionary_fields_not_in_actual': sorted(defined - actual) if comparable else None,
            })
        result.append({**item, 'status': 'multiple_schemas' if len(matches)>1 else 'found',
                       'matches': details})
    return result


def verify(directory: Path) -> int:
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    entries = manifest['files']
    expected = {e['name'] for e in entries}
    if len(expected) != len(entries):
        raise ValueError('Duplicate manifest filenames')
    for entry in entries:
        name = entry['name']
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Unsafe manifest filename')
        path = directory / name
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed')
        raw = path.read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('File checksum mismatch: ' + name)
    if {p.name for p in directory.iterdir()} != expected | {'manifest.json'}:
        raise ValueError('Unexpected or missing file')
    print('VERIFY_OK (file integrity only; see manifest status for probe completeness)')
    return 0


def run(args, password: str) -> int:
    import psycopg2

    dictionary = json.loads(args.dictionary.read_text(encoding='utf-8'))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    output = args.output / ('source_schema_' + run_id)
    output.mkdir(parents=True, exist_ok=False)
    sections = {}
    connection_failure = None
    conn = None
    try:
        conn = psycopg2.connect(
            host=args.host, port=args.port, dbname=args.database, user=args.username,
            password=password, connect_timeout=15, sslmode=args.sslmode,
            application_name='medqc_schema_probe_readonly',
            options='-c default_transaction_read_only=on -c search_path=pg_catalog',
        )
        conn.set_client_encoding('UTF8')
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ', autocommit=False)
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('statement_timeout', %s, true)",
                        (str(args.statement_timeout * 1000),))
            cur.execute("SELECT set_config('lock_timeout','5000',true)")
            cur.execute("SELECT set_config('idle_in_transaction_session_timeout','120000',true)")
        for name, query in QUERIES.items():
            sections[name] = query_section(conn, query, {'schemas': args.schema or None})
            print(name + ': ' + sections[name]['status'], flush=True)
    except Exception as exc:
        connection_failure = error_info(exc, password)
    finally:
        if conn is not None:
            conn.close()  # 回滚；从不提交源库事务。
    for name in QUERIES:
        sections.setdefault(name, {'status': 'not_run', 'rows': None})
    comparison = compare_dictionary(dictionary, sections)
    write_json(output / 'dictionary.json', dictionary)
    write_json(output / 'dictionary-comparison.json', comparison)
    write_json(output / 'queries.json', QUERIES)
    for name, section in sections.items():
        write_json(output / (name + '.json'), section)
    complete = connection_failure is None and all(s['status']=='ok' for s in sections.values())
    files = [{'name': p.name, 'bytes': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(output.iterdir())]
    manifest = {
        'schema_version': 'medqc-source-schema-probe-v1', 'run_id': run_id,
        'status': 'complete' if complete else 'partial' if conn is not None else 'failed',
        'connection_failure': connection_failure,
        'connection_target': {'host': args.host, 'port': args.port, 'database': args.database,
                              'username': args.username, 'sslmode': args.sslmode},
        'requested_schemas': args.schema or ['ALL_NON_SYSTEM_SCHEMAS'],
        'dictionary_table_count': len(dictionary['tables']),
        'requested_schema_status': {
            schema: ('catalog_unavailable' if sections['schemas']['status'] != 'ok' else
                     'found' if any(row['schema_name'] == schema for row in sections['schemas']['rows'])
                     else 'not_found_in_catalog') for schema in (args.schema or [])
        },
        'sections': {name: {'status': s['status'],
                           'metadata_row_count': None if s['rows'] is None else len(s['rows'])}
                     for name, s in sections.items()},
        'business_rows_read': False, 'data_select_tested': False,
        'notes': [
            'Complete means catalog queries completed, not that all business tables are readable.',
            'not_found_in_selected_catalog is not a permission/connection failure or proof of global absence.',
            'No business SELECT, row counts, query plans or medical text were collected.',
            'Snapshot applies to local PostgreSQL catalogs; FDW/view data consistency is not certified.',
            'Catalog JSON is discovery evidence, not an executable restore schema.',
        ], 'files': files,
    }
    write_json(output / 'manifest.json', manifest)
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as package:
        for path in sorted(output.iterdir()):
            package.write(path, arcname=output.name + '/' + path.name)
    print(('PROBE_COMPLETE' if complete else 'PROBE_INCOMPLETE') + ': ' + str(archive), flush=True)
    return 0 if complete else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path, help='Verify an extracted probe folder without connecting')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int, default=5432)
    parser.add_argument('--database')
    parser.add_argument('--username')
    parser.add_argument('--schema', action='append')
    parser.add_argument('--sslmode', choices=['disable','allow','prefer','require','verify-ca','verify-full'], default='prefer')
    parser.add_argument('--statement-timeout', type=int, default=60)
    parser.add_argument('--output', type=Path, default=Path(r'D:\medqc\source_schema_probe'))
    parser.add_argument('--dictionary', type=Path, default=Path(__file__).with_name('cdm_dictionary.json'))
    args = parser.parse_args()
    if args.verify:
        return verify(args.verify)
    if not all([args.host, args.database, args.username]) or args.statement_timeout < 1:
        parser.error('host, database, username and a positive statement-timeout are required')
    # 若控制台不能关闭回显，拒绝降级成可见密码输入。
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Source database password (hidden): ')
    if not password:
        raise ValueError('Empty password not accepted; no credential-file fallback')
    try:
        return run(args, password)
    finally:
        password = ''


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('PROBE_ABORTED: incomplete output must not be used as a successful probe.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print('PROBE_FAILED: ' + type(exc).__name__ + '; check prerequisites/output permissions.', file=sys.stderr)
        sys.exit(1)
