/**
 * 权限管理组合式函数
 * 病案质控系统 - 权限检查与控制
 */

import { computed, type DirectiveBinding } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  PermissionAction,
  ResourceType,
  UserRole,
  type AuthUserRole,
  type Permission,
  type PermissionCheckResult,
  type User,
} from '@/types/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'
import {
  checkPermission as checkUserPermission,
  getPermissionDescription,
  getRoleDescription,
  getUserPermissions as getUserPermissionList,
  hasAnyRole as userHasAnyRole,
  hasManagePermission as userHasManagePermission,
  hasPermission as userHasPermission,
  hasQCPermission as userHasQCPermission,
  hasRole as userHasRole,
  isAdmin as userIsAdmin,
  isDoctor as userIsDoctor,
  isQCManager as userIsQCManager,
  isQCStaff as userIsQCStaff,
  isSuperAdmin as userIsSuperAdmin,
} from '@/utils/permissions'

export { UserRole, PermissionAction, ResourceType }

interface StoreUserLike {
  id: string
  email?: string
  display_name?: string
  department?: string
  hospital_id?: string
  institute_id?: string
  roles?: readonly string[]
  role?: string
  is_active?: boolean
  last_login?: string
  created_at?: string
  updated_at?: string
  is_demo_account?: boolean
}

/**
 * 权限管理组合式函数
 */
export function usePermissions() {
  const authStore = useAuthStore()

  // 当前用户
  const currentUser = computed(() => authStore.user)

  // 用户有效角色（通过 authStore.userRoles / effectiveRoles 统一展开 super_admin 与 sync_admin）
  const userRoles = computed<string[]>(() => {
    const storeRoles = (authStore as { userRoles?: readonly string[] }).userRoles
    if (Array.isArray(storeRoles) && storeRoles.length > 0) {
      return [...storeRoles]
    }
    const user = currentUser.value as StoreUserLike | null
    if (!user) return []
    if (Array.isArray(user.roles)) {
      return effectiveRoles(user.roles)
    }
    if (user.role) {
      return effectiveRoles([user.role])
    }
    return []
  })

  // 归一化后的用户对象，供 @/utils/permissions 统一鉴权
  const permissionUser = computed<User | null>(() => {
    const user = currentUser.value as StoreUserLike | null
    if (!user) return null
    return {
      ...user,
      roles: userRoles.value as AuthUserRole[],
    }
  })

  // 检查是否有指定权限
  const hasPermission = (resource: ResourceType, action: PermissionAction): boolean => {
    return userHasPermission(permissionUser.value, resource, action)
  }

  // 检查权限（带上下文）
  const checkPermission = (
    resource: ResourceType,
    action: PermissionAction,
    context?: Record<string, unknown>,
  ): PermissionCheckResult => {
    return checkUserPermission(permissionUser.value, resource, action, context)
  }

  // 角色检查
  const hasRole = (role: AuthUserRole | string): boolean => {
    return userHasRole(permissionUser.value, role)
  }

  const hasAnyRole = (roles: ReadonlyArray<AuthUserRole | string>): boolean => {
    return userHasAnyRole(permissionUser.value, roles)
  }

  // 便捷的角色检查函数
  const isAdmin = computed(() => userIsAdmin(permissionUser.value))
  const isSuperAdmin = computed(() => userIsSuperAdmin(permissionUser.value))
  const isQCManager = computed(() => userIsQCManager(permissionUser.value))
  const isQCStaff = computed(() => userIsQCStaff(permissionUser.value))
  const isDoctor = computed(() => userIsDoctor(permissionUser.value))

  // 便捷的权限检查函数
  const canCreateRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE),
  )
  const canReadRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ),
  )
  const canUpdateRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE),
  )
  const canDeleteRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.DELETE),
  )
  const canAnalyzeRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE),
  )
  const canExportRecords = computed(() =>
    hasPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.EXPORT),
  )

  const canReadQCResults = computed(() =>
    hasPermission(ResourceType.QC_RESULTS, PermissionAction.READ),
  )
  const canUpdateQCResults = computed(() =>
    hasPermission(ResourceType.QC_RESULTS, PermissionAction.UPDATE),
  )
  const canReviewQCResults = computed(() =>
    hasPermission(ResourceType.QC_RESULTS, PermissionAction.REVIEW),
  )
  const canExportQCResults = computed(() =>
    hasPermission(ResourceType.QC_RESULTS, PermissionAction.EXPORT),
  )

  const canManageRules = computed(() =>
    hasPermission(ResourceType.QC_RULES, PermissionAction.MANAGE),
  )
  const canCreateRules = computed(() =>
    hasPermission(ResourceType.QC_RULES, PermissionAction.CREATE),
  )
  const canUpdateRules = computed(() =>
    hasPermission(ResourceType.QC_RULES, PermissionAction.UPDATE),
  )
  const canDeleteRules = computed(() =>
    hasPermission(ResourceType.QC_RULES, PermissionAction.DELETE),
  )

  const canManageUsers = computed(() =>
    hasPermission(ResourceType.USERS, PermissionAction.MANAGE),
  )
  const canCreateUsers = computed(() =>
    hasPermission(ResourceType.USERS, PermissionAction.CREATE),
  )
  const canUpdateUsers = computed(() =>
    hasPermission(ResourceType.USERS, PermissionAction.UPDATE),
  )
  const canDeleteUsers = computed(() =>
    hasPermission(ResourceType.USERS, PermissionAction.DELETE),
  )

  const canReadStatistics = computed(() =>
    hasPermission(ResourceType.STATISTICS, PermissionAction.READ),
  )
  const canExportStatistics = computed(() =>
    hasPermission(ResourceType.STATISTICS, PermissionAction.EXPORT),
  )

  const canManageSettings = computed(() =>
    hasPermission(ResourceType.SETTINGS, PermissionAction.MANAGE),
  )
  const canUpdateSettings = computed(() =>
    hasPermission(ResourceType.SETTINGS, PermissionAction.UPDATE),
  )

  // 组合权限检查
  const hasQCPermission = computed(() => userHasQCPermission(permissionUser.value))
  const hasManagePermission = computed(() => userHasManagePermission(permissionUser.value))

  // 获取用户权限列表
  const getUserPermissions = (): Permission[] => {
    return getUserPermissionList(permissionUser.value)
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
    isSuperAdmin,
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
    ResourceType,
  }
}

/**
 * 权限指令组合式函数
 */
export function usePermissionDirective() {
  const { checkPermission } = usePermissions()

  interface PermissionDirectiveValue {
    resource: ResourceType
    action: PermissionAction
    context?: Record<string, unknown>
  }

  // v-permission 指令实现
  const vPermission = {
    mounted(el: HTMLElement, binding: DirectiveBinding<PermissionDirectiveValue>) {
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

    updated(el: HTMLElement, binding: DirectiveBinding<PermissionDirectiveValue>) {
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
    },
  }

  return {
    vPermission,
  }
}
