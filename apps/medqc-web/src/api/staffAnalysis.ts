import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type StaffAnalysisPeriod = 'this_week' | 'last_week' | 'this_month'
export type StaffAnalysisScene = 'all' | 'running' | 'final'

export interface StaffWorkCounts {
  record_review_count: number
  reviewed_case_count: number
  initial_count: number
  recheck_count: number
  manual_defect_created_count: number
  manual_review_approved_count: number
  manual_review_rejected_count: number
  appeal_approved_count: number
  appeal_rejected_count: number
}

export interface StaffWorkSummary extends StaffWorkCounts {
  active_staff_count: number
  record_reviewer_count: number
  avg_record_reviews_per_active_staff: number | null
  avg_reviewed_cases_per_reviewer: number | null
}

export interface StaffWorkRow extends StaffWorkCounts {
  user_id: string
  name: string | null
  rank: number
}

export interface StaffAnalysisReport {
  period: StaffAnalysisPeriod
  period_label: string
  range: { start: string; end: string }
  scene: StaffAnalysisScene
  summary: StaffWorkSummary | null
  staff: StaffWorkRow[] | null
  unavailable_reason: string | null
}

export interface StaffAnalysisResult {
  success: boolean
  data?: StaffAnalysisReport
  message?: string
  status?: number
}

export async function getStaffAnalysis(
  period: StaffAnalysisPeriod,
  scene: StaffAnalysisScene,
): Promise<StaffAnalysisResult> {
  try {
    const response = await ApiService.requestRaw<StaffAnalysisReport>({
      method: 'GET',
      url: '/api/v1/quality-reports/staff-work',
      params: { period, scene },
    })
    const result = normalizeApiSuccess<StaffAnalysisReport>(response.data)
    return {
      success: result.success,
      data: result.data,
      message: result.message,
      status: response.status,
    }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message: extractApiErrorMessageFromError(error, '质控员工作分析暂不可用'),
    }
  }
}
