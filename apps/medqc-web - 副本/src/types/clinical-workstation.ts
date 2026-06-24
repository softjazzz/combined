/**
 * 临床质控演示平台 - 类型定义
 * Clinical Workstation Demo Types
 */

// ==================== 病例相关类型 ====================

/**
 * 文书类型枚举
 */
export enum DocumentType {
  ADMISSION = 'admission',                    // 入院记录
  INOUT_24H = 'inout_24h',                   // 24小时入出院记录
  FIRST_COURSE = 'first_course',             // 首次病程记录
  DAILY_COURSE = 'daily_course',             // 日常病程记录
  SURGERY_APPLY = 'surgery_apply',           // 手术申请单
  PRE_OP_DISCUSSION = 'pre_op_discussion',   // 术前讨论
  PRE_OP_SUMMARY = 'pre_op_summary',         // 术前小结
  SURGERY_RECORD = 'surgery_record',         // 手术记录
  SAFETY_CHECK = 'safety_check',             // 手术安全核查记录单
  ANESTHESIA = 'anesthesia',                 // 麻醉记录
  POST_OP_COURSE = 'post_op_course',         // 术后病程记录
  NURSING = 'nursing',                       // 护理记录
  CONSULTATION = 'consultation',             // 会诊记录
  DISCUSSION = 'discussion',                 // 疑难病例讨论记录
  ROUNDS = 'rounds',                         // 查房记录
  RESCUE = 'rescue',                         // 抢救记录
  DISCHARGE = 'discharge',                   // 出院记录
  OTHER = 'other'                            // 其他
}

/**
 * 文书类型显示名称映射
 */
export const DocumentTypeLabels: Record<DocumentType, string> = {
  [DocumentType.ADMISSION]: '入院记录',
  [DocumentType.INOUT_24H]: '24小时入出院记录',
  [DocumentType.FIRST_COURSE]: '首次病程记录',
  [DocumentType.DAILY_COURSE]: '日常病程记录',
  [DocumentType.SURGERY_APPLY]: '手术申请单',
  [DocumentType.PRE_OP_DISCUSSION]: '术前讨论',
  [DocumentType.PRE_OP_SUMMARY]: '术前小结',
  [DocumentType.SURGERY_RECORD]: '手术记录',
  [DocumentType.SAFETY_CHECK]: '手术安全核查记录单',
  [DocumentType.ANESTHESIA]: '麻醉记录',
  [DocumentType.POST_OP_COURSE]: '术后病程记录',
  [DocumentType.NURSING]: '护理记录',
  [DocumentType.CONSULTATION]: '会诊记录',
  [DocumentType.DISCUSSION]: '疑难病例讨论记录',
  [DocumentType.ROUNDS]: '查房记录',
  [DocumentType.RESCUE]: '抢救记录',
  [DocumentType.DISCHARGE]: '出院记录',
  [DocumentType.OTHER]: '其他'
}

/**
 * 文书分段内容
 */
export interface DocumentSection {
  sectionType: string         // complaint, present_illness, past_history等
  label: string               // 显示标签（如"主诉"、"现病史"）
  content: string             // 内容
  order?: number              // 显示顺序
}

/**
 * 文书模型
 */
export interface Document {
  documentId: string
  documentType: DocumentType
  title: string               // 文书标题
  recordTime: string          // 记录时间
  content: string             // 完整文书内容（用于质控分析）
  sections?: DocumentSection[] // 分段内容（用于展示）
  metadata?: {
    author?: string           // 作者/医生
    department?: string       // 科室
    visitType?: string        // 就诊类型
    patientId?: string        // 患者ID
    visitId?: string          // 就诊ID
    [key: string]: any        // 其他元数据
  }
}

/**
 * 病种复杂度
 */
export type CaseComplexity = 'low' | 'medium' | 'high'

/**
 * 病种复杂度显示名称映射
 */
export const CaseComplexityLabels: Record<CaseComplexity, string> = {
  low: '简单',
  medium: '中等',
  high: '复杂'
}

/**
 * 病例模型
 */
export interface Case {
  caseId: string
  caseName: string            // 病例名称（如"急性冠脉综合征典型病例"）

  patientInfo: {
    name: string              // 姓名（脱敏）
    gender: '男' | '女'
    age: number
    idNumber?: string         // 身份证号（脱敏）
  }

  visitInfo: {
    visitId: string
    department: string        // 科室（心内科、普外科、呼吸内科等）
    admissionDate: string     // 入院日期
    dischargeDate?: string    // 出院日期
    bedNumber?: string        // 床号
    admissionNumber?: string  // 住院号
  }

  diagnosisInfo: {
    diseaseType: string       // 病种标签（如"急性冠脉综合征"、"急性阑尾炎"等）
    complexity: CaseComplexity // 复杂度
    primaryDiagnosis?: string // 主要诊断
    otherDiagnoses?: string[] // 其他诊断
  }

  documents: Document[]       // 文书列表

  metadata: {
    isCustom: boolean         // 是否自定义病例
    createdAt: string         // 创建时间
    description?: string      // 病例描述
    tags?: string[]           // 标签
  }
}

