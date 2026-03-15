"""
数据库连接管理模块
支持 SQLite（开发）和 PostgreSQL（生产）双模式

切换方式：修改 .env 中的 DATABASE_URL
- 开发: DATABASE_URL=sqlite:///./data/medqc.db
- 生产: DATABASE_URL=postgresql://user:pass@host:5432/medqc
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextlib import contextmanager
from typing import Generator

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

# 默认使用 SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR / 'medqc.db'}"
)

# ==================== 引擎配置 ====================
_engine_kwargs = {}

if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
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
    if not DATABASE_URL.startswith("sqlite"):
        _create_views()

    db_type = "SQLite" if DATABASE_URL.startswith("sqlite") else "PostgreSQL"
    # 使用纯 ASCII 输出，避免 Windows GBK 终端编码异常导致启动流程报错
    print(f"[OK] CDM database initialized ({db_type}): {DATABASE_URL}")


def _sync_missing_columns():
    """检测 ORM 定义 vs PG 实际列差异，用 ALTER TABLE ADD COLUMN 补齐。

    幂等操作：已存在的列不会重复添加。
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
                except Exception:
                    pass  # 列已存在或其他非致命错误
            conn.commit()


def _create_views():
    """执行 qc_views.sql，创建/重建所有视图。

    幂等操作：使用 DROP VIEW IF EXISTS + CREATE VIEW。
    单条失败不影响其他视图。

    qc_statistics_view 依赖文书表名，通过 DOCUMENTS_TABLE 配置动态替换，
    避免硬编码 medical_documents vs medical_documents_test 的偏差。
    """
    from sqlalchemy import text

    sql_path = Path(__file__).parent / "sql" / "qc_views.sql"
    if not sql_path.exists():
        return

    sql_text = sql_path.read_text(encoding="utf-8")

    # 动态替换 qc_statistics_view 中的表名为 settings 配置值
    documents_table = os.getenv("DOCUMENTS_TABLE", "medical_documents_test")
    sql_text = sql_text.replace(
        "FROM medical_documents d",
        f"FROM {documents_table} d",
    )

    stmts = [s.strip() for s in sql_text.split(";") if s.strip()]

    for stmt in stmts:
        with engine.connect() as conn:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()  # 单条失败不阻断


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
