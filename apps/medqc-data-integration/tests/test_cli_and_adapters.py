from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from medqc_ingest import cli
from medqc_ingest.adapters.cache import JdbcSourceAdapter, OdbcSourceAdapter
from medqc_ingest.config import SourceSettings
from medqc_ingest.domain import IngestError, resolve_interface


class FakeDriverCursor:
    description = (("institute_id",), ("patient_id",), ("visit_id",))

    def execute(self, sql: str, params: Any) -> None:
        assert "web.mr" in sql
        assert params

    def fetchmany(self, size: int) -> list[Any]:
        return []

    def close(self) -> None:
        pass


class FakeDriverConnection:
    def cursor(self) -> FakeDriverCursor:
        return FakeDriverCursor()

    def close(self) -> None:
        pass


def _settings(tmp_path: Path, adapter: str) -> SourceSettings:
    secret = tmp_path / "secret"
    secret.write_text("fixture-value", encoding="utf-8")
    return SourceSettings(
        adapter=adapter,
        host="unused-host",
        port=1972,
        namespace="example",
        user="service",
        password_file=secret,
        odbc_driver="InterSystems ODBC35",
        jdbc_driver="example.Driver",
        jdbc_url="jdbc:example:unused",
        jdbc_jars=("driver.jar",),
    )


def test_odbc_adapter_uses_fake_driver(monkeypatch: Any, tmp_path: Path) -> None:
    def connect(connection_string: str, **kwargs: Any) -> FakeDriverConnection:
        assert "SERVER=unused-host;" in connection_string
        assert "HOST=" not in connection_string
        assert "DATABASE=example;" in connection_string
        return FakeDriverConnection()

    module = SimpleNamespace(connect=connect)
    monkeypatch.setitem(sys.modules, "pyodbc", module)
    adapter = OdbcSourceAdapter(_settings(tmp_path, "odbc"))
    adapter.open()
    cursor = adapter.query(resolve_interface("web.mr"), ("2026-10-28",))
    assert tuple(cursor.columns) == ("institute_id", "patient_id", "visit_id")
    adapter.close()


def test_jdbc_adapter_uses_fake_driver(monkeypatch: Any, tmp_path: Path) -> None:
    module = SimpleNamespace(connect=lambda *args, **kwargs: FakeDriverConnection())
    monkeypatch.setitem(sys.modules, "jaydebeapi", module)
    adapter = JdbcSourceAdapter(_settings(tmp_path, "jdbc"))
    adapter.open()
    cursor = adapter.query(resolve_interface("web.mr"), ("2026-10-28",))
    assert tuple(cursor.columns) == ("institute_id", "patient_id", "visit_id")
    adapter.close()


def test_driver_error_does_not_expose_original_text(monkeypatch: Any, tmp_path: Path) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("password=secret patient=someone")

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=fail))
    adapter = OdbcSourceAdapter(_settings(tmp_path, "odbc"))
    try:
        adapter.open()
    except IngestError as exc:
        assert "secret" not in str(exc)
        assert "someone" not in str(exc)
        assert exc.location == "odbc_connect"
    else:
        raise AssertionError("expected controlled error")


def test_unregistered_interface_fails_before_settings_load(monkeypatch: Any, capsys: Any) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("configuration must not be read")

    monkeypatch.setattr(cli.Settings, "load", forbidden)
    exit_code = cli.main(["extract", "--interface", "web.unknown", "--date", "2026-10-28"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "interface_not_registered" in captured.err
