import { describe, expect, it, vi } from 'vitest'
import router from '@/router'
import { canAccessRouteMeta } from '@/utils/routeAccess'

// 全量并发下首次动态加载整套路由与视图模块可能超过默认 5s，与其他路由 spec 保持一致
vi.setConfig({ testTimeout: 30_000 })

describe('文书管理路由', () => {
  it('V5 正式入口可解析且只允许管理员与质控管理员', async () => {
    const resolved = router.resolve('/workstation-v5/document-definitions')
    const route = resolved.matched.at(-1)
    expect(route?.name).toBe('WorkstationV4DocumentDefinitions')
    expect(route?.meta.title).toBe('文书管理')
    expect(route?.meta.permission).toEqual(['admin', 'qc_manager'])
    expect(canAccessRouteMeta(route?.meta || {}, ['admin'])).toBe(true)
    expect(canAccessRouteMeta(route?.meta || {}, ['qc_manager'])).toBe(true)
    expect(canAccessRouteMeta(route?.meta || {}, ['doctor'])).toBe(false)

    const loader = route?.components?.default
    expect(typeof loader).toBe('function')
    const module = await (loader as () => Promise<{ default: unknown }>)()
    expect(module.default).toBeTruthy()
  })
})
