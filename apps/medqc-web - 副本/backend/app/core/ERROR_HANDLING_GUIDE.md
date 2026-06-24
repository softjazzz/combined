# 错误处理使用指南

## 概述

本系统实现了统一的错误处理机制，包括：
1. 全局异常处理器
2. 统一错误响应格式
3. 请求追踪（trace_id）
4. 详细的错误日志

## 统一响应格式

### 成功响应

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "张三"
  },
  "message": "操作成功",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 错误响应

```json
{
  "success": false,
  "error": "用户不存在",
  "code": "USER_NOT_FOUND",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 验证错误响应

```json
{
  "success": false,
  "error": "请求参数验证失败",
  "code": "VALIDATION_ERROR",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "details": [
    {
      "field": "body.name",
      "message": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## 使用方法

### 1. 在路由中使用辅助函数

```python
from fastapi import APIRouter, HTTPException
from app.core.response import success_response, error_response, ErrorCode, StatusCode

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: int):
    # 查询用户
    user = await get_user_from_db(user_id)
    
    if not user:
        # 返回错误响应
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail=error_response(
                error="用户不存在",
                code=ErrorCode.USER_NOT_FOUND
            )["error"]
        )
    
    # 返回成功响应
    return success_response(
        data=user,
        message="获取用户成功"
    )
```

### 2. 使用 HTTPException

```python
from fastapi import HTTPException
from app.core.response import StatusCode

@router.post("/records")
async def create_record(record: RecordCreate):
    try:
        result = await create_record_in_db(record)
        return success_response(result, "创建成功")
    except ValueError as e:
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST,
            detail=str(e)
        )
```

### 3. 获取 trace_id

```python
from fastapi import Request
from app.core.response import get_trace_id

@router.get("/debug")
async def debug_endpoint(request: Request):
    trace_id = get_trace_id(request)
    
    # 在日志中使用 trace_id
    logger.info(f"Debug endpoint called", extra={"trace_id": trace_id})
    
    return success_response(
        data={"trace_id": trace_id},
        trace_id=trace_id
    )
```

### 4. 分页响应

```python
from app.core.response import paginated_response

@router.get("/records")
async def list_records(page: int = 1, page_size: int = 10):
    # 查询数据
    items, total = await get_records_paginated(page, page_size)
    
    return paginated_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        message="获取记录列表成功"
    )
```

## 错误代码

### 通用错误

| 代码 | 说明 | HTTP 状态码 |
|------|------|-------------|
| `INTERNAL_ERROR` | 服务器内部错误 | 500 |
| `VALIDATION_ERROR` | 请求参数验证失败 | 422 |
| `NOT_FOUND` | 资源未找到 | 404 |
| `UNAUTHORIZED` | 未授权 | 401 |
| `FORBIDDEN` | 禁止访问 | 403 |
| `BAD_REQUEST` | 错误的请求 | 400 |

### 业务错误

| 代码 | 说明 | HTTP 状态码 |
|------|------|-------------|
| `USER_NOT_FOUND` | 用户不存在 | 404 |
| `RECORD_NOT_FOUND` | 病案不存在 | 404 |
| `DOCUMENT_NOT_FOUND` | 文档不存在 | 404 |
| `RULE_NOT_FOUND` | 规则不存在 | 404 |

### 数据库错误

| 代码 | 说明 | HTTP 状态码 |
|------|------|-------------|
| `DATABASE_ERROR` | 数据库错误 | 500 |
| `DUPLICATE_ENTRY` | 重复条目 | 409 |

### 外部服务错误

| 代码 | 说明 | HTTP 状态码 |
|------|------|-------------|
| `LLM_API_ERROR` | LLM API 调用失败 | 502 |
| `SUPABASE_ERROR` | Supabase 错误 | 502 |

### 文件错误

| 代码 | 说明 | HTTP 状态码 |
|------|------|-------------|
| `FILE_NOT_FOUND` | 文件不存在 | 404 |
| `FILE_UPLOAD_ERROR` | 文件上传失败 | 400 |
| `FILE_PARSE_ERROR` | 文件解析失败 | 400 |

## 异常处理流程

```
请求 → 中间件 → 路由处理器
         ↓
    生成 trace_id
         ↓
    添加到 request.state
         ↓
    执行路由逻辑
         ↓
    发生异常？
         ↓
    是 → 异常处理器
         ↓
    HTTPException? → http_exception_handler
    ValidationError? → validation_exception_handler
    其他异常? → general_exception_handler
         ↓
    返回统一格式的错误响应
    （包含 trace_id）
```

## 日志记录

所有错误都会自动记录到日志中，包含：
- trace_id（用于追踪）
- 请求路径
- 错误消息
- 堆栈信息（仅在调试模式）

### 日志示例

```
WARNING - HTTP Exception: 404 - 资源未找到 - trace_id: 550e8400-e29b-41d4-a716-446655440000 - path: /api/users/999
ERROR - Internal Server Error: division by zero - trace_id: 550e8400-e29b-41d4-a716-446655440000 - path: /api/calculate
```

## 调试模式

在调试模式下（`logger.level == logging.DEBUG`），错误响应会包含详细的堆栈信息：

```json
{
  "success": false,
  "error": "division by zero",
  "code": "INTERNAL_ERROR",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "traceback": "Traceback (most recent call last):\n  File ..."
}
```

**注意**: 生产环境中不会返回堆栈信息，以避免泄露敏感信息。

## 最佳实践

### 1. 使用合适的错误代码

```python
# ✅ 好的做法
raise HTTPException(
    status_code=StatusCode.NOT_FOUND,
    detail="用户不存在"
)

# ❌ 不好的做法
raise HTTPException(status_code=400, detail="error")
```

### 2. 提供有意义的错误消息

```python
# ✅ 好的做法
raise HTTPException(
    status_code=StatusCode.BAD_REQUEST,
    detail="病案号格式不正确，应为8位数字"
)

# ❌ 不好的做法
raise HTTPException(status_code=400, detail="invalid input")
```

### 3. 在日志中使用 trace_id

```python
# ✅ 好的做法
trace_id = get_trace_id(request)
logger.error(
    f"Failed to process record",
    extra={"trace_id": trace_id, "record_id": record_id}
)

# ❌ 不好的做法
logger.error("Failed to process record")
```

### 4. 捕获特定异常

```python
# ✅ 好的做法
try:
    result = await process_data(data)
except ValueError as e:
    raise HTTPException(
        status_code=StatusCode.BAD_REQUEST,
        detail=str(e)
    )
except DatabaseError as e:
    raise HTTPException(
        status_code=StatusCode.INTERNAL_SERVER_ERROR,
        detail="数据库操作失败"
    )

# ❌ 不好的做法
try:
    result = await process_data(data)
except Exception:
    raise HTTPException(status_code=500, detail="error")
```

## 测试

运行错误处理测试：

```bash
# 使用 pytest
pytest app/core/test_error_handling.py -v

# 或直接运行
python app/core/test_error_handling.py
```

## 相关文件

- `app/core/middleware_errors.py` - 错误处理中间件
- `app/core/response.py` - 响应格式辅助函数
- `app/core/test_error_handling.py` - 错误处理测试
- `app/main.py` - 全局异常处理器注册

