/**
 * 工作台导航配置（UI 重设计 v1）
 * 只重排入口与分组，不改路由地址、页面功能与权限；旧 URL（?tab=、?stage=）继续有效。
 * 选中项、面包屑与可见性都由本模块的纯函数计算，布局组件只负责渲染。
 */
import type { MqIconName } from '@/components/icons/mqIcons'

export const WORKSTATION_BASE = '/workstation-v5'

export type WorklistStage = 'frontpage_generate' | 'frontpage_qc' | 'settlement_qc'

export interface NavLocation {
  path: string
  query?: Record<string, string>
}

export interface NavRouteLike {
  path: string
  query: Record<string, unknown>
  meta: Record<string, unknown>
}

export interface NavItem {
  key: string
  label: string
  to: NavLocation
  /** 定制图标名（见 components/icons/mqIcons.ts） */
  iconName: MqIconName
  /** 分组内的步骤序号（首页与结算清单 1→3），用于读屏与提示 */
  step?: number
  /** 反馈演示账号及具有读取权限的同步管理员可见 */
  demoFeedbackOnly?: boolean
  /** 当前路由是否属于该入口 */
  match: (route: NavRouteLike) => boolean
}

export interface NavGroup {
  key: string
  label?: string
  items: NavItem[]
}

export interface SectionTab {
  key: string
  label: string
  path: string
}

const p = (sub = '') => `${WORKSTATION_BASE}${sub}`

function stageOf(route: NavRouteLike): string {
  const raw = route.query.stage
  return typeof raw === 'string' ? raw.trim() : ''
}

/** 首页地址带 stage 等启动参数时实际渲染病历池，与 WorkstationV4HomeEntry 保持一致 */
function isWorklistPath(route: NavRouteLike): boolean {
  return route.path === p('/worklist') || route.path === p()
}

function matchStage(stage: WorklistStage) {
  return (route: NavRouteLike) => isWorklistPath(route) && stageOf(route) === stage
}

function matchPrefix(prefix: string, exclude: string[] = []) {
  return (route: NavRouteLike) =>
    (route.path === prefix || route.path.startsWith(`${prefix}/`)) &&
    !exclude.some((item) => route.path === item || route.path.startsWith(`${item}/`))
}

const HOME_LAUNCH_KEYS = ['record_id', 'action', 'from_stage', 'taskId', 'stage']

function hasHomeLaunchQuery(route: NavRouteLike): boolean {
  return HOME_LAUNCH_KEYS.some((key) => {
    const value = route.query[key]
    return typeof value === 'string' && value.trim() !== ''
  })
}

/** DRG/DIP 分析：一个导航入口，页内按路由切换 */
export const DRG_SECTION_TABS: SectionTab[] = [
  { key: 'pre', label: '事前分析', path: p('/drg/pre') },
  { key: 'mid', label: '事中监控', path: p('/drg/mid') },
  { key: 'payment', label: '付费监测', path: p('/drg/payment') },
  { key: 'post', label: '事后分析', path: p('/drg/post') },
  { key: 'grouper', label: '分组器', path: p('/grouper') },
]

/** 质控规则页内 Tab 名称，与 WorkstationRulesView 的 tabs 保持一致 */
const RULE_TAB_LABELS: Record<string, string> = {
  coding: '编码规则',
  frontpage: '首页规则',
  settlement: '结算规则',
  semantic: '语义规则',
}

