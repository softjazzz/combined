import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.supabase_client import _Query


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE qc_defects (id TEXT PRIMARY KEY, source_key TEXT, flag INTEGER)"))
        connection.execute(
            text("INSERT INTO qc_defects (id, source_key, flag) VALUES (:id, :source_key, 0)"),
            [
                {"id": "legacy-null", "source_key": None},
                {"id": "legacy-other", "source_key": "rule_engine"},
                {"id": "task-manual", "source_key": "task_assigned_qc"},
            ],
        )
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_neq_or_null_select_and_count_preserve_legacy_null(session_factory):
    result = (
        _Query(session_factory, "qc_defects")
        .select("id", count="exact")
        .neq_or_null("source_key", "task_assigned_qc")
        .order("id")
        .execute()
    )

    assert [row["id"] for row in result.data] == ["legacy-null", "legacy-other"]
    assert result.count == 2


def test_neq_or_null_update_only_legacy_rows(session_factory):
    updated = (
        _Query(session_factory, "qc_defects")
        .update({"flag": 1})
        .neq_or_null("source_key", "task_assigned_qc")
        .execute()
    )

    assert {row["id"] for row in updated.data} == {"legacy-null", "legacy-other"}
    rows = _Query(session_factory, "qc_defects").select("id,flag").execute().data
    assert {row["id"]: row["flag"] for row in rows} == {
        "legacy-null": 1,
        "legacy-other": 1,
        "task-manual": 0,
    }


def test_neq_or_null_binds_value_and_validates_identifier():
    query = _Query(None, "qc_defects").select("id").neq_or_null(
        "source_key", "task_assigned_qc' OR 1=1 --"
    )
    sql, params = query._build_select_sql()

    assert '"source_key" IS NULL OR "source_key" != :p0' in sql
    assert params == {"p0": "task_assigned_qc' OR 1=1 --"}

    with pytest.raises(ValueError, match="invalid_database_identifier"):
        _Query(None, "qc_defects").neq_or_null("source_key\" OR 1=1 --", "x")._build_count_sql()
