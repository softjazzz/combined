import { describe, expect, it, vi } from 'vitest'
import {
  canAccessPath,
  canAccessRoute,
  canAccessRouteMeta,
  getRoleDefaultLanding,
  NO_PERMISSION_PATH,
  resolveDeniedFallback,
  resolveFinalRoute,
  resolveLoginLanding,
  type ResolvedRouteLike,
  type RouteResolver,
} from '@/utils/routeAccess'

vi.unmock('vue-router')
window.scrollTo = vi.fn()

const { default: router } = await import('@/router')

describe('canAccessRouteMeta / canAccessRoute', () => {
  it('无 meta.permission 视为登录即可访问', () => {
    expect(canAccessRouteMeta(undefined, [])).toBe(true)
    expect(canAccessRouteMeta({}, ['doctor'])).toBe(true)
    expect(canAccessRoute({ meta: { title: '我的任务' } }, [])).toBe(true)
  })

  it('任一角色命中白名单即可访问', () => {
    const meta = { permission: ['admin', 'qc_manager'] }
    expect(canAccessRouteMeta(meta, ['qc_manager'])).toBe(true)
    expect(canAccessRouteMeta(meta, ['doctor', 'admin'])).toBe(true)
    expect(canAccessRouteMeta(meta, ['doctor'])).toBe(false)
    expect(canAccessRouteMeta(meta, [])).toBe(false)
  })

  it('空白名单与现有守卫一致：一律拒绝', () => {
    expect(canAccessRouteMeta({ permission: [] }, ['admin'])).toBe(false)
  })
})

describe('resolveFinalRoute / canAccessPath', () => {
  function fakeResolver(table: Record<string, Partial<ResolvedRouteLike>>): RouteResolver {
    return {
      resolve(to) {
        const path = typeof to === 'string' ? to : String((to as { path?: string }).path)
        const hit = table[path]
        return {
          name: hit?.name,
          path,
          fullPath: path,
          meta: hit?.meta ?? {},
          matched: hit?.matched ?? [],
        }
      },
    }
  }

  it('跟随 redirect 后按最终路由判断', () => {
    const resolver = fakeResolver({
      '/a': { name: 'A', matched: [{ redirect: '/b' }] },
      '/b': { name: 'B', meta: { permission: ['admin'] }, matched: [{}] },
    })
    expect(resolveFinalRoute(resolver, '/a')?.path).toBe('/b')
    expect(canAccessPath(resolver, '/a', ['admin'])).toBe(true)
    expect(canAccessPath(resolver, '/a', ['doctor'])).toBe(false)
  })

  it('未匹配或 NotFound 视为不可访问', () => {
    const resolver = fakeResolver({ '/x': { name: 'NotFound', matched: [{}] } })
    expect(canAccessPath(resolver, '/x', ['admin'])).toBe(false)
    expect(canAccessPath(resolver, '/none', ['admin'])).toBe(false)
  })

  it('真实路由表：/dashboard 首页跟随 redirect 到 V5 首页', () => {
    expect(resolveFinalRoute(router, '/dashboard')?.path).toBe('/workstation-v5')
    expect(canAccessPath(router, '/dashboard', ['doctor'])).toBe(true)
    expect(canAccessPath(router, '/dashboard', ['qc_staff'])).toBe(false)
  })

  it('真实路由表：子路由继承父路由 permission，子路由自身 permission 覆盖父级', () => {
    expect(canAccessPath(router, '/dashboard/drg/coding', ['coder'])).toBe(true)
    expect(canAccessPath(router, '/dashboard/drg/analysis', ['coder'])).toBe(false)
    expect(canAccessPath(router, '/dashboard/drg/analysis', ['qc_manager'])).toBe(true)
  })
})

