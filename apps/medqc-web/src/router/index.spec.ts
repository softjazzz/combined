import { describe, expect, it, vi } from 'vitest'

vi.unmock('vue-router')

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    userRoles: ['admin'],
    initialize: vi.fn(),
  }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('./index')

describe('旧 Dashboard 首页路由', () => {
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

  it('旧运行病历入口保留 query 和 hash，并只进入 V5 病历池', async () => {
    const legacyRoute = router.getRoutes().find((route) => route.name === 'RunningRecords')

    expect(legacyRoute?.redirect).toBeTypeOf('function')
    expect(legacyRoute?.components).toBeUndefined()

    await router.push('/dashboard/records/running?source=legacy&stage=review#record-list')

    expect(router.currentRoute.value.fullPath).toBe(
      '/workstation-v5/records/running?source=legacy&stage=review#record-list',
    )
  })
})
