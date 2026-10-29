"""克隆迁移入口须复用已校验连接，不能写入原始验收库。"""

from __future__ import annotations

import getpass
import os
import runpy
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import upgrade_daily_record_time_clone as upgrade


@pytest.mark.parametrize("database", [
    "medqc", "medqc_cache_poc", "medqc_bundle_acceptance", "postgres",
    "medqc_bundle_time_clone_20261029", "medqc_bundle_time_clone_20261029123456;DROP",
])
def test_non_clone_names_rejected_before_prompt_or_connection(monkeypatch, capsys, database):
    prompt = Mock(side_effect=AssertionError("must not prompt"))
    monkeypatch.setattr("builtins.input", prompt)
    assert upgrade.main(["--database", database]) == 1
    prompt.assert_not_called()
    assert '"step": "scope"' in capsys.readouterr().out


def test_process_environment_restored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "synthetic-original-url")
    with upgrade.migration_environment():
        assert os.environ["DATABASE_URL"] == ""
        assert os.environ["DB_SCHEMA_MODE"] == "split"
    assert os.environ["DATABASE_URL"] == "synthetic-original-url"


def test_connected_database_is_checked_before_any_ddl():
    connection = Mock()
    connection.execute.return_value.scalar_one.return_value = "medqc_bundle_acceptance"
    engine = SimpleNamespace(begin=lambda: nullcontext(connection))
    with pytest.raises(ValueError, match="connected_database_mismatch"):
        upgrade.upgrade_clone(engine, "medqc_bundle_time_clone_20261029123456")
    assert connection.execute.call_count == 1


def test_alembic_environment_reuses_only_supplied_connection(monkeypatch):
    import sqlalchemy as sa
    from alembic import context
    from alembic.config import Config

    connection = Mock()
    config = Config()
    config.attributes["connection"] = connection
    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    configure = Mock()
    run = Mock()
    monkeypatch.setattr(context, "configure", configure)
    monkeypatch.setattr(context, "run_migrations", run)
    monkeypatch.setattr(context, "begin_transaction", lambda: nullcontext())
    forbidden = Mock(side_effect=AssertionError("must reuse supplied connection"))
    monkeypatch.setattr(sa, "engine_from_config", forbidden)
    with upgrade.migration_environment():
        runpy.run_path(str(upgrade.BACKEND / "alembic/env.py"))
    assert configure.call_args.kwargs["connection"] is connection
    run.assert_called_once()
    forbidden.assert_not_called()


def test_connection_failure_never_prints_raw_error_or_password(monkeypatch, capsys):
    import sqlalchemy as sa

    monkeypatch.setattr("builtins.input", lambda _: "synthetic-deployer")
    monkeypatch.setattr(getpass, "getpass", lambda _: "synthetic-secret-marker")
    engine = Mock()
    monkeypatch.setattr(sa, "create_engine", lambda *_, **__: engine)
    monkeypatch.setattr(
        upgrade, "upgrade_clone",
        Mock(side_effect=RuntimeError("synthetic-secret-marker private-body-marker")),
    )
    assert upgrade.main(["--database", "medqc_bundle_time_clone_20261029123456"]) == 1
    output = capsys.readouterr().out
    assert "synthetic-secret-marker" not in output and "private-body-marker" not in output
    assert "RuntimeError" in output
    engine.dispose.assert_called_once()
