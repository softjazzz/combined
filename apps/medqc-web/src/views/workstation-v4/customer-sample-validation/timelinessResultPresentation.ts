import type { SingleRecordQcResultItem } from './single-record-result-model'
import { customerFactValueLabel } from './customerFactValuePresentation'

const TIMELINESS_METRIC_KEYS = ['threshold_hours', 'elapsed_hours', 'overdue_hours'] as const
const TIMELINESS_TIME_KEYS = ['anchor_time', 'observed_time'] as const

const TIMELINESS_FACT_KEYS = [...TIMELINESS_METRIC_KEYS, ...TIMELINESS_TIME_KEYS] as const
const TIMELINESS_METRIC_KEY_SET = new Set<string>(TIMELINESS_METRIC_KEYS)
const TIMELINESS_TIME_KEY_SET = new Set<string>(TIMELINESS_TIME_KEYS)

export type TimelinessFactKey = (typeof TIMELINESS_FACT_KEYS)[number]

export interface TimelinessDisplayRow {
  key: TimelinessFactKey
  label: string
  value: string
}

export interface TimelinessResultPresentation {
  metrics: TimelinessDisplayRow[]
  timeline: TimelinessDisplayRow[]
}

const TIMELINESS_FACT_LABELS: Record<TimelinessFactKey, string> = {
  threshold_hours: '规定时限',
  elapsed_hours: '实际间隔',
  overdue_hours: '超出时限',
  anchor_time: '起算时间',
  observed_time: '记录时间',
}

function formatTimelinessValue(key: TimelinessFactKey, rawValue: unknown): string {
  const values = Array.isArray(rawValue) ? rawValue : [rawValue]
  const value = values
    .map((entry) => {
      if (
        ['threshold_hours', 'elapsed_hours', 'overdue_hours'].includes(key) &&
        typeof entry === 'number' &&
        Number.isFinite(entry)
      ) {
        return `${entry} 小时`
      }
      return customerFactValueLabel(entry) || String(entry)
    })
    .filter(Boolean)
    .join('、')
  return value === 'true' ? '是' : value === 'false' ? '否' : value
}

function timelinessLabel(
  key: TimelinessFactKey,
  item: SingleRecordQcResultItem,
  sourceLabel: string,
): string {
  if (key === 'anchor_time' && item.rule_id === 'LX0609-01-02-01') return '入院时间'
  if (key === 'observed_time' && sourceLabel) return `${sourceLabel}时间`
  return TIMELINESS_FACT_LABELS[key]
}

export function timelinessResultRows(item: SingleRecordQcResultItem): TimelinessDisplayRow[] {
  const facts = item.customer_display_facts
  if (!facts || typeof facts !== 'object' || Array.isArray(facts)) return []

  const sourceLabel = typeof facts.source_label === 'string' ? facts.source_label.trim() : ''
  return TIMELINESS_FACT_KEYS.flatMap((key) => {
    if (!Object.prototype.hasOwnProperty.call(facts, key)) return []
    const value = formatTimelinessValue(key, facts[key])
    if (!value) return []
    return [{ key, label: timelinessLabel(key, item, sourceLabel), value }]
  })
}

export function buildTimelinessResultPresentation(
  item: SingleRecordQcResultItem,
): TimelinessResultPresentation {
  const rows = timelinessResultRows(item)
  return {
    metrics: rows.filter((row) => TIMELINESS_METRIC_KEY_SET.has(row.key)),
    timeline: rows.filter((row) => TIMELINESS_TIME_KEY_SET.has(row.key)),
  }
}

export function hasTimelinessResult(item: SingleRecordQcResultItem): boolean {
  const presentation = buildTimelinessResultPresentation(item)
  return presentation.metrics.length > 0 || presentation.timeline.length > 0
}
