import patientIconBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import patientIconElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import patientIconElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import patientIconGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import patientIconMan from '@/assets/avatar-icons/patient-icon-man.png'
import patientIconWoman from '@/assets/avatar-icons/patient-icon-woman.png'

import type { ManualSamplePoolRecord } from './types'

export const CUSTOMER_TEST_POOL_ID = 'customer-created-test-records-v1'

export function recordSortTime(record: ManualSamplePoolRecord): string {
  const fromRecord = String(record.created_at || record.updated_at || '').trim()
  if (fromRecord) return fromRecord
  return String(
    record.sample_items?.[0]?.created_at || record.sample_items?.[0]?.updated_at || '',
  ).trim()
}

export function isFocusedRecord(record: ManualSamplePoolRecord, focusedRecordId: string): boolean {
  const normalizedFocus = String(focusedRecordId || '').trim()
  if (!normalizedFocus) return false
  return [record.id, record.matched_visit_id, record.mr_no].some(
    (value) => String(value || '').trim() === normalizedFocus,
  )
}

export function sortManualSampleRecordsForDisplay(
  items: ManualSamplePoolRecord[],
  poolId: string,
  focusedRecordId = '',
): ManualSamplePoolRecord[] {
  const shouldSortCustomerTestPool = poolId === CUSTOMER_TEST_POOL_ID
  if (!shouldSortCustomerTestPool && !focusedRecordId) return items
  return [...items].sort((left, right) => {
    const leftFocused = isFocusedRecord(left, focusedRecordId)
    const rightFocused = isFocusedRecord(right, focusedRecordId)
    if (leftFocused !== rightFocused) return leftFocused ? -1 : 1
    if (shouldSortCustomerTestPool) {
      return recordSortTime(right).localeCompare(recordSortTime(left))
    }
    return 0
  })
}

export function resolveRecordPatientName(record: ManualSamplePoolRecord): string {
  return String(record.patient_name || '').trim() || '-'
}

export function resolveRecordCaseTitle(record: ManualSamplePoolRecord): string {
  const caseTitle = record.sample_items
    .map((item) => {
      const rawPayload = item.raw_payload || {}
      return typeof rawPayload.case_title === 'string' ? rawPayload.case_title.trim() : ''
    })
    .find(Boolean)
  return caseTitle || ''
}

export function resolveRecordMainDiagnosis(record: ManualSamplePoolRecord): string {
  for (const item of record.sample_items || []) {
    const rawPayload = item.raw_payload || {}
    const basicInfo = rawPayload.basic_info
    const candidates = [
      rawPayload.main_diagnosis,
      rawPayload.diagnosis,
      typeof basicInfo === 'object' && basicInfo !== null
        ? (basicInfo as Record<string, unknown>).main_diagnosis
        : undefined,
      typeof basicInfo === 'object' && basicInfo !== null
        ? (basicInfo as Record<string, unknown>).diagnosis
        : undefined,
    ]
    const diagnosis = candidates
      .map((value) => (typeof value === 'string' ? value.trim() : ''))
      .find(Boolean)
    if (diagnosis) return diagnosis
  }
  return ''
}

export function resolveRecordDisplayTitle(record: ManualSamplePoolRecord): string {
  const caseTitle = resolveRecordCaseTitle(record)
  if (caseTitle) {
    const cleaned = caseTitle
      .replace(/[-_]\d{10,}$/u, '')
      .replace(/CUSTOMER_TEST_\d+[A-Z0-9]*$/u, '')
      .replace(/[｜|]\s*LX(?:0609-)?\d{3}(?:[/、,，]\s*(?:LX(?:0609-)?)?\d{3})*\s*/u, '')
      .replace(/[｜|]\s*\d{2,4}[-_/年]?\d{1,2}[-_/月]?\d{1,2}日?\s*\d{0,2}:?\d{0,2}\s*$/u, '')
      .replace(/[｜|]\s*\d{4}[-_/]?\d{2}[-_/]?\d{2}[-_/]?\d{0,6}\s*$/u, '')
      .replace(/[｜|]\s*\d{4}-\d{4}\s*$/u, '')
      .replace(/[-_]\d{13,}$/u, '')
      .replace(/\s+/gu, ' ')
      .trim()
    return cleaned || caseTitle
  }
  return resolveRecordPatientName(record)
}

export function resolveRecordPatientTitle(record: ManualSamplePoolRecord): string {
  const patientName = resolveRecordPatientName(record)
  let title = resolveRecordDisplayTitle(record).replace(/病历$/u, '').trim()
  if (patientName !== '-' && title.startsWith(patientName)) {
    title = title
      .slice(patientName.length)
      .replace(/^[\s·・,，:：-]+/u, '')
      .trim()
  }
  if (!title || title === patientName) return patientName === '-' ? '-' : patientName
  return [patientName === '-' ? '' : patientName, title].filter(Boolean).join(' · ') || '-'
}

