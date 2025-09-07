# 病案质控系统 - 认证和权限管理系统

## 🎯 系统概述

本系统实现了一套完整的基于角色的访问控制（RBAC）系统，支持细粒度的权限管理，确保医疗数据的安全性和合规性。

## 🏗️ 系统架构

### 核心组件

1. **认证模块** (`src/stores/auth.ts`)
   - 用户登录/登出
   - 会话管理
   - 用户信息管理

2. **权限工具** (`src/utils/permissions.ts`)
   - 权限常量定义
   - 角色权限映射
   - 权限检查函数

3. **权限组合函数** (`src/composables/usePermissions.ts`)
   - 响应式权限检查
   - 便捷的权限判断
   - 权限指令支持

4. **权限组件**
   - `PermissionGuard.vue` - 权限守卫组件
   - `PermissionButton.vue` - 权限按钮组件

## 🔐 角色和权限设计

### 用户角色

| 角色 | 代码 | 描述 | 权限范围 |
|------|------|------|----------|
| 系统管理员 | `admin` | 系统最高权限 | 所有功能的完整访问权限 |
| 质控管理员 | `qc_manager` | 质控部门管理者 | 质控相关功能的管理权限 |
| 质控人员 | `qc_staff` | 质控执行人员 | 质控分析和审核权限 |
| 医务人员 | `doctor` | 医生和护士 | 病案创建和查看权限 |

### 权限资源

| 资源类型 | 代码 | 描述 |
|----------|------|------|
| 病案记录 | `medical_records` | 病案的增删改查 |
| 质控结果 | `qc_results` | 质控结果的查看和审核 |
| 质控规则 | `qc_rules` | 质控规则的管理 |
| 用户管理 | `users` | 用户账户管理 |
| 统计分析 | `statistics` | 数据统计和报表 |
| 系统设置 | `settings` | 系统配置管理 |

### 权限操作

| 操作 | 代码 | 描述 |
|------|------|------|
| 创建 | `create` | 新建资源 |
| 读取 | `read` | 查看资源 |
| 更新 | `update` | 修改资源 |
| 删除 | `delete` | 删除资源 |
| 分析 | `analyze` | 执行分析操作 |
| 审核 | `review` | 审核操作 |
| 管理 | `manage` | 管理操作 |
| 导出 | `export` | 导出数据 |

## 📝 使用方法

### 1. 在组件中使用权限检查

```vue
<script setup lang="ts">
import { usePermissions } from '@/composables/usePermissions'

const { 
  hasPermission, 
  checkPermission, 
  canCreateRecords,
  canManageUsers,
  isAdmin 
} = usePermissions()

// 检查是否有创建病案的权限
const canCreate = hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)

// 带上下文的权限检查
const canEdit = checkPermission(
  ResourceType.MEDICAL_RECORDS, 
  PermissionAction.UPDATE,
  { doctor_id: record.doctor_id }
)
</script>
```

### 2. 使用权限组件

#### PermissionGuard 权限守卫

```vue
<template>
  <!-- 基于角色的权限控制 -->
  <PermissionGuard :roles="['admin', 'qc_manager']">
    <a-button type="primary">管理员功能</a-button>
  </PermissionGuard>

  <!-- 基于资源和操作的权限控制 -->
  <PermissionGuard 
    resource="medical_records" 
    action="create"
    fallback="placeholder"
    placeholder="您没有创建病案的权限"
  >
    <CreateRecordForm />
  </PermissionGuard>

  <!-- 禁用模式 -->
  <PermissionGuard 
    resource="users" 
    action="delete"
    fallback="disabled"
  >
    <a-button danger>删除用户</a-button>
  </PermissionGuard>
</template>
```

#### PermissionButton 权限按钮

```vue
<template>
  <!-- 无权限时自动隐藏 -->
  <PermissionButton
    resource="users"
    action="create"
    type="primary"
    @click="handleCreateUser"
  >
    新增用户
  </PermissionButton>

  <!-- 基于角色的按钮控制 -->
  <PermissionButton
    :roles="['admin']"
    danger
    @click="handleSystemReset"
  >
    系统重置
  </PermissionButton>
</template>
```

### 3. 路由权限控制

```typescript
// src/router/index.ts
{
  path: '/settings',
  name: 'Settings',
  component: () => import('@/views/settings/SettingsView.vue'),
  meta: {
    title: '系统设置',
    permission: ['admin'] // 只有管理员可以访问
  }
}
```

### 4. 在API中使用权限装饰器

```typescript
import { requirePermission } from '@/utils/permissions'

class UserService {
  @requirePermission(ResourceType.USERS, PermissionAction.CREATE)
  async createUser(userData: CreateUserRequest) {
    // 创建用户逻辑
  }

  @requirePermission(ResourceType.USERS, PermissionAction.DELETE)
  async deleteUser(userId: string) {
    // 删除用户逻辑
  }
}
```

