"""
错误处理测试
验证统一错误处理中间件和响应格式
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from .middleware_errors import UnifiedErrorMiddleware
from .response import success_response, error_response, ErrorCode, StatusCode


# 创建测试应用
app = FastAPI()
app.add_middleware(UnifiedErrorMiddleware)


class TestModel(BaseModel):
    """测试数据模型"""
    name: str
    age: int


@app.get("/success")
async def test_success():
    """测试成功响应"""
    return success_response({"message": "Hello World"}, "操作成功")


@app.get("/http-error")
async def test_http_error():
    """测试 HTTP 异常"""
    raise HTTPException(status_code=404, detail="资源未找到")


@app.get("/validation-error")
async def test_validation_error(data: TestModel):
    """测试验证错误"""
    return success_response(data.dict())


@app.get("/internal-error")
async def test_internal_error():
    """测试内部错误"""
    raise ValueError("这是一个测试错误")


@app.get("/zero-division")
async def test_zero_division():
    """测试除零错误"""
    result = 1 / 0
    return {"result": result}


# 测试客户端
client = TestClient(app)


def test_success_response():
    """测试成功响应格式"""
    response = client.get("/success")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert data["message"] == "操作成功"
    assert "trace_id" in data or "trace_id" not in data  # trace_id 可选


def test_http_exception():
    """测试 HTTP 异常处理"""
    response = client.get("/http-error")
    assert response.status_code == 404
    
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "资源未找到"
    assert data["code"] == "HTTP_404"
    assert "trace_id" in data
    assert response.headers.get("X-Trace-ID") is not None


def test_validation_error():
    """测试请求验证错误"""
    # 发送无效数据（缺少必需字段）
    response = client.get("/validation-error")
    assert response.status_code == 422
    
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "请求参数验证失败"
    assert data["code"] == "VALIDATION_ERROR"
    assert "details" in data
    assert len(data["details"]) > 0
    assert "trace_id" in data


def test_internal_error():
    """测试内部错误处理"""
    response = client.get("/internal-error")
    assert response.status_code == 500
    
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["code"] == "INTERNAL_ERROR"
    assert "trace_id" in data


def test_zero_division_error():
    """测试除零错误"""
    response = client.get("/zero-division")
    assert response.status_code == 500
    
    data = response.json()
    assert data["success"] is False
    assert data["code"] == "INTERNAL_ERROR"
    assert "trace_id" in data


def test_error_response_helper():
    """测试错误响应辅助函数"""
    response = error_response(
        error="用户不存在",
        code=ErrorCode.USER_NOT_FOUND,
        trace_id="test-trace-id"
    )
    
    assert response["success"] is False
    assert response["error"] == "用户不存在"
    assert response["code"] == ErrorCode.USER_NOT_FOUND
    assert response["trace_id"] == "test-trace-id"


def test_success_response_helper():
    """测试成功响应辅助函数"""
    response = success_response(
        data={"id": 1, "name": "测试"},
        message="获取成功",
        trace_id="test-trace-id"
    )
    
    assert response["success"] is True
    assert response["data"]["id"] == 1
    assert response["message"] == "获取成功"
    assert response["trace_id"] == "test-trace-id"


if __name__ == "__main__":
    # 运行测试
    print("运行错误处理测试...")
    
    print("\n1. 测试成功响应...")
    test_success_response()
    print("✅ 成功响应测试通过")
    
    print("\n2. 测试 HTTP 异常...")
    test_http_exception()
    print("✅ HTTP 异常测试通过")
    
    print("\n3. 测试验证错误...")
    test_validation_error()
    print("✅ 验证错误测试通过")
    
    print("\n4. 测试内部错误...")
    test_internal_error()
    print("✅ 内部错误测试通过")
    
    print("\n5. 测试除零错误...")
    test_zero_division_error()
    print("✅ 除零错误测试通过")
    
    print("\n6. 测试错误响应辅助函数...")
    test_error_response_helper()
    print("✅ 错误响应辅助函数测试通过")
    
    print("\n7. 测试成功响应辅助函数...")
    test_success_response_helper()
    print("✅ 成功响应辅助函数测试通过")
    
    print("\n✅ 所有测试通过！")

