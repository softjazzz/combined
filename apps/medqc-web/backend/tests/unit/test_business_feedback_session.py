"""反馈专用会话隔离；仅使用内存 SQLite，不连接共享库。"""
from uuid import uuid4

from fastapi import FastAPI
import pytest
import sqlalchemy as sa

from app.services.qc_agent.business_feedback import FeedbackSubmit, feedback_table, get_feedback_store
from tests.manual import business_feedback_session as support


SETTINGS = {"DATABASE_URL": "postgresql+psycopg2://unused/unused", "DB_SCHEMA_MODE": "single"}


@pytest.mark.parametrize("enabled", ["0", "", "true", "yes"])
def test_default_closed_creates_no_engine(monkeypatch, enabled):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("关闭时不得创建连接")
    monkeypatch.setattr(support.sa, "create_engine", forbidden)
    app = FastAPI()
    assert support.install_feedback_override(app, {}, enabled=enabled) is None
    assert not app.dependency_overrides
    assert support.install_feedback_override(app, {}) is None


def configured(monkeypatch):
    engine = sa.create_engine("sqlite://")
    # 准备合成固定表；安装保护后不可执行DDL。
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
        feedback_table("public").create(conn)
    monkeypatch.setattr(support.sa, "create_engine", lambda *_args, **_kwargs: engine)
    app = FastAPI()
    assert support.install_feedback_override(app, SETTINGS, enabled="1") is engine
    assert list(app.dependency_overrides) == [get_feedback_store]
    return engine, app.dependency_overrides[get_feedback_store]()


def test_fixed_table_submit_idempotent_and_other_sql_blocked(monkeypatch):
    engine, store = configured(monkeypatch)
    target = dict(reference_id="r", institute_id="h", patient_id="p", visit_id="v", root_job_id="j", record_ref="d", rule_id="q", original_status="non_compliant")
    payload = FeedbackSubmit(reference_id="r", comment="联调验收", request_id=uuid4())
    first = store.submit(uid="existing-user", session_id="s", target=target, payload=payload)
    assert store.submit(uid="existing-user", session_id="s", target=target, payload=payload) == first
    assert store.read(uid="existing-user", session_id="s", reference_id="r") == first
    other = sa.Table("other", sa.MetaData(), sa.Column("id", sa.Integer), schema="public")
    for statement in (sa.text("SELECT 1"), sa.select(other), store.table.delete(), store.table.update().values(comment="改变")):
        with engine.connect() as conn, pytest.raises(RuntimeError):
            conn.execute(statement)
    engine.dispose()


def test_main_readonly_listener_is_never_modified(monkeypatch):
    main = sa.create_engine("sqlite://")
    calls = []
    def readonly(connection, _record):
        calls.append("readonly")
        connection.execute("PRAGMA query_only=ON")
    sa.event.listen(main, "connect", readonly)
    engine, _store = configured(monkeypatch)
    assert engine is not main
    assert sa.event.contains(main, "connect", readonly)
    with main.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
        with pytest.raises(sa.exc.OperationalError):
            conn.exec_driver_sql("CREATE TABLE unauthorized(id INTEGER)")
    assert calls == ["readonly"]
    main.dispose()
    engine.dispose()


@pytest.mark.parametrize("settings", [{}, {"DATABASE_URL": "sqlite://"}, {**SETTINGS, "DB_SCHEMA_MODE": "invalid"}])
def test_invalid_config_rejected_without_dependency_override(settings):
    app = FastAPI()
    with pytest.raises(RuntimeError):
        support.install_feedback_override(app, settings, enabled="1")
    assert not app.dependency_overrides
