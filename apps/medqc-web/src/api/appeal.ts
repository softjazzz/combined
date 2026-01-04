/**
 * 申诉管理 API 服务
 * Appeal Management API
 */

import type {
    Appeal,
    AppealCreateRequest,
    AppealUpdateRequest,
    AppealReviewRequest,
    AppealListResponse,
    AppealFilters,
    AppealStats
} from '@/types/appeal'

const API_V1_PREFIX = '/api/v1'

/**
 * 创建申诉
 */
export async function createAppeal(data: AppealCreateRequest): Promise<Appeal> {
    const response = await fetch(`${API_V1_PREFIX}/appeals`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(data)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '创建申诉失败')
    }

    return response.json()
}

/**
 * 获取申诉列表
 */
export async function getAppeals(filters: AppealFilters = {}): Promise<AppealListResponse> {
    const queryParams = new URLSearchParams()

    if (filters.status) queryParams.append('status', filters.status)
    if (filters.appealType) queryParams.append('appeal_type', filters.appealType)
    if (filters.appellantId) queryParams.append('appellant_id', filters.appellantId)
    if (filters.departmentId) queryParams.append('department_id', filters.departmentId)
    if (filters.startDate) queryParams.append('start_date', filters.startDate)
    if (filters.endDate) queryParams.append('end_date', filters.endDate)
    if (filters.page) queryParams.append('page', filters.page.toString())
    if (filters.pageSize) queryParams.append('page_size', filters.pageSize.toString())

    const url = `${API_V1_PREFIX}/appeals${queryParams.toString() ? `?${queryParams}` : ''}`
    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取申诉列表失败')
    }

    return response.json()
}

/**
 * 获取申诉详情
 */
export async function getAppeal(appealId: string): Promise<Appeal> {
    const response = await fetch(`${API_V1_PREFIX}/appeals/${appealId}`, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取申诉详情失败')
    }

    return response.json()
}

/**
 * 更新申诉
 */
export async function updateAppeal(
    appealId: string,
    data: AppealUpdateRequest
): Promise<Appeal> {
    const response = await fetch(`${API_V1_PREFIX}/appeals/${appealId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(data)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '更新申诉失败')
    }

    return response.json()
}

/**
 * 审核申诉
 */
export async function reviewAppeal(
    appealId: string,
    review: AppealReviewRequest
): Promise<Appeal> {
    const response = await fetch(`${API_V1_PREFIX}/appeals/${appealId}/review`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(review)
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '审核申诉失败')
    }

    return response.json()
}

/**
 * 撤销申诉
 */
export async function withdrawAppeal(appealId: string): Promise<Appeal> {
    const response = await fetch(`${API_V1_PREFIX}/appeals/${appealId}/withdraw`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '撤销申诉失败')
    }

    return response.json()
}

/**
 * 获取申诉统计
 */
export async function getAppealStats(filters: {
    departmentId?: string
    startDate?: string
    endDate?: string
} = {}): Promise<AppealStats> {
    const queryParams = new URLSearchParams()

    if (filters.departmentId) queryParams.append('department_id', filters.departmentId)
    if (filters.startDate) queryParams.append('start_date', filters.startDate)
    if (filters.endDate) queryParams.append('end_date', filters.endDate)

    const url = `${API_V1_PREFIX}/appeals/stats${queryParams.toString() ? `?${queryParams}` : ''}`
    const response = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${getAuthToken()}`
        }
    })

    if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '获取申诉统计失败')
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
