/**
 * 测试病历页面展示辅助：只做格式化与搬运，不重判条目状态或规则归属。
 */
import type {
  CurrentRuleSetCatalog,
  RuleSetEntryState,
  TestRecordItem,
} from '@/types/test-medical-records'

const ENTRY_STATE_LABELS: Record<RuleSetEntryState, string> = {
  active: '启用',
  paused: '暂停',
  offline: '下线',
}

export interface RuleOption {
  value: string
  label: string
}

/** 规则名称只取当前版本详情的 qc_point；缺失时仅显示 rule_id，不猜名称。 */
export function formatRuleLabel(
  ruleId: string,
  qcPoint: string | null,
  sourceDocument: string | null,
  state?: RuleSetEntryState,
): string {
  const parts = [ruleId]
  if (sourceDocument) parts.push(sourceDocument)
  if (qcPoint) parts.push(qcPoint)
  const text = parts.join(' · ')
  return state && state !== 'active' ? `${text}（${ENTRY_STATE_LABELS[state]}）` : text
}

export function buildRuleOptions(
  catalog: CurrentRuleSetCatalog | null,
  selectedRuleIds: string[] = [],
): RuleOption[] {
  const entries = catalog?.entries || []
  const options: RuleOption[] = entries.map((entry) => ({
    value: entry.rule_id,
    label: formatRuleLabel(entry.rule_id, entry.qc_point, entry.source_document, entry.state),
  }))
  const known = new Set(entries.map((entry) => entry.rule_id))
  selectedRuleIds
    .filter((ruleId) => !known.has(ruleId))
    .forEach((ruleId) => options.push({ value: ruleId, label: `${ruleId}（不在当前版本）` }))
  return options
}

export function formatDocumentCount(value: number | null): string {
  return typeof value === 'number' ? String(value) : '未知'
}

export function formatDateTime(value: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '未知'
  // 后端写入 UTC naive 时间；无时区后缀时按 UTC 解释再转本地显示。
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(text) ? text : `${text}Z`
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return text
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ${pad(
    parsed.getHours(),
  )}:${pad(parsed.getMinutes())}`
}

export function resolveStateTag(item: TestRecordItem): { color: string; text: string } {
  if (item.state === 'active') return { color: 'green', text: '有效' }
  if (item.state === 'removed') return { color: 'default', text: '已移除' }
  if (item.state === 'superseded') {
    return { color: 'orange', text: `已被替换${item.superseded_by ? ` → ${item.superseded_by}` : ''}` }
  }
  return { color: 'default', text: '状态未知' }
}

export function resolveOriginText(item: TestRecordItem): string {
  if (item.origin === 'derived') {
    return item.source_item_id ? `编辑派生（替换 ${item.source_item_id}）` : '派生副本'
  }
  return '新建'
}
