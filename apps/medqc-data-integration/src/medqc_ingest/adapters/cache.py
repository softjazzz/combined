"""Caché 的 ODBC/JDBC 可选适配器。"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from contextlib import suppress
from typing import Any, cast

from medqc_ingest.config import SourceSettings
from medqc_ingest.domain import ErrorKind, IngestError, InterfaceSpec


class _DbApiSourceCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        description = getattr(cursor, "description", None) or ()
        self._columns = tuple(str(column[0]) for column in description)
        self._source_types = tuple(
            _safe_type_name(column[1] if len(column) > 1 else None)
            for column in description
        )

    @property
    def columns(self) -> Sequence[str]:
        return self._columns

    @property
    def source_types(self) -> Sequence[str]:
        return self._source_types

    def fetchmany(self, size: int) -> Sequence[Sequence[Any]]:
        try:
            return cast(Sequence[Sequence[Any]], self._cursor.fetchmany(size))
        except Exception:
            raise IngestError(ErrorKind.SOURCE_QUERY, "source_fetchmany") from None

    def close(self) -> None:
        with suppress(Exception):
            self._cursor.close()


class OdbcSourceAdapter:
    def __init__(self, settings: SourceSettings) -> None:
        self._settings = settings
        self._connection: Any | None = None

    def open(self) -> None:
        try:
            pyodbc = importlib.import_module("pyodbc")
        except ImportError:
            raise IngestError(ErrorKind.CONFIGURATION, "odbc_driver_unavailable") from None
        connection_string = (
            f"DRIVER={{{self._settings.odbc_driver}}};"
            f"HOST={self._settings.host};PORT={self._settings.port};"
            f"DATABASE={self._settings.namespace};UID={self._settings.user};"
            f"PWD={self._settings.password()};"
        )
        try:
            self._connection = pyodbc.connect(
                connection_string, autocommit=True, timeout=30
            )
        except Exception:
            raise IngestError(ErrorKind.SOURCE_CONNECT, "odbc_connect") from None

    def query(self, spec: InterfaceSpec, arguments: Sequence[str]) -> _DbApiSourceCursor:
        if self._connection is None:
            raise IngestError(ErrorKind.SOURCE_CONNECT, "odbc_not_open")
        if len(arguments) != spec.argument_count:
            raise IngestError(ErrorKind.CONFIGURATION, "source_argument_count")
        try:
            cursor = self._connection.cursor()
            placeholders = ",".join("?" for _ in arguments)
            cursor.execute(f"{{CALL {spec.procedure}({placeholders})}}", *arguments)
            return _DbApiSourceCursor(cursor)
        except Exception:
            raise IngestError(ErrorKind.SOURCE_QUERY, "odbc_call") from None

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            with suppress(Exception):
                connection.close()


class JdbcSourceAdapter:
    def __init__(self, settings: SourceSettings) -> None:
        self._settings = settings
        self._connection: Any | None = None

    def open(self) -> None:
        if not self._settings.jdbc_driver or not self._settings.jdbc_url:
            raise IngestError(ErrorKind.CONFIGURATION, "jdbc_settings_missing")
        try:
            jaydebeapi = importlib.import_module("jaydebeapi")
        except ImportError:
            raise IngestError(ErrorKind.CONFIGURATION, "jdbc_driver_unavailable") from None
        try:
            self._connection = jaydebeapi.connect(
                self._settings.jdbc_driver,
                self._settings.jdbc_url,
                [self._settings.user, self._settings.password()],
                list(self._settings.jdbc_jars),
            )
        except Exception:
            raise IngestError(ErrorKind.SOURCE_CONNECT, "jdbc_connect") from None

    def query(self, spec: InterfaceSpec, arguments: Sequence[str]) -> _DbApiSourceCursor:
        if self._connection is None:
            raise IngestError(ErrorKind.SOURCE_CONNECT, "jdbc_not_open")
        if len(arguments) != spec.argument_count:
            raise IngestError(ErrorKind.CONFIGURATION, "source_argument_count")
        try:
            cursor = self._connection.cursor()
            placeholders = ",".join("?" for _ in arguments)
            cursor.execute(f"{{CALL {spec.procedure}({placeholders})}}", tuple(arguments))
            return _DbApiSourceCursor(cursor)
        except Exception:
            raise IngestError(ErrorKind.SOURCE_QUERY, "jdbc_call") from None

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            with suppress(Exception):
                connection.close()


def create_source_adapter(settings: SourceSettings) -> OdbcSourceAdapter | JdbcSourceAdapter:
    if settings.adapter == "odbc":
        return OdbcSourceAdapter(settings)
    if settings.adapter == "jdbc":
        return JdbcSourceAdapter(settings)
    raise IngestError(ErrorKind.CONFIGURATION, "source_adapter_unknown")


def _safe_type_name(value: Any) -> str:
    name = getattr(value, "__name__", None) or type(value).__name__
    safe = "".join(character for character in str(name) if character.isalnum() or character == "_")
    return safe[:64] or "unknown"
