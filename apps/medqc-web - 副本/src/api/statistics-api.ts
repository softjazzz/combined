import { getDashboardOverview, getTodoStats } from '@/api/dashboard'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export interface StatisticsOverview {
  totalRecords: number
  pendingRecords: number
  analyzingRecords: number
  completedRecords: number
  averageScore: number
  passRate: number
  todayUploads: number
  weeklyTrend: string
}

export interface TrendData {
  period: string
  recordCount: number
  averageScore: number
  passRate: number
}

export interface DepartmentStats {
  department: string
  recordCount: number
  averageScore: number
  passRate: number
  color: string
}

export interface QCScoreDistribution {
  scoreRange: string
  count: number
  percentage: number
}

export interface QCIssueStats {
  category: string
  issueCount: number
  percentage: number
}

export interface StatisticsExportResult {
  count: number
  downloadUrl: string
}

interface ReportsSummaryPayload {
  generated_at?: string
  kpis?: {
    total_records?: number
    active_rules?: number
    qc_executions?: number
    pass_rate?: number
    avg_api_time?: number
    avg_qc_score?: number
    passed?: number
    warning?: number
    failed?: number
    pending?: number
  }
  top_categories?: Array<Record<string, unknown>>
}

interface ReportsTrendPayload {
  period: 'week' | 'month' | 'quarter'
  items: Array<{
    period?: string
    record_count?: number
    average_score?: number
    pass_rate?: number
  }>
}

const CHART_COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96']

async function requestOrThrow<T = unknown>(
  config: Parameters<typeof ApiService.requestRaw>[0],
): Promise<T> {
  const response = await ApiService.requestRaw<T>(config)
  const normalized = normalizeApiSuccess<T>(response.data)
  if (!normalized.success) {
    throw new Error(normalized.message || '请求失败')
  }
  return normalized.data as T
}

function normalizePercentage(value: number | null | undefined): number {
  if (value == null || Number.isNaN(Number(value))) {
    return 0
  }
  const numeric = Number(value)
  return Number((numeric <= 1 ? numeric * 100 : numeric).toFixed(1))
}

function toNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function buildDownloadUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  if (typeof window === 'undefined') {
    return path
  }

  return new URL(path, window.location.origin).toString()
}

function formatIssueCategory(item: Record<string, unknown>): string {
  const raw =
    item.category || item.name || item.label || item.type || item.rule_type || item.document_type
  return typeof raw === 'string' && raw.trim() ? raw.trim() : '未分类'
}

function formatIssueCount(item: Record<string, unknown>): number {
  return (
    toNumber(item.issue_count) ||
    toNumber(item.count) ||
    toNumber(item.value) ||
    toNumber(item.total)
  )
}

export async function getStatisticsOverview(): Promise<StatisticsOverview> {
  const [summaryResult, dashboardResult, todoResult] = await Promise.allSettled([
    requestOrThrow<ReportsSummaryPayload>({
      method: 'GET',
      url: '/api/v1/reports/qc/summary',
    }),
    getDashboardOverview('all'),
    getTodoStats('all'),
  ])

  const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null
  const dashboard =
    dashboardResult.status === 'fulfilled' && dashboardResult.value.success
      ? dashboardResult.value.data
      : null
  const todo =
    todoResult.status === 'fulfilled' && todoResult.value.success ? todoResult.value.data : null

  const totalRecords =
    summary?.kpis?.total_records ?? dashboard?.total_records ?? todo?.record_stats?.total ?? 0
  const pendingRecords =
    todo?.task_stats?.not_started ??
    todo?.record_stats?.pending_review ??
    summary?.kpis?.pending ??
    0
  const analyzingRecords = todo?.task_stats?.in_progress ?? todo?.record_stats?.pending_recheck ?? 0

  const averageScore = toNumber(summary?.kpis?.avg_qc_score ?? dashboard?.avg_score ?? 0)

  return {
    totalRecords,
    pendingRecords,
    analyzingRecords,
    completedRecords: Math.max(totalRecords - pendingRecords - analyzingRecords, 0),
    averageScore: Number(averageScore.toFixed(1)),
    passRate: normalizePercentage(summary?.kpis?.pass_rate ?? dashboard?.pass_rate ?? 0),
    // 当前后端还没有“今日上传量/周环比”的真实统计，先显式置 0，避免继续展示假趋势。
    todayUploads: 0,
    weeklyTrend: '0%',
  }
}

export async function getTrendData(period: 'week' | 'month' | 'quarter' = 'month'): Promise<TrendData[]> {
  const payload = await requestOrThrow<ReportsTrendPayload>({
    method: 'GET',
    url: '/api/v1/reports/qc/trend',
    params: { period },
  })

  return (payload.items || []).map(item => ({
    period: item.period || '',
    recordCount: toNumber(item.record_count),
    averageScore: Number(toNumber(item.average_score).toFixed(1)),
    passRate: normalizePercentage(item.pass_rate),
  }))
}

export async function getDepartmentStats(): Promise<DepartmentStats[]> {
  const overview = await getDashboardOverview('all')
  if (!overview.success || !overview.data) {
    throw new Error(overview.message || '获取部门统计失败')
  }

  const departmentStats = overview.data.department_stats || {}
  const avgScore = toNumber(overview.data.avg_score)
  const passRate = normalizePercentage(overview.data.pass_rate)

  return Object.entries(departmentStats)
    .map(([department, count], index) => ({
      department,
      recordCount: toNumber(count),
      averageScore: avgScore,
      passRate,
      color: CHART_COLORS[index % CHART_COLORS.length],
    }))
    .sort((left, right) => right.recordCount - left.recordCount)
}

export async function getQCScoreDistribution(): Promise<QCScoreDistribution[]> {
  const overview = await getDashboardOverview('all')
  if (!overview.success || !overview.data) {
    throw new Error(overview.message || '获取评分分布失败')
  }

  const distribution = overview.data.grade_distribution || {}
  const total = Math.max(
    Object.values(distribution).reduce((sum, count) => sum + toNumber(count), 0),
    1,
  )

  return Object.entries(distribution).map(([grade, count]) => ({
    scoreRange: `${grade}级`,
    count: toNumber(count),
    percentage: Number(((toNumber(count) / total) * 100).toFixed(1)),
  }))
}

export async function getQCIssueStats(): Promise<QCIssueStats[]> {
  const summary = await requestOrThrow<ReportsSummaryPayload>({
    method: 'GET',
    url: '/api/v1/reports/qc/summary',
  })

  const categories = Array.isArray(summary.top_categories) ? summary.top_categories : []
  const normalized = categories
    .map(item => {
      const count = formatIssueCount(item)
      return {
        category: formatIssueCategory(item),
        issueCount: count,
      }
    })
    .filter(item => item.issueCount > 0)

  const total = Math.max(normalized.reduce((sum, item) => sum + item.issueCount, 0), 1)
  return normalized.map(item => ({
    ...item,
    percentage: Number(((item.issueCount / total) * 100).toFixed(1)),
  }))
}

export async function exportStatisticsReport(
  _format: 'excel' | 'pdf' = 'excel',
): Promise<StatisticsExportResult> {
  try {
    const payload = await requestOrThrow<{ download_url: string; count: number }>({
      method: 'POST',
      url: '/api/v1/reports/qc/export',
      data: {},
    })

    return {
      count: toNumber(payload.count),
      downloadUrl: buildDownloadUrl(payload.download_url),
    }
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '导出统计报表失败'))
  }
}
