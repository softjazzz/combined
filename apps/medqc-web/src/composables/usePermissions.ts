/**
 * 权限管理组合式函数
 * 病案质控系统 - 权限检查与控制
 */

import { computed, inject, type ComputedRef } from 'vue'
// import { useAuthStore } from '@/stores/auth'

// 临时模拟AuthStore
const useAuthStore = () => ({
  user: null as User | null
})

// 临时类型定义
interface User {
  id: string
  email?: string
  display_name?: string
  department?: string
  hospital_id?: string
  roles?: string[]
  is_active?: boolean
  last_login?: string
  created_at?: string
  updated_at?: string
}

enum UserRole {
  ADMIN = 'admin',
  QC_MANAGER = 'qc_manager',
  QC_STAFF = 'qc_staff',
  DOCTOR = 'doctor'
}

enum PermissionAction {
  CREATE = 'create',
  READ = 'read',
  UPDATE = 'update',
  DELETE = 'delete',
  ANALYZE = 'analyze',
  REVIEW = 'review',
  MANAGE = 'manage',
  EXPORT = 'export'
}

enum ResourceType {
  MEDICAL_RECORDS = 'medical_records',
  QC_RESULTS = 'qc_results',
  QC_RULES = 'qc_rules',
  USERS = 'users',
  STATISTICS = 'statistics',
  SETTINGS = 'settings'
}

interface Permission {
  resource: ResourceType
  action: PermissionAction
}

interface PermissionCheckResult {
  allowed: boolean
  reason?: string
}

// 角色权限映射
const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  [UserRole.ADMIN]: [
    // 管理员拥有所有权限
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.CREATE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.READ },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.UPDATE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.DELETE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.ANALYZE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.EXPORT },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.READ },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.REVIEW },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.EXPORT },
    { resource: ResourceType.QC_RULES, action: PermissionAction.CREATE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.READ },
    { resource: ResourceType.QC_RULES, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.DELETE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.MANAGE },
    { resource: ResourceType.USERS, action: PermissionAction.CREATE },
    { resource: ResourceType.USERS, action: PermissionAction.READ },
    { resource: ResourceType.USERS, action: PermissionAction.UPDATE },
    { resource: ResourceType.USERS, action: PermissionAction.DELETE },
    { resource: ResourceType.USERS, action: PermissionAction.MANAGE },
    { resource: ResourceType.STATISTICS, action: PermissionAction.READ },
    { resource: ResourceType.STATISTICS, action: PermissionAction.EXPORT },
    { resource: ResourceType.SETTINGS, action: PermissionAction.READ },
    { resource: ResourceType.SETTINGS, action: PermissionAction.UPDATE },
    { resource: ResourceType.SETTINGS, action: PermissionAction.MANAGE }
  ],
  
  [UserRole.QC_MANAGER]: [
    // 质控管理员权限
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.READ },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.ANALYZE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.EXPORT },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.READ },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.REVIEW },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.EXPORT },
    { resource: ResourceType.QC_RULES, action: PermissionAction.CREATE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.READ },
    { resource: ResourceType.QC_RULES, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.DELETE },
    { resource: ResourceType.QC_RULES, action: PermissionAction.MANAGE },
    { resource: ResourceType.USERS, action: PermissionAction.READ },
    { resource: ResourceType.STATISTICS, action: PermissionAction.READ },
    { resource: ResourceType.STATISTICS, action: PermissionAction.EXPORT }
  ],
  
  [UserRole.QC_STAFF]: [
    // 质控人员权限
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.READ },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.ANALYZE },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.READ },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.REVIEW },
    { resource: ResourceType.QC_RULES, action: PermissionAction.READ },
    { resource: ResourceType.STATISTICS, action: PermissionAction.READ }
  ],
  
  [UserRole.DOCTOR]: [
    // 医生权限（只能操作自己的记录）
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.CREATE },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.READ },
    { resource: ResourceType.MEDICAL_RECORDS, action: PermissionAction.UPDATE },
    { resource: ResourceType.QC_RESULTS, action: PermissionAction.READ },
    { resource: ResourceType.STATISTICS, action: PermissionAction.READ }
  ]
}

/**
 * 权限管理组合式函数
 */
