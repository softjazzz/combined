import type { QueueStatusCode, QueueStatusSource } from '@/types/workflow'
import type { ClinicalQcHomeProjection, ClinicalQcHomeScope } from '@/views/workstation/types'
import type {
  HomeKpis,
  WorkstationHomeBatchSummary,
  WorkstationHomeDepartmentRiskItem,
  WorkstationHomeHotspotItem,
  WorkstationHomeTodoItem,
  WorkstationHomeWorkflowStatusItem,
} from '@/views/workstation/components/legacyHomeTypes'

export type {
  ClinicalQcHomeDepartmentItem,
  ClinicalQcHomePhysicianItem,
  ClinicalQcHomePriorityItem,
  ClinicalQcHomeProjection,
  ClinicalQcHomeScope,
} from '@/views/workstation/types'
export type {
  HomeKpis,
  UnifiedTaskItem,
  WorkstationHomeBatchSummary,
  WorkstationHomeDepartmentRiskItem,
  WorkstationHomeHotspotItem,
  WorkstationHomeTodoItem,
  WorkstationHomeWorkflowStatusItem,
} from '@/views/workstation/components/legacyHomeTypes'

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

/** GET /api/v1/workstation/home 的旧版统计兼容响应。 */
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
  scope?: ClinicalQcHomeScope
  clinical_qc?: ClinicalQcHomeProjection
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
