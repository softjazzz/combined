import type {
  NotificationVM,
  PatientRecord,
  QCIssueLike,
  RecordLatestQcSummary,
  RecordLatestReviewState,
  RecordPoolQcSummary,
  RecordSourceState,
  WorkstationWorklistItem,
} from './types'
import type { QueueStatusCode, QueueStatusSource } from '@/types/workflow'

type LooseRecord = Record<string, unknown>

function asString(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function asNumber(value: unknown): number {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase()
  return ['true', '1', 'yes', 'y', 'ok'].includes(normalized)
}

function pickString(raw: LooseRecord, keys: string[]): string {
  for (const key of keys) {
    const value = asString(raw[key])
    if (value) return value
  }
  return ''
}

function normalizeQueueStatusCode(rawStatus: string): QueueStatusCode {
  const status = rawStatus.toLowerCase()
  if (
    status === 'running' ||
    status === 'failed' ||
    status === 'succeeded' ||
    status === 'unknown'
  ) {
    return status
  }
  return 'pending'
}

function normalizeQueueStatusSource(rawSource: string): QueueStatusSource {
  const source = rawSource.toLowerCase()
  if (source === 'runtime') return 'runtime'
  return 'backfill'
}

function normalizeRecordStatus(rawStatus: string): PatientRecord['status'] {
  const status = rawStatus.toLowerCase()
  if (status === 'completed' || status === 'done' || status === 'approved') return 'completed'
  if (status === 'processing' || status === 'in_progress' || status === 'running')
    return 'processing'
  if (status === 'warning' || status === 'high_risk') return 'warning'
  if (status === 'has_defects' || status === 'defect' || status === 'rejected') return 'has_defects'
  return 'pending'
}

export function isDefectStatus(status: string): boolean {
  return status === 'has_defects' || status === 'warning'
}

export function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: '\u5df2\u5b8c\u6210',
    has_defects: '\u9ad8\u98ce\u9669',
    warning: '\u9ad8\u98ce\u9669',
    processing: '\u5904\u7406\u4e2d',
    pending: '\u5f85\u5904\u7406',
  }
  return map[status] || '\u5f85\u5904\u7406'
}

export function getStatusTheme(status: string): 'emerald' | 'rose' | 'blue' | 'slate' {
  if (status === 'completed') return 'emerald'
  if (isDefectStatus(status)) return 'rose'
  if (status === 'processing') return 'blue'
  return 'slate'
}

export function resolveVisitId(record: PatientRecord): string {
  return (record as any).visitId || record.id
}

