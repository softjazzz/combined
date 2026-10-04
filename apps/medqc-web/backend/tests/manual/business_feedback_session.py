"""手工联调专用反馈会话；默认不创建连接，不自动迁移。"""
from __future__ import annotations

from collections.abc import Mapping

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import visitors
from sqlalchemy.sql.dml import Insert
from sqlalchemy.sql.selectable import Select

from app.services.qc_agent.business_feedback import BusinessFeedbackStore, feedback_table, get_feedback_store


def install_feedback_override(app, settings: Mapping[str, str | None], *, enabled: str = "0"):
    """只替换反馈依赖；不接收或修改主应用读取 engine。"""
    if enabled != "1":
        return None
    dsn = settings.get("DATABASE_URL") or ""
    mode = (settings.get("DB_SCHEMA_MODE") or "single").strip().lower()
    if not dsn or sa.engine.make_url(dsn).get_backend_name() != "postgresql" or mode not in {"single", "split"}:
        raise RuntimeError("反馈专用会话需要有效 PostgreSQL 配置")
    schema = "qc" if mode == "split" else "public"
    search_path = settings.get("DB_SEARCH_PATH") or ("public,qc,sys,cdm,legacy" if mode == "split" else "public")
    if not all(part.strip().replace("_", "").isalnum() for part in search_path.split(",")):
        raise RuntimeError("反馈专用会话 search_path 配置无效")
    table = feedback_table(schema)
    feedback_engine = sa.create_engine(
        dsn, poolclass=sa.pool.NullPool,
        connect_args={"connect_timeout": 5, "options": f"-csearch_path={search_path} -cstatement_timeout=10000 -clock_timeout=3000"},
    )

    @sa.event.listens_for(feedback_engine, "before_cursor_execute")
    def restrict_feedback_sql(_connection, _cursor, _statement, _parameters, context, _executemany):
        # 仅允许 Store 的固定表 SELECT/INSERT；拒绝文本SQL、DDL及其他表。
        statement = context.compiled.statement if context.compiled is not None else None
        if not isinstance(statement, (Select, Insert)):
            raise RuntimeError("反馈专用连接仅允许反馈表查询和新增")
        tables = [node for node in visitors.iterate(statement) if isinstance(node, sa.Table)]
        if not tables or any(node.name != table.name or node.schema != table.schema for node in tables):
            raise RuntimeError("反馈专用连接拒绝访问其他表")

    store = BusinessFeedbackStore(sessionmaker(bind=feedback_engine, autocommit=False, autoflush=False), table)
    app.dependency_overrides[get_feedback_store] = lambda: store
    return feedback_engine