export const WORKSTATION_NAV: NavGroup[] = [
  {
    key: 'home',
    items: [
      {
        key: 'home',
        label: '首页',
        to: { path: p() },
        iconName: 'overview',
        match: (route) =>
          (route.path === p() && !hasHomeLaunchQuery(route)) || route.path === p('/qc-overview'),
      },
    ],
  },
  {
    key: 'qc-work',
    label: '质控作业',
    items: [
      {
        key: 'worklist',
        label: '病历池',
        to: { path: p('/worklist') },
        iconName: 'pool',
        match: (route) =>
          (route.path === p('/worklist') && stageOf(route) === '') ||
          (route.path === p() && hasHomeLaunchQuery(route) && stageOf(route) === ''),
      },
      {
        key: 'records-running',
        label: '运行病历质控',
        to: { path: p('/records/running') },
        iconName: 'running',
        match: matchPrefix(p('/records/running')),
      },
      {
        key: 'records-final',
        label: '终末病历质控',
        to: { path: p('/records/final') },
        iconName: 'final',
        match: matchPrefix(p('/records/final')),
      },
      {
        key: 'customer-sample-validation',
        label: '客户样本验证',
        to: { path: p('/customer-sample-validation') },
        iconName: 'sample',
        match: matchPrefix(p('/customer-sample-validation'), [
          p('/customer-sample-validation/surgery-catalog'),
        ]),
      },
      {
        key: 'qc-feedback-demo',
        label: '质控反馈记录',
        to: { path: p('/qc-feedback-demo') },
        iconName: 'doc',
        demoFeedbackOnly: true,
        match: matchPrefix(p('/qc-feedback-demo')),
      },
      {
        key: 'feedback-worklist',
        label: '整改待办',
        to: { path: p('/feedback') },
        iconName: 'doc',
        match: matchPrefix(p('/feedback')),
      },
      {
        key: 'message-center',
        label: '消息中心',
        to: { path: p('/messages') },
        iconName: 'doc',
        match: matchPrefix(p('/messages')),
      },
    ],
  },
  {
    key: 'frontpage-settlement',
    label: '首页与结算清单',
    items: [
      {
        key: 'stage-frontpage-generate',
        iconName: 'fp_generate',
        label: '生成首页',
        step: 1,
        to: { path: p('/worklist'), query: { stage: 'frontpage_generate' } },
        match: matchStage('frontpage_generate'),
      },
      {
        key: 'stage-frontpage-qc',
        iconName: 'fp_qc',
        label: '首页质控',
        step: 2,
        to: { path: p('/worklist'), query: { stage: 'frontpage_qc' } },
        match: matchStage('frontpage_qc'),
      },
      {
        key: 'stage-settlement-qc',
        iconName: 'settlement',
        label: '结算清单质控',
        step: 3,
        to: { path: p('/worklist'), query: { stage: 'settlement_qc' } },
        match: matchStage('settlement_qc'),
      },
    ],
  },
  {
    key: 'rules',
    label: '规则',
    items: [
      {
        key: 'rules',
        label: '质控规则',
        to: { path: p('/rules') },
        iconName: 'rules',
        match: (route) => route.path === p('/rules'),
      },
      {
        key: 'custom-rules',
        label: '自定义质控点',
        to: { path: p('/rules/custom-workspace') },
        iconName: 'custom_rule',
        match: matchPrefix(p('/rules/custom-workspace')),
      },
      {
        key: 'surgery-catalog',
        label: '手术分级目录',
        to: { path: p('/customer-sample-validation/surgery-catalog') },
        iconName: 'surgery_catalog',
        match: matchPrefix(p('/customer-sample-validation/surgery-catalog')),
      },
      {
        key: 'rule-validation',
        label: '规则验收',
        to: { path: p('/rules/validation') },
        iconName: 'rule_validation',
        match: matchPrefix(p('/rules/validation')),
      },
    ],
  },
  {
    key: 'analysis',
    label: '分析',
    items: [
      {
        key: 'stats',
        label: '统计分析',
        to: { path: p('/stats') },
        iconName: 'stats',
        match: matchPrefix(p('/stats')),
      },
      {
        key: 'report-record-quality',
        label: '病历质量分析',
        to: { path: p('/reports/record-quality') },
        iconName: 'stats',
        match: matchPrefix(p('/reports/record-quality')),
      },
      {
        key: 'report-special-records',
        label: '特殊病历报表',
        to: { path: p('/reports/special-records') },
        iconName: 'doc',
        match: matchPrefix(p('/reports/special-records')),
      },
      {
        key: 'report-frontpage-quality',
        label: '病案首页统计',
        to: { path: p('/reports/frontpage-quality') },
        iconName: 'fp_qc',
        match: matchPrefix(p('/reports/frontpage-quality')),
      },
      {
        key: 'report-staff-analysis',
        label: '质控员工作分析',
        to: { path: p('/reports/staff-analysis') },
        iconName: 'stats',
        match: matchPrefix(p('/reports/staff-analysis')),
      },
      {
        key: 'drg',
        label: 'DRG/DIP 分析',
        to: { path: DRG_SECTION_TABS[0].path },
        iconName: 'drg',
        match: (route) => DRG_SECTION_TABS.some((tab) => route.path === tab.path),
      },
      {
        key: 'icd',
        label: 'ICD 编码查询',
        to: { path: p('/icd') },
        iconName: 'icd',
        match: matchPrefix(p('/icd')),
      },
    ],
  },
  {
    key: 'data-config',
    label: '数据与配置',
    items: [
      {
        key: 'upload',
        label: '数据上传',
        to: { path: p('/upload') },
        iconName: 'upload',
        match: matchPrefix(p('/upload')),
      },
      {
        key: 'data',
        label: '数据管理',
        to: { path: p('/data') },
        iconName: 'data',
        match: matchPrefix(p('/data')),
      },
      {
        key: 'system-config',
        label: '系统配置',
        to: { path: p('/system-config') },
        iconName: 'settings',
        match: matchPrefix(p('/system-config')),
      },
    ],
  },
]

