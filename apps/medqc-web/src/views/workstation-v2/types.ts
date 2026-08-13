import type { QueueStatusCode, QueueStatusSource } from '@/types/workflow'

export interface PatientRecord {
  id: string
  visitId?: string
  instituteId?: string
  patientId?: string
  bedNo: string
  name: string
  sex: string
  age: number
  insurance: string
  department: string
  admissionDate: string
  dischargeDate: string
  days: number
  cdmFrontpageEmpty?: boolean
  hasAdmission?: boolean
  hasFrontpageDraft?: boolean
  frontpageDraftUpdatedAt?: string
  hasFrontpageOfficial?: boolean
  hasSettlementOfficial?: boolean
  frontpageGenerateQueueStatus?: QueueStatusCode
  frontpageGenerateQueueStatusSource?: QueueStatusSource
  isDemoRecord?: boolean
  diagnosis: string
  diagnosisCode: string
  doctor: string
  status: 'pending' | 'processing' | 'completed' | 'warning' | 'has_defects'
}

export interface DeptInfo {
  name: string
  total: number
  warningCount: number
}

export interface DocItem {
  type: string
  label: string
  has_content: boolean
  content: string | null
  length: number
}

export type FrontpageFocusTarget = 'basic' | 'admission' | 'diagnosis' | 'procedure'

export type IcdApplyTarget = 'mainDiagnosis' | 'otherDiagnosis' | 'mainProcedure' | 'otherProcedure'

export interface QCIssueLike {
  id?: string
  record_id?: string
  category?: 'form' | 'coding' | 'cost' | string
  group?: string
  status?: string
  severity?: string
  rule_name?: string
  description?: string
  suggestion?: string
  evidence?: string
  dismissed?: boolean
}

export interface NotificationVM {
  id: string
  record_id: string
  title: string
  content: string
  message: string
  created_at: string
  is_read: boolean
  level?: string
  type?: string
}

export interface NotificationOverviewItem {
  overview_id: string
  type: string
  severity: string
  department: string
  record_id: string
  title: string
  summary: string
  occurrence_count: number
  unread_count: number
  latest_created_at: string
  source_notification_ids: string[]
}

export interface HomeKpis {
  hotspot_total: number
  high_risk_total: number
  my_pending_total: number
  my_in_progress_total: number
  my_overdue_total: number
  batch_summary_total: number
}

export interface WorkstationHomeDepartmentRiskItem {
  department: string
  count: number
}

export interface WorkstationHomeWorkflowStatusItem {
  workflow_type: string
  pending?: number
  in_progress?: number
  overdue?: number
  running?: number
  failed?: number
  succeeded?: number
}

export interface WorkstationHomeHotspotItem {
  id: string
  record_id: string
  visit_id: string
  patient_id?: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: 'frontpage' | 'coding' | 'settlement' | string
  severity: string
  title: string
  summary: string
  occurrence_count: number
  unread_count: number
  active_defect_count: number
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  queue_status?: QueueStatusCode
  queue_status_source?: QueueStatusSource
  latest_created_at?: string
  latest_notification_id?: string
  launch_action?: string
  launch_stage?: string
}

export interface WorkstationHomeTodoItem {
  id: string
  todo_type: string
  record_id: string
  visit_id: string
  patient_id?: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: 'frontpage' | 'coding' | 'settlement' | string
  task_status: 'pending' | 'in_progress' | 'overdue' | string
  priority: 'critical' | 'high' | 'medium' | 'normal' | string
  due_at?: string | null
  active_defect_count: number
  summary: string
  queue_status?: QueueStatusCode
  queue_status_source?: QueueStatusSource
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  launch_action?: string
  launch_stage?: string
}

export interface WorkstationHomeBatchSummary {
  id: string
  title: string
  content: string
  created_at?: string
  is_read?: boolean
  type?: string
  workflow_type?: string
}

/** 全病历质控首页的权威聚合范围。三坐标只在下钻时使用，首页不以单一 visit_id 识别病历。 */
export interface ClinicalQcHomeScope {
  hospital_scope: 'all' | string
  department: string | null
  scene: string
  rule_set_key: string
  rule_set_version: string
  generated_at: string
}