export function usePermissions() {
  const authStore = useAuthStore()
  
  // 当前用户
  const currentUser = computed(() => authStore.user)
  
  // 用户角色
  const userRoles = computed(() => currentUser.value?.roles || [])
  
  // 检查是否有指定权限
  const hasPermission = (resource: ResourceType, action: PermissionAction): boolean => {
    const user = currentUser.value
    if (!user || !user.roles) return false
    
    return user.roles.some((role: string) => {
      const rolePermissions = ROLE_PERMISSIONS[role as UserRole] || []
      return rolePermissions.some(permission => 
        permission.resource === resource && permission.action === action
      )
    })
  }
  
  // 检查权限（带上下文）
  const checkPermission = (
    resource: ResourceType, 
    action: PermissionAction,
    context?: Record<string, any>
  ): PermissionCheckResult => {
    const user = currentUser.value
    if (!user || !user.roles) {
      return { allowed: false, reason: '用户未认证' }
    }
    
    // 基础权限检查
    const hasBasicPermission = hasPermission(resource, action)
    if (!hasBasicPermission) {
      return { allowed: false, reason: '用户无此权限' }
    }
    
    // 特殊权限条件检查
    if (user.roles.includes(UserRole.DOCTOR)) {
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
        if (!user.roles.includes(UserRole.ADMIN) && context.department !== user.department) {
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
  
  // 角色检查
  const hasRole = (role: UserRole): boolean => {
    return userRoles.value.includes(role)
  }
  
  const hasAnyRole = (roles: UserRole[]): boolean => {
    return roles.some(role => userRoles.value.includes(role))
  }
  
  // 便捷的角色检查函数
  const isAdmin = computed(() => hasRole(UserRole.ADMIN))
  const isQCManager = computed(() => hasRole(UserRole.QC_MANAGER))
  const isQCStaff = computed(() => hasRole(UserRole.QC_STAFF))
  const isDoctor = computed(() => hasRole(UserRole.DOCTOR))
  
  // 便捷的权限检查函数
  const canCreateRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE))
  const canReadRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ))
  const canUpdateRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE))
  const canDeleteRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.DELETE))
  const canAnalyzeRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE))
  const canExportRecords = computed(() => hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.EXPORT))
  
  const canReadQCResults = computed(() => hasPermission(ResourceType.QC_RESULTS, PermissionAction.READ))
  const canUpdateQCResults = computed(() => hasPermission(ResourceType.QC_RESULTS, PermissionAction.UPDATE))
  const canReviewQCResults = computed(() => hasPermission(ResourceType.QC_RESULTS, PermissionAction.REVIEW))
  const canExportQCResults = computed(() => hasPermission(ResourceType.QC_RESULTS, PermissionAction.EXPORT))
  
  const canManageRules = computed(() => hasPermission(ResourceType.QC_RULES, PermissionAction.MANAGE))
  const canCreateRules = computed(() => hasPermission(ResourceType.QC_RULES, PermissionAction.CREATE))
  const canUpdateRules = computed(() => hasPermission(ResourceType.QC_RULES, PermissionAction.UPDATE))
  const canDeleteRules = computed(() => hasPermission(ResourceType.QC_RULES, PermissionAction.DELETE))
  
  const canManageUsers = computed(() => hasPermission(ResourceType.USERS, PermissionAction.MANAGE))
  const canCreateUsers = computed(() => hasPermission(ResourceType.USERS, PermissionAction.CREATE))
  const canUpdateUsers = computed(() => hasPermission(ResourceType.USERS, PermissionAction.UPDATE))
  const canDeleteUsers = computed(() => hasPermission(ResourceType.USERS, PermissionAction.DELETE))
  
  const canReadStatistics = computed(() => hasPermission(ResourceType.STATISTICS, PermissionAction.READ))
  const canExportStatistics = computed(() => hasPermission(ResourceType.STATISTICS, PermissionAction.EXPORT))
  
  const canManageSettings = computed(() => hasPermission(ResourceType.SETTINGS, PermissionAction.MANAGE))
  const canUpdateSettings = computed(() => hasPermission(ResourceType.SETTINGS, PermissionAction.UPDATE))
  
  // 组合权限检查
  const hasQCPermission = computed(() => hasAnyRole([UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.QC_STAFF]))
  const hasManagePermission = computed(() => hasAnyRole([UserRole.ADMIN, UserRole.QC_MANAGER]))
  
  // 获取用户权限列表
  const getUserPermissions = (): Permission[] => {
    const user = currentUser.value
    if (!user?.roles) return []
    
    const permissions: Permission[] = []
    user.roles.forEach((role: string) => {
      const rolePermissions = ROLE_PERMISSIONS[role as UserRole] || []
      permissions.push(...rolePermissions)
    })
    
    // 去重
    return permissions.filter((permission, index, self) => 
      index === self.findIndex(p => 
        p.resource === permission.resource && p.action === permission.action
      )
    )
  }
  
  // 权限描述
  const getPermissionDescription = (resource: ResourceType, action: PermissionAction): string => {
    const descriptions: Record<ResourceType, Record<PermissionAction, string>> = {
      [ResourceType.MEDICAL_RECORDS]: {
        [PermissionAction.CREATE]: '创建病案记录',
        [PermissionAction.READ]: '查看病案记录',
        [PermissionAction.UPDATE]: '修改病案记录',
        [PermissionAction.DELETE]: '删除病案记录',
        [PermissionAction.ANALYZE]: '分析病案记录',
        [PermissionAction.EXPORT]: '导出病案记录',
        [PermissionAction.REVIEW]: '审核病案记录',
        [PermissionAction.MANAGE]: '管理病案记录'
      },
      [ResourceType.QC_RESULTS]: {
        [PermissionAction.CREATE]: '创建质控结果',
        [PermissionAction.READ]: '查看质控结果',
        [PermissionAction.UPDATE]: '修改质控结果',
        [PermissionAction.DELETE]: '删除质控结果',
        [PermissionAction.ANALYZE]: '分析质控结果',
        [PermissionAction.EXPORT]: '导出质控结果',
        [PermissionAction.REVIEW]: '审核质控结果',
        [PermissionAction.MANAGE]: '管理质控结果'
      },
      [ResourceType.QC_RULES]: {
        [PermissionAction.CREATE]: '创建质控规则',
        [PermissionAction.READ]: '查看质控规则',
        [PermissionAction.UPDATE]: '修改质控规则',
        [PermissionAction.DELETE]: '删除质控规则',
        [PermissionAction.ANALYZE]: '分析质控规则',
        [PermissionAction.EXPORT]: '导出质控规则',
        [PermissionAction.REVIEW]: '审核质控规则',
        [PermissionAction.MANAGE]: '管理质控规则'
      },
      [ResourceType.USERS]: {
        [PermissionAction.CREATE]: '创建用户',
        [PermissionAction.READ]: '查看用户',
        [PermissionAction.UPDATE]: '修改用户',
        [PermissionAction.DELETE]: '删除用户',
        [PermissionAction.ANALYZE]: '分析用户',
        [PermissionAction.EXPORT]: '导出用户',
        [PermissionAction.REVIEW]: '审核用户',
        [PermissionAction.MANAGE]: '管理用户'
      },
      [ResourceType.STATISTICS]: {
        [PermissionAction.CREATE]: '创建统计数据',
        [PermissionAction.READ]: '查看统计数据',
        [PermissionAction.UPDATE]: '修改统计数据',
        [PermissionAction.DELETE]: '删除统计数据',
        [PermissionAction.ANALYZE]: '分析统计数据',
        [PermissionAction.EXPORT]: '导出统计数据',
        [PermissionAction.REVIEW]: '审核统计数据',
        [PermissionAction.MANAGE]: '管理统计数据'
      },
      [ResourceType.SETTINGS]: {
        [PermissionAction.CREATE]: '创建系统设置',
        [PermissionAction.READ]: '查看系统设置',
        [PermissionAction.UPDATE]: '修改系统设置',
        [PermissionAction.DELETE]: '删除系统设置',
        [PermissionAction.ANALYZE]: '分析系统设置',
        [PermissionAction.EXPORT]: '导出系统设置',
        [PermissionAction.REVIEW]: '审核系统设置',
        [PermissionAction.MANAGE]: '管理系统设置'
      }
    }
    
    return descriptions[resource]?.[action] || `${resource}:${action}`
  }
  
  // 角色描述
  const getRoleDescription = (role: UserRole): string => {
    const descriptions = {
      [UserRole.ADMIN]: '系统管理员',
      [UserRole.QC_MANAGER]: '质控管理员',
      [UserRole.QC_STAFF]: '质控人员',
      [UserRole.DOCTOR]: '医务人员'
    }
    return descriptions[role] || role
  }
  
  return {
    // 状态
    currentUser,
    userRoles,
    
    // 权限检查
    hasPermission,
    checkPermission,
    
    // 角色检查
    hasRole,
    hasAnyRole,
    
    // 便捷角色检查
    isAdmin,
    isQCManager,
    isQCStaff,
    isDoctor,
    
    // 便捷权限检查
    canCreateRecords,
    canReadRecords,
    canUpdateRecords,
    canDeleteRecords,
    canAnalyzeRecords,
    canExportRecords,
    
    canReadQCResults,
    canUpdateQCResults,
    canReviewQCResults,
    canExportQCResults,
    
    canManageRules,
    canCreateRules,
    canUpdateRules,
    canDeleteRules,
    
    canManageUsers,
    canCreateUsers,
    canUpdateUsers,
    canDeleteUsers,
    
    canReadStatistics,
    canExportStatistics,
    
    canManageSettings,
    canUpdateSettings,
    
    // 组合权限检查
    hasQCPermission,
    hasManagePermission,
    
    // 工具函数
    getUserPermissions,
    getPermissionDescription,
    getRoleDescription,
    
    // 枚举导出
    UserRole,
    PermissionAction,
    ResourceType
  }
}

/**
 * 权限指令组合式函数
 */
export function usePermissionDirective() {
  const { hasPermission, checkPermission } = usePermissions()
  
  // v-permission 指令实现
  const vPermission = {
    mounted(el, binding) {
      const { resource, action, context } = binding.value
      
      if (!resource || !action) {
        console.warn('v-permission 指令需要 resource 和 action 参数')
        return
      }
      
      const result = checkPermission(resource, action, context)
      if (!result.allowed) {
        el.style.display = 'none'
        el.setAttribute('title', result.reason || '无权限')
      }
    },
    
    updated(el, binding) {
      const { resource, action, context } = binding.value
      
      if (!resource || !action) {
        console.warn('v-permission 指令需要 resource 和 action 参数')
        return
      }
      
      const result = checkPermission(resource, action, context)
      if (!result.allowed) {
        el.style.display = 'none'
        el.setAttribute('title', result.reason || '无权限')
      } else {
        el.style.display = ''
        el.removeAttribute('title')
      }
    }
  }
  
  return {
    vPermission
  }
} 