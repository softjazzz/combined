import type {
  DeptInfo,
  PatientRecord,
  WorkstationSnapshotState,
  WorkstationWorklistItem,
} from './types'

export interface StageWorklistResponse {
  data?: {
    items?: unknown[]
    total?: number
    page?: number
    page_size?: number
    total_pages?: number
    departments?: unknown[]
  }
}

export type SnapshotTabKey = 'form' | 'coding' | 'cost'

export function normalizeStageDepartments(
  rawItems: unknown[] | undefined,
  total: number,
): DeptInfo[] {
  const items = Array.isArray(rawItems) ? rawItems : []
  if (items.length === 0) {
    return [{ name: '全部科室', total, warningCount: 0 }]
  }
  return items.map((item) => {
    const source = (item || {}) as Record<string, unknown>
    return {
      name: String(source.name || '未分科室'),
      total: Number(source.total || 0),
      warningCount: Number(source.warningCount || source.warning_count || 0),
    }
  })
}

export function stageWorklistEndpoint(stage: string): string | null {
  if (stage === 'coding_qc') return '/api/v1/workstation/coding-qc/worklist'
  if (stage === 'frontpage_qc') return '/api/v1/workstation/frontpage-qc/worklist'
  if (stage === 'settlement_qc') return '/api/v1/workstation/settlement-qc/worklist'
  return null
}

export function snapshotEndpoint(
  workflow: WorkstationWorklistItem['workflowType'],
  visitId: string,
): string {
  return `/api/v1/workstation/${workflow}-qc/${visitId}/snapshot`
}

export function mapWorklistStatus(item: WorkstationWorklistItem): PatientRecord['status'] {
  if (item.activeDefectCount > 0) return 'has_defects'
  if (item.latestQcResultId) return 'completed'
  return 'pending'
}

export function mapWorklistItemToRecord(item: WorkstationWorklistItem): PatientRecord {
  return {
    id: item.visitId,
    visitId: item.visitId,
    instituteId: item.instituteId,
    patientId: item.patientId,
    bedNo: '',
    name: item.patientName,
    sex: item.patientSex || '',
    age: Number(item.patientAge || 0),
    insurance: '',
    department: item.department || '未分科室',
    admissionDate: item.admissionDate || '',
    dischargeDate: item.dischargeDate || '',
    days: 0,
    cdmFrontpageEmpty: item.workflowType === 'frontpage' ? false : undefined,
    hasAdmission: true,
    hasFrontpageDraft: false,
    hasFrontpageOfficial: item.workflowType !== 'settlement',
    hasSettlementOfficial: item.workflowType === 'settlement',
    isDemoRecord: false,
    diagnosis: '',
    diagnosisCode: '',
    doctor: '',
    status: mapWorklistStatus(item),
  }
}

export function buildSnapshotState(
  data: Record<string, any> | undefined,
  category: SnapshotTabKey,
  workflow: WorkstationWorklistItem['workflowType'],
  workflowLabelMap: Record<WorkstationWorklistItem['workflowType'], string>,
): WorkstationSnapshotState {
  const activeDefects = Array.isArray(data?.active_defects) ? data.active_defects : []
  const latestResult = (data?.latest_qc_result || null) as Record<string, unknown> | null
  const latestNotification = (data?.latest_notification || null) as Record<string, unknown> | null

  return {
    analyzed: Boolean(latestResult || activeDefects.length > 0),
    issues: activeDefects.map((issue: any, index: number) => ({
      id: String(issue?.id || `${category}-snapshot-${index + 1}`),
      rule_name: String(issue?.rule_name || ''),
      description: String(issue?.description || ''),
      severity: String(issue?.severity || 'info'),
      category: String(issue?.category || workflowLabelMap[workflow]),
      suggestion: String(issue?.suggestion || ''),
      evidence: typeof issue?.evidence === 'string' ? issue.evidence : '',
      location: String(issue?.location || ''),
      status: String(issue?.status || ''),
    })),
    latestResult,
    latestNotification,
  }
}
