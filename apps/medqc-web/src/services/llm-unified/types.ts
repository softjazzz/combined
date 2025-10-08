/**
 * 统一 LLM 服务类型定义
 * 整合了所有 LLM 服务的通用类型
 */

// ==================== 基础类型 ====================

export interface LLMConfig {
  provider: 'openai' | 'deepseek' | 'aliyun'
  apiKey: string
  baseURL: string
  model: string
  temperature?: number
  maxTokens?: number
  timeout?: number
}

export interface CallOptions {
  temperature?: number
  maxTokens?: number
  topP?: number
  frequencyPenalty?: number
  presencePenalty?: number
  stream?: boolean
}

export interface LLMResponse {
  content: string
  usage?: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
  }
  model?: string
  finishReason?: string
}

// ==================== 医疗数据类型 ====================

export interface ExtractedMedicalData {
  recordNumber: string
  patientName: string
  patientAge?: number
  patientGender?: string
  department: string
  primaryDiagnosis: string
  secondaryDiagnosis?: string[]
  majorSurgery: string
  documents: ExtractedDocument[]
  confidence: number
  content?: string
}

export interface ExtractedDocument {
  id: string
  type: DocumentType
  title: string
  content: string
  confidence: number
  extractedAt: Date
  position?: DocumentPosition
}

export interface DocumentPosition {
  startMarker: string
  endMarker: string
  startIndex?: number
  endIndex?: number
  fullContent?: string
}

// ==================== 文档类型枚举 ====================

export enum DocumentCategory {
  ADMISSION_RECORD = 'admission_record',
  PROGRESS_NOTE = 'progress_note',
  OPERATION_RECORD = 'operation_record',
  DISCHARGE_RECORD = 'discharge_record',
  EXAMINATION_REPORT = 'examination_report',
  CONSENT_FORM = 'consent_form'
}

export enum DocumentType {
  // 入院记录
  ADMISSION_RECORD = 'admission_record',
  ADMISSION_RECORD_24H_IN = 'admission_record_24h_in',
  ADMISSION_RECORD_24H_OUT = 'admission_record_24h_out',

  // 病程记录
  FIRST_PROGRESS_NOTE = 'first_progress_note',
  DAILY_PROGRESS_NOTE = 'daily_progress_note',
  ATTENDING_FIRST_PROGRESS = 'attending_first_progress',
  ATTENDING_PROGRESS = 'attending_progress',
  CONSULTATION_RECORD = 'consultation_record',
  HANDOVER_RECORD = 'handover_record',
  STAGE_SUMMARY = 'stage_summary',

  // 手术记录
  OPERATION_RECORD = 'operation_record',
  PREOPERATIVE_SUMMARY = 'preoperative_summary',

  // 出院记录
  DISCHARGE_RECORD = 'discharge_record',
  DEATH_RECORD = 'death_record',
  DEATH_CASE_DISCUSSION = 'death_case_discussion',

  // 辅助检查
  IMAGING_REPORT = 'imaging_report',
  LAB_REPORT = 'lab_report',
  OTHER_EXAMINATION = 'other_examination',

  // 知情同意书
  SURGERY_CONSENT = 'surgery_consent',
  ANESTHESIA_CONSENT = 'anesthesia_consent',
  BLOOD_TRANSFUSION_CONSENT = 'blood_transfusion_consent',
  SPECIAL_TREATMENT_CONSENT = 'special_treatment_consent',
  CRITICAL_ILLNESS_NOTICE = 'critical_illness_notice'
}

// ==================== 解析选项和结果 ====================

export interface ParseOptions {
  enableBatchProcessing?: boolean
  confidenceThreshold?: number
  extractPatientInfo?: boolean
  extractDiagnosis?: boolean
  extractSurgeryInfo?: boolean
  classifyDocuments?: boolean
  pointerMode?: boolean
  summaryMaxLength?: number
}

export interface ParseResult {
  success: boolean
  data?: ExtractedMedicalData
  error?: string
  processingTime: number
  tokensUsed?: number
}

export interface BatchParseResult {
  success: boolean
  results: ParseResult[]
  totalProcessed: number
  successCount: number
  failureCount: number
  totalProcessingTime: number
}

// ==================== 错误类型 ====================

export class LLMError extends Error {
  constructor(
    message: string,
    public code?: string,
    public details?: unknown
  ) {
    super(message)
    this.name = 'LLMError'
  }
}

export class LLMConfigError extends LLMError {
  constructor(message: string, details?: unknown) {
    super(message, 'CONFIG_ERROR', details)
    this.name = 'LLMConfigError'
  }
}

export class LLMAPIError extends LLMError {
  constructor(message: string, details?: unknown) {
    super(message, 'API_ERROR', details)
    this.name = 'LLMAPIError'
  }
}

export class LLMParseError extends LLMError {
  constructor(message: string, details?: unknown) {
    super(message, 'PARSE_ERROR', details)
    this.name = 'LLMParseError'
  }
}