// ==================== 质控相关类型 ====================

/**
 * 违规严重程度
 */
export type ViolationSeverity = 'critical' | 'major' | 'minor'

/**
 * 违规严重程度显示名称映射
 */
export const ViolationSeverityLabels: Record<ViolationSeverity, string> = {
  critical: '严重',
  major: '一般',
  minor: '轻微'
}

/**
 * 违规严重程度颜色映射
 */
export const ViolationSeverityColors: Record<ViolationSeverity, string> = {
  critical: 'red',
  major: 'orange',
  minor: 'yellow'
}

/**
 * 违规项模型
 */
export interface Violation {
  ruleId: string
  ruleName: string
  severity: ViolationSeverity
  description: string         // 问题描述
  evidence: string[]          // 证据片段
  location?: string           // 问题定位（如"入院记录·现病史段落"）
  suggestion?: string         // 改进建议
  score?: number              // 扣分
  confidence?: number         // 置信度（0-1）
}

/**
 * 质控规则集
 */
export enum QCRuleSet {
  DEFAULT = 'default',              // 默认规则集
  SICHUAN_146 = 'sichuan_146',     // 四川146条
  LX33 = 'lx33',                   // 泸县33条
  SEMANTIC = 'semantic'            // 语义规则
}

/**
 * 质控规则集显示名称映射
 */
export const QCRuleSetLabels: Record<QCRuleSet, string> = {
  [QCRuleSet.DEFAULT]: '默认规则集',
  [QCRuleSet.SICHUAN_146]: '四川146条',
  [QCRuleSet.LX33]: '泸县33条',
  [QCRuleSet.SEMANTIC]: '语义规则'
}

/**
 * 质控评估汇总
 */
export interface QCEvaluationSummary {
  totalRules: number
  compliantRules: number
  complianceRate: number      // 合规率（百分比）
  overallGrade: string        // 总体等级（A/B/C）
  criticalViolations: number  // 严重违规数
  majorViolations?: number    // 一般违规数
  minorViolations?: number    // 轻微违规数
  issuesFound?: number        // 发现的问题数
  notApplicable?: number      // 不适用规则数
}

/**
 * 质控性能指标
 */
export interface QCPerformanceMetrics {
  processingTime: number      // 处理时间（秒）
  tokenUsage: number          // Token使用量
  estimatedCost: number       // 预估成本（美元）
}

/**
 * 质控优化指标
 */
export interface QCOptimizationMetrics {
  tokenSavingsRate: number    // Token节省率（0-1）
  estimatedOriginalTokens?: number
  actualTokensSaved?: number
  costSavings?: number
}

/**
 * 质控结果模型
 */
export interface QCResult {
  documentId: string
  caseId: string
  ruleSet: QCRuleSet
  evaluationSummary: QCEvaluationSummary
  violations: Violation[]
  performanceMetrics: QCPerformanceMetrics
  optimizationMetrics?: QCOptimizationMetrics
  timestamp: string
  status: 'completed' | 'failed' | 'analyzing'
  mode?: string               // 评估模式（如 single_prompt）
  llmInfo?: {
    model?: string
    apiEndpoint?: string
  }
}

/**
 * 整病例质控结果
 */
export interface WholeCaseQCResult {
  caseId: string
  caseName: string
  ruleSet: QCRuleSet
  documentResults: {
    documentId: string
    documentTitle: string
    documentType: DocumentType
    summary: QCEvaluationSummary
    violationsCount: number
    status: 'completed' | 'failed' | 'analyzing'
  }[]
  overallSummary: {
    totalDocuments: number
    analyzedDocuments: number
    averageComplianceRate: number
    totalViolations: number
    overallGrade: string
  }
  timestamp: string
}

// ==================== 病案首页相关类型 ====================

/**
 * 病案首页基本信息
 */
export interface FrontPageBasicInfo {
  patientName: string
  gender: string
  genderText?: string
  birthDate?: string
  ageYears?: number
  nationality?: string
  ethnicity?: string
  maritalStatus?: string
  maritalStatusText?: string
  idNumber?: string
  occupation?: string
  currentAddress?: string
  contactName?: string
  contactRelation?: string
  contactPhone?: string
}

/**
 * 病案首页住院信息
 */
export interface FrontPageHospitalization {
  hospitalName?: string
  admissionTimesInHospital?: number
  medicalRecordNo?: string
  paymentMethod?: string
  paymentMethodText?: string
  admissionWay?: string
  admissionWayText?: string
  admissionDept?: string
  admissionWard?: string
  admissionDatetime?: string
  dischargeDept?: string
  dischargeWard?: string
  dischargeDatetime?: string
  actualHospitalDays?: number
}

/**
 * 病案首页诊断信息
 */
export interface FrontPageDiagnoses {
  edDiagnosisTexts: string[]
  dischargeMainDiagnosisText?: string
  dischargeOtherDiagnosesTexts: string[]
  edDiagnosisCodes?: string[]
  dischargeMainIcd?: string
  dischargeOtherIcds?: string[]
  admissionCondition?: string
}

