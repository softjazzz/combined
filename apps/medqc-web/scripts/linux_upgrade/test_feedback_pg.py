"""仅显式指定的一次性隔离PG；不读取.env、不执行应用startup或模型。"""
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

TOOLS=Path(__file__).parent
BACKEND=TOOLS.parents[1]/'backend'
sys.path.insert(0,str(TOOLS)); sys.path.insert(0,str(BACKEND))
from feedback_pg import migrate
from feedback_upgrade import snapshot_sqlite, compatible_release, file_manifest
from app.models.demo import Feedback


@pytest.fixture
def pg(monkeypatch):
    url=os.environ.get('MEDQC_SYNTHETIC_FEEDBACK_PG_URL','')
    parsed=sa.engine.make_url(url)
    assert parsed.host=='127.0.0.1' and parsed.port==55487 and parsed.username=='feedback_test' and parsed.database=='medqc_business'
    monkeypatch.setenv('DATABASE_URL',url)
    monkeypatch.setenv('DB_SCHEMA_MODE','split')
    engine=sa.create_engine(url)
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT current_setting('data_directory')")).scalar_one().replace('\\','/').endswith('/medqc-feedback-pg-isolated-20261112/data')
        conn.execute(sa.text('DROP SCHEMA IF EXISTS qc CASCADE'))
        conn.execute(sa.text('CREATE SCHEMA qc'))
        conn.execute(sa.text('CREATE TABLE IF NOT EXISTS public.alembic_version (version_num varchar(32) primary key)'))
        conn.execute(sa.text('DELETE FROM public.alembic_version'))
        conn.execute(sa.text("INSERT INTO public.alembic_version VALUES ('20261106_000064')"))
        conn.execute(sa.text('CREATE TABLE qc.qc_appeals (sentinel text)'))
        conn.execute(sa.text("INSERT INTO qc.qc_appeals VALUES ('doctor-feedback-unchanged')"))
    yield engine,{'DATABASE_URL':url}
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT sentinel FROM qc.qc_appeals')).scalar_one()=='doctor-feedback-unchanged'
    engine.dispose()


