"""旧演示SQLite只读导入业务PG。调用方拥有单一事务；不输出反馈正文。"""
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sqlalchemy as sa
from ..models.demo import Feedback

imports = sa.Table(
    'demo_feedback_imports', Feedback.metadata,
    sa.Column('feedback_id', sa.String(36), primary_key=True),
    sa.Column('source_digest', sa.String(64), nullable=False),
    sa.Column('row_digest', sa.String(64), nullable=False),
    schema='qc',
)


def create_tables(connection):
    if connection.dialect.name != 'postgresql': raise ValueError('business_postgresql_required')
    Feedback.__table__.create(connection, checkfirst=False)
    imports.create(connection, checkfirst=False)


def normalized(row):
    item = dict(row)
    if item['evaluation_result'] not in (0, 1): raise ValueError('legacy_feedback_boolean_invalid')
    item['evaluation_result'] = bool(item['evaluation_result'])
    if item['created_at'] is not None:
        item['created_at'] = datetime.fromisoformat(item['created_at'])
        if item['created_at'].tzinfo is not None: raise ValueError('legacy_feedback_timezone_unconfirmed')
    for col in Feedback.__table__.columns:
        value=item[col.name]
        if value is None and not col.nullable: raise ValueError('legacy_feedback_required_field_missing')
        if isinstance(col.type,sa.String) and value is not None:
            if not isinstance(value,str) or (col.type.length and len(value)>col.type.length):
                raise ValueError('legacy_feedback_text_contract_invalid')
    if not item['feedback_id']: raise ValueError('legacy_feedback_identity_missing')
    return item


def row_digest(row):
    return hashlib.sha256(json.dumps(dict(row),sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def import_rows(connection, sqlite_file: Path, source_digest: str):
    if connection.dialect.name != 'postgresql': raise ValueError('business_postgresql_required')
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(12012026, 65)'))
    sqlite_file=sqlite_file.resolve(strict=True)
    columns=[c.name for c in Feedback.__table__.columns]
    inserted=skipped=0
    with closing(sqlite3.connect(sqlite_file.as_uri()+'?mode=ro',uri=True)) as old:
        old.execute('PRAGMA query_only=ON'); old.row_factory=sqlite3.Row
        if old.execute('PRAGMA quick_check').fetchall()[0][0]!='ok': raise ValueError('legacy_feedback_integrity_failed')
        actual={r[1] for r in old.execute('PRAGMA table_info(feedbacks)')}
        if actual!=set(columns): raise ValueError('legacy_feedback_schema_mismatch')
        if old.execute('SELECT feedback_id FROM feedbacks GROUP BY feedback_id HAVING count(*)>1 LIMIT 1').fetchone():
            raise ValueError('legacy_feedback_duplicate_identity')
        for raw in old.execute('SELECT '+','.join('"'+c+'"' for c in columns)+' FROM feedbacks ORDER BY feedback_id'):
            item=normalized(raw); digest=row_digest(item)
            prior=connection.execute(sa.select(imports).where(imports.c.feedback_id==item['feedback_id'])).mappings().first()
            if prior:
                if prior['source_digest']!=source_digest or prior['row_digest']!=digest:
                    raise ValueError('feedback_import_source_conflict')
                skipped+=1; continue
            existing=connection.execute(sa.select(Feedback.__table__).where(Feedback.feedback_id==item['feedback_id'])).mappings().first()
            if existing is not None and row_digest(existing)!=digest: raise ValueError('feedback_import_id_conflict')
            if existing is None:
                connection.execute(Feedback.__table__.insert().values(**item)); inserted+=1
            else: skipped+=1
            connection.execute(imports.insert().values(feedback_id=item['feedback_id'],source_digest=source_digest,row_digest=digest))
    return {'inserted':inserted,'skipped':skipped,'total':inserted+skipped}
