/**
 * 整改管理类型定义
 * Rectification Management Types
 */

/**
 * 任务严重程度
 */
export enum TaskSeverity {
    CRITICAL = 'critical',  // 严重
    MAJOR = 'major',        // 重要
    MINOR = 'minor'         // 一般
}

/**
 * 任务状态
 */
export enum TaskStatus {
    PENDING = 'pending',            // 待处理
    IN_PROGRESS = 'in_progress',    // 进行中
    SUBMITTED = 'submitted',         // 已提交
    APPROVED = 'approved',           // 已通过
    REJECTED = 'rejected'            // 未通过
}

/**
 * 验收结果
 */
export enum ReviewResult {
    PASS = 'pass',      // 通过
    FAIL = 'fail'       // 不通过
}

/**
 * 整改任务详情
 */
export interface RectificationTask {
    id: string
    qcResultId: string
    defectId: string
    recordId: string
    appealId: string | null

    // 任务信息
    taskTitle: string
    taskDescription: string
    defectType: string
    severity: TaskSeverity

    // 分配信息
    assigneeId: string
    assigneeName: string | null
    assignerId: string | null
    assignerName: string | null
    departmentId: string | null
    dueDate: string | null

    // 状态
    status: TaskStatus

    // 整改内容
    rectificationContent: string | null
    rectificationFiles: string[]
    submittedAt: string | null

    // 验收信息
    reviewerId: string | null
    reviewerName: string | null
    reviewComment: string | null
    reviewResult: ReviewResult | null
    reviewedAt: string | null

    // 时间戳
    createdAt: string
    updatedAt: string
    completedAt: string | null
}

/**
 * 创建整改任务请求
 */
export interface RectificationTaskCreateRequest {
    qcResultId: string
    defectId: string
    recordId: string
    appealId?: string
    taskTitle: string
    taskDescription: string
    defectType: string
    severity: TaskSeverity
    assigneeId: string
    assigneeName?: string
    departmentId?: string
    dueDate?: string
}

/**
 * 更新整改任务请求
 */
export interface RectificationTaskUpdateRequest {
    taskTitle?: string
    taskDescription?: string
    severity?: TaskSeverity
    dueDate?: string
    status?: TaskStatus
}

/**
 * 任务分配请求
 */
export interface TaskAssignmentRequest {
    assigneeId: string
    assigneeName?: string
    comment?: string
}

/**
 * 提交整改请求
 */
export interface TaskSubmissionRequest {
    rectificationContent: string
    rectificationFiles?: string[]
}

/**
 * 验收整改请求
 */
export interface TaskReviewRequest {
    reviewResult: ReviewResult
    reviewComment: string
}

/**
 * 整改任务列表响应
 */
export interface RectificationTaskListResponse {
    items: RectificationTask[]
    total: number
    page: number
    pageSize: number
    hasMore: boolean
}

/**
 * 整改任务筛选条件
 */
export interface TaskFilters {
    status?: TaskStatus
    severity?: TaskSeverity
    assigneeId?: string
    assignerId?: string
    departmentId?: string
    startDate?: string
    endDate?: string
    overdueOnly?: boolean
    page?: number
    pageSize?: number
}

/**
 * 整改任务统计
 */
export interface TaskStats {
    totalCount: number
    pendingCount: number
    inProgressCount: number
    submittedCount: number
    approvedCount: number
    rejectedCount: number
    overdueCount: number
    completionRate: number
    avgCompletionTimeHours: number
    onTimeRate: number
}

/**
 * 任务严重程度选项
 */
export const TASK_SEVERITY_OPTIONS = [
    { value: TaskSeverity.CRITICAL, label: '严重', color: 'red' },
    { value: TaskSeverity.MAJOR, label: '重要', color: 'orange' },
    { value: TaskSeverity.MINOR, label: '一般', color: 'blue' }
]

/**
 * 任务状态选项
 */
export const TASK_STATUS_OPTIONS = [
    { value: TaskStatus.PENDING, label: '待处理', color: 'default' },
    { value: TaskStatus.IN_PROGRESS, label: '进行中', color: 'blue' },
    { value: TaskStatus.SUBMITTED, label: '已提交', color: 'cyan' },
    { value: TaskStatus.APPROVED, label: '已通过', color: 'green' },
    { value: TaskStatus.REJECTED, label: '未通过', color: 'red' }
]

/**
 * 获取任务严重程度标签和颜色
 */
export function getTaskSeverityInfo(severity: TaskSeverity): { label: string; color: string } {
    const option = TASK_SEVERITY_OPTIONS.find(opt => opt.value === severity)
    return option || { label: severity, color: 'default' }
}

/**
 * 获取任务状态标签和颜色
 */
export function getTaskStatusInfo(status: TaskStatus): { label: string; color: string } {
    const option = TASK_STATUS_OPTIONS.find(opt => opt.value === status)
    return option || { label: status, color: 'default' }
}

/**
 * 判断任务是否逾期
 */
export function isTaskOverdue(task: RectificationTask): boolean {
    if (!task.dueDate || task.status === TaskStatus.APPROVED) {
        return false
    }
    return new Date(task.dueDate) < new Date()
}

/**
 * 计算任务剩余时间 (小时)
 */
export function getTaskRemainingHours(task: RectificationTask): number | null {
    if (!task.dueDate || task.status === TaskStatus.APPROVED) {
        return null
    }
    const now = new Date().getTime()
    const due = new Date(task.dueDate).getTime()
    return Math.floor((due - now) / (1000 * 60 * 60))
}