def legacy(path, ids=('old-1',),wal=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    if wal: db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA wal_autocheckpoint=0')
    columns=[c.name for c in Feedback.__table__.columns]
    db.execute('CREATE TABLE feedbacks ('+','.join('"'+c+'" '+('INTEGER' if c=='evaluation_result' else 'TEXT') for c in columns)+')')
    for id_ in ids:
        values={k:None for k in columns}
        values.update(feedback_id=id_,rule_id='R',rule_code='R',rule_name='合成规则',document_name='合成文书',evaluation_result=0,feedback_type='incorrect',created_at='2026-11-12 01:00:00.000000',evidence='合成反馈')
        db.execute('INSERT INTO feedbacks VALUES ('+','.join('?' for _ in columns)+')',[values[c] for c in columns])
    db.commit()
    return db


def test_migration_import_crud_idempotency_and_compatible_rollback(pg,tmp_path,monkeypatch):
    engine,env=pg
    old=tmp_path/'old'; raw=old/'backend/data/demo_feedbacks.db'
    db=legacy(raw,wal=True)
    try:
        snapshot,original,source_id=snapshot_sqlite(old,tmp_path/'backup')
        from feedback_upgrade import digest
        assert original=={name:digest(raw.parent/name) for name in original}
        result=migrate(BACKEND,env,snapshot,source_id)
        assert result['inserted']==1
        assert migrate(BACKEND,env,snapshot,source_id)['skipped']==1
        from app.database import connection
        monkeypatch.setattr(connection,'engine',engine)
        monkeypatch.setattr(connection,'SessionLocal',sessionmaker(bind=engine))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.demo import router
        app=FastAPI(); app.include_router(router)
        with TestClient(app) as client:
            payload=dict(rule_id='R',rule_code='R',rule_name='合成规则',document_name='合成文书',evaluation_result=True,feedback_type='correct')
            response=client.post('/api/v1/demo/feedbacks',json=payload)
            assert response.status_code==200,response.text
            assert client.get('/api/v1/demo/feedbacks').json()['total']==2
            assert client.get('/api/v1/demo/feedbacks/stats').status_code==200
            assert client.get('/api/v1/demo/feedbacks/by-rule/R').status_code==200
            assert client.get('/api/v1/demo/feedbacks/export').status_code==200
            assert client.delete('/api/v1/demo/feedbacks/old-1').status_code==200
            assert migrate(BACKEND,env,snapshot,source_id)['skipped']==1
            assert client.get('/api/v1/demo/feedbacks').json()['total']==1
        # 真正载入兼容回滚副本的模型，读取升级后新增PG反馈。
        kit=tmp_path/'kit'; (kit/'application').mkdir(parents=True)
        import shutil
        (old/'backend/app/models').mkdir(parents=True)
        if os.name=='nt':
            # Windows无创建symlink权限；Linux文件系统切换另有独立工具验证。
            monkeypatch.setattr(Path,'symlink_to',lambda self,target,**kw:self.write_text(str(target)))
        from feedback_upgrade import OVERLAYS
        for relative in OVERLAYS:
            target=kit/'application/backend'/relative; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(BACKEND/relative,target)
        root=tmp_path/'root'; (root/'releases').mkdir(parents=True)
        rollback,manifest=compatible_release(kit,root,old,{'build_id':'synthetic'})
        assert file_manifest(rollback)==manifest
        spec=importlib.util.spec_from_file_location('rollback_demo',rollback/'backend/app/models/demo.py')
        model=importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
        with sessionmaker(bind=engine)() as session:
            rows=session.query(model.Feedback).all()
            assert len(rows)==1 and rows[0].feedback_type=='correct'
        assert original=={name:digest(raw.parent/name) for name in original}
    finally: db.close()


def test_conflict_rolls_back_whole_import_and_revision(pg,tmp_path):
    engine,env=pg
    path=tmp_path/'old.db'; db=legacy(path,('a','b')); db.close()
    # 第二行不合法：先插入的第一行和065 DDL必须一并回滚。
    with sqlite3.connect(path) as db: db.execute("UPDATE feedbacks SET rule_id=NULL WHERE feedback_id='b'")
    with pytest.raises(ValueError,match='required_field'): migrate(BACKEND,env,path,'test-source')
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT version_num FROM public.alembic_version')).scalar_one()=='20261106_000064'
        assert not sa.inspect(conn).has_table('demo_feedbacks',schema='qc')


def test_existing_id_conflict_and_edited_import_preserved(pg,tmp_path):
    engine,env=pg
    path=tmp_path/'old.db'; legacy(path).close()
    migrate(BACKEND,env,path,'source')
    with engine.begin() as conn: conn.execute(Feedback.__table__.update().values(evidence='reviewed'))
    assert migrate(BACKEND,env,path,'source')['skipped']==1
    with engine.connect() as conn: assert conn.execute(sa.select(Feedback.evidence)).scalar_one()=='reviewed'
    with pytest.raises(ValueError,match='source_conflict'): migrate(BACKEND,env,path,'different-source')


def test_no_sqlite_runtime_fallback(monkeypatch):
    from app.database import connection,demo_db
    monkeypatch.setattr(connection,'engine',sa.create_engine('sqlite://'))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error: next(demo_db.get_db())
    assert error.value.status_code==503


def test_new_install_and_preexisting_pg_identity_conflict(pg,tmp_path):
    engine,env=pg
    assert migrate(BACKEND,env,None,'no-legacy')['total']==0
    path=tmp_path/'legacy.db'; legacy(path).close()
    with engine.begin() as conn:
        conn.execute(Feedback.__table__.insert().values(feedback_id='old-1',rule_id='different',rule_code='R',
                     rule_name='合成',document_name='合成',evaluation_result=True,feedback_type='correct'))
    with pytest.raises(ValueError,match='id_conflict'): migrate(BACKEND,env,path,'source')
    with engine.connect() as conn:
        assert conn.execute(sa.select(Feedback.rule_id)).scalar_one()=='different'
        assert conn.execute(sa.text('SELECT count(*) FROM qc.demo_feedback_imports')).scalar_one()==0
