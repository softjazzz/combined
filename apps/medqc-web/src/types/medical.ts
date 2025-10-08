/**
 * 医疗相关类型定义
 */

// 数据类型定义
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
  content?: string // 原始全文，便于前端切片展示
}

export interface ExtractedDocument {
  id: string
  category?: string      // 一级分类代码
  type: DocumentType     // 二级分类（保持向后兼容）
  title: string
  content: string // AI生成的摘要
  confidence: number
  extractedAt: Date
  classificationMethod?: 'llm_provided' | 'enhanced_classifier' | 'manual'
  // 新增：位置信息
  position?: {
    startMarker: string    // 文书开始的标识文本
    endMarker: string      // 文书结束的标识文本
    startIndex?: number    // 在原文中的起始位置（可选，由系统计算）
    endIndex?: number      // 在原文中的结束位置（可选，由系统计算）
    fullContent?: string   // 系统提取的完整原文（可选，由系统填充）
  }
}

// 阶段一：结构化索引返回的段落元数据（简化版）
export interface IndexEntry {
  id?: number
  title: string
  timestamp: string | null
  type_code?: string
  start_snippet?: string
  end_snippet?: string
  start_line_hint?: number
  end_line_hint?: number
  summary?: string
  confidence?: number
}

// 六个标准医疗文书类别（与数据库枚举对应）
export enum DocumentCategory {
  PROGRESS_NOTE = 'progress_note',            // 病程记录
  ADMISSION_RECORD = 'admission_record',      // 入院记录
  DISCHARGE_RECORD = 'discharge_record',      // 出院记录
  OPERATION_RECORD = 'operation_record',      // 手术相关记录
  EXAMINATION_REPORT = 'examination_report',  // 辅助检查
  CONSENT_FORM = 'consent_form'               // 知情同意书
}

// 文书类别显示配置
export const DOCUMENT_CATEGORY_CONFIG = {
  [DocumentCategory.PROGRESS_NOTE]: {
    label: '病程记录',
    description: '住院期间的病情变化、治疗过程、医嘱执行等动态记录',
    color: '#1890ff',
    icon: 'FileTextOutlined',
    sortOrder: 2
  },
  [DocumentCategory.ADMISSION_RECORD]: {
    label: '入院记录',
    description: '患者入院时的基本信息、主诉、现病史、既往史、体格检查等记录',
    color: '#52c41a',
    icon: 'LoginOutlined',
    sortOrder: 1
  },
  [DocumentCategory.DISCHARGE_RECORD]: {
    label: '出院记录',
    description: '患者出院时的诊疗总结、出院诊断、治疗效果等记录',
    color: '#faad14',
    icon: 'LogoutOutlined',
    sortOrder: 3
  },
  [DocumentCategory.OPERATION_RECORD]: {
    label: '手术相关记录',
    description: '手术记录、麻醉记录、术前讨论、术后总结等手术相关文书',
    color: '#f5222d',
    icon: 'MedicineBoxOutlined',
    sortOrder: 4
  },
  [DocumentCategory.EXAMINATION_REPORT]: {
    label: '辅助检查',
    description: '影像学检查、实验室检查、病理检查等辅助检查报告',
    color: '#722ed1',
    icon: 'ExperimentOutlined',
    sortOrder: 5
  },
  [DocumentCategory.CONSENT_FORM]: {
    label: '知情同意书',
    description: '各类医疗操作的知情同意书、风险告知书等',
    color: '#13c2c2',
    icon: 'SafetyCertificateOutlined',
    sortOrder: 6
  }
} as const

// 二级文书类型（更新为新的分类体系）
export enum DocumentType {
  // 入院记录类
  ADMISSION_RECORD = 'admission_record',                    // 入院记录
  ADMISSION_DIAGNOSIS = 'admission_diagnosis',              // 入院诊断

  // 病程记录类
  FIRST_PROGRESS_NOTE = 'first_progress_note',              // 首次病程记录
  DAILY_PROGRESS_NOTE = 'daily_progress_note',              // 日常病程记录
  ATTENDING_PROGRESS = 'attending_progress',                // 上级医师查房记录
  CONSULTATION_RECORD = 'consultation_record',              // 疑难病例讨论记录
  HANDOVER_RECORD = 'handover_record',                      // 交接班记录
  TRANSFER_RECORD = 'transfer_record',                      // 转科记录
  STAGE_SUMMARY = 'stage_summary',                          // 阶段小结

