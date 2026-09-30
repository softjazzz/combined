import { describe, expect, it } from 'vitest'
import {
  WORKSTATION_NAV,
  filterVisibleNav,
  findActiveNav,
  resolveBreadcrumb,
  type NavRouteLike,
} from '../workstationNav'

function route(path: string, query: Record<string, string> = {}, title = ''): NavRouteLike {
  return { path, query, meta: title ? { title } : {} }
}

const B = '/workstation-v5'

describe('workstationNav 选中项', () => {
  it.each([
    [route(B), 'home'],
    [route(`${B}/qc-overview`), 'home'],
    [route(`${B}/worklist`), 'worklist'],
    [route(B, { record_id: 'r1' }), 'worklist'],
    [route(`${B}/worklist`, { stage: 'frontpage_generate' }), 'stage-frontpage-generate'],
    [route(B, { stage: 'frontpage_qc' }), 'stage-frontpage-qc'],
    [route(`${B}/worklist`, { stage: 'settlement_qc' }), 'stage-settlement-qc'],
    [route(`${B}/rules`, { tab: 'semantic', ruleSetKey: 'luxian_0609_qc_v1' }), 'rules'],
    [route(`${B}/rules/custom-workspace`), 'custom-rules'],
    [route(`${B}/rules/validation`), 'rule-validation'],
    [route(`${B}/rules/validation/LX0609-06-01-01`), 'rule-validation'],
    [route(`${B}/customer-sample-validation/tasks`), 'customer-sample-validation'],
    [route(`${B}/customer-sample-validation/surgery-catalog`), 'surgery-catalog'],
    [route(`${B}/drg/payment`), 'drg'],
    [route(`${B}/grouper`), 'drg'],
    [route(`${B}/data`), 'data'],
  ])('%o → %s', (r, key) => {
    expect(findActiveNav(WORKSTATION_NAV, r)?.item.key).toBe(key)
  })

  it('导航外页面不误选任何入口', () => {
    expect(findActiveNav(WORKSTATION_NAV, route(`${B}/tender-acceptance`))).toBeNull()
  })
})

describe('workstationNav 面包屑', () => {
  it('首页只显示首页', () => {
    expect(resolveBreadcrumb(WORKSTATION_NAV, route(B, {}, '工作台'))).toEqual(['首页'])
  })

  it('阶段页显示阶段名而不是病历池', () => {
    expect(
      resolveBreadcrumb(
        WORKSTATION_NAV,
        route(`${B}/worklist`, { stage: 'frontpage_generate' }, '病历池'),
      ),
    ).toEqual(['首页与结算清单', '生成首页'])
  })

  it('规则页带出当前 Tab，缺省为编码规则', () => {
    expect(resolveBreadcrumb(WORKSTATION_NAV, route(`${B}/rules`, { tab: 'semantic' }))).toEqual([
      '规则',
      '质控规则',
      '语义规则',
    ])
    expect(resolveBreadcrumb(WORKSTATION_NAV, route(`${B}/rules`))).toEqual([
      '规则',
      '质控规则',
      '编码规则',
    ])
  })

  it('DRG 子页带出子页名', () => {
    expect(resolveBreadcrumb(WORKSTATION_NAV, route(`${B}/grouper`, {}, '医保分组器'))).toEqual([
      '分析',
      'DRG/DIP 分析',
      '分组器',
    ])
  })

  it('入口下的子页面追加自身标题', () => {
    expect(
      resolveBreadcrumb(
        WORKSTATION_NAV,
        route(`${B}/customer-sample-validation/tasks`, {}, '质控记录'),
      ),
    ).toEqual(['质控作业', '客户样本验证', '质控记录'])
  })

  it('导航外页面退回路由标题', () => {
    expect(
      resolveBreadcrumb(WORKSTATION_NAV, route(`${B}/tender-acceptance`, {}, '投标验收看板')),
    ).toEqual(['投标验收看板'])
  })
})

describe('workstationNav 可见性', () => {
  const permissions: Record<string, string[]> = {
    [`${B}/records/running`]: ['admin', 'qc_manager'],
    [`${B}/customer-sample-validation/surgery-catalog`]: ['admin', 'qc_manager', 'sync_admin'],
    [`${B}/rules/validation`]: ['admin', 'qc_manager'],
  }
  const resolvePermission = (to: { path: string }) => permissions[to.path]

  const keys = (groups: ReturnType<typeof filterVisibleNav>) =>
    groups.flatMap((group) => group.items.map((item) => item.key))

  it('按路由 meta.permission 隐藏无权限入口', () => {
    const visible = keys(
      filterVisibleNav(WORKSTATION_NAV, {
        isDemoFeedbackAccount: false,
        userRoles: ['doctor'],
        resolvePermission,
      }),
    )
    expect(visible).not.toContain('records-running')
    expect(visible).not.toContain('surgery-catalog')
    expect(visible).not.toContain('rule-validation')
    expect(visible).toContain('worklist')
  })

  it('质控反馈记录只对演示反馈账号可见', () => {
    const base = { userRoles: ['admin'], resolvePermission }
    expect(keys(filterVisibleNav(WORKSTATION_NAV, { ...base, isDemoFeedbackAccount: false }))).not.toContain(
      'qc-feedback-demo',
    )
    expect(keys(filterVisibleNav(WORKSTATION_NAV, { ...base, isDemoFeedbackAccount: true }))).toContain(
      'qc-feedback-demo',
    )
  })

  it('原有入口一个不少（演示账号 + 管理员）', () => {
    const visible = keys(
      filterVisibleNav(WORKSTATION_NAV, {
        isDemoFeedbackAccount: true,
        userRoles: ['admin'],
        resolvePermission,
      }),
    )
    // 18 个原有入口 + 规则验收
    expect(visible).toHaveLength(19)
    expect(visible).toContain('rule-validation')
  })
})
