import { describe, expect, it, vi } from 'vitest'
import { WORKSTATION_NAV, filterVisibleNav } from '@/components/layout/workstationNav'

vi.unmock('vue-router')
const auth = vi.hoisted(() => ({ authenticated: true, roles: ['admin'] }))
vi.mock('@/components/layout/WorkstationLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/auth/ProfileView.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/views/workstation-v4/WorkstationLoginView.vue', () => ({
  default: { template: '<div />' },
}))
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
    isAuthenticated: auth.authenticated,
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
      await router.push('/workstation-v5?source=dashboard&record_id=V&action=open_record')
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

  it('仪表盘旧根链接先进入病历池，消费联动参数后仍在病历池', async () => {
    const query = {
      source: 'dashboard',
      record_id: '["H","P","V"]',
      action: 'open_record',
      from_stage: 'frontpage_qc',
      keep: '1',
    }
    await router.push({ path: '/dashboard', query, hash: '#chart' })
    expect(router.currentRoute.value.name).toBe('WorkstationV4Worklist')
    expect(router.currentRoute.value.query).toEqual(query)
    expect(router.currentRoute.value.hash).toBe('#chart')

    await router.replace({ path: router.currentRoute.value.path, query: { keep: '1' } })
    expect(router.currentRoute.value.name).toBe('WorkstationV4Worklist')

    await router.push('/workstation-v5?stage=frontpage_qc')
    expect(router.currentRoute.value.name).toBe('WorkstationV4Index')
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
})

describe('历史页面下线重定向', () => {
  it.each([
    '/workstation-v2',
    '/workstation-v2/icd',
    '/workstation-v2/drg/pre',
    '/workstation-v2/old/nested',
    '/workstation-v3',
    '/demo',
    '/demo/lx33',
    '/demo/lx33/feedbacks',
    '/demo/lx33/create',
    '/demo/lx33/frontpage-demo',
    '/demo/clinical-workstation',
    '/demo/frontpage',
    '/dashboard/records/outpatient-emergency',
    '/dashboard/records/running',
    '/dashboard/records/final',
    '/dashboard/tasks/my',
    '/dashboard/tasks/all',
    '/dashboard/quality-control',
    '/dashboard/quality-control/create',
    '/dashboard/scoring-rules',
    '/dashboard/staff-ranking',
    '/dashboard/notifications',
    '/dashboard/permissions',
    '/dashboard/frontpage-demo',
    '/dashboard/llm-qc-demo',
    '/dashboard/llm-qc-demo-enhanced',
    '/dashboard/llm-qc-demo-new',
    '/dashboard/sichuan-qc-demo',
    '/dashboard/test-demo',
    '/dashboard/medical-records/R-1/legacy',
    '/dashboard/medical-records/R-1/simple',
  ])('%s 经 V4 入口进入现行工作台并保留参数', async (path) => {
    const matched = router.resolve(path).matched.at(-1)
    expect(matched?.redirect).toEqual({ path: '/workstation-v4' })
    expect(matched?.components).toBeFalsy()

    await router.push({ path, query: { keep: ['1', '2'] }, hash: '#recent' })
    expect(router.currentRoute.value.fullPath).toBe('/workstation-v5?keep=1&keep=2#recent')
    expect(router.currentRoute.value.params).toEqual({})
  })

  it('未登录时由工作台守卫处理旧演示链接', async () => {
    auth.authenticated = false
    try {
      await router.push('/demo/lx33/create?demo=true#rule')
      expect(router.currentRoute.value.path).toBe('/workstation-v5/login')
      expect(router.currentRoute.value.query.redirect).toBe('/workstation-v5?demo=true#rule')
    } finally {
      auth.authenticated = true
    }
  })

  it('无工作台首页权限的账号进入个人资料，避免在旧首页间循环', async () => {
    auth.roles.splice(0, auth.roles.length, 'coder')
    try {
      await router.push('/demo/lx33/feedbacks')
      expect(router.currentRoute.value.path).toBe('/auth/profile')
    } finally {
      auth.roles.splice(0, auth.roles.length, 'admin')
    }
  })

  it.each([
    ['/workstation-v4', 'WorkstationV4Index'],
    ['/workstation-v4/records/outpatient-emergency', 'WorkstationV4OutpatientEmergencyRecords'],
    ['/workstation-v4/records/running', 'WorkstationV4RunningRecords'],
    ['/workstation-v4/rules/custom-workspace', 'WorkstationV4CustomRuleWorkspace'],
    ['/workstation-v4/grouper', 'WorkstationV4Grouper'],
    ['/dashboard/medical-records/R-1', 'MedicalRecordDetail'],
    ['/dashboard/rules', 'Rules'],
    ['/dashboard/drg/coding', 'CodingAssistant'],
  ])('%s 保留现行页面 %s', (path, name) => {
    const matched = router.resolve(path).matched.at(-1)

    expect(matched?.name).toBe(name)
    expect(matched?.components?.default).toBeTypeOf('function')
    expect(matched?.redirect).toBeUndefined()
  })
})
