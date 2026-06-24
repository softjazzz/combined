"""
权限管理模块
提供基于角色的访问控制 (RBAC) 功能
"""

from functools import wraps
from typing import List, Callable, Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from datetime import datetime
import logging

from .security import get_current_user

logger = logging.getLogger(__name__)

# ============================================================================
# 权限常量定义
# ============================================================================

class ResourceType:
    """资源类型"""
    MEDICAL_RECORDS = "medical_records"
    QC_RESULTS = "qc_results"
    QC_RULES = "qc_rules"
    USERS = "users"
    STATISTICS = "statistics"
    SETTINGS = "settings"

class PermissionAction:
    """权限操作"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ANALYZE = "analyze"
    REVIEW = "review"
    MANAGE = "manage"
    EXPORT = "export"

class UserRole:
    """用户角色"""
    ADMIN = "admin"
    QC_MANAGER = "qc_manager"
    QC_STAFF = "qc_staff"
    DOCTOR = "doctor"

# ============================================================================
# 角色权限映射
# ============================================================================

ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    UserRole.ADMIN: {
        # 管理员拥有所有权限
        ResourceType.MEDICAL_RECORDS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.ANALYZE,
            PermissionAction.EXPORT,
        ],
        ResourceType.QC_RESULTS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.REVIEW,
            PermissionAction.EXPORT,
        ],
        ResourceType.QC_RULES: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.MANAGE,
        ],
        ResourceType.USERS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.MANAGE,
        ],
        ResourceType.STATISTICS: [
            PermissionAction.READ,
            PermissionAction.EXPORT,
        ],
        ResourceType.SETTINGS: [
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.MANAGE,
        ],
    },
    
    UserRole.QC_MANAGER: {
        # 质控管理员权限
        ResourceType.MEDICAL_RECORDS: [
            PermissionAction.READ,
            PermissionAction.ANALYZE,
            PermissionAction.EXPORT,
        ],
        ResourceType.QC_RESULTS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
            PermissionAction.REVIEW,
            PermissionAction.EXPORT,
        ],
        ResourceType.QC_RULES: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
            PermissionAction.DELETE,
        ],
        ResourceType.USERS: [
            PermissionAction.READ,
        ],
        ResourceType.STATISTICS: [
            PermissionAction.READ,
            PermissionAction.EXPORT,
        ],
        ResourceType.SETTINGS: [
            PermissionAction.READ,
        ],
    },
    
    UserRole.QC_STAFF: {
        # 质控专员权限
        ResourceType.MEDICAL_RECORDS: [
            PermissionAction.READ,
            PermissionAction.ANALYZE,
        ],
        ResourceType.QC_RESULTS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
        ],
        ResourceType.QC_RULES: [
            PermissionAction.READ,
        ],
        ResourceType.STATISTICS: [
            PermissionAction.READ,
        ],
    },
    
    UserRole.DOCTOR: {
        # 医生权限
        ResourceType.MEDICAL_RECORDS: [
            PermissionAction.CREATE,
            PermissionAction.READ,
            PermissionAction.UPDATE,
        ],
        ResourceType.QC_RESULTS: [
            PermissionAction.READ,
        ],
        ResourceType.QC_RULES: [
            PermissionAction.READ,
        ],
    },
}

# ============================================================================
# 权限检查函数
# ============================================================================

def has_permission(user: Dict[str, Any], resource: str, action: str) -> bool:
    """
    检查用户是否有指定权限

    Args:
        user: 用户字典对象
        resource: 资源类型
        action: 操作类型

    Returns:
        bool: 是否有权限
    """
    if not user:
        return False

    user_roles = user.get('roles', [])
    if not user_roles:
        return False

    # 检查用户的每个角色
    for role in user_roles:
        if role in ROLE_PERMISSIONS:
            resource_permissions = ROLE_PERMISSIONS[role].get(resource, [])
            if action in resource_permissions:
                return True

    return False

def has_role(user: Dict[str, Any], role: str) -> bool:
    """
    检查用户是否有指定角色

    Args:
        user: 用户字典对象
        role: 角色名称

    Returns:
        bool: 是否有角色
    """
    if not user:
        return False

    user_roles = user.get('roles', [])
    return role in user_roles

def has_any_role(user: Dict[str, Any], roles: List[str]) -> bool:
    """
    检查用户是否有任意一个指定角色

    Args:
        user: 用户字典对象
        roles: 角色列表

    Returns:
        bool: 是否有任意角色
    """
    if not user:
        return False

    user_roles = user.get('roles', [])
    return any(role in user_roles for role in roles)

def is_admin(user: Dict[str, Any]) -> bool:
    """检查是否为管理员"""
    return has_role(user, UserRole.ADMIN)

# ============================================================================
# 权限装饰器
# ============================================================================

def require_permission(resource: str, action: str):
    """
    权限检查装饰器
    
    用法:
        @require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
        async def create_record(
            record: RecordCreate,
            current_user: User = Depends(get_current_user)
        ):
            pass
    
    Args:
        resource: 资源类型
        action: 操作类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中获取 current_user
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证的用户"
                )
            
            if not has_permission(current_user, resource, action):
                user_email = current_user.get('email', 'unknown')
                logger.warning(
                    f"权限拒绝: 用户 {user_email} 尝试 {action} 操作在 {resource} 资源上"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"没有权限执行 {action} 操作在 {resource} 资源上"
                )

            user_email = current_user.get('email', 'unknown')
            logger.info(
                f"权限允许: 用户 {user_email} 执行 {action} 操作在 {resource} 资源上"
            )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_role(roles: List[str]):
    """
    角色检查装饰器
    
    用法:
        @require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
        async def manage_rules(
            current_user: User = Depends(get_current_user)
        ):
            pass
    
    Args:
        roles: 允许的角色列表
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="未认证的用户"
                )
            
            if not has_any_role(current_user, roles):
                user_email = current_user.get('email', 'unknown')
                user_roles = current_user.get('roles', [])
                logger.warning(
                    f"角色拒绝: 用户 {user_email} (角色: {user_roles}) "
                    f"尝试访问需要角色 {roles} 的资源"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"需要以下角色之一: {', '.join(roles)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_admin():
    """
    管理员权限装饰器

    用法:
        @require_admin()
        async def admin_only_action(
            current_user: User = Depends(get_current_user)
        ):
            pass
    """
    return require_role([UserRole.ADMIN])

# ============================================================================
# 权限审计
# ============================================================================

async def log_permission_check(
    user: Dict[str, Any],
    resource: str,
    action: str,
    allowed: bool,
    reason: Optional[str] = None,
    request: Optional[Request] = None
):
    """
    记录权限检查日志

    Args:
        user: 用户字典对象
        resource: 资源类型
        action: 操作类型
        allowed: 是否允许
        reason: 拒绝原因
        request: 请求对象
    """
    log_data = {
        "user_id": user.get('id') if user else None,
        "user_email": user.get('email') if user else None,
        "user_roles": user.get('roles', []) if user else [],
        "resource": resource,
        "action": action,
        "allowed": allowed,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if request:
        log_data["ip_address"] = request.client.host if request.client else None
        log_data["user_agent"] = request.headers.get("user-agent")
        log_data["path"] = request.url.path

    # 这里可以写入数据库或日志文件
    logger.info(f"权限审计: {log_data}")

    # TODO: 写入数据库
    # await db.execute(
    #     "INSERT INTO permission_audit_logs (...) VALUES (...)",
    #     log_data
    # )

# ============================================================================
# 辅助函数
# ============================================================================

def get_user_permissions(user: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    获取用户的所有权限

    Args:
        user: 用户字典对象

    Returns:
        Dict[str, List[str]]: 资源到操作列表的映射
    """
    if not user:
        return {}

    user_roles = user.get('roles', [])
    if not user_roles:
        return {}

    permissions = {}

    for role in user_roles:
        if role in ROLE_PERMISSIONS:
            for resource, actions in ROLE_PERMISSIONS[role].items():
                if resource not in permissions:
                    permissions[resource] = []
                permissions[resource].extend(actions)

    # 去重
    for resource in permissions:
        permissions[resource] = list(set(permissions[resource]))

    return permissions

def check_resource_ownership(
    user: Dict[str, Any],
    resource_owner_id: str,
    allow_admin: bool = True
) -> bool:
    """
    检查用户是否拥有资源

    Args:
        user: 用户字典对象
        resource_owner_id: 资源所有者 ID
        allow_admin: 是否允许管理员访问

    Returns:
        bool: 是否拥有资源
    """
    if not user:
        return False

    # 管理员可以访问所有资源
    if allow_admin and is_admin(user):
        return True

    # 检查是否为资源所有者
    return user.get('id') == resource_owner_id