export interface NavVisibilityContext {
  isDemoFeedbackAccount: boolean
  userRoles: string[]
  /** 返回入口目标路由声明的 meta.permission；未声明时返回 undefined */
  resolvePermission: (to: NavLocation) => string[] | undefined
}

/** 按现有路由权限与演示账号条件过滤入口；与路由守卫口径一致，不新增权限规则 */
export function filterVisibleNav(groups: NavGroup[], ctx: NavVisibilityContext): NavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (item.demoFeedbackOnly && !ctx.isDemoFeedbackAccount && !ctx.userRoles.includes('sync_admin')) return false
        const required = ctx.resolvePermission(item.to)
        if (!required || required.length === 0) return true
        return ctx.userRoles.includes('sync_admin') || required.some((role) => ctx.userRoles.includes(role))
      }),
    }))
    .filter((group) => group.items.length > 0)
}

export interface ActiveNav {
  group: NavGroup
  item: NavItem
}

export function findActiveNav(groups: NavGroup[], route: NavRouteLike): ActiveNav | null {
  for (const group of groups) {
    for (const item of group.items) {
      if (item.match(route)) return { group, item }
    }
  }
  return null
}

export function findDrgSectionTab(route: NavRouteLike): SectionTab | undefined {
  return DRG_SECTION_TABS.find((tab) => tab.path === route.path)
}

/**
 * 面包屑：分组 / 入口 / 页内位置（DRG 子页、规则 Tab、入口下的子页面）。
 * 找不到入口时退回路由自身的 meta.title，不再一律显示「工作台」。
 */
export function resolveBreadcrumb(groups: NavGroup[], route: NavRouteLike): string[] {
  const metaTitle = typeof route.meta.title === 'string' ? route.meta.title : ''
  const active = findActiveNav(groups, route)
  if (!active) return metaTitle ? [metaTitle] : ['首页']

  const crumbs: string[] = []
  if (active.group.label) crumbs.push(active.group.label)
  crumbs.push(active.item.label)

  if (active.item.key === 'drg') {
    const tab = findDrgSectionTab(route)
    if (tab) crumbs.push(tab.label)
  } else if (active.item.key === 'rules') {
    const tab = typeof route.query.tab === 'string' ? route.query.tab : ''
    crumbs.push(RULE_TAB_LABELS[tab] || RULE_TAB_LABELS.coding)
  } else if (active.item.to.path !== route.path && metaTitle && metaTitle !== active.item.label) {
    crumbs.push(metaTitle)
  }
  return crumbs
}
