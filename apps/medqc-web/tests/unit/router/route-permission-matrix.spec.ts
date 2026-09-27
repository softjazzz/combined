import { describe, expect, it, vi } from 'vitest'
import { canAccessPath } from '@/utils/routeAccess'

vi.unmock('vue-router')
window.scrollTo = vi.fn()

const { default: router } = await import('@/router')

const ALL_ROLES = [
  'admin',
  'qc_manager',
  'qc_staff',
  'doctor',
  'reviewer',
  'coder',
  'sync_admin',
  'super_admin',
] as const

function visibleRoles(path: string) {
  return ALL_ROLES.filter((role) => canAccessPath(router, path, [role]))
}

const DRG = ['admin', 'qc_manager', 'doctor', 'reviewer']
const QC_DEPT = ['admin', 'qc_manager']
const LOGGED_IN = [...ALL_ROLES]

/**
 * 页面 → 应可见角色对照表（以后端接口权限为准，前端只能等于或更窄）。
 * 每行注明页面核心接口的后端依赖；后端口径变化时同步更新本表与 src/router/routeRoles.ts。
 */
const MATRIX: Array<[path: string, roles: readonly string[], backend: string]> = [
  // DRG：drg.py / settlement.py 路由级 require_roles(admin, qc_manager, doctor, reviewer)
  ['/dashboard/drg/index', DRG, 'drg.py require_roles'],
  ['/dashboard/drg/coding', DRG, 'drg.py require_roles'],
  ['/dashboard/drg/config', DRG, 'drg_config（挂在 drg.py 下）'],
  ['/dashboard/drg/analysis', QC_DEPT, 'drg/analysis ⊂ DRG，沿用旧版更窄口径'],
  ['/workstation-v5/drg/pre', DRG, 'pre-grouping 仅登录；按 DRG 模块收口'],
  ['/workstation-v5/drg/mid', DRG, 'panel 仅登录；按 DRG 模块收口'],
  ['/workstation-v5/drg/payment', DRG, 'payment-monitoring 仅登录；按 DRG 模块收口'],
  ['/workstation-v5/drg/post', QC_DEPT, 'drg/analysis ⊂ DRG，与旧版事后分析一致'],
  ['/workstation-v5/grouper', DRG, '纯前端分组器；按 DRG 模块收口'],
  ['/workstation-v5/upload', DRG, 'drg/batches ⊂ DRG'],
  // 规则管理：custom_qc.py require_roles(admin, qc_manager)
  ['/workstation-v5/rules', QC_DEPT, 'custom_qc.py require_roles'],
  ['/workstation-v5/rules/custom-workspace', QC_DEPT, 'custom_qc.py require_roles'],
  ['/dashboard/rules', QC_DEPT, 'custom_qc / department_qc_rules 写接口'],
  // 全院质控统计：analytics/luxian-0609 与 qc-home 后端仅校验登录（待定是否收紧）
  ['/workstation-v5/stats', QC_DEPT, 'analytics/luxian-0609 仅登录；前端按质控科收口'],
  ['/workstation-v5/qc-overview', QC_DEPT, 'qc-home 仅登录；前端按质控科收口'],
  ['/workstation-v5/records/final', QC_DEPT, 'qc-result-analysis 仅登录；前端按质控科收口'],
  // 系统配置：sync 读（admin/qc_manager/sync_admin/super_admin）；写与 LLM 页签页内按角色禁用/隐藏
  [
    '/workstation-v5/system-config',
    ['admin', 'qc_manager', 'sync_admin', 'super_admin'],
    'sync.py require_sync_read_access',
  ],
  // 旧版系统设置：qc_settings / LLM 配置需 admin/sync_admin/super_admin，前端仅 admin
  ['/dashboard/settings', ['admin'], 'qc_settings.py / llm_configs.py'],
  // 客户样本验证：qc_sample_pools.py require_roles(admin, qc_manager, sync_admin)
  [
    '/workstation-v5/customer-sample-validation',
    ['admin', 'qc_manager', 'sync_admin'],
    'qc_sample_pools.py require_roles',
  ],
  // 登录即可：后端仅校验登录的通用工具
  ['/workstation-v5/icd', LOGGED_IN, 'icd_search.py 仅登录'],
  ['/dashboard/tasks/my', LOGGED_IN, '我的任务按当前用户过滤'],
]

describe('路由权限与后端口径对照表', () => {
  it.each(MATRIX)('%s 可见角色', (path, roles) => {
    expect(visibleRoles(path)).toEqual(ALL_ROLES.filter((role) => roles.includes(role)))
  })

  it('coder 不在后端 DRG 角色内，任何 DRG 页面均不可见', () => {
    const drgPaths = MATRIX.map(([path]) => path).filter(
      (path) => path.includes('/drg') || path === '/workstation-v5/grouper',
    )
    expect(drgPaths.length).toBeGreaterThan(0)
    for (const path of drgPaths) {
      expect(canAccessPath(router, path, ['coder'])).toBe(false)
    }
  })
})
