import { describe, expect, it, vi } from 'vitest'
import {
  WORKSTATION_NAV,
  filterVisibleNav,
  findActiveNav,
  resolveBreadcrumb,
} from '@/components/layout/workstationNav'

vi.unmock('vue-router')
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: true, userRoles: ['admin'], initialize: vi.fn() }),
}))
window.scrollTo = vi.fn()
const { default: router } = await import('@/router')
const path = '/workstation-v5/users'

describe('用户管理独立入口沿用持久账号 owner', () => {
  it.each(['admin', 'sync_admin', 'super_admin'])('%s 可看到与直接路由权限一致的入口', (role) => {
    const groups = filterVisibleNav(WORKSTATION_NAV, {
      isDemoFeedbackAccount: false,
      userRoles: [role],
      resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
    })
    const entry = groups
      .flatMap((group) => group.items)
      .find((item) => item.key === 'user-management')
    expect(entry?.to.path).toBe(path)
    expect(router.resolve(path).meta.permission).toEqual(['admin', 'sync_admin', 'super_admin'])
    expect(findActiveNav(groups, { path, query: {}, meta: {} })?.item.key).toBe('user-management')
    expect(resolveBreadcrumb(groups, { path, query: {}, meta: {} })).toEqual([
      '数据与配置',
      '用户管理',
    ])
  })
  it.each(['doctor', 'qc_staff', 'qc_manager'])('%s 不新增用户管理权限', (role) => {
    const groups = filterVisibleNav(WORKSTATION_NAV, {
      isDemoFeedbackAccount: false,
      userRoles: [role],
      resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
    })
    expect(
      groups.flatMap((group) => group.items).some((item) => item.key === 'user-management'),
    ).toBe(false)
  })
  it('旧账号管理深链和注册审批深链继续有效', () => {
    const old = router.resolve(
      '/workstation-v5/system-config?tab=accounts&registration_id=test-request',
    )
    expect(old.name).toBe('WorkstationV4SystemConfig')
    expect(old.query).toEqual({ tab: 'accounts', registration_id: 'test-request' })
  })
})
