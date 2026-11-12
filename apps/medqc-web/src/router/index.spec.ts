import { describe, expect, it, vi } from 'vitest'
import { WORKSTATION_NAV, filterVisibleNav } from '@/components/layout/workstationNav'

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

  it('sync_admin通过真实路由守卫进入旧首页地址，不回退dashboard', async () => {
    auth.roles.splice(0, auth.roles.length, 'sync_admin')
    try {
      await router.push('/workstation-v5/qc-overview')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/qc-overview')
      await router.push('/workstation-v5/rules/validation/LX0609-01-01-01/cases/new')
      expect(router.currentRoute.value.name).toBe('WorkstationV4RuleValidationNewCase')
    } finally {
      auth.roles.splice(0, auth.roles.length, 'admin')
    }
  }, 15_000)
  it('同步管理员菜单与演示账号一致，直接URL和创建验收病例均允许', () => {
    const visible = (roles: string[], demo: boolean) =>
      filterVisibleNav(WORKSTATION_NAV, {
        userRoles: roles,
        isDemoFeedbackAccount: demo,
        resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
      }).flatMap((group) => group.items.map((item) => item.key))
    expect(visible(['sync_admin'], false)).toEqual(visible(['admin', 'qc_manager'], true))
    for (const path of [
      'records/running',
      'records/final',
      'qc-feedback-demo',
      'rules/custom-workspace',
      'rules/validation',
      'rules/validation/LX0609-01-01-01',
      'qc-overview',
      'system-config',
    ]) {
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

  it('旧 V4 链接自动升级到对应的 V5 地址', async () => {
    await router.push('/workstation-v4/records/running?source=legacy')

    expect(router.currentRoute.value.fullPath).toBe('/workstation-v5/records/running?source=legacy')
  }, 15_000)
})


describe('反馈与整改入口保护', () => {
  it('旧整改URL复用正式页面，不再进入旧接口页面', async () => {
    const legacy = router.resolve('/dashboard/qc/rectifications').matched.at(-1)!
    const modern = router.resolve('/workstation-v5/feedback').matched.at(-1)!
    auth.roles.splice(0, auth.roles.length, 'admin')
    await router.push('/dashboard/qc/rectifications')
    await router.push('/workstation-v5/feedback')
    expect(legacy.components!.default).toBe(modern.components!.default)
    expect(legacy.meta.permission).toContain('doctor')
  })
  it.each(['/demo/lx33', '/demo/lx33/feedbacks'])('%s 必须登录管理员', path => {
    const meta = router.resolve(path).meta
    expect(meta.requiresAuth).toBe(true)
    expect(meta.permission).toEqual(['admin', 'super_admin', 'sync_admin'])
  })
})
