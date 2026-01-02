/**
 * DRG/DIP 模块 TypeScript 类型定义
 * 与后端 FastAPI Pydantic 模型对应
 */

/** 性别类型 */
export type Gender = 'M' | 'F'

/** 编码状态 */
export type CodingStatus = 'draft' | 'completed' | 'reviewed'

/** 审核状态 */
export type ReviewStatus = 'pending' | 'approved' | 'rejected'

/** 编码类别 */
export type CodeCategory = 'diagnosis' | 'procedure'

/** 严重程度 */
export type Severity = 'info' | 'warning' | 'error'

/** 建议类型 */
export type SuggestionType = 'missing_diagnosis' | 'procedure_missing' | 'complication_marking' | 'logic_conflict'

/** 建议状态 */
export type SuggestionStatus = 'pending' | 'accepted' | 'rejected'

/** 预警类型 */
export type AlertType = 'cost_overrun' | 'los_long' | 'coding_abnormal' | 'profit_loss'

/** 预警级别 */
export type AlertLevel = 'info' | 'warning' | 'critical'

/** 预警状态 */
export type AlertStatus = 'pending' | 'acknowledged' | 'resolved'

/** 风险等级 */
export type RiskLevel = 'low' | 'medium' | 'high'

/** ICD 编码 */
export interface ICDCode {
  code: string
  name: string
  category?: string
  notes?: string
}

/** 诊断项 */
export interface DiagnosisItem {
  code: string
  name: string
  sequence?: number
  is_complication?: boolean
}

/** 手术操作项 */
export interface ProcedureItem {
  code: string
  name: string
  sequence?: number
  procedure_date?: string
}

/** 病案首页基础信息 */
export interface CaseFrontPage {
  front_page_id: number
  admission_id: string
  patient_id: string
  patient_name: string
  patient_age: number
  patient_gender: Gender

  // 主诊断
  primary_diagnosis_code: string
  primary_diagnosis_name: string

  // 主手术操作
  main_procedure_code?: string
  main_procedure_name?: string
  main_procedure_date?: string

  // 其他信息
  admission_route?: string
  discharge_status?: string
  total_hospital_days?: number
  total_cost?: number

  // 编码工作追踪
  coder_id?: string
  coding_started_at?: string
  coding_completed_at?: string
  coding_status: CodingStatus

  // 审核追踪
  reviewer_id?: string
  reviewed_at?: string
  review_status: ReviewStatus

  // 审计字段
  created_at: string
  updated_at: string

  // 关联数据
  secondary_diagnoses?: DiagnosisItem[]
  procedures?: ProcedureItem[]
}

/** ICD 编码推荐 */
export interface ICDSuggestion {
  code: string
  name: string
  confidence: number
  note?: string
}

/** 编码校验警告 */
export interface ValidationWarning {
  type: SuggestionType
  message: string
  evidence?: string
  severity: Severity
}

/** 编码校验结果 */
export interface ValidationResult {
  is_valid: boolean
  warnings: ValidationWarning[]
  conflicts: string[]
}

/** DRG 分组结果 */
export interface DRGGroupingResult {
  adrg_code: string
  adrg_name: string
  drg_code: string
  drg_name: string
  weight: number
  baseline_payment: number
  expected_los?: {
    min: number
    max: number
  }
  confidence?: number
  risk_level?: RiskLevel
  grouping_logic?: string
}

/** DIP 分组结果 */
export interface DIPGroupingResult {
  dip_code: string
  dip_name: string
  dip_type: string
  diag_code?: string
  proc_code?: string
  grouping_path?: string
  // 为了兼容 DRGResultCard，我们需要映射一些字段或在组件中处理
  weight?: number // DIP might have points, map to weight
  baseline_payment?: number
}

/** DRG 分组历史记录 */
export interface DRGGroupingHistoryItem {
  grouping_id: number
  drg_code: string
  drg_name: string
  weight: number
  baseline_payment: number
  actual_cost?: number
  profit_margin?: number
  version: number
  is_latest: boolean
  grouped_at: string
}

/** 编码建议 */
export interface CodingSuggestionItem {
  suggestion_id: number
  admission_id: string
  suggestion_type: SuggestionType
  diagnosis_code?: string
  diagnosis_name?: string
  message: string
  evidence?: string
  severity: Severity
  status: SuggestionStatus
  created_at: string
}

/** DRG 预警 */
export interface DRGAlertItem {
  alert_id: number
  admission_id: string
  alert_type: AlertType
  alert_level: AlertLevel
  message: string
  metric_value?: number
  threshold_value?: number
  status: AlertStatus
  triggered_at: string
}

/** API 请求类型 */

export interface CodingSuggestRequest {
  diagnosis_name: string
  context?: string
  category: CodeCategory
}

export interface CodingValidateRequest {
  admission_id: string
  primary_diagnosis: DiagnosisItem
  secondary_diagnoses: DiagnosisItem[]
  procedures: ProcedureItem[]
}

export interface DRGPredictRequest {
  admission_id: string
  region?: string
}

export interface DIPPredictRequest {
  admission_id?: string
  city_name: string
  pdx_code: string
  adx_code?: string
  proc_code?: string
  patient_gender: string
  patient_age: number
  los: number
  total_fee: number
}

export interface HandleSuggestionRequest {
  suggestion_id: number
  action: 'accept' | 'reject'
  handled_by: string
}

/** API 响应类型 */

export interface CodingSuggestResponse {
  candidates: ICDSuggestion[]
  total: number
}

export interface ICDSearchResponse {
  results: ICDCode[]
  total: number
}

export interface DRGPredictionResponse {
  data: DRGGroupingResult
  message: string
}

export interface DRGGroupingHistoryResponse {
  history: DRGGroupingHistoryItem[]
  total: number
}

export interface CodingSuggestionsResponse {
  suggestions: CodingSuggestionItem[]
  total: number
}

export interface DRGAlertsResponse {
  alerts: DRGAlertItem[]
  total: number
}

export interface HandleSuggestionResponse {
  success: boolean
  message: string
}
export interface DIPPredictionResponse {
  data: DIPGroupingResult
  message: string
}
