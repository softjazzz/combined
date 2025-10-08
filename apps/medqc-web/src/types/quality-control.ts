// 质控点相关类型定义
import { DocumentCategory } from './medical'

// 文书类别配置接口
export interface DocumentCategoryConfig {
  category_code: DocumentCategory
  category_name: string
  category_description: string
  sort_order: number
  is_active: boolean
  default_weight: number
  required_sections: string[]
  optional_sections: string[]
  created_at: string
  updated_at: string
}

// 增强的质控规则接口（包含文书类别信息）
export interface EnhancedQCRule {
  id: string
  rule_code: string
  name: string
  description: string
  category: string
  subcategory?: string
  rule_type: 'logical' | 'semantic' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  document_categories: DocumentCategory[]
  primary_document_category: DocumentCategory
  target_sections: string[]
  applicable_record_types: string[]
  applicable_departments?: string[]
  check_logic: Record<string, any>
  scoring_config: Record<string, any>
  prompt_template?: string
  examples: any[]
  is_active: boolean
  execution_order: number
  estimated_tokens: number
  timeout_seconds: number
  version: string
  created_by: string
  created_at: string
  updated_at: string
}

// 质控规则筛选参数
export interface QCRuleFilterParams {
  keyword?: string
  category?: string
  document_category?: DocumentCategory
  rule_type?: 'logical' | 'semantic' | 'hybrid'
  severity?: 'critical' | 'major' | 'minor'
  is_active?: boolean
  page?: number
  pageSize?: number
}

export interface QualityControlPoint {
  id: string
  name: string
  source: string
  category: string
  type: string
  coreSystem?: string
  document: string
  onlineDate?: string
  lastOperator?: string
  enabled?: boolean
  status: 'online' | 'offline' | 'draft'
  lastOperationDate?: string
  managementSystem?: string
  coreSystemCategory?: string
  infoCategory?: string
  significance?: string
  errorExample?: string
  createTime?: string
  updateTime?: string
}

export interface QualityControlPointForm {
  name: string
  category: string
  type: string
  document: string
  coreSystemCategory?: string
  infoCategory?: string
  managementSystem?: string
  source?: string
  significance?: string
  errorExample?: string
}

export interface QualityControlRule {
  id: string
  pointId: string
  conditions: QualityControlCondition[]
  logicOperator: 'AND' | 'OR'
  createTime: string
  updateTime: string
}

export interface QualityControlCondition {
  id: string
  type: 'normal' | 'time' | 'group'
  field: string
  operator: string
  value: string | number
  timeUnit?: 'hour' | 'day' | 'month' | 'year'
  constraints?: QualityControlConstraint[]
}

export interface QualityControlConstraint {
  id: string
  field: string
  operator: string
  value: string | number
}

export interface QualityControlTestCase {
  id: string
  name: string
  description?: string
  medicalRecordId: string
  expectedResult: boolean
  actualResult?: boolean
  testStatus: 'pending' | 'passed' | 'failed'
  createTime: string
  updateTime?: string
}

export interface QualityControlSearchParams {
  keyword?: string
  searchType?: 'id' | 'name'
  category?: string
  type?: string
  status?: string
  enabled?: boolean
  page?: number
  pageSize?: number
}

export interface QualityControlBatchOperation {
  action: 'enable' | 'disable' | 'online' | 'offline' | 'delete'
  pointIds: string[]
}

// API 响应类型
export interface QualityControlPointListResponse {
  data: QualityControlPoint[]
  total: number
  page: number
  pageSize: number
}

export interface QualityControlPointDetailResponse {
  data: QualityControlPoint
}

// 表格列配置类型
export interface TableColumn {
  title: string
  dataIndex: string
  key: string
  width?: number
  sorter?: boolean
  fixed?: 'left' | 'right'
}

// 分页配置类型
export interface PaginationConfig {
  current: number
  pageSize: number
  total: number
  showSizeChanger: boolean
  showQuickJumper: boolean
  showTotal: (total: number, range: [number, number]) => string
  pageSizeOptions: string[]
}

