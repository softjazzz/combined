from typing import Optional, Dict, Any
from supabase import create_client, Client  # type: ignore
from .settings import get_settings
import logging
import os
import httpx
import ssl
import urllib3
from anyio import to_thread

# 仅在开发/显式允许时禁用 SSL 校验
_settings = None
try:
    _settings = get_settings()
except Exception:
    _settings = None

ALLOW_INSECURE_SSL = False
if _settings is not None:
    env = str(getattr(_settings, "ENV", "development")).lower()
    ALLOW_INSECURE_SSL = env != "production" or (os.getenv("ALLOW_INSECURE_SSL", "false").lower() == "true")
else:
    ALLOW_INSECURE_SSL = True

if ALLOW_INSECURE_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ssl._create_default_https_context = ssl._create_unverified_context

try:  # Optional import for constructing ClientOptions when create_client has incompatibility
    from supabase.lib.client_options import ClientOptions  # type: ignore
except Exception:  # pragma: no cover
    ClientOptions = None  # type: ignore

_supabase: Optional[Client] = None


def get_supabase() -> Optional[Client]:
    global _supabase
    if _supabase is not None:
        return _supabase
    settings = get_settings()
    # Fallback: if SUPABASE not set, try VITE_* (handled in settings already)
    # Prefer service role key for server-side access; fallback to anon
    api_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if settings.SUPABASE_URL and api_key:
        try:
            # 配置客户端选项，跳过SSL验证以解决证书问题
            client_options = {
                "postgrest": {
                    "headers": {"apikey": api_key}
                },
                "auth": {
                    "persistSession": False
                }
            }
            _supabase = create_client(
                str(settings.SUPABASE_URL),
                api_key,
                options=client_options
            )
            logging.getLogger(__name__).info("Supabase 客户端初始化成功: %s", settings.SUPABASE_URL)
        except TypeError as e:
            # 兼容部分版本的 supabase-py：create_client 内部传 proxy 导致报错
            if "proxy" in str(e) and ClientOptions is not None:
                try:
                    _supabase = Client(
                        str(settings.SUPABASE_URL),
                        api_key,
                        ClientOptions(),
                    )
                    logging.getLogger(__name__).info(
                        "Supabase 客户端初始化成功(兼容模式): %s", settings.SUPABASE_URL
                    )
                except Exception as e2:  # pragma: no cover
                    logging.getLogger(__name__).warning("Supabase 兼容初始化失败: %s", e2)
                    _supabase = None
            else:
                logging.getLogger(__name__).warning("Supabase 客户端初始化失败: %s", e)
                _supabase = None
        except Exception as e:
            logging.getLogger(__name__).warning("Supabase 客户端初始化失败: %s", e)
            _supabase = None

        # 最后一层兜底：使用 PostgREST 直连封装，覆盖本项目用到的最小方法集合
        if _supabase is None:
            try:
                class _RestResponse:
                    def __init__(self, data: Any, count: int | None = None) -> None:
                        self.data = data
                        self.count = count

                class _RestQuery:
                    def __init__(self, base_url: str, api_key: str, table: str) -> None:
                        self.base_url = base_url.rstrip("/")
                        self.api_key = api_key
                        self.table = table
                        self._select = "*"
                        self._filters: Dict[str, Any] = {}
                        self._method: str = "GET"
                        self._payload: Any = None
                        self._orders: list[tuple[str, bool]] = []  # (column, ascending)
                        self._limit: int | None = None
                        self._count: str | None = None  # 添加 count 支持
                        self._range: tuple[int, int] | None = None  # 添加 range 支持
                        self._single: bool = False  # 添加 single 支持

                    # 选择字段，支持传入 "id, col1, rel!inner(col)" 字符串，以及 count 参数
                    def select(self, columns: str = "*", count: str | None = None) -> "_RestQuery":
                        self._select = columns or "*"
                        self._method = "GET"
                        if count:
                            self._count = count  # 'exact', 'planned', 'estimated'
                        return self

                    # 删除操作，结合 eq 构造 where
                    def delete(self) -> "_RestQuery":
                        self._method = "DELETE"
                        return self

                    # 插入
                    def insert(self, payload: Any) -> "_RestQuery":
                        self._method = "POST"
                        self._payload = payload
                        return self

                    # 更新（最小实现，映射到 PATCH）
                    def update(self, payload: Any) -> "_RestQuery":
                        self._method = "PATCH"
                        self._payload = payload
                        return self

                    # 排序（最小实现）：支持 order("col", {"ascending": False}) 和 order("col", desc=True)
                    def order(self, column: str, options: Dict[str, Any] | None = None, desc: bool = False, **kwargs) -> "_RestQuery":
                        ascending = True

                        # 支持 desc 关键字参数
                        if desc:
                            ascending = False
                        # 支持 options 字典
                        elif isinstance(options, dict) and "ascending" in options:
                            try:
                                ascending = bool(options["ascending"])  # type: ignore[arg-type]
                            except Exception:
                                ascending = True
                        # 支持 ascending 关键字参数
                        elif "ascending" in kwargs:
                            ascending = bool(kwargs["ascending"])

                        self._orders.append((column, ascending))
                        return self

                    # 限制条数
                    def limit(self, n: int) -> "_RestQuery":
                        try:
                            self._limit = int(n)
                        except Exception:
                            self._limit = None
                        return self

                    # 等于过滤（仅支持最常用 eq）
                    def eq(self, column: str, value: Any) -> "_RestQuery":
                        self._filters[column] = value
                        return self

                    # IN 过滤（支持多个值），兼容 PostgREST 语法
                    def in_(self, column: str, values: list) -> "_RestQuery":
                        self._filters[column] = ("in", values)
                        return self

                    # IS 过滤（支持 None/True/False），兼容 PostgREST 语法
                    def is_(self, column: str, value: Any) -> "_RestQuery":
                        self._filters[column] = ("is", value)
                        return self

                    # Range 过滤（用于分页）
                    def range(self, start: int, end: int) -> "_RestQuery":
                        self._range = (start, end)
                        return self

                    # Single 方法（返回单条记录）
                    def single(self) -> "_RestQuery":
                        self._single = True
                        self._limit = 1
                        return self

                    def _headers(self) -> Dict[str, str]:
                        h = {
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                        }
                        if self._method in ("POST", "DELETE", "PATCH"):
                            h["Prefer"] = "return=representation"
                            h["Content-Type"] = "application/json"
                        # 添加 count 支持
                        if self._count:
                            h["Prefer"] = h.get("Prefer", "") + f",count={self._count}"
                        # 添加 Range 头
                        if self._range:
                            h["Range"] = f"{self._range[0]}-{self._range[1]}"
                        return h

                    async def execute_async(self) -> _RestResponse:  # type: ignore[name-defined]
                        """异步执行，减少在 FastAPI 事件循环中的阻塞。
                        若调用方无法 `await`，仍可使用同步版 `execute()`。
                        """
                        # 重要：PostgREST 参数顺序：select -> 过滤器 -> order -> limit
                        params = {}

                        # 1. select 参数
                        params["select"] = self._select

                        # 2. 过滤器参数（必须在 order 之前）
                        for k, v in self._filters.items():
                            if isinstance(v, tuple) and len(v) == 2:
                                op, val = v
                                if op == "is":
                                    if val is None:
                                        params[k] = "is.null"
                                    elif isinstance(val, bool):
                                        params[k] = f"is.{str(val).lower()}"
                                    else:
                                        params[k] = f"is.{val}"
                                elif op == "in":
                                    # IN 操作符：格式为 in.(value1,value2,value3)
                                    if isinstance(val, list):
                                        values_str = ",".join(str(item) for item in val)
                                        params[k] = f"in.({values_str})"
                                    else:
                                        params[k] = f"in.({val})"
                                else:
                                    params[k] = f"{op}.{val}"
                            else:
                                params[k] = f"eq.{v}"

                        # 3. order 参数
                        if self._orders:
                            order_parts = [f"{col}.{'asc' if asc else 'desc'}" for col, asc in self._orders]
                            params["order"] = ",".join(order_parts)

                        # 4. limit 参数
                        if self._limit is not None and not self._range:
                            params["limit"] = str(self._limit)
                        url = f"{self.base_url}/rest/v1/{self.table}"
                        async with httpx.AsyncClient(timeout=30) as c:  # 异步请求
                            if self._method == "GET":
                                r = await c.get(url, headers=self._headers(), params=params)
                            elif self._method == "POST":
                                r = await c.post(url, headers=self._headers(), params=params, json=self._payload)
                            elif self._method == "PATCH":
                                r = await c.patch(url, headers=self._headers(), params=params, json=self._payload)
                            elif self._method == "DELETE":
                                r = await c.delete(url, headers=self._headers(), params=params)
                            else:
                                raise RuntimeError("Unsupported method")
                            r.raise_for_status()
                            try:
                                data = r.json()
                            except Exception:
                                data = None

                            # 处理 count
                            count = None
                            if self._count:
                                content_range = r.headers.get("Content-Range")
                                if content_range:
                                    # Content-Range: 0-9/100
                                    parts = content_range.split("/")
                                    if len(parts) == 2:
                                        try:
                                            count = int(parts[1])
                                        except:
                                            pass

                            # 处理 single
                            if self._single and isinstance(data, list) and len(data) > 0:
                                data = data[0]

                            return _RestResponse(data, count)

                    def execute(self) -> _RestResponse:  # type: ignore[name-defined]
                        """同步执行（向后兼容）。
                        如在异步上下文中调用，仍为阻塞调用；建议改用 execute_async。
                        """
                        # 重要：PostgREST 参数顺序：select -> 过滤器 -> order -> limit
                        params = {}

                        # 1. select 参数
                        params["select"] = self._select

                        # 2. 过滤器参数（必须在 order 之前）
                        for k, v in self._filters.items():
                            if isinstance(v, tuple) and len(v) == 2:
                                op, val = v
                                if op == "is":
                                    if val is None:
                                        params[k] = "is.null"
                                    elif isinstance(val, bool):
                                        params[k] = f"is.{str(val).lower()}"
                                    else:
                                        params[k] = f"is.{val}"
                                elif op == "in":
                                    # IN 操作符：格式为 in.(value1,value2,value3)
                                    if isinstance(val, list):
                                        values_str = ",".join(str(item) for item in val)
                                        params[k] = f"in.({values_str})"
                                    else:
                                        params[k] = f"in.({val})"
                                else:
                                    params[k] = f"{op}.{val}"
                            else:
                                params[k] = f"eq.{v}"

                        # 3. order 参数
                        if self._orders:
                            order_parts = [f"{col}.{'asc' if asc else 'desc'}" for col, asc in self._orders]
                            params["order"] = ",".join(order_parts)

                        # 4. limit 参数
                        if self._limit is not None and not self._range:
                            params["limit"] = str(self._limit)
                        url = f"{self.base_url}/rest/v1/{self.table}"
                        with httpx.Client(timeout=30) as c:
                            if self._method == "GET":
                                r = c.get(url, headers=self._headers(), params=params)
                            elif self._method == "POST":
                                r = c.post(url, headers=self._headers(), params=params, json=self._payload)
                            elif self._method == "PATCH":
                                r = c.patch(url, headers=self._headers(), params=params, json=self._payload)
                            elif self._method == "DELETE":
                                r = c.delete(url, headers=self._headers(), params=params)
                            else:
                                raise RuntimeError("Unsupported method")
                            r.raise_for_status()
                            try:
                                data = r.json()
                            except Exception:
                                data = None

                            # 处理 count
                            count = None
                            if self._count:
                                content_range = r.headers.get("Content-Range")
                                if content_range:
                                    # Content-Range: 0-9/100
                                    parts = content_range.split("/")
                                    if len(parts) == 2:
                                        try:
                                            count = int(parts[1])
                                        except:
                                            pass

                            # 处理 single
                            if self._single and isinstance(data, list) and len(data) > 0:
                                data = data[0]

                            return _RestResponse(data, count)

                    class _RpcCall:
                        def __init__(self, base_url: str, api_key: str, function_name: str, params: Dict[str, Any]) -> None:
                            self.base_url = base_url.rstrip("/")
                            self.api_key = api_key
                            self.function_name = function_name
                            self.params = params or {}

                        def execute(self):
                            url = f"{self.base_url}/rest/v1/rpc/{self.function_name}"
                            headers = {
                                "apikey": self.api_key,
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                            }
                            with httpx.Client(verify=not ALLOW_INSECURE_SSL, timeout=30.0) as client:
                                r = client.post(url, json=self.params, headers=headers)
                                r.raise_for_status()
                                data = r.json() if r.text else None
                                return _RestResponse(data)

                        async def execute_async(self):
                            url = f"{self.base_url}/rest/v1/rpc/{self.function_name}"
                            headers = {
                                "apikey": self.api_key,
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                            }
                            async with httpx.AsyncClient(verify=not ALLOW_INSECURE_SSL, timeout=30.0) as client:
                                r = await client.post(url, json=self.params, headers=headers)
                                r.raise_for_status()
                                data = r.json() if r.text else None
                                return _RestResponse(data)


                class _RestClient:
                    def __init__(self, base_url: str, api_key: str) -> None:
                        self.base_url = base_url
                        self.api_key = api_key

                    def table(self, table_name: str) -> _RestQuery:  # type: ignore[name-defined]
                        return _RestQuery(self.base_url, self.api_key, table_name)

                    def rpc(self, function_name: str, params: Dict[str, Any] | None = None):  # type: ignore[name-defined]
                        base_url = self.base_url.rstrip("/")
                        api_key = self.api_key
                        fn = function_name
                        payload = params or {}

                        class _InlineRpc:
                            def execute(self_inner):
                                url = f"{base_url}/rest/v1/rpc/{fn}"
                                headers = {
                                    "apikey": api_key,
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                }
                                with httpx.Client(verify=not ALLOW_INSECURE_SSL, timeout=30.0) as client:
                                    r = client.post(url, json=payload, headers=headers)
                                    try:
                                        r.raise_for_status()
                                    except httpx.HTTPStatusError as e:  # pragma: no cover
                                        # 提供更详细的错误信息，便于排查 RPC 400/500
                                        detail = r.text
                                        raise Exception(f"RPC {fn} failed: {e} | Body: {detail}")
                                    data = r.json() if r.text else None
                                    return _RestResponse(data)

                            async def execute_async(self_inner):
                                url = f"{base_url}/rest/v1/rpc/{fn}"
                                headers = {
                                    "apikey": api_key,
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                }
                                async with httpx.AsyncClient(verify=not ALLOW_INSECURE_SSL, timeout=30.0) as client:
                                    r = await client.post(url, json=payload, headers=headers)
                                    try:
                                        r.raise_for_status()
                                    except httpx.HTTPStatusError as e:  # pragma: no cover
                                        detail = r.text
                                        raise Exception(f"RPC {fn} failed: {e} | Body: {detail}")
                                    data = r.json() if r.text else None
                                    return _RestResponse(data)

                        return _InlineRpc()

                _supabase = _RestClient(str(settings.SUPABASE_URL), api_key)
                logging.getLogger(__name__).info("Supabase REST 兼容客户端就绪: %s", settings.SUPABASE_URL)
            except Exception as e3:  # pragma: no cover
                logging.getLogger(__name__).warning("Supabase REST 兼容客户端初始化失败: %s", e3)
                _supabase = None
    return _supabase


async def async_execute(query):
    """统一的异步执行帮助函数。
    - 若 query 提供 execute_async，则直接 await 它。
    - 否则将同步 execute 放入线程池，避免阻塞事件循环。
    返回值保持与 supabase-py 一致，具备 data 字段。
    """
    try:
        exec_async = getattr(query, "execute_async", None)
        if callable(exec_async):
            return await exec_async()
    except Exception:
        pass
    return await to_thread.run_sync(query.execute)
