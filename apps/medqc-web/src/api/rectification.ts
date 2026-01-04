/**
 * 整改管理 API 服务
 * Rectification Management API
 */

import type {
    RectificationTask,
    RectificationTaskCreateRequest,
    RectificationTaskUpdateRequest,
    TaskAssignmentRequest,
    TaskSubmissionRequest,
    TaskReviewRequest,
    RectificationTaskListResponse,
    TaskFilters,
    TaskStats
} from '@/types/rectification'

const API_V1_PREFIX = '/api/v1'

/**
 * 创建整改任务
 */
export async function createRectificationTask(
    data: RectificationTaskCreateRequest
): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(data)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '创建整改任务失败')
    }

    return response.json()
}

/**
 * 获取整改任务列表
 */
export async function getRectificationTasks(
    filters: TaskFilters = {}
): Promise<RectificationTaskListResponse> {
    const queryParams = new URLSearchParams()

    if (filters.status) queryParams.append('status', filters.status)
    if (filters.severity) queryParams.append('severity', filters.severity)
    if (filters.assigneeId) queryParams.append('assignee_id', filters.assigneeId)
    if (filters.assignerId) queryParams.append('assigner_id', filters.assignerId)
    if (filters.departmentId) queryParams.append('department_id', filters.departmentId)
    if (filters.startDate) queryParams.append('start_date', filters.startDate)
    if (filters.endDate) queryParams.append('end_date', filters.endDate)
    if (filters.overdueOnly) queryParams.append('overdue_only', 'true')
    if (filters.page) queryParams.append('page', filters.page.toString())
    if (filters.pageSize) queryParams.append('page_size', filters.pageSize.toString())

    const url = `${API_V1_PREFIX}/rectifications${queryParams.toString() ? `?${queryParams}` : ''}`
    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取整改任务列表失败')
    }

    return response.json()
}

/**
 * 获取我的整改任务
 */
export async function getMyTasks(status?: string): Promise<RectificationTask[]> {
    const queryParams = new URLSearchParams()
    if (status) queryParams.append('status', status)

    const url = `${API_V1_PREFIX}/rectifications/my-tasks${queryParams.toString() ? `?${queryParams}` : ''}`
    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取我的任务失败')
    }

    return response.json()
}

/**
 * 获取整改任务详情
 */
export async function getRectificationTask(taskId: string): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications/${taskId}`, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取整改任务详情失败')
    }

    return response.json()
}

/**
 * 更新整改任务
 */
export async function updateRectificationTask(
    taskId: string,
    data: RectificationTaskUpdateRequest
): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications/${taskId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(data)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '更新整改任务失败')
    }

    return response.json()
}

/**
 * 分配/重新分配整改任务
 */
export async function assignTask(
    taskId: string,
    assignment: TaskAssignmentRequest
): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications/${taskId}/assign`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(assignment)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '分配任务失败')
    }

    return response.json()
}

/**
 * 提交整改
 */
export async function submitRectification(
    taskId: string,
    submission: TaskSubmissionRequest
): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications/${taskId}/submit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(submission)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '提交整改失败')
    }

    return response.json()
}

/**
 * 验收整改
 */
export async function reviewRectification(
    taskId: string,
    review: TaskReviewRequest
): Promise<RectificationTask> {
    const response = await fetch(`${API_V1_PREFIX}/rectifications/${taskId}/review`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(review)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '验收整改失败')
    }

    return response.json()
}

/**
 * 获取整改任务统计
 */
export async function getTaskStats(filters: {
    departmentId?: string
    assigneeId?: string
    startDate?: string
    endDate?: string
} = {}): Promise<TaskStats> {
    const queryParams = new URLSearchParams()

    if (filters.departmentId) queryParams.append('department_id', filters.departmentId)
    if (filters.assigneeId) queryParams.append('assignee_id', filters.assigneeId)
    if (filters.startDate) queryParams.append('start_date', filters.startDate)
    if (filters.endDate) queryParams.append('end_date', filters.endDate)

    const url = `${API_V1_PREFIX}/rectifications/stats${queryParams.toString() ? `?${queryParams}` : ''}`
    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取整改统计失败')
    }

    return response.json()
}

/**
 * 获取认证token
 * TODO: 根据实际的认证方案获取token
 */
function getAuthToken(): string {
    // 从localStorage或者store中获取token
    return localStorage.getItem('access_token') || ''
}
