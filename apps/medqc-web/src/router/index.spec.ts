import { describe, expect, it, vi } from 'vitest'

vi.unmock('vue-router')
const auth = vi.hoisted(() => ({ roles: ['admin'] }))
vi.mock('@/components/layout/WorkstationLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation/HomeRectificationTodos.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/qc/reports/StaffAnalysisView.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation-v4/WorkstationV4HomeEntry.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation-v4/WorkstationV4View.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/views/workstation/MessageCenter.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation-v4/QcRecordResultListView.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    userRoles: auth.roles,
    initialize: vi.fn(),
  }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('./index')

describe('旧 Dashboard 首页路由', () => {
  it('管理角色旧消息入口改走独立中心，普通质控员不因此得到病历池权限', async () => {
    auth.roles.splice(0, auth.roles.length, 'qc_staff')
    try {
      await router.push('/workstation-v5/worklist?assist=message')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/messages')
      expect(router.resolve('/workstation-v5/worklist').meta.permission).not.toContain('qc_staff')
      expect(router.resolve('/workstation-v5/records/running').meta.permission).not.toContain(
        'qc_staff',
      )
      await router.push('/workstation-v5/worklist')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/feedback')
    } finally {
      auth.roles.splice(0, auth.roles.length, 'admin')
    }
  }, 15000)

  it('医生旧消息面板保持原址，管理侧消息中心不开放给医生', async () => {
    auth.roles.splice(0, auth.roles.length, 'doctor')
    try {
      await router.push('/workstation-v5/worklist?assist=message')
      expect(router.currentRoute.value.fullPath).toBe('/workstation-v5/worklist?assist=message')
      expect(router.resolve('/workstation-v5/messages').meta.permission).not.toContain('doctor')
    } finally {
      auth.roles.splice(0, auth.roles.length, 'admin')
    }
  }, 15000)

  it('普通质控员被拒绝后进入有权访问的待办，不扩大报表权限', async () => {
    auth.roles.splice(0, auth.roles.length, 'qc_staff')
    try {
      await router.push('/workstation-v5/reports/staff-analysis')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/feedback')
      expect(
        router.resolve('/workstation-v5/reports/staff-analysis').meta.permission,
      ).not.toContain('qc_staff')
      await router.push('/workstation-v5')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/feedback')
    } finally {
      auth.roles.splice(0, auth.roles.length, 'admin')
    }
  }, 15000)
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

  it('旧 V4 链接自动升级到对应的 V5 地址', async () => {
    await router.push('/workstation-v4/records/running?source=legacy')

    expect(router.currentRoute.value.fullPath).toBe('/workstation-v5/records/running?source=legacy')
  }, 15_000)
})