export interface ClinicalQcHomePriorityItem {
  record_key: string
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name?: string
  department: string
  priority_kind: 'non_compliant' | 'data_gap' | 'uncertain' | string
  status_counts: Record<string, number>
  completed_at?: string | null
}

export interface ClinicalQcHomeDepartmentItem {
  department: string
  records_total: number
  completed_record_total: number
  high_risk_review_total: number
  data_gap_record_total: number
  uncertain_record_total: number
  defect_total: number
  average_defect_count: number
}

export interface ClinicalQcHomePhysicianItem {
  physician: string
  records_total: number
  completed_record_total: number
  high_risk_review_total: number
  data_gap_record_total: number
  uncertain_record_total: number
  defect_total: number
  average_defect_count: number
}

export interface ClinicalQcHomeProjection {
  scope: ClinicalQcHomeScope
  kpis: {
    records_total: number
    qc_pending_total: number
    qc_completed_total: number
    high_risk_review_total: number
  }
  data_health: {
    source_sync_status: 'unknown' | string
    source_error_total: number
    technical_error_total: number
    running_task_total: number | null
    running_task_state: 'unknown' | string
    last_successful_qc_at: string | null
  }
  canonical_status_counts: Record<string, number>
  priority_items: ClinicalQcHomePriorityItem[]
  department_distribution: ClinicalQcHomeDepartmentItem[]
  physician_distribution: ClinicalQcHomePhysicianItem[]
  rule_family_distribution: unknown[]
  trend: unknown | null
  comparison: unknown | null
}

export interface WorkstationHomePayload {
  date: string
  kpis: HomeKpis
  hotspots: WorkstationHomeHotspotItem[]
  my_todo_summary: {
    pending_total: number
    in_progress_total: number
    overdue_total: number
    high_priority_total: number
  }
  my_todo_items: WorkstationHomeTodoItem[]
  batch_summaries: WorkstationHomeBatchSummary[]
  department_options: string[]
  team_summary?: {
    department_risk_distribution?: WorkstationHomeDepartmentRiskItem[]
    workflow_status_distribution?: WorkstationHomeWorkflowStatusItem[]
  }
  /** 新首页唯一业务口径；旧热点/待办字段仅为旧页面兼容，不得混入该首页。 */
  scope?: ClinicalQcHomeScope
  clinical_qc?: ClinicalQcHomeProjection
}

/** 首页统一任务列表的前端聚合视图模型 */
export interface UnifiedTaskItem {
  id: string
  /** 来源类型：问题集中点 / 个人待办 */
  source_type: 'hotspot' | 'todo'
  record_id: string
  visit_id: string
  patient_name?: string
  patient_age?: number | string | null
  patient_sex?: string | null
  patient_gender?: string | null
  department: string
  workflow_type: string
  severity: string
  priority: string
  summary: string
  title?: string
  active_defect_count: number
  unread_count: number
  task_status?: string
  queue_status?: string
  latest_qc_score?: number | null
  latest_qc_grade?: string | null
  latest_created_at?: string
  due_at?: string | null
  launch_action?: string
  launch_stage?: string
}

export interface WorkstationWorklistItem {
  visitId: string
  patientId?: string
  instituteId?: string
  patientName: string
  department: string
  admissionDate?: string
  dischargeDate?: string
  workflowType: 'frontpage' | 'coding' | 'settlement'
  queueStatus: QueueStatusCode
  queueStatusSource?: QueueStatusSource
  latestQcResultId?: string
  latestQcScore?: number | null
  latestQcGrade?: string | null
  latestQcTime?: string | null
  activeDefectCount: number
  topSeverity?: string | null
  riskReason: string
  notificationStatus?: 'none' | 'read' | 'unread'
  notificationUpdatedAt?: string | null
}

export interface WorkstationSnapshotIssue {
  id: string
  rule_name?: string
  description?: string
  severity?: string
  category?: string
  suggestion?: string
  evidence?: string
  location?: string
  status?: string
}

export interface WorkstationSnapshotState {
  analyzed: boolean
  issues: WorkstationSnapshotIssue[]
  latestResult?: Record<string, unknown> | null
  latestNotification?: Record<string, unknown> | null
}
