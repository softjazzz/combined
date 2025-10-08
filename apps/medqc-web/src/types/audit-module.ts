// 人工审核模块类型定义
// 基于LLM集成质控系统的审核功能扩展

import type { EnhancedQCRule, QCRuleResult } from './enhanced-qc-rule'

// 基础枚举类型
export type AuditTaskType = 'routine' | 'special' | 'spot_check' | 'complaint_driven'
export type AuditLevel = 'department' | 'hospital' | 'expert'
export type AuditStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled'
export type TaskItemStatus = 'pending' | 'in_review' | 'completed' | 'appealed' | 'cancelled'
export type AuditResultStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'modified'
export type RiskLevel = 'A' | 'B' | 'C' // A:高风险 B:中风险 C:低风险
export type DefectSeverity = 'critical' | 'major' | 'minor'

// 缺陷状态枚举
export type DefectStatus = 
  | 'identified'              // 已识别
  | 'rectification_required'  // 需要整改
  | 'rectification_submitted' // 已提交整改
  | 'rectification_approved'  // 整改通过
  | 'rectification_rejected'  // 整改被拒
  | 'appealed'               // 已申诉
  | 'appeal_approved'        // 申诉通过
  | 'appeal_rejected'        // 申诉被拒
  | 'closed'                 // 已关闭
  | 'dismissed'              // 已忽略

// 消息类型枚举
export type MessageType = 
  | 'qc_completed'              // 质控完成通知
  | 'rectification_required'    // 缺陷整改要求
  | 'audit_result'             // 审核结果通知
  | 'appeal_result'            // 申诉结果通知
  | 'deadline_reminder'        // 截止时间提醒
  | 'system_announcement'      // 系统公告
  | 'rectification_submitted'  // 整改提交通知
  | 'appeal_submitted'         // 申诉提交通知
  | 'task_assigned'            // 任务分配通知
  | 'task_overdue'             // 任务超期提醒
  | 'batch_completed'          // 批量操作完成
  | 'expert_consultation'      // 专家会诊请求

export type MessagePriority = 'low' | 'normal' | 'high' | 'urgent'
export type MessageStatus = 'pending' | 'sent' | 'delivered' | 'read' | 'processed' | 'expired'
export type RecipientType = 'clinician' | 'reviewer' | 'admin'

// 审核任务相关接口
export interface QCAuditTask {
  id: string
  task_code: string
  task_name: string
  task_type: AuditTaskType
  audit_level: AuditLevel
  audit_scope: AuditScope
  sampling_config: SamplingConfig
  status: AuditStatus
  progress_percentage: number
  
  // 时间管理
  planned_start_date: string
  planned_end_date: string
  actual_start_date?: string
  actual_end_date?: string
  
  // 分配信息
  created_by: string
  assigned_reviewers: AssignedReviewer[]
  
  // 统计信息
  total_records: number
  completed_records: number
  defect_rate?: number
  
  // 元数据
  description?: string
  priority: number
  
  created_at: string
  updated_at: string
}

export interface AuditScope {
  departments: string[]
  document_types: string[]
  patient_types?: string[]
  date_range?: {
    start: string
    end: string
  }
  include_discharged?: boolean
  exclude_patterns?: string[]
}

export interface SamplingConfig {
  sampling_method: 'random' | 'stratified' | 'systematic' | 'risk_based'
  total_sample_size?: number
  sampling_ratio?: number // 百分比
  stratification_rules?: StratificationRule[]
  risk_based_weights?: RiskBasedWeights
  exclusion_criteria?: string[]
}

export interface StratificationRule {
  stratum_name: string
  criteria: Record<string, unknown>
  sample_ratio: number
  min_sample_size?: number
  max_sample_size?: number
}

export interface RiskBasedWeights {
  risk_A_weight: number // 高风险权重
  risk_B_weight: number // 中风险权重
  risk_C_weight: number // 低风险权重
}

export interface AssignedReviewer {
  user_id: string
  user_name: string
  role: string
  assigned_count: number
  completed_count: number
  assigned_at: string
}

// 审核任务明细
export interface QCAuditTaskItem {
  id: string
  task_id: string
  patient_id: string
  medical_record_id: string
  
  // 病历基本信息
  patient_name: string
  admission_date: string
  discharge_date?: string
  department_id: string
  department_name: string
  
  // 风险等级和复杂度
  risk_level: RiskLevel
  complexity_score: number
  
  // 审核状态
  audit_status: TaskItemStatus
  assigned_reviewer_id?: string
  
  // 审核结果汇总
  overall_score?: number
  defect_count: number
  has_critical_defects: boolean
  
  // 时间记录
  assigned_at?: string
  started_at?: string
  completed_at?: string
  
  // 备注
  reviewer_notes?: string
  
  created_at: string
  updated_at: string
}

// 多级审核结果
export interface QCAuditResult {
  id: string
  task_item_id: string
  audit_level: AuditLevel
  reviewer_id: string
  reviewer_name: string
  
  // 审核结果
  audit_score: number
  audit_conclusion?: string
  defects_found: QCDefect[]
  
  // 状态管理
  status: AuditResultStatus
  is_final: boolean
  
  // 审核时间和效率
  review_duration?: number // 分钟
  submitted_at?: string
  approved_at?: string
  
  // 修改记录
  modified_by?: string
  modification_reason?: string
  original_score?: number
  
  created_at: string
  updated_at: string
}

