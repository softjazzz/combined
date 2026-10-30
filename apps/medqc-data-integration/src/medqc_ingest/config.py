"""环境配置与凭据文件边界。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from medqc_ingest.domain import ErrorKind, IngestError


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise IngestError(ErrorKind.CONFIGURATION, f"missing:{name}")
    return value


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise IngestError(ErrorKind.CONFIGURATION, f"invalid:{name}") from None
    if value <= 0:
        raise IngestError(ErrorKind.CONFIGURATION, f"invalid:{name}")
    return value


def read_secret(path: Path, location: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise IngestError(ErrorKind.CONFIGURATION, location) from None
    if not value or "\n" in value or "\r" in value:
        raise IngestError(ErrorKind.CONFIGURATION, location)
    return value


def source_zone(name: str) -> tzinfo:
    if name == "Asia/Shanghai":
        # 当前医院取数窗口使用 UTC+8，与既有字段转换合同一致；Windows 无需另装 tzdata。
        return timezone(timedelta(hours=8), name=name)
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise IngestError(ErrorKind.CONFIGURATION, "source_timezone") from None


@dataclass(frozen=True)
class PostgresSettings:
    host: str
    port: int
    database: str
    user: str
    password_file: Path

    def connection_kwargs(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": read_secret(self.password_file, "postgres_password_file"),
            "connect_timeout": 10,
        }


@dataclass(frozen=True)
class PassfilePostgresSettings(PostgresSettings):
    """password_file 在此为受保护的 libpq passfile，口令不进入连接参数。"""

    def connection_kwargs(self) -> dict[str, object]:
        if os.environ.get("PGPASSWORD"):
            raise IngestError(ErrorKind.CONFIGURATION, "pgpassword_overrides_passfile")
        if not self.password_file.is_absolute() or not self.password_file.is_file():
            raise IngestError(ErrorKind.CONFIGURATION, "postgres_passfile")
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "passfile": str(self.password_file),
            "connect_timeout": 10,
        }


@dataclass(frozen=True)
class SourceSettings:
    adapter: str
    host: str
    port: int
    namespace: str
    user: str
    password_file: Path
    odbc_driver: str
    jdbc_driver: str | None
    jdbc_url: str | None
    jdbc_jars: tuple[str, ...]

    def password(self) -> str:
        return read_secret(self.password_file, "source_password_file")


@dataclass(frozen=True)
class Settings:
    source: SourceSettings | None
    ingest: PostgresSettings | None
    cdm: PostgresSettings | None
    chunk_size: int
    stale_batch_minutes: int
    source_timezone: str

    @classmethod
    def load(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        need_source: bool = True,
        need_ingest: bool = True,
        need_cdm: bool = False,
    ) -> Settings:
        values = os.environ if env is None else env
        source = _source_settings(values) if need_source else None
        ingest = _pg_settings(values, "INGEST") if need_ingest else None
        cdm = _pg_settings(values, "CDM") if need_cdm else None
        source_timezone = values.get("MEDQC_SOURCE_TIMEZONE", "Asia/Shanghai").strip()
        if not source_timezone:
            source_timezone = "Asia/Shanghai"
        source_zone(source_timezone)
        return cls(
            source=source,
            ingest=ingest,
            cdm=cdm,
            chunk_size=_positive_int(values, "MEDQC_CHUNK_SIZE", 1000),
            stale_batch_minutes=_positive_int(values, "MEDQC_STALE_BATCH_MINUTES", 60),
            source_timezone=source_timezone,
        )


def _source_settings(env: Mapping[str, str]) -> SourceSettings:
    adapter = env.get("MEDQC_SOURCE_ADAPTER", "odbc").strip().lower()
    if adapter not in {"odbc", "jdbc"}:
        raise IngestError(ErrorKind.CONFIGURATION, "invalid:MEDQC_SOURCE_ADAPTER")
    jdbc_jars = tuple(
        part.strip()
        for part in env.get("MEDQC_CACHE_JDBC_JARS", "").split(os.pathsep)
        if part.strip()
    )
    odbc_driver = env.get("MEDQC_CACHE_ODBC_DRIVER", "InterSystems ODBC35").strip()
    jdbc_driver = env.get("MEDQC_CACHE_JDBC_DRIVER", "").strip() or None
    jdbc_url = env.get("MEDQC_CACHE_JDBC_URL", "").strip() or None
    if adapter == "odbc" and not odbc_driver:
        raise IngestError(ErrorKind.CONFIGURATION, "missing:MEDQC_CACHE_ODBC_DRIVER")
    if adapter == "jdbc" and (not jdbc_driver or not jdbc_url or not jdbc_jars):
        raise IngestError(ErrorKind.CONFIGURATION, "missing:JDBC_SETTINGS")
    return SourceSettings(
        adapter=adapter,
        host=_required(env, "MEDQC_CACHE_HOST"),
        port=_positive_int(env, "MEDQC_CACHE_PORT", 1972),
        namespace=_required(env, "MEDQC_CACHE_NAMESPACE"),
        user=_required(env, "MEDQC_CACHE_USER"),
        password_file=Path(_required(env, "MEDQC_CACHE_PASSWORD_FILE")),
        odbc_driver=odbc_driver,
        jdbc_driver=jdbc_driver,
        jdbc_url=jdbc_url,
        jdbc_jars=jdbc_jars,
    )


def _pg_settings(env: Mapping[str, str], prefix: str) -> PostgresSettings:
    base = f"MEDQC_{prefix}_PG_"
    passfile = env.get("MEDQC_PG_PASSFILE", "").strip()
    setting_type = PassfilePostgresSettings if passfile else PostgresSettings
    return setting_type(
        host=_required(env, f"{base}HOST"),
        port=_positive_int(env, f"{base}PORT", 5432),
        database=_required(env, f"{base}DATABASE"),
        user=_required(env, f"{base}USER"),
        password_file=Path(passfile or _required(env, f"{base}PASSWORD_FILE")),
    )
