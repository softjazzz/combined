import type { QueueStatusCode, QueueStatusSource } from '@/types/workflow'

export interface PatientRecord {
  id: string
  /** 病历池服务端返回的三坐标内部键；仅用于前端行身份，不能替代真实 visit_id。 */
  recordKey?: string
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
  dischargeDatetime?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  hospitalizationStatusVerifiedAt?: string
  hospitalizationStatusSource?: string
  updateTime?: string
  sortTime?: string
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
  sourceState?: RecordSourceState
  latestQcSummary?: RecordLatestQcSummary
}

export interface RecordSourceState {
  status: 'unknown' | string
  lastSyncAt: string | null
  reasonCode: string | null
}

export interface RecordLatestQcSummary {
  status: 'ready' | 'not_run' | 'technical_error'
  completedAt?: string | null
  totalRuleCount?: number
  statusCounts?: Record<string, number>
  reasonCode?: string | null
}

export interface RecordPoolQcSummary {
  totalRecords: number
  readyRecords: number
  notRunRecords: number
  technicalErrorRecords: number
  statusCounts: Record<string, number>
  runningState: 'unknown' | string
}

export interface DeptInfo {
  name: string
  total: number
  warningCount: number
}

export interface DoctorInfo {
  name: string
  total: number
}

export interface DocumentAuthor {
  role?: string
  name?: string
  code?: string
}

export interface DocumentSignature {
  role?: string
  name?: string
  signed_at?: string
  source_field?: string
}

export interface DocItem {
  id?: string
  doc_id?: string
  doc_key?: string
  doc_type?: string
  doc_name?: string
  type: string
  label: string
  has_content: boolean
  content: string | null
  length: number
  document_id?: string
  document_title?: string
  sort_time?: string
  record_time?: string
  source_table?: string
  group_key?: string
  execution_domain?: string
  sections?: Array<{
    section_key?: string
    section_label?: string
    text?: string
    source_field?: string
    order_index?: number
  }>
  source_fields?: Array<{
    source_table?: string
    source_field?: string
    source_path?: string | null
    used?: boolean
    raw_value_preview?: string
  }>
  assembly_status?: string
  data_quality_flags?: string[]
  authors?: DocumentAuthor[]
  signatures?: DocumentSignature[]
  projection_incomplete?: boolean
  projection_notice?: string
}

export interface DocTreeNode {
  id: string
  doc_key: string
  doc_type: string
  document_id?: string
  title: string
  record_time?: string
  source_table?: string
  group_key?: string
  has_content: boolean
  length: number
  projection_incomplete?: boolean
  projection_notice?: string
}

export interface DocTreeGroup {
  key: string
  label: string
  count: number
  children: DocTreeNode[]
  subgroups?: DocTreeGroup[]
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
  interaction_target?: DoctorInteractionTarget
}

export interface DoctorInteractionTarget {
  kind: 'rectification' | 'modern_appeal' | 'case_communication' | 'account_registration' | 'account_registration_result' | 'qc_result_ready'
  id: string
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
  interaction_target?: DoctorInteractionTarget
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
  patientSex?: string
  patientAge?: number
  department: string
  admissionDate?: string
  dischargeDate?: string
  dischargeDatetime?: string
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

export type StructuredQCStatus =
  | 'non_compliant'
  | 'ai_suggested_non_compliant'
  | 'uncertain'
  | 'ai_suggested_compliant'
  | 'compliant'
  | 'not_applicable'
  | 'data_gap'
  | 'not_executed'
  | 'technical_error'
  | 'failed'
  | 'error'

export type StructuredQCDisplayStatus =
  | 'confirmed_defect'
  | 'qc_review_candidate'
  | 'needs_review'
  | 'data_quality_gap'
  | 'rejected_by_system'
  | 'technical_error_internal'
  | 'compliant'
  | 'not_applicable'
  | ''

export interface StructuredQCOverview {
  totalRules: number
  complianceRate: number
  issueCount: number
  uncertainCount: number
  compliantCount: number
  notApplicableCount: number
  failedCount: number
  docCount: number
  processingTimeSeconds: number
}

export interface StructuredQCSubitemAnchor {
  parentRuleId: string
  anchorId: string
  subitemId: string
  subitemName: string
  anchorEvidenceStatus: string
  anchorEvidence: string
  anchorDecisionReason: string
  displayStatus: string
  displayBucket: string
  canShowAsDefect: boolean
  internalOnly: boolean
}

export interface StructuredQCIssue {
  id: string
  status: StructuredQCStatus
  statusLabel: string
  displayStatus: StructuredQCDisplayStatus
  displayBucket: string
  postprocessLabel: string
  postprocessReason: string
  evidenceProblemType: string
  canShowAsDefect: boolean
  canShowToDoctor: boolean
  internalOnly: boolean
  postprocessMode: string
  firstPassStatus?: string
  firstPassDisplayStatus?: string
  adjudicatedDisplayStatus?: string
  adjudicatorReason?: string
  adjudicatorSupportingQuote?: string
  adjudicatorConfidence?: number
  ruleRequirementMatch?: string
  ruleJobId: string
  ruleId: string
  ruleCode: string
  ruleName: string
  findings: string
  evidence: string
  suggestion: string
  confidence: number
  documentType: string
  executionDomain: string
  ruleFamily: string
  defectLevel: string
  executorType: string
  recordId: string
  visitId: string
  patientName: string
  department: string
  qcPointId?: string
  ruleSetKey?: string
  ruleSetVersion?: string
  schemaVersion?: string
  resultStatus?: string
  trigger?: Record<string, unknown> | null
  dependencies?: Record<string, unknown> | null
  evidenceItems?: Array<Record<string, unknown>>
  decision?: Record<string, unknown> | null
  review?: Record<string, unknown> | null
  audit?: Record<string, unknown> | null
  metadata: {
    traceId: string
    cacheHit: boolean | null
    promptVersion: string
    modelVersion: string
    ruleVersion: string
    evidenceSource: string
    cacheKey: string
    docScope: string
    costClass: string
    llmFallback: boolean | null
    refined: boolean | null
    refineReason: string
    screeningStatus: string
    finalDecisionSource: string
    subitemAnchors: StructuredQCSubitemAnchor[]
  }
}

export interface StructuredQCGroup {
  key: string
  label: string
  count: number
  kind: 'status' | 'document' | 'domain' | 'defect' | 'rule'
}

export interface StructuredQCFilterState {
  keyword: string
  statusList: StructuredQCStatus[]
  documentType: string
  executionDomain: string
  defectLevel: string
}

export interface StructuredQCResult {
  overview: StructuredQCOverview
  issues: StructuredQCIssue[]
  groups: StructuredQCGroup[]
  subitemAnchors: StructuredQCSubitemAnchor[]
}