export function normalizeRecord(raw: unknown): PatientRecord {
  const source = (raw || {}) as LooseRecord
  const id =
    pickString(source, ['id', 'record_id', 'visit_id', 'visitId']) || `record-${Date.now()}`
  const visitId = pickString(source, ['visitId', 'visit_id']) || id
  const dischargeDatetime = pickString(source, ['dischargeDatetime', 'discharge_datetime'])
  const dischargeDate =
    pickString(source, ['dischargeDate', 'discharge_date', 'out_date']) ||
    dischargeDatetime.slice(0, 10)
  const admissionDate = pickString(source, ['admissionDate', 'admission_date', 'in_date'])
  const updateTime = pickString(source, ['updateTime', 'update_time', 'updated_at'])
  const sortTime =
    pickString(source, ['sortTime', 'sort_time']) || updateTime || dischargeDate || admissionDate
  const rawCdmFrontpageEmpty = source.cdmFrontpageEmpty ?? source.cdm_frontpage_empty
  const cdmFrontpageEmpty =
    rawCdmFrontpageEmpty === undefined || rawCdmFrontpageEmpty === null
      ? undefined
      : asBoolean(rawCdmFrontpageEmpty)
  const hasAdmission =
    asBoolean(source.hasAdmission ?? source.has_admission) ||
    Boolean(admissionDate) ||
    Boolean(pickString(source, ['in_date', 'admission_no', 'hospitalization_no']))
  const hasFrontpageDraft = asBoolean(
    source.hasFrontpageDraft ??
      source.has_frontpage_draft ??
      source.ai_frontpage_draft_exists ??
      source.draft_frontpage_exists,
  )
  const hasFrontpageOfficialByFlag = source.hasFrontpageOfficial ?? source.has_frontpage_official
  const hasFrontpageOfficial =
    hasFrontpageOfficialByFlag !== undefined && hasFrontpageOfficialByFlag !== null
      ? asBoolean(hasFrontpageOfficialByFlag)
      : cdmFrontpageEmpty === undefined
        ? false
        : !cdmFrontpageEmpty
  const settlementHint = pickString(source, [
    'settlement_status',
    'settlementStatus',
    'medinsur_serial_no',
  ])
  const hasSettlementOfficialByFlag = source.hasSettlementOfficial ?? source.has_settlement_official
  const hasSettlementOfficial =
    hasSettlementOfficialByFlag !== undefined && hasSettlementOfficialByFlag !== null
      ? asBoolean(hasSettlementOfficialByFlag)
      : Boolean(settlementHint)
  const frontpageGenerateQueueStatusRaw = pickString(source, [
    'frontpageGenerateQueueStatus',
    'frontpage_generate_queue_status',
  ])
  const frontpageGenerateQueueStatusSourceRaw = pickString(source, [
    'frontpageGenerateQueueStatusSource',
    'frontpage_generate_queue_status_source',
  ])

  return {
    id,
    recordKey: pickString(source, ['recordKey', 'record_key']) || undefined,
    visitId,
    instituteId: pickString(source, ['instituteId', 'institute_id', 'hospital_code']) || undefined,
    patientId: pickString(source, ['patientId', 'patient_id']) || undefined,
    identityStatus: (() => {
      const status = pickString(source, ['identityStatus', 'identity_status'])
      return status === 'ambiguous' || status === 'unverified' ? status : undefined
    })(),
    bedNo: pickString(source, ['bedNo', 'bed_no', 'bed_number']),
    name: pickString(source, ['name', 'patient_name', 'patientName']) || '未知患者',
    sex: pickString(source, ['sex', 'gender']) || '未知',
    age: asNumber(source.age ?? source.patient_age ?? source.age_years),
    insurance: pickString(source, ['insurance', 'insurance_type', 'medical_insurance_type']),
    department:
      pickString(source, ['department', 'dept_name', 'deptName', 'current_department']) ||
      '未分科室',
    admissionDate,
    dischargeDate,
    dischargeDatetime,
    hospitalizationStatus: (() => {
      const status = pickString(source, [
        'hospitalizationStatus',
        'hospitalization_status',
      ]).toLowerCase()
      return status === 'inpatient' || status === 'discharged' || status === 'unknown'
        ? status
        : undefined
    })(),
    hospitalizationStatusVerifiedAt:
      pickString(source, [
        'hospitalizationStatusVerifiedAt',
        'hospitalization_status_verified_at',
      ]) || undefined,
    hospitalizationStatusSource:
      pickString(source, ['hospitalizationStatusSource', 'hospitalization_status_source']) ||
      undefined,
    updateTime: updateTime || undefined,
    sortTime: sortTime || undefined,
    days: asNumber(
      source.days ?? source.stay_days ?? source.length_of_stay ?? source.hospital_days,
    ),
    cdmFrontpageEmpty,
    hasAdmission,
    hasFrontpageDraft,
    frontpageDraftUpdatedAt:
      pickString(source, [
        'frontpageDraftUpdatedAt',
        'frontpage_draft_updated_at',
        'draft_updated_at',
      ]) || undefined,
    hasFrontpageOfficial,
    hasSettlementOfficial,
    frontpageGenerateQueueStatus: frontpageGenerateQueueStatusRaw
      ? normalizeQueueStatusCode(frontpageGenerateQueueStatusRaw)
      : undefined,
    frontpageGenerateQueueStatusSource: frontpageGenerateQueueStatusSourceRaw
      ? normalizeQueueStatusSource(frontpageGenerateQueueStatusSourceRaw)
      : undefined,
    isDemoRecord: asBoolean(source.isDemoRecord ?? source.is_demo_record),
    diagnosis: pickString(source, [
      'diagnosis',
      'main_diagnosis',
      'primary_diagnosis',
      'discharge_main_diagnosis_text',
    ]),
    diagnosisCode: pickString(source, ['diagnosisCode', 'diagnosis_code', 'main_diagnosis_code']),
    doctor: pickString(source, ['doctor', 'doctor_name', 'attending_doctor']),
    status: normalizeRecordStatus(
      pickString(source, ['status', 'auditStatus', 'audit_status', 'qc_status']),
    ),
    sourceState: normalizeRecordSourceState(source.sourceState ?? source.source_state),
    latestQcSummary: normalizeRecordLatestQcSummary(
      source.latestQcSummary ?? source.latest_qc_summary,
    ),
  }
}

