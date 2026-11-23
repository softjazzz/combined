"""显式启用的独立CDM只读连接；不改变业务engine或SessionLocal。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from weakref import WeakKeyDictionary

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import Pool

_selection: ContextVar[dict | None] = ContextVar("clinical_source_selection", default=None)
_capture_executors: WeakKeyDictionary[Pool, ThreadPoolExecutor] = WeakKeyDictionary()
_capture_executors_lock = Lock()


def submit_capture(engine: Engine, operation, *args, **kwargs):
    """同一只读 CDM 池最多四路捕获，排队不占用通用工作线程。"""
    pool = engine.pool
    with _capture_executors_lock:
        executor = _capture_executors.get(pool)
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="medqc-cdm-capture")
            _capture_executors[pool] = executor
    return executor.submit(copy_context().run, operation, *args, **kwargs)


def current_selection() -> dict | None:
    return _selection.get()


@contextmanager
def selected(source: dict):
    token = _selection.set(dict(source))
    try:
        yield
    finally:
        _selection.reset(token)


class ClinicalSourceConfigurationError(RuntimeError):
    def __init__(self):
        super().__init__("invalid_independent_cdm_configuration")


def configured() -> bool:
    from ..services.clinical_source_policy import fixed_cdm
    source = current_selection()
    if source is not None:
        return source["id"] == "independent_cdm"
    if fixed_cdm():
        return True
    return bool(os.getenv("CDM_DATABASE_URL", "").strip()
                or os.getenv("CDM_PGPASSFILE", "").strip())


def _url(value: str):
    try:
        url = make_url(value)
        if (url.drivername not in {"postgresql", "postgresql+psycopg2"}
                or not url.database or not url.username or not url.host
                or set(url.query) - {"sslmode", "sslrootcert", "sslcert", "sslkey", "application_name"}):
            raise ValueError
        return url
    except Exception:
        raise ClinicalSourceConfigurationError() from None


@lru_cache(maxsize=4)
def _engine(value: str, passfile: str) -> Engine:
    url = _url(value)
    connect_args = {"connect_timeout": 5, "options": "-c default_transaction_read_only=on"}
    if passfile:
        path = Path(passfile)
        if not path.is_absolute() or not path.is_file() or url.password:
            raise ClinicalSourceConfigurationError()
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise ClinicalSourceConfigurationError()
        connect_args["passfile"] = str(path)
    try:
        return create_engine(url, connect_args=connect_args, pool_size=3, max_overflow=2,
                             pool_timeout=5, pool_pre_ping=True, pool_recycle=1800,
                             echo=False, hide_parameters=True)
    except Exception:
        raise ClinicalSourceConfigurationError() from None


def get_engine() -> Engine | None:
    source = current_selection()
    if source is not None:
        if source["id"] == "legacy_pg":
            return None
        passfile = os.getenv("CDM_PGPASSFILE", "").strip()
        if not passfile:
            raise ClinicalSourceConfigurationError()
        return _engine(source["url"], passfile)
    from ..services.clinical_source_policy import fixed_cdm
    if fixed_cdm():
        from ..services.clinical_sources import ordinary_snapshot
        source=ordinary_snapshot()
        return _engine(source["url"], os.getenv("CDM_PGPASSFILE", "").strip())
    value = os.getenv("CDM_DATABASE_URL", "").strip()
    if not value:
        if os.getenv("CDM_PGPASSFILE", "").strip():
            raise ClinicalSourceConfigurationError()
        return None
    return _engine(value, os.getenv("CDM_PGPASSFILE", "").strip())


def build_source_binding(host: str, port: int | None, database: str, username: str) -> str:
    """生成 cdm-read-v1 摘要，保留历史快照约定的字段顺序与 JSON 序列化。"""
    identity = [host, port or 5432, database, username, "cdm"]
    return "cdm-read-v1:" + hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()


def source_binding() -> str:
    """仅隔离不同临床源的持久缓存，不包含口令、passfile或患者数据。"""
    source = current_selection()
    if source is not None:
        return source["binding"]
    from ..services.clinical_source_policy import fixed_cdm
    if fixed_cdm():
        from ..services.clinical_sources import ordinary_snapshot
        return ordinary_snapshot()["binding"]
    value = os.getenv("CDM_DATABASE_URL", "").strip()
    if not value:
        if os.getenv("CDM_PGPASSFILE", "").strip():
            raise ClinicalSourceConfigurationError()
        return ""
    url = _url(value)
    return build_source_binding(url.host, url.port, url.database, url.username)
