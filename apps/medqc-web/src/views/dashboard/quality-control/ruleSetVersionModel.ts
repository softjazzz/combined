/**
 * 质控点管理页的纯数据整理：版本条目与草稿合并、草稿修改、差异清单、错误文案。
 * 规则状态、是否可执行、质控点名称与来源文书只搬运后端 entries 上的字段，不在前端重新判定或猜测。
 */

import type {
  RuleSetEntry,
  RuleSetEntryState,
  RuleSetEntryView,
  RuleSetVersionApiResult,
  RuleSetVersionSource,
} from '@/api/ruleSetVersions'

export const LX0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
export const LX0916_RULE_SET_KEY = 'luxian_0916_qc_v1'
export const CODING_QC_RULE_SET_KEY = 'coding_qc_v1'

export const RULE_SET_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: LX0609_RULE_SET_KEY, label: '泸县 0609 质控点' },
  { value: LX0916_RULE_SET_KEY, label: '泸县 0916 质控点' },
]

export const UNKNOWN_TEXT = '未知'

export const ENTRY_STATE_LABEL: Record<RuleSetEntryState, string> = {
  active: '已开启',
  paused: '已暂停',
  offline: '已下线',
  deleted: '已删除',
}

export const ENTRY_STATE_COLOR: Record<RuleSetEntryState, string> = {
  active: 'green',
  paused: 'orange',
  offline: 'default',
  deleted: 'red',
}

export const VERSION_SOURCE_LABEL: Record<RuleSetVersionSource, string> = {
  builtin: '内置',
  published: '已发布',
  retired: '已下线',
}

export type PointTab = 'online' | 'offline'

export interface QualityPointRow {
  rule_id: string
  /** 质控点名称（规则主表 qc_point）；无权威元数据时为 null。 */
  name: string | null
  /** 来源文书（规则主表 source_document）；无权威元数据时为 null。 */
  document: string | null
  /** 编码规则目录给出的权威分类名称。 */
  category: string | null
  /** 当前生效版本中的状态。 */
  state: RuleSetEntryState
  /** 草稿中的状态；与当前状态相同或无草稿时为 null。 */
  draftState: RuleSetEntryState | null
  /** 后端给出的可执行标记；缺失时为 null（显示未知）。 */
  executable: boolean | null
  departmentScopeMode: 'all' | 'selected' | null
  departmentRefs: Array<{ institute_id: string; department_name: string }> | null
  doctorVisible: boolean | null
}

export interface EntryDiffItem {
  rule_id: string
  name: string | null
  /** 基础版本中没有该规则时为 null。 */
  from: RuleSetEntryState | null
  /** 草稿中没有该规则时为 null。 */
  to: RuleSetEntryState | null
}

export function toRuleSetEntry(entry: RuleSetEntry): RuleSetEntry {
  return {
    rule_id: entry.rule_id,
    state: entry.state,
    ...(entry.department_scope_mode !== undefined
      ? { department_scope_mode: entry.department_scope_mode }
      : {}),
    ...(entry.department_refs !== undefined ? { department_refs: entry.department_refs } : {}),
    ...(entry.doctor_visible !== undefined ? { doctor_visible: entry.doctor_visible } : {}),
  }
}

function byRuleId<T extends { rule_id: string }>(items: readonly T[]): Map<string, T> {
  return new Map(items.map((item) => [item.rule_id, item]))
}

/** 按当前版本条目生成列表行，合并草稿状态与后端给出的可执行标记、名称、文书。 */
export function buildPointRows(
  currentEntries: readonly RuleSetEntryView[],
  draftEntries: readonly RuleSetEntryView[] | null,
): QualityPointRow[] {
  const draft = draftEntries ? byRuleId(draftEntries) : null
  return currentEntries.map((entry) => {
    const draftEntry = draft?.get(entry.rule_id)
    const executable = draftEntry?.executable ?? entry.executable
    return {
      rule_id: entry.rule_id,
      name: entry.qc_point ?? draftEntry?.qc_point ?? null,
      document: entry.source_document ?? draftEntry?.source_document ?? null,
      category:
        entry.category_name ??
        draftEntry?.category_name ??
        entry.category ??
        draftEntry?.category ??
        null,
      state: entry.state,
      draftState: draftEntry && draftEntry.state !== entry.state ? draftEntry.state : null,
      executable: typeof executable === 'boolean' ? executable : null,
      departmentScopeMode: draftEntry?.department_scope_mode ?? entry.department_scope_mode ?? null,
      departmentRefs: draftEntry?.department_refs ?? entry.department_refs ?? null,
      doctorVisible: draftEntry?.doctor_visible ?? entry.doctor_visible ?? null,
    }
  })
}

