/**
 * 权限管理工具函数
 * 病案质控系统 - 权限检查与控制
 */

import { 
  UserRole, 
  PermissionAction, 
  ResourceType
} from '@/types'
import type { 
  User, 
  Permission, 
  PermissionCheckResult,
  PermissionCondition,
  RolePermissions
} from '@/types'

// 权限常量定义
export const PERMISSIONS = {
  // 医疗记录权限
  MEDICAL_RECORDS: {
    CREATE: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.CREATE },
    READ: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.READ },
    UPDATE: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.UPDATE },
    DELETE: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.DELETE },
    ANALYZE: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.ANALYZE },
    EXPORT: { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.EXPORT }
  },
  
  // 质控结果权限
  QC_RESULTS: {
    READ: { resource: ResourceType.QC_RESULTS, action: PermissionAction.READ },
    UPDATE: { resource: ResourceType.QC_RESULTS, action: PermissionAction.UPDATE },
    REVIEW: { resource: ResourceType.QC_RESULTS, action: PermissionAction.REVIEW },
    EXPORT: { resource: ResourceType.QC_RESULTS, action: PermissionAction.EXPORT }
  },
  
  // 质控规则权限
  QC_RULES: {
    CREATE: { resource: ResourceType.QC_RULES, action: PermissionAction.CREATE },
    READ: { resource: ResourceType.QC_RULES, action: PermissionAction.READ },
    UPDATE: { resource: ResourceType.QC_RULES, action: PermissionAction.UPDATE },
    DELETE: { resource: ResourceType.QC_RULES, action: PermissionAction.DELETE },
    MANAGE: { resource: ResourceType.QC_RULES, action: PermissionAction.MANAGE }
  },
  
  // 用户管理权限
  USERS: {
    CREATE: { resource: ResourceType.USERS, action: PermissionAction.CREATE },
    READ: { resource: ResourceType.USERS, action: PermissionAction.READ },
    UPDATE: { resource: ResourceType.USERS, action: PermissionAction.UPDATE },
    DELETE: { resource: ResourceType.USERS, action: PermissionAction.DELETE },
    MANAGE: { resource: ResourceType.USERS, action: PermissionAction.MANAGE }
  },
  
  // 统计分析权限
  STATISTICS: {
    READ: { resource: ResourceType.STATISTICS, action: PermissionAction.READ },
    EXPORT: { resource: ResourceType.STATISTICS, action: PermissionAction.EXPORT }
  },
  
  // 系统设置权限
  SETTINGS: {
    READ: { resource: ResourceType.SETTINGS, action: PermissionAction.READ },
    UPDATE: { resource: ResourceType.SETTINGS, action: PermissionAction.UPDATE },
    MANAGE: { resource: ResourceType.SETTINGS, action: PermissionAction.MANAGE }
  }
} as const

// 角色权限映射配置
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
    ...Object.values(PERMISSIONS.QC_RESULTS),
    ...Object.values(PERMISSIONS.QC_RULES),
    PERMISSIONS.USERS.READ,
    ...Object.values(PERMISSIONS.STATISTICS)
  ],
  
  [UserRole.QC_STAFF]: [
    // 质控人员权限
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.ANALYZE,
    PERMISSIONS.QC_RESULTS.READ,
    PERMISSIONS.QC_RESULTS.UPDATE,
    PERMISSIONS.QC_RESULTS.REVIEW,
    PERMISSIONS.QC_RULES.READ,
    PERMISSIONS.STATISTICS.READ
  ],
  
  [UserRole.DOCTOR]: [
    // 医生权限（只能操作自己的记录）
    PERMISSIONS.MEDICAL_RECORDS.CREATE,
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.UPDATE,
    PERMISSIONS.QC_RESULTS.READ,
    PERMISSIONS.STATISTICS.READ
  ]
}

// 基础权限检查函数
export function hasPermission(
  user: User | null,
  resource: ResourceType,
  action: PermissionAction
): boolean {
  if (!user || !user.roles) return false
  
  // 检查用户角色是否有对应权限
  return user.roles.some((role: UserRole) => {
    const rolePermissions = ROLE_PERMISSIONS[role] || []
    return rolePermissions.some((permission: Permission) => 
      permission.resource === resource && permission.action === action
    )
  })
}

// 带条件的权限检查函数
export function checkPermission(
  user: User | null,
  resource: ResourceType,
  action: PermissionAction,
  context?: Record<string, unknown>
): PermissionCheckResult {
  if (!user || !user.roles) {
    return { allowed: false, reason: '用户未认证' }
  }
  
  // 基础权限检查
  const hasBasicPermission = hasPermission(user, resource, action)
  if (!hasBasicPermission) {
    return { allowed: false, reason: '用户无此权限' }
  }
  
  // 特殊权限条件检查
  const conditionCheck = checkPermissionConditions(user, resource, action, context)
  if (!conditionCheck.allowed) {
    return conditionCheck
  }
  
  return { allowed: true }
}

// 权限条件检查
function checkPermissionConditions(
  user: User,
  resource: ResourceType,
  action: PermissionAction,
  context?: Record<string, unknown>
): PermissionCheckResult {
  // 医生只能操作自己的记录
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
  
  // 科室限制检查
  if (context?.department && user.department) {
    if (action === PermissionAction.READ && resource === ResourceType.MEDICAL_RECORDS) {
      // 非管理员只能查看本科室的记录
      if (!user.roles?.includes(UserRole.ADMIN) && context.department !== user.department) {
        return { 
          allowed: false, 
          reason: '只能查看本科室的病案记录' 
        }
      }
    }
  }
  
  // 医院限制检查
  if (context?.hospital_id && user.hospital_id) {
    if (context.hospital_id !== user.hospital_id) {
      return { 
        allowed: false, 
        reason: '只能操作本医院的数据' 
      }
    }
  }
  
  return { allowed: true }
}

