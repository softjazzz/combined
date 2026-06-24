# 路由响应格式迁移指南

## 目标

将所有路由的响应格式统一为标准格式，使用 `success_response()` 和 `error_response()` 辅助函数。

## 标准响应格式

### 成功响应

```python
from app.core.response import success_response, get_trace_id

@router.get("/example")
async def example(request: Request):
    data = {"id": 1, "name": "示例"}
    return success_response(
        data=data,
        message="操作成功",  # 可选
        trace_id=get_trace_id(request)  # 可选但推荐
    )
```

### 错误响应

```python
from fastapi import HTTPException
from app.core.response import ErrorCode, StatusCode

@router.get("/example")
async def example():
    if not found:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="资源未找到"
        )
```

## 迁移步骤

### 1. 添加导入

在每个路由文件顶部添加：

```python
from fastapi import Request  # 如果还没有
from ..core.response import success_response, error_response, get_trace_id, ErrorCode, StatusCode
```

### 2. 更新函数签名

为每个路由函数添加 `request: Request` 参数（如果还没有）：

```python
# 旧代码
@router.get("/example")
async def example():
    ...

# 新代码
@router.get("/example")
async def example(request: Request):
    ...
```

### 3. 替换返回语句

#### 模式 1: 简单字典返回

```python
# 旧代码
return {"data": result}

# 新代码
return success_response(data=result, trace_id=get_trace_id(request))
```

#### 模式 2: 带 success 字段的返回

```python
# 旧代码
return {"success": True, "data": result, "message": "操作成功"}

# 新代码
return success_response(data=result, message="操作成功", trace_id=get_trace_id(request))
```

#### 模式 3: 直接返回数据

```python
# 旧代码
return {"id": 1, "name": "张三"}

# 新代码
return success_response(data={"id": 1, "name": "张三"}, trace_id=get_trace_id(request))
```

#### 模式 4: 列表返回

```python
# 旧代码
return {"items": items, "total": total}

# 新代码
return success_response(
    data={"items": items, "total": total},
    message="获取列表成功",
    trace_id=get_trace_id(request)
)
```

#### 模式 5: 分页返回

```python
# 旧代码
return {"data": items, "total": total, "page": page, "page_size": page_size}

# 新代码
from ..core.response import paginated_response

return paginated_response(
    items=items,
    total=total,
    page=page,
    page_size=page_size,
    trace_id=get_trace_id(request)
)
```

### 4. 更新错误处理

```python
# 旧代码
raise HTTPException(status_code=404, detail="未找到")

# 新代码
raise HTTPException(
    status_code=StatusCode.NOT_FOUND,
    detail="资源未找到"
)
```

## 路由文件清单

### ✅ 已完成

- [x] `system.py` - 系统健康检查和指标

### ⏳ 待更新

- [ ] `auth.py` - 认证授权
- [ ] `records.py` - 病案记录
- [ ] `medical_documents.py` - 医疗文书
- [ ] `qc.py` - 质控分析
- [ ] `qc_sichuan.py` - 四川省质控
- [ ] `semantic_rules.py` - 语义规则
- [ ] `llm_configs.py` - LLM 配置
- [ ] `llm_info.py` - LLM 信息
- [ ] `qc_llm_configs.py` - 质控 LLM 配置
- [ ] `tools.py` - 工具接口
- [ ] `ingest.py` - 数据导入
- [ ] `debug.py` - 调试接口
- [ ] `classification.py` - 文档分类
- [ ] `medical_records_alias.py` - 病案别名
- [ ] `reports.py` - 报告生成
- [ ] `tasks.py` - 任务管理
- [ ] `proxy.py` - 代理接口

## 验证清单

更新每个路由后，请确认：

- [ ] 所有返回语句都使用 `success_response()`
- [ ] 所有错误都使用 `HTTPException` 并使用 `StatusCode` 常量
- [ ] 所有路由函数都有 `request: Request` 参数
- [ ] 所有成功响应都包含 `trace_id`
- [ ] Python 语法检查通过
- [ ] 手动测试接口正常工作

## 测试

### 单元测试

```python
def test_example_endpoint():
    response = client.get("/api/example")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "trace_id" in data
```

### 手动测试

```bash
# 测试成功响应
curl http://localhost:8001/api/v1/health

# 预期输出
{
  "success": true,
  "data": {
    "status": "healthy",
    ...
  },
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## 常见问题

### Q: 是否所有响应都需要 trace_id？

A: 推荐所有响应都包含 trace_id，但不是强制的。对于简单的查询接口，可以省略。

### Q: 如何处理流式响应？

A: 流式响应（如 SSE）不需要使用 `success_response()`，保持原有格式即可。

### Q: 如何处理文件下载？

A: 文件下载使用 `FileResponse` 或 `StreamingResponse`，不需要使用 `success_response()`。

### Q: 旧的响应格式会影响前端吗？

A: 会的。更新后端后，需要同步更新前端的 API 调用代码。建议：
1. 先更新后端所有路由
2. 测试确认后端正常
3. 再更新前端代码

## 前端适配

前端需要更新 API 调用代码以处理新的响应格式：

```typescript
// 旧代码
const response = await fetch('/api/example')
const data = await response.json()
console.log(data.items)  // 直接访问数据

// 新代码
const response = await fetch('/api/example')
const result = await response.json()
if (result.success) {
  console.log(result.data.items)  // 从 data 字段访问
} else {
  console.error(result.error)
}
```

## 进度跟踪

- **总路由数**: 18
- **已完成**: 1
- **进度**: 5.6%
- **预计完成时间**: 20 小时


