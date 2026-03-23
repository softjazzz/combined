import type { MedicalRecord, QCResult, QCRule, UserRole } from './supabase'
import type { User as AuthUser } from './auth'
import type {
  CreateMedicalRecordRequest as CreateMedicalRecordRequestCompat,
  UpdateMedicalRecordRequest as UpdateMedicalRecordRequestCompat,
} from '@/services/supabaseMedicalRecordService'

// 重新导出auth类型
export * from './auth'

// 重新导出API类型
export type { ApiSuccessResponse, ApiErrorResponse } from './api'

// 用户相关类型
export type User = AuthUser

// API响应通用格式（已废弃，请使用 api.ts 中的类型）
// @deprecated 使用 ApiSuccessResponse 或 ApiErrorResponse 替代
export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

// 分页参数
export interface PaginationParams {
  page: number
  pageSize: number
  total?: number
}

// 分页响应
export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
}

// 排序参数
export interface SortParams {
  field: string
  order: 'asc' | 'desc'
}

// 筛选参数
export interface FilterParams {
  [key: string]: string | number | boolean | null | undefined
}

// 搜索参数
export interface SearchParams {
  keyword?: string
  filters?: FilterParams
  sort?: SortParams
  pagination?: PaginationParams
}

// 文件上传相关
export interface FileUploadResponse {
  url: string
  path: string
  size: number
  mimeType: string
}

export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

// 表单状态
export interface FormState {
  loading: boolean
  errors: Record<string, string>
  touched: Record<string, boolean>
}

// 模态框状态
export interface ModalState<T = unknown> {
  visible: boolean
  loading: boolean
  data?: T
}

// 表格列配置
export interface TableColumn<T = unknown> {
  key: string
  title: string
  dataIndex?: string
  width?: number | string
  align?: 'left' | 'center' | 'right'
  fixed?: 'left' | 'right'
  sorter?: boolean | ((a: T, b: T) => number)
  filters?: Array<{ text: string; value: string | number | boolean }>
  render?: (value: unknown, record: T, index: number) => unknown
}

// 菜单项类型
export interface MenuItem {
  key: string
  label: string
  icon?: string
  path?: string
  children?: MenuItem[]
  permission?: string[]
  hidden?: boolean
}

// 面包屑项
export interface BreadcrumbItem {
  title: string
  path?: string
}

// 通知类型
export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
  timestamp: string
  read?: boolean
}

// 主题配置
export interface ThemeConfig {
  primaryColor: string
  borderRadius: number
  colorBgContainer: string
  colorBgLayout: string
}

// 系统设置
export interface SystemSettings {
  siteName: string
  logo: string
  theme: ThemeConfig
  features: {
    enableRealtime: boolean
    enableNotifications: boolean
    maxFileSize: number
    allowedFileTypes: string[]
  }
}

// 质控相关业务类型
export interface QCAnalysisRequest {
  recordId: string
  content: string
  rules: Array<{
    id: string
    name: string
    description: string
    weight: number
    category?: string
    severity?: string
    ruleCode?: string
  }>
  /** 选中文书传递给质控引擎的精简信息 */
  documents?: Array<{
    id: string
    title?: string
    type?: string
  }>
  /** 可选：仅传递规则ID，由后端自行查找 */
  ruleIds?: string[]
  /** 额外的病历或上下文信息 */
  recordMetadata?: Record<string, unknown>
  /** 扩展配置，用于控制分析行为 */
  options?: Record<string, unknown>
}

export interface QCAnalysisResponse {
  recordId: string
  score: number
  issues: Array<{
    ruleId: string
    ruleName: string
    description: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    suggestion: string
  }>
  suggestions: string[]
  summary: string
  analysisTime: string
}

// 批量操作
export interface BatchOperation {
  type: 'analyze' | 'delete' | 'export'
  ids: string[]
  options?: Record<string, unknown>
}

export interface BatchResult {
  success: number
  failed: number
  total: number
  errors: Array<{
    id: string
    error: string
  }>
}

// 统计图表数据
export interface ChartData {
  labels: string[]
  datasets: Array<{
    label: string
    data: number[]
    backgroundColor?: string | string[]
    borderColor?: string | string[]
  }>
}

// 仪表板卡片数据
export interface DashboardCard {
  title: string
  value: number | string
  change?: {
    value: number
    type: 'increase' | 'decrease'
  }
  icon?: unknown // Vue组件引用
  color?: string
  loading?: boolean
}

export type CreateMedicalRecordRequest = CreateMedicalRecordRequestCompat
export type UpdateMedicalRecordRequest = UpdateMedicalRecordRequestCompat

export interface UserProfile {
  id: string
  name?: string
  role?: string
  department?: string
}

export interface SearchResult<T = unknown> {
  items: T[]
  total: number
}

// 路由元信息
export interface RouteMeta {
  title?: string
  icon?: string
  permission?: string[]
  hidden?: boolean
  keepAlive?: boolean
  breadcrumb?: BreadcrumbItem[]
  requiresAuth?: boolean  // 是否需要认证（默认true）
  allowDemo?: boolean     // 是否允许演示模式访问（通过?demo=true参数）
}

// 导出格式
export type ExportFormat = 'excel' | 'pdf' | 'csv' | 'word'

// 导出选项
export interface ExportOptions {
  format: ExportFormat
  filename?: string
  columns?: string[]
  filters?: FilterParams
}

// WebSocket消息类型
export interface WebSocketMessage<T = unknown> {
  type: string
  payload: T
  timestamp: string
}

// 错误类型
export interface AppError {
  code: string
  message: string
  details?: Record<string, unknown>
  timestamp: string
}

// 操作日志
export interface OperationLog {
  id: string
  userId: string
  userName: string
  action: string
  resource: string
  details: Record<string, unknown>
  ip: string
  userAgent: string
  timestamp: string
}

// 系统状态
export interface SystemStatus {
  online: boolean
  version: string
  uptime: number
  memory: {
    used: number
    total: number
  }
  database: {
    status: 'connected' | 'disconnected'
    latency: number
  }
  ai: {
    status: 'available' | 'unavailable'
    model: string
    latency: number
  }
}

// 重新导出Supabase类型
export type {
  MedicalRecord,
  QCResult,
  QCRule,
  UserRole,
  QCIssue,
  QCSuggestion,
  QCStatistics,
  MedicalRecordWithQC,
  QCResultWithRecord
} from './supabase' 