/**
 * 病案首页手术及操作信息
 */
export interface FrontPageProcedures {
  mainProcedureText?: string
  mainProcedureDate?: string
  mainProcedureLevel?: string
  surgeonName?: string
  surgeonCode?: string
  assistant1Name?: string
  assistant1Code?: string
  assistant2Name?: string
  assistant2Code?: string
  anesthesiaMethod?: string
  anesthetistName?: string
  anesthetistCode?: string
  incisionHealingGrade?: string
  mainProcedureCode?: string
}

/**
 * 病案首页其他医疗信息
 */
export interface FrontPageOtherMedicalInfo {
  pathologyText?: string
  pathologyIcd?: string
  pathologyNo?: string
  drugAllergyFlag?: string
  drugAllergyFlagText?: string
  drugAllergyDrugs: string[]
  aboBloodType?: string
  rhBloodType?: string
  rhBloodTypeText?: string
  ventilationHours?: number
  icuType?: string
  icuEnterTime?: string
  icuLeaveTime?: string
  icuTransferStatus?: string
  [key: string]: any
}

/**
 * 病案首页人员信息
 */
export interface FrontPageStaff {
  deptDirector?: string
  chiefPhysician?: string
  attendingPhysician?: string
  residentPhysician?: string
  responsibleNurse?: string
  coder?: string
}

/**
 * 病案首页费用信息
 */
export interface FrontPageCosts {
  totalCost?: number
  selfPaid?: number
  categories?: Record<string, number>
}

/**
 * 病案首页草稿模型
 */
export interface FrontPageDraft {
  basicInfo: FrontPageBasicInfo
  hospitalization: FrontPageHospitalization
  diagnoses: FrontPageDiagnoses
  procedures: FrontPageProcedures
  otherMedicalInfo: FrontPageOtherMedicalInfo
  staff: FrontPageStaff
  costs: FrontPageCosts
  evidence?: Record<string, any>         // 证据结构（含 main_diagnosis_llm / coding_audit_llm）
  confidence?: Record<string, number>    // 字段级置信度 0-1
}

// ==================== 筛选和搜索相关类型 ====================

/**
 * 病例筛选条件
 */
export interface CaseFilter {
  department?: string         // 科室
  diseaseType?: string        // 病种
  complexity?: CaseComplexity // 复杂度
  isCustom?: boolean          // 是否自定义
  keyword?: string            // 关键字搜索
}

/**
 * 科室列表
 */
export const DepartmentList = [
  '全部',
  '心内科',
  '普外科',
  '呼吸内科',
  'ICU',
  '神经内科',
  '消化内科',
  '骨科',
  '妇产科',
  '儿科'
]

// ==================== Store State 相关类型 ====================

/**
 * 临床工作站 Store State
 */
export interface ClinicalWorkstationState {
  cases: Case[]                              // 所有病例（预置+自定义）
  currentCaseId: string | null               // 当前选中病例ID
  currentDocumentId: string | null           // 当前选中文书ID
  qcResults: Map<string, QCResult>           // 质控结果缓存（key: documentId）
  wholeCaseQCResult: WholeCaseQCResult | null // 整病例质控结果
  frontpageDraft: FrontPageDraft | null      // 病案首页草稿
  isQCAnalyzing: boolean                     // 是否正在质控分析
  isFrontpageGenerating: boolean             // 是否正在生成病案首页
  selectedRuleSet: QCRuleSet                 // 选中的规则集
  filter: CaseFilter                         // 筛选条件
  activeCdssTab: 'qc' | 'frontpage'          // 右侧CDSS面板激活的Tab
}

// ==================== API 请求/响应类型 ====================

/**
 * 四川质控API请求
 */
export interface SichuanQCEvaluateRequest {
  document_id: string
  document_content: string
  document_type: string
  persist?: boolean
  prompt_mode?: string
  rule_ids?: string[]
}

/**
 * 四川质控API响应
 */
export interface SichuanQCEvaluateResponse {
  success: boolean
  data?: {
    document_id: string
    evaluation_summary: {
      compliance_rate: number
      issues_found?: number
      total_rules?: number
      compliant_rules?: number
      not_applicable?: number
      overall_grade?: string
      critical_violations?: number
      model?: string
    }
    evaluation_results?: any[]
    performance_metrics?: {
      processing_time: number
      token_usage: number
      estimated_cost: number
    }
    optimization_metrics?: {
      token_savings_rate: number
      cost_savings: number
    }
    prompt_mode?: string
    llm_info?: {
      model?: string
      api_endpoint?: string
    }
  }
  message?: string
  status?: number
}

/**
 * 病案首页生成API请求
 */
export interface FrontPageGenerateRequest {
  visit_id?: string
  documents?: Array<{
    type: string
    content: string
    meta?: Record<string, any>
  }>
}

/**
 * 病案首页生成API响应
 */
export interface FrontPageGenerateResponse {
  success: boolean
  data?: {
    frontpage: FrontPageDraft
  }
  message?: string
  trace_id?: string
}
