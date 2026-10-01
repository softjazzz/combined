export enum AppealType {
  DEFECT = 'defect',
  SCORE = 'score',
}

export enum AppealStatus {
  PENDING = 'pending',
  REVIEWING = 'reviewing',
  APPROVED = 'approved',
  ACCEPTED = 'accepted',
  REJECTED = 'rejected',
  WITHDRAWN = 'withdrawn',
}

export type AppealPriority = 'low' | 'medium' | 'high' | 'urgent'
export type AppealReviewAction = 'approve' | 'reject' | 'request_info' | 'forward'
export type AppealStatusFilter = AppealStatus | 'reviewable'
export type AppealScene = 'running' | 'final' | 'outpatient_emergency'
export type AppealSceneFilter = AppealScene | 'all'
export type AppealTargetKind = 'canonical_defect' | 'task_manual_defect'

export interface AppealEvidence {
  url?: string
  name?: string
  [key: string]: unknown
}

export interface AppealReview {
  id: string
  appealId: string
  reviewerId: string
  reviewerName: string | null
  action: AppealReviewAction
  comment: string | null
  createdAt: string
}

export interface Appeal {
  id: string
  appealNumber: string | null
  qcResultId: string
  recordId: string
  appealType: AppealType
  defectItem: string | null
  appealReason: string
  evidence: AppealEvidence[]
  status: AppealStatus
  priority: AppealPriority
  appellantId: string
  appellantName: string | null
  appellantDepartment: string | null
  reviewerId: string | null
  reviewerName: string | null
  reviewResult: string | null
  reviewedAt: string | null
  resolution: string | null
  resolutionDate: string | null
  notes: string | null
  createdAt: string
  updatedAt: string
  reviews?: AppealReview[]
  targetKind: AppealTargetKind | null
  targetId: string | null
  instituteId: string | null
  patientId: string | null
  visitId: string | null
  scene: AppealScene | null
  rootJobId: string | null
  envelopeId: string | null
  ruleSetKey: string | null
  ruleSetVersion: string | null
  caseDepartment: string | null
}

export interface AppealCaseIdentity {
  instituteId: string
  patientId: string
  visitId: string
}

interface AppealCreateRequestBase extends AppealCaseIdentity {
  scene: AppealScene
  appealReason: string
  evidence?: AppealEvidence[]
  priority?: AppealPriority
}

export type AppealCreateRequest =
  | (AppealCreateRequestBase & {
      targetKind: 'canonical_defect'
      expectedJobId: string
      expectedEnvelopeId: string
      ruleId: string
    })
  | (AppealCreateRequestBase & {
      targetKind: 'task_manual_defect'
      defectId: string
      expectedJobId?: string
      expectedEnvelopeId?: string
    })

export interface CanonicalAppealCandidateItem {
  ruleId: string
  ruleName: string | null
  conclusion: string | null
}

export interface CanonicalAppealCandidates {
  state: 'ready' | 'no_result' | 'unavailable'
  scene: AppealScene | null
  jobId: string | null
  envelopeId: string | null
  items: CanonicalAppealCandidateItem[]
}

export interface ManualAppealCandidate {
  defectId: string
  ruleCode: string | null
  ruleName: string | null
  description: string | null
  scene: AppealScene
}

export interface AppealCandidates extends AppealCaseIdentity {
  caseDepartment: string | null
  canonical: CanonicalAppealCandidates
  manualDefects: ManualAppealCandidate[]
}

export interface AppealUpdateRequest {
  appealReason?: string
  evidenceUrls?: string[]
  priority?: AppealPriority
  notes?: string
}

export interface AppealReviewRequest {
  action: AppealReviewAction
  comment?: string
  resolution?: string
}

export interface AppealListResponse {
  items: Appeal[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface AppealFilters {
  status?: AppealStatusFilter
  appealType?: AppealType
  priority?: AppealPriority
  startDate?: string
  endDate?: string
  scene?: AppealSceneFilter
  page?: number
  pageSize?: number
}

export interface AppealStats {
  total: number
  pending: number
  reviewing: number
  approved: number
  rejected: number
  withdrawn: number
  avgResolutionTimeHours: number | null
}

export const APPEAL_TYPE_OPTIONS = [
  { value: AppealType.DEFECT, label: '缺陷申诉' },
  { value: AppealType.SCORE, label: '评分申诉' },
]

export const APPEAL_STATUS_OPTIONS = [
  { value: 'reviewable', label: '待审核', color: 'orange' },
  { value: AppealStatus.PENDING, label: '待处理', color: 'orange' },
  { value: AppealStatus.REVIEWING, label: '审核中', color: 'blue' },
  { value: AppealStatus.APPROVED, label: '已通过', color: 'green' },
  { value: AppealStatus.ACCEPTED, label: '已接受', color: 'green' },
  { value: AppealStatus.REJECTED, label: '已驳回', color: 'red' },
  { value: AppealStatus.WITHDRAWN, label: '已撤回', color: 'default' },
] as const

export function getAppealTypeLabel(type: AppealType): string {
  return APPEAL_TYPE_OPTIONS.find((option) => option.value === type)?.label || type
}

export function getAppealStatusInfo(status: AppealStatus): { label: string; color: string } {
  return (
    APPEAL_STATUS_OPTIONS.find((option) => option.value === status) || {
      label: status,
      color: 'default',
    }
  )
}

export function canReviewAppeal(appeal: Appeal, roles: readonly string[]): boolean {
  return (
    roles.some((role) => role === 'admin' || role === 'qc_manager') &&
    [AppealStatus.PENDING, AppealStatus.REVIEWING].includes(appeal.status)
  )
}

export function canWithdrawAppeal(appeal: Appeal, userId: string | undefined): boolean {
  return (
    !!userId &&
    appeal.appellantId === userId &&
    [AppealStatus.PENDING, AppealStatus.REVIEWING].includes(appeal.status)
  )
}
