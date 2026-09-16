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

const { default: router } = await import('@/router')

function loadRouteComponent(component: unknown): Promise<{ default: unknown }> {
  if (typeof component !== 'function') {
    throw new Error('运行和终末质控必须加载共享结果清单视图')
  }

  return component() as Promise<{ default: unknown }>
}

describe('运行与终末质控结果清单路由', () => {
  it('两个路径都使用共享结果清单视图，并传入不同的病历阶段', async () => {
    const running = router
      .getRoutes()
      .find((route) => route.path === '/workstation-v5/records/running')
    const final = router.getRoutes().find((route) => route.path === '/workstation-v5/records/final')
    const runningLoader = running?.components?.default
    const finalLoader = final?.components?.default

    expect(runningLoader).toBeTypeOf('function')
    expect(finalLoader).toBeTypeOf('function')
    expect(running?.props?.default).toEqual({ carePhase: 'inpatient' })
    expect(final?.props?.default).toEqual({ carePhase: 'discharged' })

    const [runningModule, finalModule] = await Promise.all([
      loadRouteComponent(runningLoader),
      loadRouteComponent(finalLoader),
    ])
    expect(runningModule.default).toBe(finalModule.default)
  }, 15_000)
})
