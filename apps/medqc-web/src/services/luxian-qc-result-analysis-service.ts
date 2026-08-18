import { ApiService } from '@/services/apiService'

export type LuxianQcAnalysisStatus =
  'non_compliant' | 'data_gap' | 'uncertain' | 'compliant' | 'not_applicable' | 'not_executed'

export type LuxianQcAnalysisCarePhase = 'inpatient' | 'discharged'

export interface LuxianQcAnalysisRuleItem {
  rule_id: string
  rule_name: string
  evaluated_count: number
  non_compliant_count: number
  data_gap_count: number
  uncertain_count: number
  issue_count: number
  department_distribution: Array<{
    department: string
    record_total: number
    non_compliant_count: number
    data_gap_count: number
    uncertain_count: number
  }>
}

export interface LuxianQcAnalysisRecordItem {
  record_key: string
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  attending_physician: string
  status: LuxianQcAnalysisStatus
  completed_at: string
}

export interface LuxianQcResultAnalysisPayload {
  scope: {
    care_phase: LuxianQcAnalysisCarePhase
    department: string | null
    doctor: string | null
    rule_id: string | null
    result_status: LuxianQcAnalysisStatus | null
    completed_from: string | null
    completed_to: string | null
  }
  kpis: {
    scoped_record_total: number
    ready_record_total: number
    unavailable_result_total: number
  }
  status_distribution: Array<{ status: LuxianQcAnalysisStatus; count: number }>
  rule_distribution: LuxianQcAnalysisRuleItem[]
  physician_distribution: Array<{
    physician: string
    record_total: number
    non_compliant_count: number
    data_gap_count: number
    uncertain_count: number
  }>
  selected_rule: { rule_id: string; rule_name: string } | null
  record_page: {
    page: number
    page_size: number
    total: number
    items: LuxianQcAnalysisRecordItem[]
  }
}

export interface LuxianQcResultAnalysisQuery {
  carePhase: LuxianQcAnalysisCarePhase
  department?: string
  doctor?: string
  ruleId?: string
  resultStatus?: LuxianQcAnalysisStatus
  completedFrom?: string
  completedTo?: string
  page?: number
  pageSize?: number
}

function unwrapPayload(value: unknown): LuxianQcResultAnalysisPayload {
  const outer = value && typeof value === 'object' ? (value as Record<string, unknown>) : null
  const payload = outer && 'data' in outer ? outer.data : outer
  if (!payload || typeof payload !== 'object') {
    throw new Error('质控结果分析返回格式无效')
  }
  return payload as LuxianQcResultAnalysisPayload
}

export async function getLuxianQcResultAnalysis(
  query: LuxianQcResultAnalysisQuery,
): Promise<LuxianQcResultAnalysisPayload> {
  const params: Record<string, string | number> = {
    care_phase: query.carePhase,
    page: query.page || 1,
    page_size: query.pageSize || 20,
  }
  if (query.department?.trim()) params.department = query.department.trim()
  if (query.doctor?.trim()) params.doctor = query.doctor.trim()
  if (query.ruleId?.trim()) params.rule_id = query.ruleId.trim()
  if (query.resultStatus) params.result_status = query.resultStatus
  if (query.completedFrom?.trim()) params.completed_from = `${query.completedFrom.trim()}T00:00:00`
  if (query.completedTo?.trim()) params.completed_to = `${query.completedTo.trim()}T23:59:59`

  const response = await ApiService.getRaw(
    '/api/v1/workstation/qc-result-analysis/luxian-0609',
    params,
  )
  return unwrapPayload(response.data)
}
