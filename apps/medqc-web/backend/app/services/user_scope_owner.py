"""解析并固定账号持久化 owner，避免 sys/public 双表随连接路径漂移。"""

from __future__ import annotations

from threading import RLock
from typing import Any
import weakref

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..database.connection import DB_SEARCH_PATH

USER_SCHEMAS = ("sys", "public")

_USER_OWNER_CACHE_LOCK = RLock()
_USER_OWNER_SCHEMA_CACHE: dict[tuple[int, tuple[str, ...]], str] = {}
_USER_OWNER_FINALIZERS: set[int] = set()


def _evict_user_owner_cache_for_engine(engine_id: int) -> None:
    with _USER_OWNER_CACHE_LOCK:
        stale_keys = [key for key in _USER_OWNER_SCHEMA_CACHE if key[0] == engine_id]
        for key in stale_keys:
            _USER_OWNER_SCHEMA_CACHE.pop(key, None)
        _USER_OWNER_FINALIZERS.discard(engine_id)


def clear_user_owner_schema_cache() -> None:
    """清空按 engine/schema 缓存的用户表 owner 解析结果。"""
    with _USER_OWNER_CACHE_LOCK:
        _USER_OWNER_SCHEMA_CACHE.clear()


class UserOwnerUnavailable(RuntimeError):
    """无法唯一确定应用实际使用的 sys_users。"""


def configured_search_path() -> list[str]:
    result = []
    for raw in str(DB_SEARCH_PATH or "").split(","):
        schema = raw.strip().strip('"')
        if schema and schema != "$user" and schema not in result:
            result.append(schema)
    return result


def select_user_owner_schema(
    *,
    search_path: list[str],
    schemas_with_user_table: list[str],
) -> str:
    """按应用 search_path 选择实际可见 owner；未知 schema 抢先时拒绝。"""
    existing = set(schemas_with_user_table)
    if search_path:
        visible = next((schema for schema in search_path if schema in existing), None)
        if visible is None:
            raise UserOwnerUnavailable("账号持久表不在配置的 DB_SEARCH_PATH 中")
        if visible not in USER_SCHEMAS:
            raise UserOwnerUnavailable(f"账号持久表解析到不受信任 schema: {visible}")
        return visible
    known = [schema for schema in USER_SCHEMAS if schema in existing]
    unknown = sorted(existing.difference(USER_SCHEMAS))
    if len(known) == 1 and not unknown:
        return known[0]
    raise UserOwnerUnavailable("账号持久表 owner 不唯一且 DB_SEARCH_PATH 未明确")


def resolve_user_owner_schema(session: Session) -> str | None:
    """返回 PostgreSQL owner schema（按 engine 与 search_path 缓存）；SQLite 单测返回 None。"""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return None
    engine_obj = getattr(bind, "engine", bind)
    engine_id = id(engine_obj)
    configured = configured_search_path()
    cache_key = (engine_id, tuple(configured))
    with _USER_OWNER_CACHE_LOCK:
        cached = _USER_OWNER_SCHEMA_CACHE.get(cache_key)
        if cached is not None:
            return cached

    inspector = sa.inspect(bind)
    schemas = list(dict.fromkeys([*configured, *USER_SCHEMAS]))
    if not configured:
        schemas = list(dict.fromkeys([*inspector.get_schema_names(), *schemas]))
    existing = [
        schema for schema in schemas if inspector.has_table("sys_users", schema=schema)
    ]
    if not existing:
        raise UserOwnerUnavailable("账号持久表不存在")
    resolved = select_user_owner_schema(
        search_path=configured, schemas_with_user_table=existing
    )
    with _USER_OWNER_CACHE_LOCK:
        if engine_id not in _USER_OWNER_FINALIZERS:
            try:
                weakref.finalize(engine_obj, _evict_user_owner_cache_for_engine, engine_id)
                _USER_OWNER_FINALIZERS.add(engine_id)
            except TypeError:
                pass
        _USER_OWNER_SCHEMA_CACHE[cache_key] = resolved
    return resolved


def user_owner_options(session: Session) -> dict[str, Any]:
    schema = resolve_user_owner_schema(session)
    return {} if schema is None else {"schema_translate_map": {None: schema}}


__all__ = [
    "USER_SCHEMAS",
    "UserOwnerUnavailable",
    "clear_user_owner_schema_cache",
    "configured_search_path",
    "resolve_user_owner_schema",
    "select_user_owner_schema",
    "user_owner_options",
]
