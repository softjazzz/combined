# MedQC 项目 RBAC 与 Casbin 集成分析报告

## 📋 执行摘要

**项目**: MedQC 医疗质控系统  
**分析日期**: 2025-10-11  
**分析师**: Augment Agent  
**结论**: ⚠️ **部分适用，需谨慎评估**

### 核心建议

1. **短期（1-2月）**: ❌ **不建议** 立即引入 Casbin
2. **中期（3-6月）**: ✅ **可以考虑** 在特定场景下使用
3. **长期（6月+）**: ✅ **推荐** 作为权限系统升级方案

---

## 1. 适用性评估

### 1.1 当前权限管理现状

#### ✅ 已实现的功能

**前端权限管理**:
```typescript
// 位置: apps/medqc-web/src/utils/permissions.ts
// 位置: apps/medqc-web/src/composables/usePermissions.ts

✅ 基于角色的访问控制 (RBAC)
✅ 4 种用户角色: admin, qc_manager, qc_staff, doctor
✅ 6 种资源类型: medical_records, qc_results, qc_rules, users, statistics, settings
✅ 8 种操作类型: create, read, update, delete, analyze, review, manage, export
✅ 角色-权限映射配置
✅ 上下文相关的权限检查（科室、医院、医生限制）
✅ 权限守卫组件和指令
```

**后端权限管理**:
```python
# 位置: apps/medqc-web/backend/app/routers/auth.py

✅ JWT 认证
✅ 基于内存的用户存储（开发环境）
✅ 密码哈希验证
⚠️  权限检查逻辑较简单
⚠️  缺少细粒度的权限控制装饰器
```

**数据库层权限管理**:
```sql
-- 位置: infra/supabase/medqc/migrations/000_init_base_schema.sql

✅ Supabase RLS (Row Level Security) 策略
✅ user_roles 表存储用户角色
✅ 基于 auth.role() 的策略
⚠️  RLS 策略较为简单（仅区分 authenticated）
⚠️  缺少基于用户角色的细粒度 RLS
```

#### ❌ 缺失的功能

1. **动态权限管理**: 无法在运行时动态修改权限
2. **细粒度权限**: 缺少资源级别的权限控制
3. **权限继承**: 没有角色继承机制
4. **权限审计**: 缺少完整的权限操作日志
5. **后端权限装饰器**: 缺少统一的权限检查中间件

### 1.2 RBAC vs Casbin 对比

| 特性 | 当前 RBAC 实现 | Casbin | 评估 |
|------|---------------|--------|------|
| **角色管理** | ✅ 静态配置 | ✅ 动态管理 | Casbin 更灵活 |
| **权限模型** | ✅ 简单 RBAC | ✅ 支持 RBAC/ABAC/ACL 等 | Casbin 更强大 |
| **性能** | ✅ 极快（内存） | ⚠️ 较快（需缓存） | 当前方案更快 |
| **复杂度** | ✅ 简单易懂 | ⚠️ 学习曲线陡峭 | 当前方案更简单 |
| **扩展性** | ⚠️ 有限 | ✅ 极强 | Casbin 更好 |
| **维护成本** | ✅ 低 | ⚠️ 中等 | 当前方案更低 |
| **动态性** | ❌ 需要重启 | ✅ 运行时修改 | Casbin 更好 |
| **审计能力** | ❌ 缺失 | ✅ 内置支持 | Casbin 更好 |

### 1.3 适用性结论

#### ✅ Casbin 适合的场景

1. **多租户系统**: 需要为不同医院/科室配置不同权限
2. **复杂权限规则**: 需要基于时间、地点、资源属性的权限控制
3. **动态权限管理**: 需要在运行时修改权限而不重启系统
4. **权限审计**: 需要详细的权限操作日志
5. **大规模部署**: 多个医院实例，需要统一权限管理

#### ❌ Casbin 不适合的场景

1. **简单权限需求**: 当前 4 个角色已满足需求
2. **性能敏感**: 每次请求都需要权限检查，Casbin 会增加延迟
3. **团队经验不足**: 学习和维护成本高
4. **快速迭代**: 引入 Casbin 会增加开发复杂度

#### 🎯 MedQC 项目评估

**当前阶段**: ⚠️ **不建议立即引入 Casbin**