export function rowsForTab(rows: readonly QualityPointRow[], tab: PointTab): QualityPointRow[] {
  return rows.filter((row) =>
    tab === 'online' ? row.state === 'active' : row.state === 'paused' || row.state === 'offline',
  )
}

export function filterRows(
  rows: readonly QualityPointRow[],
  field: 'id' | 'name',
  keyword: string,
): QualityPointRow[] {
  const text = keyword.trim().toLowerCase()
  if (!text) return [...rows]
  return rows.filter((row) =>
    field === 'id'
      ? row.rule_id.toLowerCase().includes(text)
      : (row.name ?? '').toLowerCase().includes(text),
  )
}

/** 把选中规则改为目标状态；返回新条目（只含 rule_id/state）与实际变化条数。 */
export function applyStateToEntries(
  entries: readonly RuleSetEntry[],
  ruleIds: readonly string[],
  state: RuleSetEntryState,
): { entries: RuleSetEntry[]; changed: number } {
  const selected = new Set(ruleIds)
  let changed = 0
  const next = entries.map((entry) => {
    const { rule_id, state: current } = entry
    if (selected.has(rule_id) && current !== state) {
      changed += 1
      return toRuleSetEntry({ ...entry, state })
    }
    return toRuleSetEntry(entry)
  })
  return { entries: next, changed }
}

/** 所选规则中不可执行（或可执行标记未知）的规则；这些规则不能开启。 */
export function nonExecutableRuleIds(
  rows: readonly QualityPointRow[],
  ruleIds: readonly string[],
): string[] {
  const rowMap = byRuleId(rows)
  return ruleIds.filter((ruleId) => rowMap.get(ruleId)?.executable !== true)
}

/** 草稿相对基础版本的差异清单，按 rule_id 排序；名称取自条目上的 qc_point。 */
export function diffEntries(
  baseEntries: readonly RuleSetEntryView[],
  draftEntries: readonly RuleSetEntryView[],
): EntryDiffItem[] {
  const base = byRuleId(baseEntries)
  const draft = byRuleId(draftEntries)
  const ids = [...new Set([...base.keys(), ...draft.keys()])].sort()
  return ids.flatMap((ruleId) => {
    const from = base.get(ruleId)?.state ?? null
    const to = draft.get(ruleId)?.state ?? null
    const name = draft.get(ruleId)?.qc_point ?? base.get(ruleId)?.qc_point ?? null
    return from === to ? [] : [{ rule_id: ruleId, name, from, to }]
  })
}

const CONFLICT_MESSAGES: Record<string, string> = {
  draft_exists: '该规则集已有草稿，已刷新为最新草稿，请重新操作',
  version_conflict: '草稿已被他人修改，已刷新为最新内容，请核对后重试',
  version_exists: '版本号已存在，请换一个版本号',
  unsupported_rule_set: '该规则集暂仅支持内置版本，不能修改',
  current_version: '当前版本不能下线',
  builtin_version: '内置版本不能下线',
  already_retired: '该版本已下线，已刷新版本列表',
  draft_changed: '原草稿已被替换，已刷新为当前草稿，请重新导出后修改',
}

/** 409 按业务 code 给出提示；其他错误用后端消息或兜底文案。 */
export function describeFailure(
  result: RuleSetVersionApiResult<unknown>,
  fallback: string,
): string {
  if (result.status === 409 && result.code && CONFLICT_MESSAGES[result.code]) {
    return CONFLICT_MESSAGES[result.code]
  }
  return result.message || fallback
}

/** 这些冲突说明服务端状态已变化，需要刷新页面数据。 */
export function needsRefresh(result: RuleSetVersionApiResult<unknown>): boolean {
  return (
    result.status === 409 &&
    [
      'draft_exists',
      'version_conflict',
      'draft_changed',
      'already_retired',
      'current_version',
    ].includes(result.code ?? '')
  )
}

export function formatDateTime(value: string | null): string {
  if (!value) return UNKNOWN_TEXT
  // 后端版本表存无时区 UTC；无时区后缀时按 UTC 解析。
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasZone ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
