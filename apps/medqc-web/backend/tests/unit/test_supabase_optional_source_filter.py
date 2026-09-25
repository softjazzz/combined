import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.supabase_client import _Query


@pytest.fixture(params=[False, True], ids=["legacy_without_source", "with_source"])
def database(request):
    has_source = request.param
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as connection:
        source_column = ", source_key TEXT" if has_source else ""
        connection.execute(
            text(f"CREATE TABLE qc_defects (id TEXT PRIMARY KEY, flag INTEGER{source_column})")
        )
        if has_source:
            connection.execute(
                text("INSERT INTO qc_defects (id, flag, source_key) VALUES (:id, 0, :source_key)"),
                [
                    {"id": "legacy-null", "source_key": None},
                    {"id": "legacy-other", "source_key": "rule_engine"},
                    {"id": "task-manual", "source_key": "task_assigned_qc"},
                ],
            )
        else:
            connection.execute(
                text("INSERT INTO qc_defects (id, flag) VALUES (:id, 0)"),
                [{"id": name} for name in ("legacy-null", "legacy-other", "task-manual")],
            )
    yield sessionmaker(bind=engine), has_source
    engine.dispose()


def test_select_and_count_skip_only_present_manual_source(database):
    session_factory, has_source = database
    result = (
        _Query(session_factory, "qc_defects")
        .select("id", count="exact")
        .exclude_task_manual_source()
        .order("id")
        .execute()
    )

    expected = ["legacy-null", "legacy-other"]
    if not has_source:
        expected.append("task-manual")
    assert [row["id"] for row in result.data] == expected
    assert result.count == len(expected)


def test_update_skips_only_present_manual_source(database):
    session_factory, has_source = database
    updated = (
        _Query(session_factory, "qc_defects")
        .update({"flag": 1})
        .exclude_task_manual_source()
        .execute()
    )

    expected = {"legacy-null", "legacy-other"}
    if not has_source:
        expected.add("task-manual")
    assert {row["id"] for row in updated.data} == expected
    rows = _Query(session_factory, "qc_defects").select("id,flag").execute().data
    assert {row["id"]: row["flag"] for row in rows} == {
        "legacy-null": 1,
        "legacy-other": 1,
        "task-manual": 0 if has_source else 1,
    }


def test_filter_is_fixed_and_rejects_other_tables(database):
    session_factory, has_source = database
    query = _Query(session_factory, "qc_defects").select("id").exclude_task_manual_source()
    with session_factory() as session:
        sql, params = query._build_select_sql(query._effective_filters(session))
    if has_source:
        assert '"source_key" IS NULL OR "source_key" != :p0' in sql
        assert params == {"p0": "task_assigned_qc"}
    else:
        assert "source_key" not in sql
        assert params == {}

    for table in ("qc_rules", "qc.qc_defects", 'qc_defects" OR 1=1 --'):
        with pytest.raises(ValueError, match="task_manual_source_filter_requires_qc_defects"):
            _Query(None, table).exclude_task_manual_source()


def test_connection_failure_is_not_treated_as_missing_column():
    def unavailable_database():
        raise RuntimeError("database_unavailable")

    query = (
        _Query(unavailable_database, "qc_defects")
        .select("id")
        .exclude_task_manual_source()
    )
    with pytest.raises(RuntimeError, match="database_unavailable"):
        query.execute()


def test_column_probe_failure_is_not_treated_as_missing_column(database):
    session_factory, _ = database
    engine = session_factory.kw["bind"]

    def fail_probe(connection, cursor, statement, parameters, context, executemany):
        if 'SELECT * FROM "qc_defects" LIMIT 0' in statement:
            raise RuntimeError("column_probe_failed")

    event.listen(engine, "before_cursor_execute", fail_probe)
    try:
        query = (
            _Query(session_factory, "qc_defects")
            .select("id")
            .exclude_task_manual_source()
        )
        with pytest.raises(RuntimeError, match="column_probe_failed"):
            query.execute()
    finally:
        event.remove(engine, "before_cursor_execute", fail_probe)


def test_same_query_detects_hot_added_column_without_stale_cache():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE qc_defects (id TEXT PRIMARY KEY)"))
        connection.execute(
            text("INSERT INTO qc_defects (id) VALUES (:id)"),
            [{"id": name} for name in ("legacy-null", "legacy-other", "task-manual")],
        )
    session_factory = sessionmaker(bind=engine)
    query = (
        _Query(session_factory, "qc_defects")
        .select("id", count="exact")
        .exclude_task_manual_source()
        .order("id")
    )
    assert query.execute().count == 3

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE qc_defects ADD COLUMN source_key TEXT"))
        connection.execute(
            text("UPDATE qc_defects SET source_key = 'task_assigned_qc' WHERE id = 'task-manual'")
        )

    result = query.execute()
    assert result.count == 2
    assert [row["id"] for row in result.data] == ["legacy-null", "legacy-other"]
    engine.dispose()