function normalizeRecordSourceState(raw: unknown): RecordSourceState {
  const source = (raw || {}) as LooseRecord
  const status = pickString(source, ['status']).toLowerCase()
  return {
    status: status || 'unknown',
    lastSyncAt: pickString(source, ['lastSyncAt', 'last_sync_at']) || null,
    reasonCode: pickString(source, ['reasonCode', 'reason_code']) || null,
  }
}

function normalizeStatusCounts(raw: unknown): Record<string, number> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  return Object.entries(raw as LooseRecord).reduce<Record<string, number>>(
    (result, [status, count]) => {
      const normalizedStatus = status.trim()
      const normalizedCount = Number(count)
      if (normalizedStatus && Number.isFinite(normalizedCount) && normalizedCount > 0) {
        result[normalizedStatus] = normalizedCount
      }
      return result
    },
    {},
  )
}

const RECORD_REVIEW_STATES: readonly RecordLatestReviewState[] = [
  'pending_review',
  'pending_recheck',
  'approved',
  'doubtful',
]

/** 只搬运服务端审核状态；缺失或无法识别一律为 null（未知），不推断。 */
function normalizeRecordReviewState(raw: unknown): RecordLatestReviewState | null {
  return typeof raw === 'string' && (RECORD_REVIEW_STATES as readonly string[]).includes(raw)
    ? (raw as RecordLatestReviewState)
    : null
}

function normalizeRecordLatestQcSummary(raw: unknown): RecordLatestQcSummary {
  const source = (raw || {}) as LooseRecord
  const status = pickString(source, ['status'])
  if (status === 'ready') {
    return {
      status: 'ready',
      completedAt: pickString(source, ['completedAt', 'completed_at']) || null,
      totalRuleCount: asNumber(source.totalRuleCount ?? source.total_rule_count),
      statusCounts: normalizeStatusCounts(source.statusCounts ?? source.status_counts),
      reviewState: normalizeRecordReviewState(source.reviewState ?? source.review_state),
    }
  }
  if (status === 'technical_error') {
    return {
      status: 'technical_error',
      reasonCode: pickString(source, ['reasonCode', 'reason_code']) || null,
    }
  }
  return { status: 'not_run' }
}

export function normalizeRecordPoolQcSummary(raw: unknown): RecordPoolQcSummary {
  const source = (raw || {}) as LooseRecord
  return {
    totalRecords: asNumber(source.totalRecords ?? source.total_records),
    readyRecords: asNumber(source.readyRecords ?? source.ready_records),
    notRunRecords: asNumber(source.notRunRecords ?? source.not_run_records),
    technicalErrorRecords: asNumber(source.technicalErrorRecords ?? source.technical_error_records),
    statusCounts: normalizeStatusCounts(source.statusCounts ?? source.status_counts),
    runningState: pickString(source, ['runningState', 'running_state']) || 'unknown',
  }
}

function normalizeDefectStatus(rawStatus: string): string {
  const status = rawStatus.toLowerCase()
  if (!status) return 'pending'
  if (status === 'pending' || status === 'processing' || status === 'completed') return status
  if (status === 'approved' || status === 'resolved') return 'completed'
  if (status === 'rejected') return 'rejected'
  return rawStatus
}

export function normalizeDefect(raw: QCIssueLike, index: number): QCIssueLike & { id: string } {
  const source = (raw || {}) as LooseRecord
  return {
    ...raw,
    id: asString(source.id) || asString(source.defect_id) || `defect-${index}`,
    record_id: pickString(source, ['record_id', 'recordId', 'visit_id', 'visitId']) || undefined,
    status: normalizeDefectStatus(pickString(source, ['status', 'audit_status', 'auditStatus'])),
    severity: pickString(source, ['severity', 'level', 'priority']) || undefined,
    rule_name: pickString(source, ['rule_name', 'ruleName', 'title']) || undefined,
    category: pickString(source, ['category', 'group_type']) || raw.category,
    group: pickString(source, ['group', 'module', 'section']) || raw.group,
    description: pickString(source, ['description', 'message', 'issue']) || raw.description,
    suggestion: pickString(source, ['suggestion', 'recommendation', 'advice']) || raw.suggestion,
    evidence: pickString(source, ['evidence', 'quote', 'snippet']) || raw.evidence,
    dismissed: Boolean(source.dismissed ?? raw.dismissed),
  }
}

