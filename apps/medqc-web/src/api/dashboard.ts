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

export interface ReviewTodoCounts {
  pending_record_review: number
  pending_record_recheck: number
  pending_manual_defect_review: number | null
  scene: 'all'
}

export type PerformancePeriod = 'this_week' | 'last_week' | 'this_month'
export type PerformanceUnavailableReason = 'scene_not_attributable'

/** 排名项公共字段：name 取 sys_users.display_name，缺失时为 null，由前端回退显示 user_id */
interface RankingItemBase {
  user_id: string
  name: string | null
  count: number
  /** 竞争排名（1、1、3） */
  rank: number
}

/** 质控缺陷排名项：按人工缺陷创建人统计 */
export interface DefectRankingItem extends RankingItemBase {
  approved_count: number
  rejected_count: number
}

/** 质控病历排名项：按病历审核决定人统计 */
export interface RecordRankingItem extends RankingItemBase {
  initial_count: number
  recheck_count: number
}

export interface PerformanceRange {
  start: string
  end: string
}

/** 工作表现排名；排名为 null 时必须带不可用原因，不以空数组或 0 代替 */
export interface PerformanceData {
  period: PerformancePeriod
  period_label: string
  range: PerformanceRange
  scene: DashboardScene
  defect_ranking: DefectRankingItem[] | null
  record_ranking: RecordRankingItem[] | null
  unavailable_reason: PerformanceUnavailableReason | null
}

const PERFORMANCE_PERIODS: readonly PerformancePeriod[] = ['this_week', 'last_week', 'this_month']
const DASHBOARD_SCENES: readonly DashboardScene[] = ['all', 'outpatient_emergency', 'running', 'final']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function normalizeRankingBase(raw: Record<string, unknown>): RankingItemBase | null {
  const userId = typeof raw.user_id === 'number' && Number.isFinite(raw.user_id)
    ? String(raw.user_id)
    : raw.user_id
  if (typeof userId !== 'string' || !userId.trim()) return null
  if (raw.name !== null && typeof raw.name !== 'string') return null
  if (!isCount(raw.count) || !isCount(raw.rank) || raw.rank < 1) return null
  const name = typeof raw.name === 'string' && raw.name.trim() ? raw.name : null
  return { user_id: userId, name, count: raw.count, rank: raw.rank }
}

function normalizeRankingList<T>(
  raw: unknown,
  mapItem: (item: Record<string, unknown>) => T | null,
): T[] | null | undefined {
  // 返回 undefined 表示格式非法；null 表示服务端声明不可用
  if (raw === null) return null
  if (!Array.isArray(raw)) return undefined
  const items: T[] = []
  for (const entry of raw) {
    if (!isRecord(entry)) return undefined
    const item = mapItem(entry)
    if (!item) return undefined
    items.push(item)
  }
  return items
}

function normalizeDefectItem(raw: Record<string, unknown>): DefectRankingItem | null {
  const base = normalizeRankingBase(raw)
  if (!base || !isCount(raw.approved_count) || !isCount(raw.rejected_count)) return null
  return { ...base, approved_count: raw.approved_count, rejected_count: raw.rejected_count }
}

function normalizeRecordItem(raw: Record<string, unknown>): RecordRankingItem | null {
  const base = normalizeRankingBase(raw)
  if (!base || !isCount(raw.initial_count) || !isCount(raw.recheck_count)) return null
  return { ...base, initial_count: raw.initial_count, recheck_count: raw.recheck_count }
}

/**
 * 严格校验 /dashboard/performance 响应；任何字段不符合合同即返回 null（按请求失败处理），
 * 不做缺省补 0 或示例兜底。
 */
export function normalizePerformanceData(raw: unknown): PerformanceData | null {
  if (!isRecord(raw)) return null
  const period = raw.period as PerformancePeriod
  const scene = raw.scene as DashboardScene
  if (!PERFORMANCE_PERIODS.includes(period) || !DASHBOARD_SCENES.includes(scene)) return null
  if (typeof raw.period_label !== 'string') return null
  const range = raw.range
  if (!isRecord(range) || typeof range.start !== 'string' || typeof range.end !== 'string') return null
  const rawReason = raw.unavailable_reason
  if (rawReason !== null && rawReason !== 'scene_not_attributable') return null
  const reason: PerformanceUnavailableReason | null = rawReason === null ? null : 'scene_not_attributable'

  const defectRanking = normalizeRankingList(raw.defect_ranking, normalizeDefectItem)
  const recordRanking = normalizeRankingList(raw.record_ranking, normalizeRecordItem)
  if (defectRanking === undefined || recordRanking === undefined) return null
  // 排名为 null 必须有不可用原因，否则无法区分“不支持”与“缺数据”
  if ((defectRanking === null || recordRanking === null) && reason === null) return null

  return {
    period,
    period_label: raw.period_label,
    range: { start: range.start, end: range.end },
    scene,
    defect_ranking: defectRanking,
    record_ranking: recordRanking,
    unavailable_reason: reason,
  }
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

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

/**
 * V5 首页审核待办适配。
 *
 * 计数仍由 dashboard/todo-stats 的审核服务谓词给出；这里仅严格提取，避免缺字段、
 * 无权限或请求失败时被前端当成 0。人工缺陷当前没有场景归属，只允许 all 范围。
 */
export async function getReviewTodoCounts(): Promise<{
  success: boolean
  data?: ReviewTodoCounts
  message?: string
}> {
  const result = await getTodoStats('all')
  if (!result.success || !result.data) {
    return { success: false, message: result.message }
  }

  const data = result.data as unknown
  if (!isRecord(data)
    || data.scene !== 'all'
    || !isRecord(data.record_stats)
    || !isRecord(data.defect_stats)) {
    return { success: false, message: '审核待办数据格式异常' }
  }

  const recordReview = data.record_stats.pending_review
  const recordRecheck = data.record_stats.pending_recheck
  const manualDefectReview = data.defect_stats.pending_review
  if (!isNonNegativeInteger(recordReview)
    || !isNonNegativeInteger(recordRecheck)
    || (manualDefectReview !== null && !isNonNegativeInteger(manualDefectReview))) {
    return { success: false, message: '审核待办数据格式异常' }
  }

  return {
    success: true,
    data: {
      pending_record_review: recordReview,
      pending_record_recheck: recordRecheck,
      pending_manual_defect_review: isNonNegativeInteger(manualDefectReview) ? manualDefectReview : null,
      scene: 'all',
    },
  }
}

/** 获取工作表现排名；响应不符合合同时按失败返回，不回退示例数据 */
export async function getPerformanceRanking(
  period: PerformancePeriod = 'this_week',
  scene: DashboardScene = 'all',
): Promise<{ success: boolean; data?: PerformanceData; message?: string }> {
  const result = await request<unknown>({
    method: 'GET',
    url: `${BASE_URL}/performance`,
    params: { period, scene },
  })
  if (!result.success) return { success: false, message: result.message }
  const data = normalizePerformanceData(result.data)
  if (!data) return { success: false, message: '排名数据格式异常' }
  return { success: true, data, message: result.message }
}

/** 获取概览数据 */
export async function getDashboardOverview(scene: DashboardScene = 'all') {
  return request<DashboardOverview>({
    method: 'GET',
    url: `${BASE_URL}/overview`,
    params: { scene },
  })
}
