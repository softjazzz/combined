export type FrontpageCoverageStatus = 'present' | 'missing' | 'partial'

export interface FrontpageCoverageField {
  group: string
  field: string
  path: string
  status: FrontpageCoverageStatus
  message?: string
}

export interface FrontpageCoverageSummary {
  group: string
  total: number
  present: number
  missing: number
  partial: number
  status: 'completed' | 'missing' | 'review'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function asCoverageStatus(value: unknown): FrontpageCoverageStatus {
  return value === 'present' || value === 'missing' || value === 'partial' ? value : 'missing'
}

export function normalizeCoverageFields(value: unknown): FrontpageCoverageField[] {
  if (!Array.isArray(value)) return []
  return value.filter(isRecord).map((item) => ({
    group: String(item.group || '未分组'),
    field: String(item.field || item.path || '未命名字段'),
    path: String(item.path || ''),
    status: asCoverageStatus(item.status),
    message: typeof item.message === 'string' ? item.message : undefined,
  }))
}

export function extractCoverageFields(reportLike: unknown): FrontpageCoverageField[] {
  if (!isRecord(reportLike)) return []
  const coverage = isRecord(reportLike.coverage) ? reportLike.coverage : reportLike
  return normalizeCoverageFields(coverage.fields)
}

export function summarizeCoverageFields(
  fields: FrontpageCoverageField[],
): FrontpageCoverageSummary[] {
  const byGroup = new Map<string, FrontpageCoverageSummary>()
  for (const field of fields) {
    const group = field.group || '未分组'
    const current =
      byGroup.get(group) ||
      ({
        group,
        total: 0,
        present: 0,
        missing: 0,
        partial: 0,
        status: 'completed',
      } satisfies FrontpageCoverageSummary)
    current.total += 1
    if (field.status === 'present') current.present += 1
    if (field.status === 'missing') current.missing += 1
    if (field.status === 'partial') current.partial += 1
    current.status = current.missing > 0 ? 'missing' : current.partial > 0 ? 'review' : 'completed'
    byGroup.set(group, current)
  }
  return Array.from(byGroup.values())
}

export function topMissingCoverageFields(
  fields: FrontpageCoverageField[],
  limit = 6,
): FrontpageCoverageField[] {
  return fields.filter((item) => item.status === 'missing').slice(0, limit)
}

export function coverageStatusText(status: FrontpageCoverageSummary['status']): string {
  if (status === 'completed') return '已完成'
  if (status === 'review') return '需复核'
  return '有缺失'
}
