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
}

// 保持创建表单已有的调用形状，API 层负责转换为后端字段。
export interface AppealCreateRequest {
  qcResultId: string
  defectId?: string
  recordId: string
  appealReason: string
  appealType: AppealType
  evidenceUrls?: string[]
  priority?: AppealPriority
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
  return APPEAL_STATUS_OPTIONS.find((option) => option.value === status) || { label: status, color: 'default' }
}

export function canReviewAppeal(appeal: Appeal, roles: readonly string[]): boolean {
  return roles.some((role) => role === 'admin' || role === 'qc_manager') &&
    [AppealStatus.PENDING, AppealStatus.REVIEWING].includes(appeal.status)
}

export function canWithdrawAppeal(appeal: Appeal, userId: string | undefined): boolean {
  return !!userId && appeal.appellantId === userId &&
    [AppealStatus.PENDING, AppealStatus.REVIEWING].includes(appeal.status)
}