describe('登录落地', () => {
  it('按角色默认落地', () => {
    expect(getRoleDefaultLanding(router, ['admin'])).toBe('/workstation-v5')
    expect(getRoleDefaultLanding(router, ['qc_manager'])).toBe('/workstation-v5')
    expect(getRoleDefaultLanding(router, ['qc_staff'])).toBe('/dashboard/tasks/my?tab=received')
    expect(getRoleDefaultLanding(router, ['doctor'])).toBe('/dashboard/qc/rectifications')
  })

  it('多角色按 admin > qc_manager > qc_staff > doctor 取落地', () => {
    expect(getRoleDefaultLanding(router, ['doctor', 'qc_staff'])).toBe(
      '/dashboard/tasks/my?tab=received',
    )
    expect(getRoleDefaultLanding(router, ['qc_staff', 'qc_manager'])).toBe('/workstation-v5')
  })

  it('其他角色取首个可访问页面', () => {
    expect(getRoleDefaultLanding(router, ['sync_admin'])).toBe('/workstation-v5')
    expect(getRoleDefaultLanding(router, ['coder'])).toBe('/dashboard/workstation')
    expect(getRoleDefaultLanding(router, [])).toBe('/dashboard/tasks/my')
  })

  it('redirect 可访问则直达 redirect', () => {
    expect(resolveLoginLanding(router, ['doctor'], '/dashboard/qc/appeals?id=1')).toEqual({
      target: '/dashboard/qc/appeals?id=1',
      redirectDenied: false,
    })
  })

  it('redirect 不可访问回到角色默认页并标记提示', () => {
    expect(resolveLoginLanding(router, ['doctor'], '/workstation-v5/records/final')).toEqual({
      target: '/dashboard/qc/rectifications',
      redirectDenied: true,
    })
    expect(resolveLoginLanding(router, ['qc_staff'], '/workstation-v5')).toEqual({
      target: '/dashboard/tasks/my?tab=received',
      redirectDenied: true,
    })
    expect(resolveLoginLanding(router, ['admin'], '/no/such/page')).toEqual({
      target: '/workstation-v5',
      redirectDenied: true,
    })
  })

  it('无 redirect、外跳地址或登录页本身直接按角色默认落地且不提示', () => {
    expect(resolveLoginLanding(router, ['qc_staff'], null).target).toBe(
      '/dashboard/tasks/my?tab=received',
    )
    expect(resolveLoginLanding(router, ['admin'], '//evil.example.com')).toEqual({
      target: '/workstation-v5',
      redirectDenied: false,
    })
    expect(resolveLoginLanding(router, ['admin'], '/auth/login')).toEqual({
      target: '/workstation-v5',
      redirectDenied: false,
    })
  })
})

describe('resolveDeniedFallback', () => {
  it('真实路由表：拒绝后去角色默认页，兜底页本身登录即可访问', () => {
    expect(resolveDeniedFallback(router, ['qc_staff'], '/workstation-v5')).toBe(
      '/dashboard/tasks/my?tab=received',
    )
    expect(resolveDeniedFallback(router, [], '/dashboard/settings')).toBe('/dashboard/tasks/my')
    expect(canAccessPath(router, NO_PERMISSION_PATH, [])).toBe(true)
  })

  it('默认页不可访问或等于被拒目标时落到无权访问页', () => {
    const denyAll: RouteResolver = {
      resolve(to) {
        const path = typeof to === 'string' ? to.split('?')[0] : '/'
        return { name: 'X', path, fullPath: path, meta: { permission: ['admin'] }, matched: [{}] }
      },
    }
    expect(resolveDeniedFallback(denyAll, ['qc_staff'], '/any')).toBe(NO_PERMISSION_PATH)

    const openAll: RouteResolver = {
      resolve(to) {
        const path = typeof to === 'string' ? to.split('?')[0] : '/'
        return { name: 'X', path, fullPath: path, meta: {}, matched: [{}] }
      },
    }
    expect(resolveDeniedFallback(openAll, ['qc_staff'], '/dashboard/tasks/my')).toBe(
      NO_PERMISSION_PATH,
    )
  })
})
