import { describe, expect, it, vi } from 'vitest'
import { canAccessPath } from '@/utils/routeAccess'

vi.unmock('vue-router')
window.scrollTo = vi.fn()

const { default: router } = await import('@/router')

const REPORTS = [
  ['record-quality', '病历质量分析'],
  ['special-records', '特殊病历报表'],
  ['frontpage-quality', '病案首页统计分析'],
  ['staff-analysis', '质控员工作分析'],
] as const

describe('V5 报表路由', () => {
  it.each(REPORTS)('%s 保持 V5 布局和原报表权限', (slug, title) => {
    const path = `/workstation-v5/reports/${slug}`
    const resolved = router.resolve(`${path}?scene=final#details`)
    expect(resolved.matched.map((record) => record.path)).toEqual(['/workstation-v5', path])
    expect(resolved.meta.requiresAuth).toBe(true)
    expect(resolved.meta.title).toBe(title)
    expect(resolved.query.scene).toBe('final')
    expect(resolved.hash).toBe('#details')
    expect(resolved.matched.some((record) => record.redirect)).toBe(false)
    for (const role of ['admin', 'qc_manager']) {
      expect(canAccessPath(router, path, [role])).toBe(true)
    }
    for (const role of ['doctor', 'reviewer', 'qc_staff', 'sync_admin', 'super_admin', 'coder']) {
      expect(canAccessPath(router, path, [role])).toBe(false)
    }
  })

  it.each(REPORTS)('%s 旧链接仍能解析，V5 入口独立注册', (slug) => {
    const legacy = router.resolve(`/dashboard/qc/reports/${slug}`)
    const current = router.resolve(`/workstation-v5/reports/${slug}`)
    expect(legacy.matched[legacy.matched.length - 1]?.components?.default).toBeTypeOf('function')
    expect(current.matched[current.matched.length - 1]?.components?.default).toBeTypeOf('function')
    expect(current.name).not.toBe(legacy.name)
  })
})
