import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { ApiService } from '@/services/apiService'
import { effectiveRoles } from '@/utils/effectiveRoles'
import { PERMISSIONS, checkPermission, getUserPermissions, hasPermission } from '@/utils/permissions'
import type { User } from '@/types/auth'

describe('sync_admin超级管理员', () => {
  beforeEach(() => setActivePinia(createPinia()))
  const user: User = { id: 'sync-test', roles: ['sync_admin'], department: 'ops', hospital_id: 'test' }

  it('授权角色包含所有管理能力但不附加医生身份，不修改原角色', () => {
    const roles = ['sync_admin']
    expect(effectiveRoles(roles)).toEqual(['sync_admin', 'admin', 'qc_manager', 'developer', 'super_admin'])
    expect(roles).toEqual(['sync_admin'])
    expect(effectiveRoles(['doctor'])).toEqual(['doctor'])
  })

  it('具备全部已定义资源操作权限', () => {
    const permissions = Object.values(PERMISSIONS).flatMap((group) => Object.values(group))
    for (const permission of permissions) {
      expect(hasPermission(user, permission.resource, permission.action)).toBe(true)
      expect(checkPermission(user, permission.resource, permission.action, { hospital_id: 'other', department: 'other' }).allowed).toBe(true)
    }
    expect(getUserPermissions(user)).toHaveLength(permissions.length)
    expect(hasPermission({ id: 'doctor', roles: [] }, permissions[0].resource, permissions[0].action)).toBe(false)
  })

  it('真实认证store统一提供继承权限，同时保留原始角色', async () => {
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({ success: true, data: user })
    const auth = useAuthStore()
    await auth.initialize()
    expect(auth.userRoles).toEqual(effectiveRoles(['sync_admin']))
    expect(auth.user?.roles).toEqual(['sync_admin'])
  })
})
