"""Startup schema writes are allowed only in legacy single-schema mode."""

from unittest.mock import Mock

import pytest

from app.database import connection


@pytest.mark.parametrize(
    ("schema_mode", "expected_calls"),
    [
        ("split", (0, 0, 0)),
        ("single", (1, 1, 1)),
    ],
)
def test_init_db_schema_writes_follow_mode(
    monkeypatch: pytest.MonkeyPatch,
    schema_mode: str,
    expected_calls: tuple[int, int, int],
) -> None:
    engine = object()
    create_all = Mock()
    sync_columns = Mock()
    create_views = Mock(return_value=([], []))
    monkeypatch.setattr(connection, "engine", engine)
    monkeypatch.setattr(connection, "DB_SCHEMA_MODE", schema_mode)
    monkeypatch.setattr(connection.Base.metadata, "create_all", create_all)
    monkeypatch.setattr(connection, "_sync_missing_columns", sync_columns)
    monkeypatch.setattr(connection, "_create_views", create_views)

    connection.init_db()

    assert (
        create_all.call_count,
        sync_columns.call_count,
        create_views.call_count,
    ) == expected_calls
    if schema_mode == "single":
        create_all.assert_called_once_with(bind=engine)


def test_init_db_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection, "engine", None)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        connection.init_db()