// 角色权限检查
export function hasRole(user: User | null, role: UserRole): boolean {
  return user?.roles?.includes(role) || false
}

// 多角色权限检查
export function hasAnyRole(user: User | null, roles: UserRole: unknown[]): boolean {
  if (!user?.roles) return false
  return roles.some(role => user.roles!.includes(role))
}

// 检查是否为管理员
export function isAdmin(user: User | null): boolean {
  return hasRole(user, UserRole.ADMIN)
}

// 检查是否为质控管理员
export function isQCManager(user: User | null): boolean {
  return hasRole(user, UserRole.QC_MANAGER)
}

// 检查是否为质控人员
export function isQCStaff(user: User | null): boolean {
  return hasRole(user, UserRole.QC_STAFF)
}

// 检查是否为医生
export function isDoctor(user: User | null): boolean {
  return hasRole(user, UserRole.DOCTOR)
}

// 检查是否有质控相关权限
export function hasQCPermission(user: User | null): boolean {
  return hasAnyRole(user, [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.QC_STAFF])
}

// 检查是否有管理权限
export function hasManagePermission(user: User | null): boolean {
  return hasAnyRole(user, [UserRole.ADMIN, UserRole.QC_MANAGER])
}

// 获取用户权限列表
export function getUserPermissions(user: User | null): Permission[] {
  if (!user?.roles) return []
  
  const permissions: Permission[] = []
  user.roles.forEach(role => {
    const rolePermissions = ROLE_PERMISSIONS[role] || []
    permissions.push(...rolePermissions)
  })
  
  // 去重
  return permissions.filter((permission, index, self) => 
    index === self.findIndex(p => 
      p.resource === permission.resource && p.action === permission.action
    )
  )
}

// 权限描述映射
export const PERMISSION_DESCRIPTIONS = {
  [ResourceType.MEDICAL_RECORDS]: {
    [PermissionAction.CREATE]: '创建病案记录',
    [PermissionAction.READ]: '查看病案记录',
    [PermissionAction.UPDATE]: '修改病案记录',
    [PermissionAction.DELETE]: '删除病案记录',
    [PermissionAction.ANALYZE]: '分析病案记录',
    [PermissionAction.EXPORT]: '导出病案记录'
  },
  [ResourceType.QC_RESULTS]: {
    [PermissionAction.READ]: '查看质控结果',
    [PermissionAction.UPDATE]: '修改质控结果',
    [PermissionAction.REVIEW]: '审核质控结果',
    [PermissionAction.EXPORT]: '导出质控结果'
  },
  [ResourceType.QC_RULES]: {
    [PermissionAction.CREATE]: '创建质控规则',
    [PermissionAction.READ]: '查看质控规则',
    [PermissionAction.UPDATE]: '修改质控规则',
    [PermissionAction.DELETE]: '删除质控规则',
    [PermissionAction.MANAGE]: '管理质控规则'
  },
  [ResourceType.USERS]: {
    [PermissionAction.CREATE]: '创建用户',
    [PermissionAction.READ]: '查看用户',
    [PermissionAction.UPDATE]: '修改用户',
    [PermissionAction.DELETE]: '删除用户',
    [PermissionAction.MANAGE]: '管理用户'
  },
  [ResourceType.STATISTICS]: {
    [PermissionAction.READ]: '查看统计数据',
    [PermissionAction.EXPORT]: '导出统计数据'
  },
  [ResourceType.SETTINGS]: {
    [PermissionAction.READ]: '查看系统设置',
    [PermissionAction.UPDATE]: '修改系统设置',
    [PermissionAction.MANAGE]: '管理系统设置'
  }
} as const

// 获取权限描述
export function getPermissionDescription(resource: ResourceType, action: PermissionAction): string {
  return PERMISSION_DESCRIPTIONS[resource]?.[action] || `${resource}:${action}`
}

// 角色描述映射
export const ROLE_DESCRIPTIONS = {
  [UserRole.ADMIN]: '系统管理员',
  [UserRole.QC_MANAGER]: '质控管理员',
  [UserRole.QC_STAFF]: '质控人员',
  [UserRole.DOCTOR]: '医务人员'
} as const

// 获取角色描述
export function getRoleDescription(role: UserRole): string {
  return ROLE_DESCRIPTIONS[role] || role
}

// 权限验证装饰器（用于API路由）
export function requirePermission(
  resource: ResourceType,
  action: PermissionAction
) {
  return function (target: unknown, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value
    
    descriptor.value = async function (...args: unknown[]) {
      const user = this.user || args[0]?.user
      
      const result = checkPermission(user, resource, action, args[0]?.context)
      if (!result.allowed) {
        throw new Error(`权限不足: ${result.reason}`)
      }
      
      return originalMethod.apply(this, args)
    }
    
    return descriptor
  }
}

// 权限检查中间件
export function createPermissionMiddleware(
  resource: ResourceType,
  action: PermissionAction
) {
  return (user: User | null, context?: Record<string, unknown>) => {
    const result = checkPermission(user, resource, action, context)
    if (!result.allowed) {
      throw new Error(`权限不足: ${result.reason}`)
    }
    return true
  }
} 