export function normalizeNotification(raw: unknown, index: number): NotificationVM {
  const source = (raw || {}) as LooseRecord
  const title = pickString(source, ['title', 'subject', 'type_label']) || '通知消息'
  const content = pickString(source, ['content', 'message', 'body']) || '暂无内容'
  return {
    id: pickString(source, ['id', 'notification_id']) || `notification-${index}`,
    record_id: pickString(source, ['record_id', 'recordId', 'visit_id', 'visitId']),
    title,
    content,
    message: pickString(source, ['message']) || content,
    created_at: pickString(source, ['created_at', 'createdAt', 'timestamp']),
    is_read: Boolean(source.is_read ?? source.isRead),
    level: pickString(source, ['level', 'severity']) || undefined,
    type: pickString(source, ['type', 'category']) || undefined,
  }
}

export function normalizeWorklistItem(raw: unknown): WorkstationWorklistItem {
  const source = (raw || {}) as LooseRecord
  const visitId =
    pickString(source, ['visitId', 'visit_id', 'id', 'record_id']) || `visit-${Date.now()}`
  const notificationStatus = pickString(source, ['notificationStatus', 'notification_status'])
  const queueStatus = normalizeQueueStatusCode(
    pickString(source, ['queueStatus', 'queue_status']) || 'pending',
  )
  const queueStatusSource = normalizeQueueStatusSource(
    pickString(source, ['queueStatusSource', 'queue_status_source']) || 'backfill',
  )
  const latestQcScoreRaw = source.latestQcScore ?? source.latest_qc_score

  return {
    visitId,
    patientId: pickString(source, ['patientId', 'patient_id']) || undefined,
    instituteId: pickString(source, ['instituteId', 'institute_id']) || undefined,
    identityStatus: (() => {
      const status = pickString(source, ['identityStatus', 'identity_status'])
      return status === 'ambiguous' || status === 'unverified' ? status : undefined
    })(),
    patientName: pickString(source, ['patientName', 'patient_name', 'name']) || '未知患者',
    patientSex: pickString(source, ['patientSex', 'patient_sex', 'sex', 'gender']) || undefined,
    patientAge: asNumber(source.patientAge ?? source.patient_age ?? source.age ?? source.age_years),
    department: pickString(source, ['department', 'dept_name', 'deptName']) || '未分科室',
    admissionDate: pickString(source, ['admissionDate', 'admission_date']) || undefined,
    dischargeDate:
      pickString(source, ['dischargeDate', 'discharge_date']) ||
      pickString(source, ['dischargeDatetime', 'discharge_datetime']).slice(0, 10) ||
      undefined,
    dischargeDatetime: pickString(source, ['dischargeDatetime', 'discharge_datetime']) || undefined,
    workflowType:
      (pickString(source, [
        'workflowType',
        'workflow_type',
      ]) as WorkstationWorklistItem['workflowType']) || 'frontpage',
    queueStatus,
    queueStatusSource,
    latestQcResultId: pickString(source, ['latestQcResultId', 'latest_qc_result_id']) || undefined,
    latestQcScore:
      latestQcScoreRaw === undefined || latestQcScoreRaw === null || latestQcScoreRaw === ''
        ? null
        : asNumber(latestQcScoreRaw),
    latestQcGrade: pickString(source, ['latestQcGrade', 'latest_qc_grade']) || undefined,
    latestQcTime: pickString(source, ['latestQcTime', 'latest_qc_time']) || undefined,
    activeDefectCount: asNumber(source.activeDefectCount ?? source.active_defect_count),
    topSeverity: pickString(source, ['topSeverity', 'top_severity']) || undefined,
    riskReason: pickString(source, ['riskReason', 'risk_reason']),
    notificationStatus:
      notificationStatus === 'read' || notificationStatus === 'unread'
        ? (notificationStatus as 'read' | 'unread')
        : 'none',
    notificationUpdatedAt:
      pickString(source, ['notificationUpdatedAt', 'notification_updated_at']) || undefined,
  }
}