export function resolveRecordPatientAvatarSrc(record: ManualSamplePoolRecord): string {
  const sex = resolveRecordPatientSex(record)
  const age = resolveRecordPatientAge(record)
  const female = /女|female|^f$/iu.test(sex)
  if (Number.isFinite(age) && age > 0 && age < 14) {
    return female ? patientIconGirl : patientIconBoy
  }
  if (Number.isFinite(age) && age >= 55) {
    return female ? patientIconElderWoman : patientIconElderMan
  }
  return female ? patientIconWoman : patientIconMan
}

function resolveRecordPatientSex(record: ManualSamplePoolRecord): string {
  const directValue = pickStringField(record as unknown as Record<string, unknown>, [
    'patient_sex',
    'patient_gender',
    'sex',
    'gender',
  ])
  if (directValue) return directValue
  const payloads = collectRecordPayloads(record)
  for (const payload of payloads) {
    const value = pickStringField(payload, ['sex', 'patient_sex', 'patient_gender', 'gender'])
    if (value) return value
    const basicInfo = payload.basic_info
    if (isPlainRecord(basicInfo)) {
      const basicValue = pickStringField(basicInfo, [
        'sex',
        'patient_sex',
        'patient_gender',
        'gender',
      ])
      if (basicValue) return basicValue
    }
  }
  return ''
}

function resolveRecordPatientAge(record: ManualSamplePoolRecord): number {
  const directValue = pickNumberField(record as unknown as Record<string, unknown>, [
    'patient_age',
    'age',
    'age_year',
    'age_years',
  ])
  if (directValue > 0) return directValue
  const payloads = collectRecordPayloads(record)
  for (const payload of payloads) {
    const value = pickNumberField(payload, ['age', 'patient_age', 'age_year', 'age_years'])
    if (value > 0) return value
    const basicInfo = payload.basic_info
    if (isPlainRecord(basicInfo)) {
      const basicValue = pickNumberField(basicInfo, ['age', 'patient_age', 'age_year', 'age_years'])
      if (basicValue > 0) return basicValue
    }
  }
  return 0
}

function collectRecordPayloads(record: ManualSamplePoolRecord): Record<string, unknown>[] {
  return (record.sample_items || []).map((item) => item.raw_payload).filter(isPlainRecord)
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function pickStringField(source: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function pickNumberField(source: Record<string, unknown>, keys: string[]): number {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string') {
      const parsed = Number(value.replace(/[^\d.]/gu, ''))
      if (Number.isFinite(parsed)) return parsed
    }
  }
  return 0
}

export function resolveRecordIdentifier(record: ManualSamplePoolRecord): string {
  const rawVisitId = String(record.sample_items?.[0]?.visit_id || '').trim()
  return (
    String(record.mr_no || '').trim() ||
    rawVisitId ||
    String(record.matched_visit_id || '').trim() ||
    '-'
  )
}

export function resolveRecordDisplayCode(record: ManualSamplePoolRecord): string {
  const identifier = resolveRecordIdentifier(record)
  if (/^CUSTOMER_TEST_/u.test(identifier.trim())) {
    const displayTime = formatRecordCodeTime(recordSortTime(record))
    if (displayTime) return `测试-${displayTime}`
  }
  const customerTestMatch = identifier
    .trim()
    .match(/^CUSTOMER_TEST_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})\d{0,2}[A-Z0-9]*$/u)
  if (customerTestMatch) {
    const [, , month, day, hour, minute] = customerTestMatch
    return `测试-${month}${day}-${hour}${minute}`
  }
  return resolveRecordShortIdentifier(record).replace(/^编号\s*/u, '')
}

function resolveRecordShortIdentifier(record: ManualSamplePoolRecord): string {
  const identifier = resolveRecordIdentifier(record)
  if (identifier === '-') return '-'
  const normalized = identifier.trim()
  const customerTestMatch = normalized.match(/^CUSTOMER_TEST_(\d{8})(\d{4,6})([A-Z0-9]+)$/u)
  if (customerTestMatch) {
    const [, , , suffix] = customerTestMatch
    return `编号 ${suffix.slice(-6)}`
  }
  return normalized.length > 22 ? `编号 ...${normalized.slice(-10)}` : `编号 ${normalized}`
}

export function resolveRecordCreatedDate(record: ManualSamplePoolRecord): string {
  const raw = recordSortTime(record)
  if (!raw) return ''
  return formatCompactDate(raw)
}

function formatRecordCodeTime(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const date = parseBackendDateTime(text)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('month')}${getPart('day')}-${getPart('hour')}${getPart('minute')}`
}

function formatCompactDate(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const date = parseBackendDateTime(text)
  if (Number.isNaN(date.getTime())) return text
  const parts = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('year')}-${getPart('month')}-${getPart('day')}`
}

export function parseBackendDateTime(value: string): Date {
  const text = value.trim()
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const normalizedWithMilliseconds = normalized.replace(/\.(\d{3})\d+/u, '.$1')
  return new Date(hasTimezone ? normalizedWithMilliseconds : `${normalizedWithMilliseconds}Z`)
}

export function formatRecordDischargeTime(value?: string): string {
  const text = String(value || '').trim()
  if (!text) return ''
  const matched = text.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)/u)
  return matched ? `${matched[1]} ${matched[2]}` : text
}
