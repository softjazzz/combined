"""
Demo 反馈系统数据库连接管理
使用 SQLite 进行持久化存储
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from ..models.demo import Base

# 数据库文件路径
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "demo_feedbacks.db"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 数据库连接 URL
DATABASE_URL = f"sqlite:///{DB_FILE}"

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 特定配置
    echo=False  # 设置为 True 可查看 SQL 语句（调试用）
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    # Keep ASCII output to avoid Windows GBK console encoding errors.
    print(f"Database initialized: {DB_FILE}")


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理器用）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# 启动时自动初始化数据库
init_db()
