# API 请求日志使用指南

## 概述

本系统实现了统一的 API 请求日志中间件，用于记录所有 HTTP 请求的详细信息，提升系统的可观测性和可调试性。

---

## 功能特性

### 1. 自动 Trace ID 生成

每个请求都会自动生成一个唯一的 `trace_id`（UUID 格式），用于追踪请求的完整生命周期。

**特性**:
- ✅ 自动生成 UUID 格式的 trace_id
- ✅ 支持从请求头 `X-Trace-ID` 传入自定义 trace_id
- ✅ 在响应头中返回 `X-Trace-ID`
- ✅ 存储到 `request.state.trace_id` 供其他中间件使用

### 2. 请求生命周期日志

**请求开始日志**:
```
2025-10-09 07:50:19 - app.access - INFO - [abc-123-def] - Request started
```

记录信息：
- HTTP 方法（GET, POST, PUT, DELETE 等）
- 请求路径
- 查询参数
- 客户端 IP
- User-Agent

**请求完成日志**:
```
2025-10-09 07:50:19 - app.access - INFO - [abc-123-def] - Request completed
```

记录信息：
- HTTP 状态码
- 请求耗时（毫秒）
- 日志级别（成功=INFO，错误=WARNING）

**请求失败日志**:
```
2025-10-09 07:50:19 - app.access - ERROR - [abc-123-def] - Request failed: ValueError
```

记录信息：
- 异常类型和消息
- 完整的堆栈跟踪
- 请求耗时

### 3. 统一日志格式

所有日志都遵循统一格式：
```
%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] - %(message)s
```

示例：
```
2025-10-09 07:50:19 - app.access - INFO - [550e8400-e29b-41d4-a716-446655440000] - Request started
```

---

## 使用方法

### 1. 在路由中获取 Trace ID

```python
from fastapi import Request
from app.core.logging import get_trace_id

@app.get("/api/example")
async def example_endpoint(request: Request):
    trace_id = get_trace_id(request)
    logger.info(f"Processing request", extra={"trace_id": trace_id})
    return {"trace_id": trace_id}
```

### 2. 在业务逻辑中记录日志

```python
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

async def process_data(request: Request, data: dict):
    trace_id = request.state.trace_id
    
    logger.info(
        "Processing data",
        extra={
            "trace_id": trace_id,
            "data_size": len(data)
        }
    )
    
    # 业务逻辑...
    
    logger.info(
        "Data processed successfully",
        extra={"trace_id": trace_id}
    )
```

### 3. 在异常处理中使用 Trace ID

```python
from fastapi import HTTPException, Request

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", "unknown")
    
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={"trace_id": trace_id}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "trace_id": trace_id
        },
        headers={"X-Trace-ID": trace_id}
    )
```

### 4. 客户端传递 Trace ID

客户端可以在请求头中传递自定义的 trace_id：

```bash
curl -H "X-Trace-ID: my-custom-trace-123" http://localhost:8001/api/example
```

响应头中会返回相同的 trace_id：
```
X-Trace-ID: my-custom-trace-123
```

---

## 日志示例

### 成功请求

```
2025-10-09 07:50:19 - app.access - INFO - [550e8400-e29b-41d4-a716-446655440000] - Request started
2025-10-09 07:50:19 - app.business - INFO - [550e8400-e29b-41d4-a716-446655440000] - Processing quality control
2025-10-09 07:50:19 - app.access - INFO - [550e8400-e29b-41d4-a716-446655440000] - Request completed
```

### 失败请求

```
2025-10-09 07:50:19 - app.access - INFO - [550e8400-e29b-41d4-a716-446655440000] - Request started
2025-10-09 07:50:19 - app.business - ERROR - [550e8400-e29b-41d4-a716-446655440000] - Database connection failed
2025-10-09 07:50:19 - app.access - ERROR - [550e8400-e29b-41d4-a716-446655440000] - Request failed: ConnectionError
Traceback (most recent call last):
  ...
```

---

## 配置选项

### 修改日志级别

在 `app/main.py` 中：

```python
from app.core.logging import configure_logging
import logging

# 开发环境：详细日志
configure_logging(level=logging.DEBUG)

# 生产环境：只记录重要信息
configure_logging(level=logging.INFO)
```

### 自定义日志格式

在 `app/core/logging.py` 中修改 `configure_logging` 函数：

```python
formatter = logging.Formatter(
    fmt="%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
```

---

## 最佳实践

### 1. 始终传递 Trace ID

在所有日志记录中都应该包含 trace_id：

```python
# ✅ 好的做法
logger.info("Processing data", extra={"trace_id": trace_id})

# ❌ 不好的做法
logger.info("Processing data")  # 缺少 trace_id
```

### 2. 使用结构化日志

使用 `extra` 参数传递结构化数据：

```python
logger.info(
    "User action",
    extra={
        "trace_id": trace_id,
        "user_id": user.id,
        "action": "login",
        "ip": request.client.host
    }
)
```

### 3. 合理的日志级别

- `DEBUG`: 详细的调试信息
- `INFO`: 一般信息（请求开始/完成）
- `WARNING`: 警告信息（4xx 错误）
- `ERROR`: 错误信息（5xx 错误、异常）
- `CRITICAL`: 严重错误（系统崩溃）

### 4. 避免敏感信息

不要在日志中记录敏感信息：

```python
# ❌ 不要这样做
logger.info(f"User password: {password}")
logger.info(f"Credit card: {card_number}")

# ✅ 应该这样做
logger.info(f"User authenticated: {user_id}")
logger.info(f"Payment processed: {transaction_id}")
```

---

## 故障排查

### 问题 1: 日志中没有 trace_id

**原因**: 日志记录时没有传递 trace_id

**解决方案**:
```python
# 确保使用 extra 参数
logger.info("Message", extra={"trace_id": trace_id})
```

### 问题 2: 响应头中没有 X-Trace-ID

**原因**: 中间件顺序不正确

**解决方案**: 确保 `request_logger_middleware` 在其他中间件之前注册

### 问题 3: 日志格式不正确

**原因**: TraceIDFilter 未正确应用

**解决方案**: 检查 `configure_logging()` 是否在应用启动时调用

---

## 性能考虑

- ✅ 日志中间件对性能影响极小（< 1ms）
- ✅ 使用异步日志写入，不阻塞请求处理
- ✅ 生产环境建议使用 INFO 级别，避免过多 DEBUG 日志

---

## 相关文档

- [错误处理指南](ERROR_HANDLING_GUIDE.md)
- [中间件文档](../middleware/README.md)
- [FastAPI 日志文档](https://fastapi.tiangolo.com/tutorial/middleware/)

---

**最后更新**: 2025-10-09  
**维护者**: Backend Team