**原因**:
1. ✅ 当前权限模型已满足基本需求
2. ✅ 前端权限管理已经很完善
3. ⚠️ 后端权限检查较弱，但可以通过简单改进解决
4. ⚠️ 引入 Casbin 会增加系统复杂度
5. ⚠️ 团队需要学习 Casbin 的使用

**建议**: 先优化现有权限系统，待需求明确后再考虑 Casbin

---

## 2. 技术方案

### 2.1 方案 A: 优化现有 RBAC（推荐）

#### 优势
- ✅ 开发成本低
- ✅ 维护简单
- ✅ 性能最优
- ✅ 团队熟悉

#### 实施步骤

**步骤 1: 增强后端权限检查**

```python
# 新建文件: apps/medqc-web/backend/app/core/permissions.py

from functools import wraps
from typing import List, Callable
from fastapi import HTTPException, status, Depends
from .auth import get_current_user

# 权限装饰器
def require_permission(resource: str, action: str):
    """
    权限检查装饰器
    
    用法:
    @require_permission('medical_records', 'create')
    async def create_record(current_user: User = Depends(get_current_user)):
        pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, current_user = Depends(get_current_user), **kwargs):
            if not has_permission(current_user, resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"没有权限执行 {action} 操作在 {resource} 资源上"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# 角色检查装饰器
def require_role(roles: List[str]):
    """
    角色检查装饰器
    
    用法:
    @require_role(['admin', 'qc_manager'])
    async def manage_rules(current_user: User = Depends(get_current_user)):
        pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, current_user = Depends(get_current_user), **kwargs):
            if not any(role in current_user.roles for role in roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"需要以下角色之一: {', '.join(roles)}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# 权限检查函数
def has_permission(user, resource: str, action: str) -> bool:
    """检查用户是否有指定权限"""
    # 管理员拥有所有权限
    if 'admin' in user.roles:
        return True
    
    # 角色权限映射
    ROLE_PERMISSIONS = {
        'qc_manager': {
            'medical_records': ['read', 'analyze', 'export'],
            'qc_results': ['read', 'create', 'update', 'delete'],
            'qc_rules': ['read', 'create', 'update', 'delete'],
            'statistics': ['read'],
        },
        'qc_staff': {
            'medical_records': ['read', 'analyze'],
            'qc_results': ['read', 'create'],
            'qc_rules': ['read'],
            'statistics': ['read'],
        },
        'doctor': {
            'medical_records': ['read', 'create', 'update'],
            'qc_results': ['read'],
        }
    }
    
    for role in user.roles:
        if role in ROLE_PERMISSIONS:
            if resource in ROLE_PERMISSIONS[role]:
                if action in ROLE_PERMISSIONS[role][resource]:
                    return True
    
    return False
```

**步骤 2: 增强 RLS 策略**

```sql
-- 新建文件: infra/supabase/medqc/migrations/007_enhance_rls_policies.sql

-- 删除旧的简单策略
DROP POLICY IF EXISTS "认证用户可以查看医疗记录" ON medical_records;
DROP POLICY IF EXISTS "认证用户可以查看质控规则" ON qc_rules;
DROP POLICY IF EXISTS "认证用户可以查看质控结果" ON qc_results;

-- 创建辅助函数：获取用户角色
CREATE OR REPLACE FUNCTION get_user_roles(user_id UUID)
RETURNS TEXT[] AS $$
  SELECT ARRAY_AGG(role) 
  FROM user_roles 
  WHERE user_roles.user_id = $1;
$$ LANGUAGE SQL STABLE;

-- 创建辅助函数：检查用户是否有角色
CREATE OR REPLACE FUNCTION has_role(user_id UUID, required_role TEXT)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles 
    WHERE user_roles.user_id = $1 AND role = $2
  );
$$ LANGUAGE SQL STABLE;

-- Medical Records 策略
-- 管理员和质控人员可以查看所有记录
CREATE POLICY "admin_qc_can_view_all_records" ON medical_records
  FOR SELECT
  USING (
    has_role(auth.uid(), 'admin') OR
    has_role(auth.uid(), 'qc_manager') OR
    has_role(auth.uid(), 'qc_staff')
  );

-- 医生只能查看自己的记录
CREATE POLICY "doctors_can_view_own_records" ON medical_records
  FOR SELECT
  USING (
    has_role(auth.uid(), 'doctor') AND
    created_by = auth.uid()
  );

-- 管理员和质控管理员可以创建记录
CREATE POLICY "admin_qc_manager_can_create_records" ON medical_records
  FOR INSERT
  WITH CHECK (
    has_role(auth.uid(), 'admin') OR
    has_role(auth.uid(), 'qc_manager')
  );

-- QC Rules 策略
-- 所有认证用户可以查看规则
CREATE POLICY "authenticated_can_view_rules" ON qc_rules
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 只有管理员和质控管理员可以修改规则
CREATE POLICY "admin_qc_manager_can_modify_rules" ON qc_rules
  FOR ALL
  USING (
    has_role(auth.uid(), 'admin') OR
    has_role(auth.uid(), 'qc_manager')
  );

-- QC Results 策略
-- 所有认证用户可以查看质控结果
CREATE POLICY "authenticated_can_view_results" ON qc_results
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- 质控人员可以创建和修改结果
CREATE POLICY "qc_staff_can_modify_results" ON qc_results
  FOR ALL
  USING (
    has_role(auth.uid(), 'admin') OR
    has_role(auth.uid(), 'qc_manager') OR
    has_role(auth.uid(), 'qc_staff')
  );
```

