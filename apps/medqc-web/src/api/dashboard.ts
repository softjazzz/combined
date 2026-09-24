/**
 * Dashboard 统计 API 服务
 *
 * 提供待办统计、工作表现排名、概览数据
 */

import { ApiService } from '@/services/apiService'
import {
  extractApiErrorMessageFromError,
  normalizeApiSuccess,
} from '@/utils/api-envelope'

const BASE_URL = '/api/v1/dashboard'
export type DashboardScene = 'all' | 'outpatient_emergency' | 'running' | 'final'

async function request<T = any>(
  config: Parameters<typeof ApiService.requestRaw>[0],
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
      message: extractApiErrorMessageFromError(error, '网络异常'),
    }
  }
}

// ============= 类型定义 =============

export interface TodoStats {
  task_stats: {
    countdown: number | null
    in_progress: number | null
    not_started: number | null
    as_of?: string
  }
  defect_stats: {
    clinical_appeals: number | null
    pending_review: number | null
    urged: number | null
  }
  record_stats: {
    pending_review: number | null
    pending_recheck: number | null
    total: number | null
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
  scene?: DashboardScene
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
  scene?: DashboardScene
}

export interface DashboardOverview {
  total_records: number
  avg_score: number
  pass_rate: number
  grade_distribution: Record<string, number>
  department_stats: Record<string, number>
  total_defects?: number
  scene?: DashboardScene
}

// ============= API 函数 =============

/** 获取待办统计 */
export async function getTodoStats(scene: DashboardScene = 'all') {
  return request<TodoStats>({
    method: 'GET',
    url: `${BASE_URL}/todo-stats`,
    params: { scene },
  })
}

/** 获取工作表现排名 */
export async function getPerformanceRanking(
  period: 'this_week' | 'last_week' | 'this_month' = 'this_week',
  scene: DashboardScene = 'all',
) {
  return request<PerformanceData>({
    method: 'GET',
    url: `${BASE_URL}/performance`,
    params: { period, scene },
  })
}

/** 获取概览数据 */
export async function getDashboardOverview(scene: DashboardScene = 'all') {
  return request<DashboardOverview>({
    method: 'GET',
    url: `${BASE_URL}/overview`,
    params: { scene },
  })
}
