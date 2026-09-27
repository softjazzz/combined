import { describe, expect, it, vi } from 'vitest'

vi.unmock('vue-router')

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: true, userRoles: ['sync_admin'], initialize: vi.fn() }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('@/router')
const { canAccessRouteMeta } = await import('@/utils/routeAccess')

describe('测试病历管理路由权限', () => {
  it('与后端样本池接口角色一致：admin、qc_manager、sync_admin 可见，developer 不可见', () => {
    const resolved = router.resolve({ name: 'TestMedicalRecords' })
    expect(resolved.meta.permission).toEqual(['admin', 'qc_manager', 'sync_admin'])
    for (const role of ['admin', 'qc_manager', 'sync_admin']) {
      expect(canAccessRouteMeta(resolved.meta, [role])).toBe(true)
    }
    expect(canAccessRouteMeta(resolved.meta, ['developer'])).toBe(false)
  })
})
