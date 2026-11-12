"""演示反馈迁移子进程；仅显式授权后写业务PG，绝不读现场SQLite原文件。"""
import argparse
import json
import os
from pathlib import Path
import sys


def migrate(backend, env, snapshot, source_digest):
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from alembic.config import Config
    from alembic import command
    url=make_url(env.get('DATABASE_URL',''))
    if url.drivername not in ('postgresql','postgresql+psycopg2') or url.database!='medqc_business' or url.query:
        raise ValueError('business_postgresql_required')
    sys.path.insert(0,str(backend))
    from app.database.demo_feedback_transfer import import_rows
    engine=sa.create_engine(url,hide_parameters=True,poolclass=sa.pool.NullPool,
                            connect_args={'connect_timeout':5,'options':'-c statement_timeout=60000 -c lock_timeout=3000'})
    try:
        with engine.begin() as conn:
            conn.execute(sa.text('SELECT pg_advisory_xact_lock(12012026,65)'))
            revision=conn.execute(sa.text('SELECT version_num FROM public.alembic_version')).scalars().all()
            if revision not in (['20261106_000064'],['20261112_000065']):
                raise ValueError('migration_baseline_mismatch')
            config=Config()
            config.set_main_option('script_location',str(backend/'alembic'))
            config.attributes['connection']=conn
            command.upgrade(config,'20261112_000065')
            result=import_rows(conn,snapshot,source_digest) if snapshot else {'inserted':0,'skipped':0,'total':0}
        return {'ok':True,'revision':'20261112_000065',**result}
    finally:
        engine.dispose()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true'); p.add_argument('--snapshot',type=Path)
    p.add_argument('--source-digest',required=True)
    a=p.parse_args()
    if not a.execute: p.error('explicit_execute_required')
    try:
        result=migrate(Path(__file__).parent/'application/backend',dict(os.environ),a.snapshot,a.source_digest)
    except Exception:
        result={'ok':False,'error':'feedback_migration_failed_transaction_rolled_back'}
    print(json.dumps(result)); raise SystemExit(0 if result['ok'] else 1)
