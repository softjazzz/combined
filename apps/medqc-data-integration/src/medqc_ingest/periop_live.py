"""第二批真实源的显式日期边界；不变更公共注册表或ODBC实现。"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from medqc_ingest.adapters.cache import OdbcSourceAdapter
from medqc_ingest.config import Settings, SourceSettings
from medqc_ingest.domain import ErrorKind, IngestError, InterfaceSpec
from medqc_ingest.periop_replay import explicit_window, require
from medqc_ingest.ports import SourceCursor

LIVE_PROFILE = "periop-live-explicit-v1"
BASELINE_INGEST = "medqc_periop_ingest_takeover_20261101043319"
BASELINE_CDM = "medqc_periop_cdm_takeover_20261101043319"
BASELINE_RESULT_SHA = "18a4a0241265aca3b24f427650e70aaf252638a65b63a8eb0d9c4826df067d5d"
SOURCE_KEYS = frozenset(
    {
        "MEDQC_SOURCE_ADAPTER",
        "MEDQC_CACHE_HOST",
        "MEDQC_CACHE_PORT",
        "MEDQC_CACHE_NAMESPACE",
        "MEDQC_CACHE_USER",
        "MEDQC_CACHE_PASSWORD_FILE",
        "MEDQC_CACHE_ODBC_DRIVER",
        "MEDQC_SOURCE_TIMEZONE",
    }
)


def verify_baseline_evidence(acceptance: dict[str, Any], plan: dict[str, Any]) -> None:
    require(
        acceptance.get("status") == "PERIOP_ARCHIVE_TAKEOVER_ACCEPTED"
        and acceptance.get("synthetic") is False
        and acceptance.get("postgres_major") == 16
        and acceptance.get("raw_rows") == acceptance.get("history_rows") == 9365
        and acceptance.get("source_unchanged") is True
        and acceptance.get("active_interfaces") == 13,
        "periop_live_baseline_evidence",
    )
    require(
        plan.get("databases", {}).get("ingest") == BASELINE_INGEST
        and plan.get("databases", {}).get("cdm") == BASELINE_CDM,
        "periop_live_baseline_evidence_databases",
    )


def live_database_names(suffix: str) -> dict[str, str]:
    require(re.fullmatch(r"[0-9]{14}", suffix) is not None, "periop_live_database_suffix")
    return {
        role: f"medqc_periop_live_{role}_{suffix}"
        for role in ("ingest", "cdm", "restore_ingest", "restore_cdm")
    }


def source_settings(path: Path) -> SourceSettings:
    document = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(document, dict), "periop_live_source_config_object")
    # 只筛选源参数，不读取旧服务PG口令，不创建其Settings或运行旧入口。
    values = {key: value for key, value in document.items() if key in SOURCE_KEYS}
    require(all(isinstance(v, str) for v in values.values()), "periop_live_source_config_types")
    require(values.get("MEDQC_SOURCE_ADAPTER", "odbc") == "odbc", "periop_live_odbc_only")
    source = Settings.load(values, need_ingest=False, need_cdm=False).source
    assert source is not None
    require(
        source.port == 1972 and source.odbc_driver == "InterSystems ODBC35",
        "periop_live_driver_contract",
    )
    require(
        all(
            not any(ch in v for ch in ";{}\r\n") and v.strip() == v
            for v in (source.host, source.namespace, source.user)
        ),
        "periop_live_source_fields",
    )
    require(
        source.password_file.is_absolute() and source.password_file.is_file(),
        "periop_live_existing_password_file",
    )
    return source


def live_spec(spec: InterfaceSpec) -> InterfaceSpec:
    return replace(spec, evidence_version=LIVE_PROFILE + ";" + spec.evidence_version)


def safe_odbc_diagnostic(error: BaseException) -> dict[str, str | int | None]:
    current: BaseException | None = error
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        args = current.args
        if (
            len(args) >= 2
            and isinstance(args[0], str)
            and re.fullmatch(r"[0-9A-Z]{5}", args[0])
            and isinstance(args[1], str)
        ):
            match = re.search(r"\bNative Code\s*:?\s*(-?[0-9]{1,6})\b", args[1], re.I)
            return {"sqlstate": args[0], "native": int(match[1]) if match else None}
        current = current.__cause__ or current.__context__
    return {"sqlstate": None, "native": None}


def known_vendor_failure(error: Exception, item: dict[str, Any], day: str) -> bool:
    explicit_window(day)
    if not (
        isinstance(error, IngestError)
        and error.kind == ErrorKind.SOURCE_QUERY.value
        and error.location == "odbc_call"
        and item["source_state"] == "partial_source"
        and any(w["date"] == day and w["status"] == "failed" for w in item["source_window_status"])
    ):
        return False
    current: BaseException | None = error
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        args = current.args
        # 原文仅在内存提取受控错误码；不记录或回显错误正文。
        if (
            len(args) >= 2
            and args[0] == "HY000"
            and isinstance(args[1], str)
            and re.search(r"(?:\bNative Code\s*:?\s*400\b|\(400\))", args[1], re.I)
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


class StrictLiveCursor:
    def __init__(self, inner: SourceCursor) -> None:
        self.inner = inner

    @property
    def columns(self) -> Sequence[str]:
        return self.inner.columns

    @property
    def source_types(self) -> Sequence[str]:
        return self.inner.source_types

    def fetchmany(self, size: int) -> Sequence[Sequence[Any]]:
        rows = self.inner.fetchmany(size)
        require(
            all(
                len(row) == len(self.columns)
                and all(value is None or isinstance(value, str) for value in row)
                for row in rows
            ),
            "periop_live_type_drift",
        )
        return rows

    def close(self) -> None:
        self.inner.close()


class StrictLiveSource:
    def __init__(self, settings: SourceSettings) -> None:
        self.inner = OdbcSourceAdapter(settings)

    def open(self) -> None:
        self.inner.open()

    def query(self, spec: InterfaceSpec, arguments: Sequence[str]) -> StrictLiveCursor:
        require(len(arguments) == 1, "periop_live_single_explicit_date")
        explicit_window(arguments[0])
        return StrictLiveCursor(self.inner.query(spec, arguments))

    def close(self) -> None:
        self.inner.close()