## 🔧 权限配置

### 角色权限映射

```typescript
// src/utils/permissions.ts
export const ROLE_PERMISSIONS: RolePermissions = {
  [UserRole.ADMIN]: [
    // 管理员拥有所有权限
    ...Object.values(PERMISSIONS.MEDICAL_RECORDS),
    ...Object.values(PERMISSIONS.QC_RESULTS),
    ...Object.values(PERMISSIONS.QC_RULES),
    ...Object.values(PERMISSIONS.USERS),
    ...Object.values(PERMISSIONS.STATISTICS),
    ...Object.values(PERMISSIONS.SETTINGS)
  ],
  
  [UserRole.QC_MANAGER]: [
    // 质控管理员权限
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.ANALYZE,
    PERMISSIONS.MEDICAL_RECORDS.EXPORT,
    // ... 其他权限
  ],
  
  // ... 其他角色配置
}
```

### 权限条件检查

系统支持基于上下文的权限检查：

```typescript
// 医生只能操作自己的病案
if (user.roles?.includes(UserRole.DOCTOR)) {
  if (resource === ResourceType.MEDICAL_RECORDS && context?.doctor_id) {
    if (context.doctor_id !== user.id) {
      return { 
        allowed: false, 
        reason: '医生只能操作自己的病案记录' 
      }
    }
  }
}

// 科室限制
if (context?.department && user.department) {
  if (!user.roles?.includes(UserRole.ADMIN) && context.department !== user.department) {
    return { 
      allowed: false, 
      reason: '只能查看本科室的病案记录' 
    }
  }
}
```

## 🛡️ 安全特性

### 1. 数据脱敏
- 敏感医疗数据在前端显示时进行脱敏处理
- 完整数据仅在后端处理

### 2. 会话管理
- 自动刷新认证令牌
- 会话超时自动登出
- 检测异常登录行为

### 3. 审计日志
- 记录所有权限相关操作
- 包含用户、时间、操作类型等信息
- 支持审计查询和分析

### 4. 多因素认证（规划中）
- 支持短信验证码
- 支持邮箱验证
- 支持TOTP应用

## 📊 用户管理界面

系统提供了完整的用户管理界面，展示了权限系统的实际应用：

- **用户列表**：显示所有用户及其角色状态
- **权限控制**：按钮和操作根据当前用户权限动态显示
- **角色管理**：支持多角色分配和管理
- **状态管理**：用户状态控制（正常/停用/锁定）

## 🚀 扩展指南

### 添加新角色

1. 在 `UserRole` 枚举中添加新角色
2. 在 `ROLE_PERMISSIONS` 中配置角色权限
3. 更新角色描述映射
4. 在UI中添加角色选项

### 添加新权限

1. 在 `ResourceType` 或 `PermissionAction` 中添加新类型
2. 在 `PERMISSIONS` 常量中定义权限
3. 更新权限描述映射
4. 在相关角色中分配权限

### 自定义权限检查

```typescript
// 自定义权限检查逻辑
const customPermissionCheck = (user: User, context: any) => {
  // 自定义逻辑
  if (context.isEmergency && user.department === '急诊科') {
    return { allowed: true }
  }
  
  // 使用标准权限检查
  return checkPermission(user, ResourceType.MEDICAL_RECORDS, PermissionAction.READ, context)
}
```

## 🔍 调试和测试

### 权限调试

```typescript
// 获取用户所有权限
const permissions = getUserPermissions()
console.log('用户权限:', permissions)

// 检查特定权限
const result = checkPermission(ResourceType.USERS, PermissionAction.CREATE)
console.log('权限检查结果:', result)
```

### 测试账户

系统提供了以下测试账户：

| 邮箱 | 密码 | 角色 | 用途 |
|------|------|------|------|
| admin@demo.com | demo123456 | 管理员 | 系统管理测试 |
| qc@demo.com | demo123456 | 质控管理员 | 质控功能测试 |
| doctor@demo.com | demo123456 | 医务人员 | 医生功能测试 |

## 📚 相关文档

- [Vue 3 Composition API](https://v3.vuejs.org/guide/composition-api-introduction.html)
- [Ant Design Vue](https://antdv.com/)
- [Supabase Auth](https://supabase.com/docs/guides/auth)
- [TypeScript 手册](https://www.typescriptlang.org/docs/)

## 🤝 贡献指南

1. 遵循现有的代码风格和命名规范
2. 添加适当的类型定义
3. 编写单元测试
4. 更新相关文档
5. 确保安全性和性能

---

*本文档将随着系统的发展持续更新，请定期查看最新版本。* 