import type { Component } from 'vue'

// 统计数据接口
export interface DashboardStats {
  totalRecords: number
  pendingRecords: number
  analyzingRecords: number
  completedRecords: number
  averageScore: number
  passRate: number
  todayUploads: number
  weeklyTrend: string
}

// 趋势变化类型
export interface TrendChange {
  value: number
  type: 'increase' | 'decrease'
  period?: 'day' | 'week' | 'month'
}

// 仪表盘卡片接口（改进版）
export interface DashboardCard {
  id: string
  title: string
  value: number | string
  change?: TrendChange
  icon: Component
  color: string
  loading?: boolean
  clickable?: boolean
  description?: string
}

// 快捷操作接口
export interface QuickAction {
  id: string
  title: string
  description: string
  icon: Component
  color: string
  action: string
  disabled?: boolean
  loading?: boolean
}

// 活动记录接口
export interface ActivityRecord {
  id: string
  title: string
  description: string
  time: string
  type: 'info' | 'success' | 'warning' | 'error'
  icon: Component
  color: string
  user?: string
  details?: Record<string, any>
}

// 图表数据接口
export interface ChartDataPoint {
  date: string
  count: number
  score: number
  passRate: number
  [key: string]
}

// 时间段选项
export type TimePeriod = 'week' | 'month' | 'quarter' | 'year'

// 图表类型
export type ChartType = 'line' | 'bar' | 'area'

// 指标类型
export type MetricType = 'all' | 'count' | 'score' | 'pass_rate'

// API响应接口
export interface DashboardApiResponse {
  stats: DashboardStats
  chartData: ChartDataPoint[]
  activities: ActivityRecord[]
  timestamp: string
}

// 错误处理接口
export interface DashboardError {
  code: string
  message: string
  module: 'stats' | 'chart' | 'activities' | 'actions'
  timestamp: string
}

// 加载状态接口
export interface LoadingState {
  stats: boolean
  chart: boolean
  activities: boolean
  refreshing: boolean
}
