import type { PatientRecord, QCIssueLike } from './types'

export function isDefectStatus(status: string): boolean {
  return status === 'has_defects' || status === 'warning'
}

export function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: '\u5df2\u5b8c\u6210',
    has_defects: '\u9ad8\u98ce\u9669',
    warning: '\u9ad8\u98ce\u9669',
    processing: '\u5904\u7406\u4e2d',
    pending: '\u5f85\u5904\u7406',
  }
  return map[status] || '\u5f85\u5904\u7406'
}

export function getStatusTheme(status: string): 'emerald' | 'rose' | 'blue' | 'slate' {
  if (status === 'completed') return 'emerald'
  if (isDefectStatus(status)) return 'rose'
  if (status === 'processing') return 'blue'
  return 'slate'
}

export function resolveVisitId(record: PatientRecord): string {
  return (record as any).visitId || record.id
}

export function normalizeDefect(raw: QCIssueLike, index: number): QCIssueLike & { id: string } {
  return {
    ...raw,
    id: (raw as any).id || `defect-${index}`,
  }
}
