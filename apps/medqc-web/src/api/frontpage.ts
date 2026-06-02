/**
 * 病案首页 API
 *
 * 提供病案首页自动生成和画像分析相关接口
 */

import { http } from '@/utils/http'
import { unwrapApiEnvelope } from '@/utils/api-envelope'

const FRONTPAGE_AUTO_GENERATE_TIMEOUT_MS = 180000

export type FrontpageReportScene = 'nhc_frontpage' | 'insurance_settlement' | 'combined'

export type AuditFindingType =
  | 'diagnosis_missing'
  | 'procedure_missing'
  | 'diagnosis_inappropriate'
  | 'diagnosis_insufficient_evidence'

export type AuditFindingSeverity = 'high' | 'medium' | 'low'

export interface MainDiagnosisKeyEvidence {
  quote?: string
  source?: string
  why_it_supports?: string
}

export interface MainDiagnosisLLMEvidence {
  clinician_main_diagnosis?: string
  llm_recommended_main_diagnosis?: string
  is_consistent_with_clinician?: boolean
  recommended_main_diagnosis_action?: 'promote_existing' | 'refine_current' | 'keep'
  recommended_main_diagnosis_source?: 'other_diagnosis' | 'llm_refinement' | 'none'
  recommended_main_diagnosis_source_other_index?: number
  recommendation_summary?: string
  confidence?: number
  conclusion?: string
  key_evidence?: MainDiagnosisKeyEvidence[]
  reasoning_summary?: string
}

export interface CodingAuditEvidenceLine {
  quote?: string
  source?: string
  why_it_supports?: string
}

export interface CodingAuditFinding {
  type?: AuditFindingType
  severity?: AuditFindingSeverity
  clinician_text?: string
  llm_recommendation?: string
  reason?: string
  evidence?: CodingAuditEvidenceLine[]
}

export interface CodingAuditLLMEvidence {
  version?: string
  summary?: string
  confidence?: number
  counts?: Partial<Record<AuditFindingType, number>>
  findings?: CodingAuditFinding[]
  top_alert?: {
    type?: AuditFindingType
    severity?: AuditFindingSeverity
    summary?: string
    count?: number
  } | null
}

export interface FrontPageEvidence {
  main_diagnosis_llm?: MainDiagnosisLLMEvidence | null
  coding_audit_llm?: CodingAuditLLMEvidence | null
  [key: string]: any
}

export interface FrontPageDraft {
  basic_info: any
  hospitalization: any
  diagnoses: any
  procedures: any
  other_medical_info: any
  staff: any
  costs: any
  evidence: FrontPageEvidence
  confidence: any
}

export interface ProfileAnalyzeRequest {
  visit_id?: string
  medical_text?: string
  frontpage_diagnoses?: string[]
  frontpage_procedures?: string[]
}

export interface ProfileAnalyzeResponse {
  success: boolean
  data?: {
    diagnosis_timeline: Array<{
      diagnosis_name: string
      first_mention_time?: string
      first_mention_source?: string
      status: 'suspected' | 'confirmed' | 'ruled_out'
      timeline_events?: Array<{
        time: string
        event: string
        source: string
      }>
    }>
    surgery_verification: Array<{
      surgery_name: string
      plan_source?: string
      execution_source?: string
      execution_time?: string
      verification_status: 'verified' | 'planned_only' | 'executed_only'
    }>
    discrepancies: Array<{
      type: 'missing_in_frontpage' | 'not_supported_by_record' | 'inconsistent'
      item_category: 'diagnosis' | 'procedure'
      item_name: string
      suggestion: string
      severity: 'warning' | 'error'
    }>
  }
  message?: string
  error?: string
}

export interface AutoGenerateRequest {
  visit_id?: string
  medical_text?: string
  force_llm?: boolean
  scene?: FrontpageReportScene
  report_scene?: FrontpageReportScene
  documents?: Array<{
    type: string
    content: string
  }>
}

export interface AutoGenerateResponse {
  success: boolean
  data?: {
    frontpage: FrontPageDraft
  }
  message?: string
  error?: string
}

