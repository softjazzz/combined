/**
 * 评分标准管理页的纯函数：档位连续性预校验、项目组/条目整表预校验与展示格式。
 * 前端校验只为及早提示，最终以后端 422 problems 为准（合同第 2、4 节）。
 */

import type {
  ScoringGradeBand,
  ScoringItem,
  ScoringScene,
  ScoringStandardStatus,
} from '@/api/scoring'

export const UNKNOWN_TEXT = '未知'
export const MAX_BANDS = 20

export const SCENE_LABELS: Record<ScoringScene, string> = {
  running: '运行病历',
  final: '终末病历',
  outpatient: '门急诊',
}

export const SCENE_ORDER: ScoringScene[] = ['running', 'final', 'outpatient']

export const STATUS_LABELS: Record<ScoringStandardStatus, string> = {
  draft: '草稿',
  active: '启用中',
  archived: '已归档',
}

/** 编辑中的档位：数值可暂为空。 */
export interface EditableBand {
  name: string
  min_score: number | null
  max_score: number | null
}

/** 编辑中的项目组：封顶为空表示不封顶。 */
export interface EditableGroup {
  key: string
  group_name: string
  max_deduction: number | null
  sort_order: number | null
}

export interface EditableItem {
  key: string
  rule_id: string
  group_name: string
  deduction: number | null
  is_veto: boolean
  enabled: boolean
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** 金额比较按分精度，避免浮点误差误报空隙。 */
function cents(value: number): number {
  return Math.round(value * 100)
}

export function defaultBands(baseScore = 100): EditableBand[] {
  return [
    { name: '甲', min_score: 90, max_score: baseScore },
    { name: '乙', min_score: 75, max_score: 90 },
    { name: '丙', min_score: 0, max_score: 75 },
  ]
}

/**
 * 档位连续性预校验：至少 1 档、名称唯一非空、min < max、降序、首尾相接，
 * 最高档上限等于满分、最低档下限为 0，否决档位必须是档位名称之一。
 */
export function validateBands(
  bands: readonly EditableBand[],
  baseScore: number | null,
  vetoGrade: string,
): string[] {
  const problems: string[] = []
  if (!isNumber(baseScore) || baseScore <= 0) problems.push('满分必须大于 0')
  if (bands.length === 0) problems.push('至少需要 1 个档位')
  if (bands.length > MAX_BANDS) problems.push(`档位不能超过 ${MAX_BANDS} 个`)
  const names = new Set<string>()
  let numeric = true
  bands.forEach((band, index) => {
    const label = `第 ${index + 1} 档`
    const name = band.name.trim()
    if (!name) problems.push(`${label}名称不能为空`)
    else if (names.has(name)) problems.push(`档位名称重复：${name}`)
    else names.add(name)
    if (!isNumber(band.min_score) || !isNumber(band.max_score)) {
      problems.push(`${label}（${name || '?'}）分数不能为空`)
      numeric = false
      return
    }
    if (band.min_score < 0 || band.max_score < 0) problems.push(`${label}（${name || '?'}）分数不能为负`)
    if (band.min_score >= band.max_score) {
      problems.push(`${label}（${name || '?'}）下限必须小于上限`)
      numeric = false
    }
  })
  if (numeric && bands.length > 0) {
    const typed = bands as Array<EditableBand & { min_score: number; max_score: number }>
    const descending = typed.every((band, index) => index === 0 || cents(band.max_score) <= cents(typed[index - 1].max_score))
    if (!descending) {
      problems.push('档位必须按分数从高到低排列')
    } else {
      for (let index = 1; index < typed.length; index += 1) {
        const previous = typed[index - 1]
        const current = typed[index]
        if (cents(current.max_score) < cents(previous.min_score)) {
          problems.push(`档位 ${current.name} 与 ${previous.name} 之间有空隙：[${current.max_score}, ${previous.min_score})`)
        } else if (cents(current.max_score) > cents(previous.min_score)) {
          problems.push(`档位 ${current.name} 与 ${previous.name} 重叠：[${previous.min_score}, ${current.max_score})`)
        }
      }
      if (isNumber(baseScore) && cents(typed[0].max_score) !== cents(baseScore)) {
        problems.push(`最高档上限必须等于满分 ${baseScore}（当前 ${typed[0].max_score}）`)
      }
      if (cents(typed[typed.length - 1].min_score) !== 0) {
        problems.push(`最低档下限必须为 0（当前 ${typed[typed.length - 1].min_score}）`)
      }
    }
  }
  const veto = vetoGrade.trim()
  if (!veto) problems.push('否决档位不能为空')
  else if (names.size > 0 && !names.has(veto)) problems.push(`否决档位（${veto}）必须是档位名称之一`)
  return problems
}

/**
 * 项目组与条目整表预校验：组名唯一非空、封顶/排序合法、条目规则唯一且属于规则全集、
 * 所属组存在、扣分非负。ruleUniverse 为空（规则清单未加载）时不校验规则归属。
 */
export function validateGroupsAndItems(
  groups: readonly EditableGroup[],
  items: readonly EditableItem[],
  ruleUniverse: ReadonlySet<string>,
): string[] {
  const problems: string[] = []
  const groupNames = new Set<string>()
  groups.forEach((group, index) => {
    const name = group.group_name.trim()
    if (!name) {
      problems.push(`第 ${index + 1} 个项目组名称不能为空`)
      return
    }
    if (groupNames.has(name)) problems.push(`项目组名称重复：${name}`)
    groupNames.add(name)
    if (group.max_deduction !== null && (!isNumber(group.max_deduction) || group.max_deduction < 0)) {
      problems.push(`项目组 ${name} 封顶扣分必须为非负数或留空`)
    }
    if (group.sort_order !== null && (!Number.isInteger(group.sort_order) || group.sort_order < 0)) {
      problems.push(`项目组 ${name} 排序必须为非负整数`)
    }
  })
  const ruleIds = new Set<string>()
  items.forEach((item, index) => {
    const ruleId = item.rule_id.trim().toUpperCase()
    const label = ruleId || `第 ${index + 1} 条`
    if (!ruleId) problems.push(`第 ${index + 1} 条条目未选择规则`)
    else if (ruleIds.has(ruleId)) problems.push(`规则重复（一条规则只能属于一个项目组）：${ruleId}`)
    else {
      ruleIds.add(ruleId)
      if (ruleUniverse.size > 0 && !ruleUniverse.has(ruleId)) problems.push(`规则 ${ruleId} 不属于该规则集当前版本`)
    }
    if (!item.group_name.trim() || !groupNames.has(item.group_name.trim())) {
      problems.push(`条目 ${label} 所属项目组不存在`)
    }
    if (!isNumber(item.deduction) || item.deduction < 0) problems.push(`条目 ${label} 扣分必须为非负数`)
  })
  return problems
}

/** 编辑态 → 写接口：排序为空时按当前顺序补齐。 */
export function toGroupWrites(groups: readonly EditableGroup[]) {
  return groups.map((group, index) => ({
    group_name: group.group_name.trim(),
    max_deduction: group.max_deduction,
    sort_order: group.sort_order ?? index + 1,
  }))
}

export function toItemWrites(items: readonly EditableItem[]): ScoringItem[] {
  return items.map((item) => ({
    group_name: item.group_name.trim(),
    rule_id: item.rule_id.trim().toUpperCase(),
    deduction: item.deduction as number,
    is_veto: item.is_veto,
    enabled: item.enabled,
  }))
}

export function toBandWrites(bands: readonly EditableBand[]): ScoringGradeBand[] {
  return bands.map((band) => ({
    name: band.name.trim(),
    min_score: band.min_score as number,
    max_score: band.max_score as number,
  }))
}

/** 档位摘要，例如“甲 ≥90 · 乙 75–90 · 丙 <75”。 */
export function bandsSummary(bands: readonly ScoringGradeBand[]): string {
  if (!bands.length) return UNKNOWN_TEXT
  return bands.map((band) => `${band.name} ${band.min_score}–${band.max_score}`).join(' · ')
}

export function formatScore(value: number | null | undefined): string {
  return isNumber(value) ? String(Number(value.toFixed(2))) : UNKNOWN_TEXT
}

/** 库内时间为无时区 UTC；无时区后缀时按 UTC 解析后以本地时间展示。 */
export function formatUtcTime(value: string | null | undefined): string {
  const text = String(value || '').trim()
  if (!text) return UNKNOWN_TEXT
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/iu.test(text)
  const date = new Date(hasZone ? text : `${text}Z`)
  if (Number.isNaN(date.getTime())) return UNKNOWN_TEXT
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