// ==================== LLM质控演示相关类型定义 ====================

// 文书信息（测试对象的第二级）
export interface RecordDocumentInfo {
  id: string
  title?: string
  type?: string
  created_at?: string
}

// 质控通知模型
export interface QCNotification {
  id: string
  type: 'warning' | 'error' | 'info' | 'success'
  title: string
  message: string
  qcResult: QCResult
  timestamp: Date
  isRead: boolean
  canAppeal: boolean
  appealId?: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  location?: string
  suggestion?: string
  status?: 'pending' | 'processing' | 'resolved' | 'appealed' | string
  recordInfo?: {
    patientName?: string
    recordNumber?: string
    department?: string
    doctor?: string
    admissionDate?: string
    status?: string
  }
}

// 申诉理由枚举
export enum AppealReason {
  RULE_MISAPPLICATION = 'rule_misapplication',
  DATA_INACCURACY = 'data_inaccuracy',
  CONTEXT_MISSING = 'context_missing',
  TECHNICAL_ERROR = 'technical_error',
  OTHER = 'other'
}

// 申诉模型
export interface Appeal {
  id: string
  qcResultId: string
  notificationId: string
  reason: AppealReason
  reasonText: string
  description: string
  attachments: File[]
  status: 'pending' | 'reviewing' | 'approved' | 'rejected'
  submittedAt: Date
  reviewedAt?: Date
  reviewerComment?: string
  submittedBy: string
}

// 演示步骤模型
export interface DemoStep {
  id: string
  name: string
  description: string
  duration: number
  component: string
  data: any
  status: 'pending' | 'running' | 'completed' | 'error'
}

// 质控结果模型（扩展现有）
export interface QCResult {
  id: string
  recordId: string
  overallScore: number
  overallGrade: string
  analysisDate: string
  issues: QCIssue[]
  suggestions: QCSuggestion[]
  ruleResults: QCRuleResult[]
  analysisSteps?: AnalysisStep[]
  metadata?: QCResultMetadata
}

// 质控问题模型（扩展现有）
export interface QCIssue {
  id: string
  ruleName: string
  ruleId: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: string
  location: string
  suggestion: string
  evidence?: string
  canAppeal: boolean
}

// 质控建议模型
export interface QCSuggestion {
  id: string
  category: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high'
  actionRequired: boolean
}

// 质控规则结果模型
export interface QCRuleResult {
  ruleId: string
  ruleName: string
  passed: boolean
  score: number
  maxScore: number
  details: string
  executionTime: number
  confidence: number
}

// 分析步骤模型
export interface AnalysisStep {
  id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'error'
  startTime?: Date
  endTime?: Date
  result?: any
  error?: string
}

// 质控结果元数据
export interface QCResultMetadata {
  analysisVersion: string
  modelVersion: string
  processingTime: number
  rulesApplied: number
  totalTokens?: number
  confidence: number
  documents?: Array<{ id: string; title?: string; type?: string }>
  record?: Record<string, any>
  engine?: string
  analysisId?: string
  scoreBaseline?: Record<string, any>
}

// 演示配置模型
export interface DemoConfig {
  selectedRules: string[]
  testRecordId: string
  simulateRealTime: boolean
  showAnalysisSteps: boolean
  enableNotifications: boolean
  autoAdvance: boolean
  stepDelay: number
}

// 演示状态模型
export interface DemoState {
  // 三步流程：测试对象 -> 规则配置 -> 运行与结果
  currentStep: 'target' | 'rules' | 'run'
  isRunning: boolean
  isPaused: boolean
  progress: number
  selectedRules: QualityControlRule[]
  testRecord: any
  // 单/多选文书：向后兼容
  selectedDocument?: RecordDocumentInfo | RecordDocumentInfo[] | null
  analysisResult: QCResult | null
  notifications: QCNotification[]
  activeNotification: QCNotification | null
  appeals: Appeal[]
  currentAppeal: Appeal | null
  error: string | null
}