export interface GenerateReportDraftRequest {
  visit_id?: string
  patient_id?: string
  medical_text?: string
  scene?: FrontpageReportScene
  report_scene?: FrontpageReportScene
  documents?: Array<{
    type: string
    content: string
    meta?: Record<string, unknown>
  }>
}

export interface FrontpageCoverageField {
  group: string
  field: string
  path: string
  status: 'present' | 'partial' | 'missing' | string
  message?: string
}

export interface FrontpageCoverageReport {
  scene: FrontpageReportScene | string
  status: 'complete' | 'partial' | string
  total: number
  present: number
  partial: number
  missing: number
  text_extraction?: {
    total?: number
    present?: number
    success?: number
    missing?: number
    rate?: number
  }
  settlement_from_frontpage?: {
    total?: number
    present?: number
    success?: number
    missing?: number
    generated?: boolean
  }
  fields: FrontpageCoverageField[]
  warnings: string[]
}

export interface GenerateReportDraftResponse {
  success: boolean
  data?: {
    scene: FrontpageReportScene | string
    frontpage: FrontPageDraft
    settlement?: Record<string, unknown> | null
    coverage?: FrontpageCoverageReport
    warnings?: string[]
  }
  message?: string
  error?: string
}

export interface FrontpageExtractionSettings {
  sql_prefill_enabled: boolean
  llm_backfill_enabled: boolean
  allow_force_llm_regenerate: boolean
  include_demo_records: boolean
  auto_hide_demo_when_real_data: boolean
  demo_hide_threshold: number
  stream_progress_enabled: boolean
  default_preview_tab: 'fields' | 'preview'
}

export interface FrontpageExtractionSettingsResponse {
  settings: FrontpageExtractionSettings
  source: 'default' | 'file' | string
}

export interface FrontpageExtractionSettingsUpdate {
  sql_prefill_enabled?: boolean
  llm_backfill_enabled?: boolean
  allow_force_llm_regenerate?: boolean
  include_demo_records?: boolean
  auto_hide_demo_when_real_data?: boolean
  demo_hide_threshold?: number
  stream_progress_enabled?: boolean
  default_preview_tab?: 'fields' | 'preview'
}

export const frontpageApi = {
  /**
   * 自动生成病案首页草稿
   */
  async autoGenerateDraft(request: AutoGenerateRequest): Promise<AutoGenerateResponse> {
    const response = await http.post('/api/v1/frontpage/auto-generate-draft', request, {
      timeout: FRONTPAGE_AUTO_GENERATE_TIMEOUT_MS,
    })
    return response.data
  },

  /**
   * 生成病案首页/医保结算清单联合草稿
   */
  async generateReportDraft(
    request: GenerateReportDraftRequest,
  ): Promise<GenerateReportDraftResponse> {
    const response = await http.post('/api/v1/frontpage/generate-report-draft', request, {
      timeout: FRONTPAGE_AUTO_GENERATE_TIMEOUT_MS,
    })
    return response.data
  },

  /**
   * F13: 医疗画像分析
   */
  async analyzeProfile(request: ProfileAnalyzeRequest): Promise<ProfileAnalyzeResponse> {
    const response = await http.post('/api/v1/frontpage/profile/analyze', request)
    return response.data
  },

  /**
   * 读取首页抽取设置
   */
  async getExtractionSettings(): Promise<FrontpageExtractionSettingsResponse> {
    const response = await http.get('/api/v1/frontpage/settings')
    return unwrapApiEnvelope<FrontpageExtractionSettingsResponse>(response.data)
  },

  /**
   * 更新首页抽取设置（部分更新）
   */
  async updateExtractionSettings(
    update: FrontpageExtractionSettingsUpdate,
  ): Promise<FrontpageExtractionSettingsResponse> {
    const response = await http.put('/api/v1/frontpage/settings', update)
    return unwrapApiEnvelope<FrontpageExtractionSettingsResponse>(response.data)
  },

  /**
   * 重置首页抽取设置
   */
  async resetExtractionSettings(): Promise<FrontpageExtractionSettingsResponse> {
    const response = await http.post('/api/v1/frontpage/settings/reset')
    return unwrapApiEnvelope<FrontpageExtractionSettingsResponse>(response.data)
  },
}

export default frontpageApi