// 质控缺陷
export interface QCDefect {
  id: string
  audit_result_id: string
  task_item_id: string
  
  // 缺陷基本信息
  defect_code?: string
  defect_type: string
  defect_category: string
  severity: DefectSeverity
  
  // 缺陷描述
  title: string
  description: string
  location?: string
  evidence?: string
  
  // 整改要求
  rectification_requirement?: string
  rectification_suggestion?: string
  estimated_rectification_time?: number
  
  // 状态管理
  status: DefectStatus
  
  // 评分影响
  score_deduction: number
  
  // AI辅助标识
  ai_assisted: boolean
  ai_confidence?: number
  
  // 时间戳
  identified_at: string
  rectification_deadline?: string
  resolved_at?: string
  
  created_at: string
  updated_at: string
}

// 消息通知
export interface QCNotification {
  id: string
  type: MessageType
  priority: MessagePriority
  status: MessageStatus
  
  // 发送方信息
  sender_id?: string
  sender_name?: string
  sender_role?: string
  
  // 接收方信息
  recipient_id: string
  recipient_type: RecipientType
  
  // 消息内容
  title: string
  content: string
  summary?: string
  
  // 关联数据
  related_data: NotificationRelatedData
  
  // 行为配置
  actions?: MessageAction[]
  auto_expire: boolean
  expires_at?: string
  
  // 状态时间戳
  created_at: string
  updated_at: string
  sent_at?: string
  delivered_at?: string
  read_at?: string
  processed_at?: string
  
  // 分发信息
  distribution_channel?: string
  delivery_attempts: number
  last_attempt_at?: string
}

export interface NotificationRelatedData {
  patient_id?: string
  medical_record_id?: string
  audit_task_id?: string
  task_item_id?: string
  defect_id?: string
  conversation_id?: string
  [key: string]
}

export interface MessageAction {
  id: string
  label: string
  type: 'primary' | 'secondary' | 'danger'
  action: 'navigate' | 'api_call' | 'modal' | 'confirm'
  config: {
    url?: string
    api_endpoint?: string
    modal_component?: string
    confirm_message?: string
    params?: Record<string, unknown>
  }
}

// 用户通知偏好
export interface UserNotificationPreferences {
  id: string
  user_id: string
  
  // 通道偏好
  preferred_channel: string
  enable_browser_notifications: boolean
  enable_email_notifications: boolean
  enable_sms_notifications: boolean
  
  // 消息类型偏好
  message_type_preferences: Record<string, boolean>
  
  // 免打扰设置
  quiet_hours_start?: string
  quiet_hours_end?: string
  quiet_days?: number[]
  
  // 批量设置
  enable_batch_digest: boolean
  batch_digest_frequency: string
  
  created_at: string
  updated_at: string
}

// 请求和响应接口
export interface CreateAuditTaskRequest {
  task_name: string
  task_type: AuditTaskType
  audit_level: AuditLevel
  audit_scope: AuditScope
  sampling_config: SamplingConfig
  planned_start_date: string
  planned_end_date: string
  assigned_reviewers: string[]
  description?: string
  priority?: number
}

export interface AuditTaskFilter {
  task_type?: AuditTaskType
  audit_level?: AuditLevel
  status?: AuditStatus
  assigned_reviewer?: string
  date_range?: {
    start: string
    end: string
  }
  search?: string
}

export interface BatchAuditRequest {
  task_id: string
  task_item_ids: string[]
  audit_template?: AuditTemplate
  batch_notes?: string
}

export interface AuditTemplate {
  default_score: number
  common_defects: Partial<QCDefect>[]
  auto_apply_rules: boolean
}

export interface BatchAuditResult {
  total_processed: number
  successful_count: number
  failed_count: number
  errors: BatchError[]
  processed_items: ProcessedAuditItem[]
}

export interface BatchError {
  task_item_id: string
  error_message: string
  error_code?: string
}

export interface ProcessedAuditItem {
  task_item_id: string
  audit_result_id: string
  score: number
  defect_count: number
  has_critical_defects: boolean
  processing_time: number
}

// AI辅助相关接口
export interface AIDefectSuggestion {
  suggested_type: string
  suggested_category: string
  suggested_severity: DefectSeverity
  suggested_title: string
  suggested_description: string
  suggested_location?: string
  confidence: number
  supporting_evidence: string[]
  rectification_suggestions: string[]
}

export interface DefectAnalysisContext {
  medical_record: Record<string, unknown>
  audit_level: AuditLevel
  reviewer_expertise: string[]
  historical_defects?: QCDefect[]
}

// 统计和分析接口
export interface AuditStatistics {
  total_tasks: number
  completed_tasks: number
  average_completion_time: number
  overall_defect_rate: number
  defects_by_severity: Record<DefectSeverity, number>
  defects_by_category: Record<string, number>
  reviewer_performance: ReviewerPerformance[]
}

export interface ReviewerPerformance {
  reviewer_id: string
  reviewer_name: string
  completed_audits: number
  average_score: number
  average_review_time: number
  defect_detection_rate: number
  consistency_score: number
}

// 导出接口
export interface AuditExportConfig {
  task_ids?: string[]
  date_range?: {
    start: string
    end: string
  }
  include_defects: boolean
  include_statistics: boolean
  format: 'excel' | 'csv' | 'pdf'
}

export interface ExportResult {
  file_url: string
  file_name: string
  file_size: number
  export_time: string
  record_count: number
}
