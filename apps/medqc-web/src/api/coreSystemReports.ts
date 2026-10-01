import { ApiService } from '@/services/apiService'
import { unwrapApiEnvelope } from '@/utils/api-envelope'

export interface CoreReportFilters {
  scene: 'running' | 'final'
  institute_id?: string
  department?: string
  doctor?: string
  completed_from?: string
  completed_to?: string
  system_id?: string
  rule_id?: string
  problems_only?: boolean
}
export interface CorePoint {
  rule_id: string
  rule_name: string
  status: string
  is_confirmed_issue: boolean
  system_ids: string[] | null
}
export interface CoreReportRow {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  doctor: string
  completed_at: string | null
  root_job_id: string | null
  envelope_id: string | null
  rule_set_key: string | null
  rule_set_version: string | null
  coverage: 'known' | 'unknown' | 'unavailable'
  points: CorePoint[]
}
export interface CoreSystemReport {
  as_of: string
  scene: 'running' | 'final'
  contract: string
  scope: { scope_label: string; scope_basis: string; archive_status: string | null }
  reference: {
    title: string
    reference_date: string
    source_url: string
    reference_note: string
    systems: Array<{ id: string; name: string; text: string }>
  }
  systems: Array<{
    id: string
    name: string
    record_count: number | null
    problem_records: number | null
    problem_rate: number | null
    points: Array<
      Pick<CorePoint, 'rule_id' | 'rule_name' | 'system_ids'> & {
        rule_set_key: string
        rule_set_version: string
        record_count: number
        problem_records: number
      }
    >
  }>
  summary: {
    candidate_records: number
    unknown_records: number
    unavailable_records: number
    unknown_points: number
  }
  items: CoreReportRow[]
  total: number
  page: number
  page_size: number
}
const base = '/api/v1/core-system-reports'
function params(filters: CoreReportFilters): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== '' && value !== undefined),
  )
}
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const count = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const ids = Array.from({ length: 18 }, (_, index) => `CORE-${String(index + 1).padStart(2, '0')}`)
function point(value: unknown): boolean {
  return (
    object(value) &&
    typeof value.rule_id === 'string' &&
    !!value.rule_id &&
    typeof value.rule_name === 'string' &&
    typeof value.status === 'string' &&
    typeof value.is_confirmed_issue === 'boolean' &&
    (value.system_ids === null ||
      (Array.isArray(value.system_ids) && value.system_ids.every((id) => ids.includes(String(id)))))
  )
}
function pointSummary(value: unknown): boolean {
  return (
    object(value) &&
    typeof value.rule_id === 'string' &&
    !!value.rule_id &&
    typeof value.rule_name === 'string' &&
    Array.isArray(value.system_ids) &&
    value.system_ids.length > 0 &&
    value.system_ids.every((id) => ids.includes(String(id)))
  )
}
function assertReport(value: unknown, page: number): asserts value is CoreSystemReport {
  const fail = () => {
    throw new Error('核心制度报表回执不完整，请重试')
  }
  if (
    !object(value) ||
    typeof value.as_of !== 'string' ||
    !Number.isFinite(Date.parse(value.as_of)) ||
    typeof value.contract !== 'string' ||
    !['running', 'final'].includes(String(value.scene)) ||
    !object(value.scope) ||
    typeof value.scope.scope_label !== 'string' ||
    typeof value.scope.scope_basis !== 'string' ||
    !(value.scope.archive_status === null || typeof value.scope.archive_status === 'string') ||
    !object(value.summary) ||
    !['candidate_records', 'unknown_records', 'unavailable_records', 'unknown_points'].every(
      (key) => count(value.summary && object(value.summary) ? value.summary[key] : undefined),
    ) ||
    !count(value.total) ||
    value.page !== page ||
    value.page_size !== 20 ||
    !Array.isArray(value.items) ||
    value.items.length > 20 ||
    !Array.isArray(value.systems) ||
    value.systems.length !== 18 ||
    !object(value.reference) ||
    value.reference.reference_date !== '2018-04-18' ||
    typeof value.reference.source_url !== 'string' ||
    typeof value.reference.reference_note !== 'string' ||
    typeof value.reference.title !== 'string' ||
    !Array.isArray(value.reference.systems) ||
    value.reference.systems.length !== 18
  )
    return fail()
  if (
    !value.systems.every((system, index) => {
      if (
        !object(system) ||
        system.id !== ids[index] ||
        typeof system.name !== 'string' ||
        !Array.isArray(system.points)
      )
        return false
      const validCounts =
        system.record_count === null
          ? system.problem_records === null && system.problem_rate === null
          : count(system.record_count) &&
            system.record_count > 0 &&
            count(system.problem_records) &&
            system.problem_records <= system.record_count &&
            typeof system.problem_rate === 'number' &&
            system.problem_rate === system.problem_records / system.record_count
      return (
        validCounts &&
        system.points.every(
          (p) =>
            pointSummary(p) &&
            object(p) &&
            typeof p.rule_set_key === 'string' &&
            typeof p.rule_set_version === 'string' &&
            count(p.record_count) &&
            count(p.problem_records) &&
            p.problem_records <= p.record_count,
        )
      )
    }) ||
    !value.reference.systems.every(
      (system, index) =>
        object(system) &&
        system.id === ids[index] &&
        typeof system.name === 'string' &&
        typeof system.text === 'string' &&
        system.text.length > 0,
    ) ||
    !value.items.every(
      (row) =>
        object(row) &&
        ['institute_id', 'patient_id', 'visit_id', 'patient_name', 'department', 'doctor'].every(
          (key) => typeof row[key] === 'string',
        ) &&
        !!row.institute_id &&
        !!row.patient_id &&
        !!row.visit_id &&
        ['completed_at', 'root_job_id', 'envelope_id', 'rule_set_key', 'rule_set_version'].every(
          (key) => row[key] === null || typeof row[key] === 'string',
        ) &&
        ['known', 'unknown', 'unavailable'].includes(String(row.coverage)) &&
        Array.isArray(row.points) &&
        row.points.every(point),
    )
  )
    return fail()
}
export async function getCoreSystemReport(
  filters: CoreReportFilters,
  page = 1,
): Promise<CoreSystemReport> {
  const response = await ApiService.requestRaw<unknown>({
    url: base,
    method: 'GET',
    params: { ...params(filters), page, page_size: 20 },
  })
  const result = unwrapApiEnvelope<unknown>(response.data)
  assertReport(result, page)
  return result
}
export async function exportCoreSystemReport(filters: CoreReportFilters): Promise<Blob> {
  return (
    await ApiService.requestRaw<Blob>({
      url: `${base}/export`,
      method: 'GET',
      params: params(filters),
      responseType: 'blob',
    })
  ).data
}
