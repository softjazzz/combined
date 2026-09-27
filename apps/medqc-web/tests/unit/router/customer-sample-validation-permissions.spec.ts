import { describe, expect, it, vi } from 'vitest'

// 本文件用例会真实导航并懒加载路由组件树（结果清单、审核面板等），全量并发下单条可超过 15 秒。
vi.setConfig({ testTimeout: 30_000 })

vi.unmock('vue-router')

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    userRoles: ['sync_admin'],
    initialize: vi.fn(),
  }),
}))

window.scrollTo = vi.fn()

const { default: router } = await import('@/router')

describe('客户样本验证路由权限', () => {
  it('同步管理员可以进入客户样本验证及其配套页面', async () => {
    const paths = [
      '/workstation-v5/customer-sample-validation',
      '/workstation-v5/customer-sample-validation/synthetic-case/new',
      '/workstation-v5/customer-sample-validation/tasks',
      '/workstation-v5/customer-sample-validation/surgery-catalog',
    ]

    for (const path of paths) {
      const route = router.getRoutes().find((item) => item.path === path)
      expect(route?.meta.permission).toContain('sync_admin')
    }

    await router.push(paths[0])
    expect(router.currentRoute.value.path).toBe(paths[0])
  }, 30_000)
})
