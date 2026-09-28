import { describe, expect, it, vi } from 'vitest'

// 本文件用例会真实导航并懒加载路由组件树（结果清单、审核面板等），全量并发下单条可超过 15 秒。
vi.setConfig({ testTimeout: 30_000 })

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
  it('扫码确认页必须登录且不额外限制角色', () => {
    const route = router.getRoutes().find((item) => item.name === 'QrLoginConfirm')
    expect(route?.path).toBe('/auth/qr-confirm')
    expect(route?.meta).toMatchObject({ requiresAuth: true, title: '确认电脑登录' })
    expect(route?.meta.permission).toBeUndefined()
  })

  it('编码质控点管理使用独立菜单路由且仅管理员角色可进入', () => {
    const route = router.getRoutes().find((item) => item.name === 'CodingQualityControlPointManagement')
    expect(route?.path).toBe('/dashboard/coding-quality-control')
    expect(route?.meta).toMatchObject({
      title: '编码质控点管理',
      permission: ['admin', 'qc_manager'],
    })
    expect(route?.props?.default).toEqual({ managementMode: 'coding' })
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
    30_000,
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
