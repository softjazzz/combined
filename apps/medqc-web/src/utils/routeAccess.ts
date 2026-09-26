/**
 * 路由访问判断（纯函数）
 *
 * 唯一权限来源：路由记录的 meta.permission（角色白名单）。
 * - 无 meta.permission：登录即可访问；
 * - 有 meta.permission：用户任一角色命中即可访问。
 * 路由守卫、两套布局菜单和登录落地共用本文件，避免各处手写角色判断。
 */
import type { RouteLocationRaw } from 'vue-router'

export type UserRoleList = readonly string[]

export interface RouteAccessMeta {
  permission?: unknown
  [key: string]: unknown
}

/** 最小可解析路由结构：兼容 vue-router 的 RouteLocationNormalized / resolve() 结果 */
export interface ResolvedRouteLike {
  name?: unknown
  path: string
  fullPath: string
  meta: RouteAccessMeta
  matched: ReadonlyArray<{ redirect?: unknown }>
}

/** 只需要 router.resolve 能力，便于测试注入 */
export interface RouteResolver {
  resolve(to: RouteLocationRaw): ResolvedRouteLike
}

/** 判断 meta（已由 vue-router 合并父子路由）是否允许当前角色访问 */
export function canAccessRouteMeta(
  meta: RouteAccessMeta | null | undefined,
  roles: UserRoleList,
): boolean {
  const permission = meta?.permission
  if (!permission) return true
  if (Array.isArray(permission)) {
    return permission.some((item) => roles.includes(String(item)))
  }
  return roles.includes(String(permission))
}

/** 判断路由记录/路由位置是否允许当前角色访问 */
export function canAccessRoute(
  route: { meta?: RouteAccessMeta | null } | null | undefined,
  roles: UserRoleList,
): boolean {
  return canAccessRouteMeta(route?.meta, roles)
}

const MAX_REDIRECT_HOPS = 5

/**
 * 解析目标并跟随路由记录上的 redirect（与 vue-router 一致，只看最后一个匹配记录），
 * 得到真正会渲染的路由位置。无法匹配或落入 NotFound 时返回 null。
 */
export function resolveFinalRoute(
  resolver: RouteResolver,
  target: RouteLocationRaw,
): ResolvedRouteLike | null {
  let resolved: ResolvedRouteLike
  try {
    resolved = resolver.resolve(target)
  } catch {
    return null
  }

  for (let hop = 0; hop < MAX_REDIRECT_HOPS; hop += 1) {
    const lastMatched = resolved.matched[resolved.matched.length - 1]
    const redirect = lastMatched?.redirect
    if (!redirect) break
    const next = typeof redirect === 'function' ? redirect(resolved) : redirect
    try {
      resolved = resolver.resolve(next as RouteLocationRaw)
    } catch {
      return null
    }
  }

  if (resolved.matched.length === 0 || resolved.name === 'NotFound') return null
  return resolved
}

/** 目标地址（含 redirect 跟随）是否对当前角色可访问 */
export function canAccessPath(
  resolver: RouteResolver,
  target: RouteLocationRaw,
  roles: UserRoleList,
): boolean {
  const resolved = resolveFinalRoute(resolver, target)
  return resolved ? canAccessRouteMeta(resolved.meta, roles) : false
}

// ---------------------------------------------------------------------------
// 登录落地
// ---------------------------------------------------------------------------

/** 管理类角色默认落地：沿用项目现有默认首页（/ 与 /dashboard 均重定向到 V5 工作台首页） */
export const MANAGER_DEFAULT_LANDING = '/workstation-v5'
/** 质控员默认落地：我的任务-我收到 */
export const QC_STAFF_DEFAULT_LANDING = '/dashboard/tasks/my?tab=received'
/** 临床医生候选落地：优先整改、申诉，再退回工作台 */
export const DOCTOR_LANDING_CANDIDATES = [
  '/dashboard/qc/rectifications',
  '/dashboard/qc/appeals',
  '/workstation-v5',
] as const
/** 其他角色兜底候选：取首个可访问页面；我的任务无 permission，登录即可访问 */
export const FALLBACK_LANDING_CANDIDATES = [
  '/workstation-v5',
  '/dashboard/workstation',
  '/dashboard/tasks/my',
] as const

