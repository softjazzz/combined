"""Explicitly opted-in, read-only metadata check; never imports app.main/connection."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys


def contract(backend):
    # Read exact constants and owner-selection function without importing auth
    # storage, ORM models, the application, or its connection module.
    auth = ast.parse((backend / 'app/services/auth_store.py').read_text(encoding='utf-8'))
    required = next(ast.literal_eval(n.value) for n in auth.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_REQUIRED_AUTH_COLUMNS' for t in n.targets))
    owner = ast.parse((backend / 'app/services/user_scope_owner.py').read_text(encoding='utf-8'))
    fn = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'select_user_owner_schema')
    scope = {'UserOwnerUnavailable': RuntimeError, 'USER_SCHEMAS': ('sys', 'public')}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<exact owner contract>', 'exec'), scope)
    module = ast.parse((backend / 'app/core/server_startup.py').read_text(encoding='utf-8'))
    tables = next(ast.literal_eval(n.iter) for n in ast.walk(module) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'table')
    spec = importlib.util.spec_from_file_location('readonly_refresh_contract', backend / 'app/services/bundles/refresh_storage.py')
    refresh = importlib.util.module_from_spec(spec); spec.loader.exec_module(refresh)
    return required, tables, scope['select_user_owner_schema'], refresh


def check(backend, env, revision='20261106_000064'):
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    url = make_url(env.get('DATABASE_URL', ''))
    if url.drivername not in ('postgresql', 'postgresql+psycopg2') or url.database != 'medqc_business' or url.query:
        raise ValueError('explicit_business_postgresql_without_url_overrides_required')
    path = env.get('DB_SEARCH_PATH', '').strip() or ('public,qc,sys,cdm,legacy' if env.get('DB_SCHEMA_MODE') == 'split' else '')
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_,' for c in path):
        raise ValueError('unsupported_search_path')
    required, tables, choose_owner, refresh = contract(backend)
    options = '-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=3000'
    if path: options += ' -c search_path=' + path
    engine = sa.create_engine(url, echo=False, hide_parameters=True, poolclass=sa.pool.NullPool, connect_args={'options': options, 'connect_timeout': 5})
    @sa.event.listens_for(engine, 'before_cursor_execute')
    def guard(conn, cursor, statement, parameters, context, many):
        sql = statement.strip().upper()
        if not (sql.startswith('SELECT ') or sql.startswith('SHOW ') or sql == 'SET TRANSACTION READ ONLY'):
            raise ValueError('non_readonly_statement_rejected')
    try:
        with engine.connect() as conn:
            conn.execute(sa.text('SET TRANSACTION READ ONLY'))
            try:
                if conn.execute(sa.text('SHOW transaction_read_only')).scalar_one() != 'on': raise ValueError('readonly_not_effective')
                if conn.execute(sa.text('SELECT current_database()')).scalar_one() != 'medqc_business': raise ValueError('wrong_database')
                if revision not in ('20261106_000064','20261112_000065'):
                    raise ValueError('unsupported_revision')
                if conn.execute(sa.text('SELECT version_num FROM public.alembic_version')).scalars().all() != [revision]:
                    raise ValueError('public_alembic_revision_mismatch')
                refresh.bind_storage(conn)
                inspector = sa.inspect(conn)
                if revision == '20261112_000065':
                    for name in ('demo_feedbacks','demo_feedback_imports'):
                        if not inspector.has_table(name,schema='qc'):
                            raise ValueError('feedback_pg_tables_missing')
                for table in tables:
                    if not inspector.has_table(table, schema='qc'): raise ValueError('required_qc_table_missing')
                owner = choose_owner(search_path=path.split(',') if path else [], schemas_with_user_table=[s for s in ('sys','public') if inspector.has_table('sys_users', schema=s)])
                columns = {c['name'] for c in inspector.get_columns('sys_users', schema=owner)}
                if not required | {'institute_id'} <= columns: raise ValueError('auth_columns_missing')
            finally: conn.rollback()
    finally: engine.dispose()
    return {'ok': True, 'revision': revision, 'revision_schema': 'public', 'business_schema': 'qc', 'transaction_read_only': True, 'clinical_rows_read': 0}


if __name__ == '__main__':
    if sys.argv[1:] != ['--allow-readonly-db']:
        print('{"ok":false,"error":"explicit_readonly_connection_opt_in_required"}'); raise SystemExit(2)
    try:
        result = check(Path(__file__).parent / 'application/backend', dict(os.environ))
    except Exception:
        # Driver messages can contain DSNs/parameters; never print exception text.
        result = {'ok': False, 'error': 'readonly_schema_preflight_failed; no_switch; inspect_metadata_in_approved_channel'}
    print(json.dumps(result)); raise SystemExit(0 if result['ok'] else 1)
