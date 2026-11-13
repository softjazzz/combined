"""演示反馈使用业务PG独立表；导入模块不建表、不读取SQLite。"""
from contextlib import contextmanager
from fastapi import HTTPException
from . import connection


def _session():
    engine = connection.engine
    if engine is None or engine.dialect.name != "postgresql" or connection.SessionLocal is None:
        raise HTTPException(503, "demo_feedback_business_postgresql_required")
    return connection.SessionLocal()


def get_db():
    db = _session()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = _session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
