// @ts-nocheck
import type { Component } from 'vue'

// 缁熻鏁版嵁鎺ュ彛
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

// 瓒嬪娍鍙樺寲绫诲瀷
export interface TrendChange {
  value: number
  type: 'increase' | 'decrease'
  period?: 'day' | 'week' | 'month'
}

// 浠〃鐩樺崱鐗囨帴鍙ｏ紙鏀硅繘鐗堬級
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

// 蹇嵎鎿嶄綔鎺ュ彛
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

// 娲诲姩璁板綍鎺ュ彛
export interface ActivityRecord {
  id: string
  title: string
  description: string
  time: string
  type: 'info' | 'success' | 'warning' | 'error'
  icon: Component
  color: string
  user?: string
  details?: Record<string, unknown>
}

// 鍥捐〃鏁版嵁鎺ュ彛
export interface ChartDataPoint {
  date: string
  count: number
  score: number
  passRate: number
  [key: string]
}

// 鏃堕棿娈甸€夐」
export type TimePeriod = 'week' | 'month' | 'quarter' | 'year'

// 鍥捐〃绫诲瀷
export type ChartType = 'line' | 'bar' | 'area'

// 鎸囨爣绫诲瀷
export type MetricType = 'all' | 'count' | 'score' | 'pass_rate'

// API鍝嶅簲鎺ュ彛
export interface DashboardApiResponse {
  stats: DashboardStats
  chartData: ChartDataPoint[]
  activities: ActivityRecord[]
  timestamp: string
}

// 閿欒澶勭悊鎺ュ彛
export interface DashboardError {
  code: string
  message: string
  module: 'stats' | 'chart' | 'activities' | 'actions'
  timestamp: string
}

// 鍔犺浇鐘舵€佹帴鍙?
export interface LoadingState {
  stats: boolean
  chart: boolean
  activities: boolean
  refreshing: boolean
}

