"""
SQLAlchemy 适配客户端 — 替代 Supabase PostgREST

设计目标：
- 保持 .table().select().eq().execute() 链式 API 不变
- 24 个路由文件零改动
- get_supabase() 返回本适配客户端而非 Supabase Client
- 支持同步 execute() 和异步 execute_async()
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# ==================== 连接池（复用 database/connection.py 的配置逻辑） ====================

_engine = None
_SessionLocal = None


def _get_session_factory():
    """获取或创建 SQLAlchemy Session 工厂"""
    global _engine, _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    from dotenv import load_dotenv
    from pathlib import Path
    # __file__ = app/core/supabase_client.py → 往上三级到 backend/.env
    _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_env_path)

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        logger.warning("DATABASE_URL 未设置，SQLAlchemy 适配客户端不可用")
        return None

    schema_mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    search_path = os.getenv("DB_SEARCH_PATH", "").strip()
    if not search_path and schema_mode == "split":
        search_path = "public,qc,sys,cdm,legacy"

    engine_kwargs = {}
    if db_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        connect_args = {
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
        }
        if search_path:
            connect_args["options"] = f"-csearch_path={search_path}"

        engine_kwargs.update({
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "5")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
            "pool_use_lifo": True,
            "connect_args": connect_args,
        })

    _engine = create_engine(db_url, pool_pre_ping=True, **engine_kwargs)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    logger.info(
        "SQLAlchemy 适配客户端连接池就绪: %s (schema_mode=%s, search_path=%s)",
        db_url.split("@")[-1] if "@" in db_url else db_url,
        schema_mode,
        search_path or "<default>",
    )
    return _SessionLocal


# ==================== Response 对象 ====================

class _Response:
    """兼容 Supabase 响应格式"""
    def __init__(self, data: Any = None, count: Optional[int] = None):
        self.data = data
        self.count = count


# ==================== Query Builder ====================

class _Query:
    """
    模拟 Supabase PostgREST 的链式查询构建器。
    支持的方法: select, eq, in_, is_, neq, gte, lte, gt, lt, like, ilike,
                or_, order, limit, range, single, insert, update, delete
    """

    def __init__(self, session_factory, table_name: str):
        self._session_factory = session_factory
        self._table = table_name
        self._method = "SELECT"
        self._columns = "*"
        self._filters: List[Tuple[str, str, Any]] = []  # (column, op, value)
        self._or_filters: List[str] = []  # raw OR filter strings
        self._orders: List[Tuple[str, bool]] = []  # (column, ascending)
        self._limit_val: Optional[int] = None
        self._range_val: Optional[Tuple[int, int]] = None
        self._single: bool = False
        self._count_mode: Optional[str] = None
        self._payload: Any = None

    # ---------- 方法设置 ----------

    def select(self, columns: str = "*", count: Optional[str] = None) -> _Query:
        self._method = "SELECT"
        self._columns = columns or "*"
        if count:
            self._count_mode = count
        return self

    def insert(self, payload: Any) -> _Query:
        self._method = "INSERT"
        self._payload = payload
        return self

    def update(self, payload: Any) -> _Query:
        self._method = "UPDATE"
        self._payload = payload
        return self

    def delete(self) -> _Query:
        self._method = "DELETE"
        return self

    # ---------- 过滤器 ----------

    def eq(self, column: str, value: Any) -> _Query:
        self._filters.append((column, "=", value))
        return self

    def neq(self, column: str, value: Any) -> _Query:
        self._filters.append((column, "!=", value))
        return self

    def gt(self, column: str, value: Any) -> _Query:
        self._filters.append((column, ">", value))
        return self

    def gte(self, column: str, value: Any) -> _Query:
        self._filters.append((column, ">=", value))
        return self

    def lt(self, column: str, value: Any) -> _Query:
        self._filters.append((column, "<", value))
        return self

    def lte(self, column: str, value: Any) -> _Query:
        self._filters.append((column, "<=", value))
        return self

    def like(self, column: str, pattern: str) -> _Query:
        self._filters.append((column, "LIKE", pattern))
        return self

    def ilike(self, column: str, pattern: str) -> _Query:
        self._filters.append((column, "ILIKE", pattern))
        return self

    def in_(self, column: str, values: list) -> _Query:
        self._filters.append((column, "IN", values))
        return self

    def is_(self, column: str, value: Any) -> _Query:
        self._filters.append((column, "IS", value))
        return self

    def or_(self, filter_str: str) -> _Query:
        """兼容 Supabase 的 or_ 过滤，格式如 'col1.ilike.%val%,col2.ilike.%val%'"""
        self._or_filters.append(filter_str)
        return self

    # ---------- 排序/分页 ----------

    def order(self, column: str, options: Optional[Dict] = None,
              desc: bool = False, **kwargs) -> _Query:
        ascending = True
        if desc:
            ascending = False
        elif isinstance(options, dict) and "ascending" in options:
            ascending = bool(options["ascending"])
        elif "ascending" in kwargs:
            ascending = bool(kwargs["ascending"])
        self._orders.append((column, ascending))
        return self

    def limit(self, n: int) -> _Query:
        self._limit_val = int(n)
        return self

    def range(self, start: int, end: int) -> _Query:
        self._range_val = (start, end)
        return self

    def single(self) -> _Query:
        self._single = True
        self._limit_val = 1
        return self

    # ---------- 构建 SQL ----------

    def _build_where(self) -> Tuple[str, Dict[str, Any]]:
        """构建 WHERE 子句和参数"""
        clauses = []
        params: Dict[str, Any] = {}
        param_idx = 0

        for col, op, val in self._filters:
            pname = f"p{param_idx}"
            param_idx += 1

            if op == "IN":
                if not val:
                    clauses.append("FALSE")
                else:
                    placeholders = ", ".join(f":{pname}_{i}" for i in range(len(val)))
                    clauses.append(f'"{col}" IN ({placeholders})')
                    for i, v in enumerate(val):
                        params[f"{pname}_{i}"] = v
            elif op == "IS":
                if val is None:
                    clauses.append(f'"{col}" IS NULL')
                elif isinstance(val, bool):
                    clauses.append(f'"{col}" IS {"TRUE" if val else "FALSE"}')
                else:
                    clauses.append(f'"{col}" IS NULL')
            else:
                clauses.append(f'"{col}" {op} :{pname}')
                params[pname] = val

        # 处理 or_ 过滤器
        for or_str in self._or_filters:
            or_parts = []
            for part in or_str.split(","):
                part = part.strip()
                segments = part.split(".", 2)
                if len(segments) >= 3:
                    col, op_name, val = segments[0], segments[1], segments[2]
                    pname = f"p{param_idx}"
                    param_idx += 1
                    if op_name == "ilike":
                        or_parts.append(f'"{col}" ILIKE :{pname}')
                        params[pname] = val
                    elif op_name == "like":
                        or_parts.append(f'"{col}" LIKE :{pname}')
                        params[pname] = val
                    elif op_name == "eq":
                        or_parts.append(f'"{col}" = :{pname}')
                        params[pname] = val
                    elif op_name == "neq":
                        or_parts.append(f'"{col}" != :{pname}')
                        params[pname] = val
                    else:
                        or_parts.append(f'"{col}" = :{pname}')
                        params[pname] = val
            if or_parts:
                clauses.append(f"({' OR '.join(or_parts)})")

        where = " AND ".join(clauses) if clauses else ""
        return where, params

    def _build_select_sql(self) -> Tuple[str, Dict[str, Any]]:
        where, params = self._build_where()

        # 列选择（简化：忽略关系查询，只取字段名）
        if self._columns == "*":
            cols = "*"
        else:
            # 过滤掉 Supabase 关系语法如 "rel!inner(col)"
            col_parts = []
            for c in self._columns.split(","):
                c = c.strip()
                if "(" not in c:
                    col_parts.append(f'"{c}"' if c != "*" else "*")
            cols = ", ".join(col_parts) if col_parts else "*"

        sql = f'SELECT {cols} FROM "{self._table}"'
        if where:
            sql += f" WHERE {where}"

        for col, asc in self._orders:
            direction = "ASC" if asc else "DESC"
            sql += f' ORDER BY "{col}" {direction}'

        if self._range_val:
            offset = self._range_val[0]
            limit = self._range_val[1] - self._range_val[0] + 1
            sql += f" LIMIT {limit} OFFSET {offset}"
        elif self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"

        return sql, params

    def _build_count_sql(self) -> Tuple[str, Dict[str, Any]]:
        where, params = self._build_where()
        sql = f'SELECT COUNT(*) FROM "{self._table}"'
        if where:
            sql += f" WHERE {where}"
        return sql, params

    # ---------- 执行 ----------

    def execute(self) -> _Response:
        """同步执行"""
        session_factory = self._session_factory
        if session_factory is None:
            return _Response(data=[], count=0)

        session = session_factory()
        try:
            if self._method == "SELECT":
                return self._exec_select(session)
            elif self._method == "INSERT":
                return self._exec_insert(session)
            elif self._method == "UPDATE":
                return self._exec_update(session)
            elif self._method == "DELETE":
                return self._exec_delete(session)
            else:
                return _Response(data=[])
        except Exception as e:
            session.rollback()
            logger.error("SQL 执行错误 [%s on %s]: %s", self._method, self._table, e)
            raise
        finally:
            session.close()

    async def execute_async(self) -> _Response:
        """异步执行（在线程池中运行同步代码）"""
        from anyio import to_thread
        return await to_thread.run_sync(self.execute)

    def _exec_select(self, session) -> _Response:
        sql, params = self._build_select_sql()
        result = session.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result]

        count = None
        if self._count_mode:
            count_sql, count_params = self._build_count_sql()
            count_result = session.execute(text(count_sql), count_params)
            count = count_result.scalar()

        if self._single:
            data = rows[0] if rows else None
        else:
            data = rows

        return _Response(data=data, count=count)

    @staticmethod
    def _serialize_params(row: dict) -> dict:
        """将 dict/list 类型的值序列化为 JSON 字符串，防止 psycopg2 报错。"""
        import json as _json
        out = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)):
                out[k] = _json.dumps(v, ensure_ascii=False, default=str)
            else:
                out[k] = v
        return out

    def _exec_insert(self, session) -> _Response:
        payload = self._payload
        if isinstance(payload, dict):
            payload = [payload]

        if not payload:
            return _Response(data=[])

        results = []
        for row in payload:
            cols = list(row.keys())
            col_str = ", ".join(f'"{c}"' for c in cols)
            val_str = ", ".join(f":{c}" for c in cols)
            sql = f'INSERT INTO "{self._table}" ({col_str}) VALUES ({val_str}) RETURNING *'
            result = session.execute(text(sql), self._serialize_params(row))
            inserted = [dict(r._mapping) for r in result]
            results.extend(inserted)

        session.commit()
        return _Response(data=results)

    def _exec_update(self, session) -> _Response:
        if not self._payload:
            return _Response(data=[])

        where, params = self._build_where()
        set_parts = []
        for key, val in self._payload.items():
            pname = f"set_{key}"
            set_parts.append(f'"{key}" = :{pname}')
            # dict/list 需序列化为 JSON 字符串
            if isinstance(val, (dict, list)):
                import json as _json
                params[pname] = _json.dumps(val, ensure_ascii=False, default=str)
            else:
                params[pname] = val

        sql = f'UPDATE "{self._table}" SET {", ".join(set_parts)}'
        if where:
            sql += f" WHERE {where}"
        sql += " RETURNING *"

        result = session.execute(text(sql), params)
        rows = [dict(r._mapping) for r in result]
        session.commit()
        return _Response(data=rows)

    def _exec_delete(self, session) -> _Response:
        where, params = self._build_where()
        sql = f'DELETE FROM "{self._table}"'
        if where:
            sql += f" WHERE {where}"
        sql += " RETURNING *"

        result = session.execute(text(sql), params)
        rows = [dict(r._mapping) for r in result]
        session.commit()
        return _Response(data=rows)


# ==================== RPC 调用 ====================

class _RpcCall:
    """模拟 Supabase RPC 调用 — 映射为 PG 函数调用"""

    def __init__(self, session_factory, function_name: str, params: Optional[Dict] = None):
        self._session_factory = session_factory
        self._function_name = function_name
        self._params = params or {}

    def execute(self) -> _Response:
        session_factory = self._session_factory
        if session_factory is None:
            return _Response(data=None)

        session = session_factory()
        try:
            # 构建 SELECT function_name(param1 => :p1, ...)
            if self._params:
                param_str = ", ".join(f"{k} => :{k}" for k in self._params)
                sql = f"SELECT * FROM {self._function_name}({param_str})"
            else:
                sql = f"SELECT * FROM {self._function_name}()"

            result = session.execute(text(sql), self._params)
            rows = [dict(r._mapping) for r in result]
            return _Response(data=rows)
        except Exception as e:
            logger.error("RPC 执行错误 [%s]: %s", self._function_name, e)
            raise
        finally:
            session.close()

    async def execute_async(self) -> _Response:
        from anyio import to_thread
        return await to_thread.run_sync(self.execute)


# ==================== 主客户端 ====================

class _PgClient:
    """SQLAlchemy 版 Supabase 兼容客户端"""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def table(self, table_name: str) -> _Query:
        return _Query(self._session_factory, table_name)

    def rpc(self, function_name: str, params: Optional[Dict] = None) -> _RpcCall:
        return _RpcCall(self._session_factory, function_name, params)


# ==================== 公共 API（替代原 supabase_client.py） ====================

_client: Optional[_PgClient] = None


def get_supabase() -> Optional[_PgClient]:
    """获取数据库客户端（SQLAlchemy 适配版）

    返回值兼容原 Supabase Client 的链式 API：
        sb = get_supabase()
        sb.table("qc_tasks").select("*").eq("id", task_id).execute()

    24 个路由文件无需修改。
    """
    global _client
    if _client is not None:
        return _client

    session_factory = _get_session_factory()
    if session_factory is None:
        logger.warning("无法创建 SQLAlchemy 会话工厂，get_supabase() 返回 None")
        return None

    _client = _PgClient(session_factory)
    logger.info("SQLAlchemy 适配客户端已就绪（替代 Supabase）")
    return _client


async def async_execute(query):
    """统一的异步执行辅助函数（兼容原接口）

    - 若 query 提供 execute_async，直接 await
    - 否则在线程池中运行同步 execute
    """
    try:
        exec_async = getattr(query, "execute_async", None)
        if callable(exec_async):
            return await exec_async()
    except Exception:
        pass
    from anyio import to_thread
    return await to_thread.run_sync(query.execute)
