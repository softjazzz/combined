/**
 * 申诉管理类型定义
 * Appeal Management Types
 */

/**
 * 申诉类型
 */
export enum AppealType {
    INCORRECT_RULE = 'incorrect_rule',  // 规则判定有误
    SPECIAL_CASE = 'special_case',      // 特殊情况
    OTHER = 'other'                     // 其他
}

/**
 * 申诉状态
 */
export enum AppealStatus {
    PENDING = 'pending',        // 待审核
    APPROVED = 'approved',      // 已通过
    REJECTED = 'rejected',      // 已驳回
    WITHDRAWN = 'withdrawn'     // 已撤销
}

/**
 * 申诉详情
 */
export interface Appeal {
    id: string
    qcResultId: string
    defectId: string
    recordId: string

    // 申诉人信息
    appellantId: string
    appellantName: string | null
    departmentId: string | null

    // 申诉内容
    appealReason: string
    appealType: AppealType
    evidenceUrls: string[]

    // 审核信息
    status: AppealStatus
    reviewerId: string | null
    reviewerName: string | null
    reviewComment: string | null
    reviewedAt: string | null

    // 时间戳
    createdAt: string
    updatedAt: string
}

/**
 * 创建申诉请求
 */
export interface AppealCreateRequest {
    qcResultId: string
    defectId: string
    recordId: string
    appealReason: string
    appealType: AppealType
    evidenceUrls?: string[]
}

/**
 * 更新申诉请求
 */
export interface AppealUpdateRequest {
    appealReason?: string
    appealType?: AppealType
    evidenceUrls?: string[]
}

/**
 * 审核申诉请求
 */
export interface AppealReviewRequest {
    decision: 'approve' | 'reject'
    comment: string
}

/**
 * 申诉列表响应
 */
export interface AppealListResponse {
    items: Appeal[]
    total: number
    page: number
    pageSize: number
    hasMore: boolean
}

/**
 * 申诉筛选条件
 */
export interface AppealFilters {
    status?: AppealStatus
    appealType?: AppealType
    appellantId?: string
    departmentId?: string
    startDate?: string
    endDate?: string
    page?: number
    pageSize?: number
}

/**
 * 申诉统计
 */
export interface AppealStats {
    totalCount: number
    pendingCount: number
    approvedCount: number
    rejectedCount: number
    withdrawnCount: number
    approvalRate: number
    avgReviewTimeHours: number
}

/**
 * 申诉类型选项
 */
export const APPEAL_TYPE_OPTIONS = [
    { value: AppealType.INCORRECT_RULE, label: '规则判定有误' },
    { value: AppealType.SPECIAL_CASE, label: '特殊情况' },
    { value: AppealType.OTHER, label: '其他' }
]

/**
 * 申诉状态选项
 */
export const APPEAL_STATUS_OPTIONS = [
    { value: AppealStatus.PENDING, label: '待审核', color: 'orange' },
    { value: AppealStatus.APPROVED, label: '已通过', color: 'green' },
    { value: AppealStatus.REJECTED, label: '已驳回', color: 'red' },
    { value: AppealStatus.WITHDRAWN, label: '已撤销', color: 'gray' }
]

/**
 * 获取申诉类型标签
 */
export function getAppealTypeLabel(type: AppealType): string {
    const option = APPEAL_TYPE_OPTIONS.find(opt => opt.value === type)
    return option?.label || type
}

/**
 * 获取申诉状态标签和颜色
 */
export function getAppealStatusInfo(status: AppealStatus): { label: string; color: string } {
    const option = APPEAL_STATUS_OPTIONS.find(opt => opt.value === status)
    return option || { label: status, color: 'default' }
}
