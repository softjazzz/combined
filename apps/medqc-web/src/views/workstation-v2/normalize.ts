import type { NotificationVM, PatientRecord, QCIssueLike } from './types'

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
  const normalized = String(value ?? '').trim().toLowerCase()
  return ['true', '1', 'yes', 'y', 'ok'].includes(normalized)
}

function pickString(raw: LooseRecord, keys: string[]): string {
  for (const key of keys) {
    const value = asString(raw[key])
    if (value) return value
  }
  return ''
}

function normalizeRecordStatus(rawStatus: string): PatientRecord['status'] {
  const status = rawStatus.toLowerCase()
  if (status === 'completed' || status === 'done' || status === 'approved') return 'completed'
  if (status === 'processing' || status === 'in_progress' || status === 'running') return 'processing'
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
  const id = pickString(source, ['id', 'record_id', 'visit_id', 'visitId']) || `record-${Date.now()}`
  const visitId = pickString(source, ['visitId', 'visit_id']) || id
  const dischargeDate = pickString(source, ['dischargeDate', 'discharge_date', 'out_date'])
  const admissionDate = pickString(source, ['admissionDate', 'admission_date', 'in_date'])
  const rawCdmFrontpageEmpty = source.cdmFrontpageEmpty ?? source.cdm_frontpage_empty
  const cdmFrontpageEmpty = rawCdmFrontpageEmpty === undefined || rawCdmFrontpageEmpty === null
    ? undefined
    : asBoolean(rawCdmFrontpageEmpty)
  const hasAdmission = asBoolean(source.hasAdmission ?? source.has_admission)
    || Boolean(admissionDate)
    || Boolean(pickString(source, ['in_date', 'admission_no', 'hospitalization_no']))
  const hasFrontpageDraft = asBoolean(
    source.hasFrontpageDraft
    ?? source.has_frontpage_draft
    ?? source.ai_frontpage_draft_exists
    ?? source.draft_frontpage_exists,
  )
  const hasFrontpageOfficialByFlag = source.hasFrontpageOfficial ?? source.has_frontpage_official
  const hasFrontpageOfficial = hasFrontpageOfficialByFlag !== undefined && hasFrontpageOfficialByFlag !== null
    ? asBoolean(hasFrontpageOfficialByFlag)
    : (cdmFrontpageEmpty === undefined ? false : !cdmFrontpageEmpty)
  const settlementHint = pickString(source, ['settlement_status', 'settlementStatus', 'medinsur_serial_no'])
  const hasSettlementOfficialByFlag = source.hasSettlementOfficial ?? source.has_settlement_official
  const hasSettlementOfficial = hasSettlementOfficialByFlag !== undefined && hasSettlementOfficialByFlag !== null
    ? asBoolean(hasSettlementOfficialByFlag)
    : Boolean(settlementHint)

  return {
    id,
    visitId,
    instituteId: pickString(source, ['instituteId', 'institute_id', 'hospital_code']) || undefined,
    patientId: pickString(source, ['patientId', 'patient_id']) || undefined,
    bedNo: pickString(source, ['bedNo', 'bed_no', 'bed_number']),
    name: pickString(source, ['name', 'patient_name', 'patientName']) || '未知患者',
    sex: pickString(source, ['sex', 'gender']) || '未知',
    age: asNumber(source.age ?? source.patient_age ?? source.age_years),
    insurance: pickString(source, ['insurance', 'insurance_type', 'medical_insurance_type']),
    department: pickString(source, ['department', 'dept_name', 'deptName', 'current_department']) || '未分科室',
    admissionDate,
    dischargeDate,
    days: asNumber(source.days ?? source.stay_days ?? source.length_of_stay ?? source.hospital_days),
    cdmFrontpageEmpty,
    hasAdmission,
    hasFrontpageDraft,
    frontpageDraftUpdatedAt: pickString(source, ['frontpageDraftUpdatedAt', 'frontpage_draft_updated_at', 'draft_updated_at']) || undefined,
    hasFrontpageOfficial,
    hasSettlementOfficial,
    diagnosis: pickString(source, ['diagnosis', 'main_diagnosis', 'primary_diagnosis', 'discharge_main_diagnosis_text']),
    diagnosisCode: pickString(source, ['diagnosisCode', 'diagnosis_code', 'main_diagnosis_code']),
    doctor: pickString(source, ['doctor', 'doctor_name', 'attending_doctor']),
    status: normalizeRecordStatus(
      pickString(source, ['status', 'auditStatus', 'audit_status', 'qc_status']),
    ),
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
