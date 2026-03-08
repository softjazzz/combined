/**
 * Dashboard 统计 API 服务
 *
 * 提供待办统计、工作表现排名、概览数据
 */

import { useAuthStore } from '@/stores/auth'

const BASE_URL = '/api/v1/dashboard'

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
async function request<T = any>(url: string): Promise<{ success: boolean; data?: T; message?: string }> {
    try {
        const response = await fetch(url, { headers: getHeaders() })
        const result = await response.json().catch(() => ({}))

        if (!response.ok) {
            return {
                success: false,
                message: result?.detail || result?.error || response.statusText,
            }
        }

        return {
            success: result?.success !== false,
            data: result?.data || result,
            message: result?.message,
        }
    } catch (error: any) {
        return { success: false, message: error?.message || '网络异常' }
    }
}

// ============= 类型定义 =============

export interface TodoStats {
    task_stats: {
        countdown: number
        in_progress: number
        not_started: number
    }
    defect_stats: {
        clinical_appeals: number
        pending_review: number
        urged: number
    }
    record_stats: {
        pending_review: number
        pending_recheck: number
        total: number
    }
    overview?: {
        total_records: number
        avg_score: number
        pass_rate: number
        total_defects?: number
        grade_a?: number
        grade_b?: number
        grade_c?: number
    }
    department_breakdown?: Record<string, number>
}

export interface RankingItem {
    name: string
    count: number
    rank: number
}

export interface PerformanceData {
    defect_ranking: RankingItem[]
    record_ranking: RankingItem[]
    period: string
    period_label: string
}

export interface DashboardOverview {
    total_records: number
    avg_score: number
    pass_rate: number
    grade_distribution: Record<string, number>
    department_stats: Record<string, number>
    total_defects?: number
}

// ============= API 函数 =============

/** 获取待办统计 */
export async function getTodoStats() {
    return request<TodoStats>(`${BASE_URL}/todo-stats`)
}

/** 获取工作表现排名 */
export async function getPerformanceRanking(period: 'this_week' | 'last_week' | 'this_month' = 'this_week') {
    return request<PerformanceData>(`${BASE_URL}/performance?period=${period}`)
}

/** 获取概览数据 */
export async function getDashboardOverview() {
    return request<DashboardOverview>(`${BASE_URL}/overview`)
}
