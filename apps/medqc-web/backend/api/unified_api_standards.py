# 统一API接口规范
# 定义所有API端点的统一响应格式、错误处理和性能监控标准

from typing import Any, Dict, List, Optional, TypeVar, Generic
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# API版本枚举
class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"  # 增强版API

# 响应状态枚举
class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

# 统一API响应模型
class UnifiedAPIResponse(BaseModel, Generic[T]):
    """统一的API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    status: ResponseStatus = Field(..., description="响应状态")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    errors: Optional[List[str]] = Field(None, description="错误信息列表")
    warnings: Optional[List[str]] = Field(None, description="警告信息列表")
    
    # 元数据
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间戳")
    request_id: Optional[str] = Field(None, description="请求ID")
    api_version: APIVersion = Field(APIVersion.V2, description="API版本")
    
    # 性能信息
    processing_time_ms: Optional[float] = Field(None, description="处理时间(毫秒)")
    cache_hit: Optional[bool] = Field(None, description="是否命中缓存")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# 分页响应模型
class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    items: List[T] = Field(..., description="数据项列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int
    ) -> 'PaginatedResponse[T]':
        """创建分页响应"""
        total_pages = (total + page_size - 1) // page_size
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )

# 错误详情模型
class ErrorDetail(BaseModel):
    """错误详情"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    field: Optional[str] = Field(None, description="相关字段")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")

# 统一错误响应模型
class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    success: bool = Field(False, description="请求是否成功")
    status: ResponseStatus = Field(ResponseStatus.ERROR, description="响应状态")
    message: str = Field(..., description="错误消息")
    error_code: str = Field(..., description="错误代码")
    error_details: Optional[List[ErrorDetail]] = Field(None, description="错误详情列表")
    
    # 元数据
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间戳")
    request_id: Optional[str] = Field(None, description="请求ID")
    api_version: APIVersion = Field(APIVersion.V2, description="API版本")
    
    # 调试信息（仅开发环境）
    debug_info: Optional[Dict[str, Any]] = Field(None, description="调试信息")

