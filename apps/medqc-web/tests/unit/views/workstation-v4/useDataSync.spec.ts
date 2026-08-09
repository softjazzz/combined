import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

let mockUserRoles: string[] = []

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get userRoles() {
      return mockUserRoles
    },
  }),
}))

describe('useDataSync 系统配置权限', () => {
  beforeEach(() => {
    mockUserRoles = []
  })

  it.each(['admin', 'sync_admin', 'super_admin'])('%s 可以修改同步配置', (role) => {
    mockUserRoles = [role]

    const { isReadonly } = useDataSync()

    expect(isReadonly.value).toBe(false)
  })

  it.each(['qc_manager', 'doctor'])('%s 只能读取同步配置', (role) => {
    mockUserRoles = [role]

    const { isReadonly } = useDataSync()

    expect(isReadonly.value).toBe(true)
  })
})
