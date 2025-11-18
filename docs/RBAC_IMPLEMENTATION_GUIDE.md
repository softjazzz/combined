# MedQC 权限系统优化实施指南

## 📋 目录

1. [后端权限装饰器实现](#1-后端权限装饰器实现)
2. [增强 RLS 策略](#2-增强-rls-策略)
3. [权限审计日志](#3-权限审计日志)
4. [使用示例](#4-使用示例)
5. [测试方案](#5-测试方案)
6. [部署步骤](#6-部署步骤)

---

## 1. 后端权限装饰器实现

### 1.1 创建权限管理模块

**文件**: `apps/medqc-web/backend/app/core/permissions.py`

```python
"""
权限管理模块
提供基于角色的访问控制 (RBAC) 功能
"""

from functools import wraps
from typing import List, Callable, Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from datetime import datetime
import logging

from .auth import get_current_user
from ..models.user import User

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
    },
}

# ============================================================================
# 权限检查函数
# ============================================================================

def has_permission(user: User, resource: str, action: str) -> bool:
    """
    检查用户是否有指定权限
    
    Args:
        user: 用户对象
        resource: 资源类型
        action: 操作类型
    
    Returns:
        bool: 是否有权限
    """
    if not user or not user.roles:
        return False
    
    # 检查用户的每个角色
    for role in user.roles:
        if role in ROLE_PERMISSIONS:
            resource_permissions = ROLE_PERMISSIONS[role].get(resource, [])
            if action in resource_permissions:
                return True
    
    return False

def has_role(user: User, role: str) -> bool:
    """
    检查用户是否有指定角色
    
    Args:
        user: 用户对象
        role: 角色名称
    
    Returns:
        bool: 是否有角色
    """
    if not user or not user.roles:
        return False
    return role in user.roles

def has_any_role(user: User, roles: List[str]) -> bool:
    """
    检查用户是否有任意一个指定角色
    
    Args:
        user: 用户对象
        roles: 角色列表
    
    Returns:
        bool: 是否有任意角色
    """
    if not user or not user.roles:
        return False
    return any(role in user.roles for role in roles)

def is_admin(user: User) -> bool:
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
                logger.warning(
                    f"权限拒绝: 用户 {current_user.email} 尝试 {action} 操作在 {resource} 资源上"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"没有权限执行 {action} 操作在 {resource} 资源上"
                )
            
            logger.info(
                f"权限允许: 用户 {current_user.email} 执行 {action} 操作在 {resource} 资源上"
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
                logger.warning(
                    f"角色拒绝: 用户 {current_user.email} (角色: {current_user.roles}) "
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
    user: User,
    resource: str,
    action: str,
    allowed: bool,
    reason: Optional[str] = None,
    request: Optional[Request] = None
):
    """
    记录权限检查日志
    
    Args:
        user: 用户对象
        resource: 资源类型
        action: 操作类型
        allowed: 是否允许
        reason: 拒绝原因
        request: 请求对象
    """
    log_data = {
        "user_id": user.id if user else None,
        "user_email": user.email if user else None,
        "user_roles": user.roles if user else [],
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

def get_user_permissions(user: User) -> Dict[str, List[str]]:
    """
    获取用户的所有权限
    
    Args:
        user: 用户对象
    
    Returns:
        Dict[str, List[str]]: 资源到操作列表的映射
    """
    if not user or not user.roles:
        return {}
    
    permissions = {}
    
    for role in user.roles:
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
    user: User,
    resource_owner_id: str,
    allow_admin: bool = True
) -> bool:
    """
    检查用户是否拥有资源
    
    Args:
        user: 用户对象
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
    return user.id == resource_owner_id
```

---

## 2. 增强 RLS 策略

### 2.1 创建迁移脚本

**文件**: `infra/supabase/medqc/migrations/007_enhance_rls_policies.sql`

```sql
-- ============================================================================
-- 增强 RLS 策略
-- 版本: 007
-- 描述: 实现基于角色的细粒度行级安全策略
-- ============================================================================

-- 1. 删除旧的简单策略
DROP POLICY IF EXISTS "认证用户可以查看医疗记录" ON medical_records;
DROP POLICY IF EXISTS "认证用户可以查看质控规则" ON qc_rules;
DROP POLICY IF EXISTS "认证用户可以查看质控结果" ON qc_results;

-- 2. 创建辅助函数

-- 获取用户角色
CREATE OR REPLACE FUNCTION get_user_roles(p_user_id UUID)
RETURNS TEXT[] AS $$
  SELECT ARRAY_AGG(role) 
  FROM user_roles 
  WHERE user_id = p_user_id;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 检查用户是否有指定角色
CREATE OR REPLACE FUNCTION has_role(p_user_id UUID, p_role TEXT)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = p_user_id AND role = p_role
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 检查用户是否有任意一个角色
CREATE OR REPLACE FUNCTION has_any_role(p_user_id UUID, p_roles TEXT[])
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_id = p_user_id AND role = ANY(p_roles)
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 3. Medical Records 策略

-- 管理员和质控人员可以查看所有记录
CREATE POLICY "admin_qc_view_all_medical_records" ON medical_records
  FOR SELECT
  USING (
    has_any_role(
      auth.uid(), 
      ARRAY['admin', 'qc_manager', 'qc_staff']
    )
  );

-- 医生只能查看自己创建的记录
CREATE POLICY "doctor_view_own_medical_records" ON medical_records
  FOR SELECT
  USING (
    has_role(auth.uid(), 'doctor') AND
    created_by = auth.uid()
  );

-- 管理员和质控管理员可以创建记录
CREATE POLICY "admin_qc_manager_create_medical_records" ON medical_records
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 管理员和质控管理员可以更新记录
CREATE POLICY "admin_qc_manager_update_medical_records" ON medical_records
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 只有管理员可以删除记录
CREATE POLICY "admin_delete_medical_records" ON medical_records
  FOR DELETE
  USING (has_role(auth.uid(), 'admin'));

-- 4. QC Rules 策略

-- 所有认证用户可以查看规则
CREATE POLICY "authenticated_view_qc_rules" ON qc_rules
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 管理员和质控管理员可以创建规则
CREATE POLICY "admin_qc_manager_create_qc_rules" ON qc_rules
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 管理员和质控管理员可以更新规则
CREATE POLICY "admin_qc_manager_update_qc_rules" ON qc_rules
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 只有管理员可以删除规则
CREATE POLICY "admin_delete_qc_rules" ON qc_rules
  FOR DELETE
  USING (has_role(auth.uid(), 'admin'));

-- 5. QC Results 策略

-- 所有认证用户可以查看质控结果
CREATE POLICY "authenticated_view_qc_results" ON qc_results
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 质控人员可以创建结果
CREATE POLICY "qc_staff_create_qc_results" ON qc_results
  FOR INSERT
  WITH CHECK (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager', 'qc_staff'])
  );

-- 质控人员可以更新结果
CREATE POLICY "qc_staff_update_qc_results" ON qc_results
  FOR UPDATE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager', 'qc_staff'])
  );

-- 管理员和质控管理员可以删除结果
CREATE POLICY "admin_qc_manager_delete_qc_results" ON qc_results
  FOR DELETE
  USING (
    has_any_role(auth.uid(), ARRAY['admin', 'qc_manager'])
  );

-- 6. User Roles 策略

-- 用户可以查看自己的角色
CREATE POLICY "users_view_own_roles" ON user_roles
  FOR SELECT
  USING (user_id = auth.uid());

-- 管理员可以查看所有角色
CREATE POLICY "admin_view_all_roles" ON user_roles
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

-- 只有管理员可以管理角色
CREATE POLICY "admin_manage_roles" ON user_roles
  FOR ALL
  USING (has_role(auth.uid(), 'admin'));

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE 'RLS 策略增强完成！';
  RAISE NOTICE '已创建基于角色的细粒度访问控制策略';
  RAISE NOTICE '==============================================';
END $$;
```

---

## 3. 权限审计日志

### 3.1 创建审计日志表

**文件**: `infra/supabase/medqc/migrations/008_add_permission_audit_logs.sql`

```sql
-- ============================================================================
-- 权限审计日志
-- 版本: 008
-- 描述: 创建权限审计日志表，记录所有权限检查操作
-- ============================================================================

-- 1. 创建权限审计日志表
CREATE TABLE IF NOT EXISTS permission_audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  user_email TEXT,
  user_roles TEXT[],
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  action TEXT NOT NULL,
  allowed BOOLEAN NOT NULL,
  reason TEXT,
  ip_address TEXT,
  user_agent TEXT,
  request_path TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建索引
CREATE INDEX idx_permission_audit_logs_user ON permission_audit_logs(user_id);
CREATE INDEX idx_permission_audit_logs_created ON permission_audit_logs(created_at DESC);
CREATE INDEX idx_permission_audit_logs_resource ON permission_audit_logs(resource_type, resource_id);
CREATE INDEX idx_permission_audit_logs_allowed ON permission_audit_logs(allowed);

-- 3. 创建审计日志视图
CREATE OR REPLACE VIEW permission_audit_summary AS
SELECT 
  user_email,
  resource_type,
  action,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN allowed THEN 1 ELSE 0 END) as allowed_count,
  SUM(CASE WHEN NOT allowed THEN 1 ELSE 0 END) as denied_count,
  MAX(created_at) as last_attempt
FROM permission_audit_logs
GROUP BY user_email, resource_type, action
ORDER BY last_attempt DESC;

-- 4. 创建清理旧日志的函数
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM permission_audit_logs
  WHERE created_at < NOW() - (days_to_keep || ' days')::INTERVAL;
  
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 5. 启用 RLS
ALTER TABLE permission_audit_logs ENABLE ROW LEVEL SECURITY;

-- 6. 创建 RLS 策略
-- 管理员可以查看所有审计日志
CREATE POLICY "admin_view_all_audit_logs" ON permission_audit_logs
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'));

-- 用户可以查看自己的审计日志
CREATE POLICY "users_view_own_audit_logs" ON permission_audit_logs
  FOR SELECT
  USING (user_id = auth.uid());

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '权限审计日志表创建完成！';
  RAISE NOTICE '已创建 permission_audit_logs 表和相关视图';
  RAISE NOTICE '==============================================';
END $$;
```

---

## 4. 使用示例

### 4.1 在 FastAPI 路由中使用

```python
# apps/medqc-web/backend/app/routers/medical_records.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..core.permissions import (
    require_permission,
    require_role,
    ResourceType,
    PermissionAction,
    UserRole,
)
from ..core.auth import get_current_user
from ..models.user import User
from ..models.medical_record import MedicalRecord, MedicalRecordCreate

router = APIRouter(prefix="/api/medical-records", tags=["medical-records"])

# 示例 1: 使用权限装饰器
@router.get("/", response_model=List[MedicalRecord])
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def list_records(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """获取医疗记录列表（需要读取权限）"""
    # 实现逻辑
    pass

# 示例 2: 使用角色装饰器
@router.post("/", response_model=MedicalRecord)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def create_record(
    record: MedicalRecordCreate,
    current_user: User = Depends(get_current_user)
):
    """创建医疗记录（需要管理员或质控管理员角色）"""
    # 实现逻辑
    pass

# 示例 3: 手动权限检查
@router.put("/{record_id}", response_model=MedicalRecord)
async def update_record(
    record_id: str,
    record: MedicalRecordCreate,
    current_user: User = Depends(get_current_user)
):
    """更新医疗记录"""
    from ..core.permissions import has_permission, check_resource_ownership
    
    # 检查基本权限
    if not has_permission(current_user, ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE):
        raise HTTPException(status_code=403, detail="没有更新权限")
    
    # 检查资源所有权
    existing_record = await get_record(record_id)
    if not check_resource_ownership(current_user, existing_record.created_by):
        raise HTTPException(status_code=403, detail="只能更新自己的记录")
    
    # 实现更新逻辑
    pass
```

---

## 5. 测试方案

### 5.1 单元测试

```python
# tests/test_permissions.py

import pytest
from app.core.permissions import (
    has_permission,
    has_role,
    ResourceType,
    PermissionAction,
    UserRole,
)
from app.models.user import User

def test_admin_has_all_permissions():
    """测试管理员拥有所有权限"""
    admin = User(id="1", email="admin@test.com", roles=[UserRole.ADMIN])
    
    assert has_permission(admin, ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
    assert has_permission(admin, ResourceType.QC_RULES, PermissionAction.DELETE)
    assert has_permission(admin, ResourceType.USERS, PermissionAction.MANAGE)

def test_qc_staff_limited_permissions():
    """测试质控专员权限限制"""
    qc_staff = User(id="2", email="qc@test.com", roles=[UserRole.QC_STAFF])
    
    # 应该有的权限
    assert has_permission(qc_staff, ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
    assert has_permission(qc_staff, ResourceType.QC_RESULTS, PermissionAction.CREATE)
    
    # 不应该有的权限
    assert not has_permission(qc_staff, ResourceType.MEDICAL_RECORDS, PermissionAction.DELETE)
    assert not has_permission(qc_staff, ResourceType.USERS, PermissionAction.MANAGE)

def test_doctor_permissions():
    """测试医生权限"""
    doctor = User(id="3", email="doctor@test.com", roles=[UserRole.DOCTOR])
    
    # 应该有的权限
    assert has_permission(doctor, ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
    assert has_permission(doctor, ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
    
    # 不应该有的权限
    assert not has_permission(doctor, ResourceType.QC_RULES, PermissionAction.UPDATE)
    assert not has_permission(doctor, ResourceType.USERS, PermissionAction.READ)
```

---

## 6. 部署步骤

### 6.1 部署清单

- [ ] 1. 创建权限管理模块 (`app/core/permissions.py`)
- [ ] 2. 执行数据库迁移 007 (增强 RLS 策略)
- [ ] 3. 执行数据库迁移 008 (权限审计日志)
- [ ] 4. 更新路由添加权限装饰器
- [ ] 5. 运行单元测试
- [ ] 6. 运行集成测试
- [ ] 7. 部署到测试环境
- [ ] 8. 验证权限功能
- [ ] 9. 部署到生产环境
- [ ] 10. 监控审计日志

### 6.2 部署命令

```bash
# 1. 执行数据库迁移
cd infra/supabase/medqc
psql -h your-db-host -U postgres -d medqc -f migrations/007_enhance_rls_policies.sql
psql -h your-db-host -U postgres -d medqc -f migrations/008_add_permission_audit_logs.sql

# 2. 运行测试
cd apps/medqc-web/backend
pytest tests/test_permissions.py -v

# 3. 重启后端服务
pm2 restart medqc-backend
```

---

**文档版本**: 1.0  
**最后更新**: 2025-10-11  
**维护者**: Augment Agent

