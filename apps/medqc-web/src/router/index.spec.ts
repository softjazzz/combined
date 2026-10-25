import { describe, expect, it, vi } from 'vitest'
import { WORKSTATION_NAV, filterVisibleNav } from '@/components/layout/workstationNav'

vi.unmock('vue-router')
const authState = vi.hoisted(() => ({ roles: ['admin'] }))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    userRoles: authState.roles,
    initialize: vi.fn(),
  }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('./index')

describe('旧 Dashboard 首页路由', () => {
  it('sync_admin通过真实路由守卫进入旧首页地址，不回退dashboard', async () => {
    authState.roles.splice(0, authState.roles.length, 'sync_admin')
    try {
      await router.push('/workstation-v5/qc-overview')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/qc-overview')
      await router.push('/workstation-v5/rules/validation/LX0609-01-01-01/cases/new')
      expect(router.currentRoute.value.name).toBe('WorkstationV4RuleValidationNewCase')
    } finally {
      authState.roles.splice(0, authState.roles.length, 'admin')
    }
  }, 15_000)
  it('同步管理员菜单与演示账号一致，直接URL和创建验收病例均允许', () => {
    const visible = (roles: string[], demo: boolean) => filterVisibleNav(WORKSTATION_NAV, {
      userRoles: roles,
      isDemoFeedbackAccount: demo,
      resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
    }).flatMap((group) => group.items.map((item) => item.key))
    expect(visible(['sync_admin'], false)).toEqual(visible(['admin', 'qc_manager'], true))
    for (const path of ['records/running', 'records/final', 'qc-feedback-demo', 'rules/custom-workspace', 'rules/validation', 'rules/validation/LX0609-01-01-01', 'qc-overview', 'system-config']) {
      expect(router.resolve(`/workstation-v5/${path}`).meta.permission).toContain('sync_admin')
    }
    expect(visible(['sync_admin'], false)).toContain('rule-validation')
  })
  it('不再挂载 DashboardView，并安全跳转到工作台首页', async () => {
    const dashboardRoute = router.getRoutes().find((route) => route.name === 'Dashboard')

    expect(dashboardRoute?.redirect).toBeTypeOf('function')
    expect(dashboardRoute?.components).toBeUndefined()

    const redirect = dashboardRoute?.redirect
    if (typeof redirect !== 'function') {
      throw new Error('旧 Dashboard 首页必须使用函数重定向')
    }
    const target = redirect({
      query: { source: 'legacy-link', scene: 'final' },
      hash: '#recent-task',
    } as never)

    expect(target).toEqual({
      path: '/workstation-v5',
      query: { source: 'legacy-link', scene: 'final' },
      hash: '#recent-task',
    })
  })

  it('根入口直达工作台，不经过旧 Dashboard 形成循环', async () => {
    const rootRoute = router.getRoutes().find((route) => route.path === '/')

    expect(rootRoute?.redirect).toBe('/workstation-v5')
  })

  it('工作台入口保持原路径与参数', async () => {
    const target = router.resolve({ path: '/workstation-v5', query: { entry: 'direct' } })

    expect(target.path).toBe('/workstation-v5')
    expect(target.query).toEqual({ entry: 'direct' })
  })

  it(
    '旧 V4 链接自动升级到对应的 V5 地址',
    async () => {
      await router.push('/workstation-v4/records/running?source=legacy')

      expect(router.currentRoute.value.fullPath).toBe(
        '/workstation-v5/records/running?source=legacy',
      )
    },
    15_000,
  )
})
