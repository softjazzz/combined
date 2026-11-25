import { ApiService } from '@/services/apiService'
import { normalizeRecord, normalizeRecordLatestQcSummary } from '../normalize'
import type { PatientRecord, RecordLatestQcSummary } from '../types'
import type { SichuanBatchJob } from '../semantic-rules/types'
import type { QCRecordResultFocus } from '../customer-sample-validation/QCRecordResultComparisonDrawer.vue'
import {
  resolveResultPresentation,
  statusCount,
} from '../components/qc/latestQcSummaryPresentation'
import { buildCaseRecordKey } from './caseRecordKey'

const WORKSTATION_URL = '/api/medical-records/workstation'

export interface BatchResultRecordItem {
  recordKey: string
  instituteId: string
  patientId: string
  visitId: string
  recordId: string
  patientName: string
  patientSex?: string
  patientAge?: number
  department: string
  doctor?: string
  admissionDate?: string
  dischargeDate?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  confirmedIssueCount: number
  resultStatus:
    | 'priority'
    | 'completed'
    | 'data-gap'
    | 'uncertain'
    | 'technical-error'
    | 'not-run'
    | 'unknown'
  resultLabel: string
  issueSummary: string
  latestQcTime: string
}

export interface ResolvedBatchResults {
  jobId: string
  items: BatchResultRecordItem[]
  totalCount: number
  issueRecordCount: number
  compliantRecordCount: number
}

function workstationPayload(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== 'object') return {}
  const record = raw as Record<string, unknown>
  if (record.data && typeof record.data === 'object') {
    return record.data as Record<string, unknown>
  }
  return record
}

function recordIdentityKey(record: Partial<PatientRecord>): string {
  const explicitKey = String(record.recordKey || '').trim()
  if (explicitKey) return explicitKey
  const instituteId = String(record.instituteId || '').trim()
  const patientId = String(record.patientId || '').trim()
  const visitId = String(record.visitId || '').trim()
  return buildCaseRecordKey(instituteId, patientId, visitId)
}

function hasCompleteIdentity(record: PatientRecord): boolean {
  return Boolean(
    String(record.instituteId || '').trim() &&
      String(record.patientId || '').trim() &&
      String(record.visitId || '').trim(),
  )
}

function formatMedicalRecordTimestamp(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return ''
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}):(\d{2}))?/u)
  if (!match) return ''
  return match[2] && match[3] ? `${match[1]} ${match[2]}:${match[3]}` : match[1]
}

function statusSortRank(status: BatchResultRecordItem['resultStatus']): number {
  switch (status) {
    case 'priority':
      return 0
    case 'technical-error':
      return 1
    case 'data-gap':
      return 2
    case 'uncertain':
      return 3
    case 'completed':
      return 4
    case 'not-run':
      return 5
    default:
      return 6
  }
}

export function sortBatchResultRecords(items: BatchResultRecordItem[]): BatchResultRecordItem[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      if (right.item.confirmedIssueCount !== left.item.confirmedIssueCount) {
        return right.item.confirmedIssueCount - left.item.confirmedIssueCount
      }
      const rankDiff = statusSortRank(left.item.resultStatus) - statusSortRank(right.item.resultStatus)
      if (rankDiff !== 0) return rankDiff
      return left.index - right.index
    })
    .map(({ item }) => item)
}

export function toBatchResultRecordItem(
  record: PatientRecord,
  summaryOverride: RecordLatestQcSummary | undefined,
  confirmedOnly: boolean,
): BatchResultRecordItem {
  const summary = summaryOverride ?? record.latestQcSummary
  const presentation = resolveResultPresentation(summary, 'ready', { confirmedOnly })
  const confirmedIssueCount = statusCount(summary?.statusCounts || {}, 'non_compliant')
  const recordKey = recordIdentityKey(record)
  return {
    recordKey,
    instituteId: String(record.instituteId || '').trim(),
    patientId: String(record.patientId || '').trim(),
    visitId: String(record.visitId || '').trim(),
    recordId: String(record.id || record.visitId || '').trim(),
    patientName: String(record.name || '').trim() || '患者信息待核实',
    patientSex: record.sex,
    patientAge: record.age,
    department: String(record.department || '').trim() || '未分科室',
    doctor: String(record.doctor || '').trim() || undefined,
    admissionDate: record.admissionDate,
    dischargeDate: record.dischargeDate,
    hospitalizationStatus: record.hospitalizationStatus,
    confirmedIssueCount,
    resultStatus: presentation.resultStatus,
    resultLabel: presentation.resultLabel,
    issueSummary: presentation.issueSummary,
    latestQcTime: presentation.latestQcTime,
  }
}

