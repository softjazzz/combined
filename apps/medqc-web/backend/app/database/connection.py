"""
数据库连接管理模块
支持 SQLite（开发）和 PostgreSQL（生产）双模式

切换方式：修改 .env 中的 DATABASE_URL
- 开发: DATABASE_URL=sqlite:///./data/medqc.db
- 生产: DATABASE_URL=postgresql://user:pass@host:5432/medqc
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# 加载 .env 文件（从 backend/ 目录）
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

# ==================== Base 类 ====================
class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


# ==================== 数据库 URL ====================
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 必须显式配置 DATABASE_URL（PostgreSQL），不再默认 SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    import logging as _log
    _log.getLogger(__name__).warning(
        "[connection] DATABASE_URL 未配置，数据库功能不可用。"
        "请设置环境变量 DATABASE_URL 指向 PostgreSQL 实例。"
    )

# ==================== 引擎配置 ====================
_engine_kwargs = {}

if DATABASE_URL and not DATABASE_URL.startswith("sqlite"):
    # PostgreSQL 默认不要无限等待。连接失败或连接池拿不到连接时，应尽快报错，
    # 否则在 Windows 开发环境里会表现成“进程还活着，但所有接口都 pending”。
    _engine_kwargs.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "5")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
            "pool_use_lifo": True,
            "connect_args": {
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
            },
        }
    )

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    **_engine_kwargs
)

# SQLite 启用外键约束
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ==================== Session ====================
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库：建表 → 补齐列 → 创建视图（可重复执行、幂等）"""
    # 导入模型确保注册到 Base.metadata
    from .models import cdm  # noqa: F401
    from .models import sync  # noqa: F401  — 同步状态追踪表
    from .models import qc  # noqa: F401  — 质控业务层表

    # Step 1: 建表（已存在的表会跳过）
    Base.metadata.create_all(bind=engine)

    # Step 2: 补齐已有表与 ORM 定义的列差异（ALTER TABLE ADD COLUMN）
    if not DATABASE_URL.startswith("sqlite"):
        _sync_missing_columns()

    # Step 3: 创建/重建视图
    view_ok = []
    view_fail = []
    if not DATABASE_URL.startswith("sqlite"):
        view_ok, view_fail = _create_views()

    db_type = "SQLite" if DATABASE_URL.startswith("sqlite") else "PostgreSQL"
    # 使用纯 ASCII 输出，避免 Windows GBK 终端编码异常导致启动流程报错
    print(f"[OK] CDM database initialized ({db_type}): {DATABASE_URL}")
    if view_ok:
        print(f"  views OK: {', '.join(view_ok)}")
    if view_fail:
        print(f"  views SKIPPED: {', '.join(view_fail)}")


def _sync_missing_columns():
    """检测 ORM 定义 vs PG 实际列差异，用 ALTER TABLE ADD COLUMN 补齐。

    幂等操作：已存在的列不会重复添加。

    已知限制：仅补列类型，不补 DEFAULT / NOT NULL / COMMENT 等约束。
    完整 schema 对齐需通过 Alembic migration 实现。
    """
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
                    logger.info(f"[schema-sync] ADD COLUMN {table.name}.{col_name} ({col_type})")
                except Exception as e:
                    logger.warning(f"[schema-sync] SKIP {table.name}.{col_name}: {e}")
            conn.commit()


def _create_views():
    """执行 qc_views.sql，创建/重建所有视图。

    幂等操作：使用 DROP VIEW IF EXISTS + CREATE VIEW。
    单条失败不影响其他视图。

    qc_statistics_view 依赖文书表名，通过 DOCUMENTS_TABLE 配置动态替换，
    避免硬编码 medical_documents vs medical_documents_test 的偏差。

    Returns:
        (ok_list, fail_list): 成功和失败的视图名列表
    """
    import re
    from sqlalchemy import text

    sql_path = Path(__file__).parent / "sql" / "qc_views.sql"
    if not sql_path.exists():
        return [], []

    sql_text = sql_path.read_text(encoding="utf-8")

    # 动态替换 qc_statistics_view 中的表名为 settings 配置值
    documents_table = os.getenv("DOCUMENTS_TABLE", "medical_documents_test")
    sql_text = sql_text.replace(
        "FROM medical_documents d",
        f"FROM {documents_table} d",
    )

    stmts = [s.strip() for s in sql_text.split(";") if s.strip()]

    ok_list = []
    fail_list = []

    for stmt in stmts:
        # 仅统计 CREATE VIEW 语句，避免把普通 SQL 误记为 "unknown"
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
                    logger.warning(f"[views] SKIP {view_name}: {e}")

    return ok_list, fail_list


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """上下文管理器用"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