# 性能监控装饰器
def api_performance_monitor(operation_name: str):
    """API性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            request_id = kwargs.get('request_id', 'unknown')
            
            try:
                # 执行原函数
                result = await func(*args, **kwargs)
                
                # 计算处理时间
                processing_time = (time.time() - start_time) * 1000
                
                # 如果结果是UnifiedAPIResponse，添加性能信息
                if isinstance(result, UnifiedAPIResponse):
                    result.processing_time_ms = processing_time
                    result.request_id = request_id
                
                # 记录性能日志
                logger.info(
                    f"API性能监控 - 操作: {operation_name}, "
                    f"处理时间: {processing_time:.2f}ms, "
                    f"请求ID: {request_id}"
                )
                
                return result
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                
                # 记录错误日志
                logger.error(
                    f"API错误监控 - 操作: {operation_name}, "
                    f"处理时间: {processing_time:.2f}ms, "
                    f"错误: {str(e)}, "
                    f"请求ID: {request_id}",
                    exc_info=True
                )
                
                raise e
        
        return wrapper
    return decorator

# 统一成功响应创建器
def create_success_response(
    data: Any = None,
    message: str = "操作成功",
    cache_hit: bool = False,
    warnings: List[str] = None
) -> UnifiedAPIResponse:
    """创建成功响应"""
    return UnifiedAPIResponse(
        success=True,
        status=ResponseStatus.SUCCESS,
        message=message,
        data=data,
        warnings=warnings,
        cache_hit=cache_hit
    )

# 统一错误响应创建器
def create_error_response(
    message: str,
    error_code: str = "INTERNAL_ERROR",
    error_details: List[ErrorDetail] = None,
    debug_info: Dict[str, Any] = None
) -> ErrorResponse:
    """创建错误响应"""
    return ErrorResponse(
        message=message,
        error_code=error_code,
        error_details=error_details or [],
        debug_info=debug_info
    )

# 统一警告响应创建器
def create_warning_response(
    data: Any = None,
    message: str = "操作完成但有警告",
    warnings: List[str] = None
) -> UnifiedAPIResponse:
    """创建警告响应"""
    return UnifiedAPIResponse(
        success=True,
        status=ResponseStatus.WARNING,
        message=message,
        data=data,
        warnings=warnings or []
    )

# API路径规范
class APIPathStandards:
    """API路径规范"""
    
    # 基础路径
    BASE_PATH = "/api"
    
    # 版本路径
    V1_PATH = f"{BASE_PATH}/v1"
    V2_PATH = f"{BASE_PATH}/v2"
    
    # 增强版服务路径
    ENHANCED_AI_ASSISTANCE = f"{V2_PATH}/enhanced-ai-assistance"
    ENHANCED_AUDIT_TASKS = f"{V2_PATH}/enhanced-audit-tasks"
    
    # 兼容性路径（重定向到增强版）
    LEGACY_AI_ASSISTANCE = f"{V1_PATH}/ai-assistance"
    LEGACY_AUDIT_TASKS = f"{V1_PATH}/audit-tasks"
    
    # 系统管理路径
    SYSTEM_HEALTH = f"{BASE_PATH}/system/health"
    SYSTEM_METRICS = f"{BASE_PATH}/system/metrics"
    SYSTEM_STATUS = f"{BASE_PATH}/system/status"

# HTTP状态码规范
class HTTPStatusCodes:
    """HTTP状态码规范"""
    
    # 成功响应
    OK = 200                    # 请求成功
    CREATED = 201              # 资源创建成功
    ACCEPTED = 202             # 请求已接受，正在处理
    NO_CONTENT = 204           # 请求成功，无返回内容
    
    # 重定向
    MOVED_PERMANENTLY = 301    # 永久重定向
    FOUND = 302               # 临时重定向
    
    # 客户端错误
    BAD_REQUEST = 400         # 请求参数错误
    UNAUTHORIZED = 401        # 未授权
    FORBIDDEN = 403           # 禁止访问
    NOT_FOUND = 404           # 资源不存在
    METHOD_NOT_ALLOWED = 405  # 方法不允许
    CONFLICT = 409            # 资源冲突
    UNPROCESSABLE_ENTITY = 422 # 请求格式正确但语义错误
    TOO_MANY_REQUESTS = 429   # 请求过于频繁
    
    # 服务器错误
    INTERNAL_SERVER_ERROR = 500 # 内部服务器错误
    BAD_GATEWAY = 502          # 网关错误
    SERVICE_UNAVAILABLE = 503  # 服务不可用
    GATEWAY_TIMEOUT = 504      # 网关超时

# 请求头规范
class RequestHeaders:
    """请求头规范"""
    
    AUTHORIZATION = "Authorization"
    CONTENT_TYPE = "Content-Type"
    ACCEPT = "Accept"
    USER_AGENT = "User-Agent"
    REQUEST_ID = "X-Request-ID"
    API_VERSION = "X-API-Version"
    CLIENT_VERSION = "X-Client-Version"
    
    # 自定义头
    ENABLE_CACHE = "X-Enable-Cache"
    FORCE_REFRESH = "X-Force-Refresh"
    PERFORMANCE_TRACKING = "X-Performance-Tracking"

# 响应头规范
class ResponseHeaders:
    """响应头规范"""
    
    CONTENT_TYPE = "Content-Type"
    CACHE_CONTROL = "Cache-Control"
    ETAG = "ETag"
    LAST_MODIFIED = "Last-Modified"
    
    # 自定义头
    REQUEST_ID = "X-Request-ID"
    API_VERSION = "X-API-Version"
    PROCESSING_TIME = "X-Processing-Time-Ms"
    CACHE_HIT = "X-Cache-Hit"
    RATE_LIMIT_REMAINING = "X-RateLimit-Remaining"
    RATE_LIMIT_RESET = "X-RateLimit-Reset"

# 内容类型规范
class ContentTypes:
    """内容类型规范"""
    
    JSON = "application/json"
    XML = "application/xml"
    FORM_DATA = "multipart/form-data"
    URL_ENCODED = "application/x-www-form-urlencoded"
    TEXT_PLAIN = "text/plain"
    TEXT_HTML = "text/html"
    
    # 文件类型
    PDF = "application/pdf"
    EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    CSV = "text/csv"

# API版本兼容性管理
class APIVersionManager:
    """API版本兼容性管理"""
    
    @staticmethod
    def get_supported_versions() -> List[str]:
        """获取支持的API版本"""
        return [APIVersion.V1, APIVersion.V2]
    
    @staticmethod
    def get_latest_version() -> str:
        """获取最新API版本"""
        return APIVersion.V2
    
    @staticmethod
    def is_version_supported(version: str) -> bool:
        """检查版本是否支持"""
        return version in APIVersionManager.get_supported_versions()
    
    @staticmethod
    def get_deprecation_info(version: str) -> Optional[Dict[str, Any]]:
        """获取版本弃用信息"""
        if version == APIVersion.V1:
            return {
                "deprecated": True,
                "sunset_date": "2025-06-01",
                "migration_guide": "/docs/migration/v1-to-v2",
                "replacement_version": APIVersion.V2
            }
        return None
