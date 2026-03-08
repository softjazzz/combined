/**
 * 缺陷操作 API 服务
 *
 * 提供缺陷的催办、撤回、标记整改、审核通过、审核存疑等操作
 */

import { useAuthStore } from '@/stores/auth'

const BASE_URL = '/api/v1/qc/defects'

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

export interface DefectItem {
    id: string
    record_id: string
    patient_name?: string
    department?: string
    rule_name: string
    description: string
    severity: 'critical' | 'error' | 'warning' | 'info'
    category: string
    location: string
    suggestion: string
    status: 'pending' | 'urged' | 'remediated' | 'approved' | 'rejected'
    created_at: string
    urged_at?: string
    remediated_at?: string
    approved_at?: string
}

export interface DefectListResponse {
    items: DefectItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
}

export interface DefectStats {
    total: number
    by_severity: Record<string, number>
    by_category: Record<string, number>
    by_status: Record<string, number>
}

// ============= API 函数 =============

/** 获取缺陷列表 */
export async function getDefectList(params?: {
    record_id?: string
    department?: string
    severity?: string
    category?: string
    status?: string
    start_date?: string
    end_date?: string
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
    return request<DefectListResponse>(url)
}

/** 催办缺陷 */
export async function urgeDefect(defectId: string, data: { message?: string; deadline?: string }) {
    return request(`${BASE_URL}/${defectId}/urge`, {
        method: 'POST',
        body: JSON.stringify({
            message: data.message || '请尽快完成整改',
            deadline: data.deadline,
        }),
    })
}

/** 撤回催办 */
export async function cancelUrgeDefect(defectId: string, reason?: string) {
    return request(`${BASE_URL}/${defectId}/cancel-urge`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
    })
}

/** 标记已整改 */
export async function markDefectRemediated(defectId: string, data: { remediation_note: string; evidence?: string[] }) {
    return request(`${BASE_URL}/${defectId}/mark-remediated`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

/** 审核通过 */
export async function approveDefect(defectId: string, comment?: string) {
    return request(`${BASE_URL}/${defectId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ comment }),
    })
}

/** 审核存疑（退回） */
export async function rejectDefect(defectId: string, data: { reason: string; suggestion?: string }) {
    return request(`${BASE_URL}/${defectId}/reject`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

/** 批量操作 */
export async function batchDefectAction(data: { defect_ids: string[]; action: 'approve' | 'reject' | 'urge'; message?: string }) {
    return request(`${BASE_URL}/batch-action`, {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

/** 导出缺陷列表 */
export function getDefectExportUrl(params?: {
    format?: string
    max_rows?: number
    record_id?: string
    department?: string
    severity?: string
    category?: string
    status?: string
    start_date?: string
    end_date?: string
}) {
    const queryParams = new URLSearchParams()
    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                queryParams.append(key, String(value))
            }
        })
    }
    return `${BASE_URL}/export${queryParams.toString() ? '?' + queryParams.toString() : ''}`
}

/** 下载导出文件 */
export async function exportDefects(params?: Parameters<typeof getDefectExportUrl>[0]) {
    const url = getDefectExportUrl(params)
    const authStore = useAuthStore()
    try {
        const response = await fetch(url, {
            headers: {
                ...(authStore.token ? { 'Authorization': `Bearer ${authStore.token}` } : {}),
            },
        })
        if (!response.ok) {
            return { success: false, message: '导出失败' }
        }
        // 下载文件
        const blob = await response.blob()
        const disposition = response.headers.get('Content-Disposition')
        const filename = disposition?.match(/filename="?(.+?)"?$/)?.[1] || `缺陷列表.${params?.format || 'xlsx'}`
        const link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(link.href)
        return { success: true, message: '导出成功' }
    } catch (error: any) {
        return { success: false, message: error?.message || '导出失败' }
    }
}

/** 获取缺陷统计 */
export async function getDefectStats(params?: {
    record_id?: string
    department?: string
    start_date?: string
    end_date?: string
}) {
    const queryParams = new URLSearchParams()
    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== '') {
                queryParams.append(key, String(value))
            }
        })
    }
    const url = `${BASE_URL}/stats${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return request<DefectStats>(url)
}