export function toComparisonFocusFromBatchItem(item: BatchResultRecordItem): QCRecordResultFocus {
  const labelParts = [
    item.patientName || '患者信息待核实',
    item.department || '未分科室',
    `住院号 ${item.visitId}`,
  ]
  return {
    visitId: item.visitId,
    instituteId: item.instituteId,
    patientId: item.patientId,
    recordId: item.recordId || item.visitId,
    patientName: item.patientName,
    patientSex: item.patientSex,
    patientAge: item.patientAge,
    admissionTime: formatMedicalRecordTimestamp(item.admissionDate) || undefined,
    dischargeTime: formatMedicalRecordTimestamp(item.dischargeDate) || undefined,
    listQcTime:
      item.latestQcTime && item.latestQcTime !== '—' ? `质控结束 ${item.latestQcTime}` : undefined,
    label: labelParts.join(' · '),
  }
}

async function fetchJobRecordsFromWorkstation(
  jobId: string,
  sourceId?: string,
): Promise<PatientRecord[]> {
  try {
    const params: Record<string, string | number> = {
      analytics_job_id: jobId,
      page: 1,
      page_size: 200,
    }
    if (sourceId) params.source_id = sourceId
    const response = await ApiService.getRaw(WORKSTATION_URL, { params })
    const data = workstationPayload(response.data)
    const rawRecords = Array.isArray(data.records) ? data.records : []
    return rawRecords.map(normalizeRecord).filter(hasCompleteIdentity)
  } catch {
    return []
  }
}

async function fetchLatestSummariesForRecordKeys(
  recordKeys: string[],
  sourceId?: string,
): Promise<Map<string, RecordLatestQcSummary>> {
  const summaries = new Map<string, RecordLatestQcSummary>()
  const uniqueKeys = [...new Set(recordKeys.map((key) => key.trim()).filter(Boolean))]
  if (!uniqueKeys.length) return summaries
  try {
    const params: Record<string, string> = {}
    if (sourceId) params.source_id = sourceId
    const response = await ApiService.postRaw(
      `${WORKSTATION_URL}/qc-summary`,
      { record_keys: uniqueKeys, include_totals: false },
      { params },
    )
    const data = workstationPayload(response.data)
    const rawRecords = Array.isArray(data.records) ? data.records : []
    for (const rawRecord of rawRecords) {
      if (!rawRecord || typeof rawRecord !== 'object') continue
      const record = rawRecord as Record<string, unknown>
      const key =
        typeof record.recordKey === 'string'
          ? record.recordKey.trim()
          : typeof record.record_key === 'string'
            ? record.record_key.trim()
            : ''
      const rawSummary = record.latest_qc_summary ?? record.latestQcSummary
      if (key && rawSummary) {
        summaries.set(key, normalizeRecordLatestQcSummary(rawSummary))
      }
    }
  } catch {
    // 摘要拉取失败时退回病历自身已缓存摘要
  }
  return summaries
}

export async function resolveBatchResultRecords(options: {
  job: SichuanBatchJob
  sourceId?: string
  submittedRecords?: PatientRecord[]
  currentRecords?: PatientRecord[]
  confirmedOnly: boolean
}): Promise<ResolvedBatchResults> {
  const { job, sourceId, submittedRecords = [], currentRecords = [], confirmedOnly } = options
  const jobId = String(job.id || '').trim()
  const expectedTotal = Math.max(
    0,
    Math.trunc(Number(job.total_records ?? job.summary?.total_records ?? 0) || 0),
  )

  const recordMap = new Map<string, PatientRecord>()
  const currentMap = new Map<string, PatientRecord>()
  for (const record of currentRecords) {
    if (!hasCompleteIdentity(record)) continue
    const key = recordIdentityKey(record)
    if (key) currentMap.set(key, record)
  }

  for (const record of submittedRecords) {
    if (!hasCompleteIdentity(record)) continue
    const key = recordIdentityKey(record)
    if (!key) continue
    const fresher = currentMap.get(key)
    recordMap.set(key, fresher ? { ...record, ...fresher } : record)
  }

  if (jobId && (recordMap.size === 0 || (expectedTotal > 0 && recordMap.size < expectedTotal))) {
    const serverRecords = await fetchJobRecordsFromWorkstation(jobId, sourceId)
    for (const record of serverRecords) {
      const key = recordIdentityKey(record)
      if (!key) continue
      const existing = recordMap.get(key) ?? currentMap.get(key)
      recordMap.set(key, existing ? { ...existing, ...record } : record)
    }
  }

  const resolvedRecords = [...recordMap.values()]
  const recordKeys = resolvedRecords.map((record) => recordIdentityKey(record)).filter(Boolean)
  const latestSummaries = await fetchLatestSummariesForRecordKeys(recordKeys, sourceId)

  const mapped = resolvedRecords.map((record) => {
    const key = recordIdentityKey(record)
    return toBatchResultRecordItem(record, latestSummaries.get(key), confirmedOnly)
  })
  const items = sortBatchResultRecords(mapped)
  const issueRecordCount = items.filter((item) => item.confirmedIssueCount > 0).length
  const compliantRecordCount = items.filter(
    (item) => item.confirmedIssueCount === 0 && item.resultStatus === 'completed',
  ).length

  return {
    jobId,
    items,
    totalCount: items.length,
    issueRecordCount,
    compliantRecordCount,
  }
}