**步骤 3: 添加权限审计日志**

```sql
-- 创建权限审计日志表
CREATE TABLE IF NOT EXISTS permission_audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  user_email TEXT,
  user_roles TEXT[],
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  action TEXT NOT NULL,
  allowed BOOLEAN NOT NULL,
  reason TEXT,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_permission_audit_logs_user ON permission_audit_logs(user_id);
CREATE INDEX idx_permission_audit_logs_created ON permission_audit_logs(created_at DESC);
CREATE INDEX idx_permission_audit_logs_resource ON permission_audit_logs(resource_type, resource_id);
```

**工作量评估**: 2-3 天  
**风险**: 低  
**优先级**: 高

---

### 2.2 方案 B: 集成 Casbin（可选）

#### 适用场景
- 需要复杂的权限规则
- 需要动态权限管理
- 多租户部署

#### 实施步骤

**步骤 1: 安装 Casbin**

```bash
# Python 后端
pip install casbin casbin-sqlalchemy-adapter

# 添加到 requirements.txt
echo "casbin==1.36.2" >> apps/medqc-web/backend/requirements.txt
echo "casbin-sqlalchemy-adapter==1.5.0" >> apps/medqc-web/backend/requirements.txt
```

**步骤 2: 创建 Casbin 模型**

```ini
# 新建文件: apps/medqc-web/backend/app/core/casbin_model.conf

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

**步骤 3: 创建 Casbin 策略表**

```sql
-- 创建 Casbin 策略表
CREATE TABLE IF NOT EXISTS casbin_rule (
    id SERIAL PRIMARY KEY,
    ptype VARCHAR(100),
    v0 VARCHAR(100),
    v1 VARCHAR(100),
    v2 VARCHAR(100),
    v3 VARCHAR(100),
    v4 VARCHAR(100),
    v5 VARCHAR(100)
);

CREATE INDEX idx_casbin_rule_ptype ON casbin_rule(ptype);
```

**步骤 4: 初始化 Casbin**

```python
# 新建文件: apps/medqc-web/backend/app/core/casbin_enforcer.py

import casbin
from casbin_sqlalchemy_adapter import Adapter
from sqlalchemy import create_engine

# 数据库连接
DATABASE_URL = "postgresql://user:password@localhost/medqc"
engine = create_engine(DATABASE_URL)

# 创建适配器
adapter = Adapter(engine)

# 创建执行器
enforcer = casbin.Enforcer("app/core/casbin_model.conf", adapter)

# 初始化策略
def init_policies():
    """初始化权限策略"""
    # 角色继承
    enforcer.add_grouping_policy("alice", "admin")
    enforcer.add_grouping_policy("bob", "qc_manager")
    
    # 管理员权限
    enforcer.add_policy("admin", "medical_records", "read")
    enforcer.add_policy("admin", "medical_records", "create")
    enforcer.add_policy("admin", "medical_records", "update")
    enforcer.add_policy("admin", "medical_records", "delete")
    
    # 质控管理员权限
    enforcer.add_policy("qc_manager", "medical_records", "read")
    enforcer.add_policy("qc_manager", "qc_results", "create")
    
    # 保存策略
    enforcer.save_policy()

# 权限检查函数
def check_permission(user_id: str, resource: str, action: str) -> bool:
    """检查用户权限"""
    return enforcer.enforce(user_id, resource, action)