  // 手术记录类
  PREOPERATIVE_SUMMARY = 'preoperative_summary',           // 术前小结
  PREOPERATIVE_DISCUSSION = 'preoperative_discussion',     // 术前讨论
  OPERATION_RECORD = 'operation_record',                    // 手术记录
  POSTOPERATIVE_FIRST_NOTE = 'postoperative_first_note',   // 术后首次病程记录
  ANESTHESIA_RECORD = 'anesthesia_record',                 // 麻醉记录

  // 护理文书类
  NURSING_RECORD = 'nursing_record',                        // 护理记录单
  TEMPERATURE_CHART = 'temperature_chart',                  // 体温单
  NURSING_PLAN = 'nursing_plan',                           // 护理计划单
  NURSING_ASSESSMENT = 'nursing_assessment',               // 护理评估单

  // 出院记录类
  DISCHARGE_RECORD = 'discharge_record',                    // 出院记录
  DISCHARGE_SUMMARY = 'discharge_summary',                 // 出院小结
  DEATH_RECORD = 'death_record',                           // 死亡记录

  // 检查报告类
  IMAGING_EXAMINATION = 'imaging_examination',              // 影像学检查
  LABORATORY_TEST = 'laboratory_test',                     // 实验室检查
  PATHOLOGY_EXAMINATION = 'pathology_examination',         // 病理检查
  SPECIAL_EXAMINATION = 'special_examination',             // 特殊检查

  // 医嘱记录类
  LONG_TERM_ORDER = 'long_term_order',                     // 长期医嘱
  TEMPORARY_ORDER = 'temporary_order',                     // 临时医嘱
  ORDER_EXECUTION = 'order_execution'                      // 医嘱执行记录
}

export interface ParseOptions {
  enableBatchProcessing?: boolean
  confidenceThreshold?: number
  extractPatientInfo?: boolean
  extractDiagnosisInfo?: boolean
  extractSurgeryInfo?: boolean
  classifyDocuments?: boolean
}

export interface ParseResult {
  success: boolean
  data?: ExtractedMedicalData
  error?: string
  processingTime?: number
  tokensUsed?: number
}

export interface BatchParseResult {
  success: boolean
  results: ParseResult[]
  totalProcessed: number
  successCount: number
  failureCount: number
}

// LLM配置接口
export interface LLMConfig {
  apiEndpoint?: string
  apiKey?: string
  model?: string
  pointerMode?: boolean
  summaryMaxLength?: number
}

// 文档分类结果
export interface ClassificationResult {
  type: DocumentType
  confidence: number
  title?: string
}

// API响应接口
export interface LLMResponse {
  success: boolean
  data?: any
  error?: string
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

// 新增：文书分类相关接口
export interface DocumentCategoryInfo {
  id: string
  category_code: string
  category_name: string
  description?: string
  sort_order: number
  is_active: boolean
}

export interface DocumentTypeInfo {
  id: string
  category_id: string
  type_code: string
  type_name: string
  description?: string
  sort_order: number
  is_active: boolean
  required_sections: string[]
  validation_rules: Record<string, unknown>
}

export interface MedicalDocumentInfo {
  id: string
  record_id: string
  category_id: string
  type_id: string
  title: string
  content: string
  summary?: string
  ai_classified: boolean
  classification_confidence: number
  manual_verified: boolean
  position_info: {
    start_marker?: string
    end_marker?: string
    start_index?: number
    end_index?: number
    full_content?: string
  }
  sort_order: number
  status: 'active' | 'archived' | 'deleted'
  qc_status: 'pending' | 'passed' | 'failed' | 'reviewing'
  qc_score?: number
  qc_issues: QCIssue[]
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface QCIssue {
  category: string
  description: string
  severity: 'critical' | 'major' | 'minor'
  suggestion: string
  evidence_text?: string
  evidence_location?: Record<string, unknown>
}

export interface QCTemplate {
  id: string
  template_name: string
  template_code: string
  description?: string
  applicable_categories: string[]
  applicable_document_types: string[]
  template_config: Record<string, unknown>
  prompt_template: string
  scoring_rules: Record<string, unknown>
  is_active: boolean
  version: string
}

export interface DocumentQCResult {
  id: string
  document_id: string
  template_id?: string
  result_status: 'passed' | 'failed' | 'warning' | 'error'
  score: number
  max_score: number
  confidence_score: number
  issue_category?: string
  issue_description?: string
  evidence_text?: string
  evidence_location?: Record<string, unknown>
  suggestions: string[]
  ai_reasoning?: string
  ai_model_used?: string
  analysis_time_ms?: number
  manual_review_status: 'pending' | 'confirmed' | 'disputed' | 'corrected'
  created_at: string
}
