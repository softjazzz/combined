"""跨方言表结构探测共享工具。

统一 PostgreSQL schema 查找顺序（DB_SEARCH_PATH + 兜底 schema 列表）与非 PG 方言（如 SQLite）的列集合读取，
避免多个路由重复维护各自的表字段探测实现。
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import inspect as sa_inspect

from ..services.user_scope_owner import configured_search_path

DEFAULT_PG_FALLBACK_SCHEMAS: tuple[str, ...] = ("qc", "public", "sys", "cdm")


def get_table_columns(
    session,
    table_name: str,
    *,
    fallback_schemas: Sequence[str] = DEFAULT_PG_FALLBACK_SCHEMAS,
) -> set[str]:
    """返回指定表的列名集合；表不存在时返回空集合。

    PostgreSQL 优先按 `configured_search_path()` 顺序查找，再按 `fallback_schemas` 顺序回退，
    最后回退到连接默认 schema；非 PostgreSQL 方言直接查询默认表。
    """
    bind = session.get_bind()
    inspector = sa_inspect(bind)
    if bind.dialect.name != "postgresql":
        if not inspector.has_table(table_name):
            return set()
        return {col["name"] for col in inspector.get_columns(table_name)}

    schemas = list(dict.fromkeys([*configured_search_path(), *fallback_schemas]))
    for schema in schemas:
        if inspector.has_table(table_name, schema=schema):
            return {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
    if inspector.has_table(table_name):
        return {col["name"] for col in inspector.get_columns(table_name)}
    return set()


__all__ = ["DEFAULT_PG_FALLBACK_SCHEMAS", "get_table_columns"]
