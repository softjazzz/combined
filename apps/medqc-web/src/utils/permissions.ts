/**
 * 权限管理工具函数
 * 病案质控系统 - 权限检查与控制
 */

import { PermissionAction, ResourceType, UserRole } from '@/types/auth'
import type { Permission, PermissionCheckResult, RolePermissions, User } from '@/types/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'

const createPermission = (
  id: string,
  resource: ResourceType,
  action: PermissionAction,
): Permission => ({
  id,
  resource,
  action,
})

// 权限常量定义
export const PERMISSIONS = {
  MEDICAL_RECORDS: {
    CREATE: createPermission(
      'medical_records:create',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.CREATE,
    ),
    READ: createPermission(
      'medical_records:read',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.READ,
    ),
    UPDATE: createPermission(
      'medical_records:update',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.UPDATE,
    ),
    DELETE: createPermission(
      'medical_records:delete',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.DELETE,
    ),
    ANALYZE: createPermission(
      'medical_records:analyze',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.ANALYZE,
    ),
    EXPORT: createPermission(
      'medical_records:export',
      ResourceType.MEDICAL_RECORDS,
      PermissionAction.EXPORT,
    ),
  },

  QC_RESULTS: {
    READ: createPermission('qc_results:read', ResourceType.QC_RESULTS, PermissionAction.READ),
    UPDATE: createPermission('qc_results:update', ResourceType.QC_RESULTS, PermissionAction.UPDATE),
    REVIEW: createPermission('qc_results:review', ResourceType.QC_RESULTS, PermissionAction.REVIEW),
    EXPORT: createPermission('qc_results:export', ResourceType.QC_RESULTS, PermissionAction.EXPORT),
  },

  QC_RULES: {
    CREATE: createPermission('qc_rules:create', ResourceType.QC_RULES, PermissionAction.CREATE),
    READ: createPermission('qc_rules:read', ResourceType.QC_RULES, PermissionAction.READ),
    UPDATE: createPermission('qc_rules:update', ResourceType.QC_RULES, PermissionAction.UPDATE),
    DELETE: createPermission('qc_rules:delete', ResourceType.QC_RULES, PermissionAction.DELETE),
    MANAGE: createPermission('qc_rules:manage', ResourceType.QC_RULES, PermissionAction.MANAGE),
  },

  USERS: {
    CREATE: createPermission('users:create', ResourceType.USERS, PermissionAction.CREATE),
    READ: createPermission('users:read', ResourceType.USERS, PermissionAction.READ),
    UPDATE: createPermission('users:update', ResourceType.USERS, PermissionAction.UPDATE),
    DELETE: createPermission('users:delete', ResourceType.USERS, PermissionAction.DELETE),
    MANAGE: createPermission('users:manage', ResourceType.USERS, PermissionAction.MANAGE),
  },

  STATISTICS: {
    READ: createPermission('statistics:read', ResourceType.STATISTICS, PermissionAction.READ),
    EXPORT: createPermission('statistics:export', ResourceType.STATISTICS, PermissionAction.EXPORT),
  },

  SETTINGS: {
    READ: createPermission('settings:read', ResourceType.SETTINGS, PermissionAction.READ),
    UPDATE: createPermission('settings:update', ResourceType.SETTINGS, PermissionAction.UPDATE),
    MANAGE: createPermission('settings:manage', ResourceType.SETTINGS, PermissionAction.MANAGE),
  },
} as const

// 角色权限映射配置
export const ROLE_PERMISSIONS: RolePermissions = {
  [UserRole.ADMIN]: [
    ...Object.values(PERMISSIONS.MEDICAL_RECORDS),
    ...Object.values(PERMISSIONS.QC_RESULTS),
    ...Object.values(PERMISSIONS.QC_RULES),
    ...Object.values(PERMISSIONS.USERS),
    ...Object.values(PERMISSIONS.STATISTICS),
    ...Object.values(PERMISSIONS.SETTINGS),
  ],

  [UserRole.QC_MANAGER]: [
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.ANALYZE,
    PERMISSIONS.MEDICAL_RECORDS.EXPORT,
    ...Object.values(PERMISSIONS.QC_RESULTS),
    ...Object.values(PERMISSIONS.QC_RULES),
    PERMISSIONS.USERS.READ,
    ...Object.values(PERMISSIONS.STATISTICS),
  ],

  [UserRole.QC_STAFF]: [
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.ANALYZE,
    PERMISSIONS.QC_RESULTS.READ,
    PERMISSIONS.QC_RESULTS.UPDATE,
    PERMISSIONS.QC_RESULTS.REVIEW,
    PERMISSIONS.QC_RULES.READ,
    PERMISSIONS.STATISTICS.READ,
  ],

  [UserRole.DOCTOR]: [
    PERMISSIONS.MEDICAL_RECORDS.CREATE,
    PERMISSIONS.MEDICAL_RECORDS.READ,
    PERMISSIONS.MEDICAL_RECORDS.UPDATE,
    PERMISSIONS.QC_RESULTS.READ,
    PERMISSIONS.STATISTICS.READ,
  ],
}