const LOGIN_ROUTE_NAMES = new Set(['Login', 'WorkstationV4Login'])

function firstAccessible(
  resolver: RouteResolver,
  candidates: readonly string[],
  roles: UserRoleList,
): string | null {
  return candidates.find((candidate) => canAccessPath(resolver, candidate, roles)) ?? null
}

/** 按角色计算默认落地页（多角色时按 admin > qc_manager > qc_staff > doctor 优先） */
export function getRoleDefaultLanding(resolver: RouteResolver, roles: UserRoleList): string {
  const plans: Array<[string, readonly string[]]> = [
    ['admin', [MANAGER_DEFAULT_LANDING]],
    ['qc_manager', [MANAGER_DEFAULT_LANDING]],
    ['qc_staff', [QC_STAFF_DEFAULT_LANDING]],
    ['doctor', DOCTOR_LANDING_CANDIDATES],
  ]
  for (const [role, candidates] of plans) {
    if (!roles.includes(role)) continue
    const target = firstAccessible(resolver, candidates, roles)
    if (target) return target
  }
  return (
    firstAccessible(resolver, FALLBACK_LANDING_CANDIDATES, roles) ??
    FALLBACK_LANDING_CANDIDATES[FALLBACK_LANDING_CANDIDATES.length - 1]
  )
}

export interface LoginLanding {
  /** 最终跳转地址 */
  target: string
  /** redirect 存在但当前角色无权访问（调用方据此提示“无权访问该页面”） */
  redirectDenied: boolean
}

/** 仅接受站内绝对路径，拒绝协议相对地址等外跳 */
function isSafeInternalPath(value: string): boolean {
  return value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\')
}

/**
 * 计算登录后的落地页：
 * - redirect 为站内路径且当前角色可访问 → 去 redirect；
 * - redirect 不可访问 → 回角色默认页并标记 redirectDenied；
 * - 无 redirect（或指向登录页本身） → 角色默认页。
 */
export function resolveLoginLanding(
  resolver: RouteResolver,
  roles: UserRoleList,
  redirect?: string | null,
): LoginLanding {
  const fallback = getRoleDefaultLanding(resolver, roles)
  if (typeof redirect !== 'string' || !redirect.trim() || !isSafeInternalPath(redirect)) {
    return { target: fallback, redirectDenied: false }
  }

  const resolved = resolveFinalRoute(resolver, redirect)
  if (resolved && LOGIN_ROUTE_NAMES.has(String(resolved.name ?? ''))) {
    return { target: fallback, redirectDenied: false }
  }
  if (!resolved || !canAccessRouteMeta(resolved.meta, roles)) {
    return { target: fallback, redirectDenied: true }
  }
  return { target: redirect, redirectDenied: false }
}

/** 无权访问兜底页（路由不设 meta.permission，所有登录用户可访问） */
export const NO_PERMISSION_PATH = '/no-permission'

/**
 * 守卫拒绝访问后的去向：角色默认页；若默认页不可访问，或其最终路径就是当前被拒目标，
 * 则落到无权访问页，保证不会在受限页之间循环重定向。
 */
export function resolveDeniedFallback(
  resolver: RouteResolver,
  roles: UserRoleList,
  deniedPath: string,
): string {
  const landing = getRoleDefaultLanding(resolver, roles)
  const resolved = resolveFinalRoute(resolver, landing)
  if (!resolved || !canAccessRouteMeta(resolved.meta, roles) || resolved.path === deniedPath) {
    return NO_PERMISSION_PATH
  }
  return landing
}

/** 登录落地提示文案 */
export const ROUTE_ACCESS_DENIED_MESSAGE = '无权访问该页面'
