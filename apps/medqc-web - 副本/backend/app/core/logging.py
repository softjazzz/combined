import logging
import time
import re
import uuid
from typing import Callable
from fastapi import Request, Response

from .runtime_metrics import runtime_request_metrics


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


_TRACE_ID_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def _extract_traceparent_trace_id(traceparent: str) -> str | None:
    """从 W3C traceparent 头提取 trace-id，容错失败时返回 None。"""
    if not traceparent:
        return None

    parts = traceparent.strip().split("-")
    if len(parts) < 4:
        return None

    trace_id = parts[1]
    if not _TRACE_ID_HEX_PATTERN.fullmatch(trace_id):
        return None
    if trace_id.lower() == "0" * 32:
        return None
    return trace_id.lower()


def _extract_current_span_trace_id() -> str | None:
    """尝试从当前 OTel span context 提取 trace_id，失败时返回 None。"""
    try:
        from opentelemetry import trace as otel_trace  # type: ignore
    except Exception:
        return None

    try:
        span = otel_trace.get_current_span()
        span_context = span.get_span_context() if span else None
        if not span_context or not getattr(span_context, "is_valid", False):
            return None
        return f"{span_context.trace_id:032x}"
    except Exception:
        return None


def _attach_trace_to_current_span(trace_id: str, request: Request) -> None:
    """将当前请求 trace_id 挂载到 span attribute，便于日志与链路追踪关联。"""
    try:
        from opentelemetry import trace as otel_trace  # type: ignore
    except Exception:
        return

    try:
        span = otel_trace.get_current_span()
        span_context = span.get_span_context() if span else None
        if not span_context or not getattr(span_context, "is_valid", False):
            return
        span.set_attribute("medqc.trace_id", trace_id)
        span.set_attribute("http.request.method", request.method)
        span.set_attribute("url.path", request.url.path)
    except Exception:
        return


def get_trace_id(request: Request) -> str:
    """获取或生成 trace_id"""
    # 1) X-Trace-ID 优先透传
    trace_id = request.headers.get("X-Trace-ID")
    if trace_id and trace_id.strip():
        return trace_id

    # 2) 兼容 X-Request-ID
    request_id = request.headers.get("X-Request-ID")
    if request_id and request_id.strip():
        return request_id

    # 3) 兼容 W3C traceparent
    traceparent = request.headers.get("traceparent")
    parsed_trace_id = _extract_traceparent_trace_id(traceparent) if traceparent else None
    if parsed_trace_id:
        return parsed_trace_id

    # 从 request.state 获取（兜底）
    if hasattr(request.state, "trace_id"):
        return request.state.trace_id

    # 4) 若存在 OTel span context，优先复用其 trace_id 便于关联
    span_trace_id = _extract_current_span_trace_id()
    if span_trace_id:
        return span_trace_id

    # 5) 生成新的 trace_id
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
    _attach_trace_to_current_span(trace_id, request)

    # 获取 logger
    logger = logging.getLogger("app.access")

    # 记录请求开始
    runtime_request_metrics.mark_request_started()
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
        runtime_request_metrics.mark_request_finished(status_code=500, duration_ms=duration)
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": f"{duration:.2f}",
            },
            exc_info=True
        )
        raise

    # 计算耗时
    duration = (time.time() - start_time) * 1000
    runtime_request_metrics.mark_request_finished(status_code=response.status_code, duration_ms=duration)

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

