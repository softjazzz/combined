/**
 * 任务管理 API 服务
 *
 * 提供任务的创建、查询、抽样、分配、进度查看等功能
 */

import { useAuthStore } from '@/stores/auth'

const BASE_URL = '/api/v1/tasks'

/** 获取带认证的请求头 */
function getHeaders(): Record<string, string> {
    const authStore = useAuthStore()
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (authStore.token) {
        headers['Authorization'] = `Bearer ${authStore.token}`
    }
    return headers
}

/** 通用请求封装 */
async function request<T = any>(url: string, options: RequestInit = {}): Promise<{ success: boolean; data?: T; message?: string }> {
    try {
        const response = await fetch(url, {
            headers: getHeaders(),
            ...options,
        })
        const result = await response.json().catch(() => ({}))

        if (!response.ok) {
            return {
                success: false,
                message: result?.detail || result?.error || result?.message || response.statusText,
            }
        }

        return {
            success: result?.success !== false,
            data: result?.data || result,
            message: result?.message,
        }
    } catch (error: any) {
        return {
            success: false,
            message: error?.message || '网络异常或服务器不可用',
        }
    }
}

// ============= 类型定义 =============

export type TaskType = 'one_time' | 'scheduled'
export type TaskStatus = 'draft' | 'sampling' | 'assigned' | 'in_progress' | 'completed' | 'cancelled'
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

export interface TaskCreateData {
    task_name: string
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
    by_status: Record<string, number>
    draft: number
    in_progress: number
    completed: number
    cancelled: number
}

// ============= API 函数 =============

/** 获取任务列表 */
export async function getTaskList(params?: {
    tab?: 'all' | 'created' | 'received'
    status?: TaskStatus
    keyword?: string
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
    return request<TaskListResponse>(url)
}

/** 获取任务统计 */
export async function getTaskStats() {
    return request<TaskStats>(`${BASE_URL}/stats`)
}

/** 获取任务详情 */
export async function getTaskDetail(taskId: string) {
    return request<TaskItem & { records?: any[] }>(`${BASE_URL}/${taskId}`)
}

/** 创建任务 */
export async function createTask(data: TaskCreateData) {
    return request<TaskItem>(`${BASE_URL}`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

/** 更新任务 */
export async function updateTask(taskId: string, data: Partial<TaskCreateData & { status?: TaskStatus }>) {
    return request<TaskItem>(`${BASE_URL}/${taskId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    })
}

/** 执行抽样 */
export async function executeSampling(taskId: string) {
    return request(`${BASE_URL}/${taskId}/sample`, { method: 'POST' })
}

/** 分配任务 */
export async function assignTask(taskId: string, data: {
    assignees: Array<{ user_id: string; user_name: string; department?: string }>
    method?: AssignMethod
}) {
    return request(`${BASE_URL}/${taskId}/assign`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

/** 获取任务进度 */
export async function getTaskProgress(taskId: string) {
    return request<TaskProgress>(`${BASE_URL}/${taskId}/progress`)
}

/** 重新质控 */
export async function reAnalyzeTask(taskId: string) {
    return request(`${BASE_URL}/${taskId}/re-analyze`, { method: 'POST' })
}

/** 取消任务 */
export async function cancelTask(taskId: string) {
    return request(`${BASE_URL}/${taskId}/cancel`, { method: 'POST' })
}

/** 删除任务 */
export async function deleteTask(taskId: string) {
    return request(`${BASE_URL}/${taskId}`, { method: 'DELETE' })
}
