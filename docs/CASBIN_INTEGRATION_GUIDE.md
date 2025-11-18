# Casbin 集成指南（可选方案）

> ⚠️ **注意**: 这是一个可选的高级方案，仅在需要复杂权限管理时考虑使用

## 📋 目录

1. [何时使用 Casbin](#1-何时使用-casbin)
2. [Casbin 基础概念](#2-casbin-基础概念)
3. [集成步骤](#3-集成步骤)
4. [配置示例](#4-配置示例)
5. [使用示例](#5-使用示例)
6. [性能优化](#6-性能优化)
7. [最佳实践](#7-最佳实践)

---

## 1. 何时使用 Casbin

### ✅ 适合使用 Casbin 的场景

1. **复杂权限规则**
   - 需要基于资源属性的权限控制（ABAC）
   - 需要基于时间、地点的动态权限
   - 需要复杂的权限继承关系

2. **多租户系统**
   - 不同医院有不同的权限配置
   - 需要租户级别的权限隔离
   - 需要动态添加/删除租户

3. **动态权限管理**
   - 需要在运行时修改权限而不重启系统
   - 需要通过 UI 配置权限
   - 需要权限版本管理

4. **大规模部署**
   - 多个医院实例
   - 需要统一的权限管理平台
   - 需要权限审计和合规性

### ❌ 不适合使用 Casbin 的场景

1. **简单权限需求**
   - 只有 4-5 个固定角色
   - 权限规则简单明确
   - 不需要动态修改

2. **性能敏感**
   - 每秒数千次权限检查
   - 延迟要求 < 1ms
   - 资源受限环境

3. **团队经验不足**
   - 团队不熟悉 Casbin
   - 缺少维护经验
   - 快速迭代阶段

---

## 2. Casbin 基础概念

### 2.1 核心组件

```
┌─────────────────────────────────────────────────┐
│                   Casbin                        │
├─────────────────────────────────────────────────┤
│  Model (模型)                                    │
│  ├─ Request Definition (请求定义)                │
│  ├─ Policy Definition (策略定义)                 │
│  ├─ Role Definition (角色定义)                   │
│  ├─ Policy Effect (策略效果)                     │
│  └─ Matchers (匹配器)                           │
├─────────────────────────────────────────────────┤
│  Policy (策略)                                   │
│  ├─ p: 权限策略                                  │
│  └─ g: 角色继承                                  │
├─────────────────────────────────────────────────┤
│  Adapter (适配器)                                │
│  └─ PostgreSQL / MySQL / Redis                 │
└─────────────────────────────────────────────────┘
```

### 2.2 权限模型类型

| 模型 | 说明 | 适用场景 |
|------|------|----------|
| **ACL** | 访问控制列表 | 简单的用户-资源权限 |
| **RBAC** | 基于角色的访问控制 | 用户-角色-权限 |
| **ABAC** | 基于属性的访问控制 | 复杂的条件判断 |
| **RESTful** | RESTful API 权限 | API 接口权限控制 |

---

## 3. 集成步骤

### 3.1 安装依赖

```bash
# Python 后端
cd apps/medqc-web/backend
pip install casbin==1.36.2
pip install casbin-sqlalchemy-adapter==1.5.0
pip install sqlalchemy==2.0.23

# 更新 requirements.txt
cat >> requirements.txt << EOF
casbin==1.36.2
casbin-sqlalchemy-adapter==1.5.0
sqlalchemy==2.0.23
EOF
```

### 3.2 创建数据库表

```sql
-- infra/supabase/medqc/migrations/009_add_casbin_tables.sql

-- Casbin 策略表
CREATE TABLE IF NOT EXISTS casbin_rule (
    id SERIAL PRIMARY KEY,
    ptype VARCHAR(100) NOT NULL,
    v0 VARCHAR(100),
    v1 VARCHAR(100),
    v2 VARCHAR(100),
    v3 VARCHAR(100),
    v4 VARCHAR(100),
    v5 VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_casbin_rule_ptype ON casbin_rule(ptype);
CREATE INDEX idx_casbin_rule_v0 ON casbin_rule(v0);
CREATE INDEX idx_casbin_rule_v1 ON casbin_rule(v1);

-- 启用 RLS
ALTER TABLE casbin_rule ENABLE ROW LEVEL SECURITY;

-- 只有管理员可以管理 Casbin 规则
CREATE POLICY "admin_manage_casbin_rules" ON casbin_rule
  FOR ALL
  USING (has_role(auth.uid(), 'admin'));

COMMENT ON TABLE casbin_rule IS 'Casbin 权限策略存储表';
```

### 3.3 创建 Casbin 模型

```ini
# apps/medqc-web/backend/app/core/casbin_model.conf

[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

### 3.4 创建 Casbin 管理器

```python
# apps/medqc-web/backend/app/core/casbin_manager.py

"""
Casbin 权限管理器
提供基于 Casbin 的动态权限控制
"""

import casbin
from casbin_sqlalchemy_adapter import Adapter
from sqlalchemy import create_engine
from typing import List, Optional
import logging
from pathlib import Path

from ..config import get_settings

logger = logging.getLogger(__name__)

class CasbinManager:
    """Casbin 权限管理器"""
    
    _instance = None
    _enforcer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._enforcer is None:
            self._initialize()
    
    def _initialize(self):
        """初始化 Casbin"""
        try:
            settings = get_settings()
            
            # 创建数据库引擎
            engine = create_engine(settings.database_url)
            
            # 创建适配器
            adapter = Adapter(engine)
            
            # 模型文件路径
            model_path = Path(__file__).parent / "casbin_model.conf"
            
            # 创建执行器
            self._enforcer = casbin.Enforcer(str(model_path), adapter)
            
            # 加载策略
            self._enforcer.load_policy()
            
            logger.info("Casbin 初始化成功")
            
        except Exception as e:
            logger.error(f"Casbin 初始化失败: {e}")
            raise
    
    @property
    def enforcer(self):
        """获取 Casbin 执行器"""
        return self._enforcer
    
    # ========================================================================
    # 权限检查
    # ========================================================================
    
    def enforce(self, user_id: str, resource: str, action: str) -> bool:
        """
        检查用户权限
        
        Args:
            user_id: 用户 ID
            resource: 资源
            action: 操作
        
        Returns:
            bool: 是否有权限
        """
        try:
            return self._enforcer.enforce(user_id, resource, action)
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False
    
    # ========================================================================
    # 策略管理
    # ========================================================================
    
    def add_policy(self, user_id: str, resource: str, action: str) -> bool:
        """
        添加权限策略
        
        Args:
            user_id: 用户 ID
            resource: 资源
            action: 操作
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.add_policy(user_id, resource, action)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"添加策略失败: {e}")
            return False
    
    def remove_policy(self, user_id: str, resource: str, action: str) -> bool:
        """
        删除权限策略
        
        Args:
            user_id: 用户 ID
            resource: 资源
            action: 操作
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.remove_policy(user_id, resource, action)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"删除策略失败: {e}")
            return False
    
    def get_policies_for_user(self, user_id: str) -> List[List[str]]:
        """
        获取用户的所有权限策略
        
        Args:
            user_id: 用户 ID
        
        Returns:
            List[List[str]]: 策略列表
        """
        try:
            return self._enforcer.get_permissions_for_user(user_id)
        except Exception as e:
            logger.error(f"获取用户策略失败: {e}")
            return []
    
    # ========================================================================
    # 角色管理
    # ========================================================================
    
    def add_role_for_user(self, user_id: str, role: str) -> bool:
        """
        为用户添加角色
        
        Args:
            user_id: 用户 ID
            role: 角色
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.add_grouping_policy(user_id, role)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"添加角色失败: {e}")
            return False
    
    def remove_role_for_user(self, user_id: str, role: str) -> bool:
        """
        删除用户角色
        
        Args:
            user_id: 用户 ID
            role: 角色
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.remove_grouping_policy(user_id, role)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"删除角色失败: {e}")
            return False
    
    def get_roles_for_user(self, user_id: str) -> List[str]:
        """
        获取用户的所有角色
        
        Args:
            user_id: 用户 ID
        
        Returns:
            List[str]: 角色列表
        """
        try:
            return self._enforcer.get_roles_for_user(user_id)
        except Exception as e:
            logger.error(f"获取用户角色失败: {e}")
            return []
    
    def get_users_for_role(self, role: str) -> List[str]:
        """
        获取拥有指定角色的所有用户
        
        Args:
            role: 角色
        
        Returns:
            List[str]: 用户 ID 列表
        """
        try:
            return self._enforcer.get_users_for_role(role)
        except Exception as e:
            logger.error(f"获取角色用户失败: {e}")
            return []
    
    # ========================================================================
    # 批量操作
    # ========================================================================
    
    def add_policies(self, policies: List[List[str]]) -> bool:
        """
        批量添加策略
        
        Args:
            policies: 策略列表 [[user_id, resource, action], ...]
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.add_policies(policies)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"批量添加策略失败: {e}")
            return False
    
    def remove_policies(self, policies: List[List[str]]) -> bool:
        """
        批量删除策略
        
        Args:
            policies: 策略列表 [[user_id, resource, action], ...]
        
        Returns:
            bool: 是否成功
        """
        try:
            result = self._enforcer.remove_policies(policies)
            if result:
                self._enforcer.save_policy()
            return result
        except Exception as e:
            logger.error(f"批量删除策略失败: {e}")
            return False
    
    # ========================================================================
    # 工具方法
    # ========================================================================
    
    def reload_policy(self):
        """重新加载策略"""
        try:
            self._enforcer.load_policy()
            logger.info("策略重新加载成功")
        except Exception as e:
            logger.error(f"重新加载策略失败: {e}")
    
    def clear_policy(self):
        """清空所有策略"""
        try:
            self._enforcer.clear_policy()
            self._enforcer.save_policy()
            logger.info("策略已清空")
        except Exception as e:
            logger.error(f"清空策略失败: {e}")


# 全局实例
casbin_manager = CasbinManager()
```

---

## 4. 配置示例

### 4.1 初始化权限策略

```python
# apps/medqc-web/backend/app/core/casbin_init.py

"""
初始化 Casbin 权限策略
"""

from .casbin_manager import casbin_manager

def init_casbin_policies():
    """初始化 Casbin 权限策略"""
    
    # 1. 定义角色权限
    role_permissions = [
        # 管理员权限
        ["admin", "medical_records", "create"],
        ["admin", "medical_records", "read"],
        ["admin", "medical_records", "update"],
        ["admin", "medical_records", "delete"],
        ["admin", "qc_rules", "create"],
        ["admin", "qc_rules", "read"],
        ["admin", "qc_rules", "update"],
        ["admin", "qc_rules", "delete"],
        ["admin", "users", "manage"],
        
        # 质控管理员权限
        ["qc_manager", "medical_records", "read"],
        ["qc_manager", "medical_records", "analyze"],
        ["qc_manager", "qc_results", "create"],
        ["qc_manager", "qc_results", "read"],
        ["qc_manager", "qc_results", "update"],
        ["qc_manager", "qc_rules", "read"],
        ["qc_manager", "qc_rules", "update"],
        
        # 质控专员权限
        ["qc_staff", "medical_records", "read"],
        ["qc_staff", "qc_results", "create"],
        ["qc_staff", "qc_results", "read"],
        ["qc_staff", "qc_rules", "read"],
        
        # 医生权限
        ["doctor", "medical_records", "create"],
        ["doctor", "medical_records", "read"],
        ["doctor", "medical_records", "update"],
        ["doctor", "qc_results", "read"],
    ]
    
    # 批量添加角色权限
    casbin_manager.add_policies(role_permissions)
    
    print("✅ Casbin 权限策略初始化完成")

if __name__ == "__main__":
    init_casbin_policies()
```

---

## 5. 使用示例

### 5.1 在 FastAPI 中使用

```python
# apps/medqc-web/backend/app/routers/medical_records.py

from fastapi import APIRouter, Depends, HTTPException
from ..core.casbin_manager import casbin_manager
from ..core.auth import get_current_user

router = APIRouter()

@router.get("/medical-records")
async def list_records(current_user = Depends(get_current_user)):
    """获取医疗记录列表"""
    
    # 使用 Casbin 检查权限
    if not casbin_manager.enforce(current_user.id, "medical_records", "read"):
        raise HTTPException(status_code=403, detail="没有读取权限")
    
    # 业务逻辑
    return {"records": []}

@router.post("/medical-records")
async def create_record(current_user = Depends(get_current_user)):
    """创建医疗记录"""
    
    # 检查权限
    if not casbin_manager.enforce(current_user.id, "medical_records", "create"):
        raise HTTPException(status_code=403, detail="没有创建权限")
    
    # 业务逻辑
    return {"message": "创建成功"}
```

### 5.2 权限管理 API

```python
# apps/medqc-web/backend/app/routers/permissions.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel

from ..core.casbin_manager import casbin_manager
from ..core.auth import get_current_user
from ..core.permissions import require_admin

router = APIRouter(prefix="/api/permissions", tags=["permissions"])

class PolicyCreate(BaseModel):
    user_id: str
    resource: str
    action: str

class RoleAssign(BaseModel):
    user_id: str
    role: str

@router.post("/policies")
@require_admin()
async def add_policy(
    policy: PolicyCreate,
    current_user = Depends(get_current_user)
):
    """添加权限策略（仅管理员）"""
    result = casbin_manager.add_policy(
        policy.user_id,
        policy.resource,
        policy.action
    )
    
    if result:
        return {"message": "策略添加成功"}
    else:
        raise HTTPException(status_code=400, detail="策略添加失败")

@router.get("/policies/{user_id}")
@require_admin()
async def get_user_policies(
    user_id: str,
    current_user = Depends(get_current_user)
):
    """获取用户的所有权限策略"""
    policies = casbin_manager.get_policies_for_user(user_id)
    return {"policies": policies}

@router.post("/roles")
@require_admin()
async def assign_role(
    role_assign: RoleAssign,
    current_user = Depends(get_current_user)
):
    """为用户分配角色"""
    result = casbin_manager.add_role_for_user(
        role_assign.user_id,
        role_assign.role
    )
    
    if result:
        return {"message": "角色分配成功"}
    else:
        raise HTTPException(status_code=400, detail="角色分配失败")
```

---

## 6. 性能优化

### 6.1 启用缓存

```python
# 在 casbin_manager.py 中添加

from functools import lru_cache
from datetime import datetime, timedelta

class CasbinManager:
    def __init__(self):
        # ... 现有代码 ...
        self._cache = {}
        self._cache_ttl = 300  # 5 分钟
    
    def enforce(self, user_id: str, resource: str, action: str) -> bool:
        """带缓存的权限检查"""
        cache_key = f"{user_id}:{resource}:{action}"
        
        # 检查缓存
        if cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=self._cache_ttl):
                return cached_result
        
        # 执行检查
        result = self._enforcer.enforce(user_id, resource, action)
        
        # 更新缓存
        self._cache[cache_key] = (result, datetime.now())
        
        return result
    
    def clear_cache(self):
        """清空缓存"""
        self._cache = {}
```

---

## 7. 最佳实践

### 7.1 权限设计原则

1. **最小权限原则**: 默认拒绝，显式授权
2. **角色分离**: 使用角色而不是直接授权给用户
3. **定期审计**: 定期检查和清理无用权限
4. **版本控制**: 记录权限变更历史

### 7.2 注意事项

1. ⚠️ **性能**: Casbin 会增加 1-5ms 延迟
2. ⚠️ **缓存**: 必须使用缓存优化性能
3. ⚠️ **一致性**: 注意缓存和数据库的一致性
4. ⚠️ **复杂度**: 不要过度设计权限规则

---

**文档版本**: 1.0  
**最后更新**: 2025-10-11  
**维护者**: Augment Agent

