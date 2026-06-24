"""
统一错误处理中间件
处理所有类型的异常并返回统一格式的错误响应
"""

from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
import traceback
import uuid
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class UnifiedErrorMiddleware(BaseHTTPMiddleware):
    """
    统一错误处理中间件

    处理以下类型的异常：
    1. HTTPException - FastAPI HTTP 异常
    2. RequestValidationError - 请求验证错误
    3. Exception - 其他所有异常

    所有错误响应都包含 trace_id 用于追踪
    """

    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())

        # 将 trace_id 添加到请求状态，便于在路由中使用
        request.state.trace_id = trace_id

        try:
            response = await call_next(request)

            # 在响应头中添加 trace_id
            response.headers["X-Trace-ID"] = trace_id

            return response

        except HTTPException as e:
            # 处理 FastAPI HTTP 异常
            logger.warning(
                f"HTTP Exception: {e.status_code} - {e.detail}",
                extra={"trace_id": trace_id, "path": request.url.path}
            )

            return JSONResponse(
                status_code=e.status_code,
                content={
                    "success": False,
                    "error": e.detail,
                    "code": f"HTTP_{e.status_code}",
                    "trace_id": trace_id,
                },
                headers={"X-Trace-ID": trace_id}
            )

        except RequestValidationError as e:
            # 处理请求验证错误
            logger.warning(
                f"Validation Error: {e.errors()}",
                extra={"trace_id": trace_id, "path": request.url.path}
            )

            # 格式化验证错误信息
            errors = []
            for error in e.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                })

            return JSONResponse(
                status_code=HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "success": False,
                    "error": "请求参数验证失败",
                    "code": "VALIDATION_ERROR",
                    "trace_id": trace_id,
                    "details": errors
                },
                headers={"X-Trace-ID": trace_id}
            )

        except Exception as e:
            # 处理所有其他异常
            tb = traceback.format_exc()

            logger.error(
                f"Internal Server Error: {str(e)}",
                extra={"trace_id": trace_id, "path": request.url.path, "traceback": tb}
            )

            # 在生产环境中不暴露详细的错误信息
            error_detail = str(e) if logger.level == logging.DEBUG else "服务器内部错误"

            return JSONResponse(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": error_detail,
                    "code": "INTERNAL_ERROR",
                    "trace_id": trace_id,
                    # 只在调试模式下返回堆栈信息
                    **({"traceback": tb} if logger.level == logging.DEBUG else {})
                },
                headers={"X-Trace-ID": trace_id}
            )


