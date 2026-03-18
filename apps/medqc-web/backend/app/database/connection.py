"""Database connection management for MedQC backend (PostgreSQL)."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# Load backend-local .env
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# DATABASE_URL must be explicitly configured for PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    logger.warning(
        "[connection] DATABASE_URL is not configured. Database features are unavailable."
    )


def _resolve_schema_mode() -> str:
    return os.getenv("DB_SCHEMA_MODE", "single").strip().lower()


def _resolve_search_path(schema_mode: str) -> str:
    search_path = os.getenv("DB_SEARCH_PATH", "").strip()
    if not search_path and schema_mode == "split":
        # Keep public first to avoid accidental CREATE TABLE into qc/sys/cdm
        # from legacy init_db/create_all paths.
        search_path = "public,qc,sys,cdm,legacy"
    return search_path


DB_SCHEMA_MODE = _resolve_schema_mode()
DB_SEARCH_PATH = _resolve_search_path(DB_SCHEMA_MODE)

_engine_kwargs = {}
if DATABASE_URL:
    connect_args = {
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
    }
    if DB_SEARCH_PATH:
        connect_args["options"] = f"-csearch_path={DB_SEARCH_PATH}"

    _engine_kwargs.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "5")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
            "pool_use_lifo": True,
            "connect_args": connect_args,
        }
    )

engine = None
if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
        **_engine_kwargs,
    )

SessionLocal = (
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
    if engine is not None
    else None
)


def init_db():
    """Initialize DB objects: create tables, sync missing columns, create views."""
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot initialize database.")

    # Import models so metadata is registered.
    from .models import cdm  # noqa: F401
    from .models import sync  # noqa: F401
    from .models import qc  # noqa: F401

    if DB_SCHEMA_MODE == "split":
        logger.info(
            "[init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic."
        )
    else:
        Base.metadata.create_all(bind=engine)
        _sync_missing_columns()

    view_ok, view_fail = _create_views()

    print(f"[OK] CDM database initialized (PostgreSQL): {DATABASE_URL}")
    if view_ok:
        print(f"  views OK: {', '.join(view_ok)}")
    if view_fail:
        print(f"  views SKIPPED: {', '.join(view_fail)}")


def _sync_missing_columns():
    """Sync columns present in ORM but missing in existing PG tables.

    Known limitation:
    - only adds missing columns with type
    - does not backfill constraints/default/comment
    """
    if engine is None:
        return

    from sqlalchemy import inspect as sa_inspect, text

    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        db_cols = {c["name"] for c in inspector.get_columns(table.name)}
        orm_cols = {c.name for c in table.columns}
        missing = orm_cols - db_cols
        if not missing:
            continue

        with engine.connect() as conn:
            for col_name in sorted(missing):
                col = table.c[col_name]
                col_type = col.type.compile(dialect=engine.dialect)
                sql = f'ALTER TABLE "{table.name}" ADD COLUMN "{col_name}" {col_type}'
                try:
                    conn.execute(text(sql))
                    logger.info("[schema-sync] ADD COLUMN %s.%s (%s)", table.name, col_name, col_type)
                except Exception as e:
                    logger.warning("[schema-sync] SKIP %s.%s: %s", table.name, col_name, e)
            conn.commit()


def _create_views():
    """Create/recreate views from qc_views.sql.

    Returns:
        tuple[list[str], list[str]]: (ok_list, fail_list)
    """
    if engine is None:
        return [], []

    import re
    from sqlalchemy import text

    sql_path = Path(__file__).parent / "sql" / "qc_views.sql"
    if not sql_path.exists():
        return [], []

    sql_text = sql_path.read_text(encoding="utf-8")

    # Replace base documents table for qc_statistics_view based on runtime env.
    documents_table = os.getenv("DOCUMENTS_TABLE", "medical_documents")
    if DB_SCHEMA_MODE == "split" and "." not in documents_table:
        documents_table = f"cdm.{documents_table}"
    sql_text = sql_text.replace(
        "FROM medical_documents d",
        f"FROM {documents_table} d",
    )

    if DB_SCHEMA_MODE == "split":
        view_names = [
            "v_qc_task_progress",
            "qc_appeals_statistics",
            "qc_remediation_statistics",
            "qc_assignee_workload",
            "qc_statistics_view",
            "v_qc_coder_ranking",
        ]
        for view_name in view_names:
            sql_text = sql_text.replace(
                f"DROP VIEW IF EXISTS {view_name};",
                f"DROP VIEW IF EXISTS qc.{view_name};",
            )
            sql_text = sql_text.replace(
                f"CREATE VIEW {view_name} AS",
                f"CREATE VIEW qc.{view_name} AS",
            )

        sql_text = sql_text.replace("FROM qc_tasks t", "FROM qc.qc_tasks t")
        sql_text = sql_text.replace(
            "LEFT JOIN qc_task_records r",
            "LEFT JOIN qc.qc_task_records r",
        )
        sql_text = sql_text.replace("FROM qc_appeals", "FROM qc.qc_appeals")
        sql_text = sql_text.replace(
            "FROM qc_remediation_tasks",
            "FROM qc.qc_remediation_tasks",
        )
        sql_text = sql_text.replace(
            "FROM qc_coder_workload_daily",
            "FROM qc.qc_coder_workload_daily",
        )

    stmts = [s.strip() for s in sql_text.split(";") if s.strip()]

    ok_list = []
    fail_list = []

    for stmt in stmts:
        # Track only CREATE VIEW statements in summary logs.
        m = re.search(
            r'^\s*CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?("?[\w\.]+"?)',
            stmt,
            re.IGNORECASE,
        )
        is_create_view = m is not None
        view_name = m.group(1).strip('"') if m else None

        with engine.connect() as conn:
            try:
                conn.execute(text(stmt))
                conn.commit()
                if is_create_view and view_name:
                    ok_list.append(view_name)
            except Exception as e:
                conn.rollback()
                if is_create_view and view_name:
                    fail_list.append(view_name)
                    logger.warning("[views] SKIP %s: %s", view_name, e)

    return ok_list, fail_list


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for DB session."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot create DB session.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for DB session."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot create DB session.")

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
