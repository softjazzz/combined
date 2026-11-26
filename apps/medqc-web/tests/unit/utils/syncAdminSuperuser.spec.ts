import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { ApiService } from '@/services/apiService'
import { usePermissions } from '@/composables/usePermissions'
import { effectiveRoles } from '@/utils/effectiveRoles'
import {
  PERMISSIONS,
  checkPermission,
  getRoleDescription,
  getUserPermissions,
  hasAnyRole,
  hasPermission,
  hasRole,
  isAdmin,
  isSuperAdmin,
} from '@/utils/permissions'
import { PermissionAction, ResourceType, UserRole, type User } from '@/types/auth'

describe('sync_admin 与 super_admin 超级管理员权限', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  const syncAdminUser: User = {
    id: 'sync-test',
    roles: ['sync_admin'],
    department: 'ops',
    hospital_id: 'test',
  }
  const superAdminUser: User = {
    id: 'super-test',
    roles: ['super_admin'],
    department: 'ops',
    hospital_id: 'test',
  }

  it('授权角色包含所有管理能力但不附加医生身份，不修改原角色', () => {
    const roles = ['sync_admin']
    expect(effectiveRoles(roles)).toEqual([
      'sync_admin',
      'admin',
      'qc_manager',
      'developer',
      'super_admin',
    ])
    expect(roles).toEqual(['sync_admin'])
    expect(effectiveRoles(['doctor'])).toEqual(['doctor'])
  })

  it('纯 super_admin 展开管理角色但不附加 sync_admin 或 doctor，不修改原角色', () => {
    const roles = ['super_admin']
    const expanded = effectiveRoles(roles)
    expect(expanded).toEqual(['super_admin', 'admin', 'qc_manager', 'developer'])
    expect(expanded).not.toContain('sync_admin')
    expect(expanded).not.toContain('doctor')
    expect(roles).toEqual(['super_admin'])
  })

  it('纯 super_admin 具备全部已定义资源操作权限且不受跨科室/跨院区条件拦截', () => {
    const permissions = Object.values(PERMISSIONS).flatMap((group) => Object.values(group))
    for (const permission of permissions) {
      expect(hasPermission(superAdminUser, permission.resource, permission.action)).toBe(true)
      expect(
        checkPermission(superAdminUser, permission.resource, permission.action, {
          hospital_id: 'other',
          department: 'other',
          doctor_id: 'another-doc',
        }).allowed,
      ).toBe(true)
    }
    expect(getUserPermissions(superAdminUser)).toHaveLength(permissions.length)
    expect(isAdmin(superAdminUser)).toBe(true)
    expect(isSuperAdmin(superAdminUser)).toBe(true)
    expect(hasRole(superAdminUser, 'super_admin')).toBe(true)
    expect(hasRole(superAdminUser, UserRole.ADMIN)).toBe(true)
    expect(hasAnyRole(superAdminUser, ['super_admin', 'sync_admin'])).toBe(true)
    expect(getRoleDescription('super_admin')).toBe('超级管理员')
    expect(getRoleDescription('sync_admin')).toBe('同步管理员')
  })

  it('sync_admin 具备全部已定义资源操作权限', () => {
    const permissions = Object.values(PERMISSIONS).flatMap((group) => Object.values(group))
    for (const permission of permissions) {
      expect(hasPermission(syncAdminUser, permission.resource, permission.action)).toBe(true)
      expect(
        checkPermission(syncAdminUser, permission.resource, permission.action, {
          hospital_id: 'other',
          department: 'other',
        }).allowed,
      ).toBe(true)
    }
    expect(getUserPermissions(syncAdminUser)).toHaveLength(permissions.length)
    expect(isAdmin(syncAdminUser)).toBe(true)
    expect(isSuperAdmin(syncAdminUser)).toBe(true)
    expect(
      hasPermission({ id: 'doctor', roles: [] }, permissions[0].resource, permissions[0].action),
    ).toBe(false)
  })

  it('真实认证store统一提供继承权限，同时保留原始角色', async () => {
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({ success: true, data: syncAdminUser })
    const auth = useAuthStore()
    await auth.initialize()
    expect(auth.userRoles).toEqual(effectiveRoles(['sync_admin']))
    expect(auth.user?.roles).toEqual(['sync_admin'])
  })

  it('usePermissions 绑定真实 authStore，正确评估 super_admin、doctor 与未登录态', async () => {
    const permissions = usePermissions()
    expect(permissions.currentUser.value).toBeNull()
    expect(permissions.isAdmin.value).toBe(false)
    expect(permissions.hasPermission(ResourceType.SETTINGS, PermissionAction.MANAGE)).toBe(false)
    expect(permissions.checkPermission(ResourceType.SETTINGS, PermissionAction.MANAGE)).toEqual({
      allowed: false,
      reason: '用户未认证',
    })

    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true,
      data: superAdminUser,
    })
    const auth = useAuthStore()
    await auth.initialize()

    expect(permissions.currentUser.value?.id).toBe('super-test')
    expect(permissions.isAdmin.value).toBe(true)
    expect(permissions.isSuperAdmin.value).toBe(true)
    expect(permissions.canManageSettings.value).toBe(true)
    expect(permissions.canManageUsers.value).toBe(true)
    expect(
      permissions.checkPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ, {
        department: 'other-dept',
        hospital_id: 'other-hospital',
      }).allowed,
    ).toBe(true)

    // 切换到普通医生角色：受本科室与本人病历限制
    setActivePinia(createPinia())
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true,
      data: {
        id: 'doc-1',
        roles: [UserRole.DOCTOR],
        department: '心内科',
        hospital_id: 'hosp-1',
      },
    })
    const doctorAuth = useAuthStore()
    await doctorAuth.initialize()
    const doctorPermissions = usePermissions()

    expect(doctorPermissions.isAdmin.value).toBe(false)
    expect(doctorPermissions.isDoctor.value).toBe(true)
    expect(doctorPermissions.canManageSettings.value).toBe(false)
    expect(
      doctorPermissions.checkPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ, {
        doctor_id: 'doc-1',
        department: '心内科',
        hospital_id: 'hosp-1',
      }).allowed,
    ).toBe(true)
    expect(
      doctorPermissions.checkPermission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ, {
        doctor_id: 'doc-2',
        department: '心内科',
        hospital_id: 'hosp-1',
      }).allowed,
    ).toBe(false)
  })
})
