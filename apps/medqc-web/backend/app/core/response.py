"""
统一响应格式辅助函数
提供标准化的 API 响应格式
"""

from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field
from fastapi import Request
import uuid


class ErrorDetail(BaseModel):
    """错误详情模型"""
    field: str = Field(..., description="错误字段")
    message: str = Field(..., description="错误消息")
    type: str = Field(..., description="错误类型")


class ApiResponse(BaseModel):
    """统一 API 响应模型"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[Any] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误消息")
    code: Optional[str] = Field(None, description="错误代码")
    trace_id: Optional[str] = Field(None, description="追踪ID")
    details: Optional[List[ErrorDetail]] = Field(None, description="详细错误信息")
    message: Optional[str] = Field(None, description="提示消息")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "示例"},
                "message": "操作成功"
            }
        }


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成成功响应
    
    Args:
        data: 响应数据
        message: 提示消息
        trace_id: 追踪ID
        
    Returns:
        统一格式的成功响应
        
    Example:
        >>> success_response({"id": 1, "name": "张三"}, "获取成功")
        {
            "success": True,
            "data": {"id": 1, "name": "张三"},
            "message": "获取成功"
        }
    """
    response = {
        "success": True,
        "data": data
    }
    
    if message:
        response["message"] = message
        
    if trace_id:
        response["trace_id"] = trace_id
        
    return response


def error_response(
    error: str,
    code: str = "ERROR",
    details: Optional[List[Dict[str, str]]] = None,
    trace_id: Optional[str] = None,
    status_code: int = 400
) -> Dict[str, Any]:
    """
    生成错误响应
    
    Args:
        error: 错误消息
        code: 错误代码
        details: 详细错误信息
        trace_id: 追踪ID
        status_code: HTTP 状态码（仅用于文档，实际状态码由 HTTPException 设置）
        
    Returns:
        统一格式的错误响应
        
    Example:
        >>> error_response("用户不存在", "USER_NOT_FOUND")
        {
            "success": False,
            "error": "用户不存在",
            "code": "USER_NOT_FOUND"
        }
    """
    response = {
        "success": False,
        "error": error,
        "code": code
    }
    
    if details:
        response["details"] = details
        
    if trace_id:
        response["trace_id"] = trace_id
        
    return response


def get_trace_id(request: Request) -> str:
    """
    从请求中获取或生成 trace_id
    
    Args:
        request: FastAPI Request 对象
        
    Returns:
        trace_id 字符串
    """
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def paginated_response(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 10,
    message: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成分页响应
    
    Args:
        items: 当前页的数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        message: 提示消息
        trace_id: 追踪ID
        
    Returns:
        统一格式的分页响应
        
    Example:
        >>> paginated_response([{"id": 1}, {"id": 2}], total=100, page=1, page_size=10)
        {
            "success": True,
            "data": {
                "items": [{"id": 1}, {"id": 2}],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10
            }
        }
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    response = {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    }
    
    if message:
        response["message"] = message
        
    if trace_id:
        response["trace_id"] = trace_id
        
    return response


# 常用错误代码常量
class ErrorCode:
    """错误代码常量"""
    
    # 通用错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    
    # 业务错误
    USER_NOT_FOUND = "USER_NOT_FOUND"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    RULE_NOT_FOUND = "RULE_NOT_FOUND"
    
    # 数据库错误
    DATABASE_ERROR = "DATABASE_ERROR"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    
    # 外部服务错误
    LLM_API_ERROR = "LLM_API_ERROR"
    SUPABASE_ERROR = "SUPABASE_ERROR"
    
    # 文件错误
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_UPLOAD_ERROR = "FILE_UPLOAD_ERROR"
    FILE_PARSE_ERROR = "FILE_PARSE_ERROR"


# 常用 HTTP 状态码
class StatusCode:
    """HTTP 状态码常量"""
    
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503

