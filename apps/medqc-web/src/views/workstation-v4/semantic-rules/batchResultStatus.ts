import type { SichuanBatchIssueItem } from './types'

export function normalizeLuxianStatusKey(status?: string): string {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'technical_error_internal' || normalized === 'error') return 'technical_error'
  if (normalized === 'unsupported' || normalized === 'not_run') return 'not_executed'
  if (normalized === 'data_quality_gap') return 'data_gap'
  if (normalized === 'needs_manual_review') return 'ai_suggested_non_compliant'
  return normalized
}

export function resolveIssueCanonicalStatus(item: Partial<SichuanBatchIssueItem>): string {
  const isLuxianItem = String(item.rule_id || item.rule_code || '')
    .trim()
    .toUpperCase()
    .startsWith('LX0609-')
  return normalizeLuxianStatusKey(
    isLuxianItem
      ? item.status || item.canonical_status || item.result_status || item.display_status
      : item.result_status || item.status || item.canonical_status || item.display_status,
  )
}
