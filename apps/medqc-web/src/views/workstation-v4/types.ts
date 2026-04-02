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

export interface WorkstationHomeHotspotItem {
  id: string
  record_id: string
  visit_id: string
  patient_id?: string
  patient_name?: string
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
    department_risk_distribution?: Array<{ department: string; count: number }>
    workflow_status_distribution?: Array<Record<string, unknown>>
  }
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
