import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { ApiService } from '@/services/apiService'
import { useBusinessReadAccess } from '@/composables/useBusinessReadAccess'
import { UserRole, type AuthUserRole } from '@/types/auth'

describe('新增业务查看入口的账号边界', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it.each<{ roles: AuthUserRole[]; readOnly: boolean }>([
    { roles: ['sync_admin'], readOnly: true },
    { roles: [UserRole.ADMIN], readOnly: false },
    { roles: [UserRole.QC_MANAGER], readOnly: false },
    { roles: ['sync_admin', UserRole.ADMIN], readOnly: false },
  ])('$roles 只读=$readOnly，使用真实认证store', async ({ roles, readOnly }) => {
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true, data: { id: 'read-test', roles, is_demo_account: true },
    })
    await useAuthStore().initialize()
    expect(useBusinessReadAccess().isBusinessReadOnly.value).toBe(readOnly)
  })
})
