/**
 * 任务管理 API 服务
 *
 * 提供任务的创建、查询、抽样、分配、进度查看等功能
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/tasks'

/** 结构化业务错误（如 409 `{code, message, ...}`），额外字段原样保留供调用方展示。 */
export interface TaskApiErrorDetail {
    code: string
    message?: string
    /** original_reviewer_unmatched：不匹配的病历数 */
    unmatched_count?: number
    /** department_unassigned：没有对应受领人的科室 */
    departments?: string[]
    /** method_unavailable：不可用原因 */
    reason?: string
}

/**
 * 读取结构化错误 detail。
 * 后端统一异常包装把 HTTPException.detail 放在 `error` 字段；直连 FastAPI 时位于 `detail`。
 */
function extractTaskErrorDetail(error: unknown): TaskApiErrorDetail | undefined {
    if (!isAxiosError(error)) return undefined
    const body: unknown = error.response?.data
    if (typeof body !== 'object' || body === null) return undefined
    for (const key of ['detail', 'error'] as const) {
        const candidate: unknown = (body as Record<string, unknown>)[key]
        if (typeof candidate !== 'object' || candidate === null) continue
        const raw = candidate as Record<string, unknown>
        if (typeof raw.code !== 'string' || !raw.code.trim()) continue
        const detail: TaskApiErrorDetail = { code: raw.code }
        if (typeof raw.message === 'string' && raw.message.trim()) detail.message = raw.message
        if (typeof raw.reason === 'string' && raw.reason.trim()) detail.reason = raw.reason
        if (typeof raw.unmatched_count === 'number' && Number.isInteger(raw.unmatched_count) && raw.unmatched_count >= 0) {
            detail.unmatched_count = raw.unmatched_count
        }
        if (Array.isArray(raw.departments)) {
            const departments = raw.departments.filter((item): item is string => typeof item === 'string' && !!item.trim())
            if (departments.length) detail.departments = departments
        }
        return detail
    }
    return undefined
}

/** 通用请求封装 */
async function request<T = any>(
    config: Parameters<typeof ApiService.requestRaw>[0]
): Promise<{ success: boolean; data?: T; message?: string; status?: number; code?: string; errorDetail?: TaskApiErrorDetail }> {
    try {
        const response = await ApiService.requestRaw<T>(config)
        const normalized = normalizeApiSuccess<T>(response.data)
        return {
            success: normalized.success,
            data: normalized.data,
            message: normalized.message,
            ...(response.status === 404 ? { status: 404 } : {}),
        }
    } catch (error) {
        const detail = extractTaskErrorDetail(error)
        return {
            success: false,
            message: detail?.message || extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
            status: isAxiosError(error) ? error.response?.status : undefined,
            ...(detail ? { code: detail.code, errorDetail: detail } : {}),
        }
    }
}

// ============= 类型定义 =============

export type TaskType = 'one_time' | 'scheduled'
export type TaskStatus = 'draft' | 'sampling' | 'assigned' | 'in_progress' | 'completed' | 'cancelled'
export type TaskTab = 'all' | 'created' | 'received'
export type TaskTodo = 'assigned' | 'in_progress' | 'due_soon'
export type TaskScene = 'running' | 'final' | 'outpatient'
export type TaskSceneFilter = TaskScene | 'unclassified'
export type SamplingMethod = 'all' | 'count' | 'percentage'
export type AssignMethod = 'keep' | 'by_department' | 'by_ratio' | 'by_type' | 'by_original_reviewer'
/** 新建任务与分配接口当前可用的分配方式（病历类型不可用，见 V3.6 分配策略合同）。 */
export type TaskAssignableMethod = 'by_ratio' | 'by_original_reviewer' | 'by_department'
/** 原质控员策略下，病历无原质控员或其不在选定人中时的处理方式。 */
export type AssignFallback = 'by_ratio' | 'reject'

export interface TaskAssignConfig {
    fallback?: AssignFallback
}

export interface TaskItem {
    id: string
    task_number: string
    task_name: string
    task_type: TaskType
    status: TaskStatus
    progress: number
    total_records: number
    completed_records: number
    creator_id: string
    creator_name: string
    scene?: TaskScene | null
    rule_set_key?: string | null
    rule_set_version?: string | null
    deadline?: string
    sampling_method?: SamplingMethod
    sampling_config?: Record<string, unknown> | null
    assign_method?: AssignMethod
    /** 后端既有字段；by_original_reviewer 的 fallback 存于此（合同中记作 assign_config.fallback） */
    assignee_config?: TaskAssignConfig | null
    date_range?: { start?: string; end?: string }
    department_filter?: string[]
    created_at: string
    updated_at: string
}

