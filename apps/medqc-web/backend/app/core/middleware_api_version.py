"""
API 版本控制中间件

功能:
- 提供向后兼容性，将 /api/* 请求重定向到 /api/v1/*
- 在响应头中添加 API 版本信息
- 记录使用旧版本 API 的请求
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from typing import Callable

logger = logging.getLogger(__name__)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    API 版本控制中间件

    特性:
    1. 自动将 /api/* 重定向到 /api/v1/*（向后兼容）
    2. 在响应头中添加 X-API-Version
    3. 记录使用旧版本 API 的请求（用于迁移监控）

    排除路径:
    - /api/v1/* (已包含版本号)
    - /docs, /redoc, /openapi.json (文档)
    - /downloads (静态文件)
    """

    def __init__(self, app, enable_legacy_redirect: bool = True):
        """
        初始化中间件

        Args:
            app: FastAPI 应用实例
            enable_legacy_redirect: 是否启用旧版本重定向（默认: True）
        """
        super().__init__(app)
        self.enable_legacy_redirect = enable_legacy_redirect

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件

        Returns:
            响应对象
        """
        path = request.url.path

        # 检查是否需要重定向（向后兼容）
        if self.enable_legacy_redirect and self._should_redirect(path):
            # 将 /api/* 重定向到 /api/v1/*
            new_path = path.replace("/api/", "/api/v1/", 1)

            # 记录使用旧版本 API 的请求
            trace_id = getattr(request.state, "trace_id", "unknown")
            logger.warning(
                f"Legacy API usage detected: {path} → {new_path}",
                extra={
                    "trace_id": trace_id,
                    "old_path": path,
                    "new_path": new_path,
                    "method": request.method,
                    "client": request.client.host if request.client else "unknown"
                }
            )

            # 构建新的 URL
            new_url = request.url.replace(path=new_path)

            # 返回重定向响应（307 保持请求方法）
            return RedirectResponse(url=str(new_url), status_code=307)

        # 处理请求
        response = await call_next(request)

        # 添加 API 版本信息到响应头
        response.headers["X-API-Version"] = "v1"

        return response

    def _should_redirect(self, path: str) -> bool:
        """
        判断是否需要重定向

        Args:
            path: 请求路径

        Returns:
            是否需要重定向
        """
        # 已经包含版本号的路径
        if "/api/v1/" in path:
            return False

        # 文档路径
        if path in ["/docs", "/redoc", "/openapi.json"]:
            return False

        # 静态文件路径
        if path.startswith("/downloads"):
            return False

        # 健康检查路径（/api/health）
        if path == "/api/health":
            return True

        # 其他 /api/* 路径
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            return True

        return False


def create_api_version_middleware(enable_legacy_redirect: bool = True):
    """
    创建 API 版本控制中间件工厂函数

    Args:
        enable_legacy_redirect: 是否启用旧版本重定向

    Returns:
        中间件类
    """
    class ConfiguredAPIVersionMiddleware(APIVersionMiddleware):
        def __init__(self, app):
            super().__init__(app, enable_legacy_redirect=enable_legacy_redirect)

    return ConfiguredAPIVersionMiddleware
