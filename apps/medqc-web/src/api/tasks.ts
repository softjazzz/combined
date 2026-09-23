/**
 * 任务管理 API 服务
 *
 * 提供任务的创建、查询、抽样、分配、进度查看等功能
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

const BASE_URL = '/api/v1/tasks'

/** 通用请求封装 */
async function request<T = any>(
    config: Parameters<typeof ApiService.requestRaw>[0]
): Promise<{ success: boolean; data?: T; message?: string }> {
    try {
        const response = await ApiService.requestRaw<T>(config)
        const normalized = normalizeApiSuccess<T>(response.data)
        return {
            success: normalized.success,
            data: normalized.data,
            message: normalized.message,
        }
    } catch (error) {
        return {
            success: false,
            message: extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
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
export type AssignMethod = 'keep' | 'by_department' | 'by_ratio' | 'by_type'

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
    deadline?: string
    sampling_method?: SamplingMethod
    assign_method?: AssignMethod
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
    assignee_id?: string | null
    assignee_name?: string | null
    status: string | null
    score?: number | null
    defect_count?: number | null
    created_at?: string | null
    completed_at?: string | null
    error_message?: string | null
}

export interface TaskDetail extends TaskItem {
    records: TaskRecordItem[]
}

export interface TaskCreateData {
    task_name: string
    scene: TaskScene
    task_type?: TaskType
    schedule_config?: Record<string, any>
    date_range?: { start?: string; end?: string }
    department_filter?: string[]
    record_ids?: string[]
    sampling_method?: SamplingMethod
    sampling_config?: Record<string, any>
    assign_method?: AssignMethod
    assignee_config?: Record<string, any>
    deadline?: string
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

/** 创建任务 */
export async function createTask(data: TaskCreateData) {
    return request<TaskItem>({
        method: 'POST',
        url: `${BASE_URL}`,
        data,
    })
}

/** 更新任务 */
export type TaskUpdateData = Omit<Partial<TaskCreateData>, 'scene'> & { status?: TaskStatus }

export async function updateTask(taskId: string, data: TaskUpdateData) {
    return request<TaskItem>({
        method: 'PUT',
        url: `${BASE_URL}/${taskId}`,
        data,
    })
}

/** 执行抽样 */
export async function executeSampling(taskId: string) {
    return request({ method: 'POST', url: `${BASE_URL}/${taskId}/sample` })
}

/** 分配任务 */
export async function assignTask(taskId: string, data: {
    assignees: Array<{ user_id: string; user_name: string; department?: string }>
    method?: AssignMethod
}) {
    return request({
        method: 'POST',
        url: `${BASE_URL}/${taskId}/assign`,
        data,
    })
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