export interface TaskListResponse {
    items: TaskItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
}

export interface TaskRecordItem {
    id: string
    task_id: string
    record_id: string | null
    institute_id?: string | null
    patient_id?: string | null
    visit_id?: string | null
    assignee_id?: string | null
    assignee_name?: string | null
    status: string | null
    score?: number | null
    defect_count?: number | null
    created_at?: string | null
    completed_at?: string | null
    error_message?: string | null
}

export interface TaskRecordStartResult {
    task_id: string
    task_record_id: string
    status: 'in_progress'
    idempotent?: boolean
}

export interface TaskRecordCompleteResult {
    task_id: string
    task_record_id: string
    status: 'completed'
    run_number: number
    idempotent: boolean
    score: number | null
    defect_count: number | null
}

export interface TaskRecordSyncStarted {
    job_id: string
    status: 'queued' | 'running'
    reused: boolean
}

export interface TaskRecordSyncResult {
    job_id: string
    status: 'queued' | 'running' | 'completed' | 'failed'
    total: number
    ready_count: number
    failed_count: number
    contract_version: 'task-record-sync-v1'
    records: Array<{
        task_record_id: string
        status: 'ready' | 'failed'
        reason_code?: string | null
    }>
}

export interface TaskDetail extends TaskItem {
    records: TaskRecordItem[]
}

export interface TaskQcRun {
    task_id: string
    run_number: number
    job_id: string
    triggered_by: string
    run_scope: TaskQcRunScope
    created_at: string
}

export type TaskQcRunScope = 'all' | 'assigned'

export interface TaskQcRunCreated {
    task_id: string
    run_number: number
    job_id: string
    run_scope: TaskQcRunScope
    status: 'queued'
}

export interface TaskQcRunRecordResult {
    task_id: string
    run_number: number
    task_record_id: string
    job_id: string
    job_status: string
    result_state: 'pending' | 'available' | 'unavailable'
    rule_set_key: string
    items: TaskQcSafeResultItem[]
}

export type TaskManualDefectSeverity = 'info' | 'warning' | 'error' | 'critical'

export interface TaskManualDefectCreate {
    defect_id: string
    run_number: number
    rule_name: string
    description: string
    severity: TaskManualDefectSeverity
    suggestion?: string | null
    evidence?: string | null
}

export interface TaskManualDefect {
    id: string
    task_id: string
    task_record_id: string
    run_number: number
    rule_name: string
    description: string
    severity: TaskManualDefectSeverity
    suggestion: string | null
    evidence: string | null
    manual_review_status: 'pending' | 'approved' | 'rejected'
    created_at: string
    idempotent?: boolean
}

export interface TaskManualDefectList {
    items: TaskManualDefect[]
    total: number
    limit: number
    offset: number
}

export interface TaskQcSafeResultItem {
    rule_id?: string
    rule_code?: string
    qc_point_id?: string
    rule_name?: string
    status: string
    result_status?: string
    display_status?: string
    is_compliant?: boolean | null
    conclusion?: string
    findings?: string
    suggestion?: string
    evidence?: string[] | TaskQcSafeEvidenceRef[]
}

export interface TaskQcSafeEvidenceRef {
    source_type: string
    source_ref: string
    field_path?: string
    evidence_excerpt?: string
    excerpt_kind?: string
    record_time?: string
}

export interface TaskCreateData {
    task_name: string
    scene: TaskScene
    rule_set_key: string
    task_type?: TaskType
    schedule_config?: Record<string, any>
    date_range?: { start?: string; end?: string }
    department_filter?: string[]
    record_ids?: string[]
    record_refs?: TaskCaseRef[]
    sampling_method?: SamplingMethod
    sampling_config?: Record<string, any>
    assign_method?: AssignMethod
    /** 仅 by_original_reviewer 需要 fallback（合同中记作 assign_config.fallback，后端沿用 assignee_config） */
    assignee_config?: TaskAssignConfig
    deadline?: string
}

export interface TaskRuleSetOption {
    rule_set_key: string
    rule_set_name: string
    rule_set_version: string
    scope: string
}

export interface TaskAssigneeOption {
    user_id: string
    user_name: string
    department?: string | null
}

export interface TaskCaseRef {
    institute_id: string
    patient_id: string
    visit_id: string
}