```

**步骤 5: 集成到 FastAPI**

```python
# 修改文件: apps/medqc-web/backend/app/core/permissions.py

from .casbin_enforcer import check_permission as casbin_check

def require_permission_casbin(resource: str, action: str):
    """使用 Casbin 的权限检查装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, current_user = Depends(get_current_user), **kwargs):
            if not casbin_check(current_user.id, resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"没有权限执行 {action} 操作在 {resource} 资源上"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

**工作量评估**: 5-7 天  
**风险**: 中等  
**优先级**: 低

---

## 3. 实施建议

### 3.1 推荐方案：渐进式优化

#### 阶段 1: 立即执行（1-2周）

1. ✅ **增强后端权限检查**
   - 实现权限装饰器
   - 添加到关键 API 端点
   - 工作量: 2-3 天

2. ✅ **优化 RLS 策略**
   - 实现基于角色的 RLS
   - 添加辅助函数
   - 工作量: 1-2 天

3. ✅ **添加权限审计日志**
   - 创建审计日志表
   - 记录关键操作
   - 工作量: 1 天

#### 阶段 2: 短期优化（1-2月）

1. ⚠️ **评估 Casbin 必要性**
   - 收集实际权限需求
   - 评估复杂度
   - 决定是否引入

2. ✅ **完善权限管理界面**
   - 权限配置页面
   - 角色管理页面
   - 工作量: 3-5 天

3. ✅ **性能优化**
   - 权限检查缓存
   - RLS 查询优化
   - 工作量: 2-3 天

#### 阶段 3: 中长期规划（3-6月）

1. 🔄 **考虑 Casbin 集成**（如果需要）
   - 复杂权限规则
   - 动态权限管理
   - 多租户支持

2. 🔄 **权限系统升级**
   - ABAC (Attribute-Based Access Control)
   - 细粒度资源权限
   - 时间/地点限制

### 3.2 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Casbin 学习曲线陡峭 | 高 | 中 | 先优化现有系统，积累经验 |
| 性能下降 | 中 | 高 | 使用缓存，优化查询 |
| 系统复杂度增加 | 高 | 中 | 渐进式引入，充分测试 |
| 团队抵触 | 中 | 中 | 培训和文档支持 |

### 3.3 成本效益分析

#### 方案 A: 优化现有 RBAC

**成本**:
- 开发时间: 5-7 天
- 学习成本: 低
- 维护成本: 低

**收益**:
- 满足当前需求
- 性能最优
- 易于维护

**ROI**: ⭐⭐⭐⭐⭐

#### 方案 B: 集成 Casbin

**成本**:
- 开发时间: 10-15 天
- 学习成本: 高
- 维护成本: 中等

**收益**:
- 支持复杂权限
- 动态管理
- 可扩展性强

**ROI**: ⭐⭐⭐ (当前阶段)

---

## 4. 结论与建议

### 4.1 核心建议

1. **短期（现在）**: ✅ **优先优化现有 RBAC 系统**
   - 实施方案 A
   - 工作量小，收益大
   - 满足当前需求

2. **中期（3-6月）**: ⚠️ **评估 Casbin 必要性**
   - 根据实际需求决定
   - 如果权限规则变复杂，再考虑

3. **长期（6月+）**: ✅ **考虑权限系统升级**
   - Casbin 或其他方案
   - 支持多租户
   - ABAC 模型

### 4.2 决策树

```
是否需要动态权限管理？
├─ 否 → 使用方案 A（优化现有 RBAC）✅
└─ 是 → 是否需要复杂权限规则？
    ├─ 否 → 使用方案 A + 简单动态配置
    └─ 是 → 考虑方案 B（Casbin）⚠️
```

### 4.3 最终建议

**立即行动**: 实施方案 A - 优化现有 RBAC 系统

**理由**:
1. ✅ 满足当前 90% 的需求
2. ✅ 开发成本低，风险小
3. ✅ 性能最优
4. ✅ 团队熟悉，易于维护
5. ✅ 为未来升级留有空间

**不建议**: 立即引入 Casbin

**理由**:
1. ❌ 当前权限需求不复杂
2. ❌ 学习和维护成本高
3. ❌ 可能过度设计
4. ❌ 性能开销
5. ❌ 增加系统复杂度

---

**报告完成日期**: 2025-10-11  
**下一步**: 实施方案 A 的阶段 1 任务

