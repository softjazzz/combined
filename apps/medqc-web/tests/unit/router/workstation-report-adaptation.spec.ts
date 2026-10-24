import { describe, expect, it, vi } from 'vitest'
import {
  WORKSTATION_NAV,
  DRG_SECTION_TABS,
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
const B = '/workstation-v5'
const reports = [
  ['record-quality', '病历质量分析'],
  ['special-records', '特殊病历报表'],
  ['frontpage-quality', '病案首页统计'],
  ['staff-analysis', '质控员工作分析'],
] as const

function loadPage(loader: unknown): Promise<{ default: unknown }> {
  if (typeof loader !== 'function') throw new Error('报表必须懒加载实际页面')
  return loader() as Promise<{ default: unknown }>
}

describe('业务线四报表定向适配', () => {
  it('整改待办保留V5外壳，医生和质控可访问，同步管理员不可访问', () => {
    const path = `${B}/feedback`
    const resolved = router.resolve(path)
    expect(resolved.matched[0].path).toBe(B)
    expect(resolved.meta.requiresAuth).toBe(true)
    expect(resolved.meta.permission).toEqual(['admin', 'qc_manager', 'qc_staff', 'doctor'])
    expect(resolved.redirectedFrom).toBeUndefined()
    expect(findActiveNav(WORKSTATION_NAV, { path, query: {}, meta: {} })?.item.key).toBe(
      'feedback-worklist',
    )
    for (const role of ['doctor', 'qc_manager', 'sync_admin']) {
      const nav = filterVisibleNav(WORKSTATION_NAV, {
        isDemoFeedbackAccount: false,
        userRoles: [role],
        resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
      })
      expect(
        nav.flatMap((group) => group.items).some((item) => item.key === 'feedback-worklist'),
      ).toBe(role !== 'sync_admin')
    }
  })
  it.each(reports)(
    '%s 直接加载页面、保留V5外壳与角色权限',
    async (slug, title) => {
      const path = `${B}/reports/${slug}`
      const resolved = router.resolve(path)
      expect(resolved.matched[0].path).toBe(B)
      expect(resolved.meta.requiresAuth).toBe(true)
      expect(resolved.meta.permission).toEqual(['admin', 'qc_manager'])
      expect(resolved.redirectedFrom).toBeUndefined()
      const entry = router.getRoutes().find((r) => r.path === path)!
      expect(entry.redirect).toBeUndefined()
      const loader = entry.components?.default
      expect(loader).toBeTypeOf('function')
      const page = await loadPage(loader)
      expect(page).toHaveProperty('default')
      const route = { path, query: {}, meta: { title } }
      expect(findActiveNav(WORKSTATION_NAV, route)?.item.key).toBe(`report-${slug}`)
      expect(resolveBreadcrumb(WORKSTATION_NAV, route)).toEqual(['分析', title])
    },
    30_000,
  )

  it.each(['doctor', 'sync_admin'])('%s 不新增四报表可见权限', (role) => {
    const nav = filterVisibleNav(WORKSTATION_NAV, {
      isDemoFeedbackAccount: false,
      userRoles: [role],
      resolvePermission: (to) => router.resolve(to).meta.permission as string[] | undefined,
    })
    expect(nav.flatMap((g) => g.items).filter((i) => i.key.startsWith('report-'))).toEqual([])
  })

  it('保留19个旧入口、手术目录、规则验收及全部DRG页内地址', () => {
    const originalKeys = [
      'home',
      'worklist',
      'records-running',
      'records-final',
      'customer-sample-validation',
      'qc-feedback-demo',
      'stage-frontpage-generate',
      'stage-frontpage-qc',
      'stage-settlement-qc',
      'rules',
      'custom-rules',
      'surgery-catalog',
      'rule-validation',
      'stats',
      'drg',
      'icd',
      'upload',
      'data',
      'system-config',
    ]
    const items = WORKSTATION_NAV.flatMap((g) => g.items)
    expect(
      items
        .filter((i) => !i.key.startsWith('report-') && i.key !== 'feedback-worklist')
        .map((i) => i.key),
    ).toEqual(originalKeys)
    expect(DRG_SECTION_TABS.map((tab) => tab.path)).toEqual(
      ['drg/pre', 'drg/mid', 'drg/payment', 'drg/post', 'grouper'].map((p) => `${B}/${p}`),
    )
    expect(router.resolve(`${B}/customer-sample-validation/tasks`).name).toBe(
      'WorkstationV4CustomerSampleValidationTasks',
    )
  })
})