export interface TaskProgress {
    task_id: string
    task_name: string
    total_records: number
    completed_records: number
    progress_pct: number
    pending_count: number
    working_count: number
    done_count: number
    avg_score?: number
    total_defects: number
}

export interface TaskStats {
    total: number
    by_status: Partial<Record<TaskStatus, number>>
    draft: number
    in_progress: number
    completed: number
    cancelled: number
}

export interface TaskTodoStats {
    as_of: string
    assigned: number
    in_progress: number
    due_soon: number
}

// ============= API 函数 =============

/** 获取任务列表 */
export async function getTaskList(params?: {
    tab?: TaskTab
    status?: TaskStatus
    keyword?: string
    todo?: TaskTodo
    as_of?: string
    scene?: TaskSceneFilter
    page?: number
    page_size?: number
}) {
    const queryParams = new URLSearchParams()
    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                queryParams.append(key, String(value))
            }
        })
    }
    const url = `${BASE_URL}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return request<TaskListResponse>({ method: 'GET', url })
}

/** 获取任务统计 */
export async function getTaskStats(params?: { tab?: TaskTab; scene?: TaskSceneFilter }) {
    const queryParams = new URLSearchParams()
    if (params?.tab) {
        queryParams.set('tab', params.tab)
    }
    if (params?.scene) {
        queryParams.set('scene', params.scene)
    }
    const query = queryParams.toString()
    return request<TaskStats>({
        method: 'GET',
        url: `${BASE_URL}/stats${query ? `?${query}` : ''}`,
    })
}

/** 获取当前用户任务待办统计，省略 scene 时覆盖全部场景 */
export async function getTaskTodoStats(params?: { scene?: TaskSceneFilter }) {
    const query = params?.scene ? `?scene=${encodeURIComponent(params.scene)}` : ''
    return request<TaskTodoStats>({ method: 'GET', url: `${BASE_URL}/todo-stats${query}` })
}

/** 获取任务详情；received 仅返回当前用户获分配的病历清单 */
export async function getTaskDetail(taskId: string, params?: { tab?: TaskTab }) {
    const query = params?.tab ? `?tab=${encodeURIComponent(params.tab)}` : ''
    return request<TaskDetail>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}${query}`,
    })
}

/** 当前受领人开始处理单份任务病历，任务运行批次状态不受此接口影响。 */
export async function startTaskRecord(taskId: string, taskRecordId: string) {
    return request<TaskRecordStartResult>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/records/${encodeURIComponent(taskRecordId)}/start`,
    })
}

/** 受领质控员显式完成病历处理；必须指定已核实的运行批次。 */
export async function completeTaskRecord(taskId: string, taskRecordId: string, runNumber: number) {
    return request<TaskRecordCompleteResult>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/records/${encodeURIComponent(taskRecordId)}/complete`,
        data: { run_number: runNumber },
    })
}

/** 受领任务病历的人工缺陷；defect_id 由客户端生成，供不确定响应安全重试。 */
export async function createTaskManualDefect(taskId: string, taskRecordId: string, data: TaskManualDefectCreate) {
    return request<TaskManualDefect>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/records/${encodeURIComponent(taskRecordId)}/manual-defects`,
        data,
    })
}

export async function getTaskManualDefects(taskId: string, taskRecordId: string, limit = 50, offset = 0) {
    return request<TaskManualDefectList>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/records/${encodeURIComponent(taskRecordId)}/manual-defects`,
        params: { limit, offset },
    })
}

/** 创建人显式将任务病例同步到本地工作区；不会自动启动质控。 */
export async function syncTaskRecords(taskId: string) {
    return request<TaskRecordSyncStarted>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/sync-records`,
    })
}

export async function getTaskRecordSyncJob(taskId: string, jobId: string) {
    return request<TaskRecordSyncResult>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/sync-records/${encodeURIComponent(jobId)}`,
    })
}

export async function getLatestTaskRecordSyncJob(taskId: string) {
    return request<TaskRecordSyncResult>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/sync-records/latest`,
        validateStatus: (status) => status >= 200 && status < 300 || status === 404,
    })
}

/** all 为创建人整批，assigned 为当前用户受领子集。 */
export async function getTaskQcRuns(taskId: string, scope?: TaskQcRunScope) {
    return request<TaskQcRun[]>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/qc-runs${scope ? `?scope=${scope}` : ''}`,
    })
}

