import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.unmock('vue-router')

const authState = vi.hoisted(() => ({
  isAuthenticated: true,
  userRoles: ['admin'] as string[],
  // 守卫每次导航都会读取角色，用读取次数近似导航次数，检测循环重定向
  roleReads: 0,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isAuthenticated() {
      return authState.isAuthenticated
    },
    get userRoles() {
      authState.roleReads += 1
      if (authState.roleReads > 50) throw new Error('疑似循环重定向')
      return authState.userRoles
    },
    initialize: vi.fn(),
  }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('@/router')

// 在业务守卫之后追加一个记录守卫：记下最终放行的目标后中止导航，避免加载页面组件。
let reached: string | null = null
router.beforeEach((to) => {
  reached = to.fullPath
  return false
})

async function visit(path: string) {
  reached = null
  authState.roleReads = 0
  await router.push(path).catch(() => undefined)
  return reached
}

describe('路由守卫权限判断（锁定现有行为）', () => {
  beforeEach(() => {
    authState.isAuthenticated = true
    authState.userRoles = ['admin']
  })

  it.each(['record-quality', 'special-records', 'frontpage-quality', 'staff-analysis'])(
    'V5 报表 %s 保留场景，未登录时使用工作台登录页',
    async (slug) => {
      const target = `/workstation-v5/reports/${slug}?scene=final`
      authState.userRoles = ['qc_manager']
      expect(await visit(target)).toBe(target)
      authState.isAuthenticated = false
      const login = router.resolve((await visit(target))!)
      expect(login.path).toBe('/workstation-v5/login')
      expect(login.query.redirect).toBe(target)
    },
  )

  it('未登录访问 dashboard 页面跳转到通用登录页并带 redirect', async () => {
    authState.isAuthenticated = false
    expect(await visit('/dashboard/tasks/all')).toBe('/auth/login?redirect=/dashboard/tasks/all')
  })

  it('未登录访问工作台页面跳转到工作台登录页', async () => {
    authState.isAuthenticated = false
    expect(await visit('/workstation-v5/worklist')).toBe(
      '/workstation-v5/login?redirect=/workstation-v5/worklist',
    )
  })

  it('角色命中 meta.permission 时放行', async () => {
    authState.userRoles = ['doctor']
    expect(await visit('/dashboard/qc/appeals')).toBe('/dashboard/qc/appeals')
  })

  it('无 meta.permission 的页面登录即可访问', async () => {
    authState.userRoles = ['qc_staff']
    expect(await visit('/dashboard/tasks/my?tab=received')).toBe('/dashboard/tasks/my?tab=received')
  })

  it('子路由继承父路由的 meta.permission', async () => {
    authState.userRoles = ['reviewer']
    expect(await visit('/dashboard/drg/coding')).toBe('/dashboard/drg/coding')
  })

  it('DRG 与后端口径一致：coder 被拒回默认页，doctor 放行', async () => {
    authState.userRoles = ['coder']
    expect(await visit('/dashboard/drg/coding')).toBe('/dashboard/workstation')
    authState.userRoles = ['doctor']
    expect(await visit('/dashboard/drg/coding')).toBe('/dashboard/drg/coding')
  })

  it('角色未命中时转到角色默认页', async () => {
    authState.userRoles = ['doctor']
    expect(await visit('/dashboard/tasks/all')).toBe('/dashboard/qc/rectifications')
  })

  // 回归：原先拒绝后固定跳 /dashboard → /workstation-v5，无 V5 权限的角色会无限重定向
  it.each([
    [[], '/dashboard/settings', '/dashboard/tasks/my'],
    [['coder'], '/dashboard/settings', '/dashboard/workstation'],
    [['qc_staff'], '/dashboard/tasks/all', '/dashboard/tasks/my?tab=received'],
    [['qc_staff'], '/workstation-v5', '/dashboard/tasks/my?tab=received'],
  ])('角色 %j 访问受限页 %s 不循环，停在 %s', async (roles, path, expected) => {
    authState.userRoles = roles as string[]
    expect(await visit(path)).toBe(expected)
    expect(authState.roleReads).toBeLessThanOrEqual(4)
  })

  it('已登录访问工作台登录页：redirect 可访问则直达', async () => {
    authState.userRoles = ['admin']
    expect(await visit('/workstation-v5/login?redirect=/workstation-v5/records/final')).toBe(
      '/workstation-v5/records/final',
    )
  })

  it('已登录访问工作台登录页：无 V5 权限的质控员按角色默认落地，不再被送回工作台', async () => {
    authState.userRoles = ['qc_staff']
    expect(await visit('/workstation-v5/login')).toBe('/dashboard/tasks/my?tab=received')
  })
})
