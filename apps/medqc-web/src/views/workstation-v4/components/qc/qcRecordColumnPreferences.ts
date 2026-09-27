import type { QcRecordCarePhase } from './QcRecordResultTable.vue'

export type QcRecordOptionalColumn = 'department' | 'time' | 'summary' | 'latestQc' | 'score'

export interface QcRecordColumnOption {
  key: QcRecordOptionalColumn
  label: string
}

export const QC_RECORD_COLUMN_OPTIONS: readonly QcRecordColumnOption[] = [
  { key: 'department', label: '科室 / 床位' },
  { key: 'time', label: '入院 / 出院时间' },
  { key: 'summary', label: '问题摘要' },
  { key: 'latestQc', label: '最近质控' },
  { key: 'score', label: '得分 / 等级' },
]

const STORAGE_VERSION = 1
const STORAGE_PREFIX = 'medqc:qc-record-columns:v1'

interface StoredQcRecordColumns {
  version: typeof STORAGE_VERSION
  columns: QcRecordOptionalColumn[]
}

export function defaultQcRecordColumns(options: {
  compactReview: boolean
  showScore: boolean
}): QcRecordOptionalColumn[] {
  const columns: QcRecordOptionalColumn[] = options.compactReview
    ? ['summary', 'latestQc']
    : ['department', 'time', 'summary', 'latestQc']
  if (options.showScore) columns.push('score')
  return columns
}

export function sanitizeQcRecordColumns(
  value: unknown,
  allowed: readonly QcRecordOptionalColumn[],
  defaults: readonly QcRecordOptionalColumn[],
): QcRecordOptionalColumn[] {
  if (!Array.isArray(value)) return [...defaults]
  const allowedSet = new Set<QcRecordOptionalColumn>(allowed)
  if (value.some((column) => typeof column !== 'string' || !allowedSet.has(column as QcRecordOptionalColumn))) {
    return [...defaults]
  }
  return [...new Set(value as QcRecordOptionalColumn[])]
}

export function qcRecordColumnStorageKey(
  userId: string | null | undefined,
  carePhase: QcRecordCarePhase,
): string | null {
  const stableUserId = String(userId || '').trim()
  if (!stableUserId || stableUserId === 'unknown') return null
  return `${STORAGE_PREFIX}:${encodeURIComponent(stableUserId)}:${carePhase}`
}

export function loadQcRecordColumns(
  storage: Pick<Storage, 'getItem'>,
  key: string,
  allowed: readonly QcRecordOptionalColumn[],
  defaults: readonly QcRecordOptionalColumn[],
): QcRecordOptionalColumn[] {
  try {
    const raw = storage.getItem(key)
    if (!raw) return [...defaults]
    const payload = JSON.parse(raw) as Partial<StoredQcRecordColumns>
    if (payload.version !== STORAGE_VERSION) return [...defaults]
    return sanitizeQcRecordColumns(payload.columns, allowed, defaults)
  } catch {
    return [...defaults]
  }
}

export function saveQcRecordColumns(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  columns: readonly QcRecordOptionalColumn[],
): boolean {
  try {
    const payload: StoredQcRecordColumns = {
      version: STORAGE_VERSION,
      columns: [...columns],
    }
    storage.setItem(key, JSON.stringify(payload))
    return true
  } catch {
    return false
  }
}