export async function createTaskQcRun(taskId: string, scope?: TaskQcRunScope) {
    return request<TaskQcRunCreated>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/qc-runs${scope ? `?scope=${scope}` : ''}`,
    })
}

/** 按指定运行批次和任务病历关联读取客户安全结果，不查询最新批次。 */
export async function getTaskQcRunRecordResult(
    taskId: string,
    runNumber: number,
    taskRecordId: string,
    scope: TaskQcRunScope,
) {
    return request<TaskQcRunRecordResult>({
        method: 'GET',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/qc-runs/${encodeURIComponent(String(runNumber))}/records/${encodeURIComponent(taskRecordId)}?scope=${scope}`,
    })
}

/** 创建任务 */
export async function createTask(data: TaskCreateData) {
    return request<TaskItem>({
        method: 'POST',
        url: `${BASE_URL}`,
        data,
    })
}

/** 获取工作区已发布规则集；请求失败与空目录由调用方分别处理 */
export async function getTaskRuleSets() {
    return request<{ items: TaskRuleSetOption[] }>({
        method: 'GET',
        url: '/api/v1/qc/sichuan/workspace/rule-sets',
    })
}

/** 开始已受领任务 */
export type TaskUpdateData = { status: 'in_progress' }

export interface TaskStartResult {
    id: string
    status: 'in_progress'
    updated_at?: string | null
    idempotent?: boolean
}

export async function updateTask(taskId: string, data: TaskUpdateData) {
    return request<TaskStartResult>({
        method: 'PUT',
        url: `${BASE_URL}/${taskId}`,
        data,
    })
}

/** 执行抽样 */
export async function executeSampling(taskId: string) {
    return request({ method: 'POST', url: `${BASE_URL}/${taskId}/sample` })
}

/** 每人通过哪种途径获得病历；字段缺失表示后端未提供，不代表 0。 */
export interface TaskAssignReasonCounts {
    original_reviewer?: number
    department?: number
    ratio_fallback?: number
}

export interface TaskAssignmentDetail {
    user_id: string
    user_name: string
    department?: string | null
    count: number
    reason_counts?: TaskAssignReasonCounts
}

export interface TaskAssignResult {
    task_id?: string
    total_assigned: number
    assignment_summary?: Record<string, number>
    assignment_details?: TaskAssignmentDetail[]
    idempotent?: boolean
}

export interface TaskBatchAssignTarget {
    task_id: string
    method: TaskAssignableMethod
    fallback?: AssignFallback
}

export interface TaskBatchAssignItem {
    task_id: string
    success: boolean
    status?: number
    code?: string
    message?: string
    details?: Record<string, unknown>
    result?: TaskAssignResult
}

export interface TaskBatchAssignResult {
    total: number
    success_count: number
    failed_count: number
    atomic: false
    items: TaskBatchAssignItem[]
}

/** 分配任务；fallback 仅 by_original_reviewer 使用 */
export async function assignTask(taskId: string, data: {
    assignees: Array<{ user_id: string; user_name: string; department?: string }>
    method?: AssignMethod
    fallback?: AssignFallback
}) {
    return request<TaskAssignResult>({
        method: 'POST',
        url: `${BASE_URL}/${encodeURIComponent(taskId)}/assign`,
        data,
    })
}

/** 批量分配任务；服务端逐任务独立事务，响应逐项报告成功与失败。 */
export async function assignTasksBatch(data: {
    tasks: TaskBatchAssignTarget[]
    assignees: Array<{ user_id: string; user_name: string; department?: string }>
}) {
    return request<TaskBatchAssignResult>({
        method: 'POST',
        url: `${BASE_URL}/batch-assign`,
        data,
    })
}

/** 可分配质控员目录；空目录与请求失败由页面分别呈现。 */
export async function getTaskAssigneeOptions() {
    return request<TaskAssigneeOption[]>({ method: 'GET', url: `${BASE_URL}/assignee-options` })
}

/** 获取任务进度 */
export async function getTaskProgress(taskId: string) {
    return request<TaskProgress>({ method: 'GET', url: `${BASE_URL}/${taskId}/progress` })
}

/** 重新质控 */
export async function reAnalyzeTask(taskId: string) {
    return request({ method: 'POST', url: `${BASE_URL}/${taskId}/re-analyze` })
}

/** 取消任务 */
export async function cancelTask(taskId: string) {
    return request({ method: 'POST', url: `${BASE_URL}/${taskId}/cancel` })
}

/** 删除任务 */
export async function deleteTask(taskId: string) {
    return request({ method: 'DELETE', url: `${BASE_URL}/${taskId}` })
}
