import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response


class TraceIDFilter(logging.Filter):
    """为日志记录添加 trace_id"""
    def filter(self, record):
        if not hasattr(record, 'trace_id'):
            record.trace_id = 'no-trace-id'
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """配置日志系统"""
    # 创建格式化器
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有的 handlers
    root_logger.handlers.clear()

    # 添加控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(TraceIDFilter())
    root_logger.addHandler(console_handler)

    # 配置 app.access logger
    access_logger = logging.getLogger("app.access")
    access_logger.setLevel(level)
    access_logger.propagate = True


def get_trace_id(request: Request) -> str:
    """获取或生成 trace_id"""
    # 优先从请求头获取
    trace_id = request.headers.get("X-Trace-ID")
    if trace_id:
        return trace_id

    # 从 request.state 获取
    if hasattr(request.state, "trace_id"):
        return request.state.trace_id

    # 生成新的 trace_id
    return str(uuid.uuid4())


async def request_logger_middleware(request: Request, call_next: Callable) -> Response:
    """
    请求日志中间件

    功能:
    1. 为每个请求生成唯一的 trace_id
    2. 记录请求开始信息
    3. 记录请求完成信息（状态码、耗时）
    4. 在响应头中添加 trace_id
    5. 将 trace_id 存储到 request.state 供其他中间件使用
    """
    # 生成或获取 trace_id
    trace_id = get_trace_id(request)
    request.state.trace_id = trace_id

    # 获取 logger
    logger = logging.getLogger("app.access")

    # 记录请求开始
    logger.info(
        "Request started",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "client": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )

    # 执行请求
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        # 记录异常
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": f"{duration:.2f}",
            },
            exc_info=True
        )
        raise

    # 计算耗时
    duration = (time.time() - start_time) * 1000

    # 记录请求完成
    log_level = logging.INFO if response.status_code < 400 else logging.WARNING
    logger.log(
        log_level,
        f"Request completed",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": f"{duration:.2f}",
        }
    )

    # 在响应头中添加 trace_id
    response.headers["X-Trace-ID"] = trace_id

    return response