// 基础权限检查函数
export function hasPermission(
  user: User | null,
  resource: ResourceType,
  action: PermissionAction,
): boolean {
  if (!user?.roles?.length) {
    return false
  }

  return effectiveRoles(user.roles).some((role) => {
    const rolePermissions = ROLE_PERMISSIONS[role as UserRole] || []
    return rolePermissions.some(
      (permission: Permission) => permission.resource === resource && permission.action === action,
    )
  })
}

// 带条件的权限检查函数
export function checkPermission(
  user: User | null,
  resource: ResourceType,
  action: PermissionAction,
  context?: Record<string, unknown>,
): PermissionCheckResult {
  if (!user?.roles?.length) {
    return { allowed: false, reason: '用户未认证' }
  }

  const hasBasicPermission = hasPermission(user, resource, action)
  if (!hasBasicPermission) {
    return { allowed: false, reason: '用户无此权限' }
  }

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
  context?: Record<string, unknown>,
): PermissionCheckResult {
  if (user.roles?.includes('sync_admin')) return { allowed: true }
  const doctorId = typeof context?.doctor_id === 'string' ? context.doctor_id : undefined
  const department = typeof context?.department === 'string' ? context.department : undefined
  const hospitalId = typeof context?.hospital_id === 'string' ? context.hospital_id : undefined

  // 医生只能操作自己的病历
  if (
    user.roles?.includes(UserRole.DOCTOR) &&
    resource === ResourceType.MEDICAL_RECORDS &&
    doctorId
  ) {
    if (doctorId !== user.id) {
      return {
        allowed: false,
        reason: '医生只能操作自己的病历记录',
      }
    }
  }

  // 科室范围限制
  if (department && user.department) {
    if (action === PermissionAction.READ && resource === ResourceType.MEDICAL_RECORDS) {
      if (!user.roles?.includes(UserRole.ADMIN) && department !== user.department) {
        return {
          allowed: false,
          reason: '只能查看本科室的病案记录',
        }
      }
    }
  }

  // 医院范围限制
  if (hospitalId && user.hospital_id) {
    if (hospitalId !== user.hospital_id) {
      return {
        allowed: false,
        reason: '只能操作本医院的数据',
      }
    }
  }

  return { allowed: true }
}

// 角色权限检查
export function hasRole(user: User | null, role: UserRole): boolean {
  return effectiveRoles(user?.roles || []).includes(role)
}

// 多角色权限检查
export function hasAnyRole(user: User | null, roles: UserRole[]): boolean {
  if (!user?.roles?.length) {
    return false
  }

  return roles.some((role) => effectiveRoles(user.roles!).includes(role))
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
  if (!user?.roles?.length) {
    return []
  }

  const permissions: Permission[] = []
  effectiveRoles(user.roles).forEach((role) => {
    const rolePermissions = ROLE_PERMISSIONS[role as UserRole] || []
    permissions.push(...rolePermissions)
  })

  return permissions.filter(
    (permission, index, self) =>
      index ===
      self.findIndex(
        (item) => item.resource === permission.resource && item.action === permission.action,
      ),
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
    [PermissionAction.EXPORT]: '导出病案记录',
  },
  [ResourceType.QC_RESULTS]: {
    [PermissionAction.READ]: '查看质控结果',
    [PermissionAction.UPDATE]: '修改质控结果',
    [PermissionAction.REVIEW]: '审核质控结果',
    [PermissionAction.EXPORT]: '导出质控结果',
  },
  [ResourceType.QC_RULES]: {
    [PermissionAction.CREATE]: '创建质控规则',
    [PermissionAction.READ]: '查看质控规则',
    [PermissionAction.UPDATE]: '修改质控规则',
    [PermissionAction.DELETE]: '删除质控规则',
    [PermissionAction.MANAGE]: '管理质控规则',
  },
  [ResourceType.USERS]: {
    [PermissionAction.CREATE]: '创建用户',
    [PermissionAction.READ]: '查看用户',
    [PermissionAction.UPDATE]: '修改用户',
    [PermissionAction.DELETE]: '删除用户',
    [PermissionAction.MANAGE]: '管理用户',
  },
  [ResourceType.STATISTICS]: {
    [PermissionAction.READ]: '查看统计数据',
    [PermissionAction.EXPORT]: '导出统计数据',
  },
  [ResourceType.SETTINGS]: {
    [PermissionAction.READ]: '查看系统设置',
    [PermissionAction.UPDATE]: '修改系统设置',
    [PermissionAction.MANAGE]: '管理系统设置',
  },
} as const

// 获取权限描述
export function getPermissionDescription(resource: ResourceType, action: PermissionAction): string {
  const resourceMap = PERMISSION_DESCRIPTIONS[resource] as
    | Partial<Record<PermissionAction, string>>
    | undefined
  return resourceMap?.[action] || `${resource}:${action}`
}

// 角色描述映射
export const ROLE_DESCRIPTIONS = {
  [UserRole.ADMIN]: '系统管理员',
  [UserRole.QC_MANAGER]: '质控管理员',
  [UserRole.QC_STAFF]: '质控人员',
  [UserRole.DOCTOR]: '医生',
} as const

// 获取角色描述
export function getRoleDescription(role: UserRole): string {
  return ROLE_DESCRIPTIONS[role] || role
}
