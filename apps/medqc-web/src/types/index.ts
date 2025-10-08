import type { User as SupabaseUser } from '@supabase/supabase-js'
import type { MedicalRecord, QCResult, QCRule, UserRole } from './supabase'

// 重新导出auth类型
export * from './auth'

// 用户相关类型
export interface User extends SupabaseUser {
  roles?: string[]
  hospital_id?: string
  department?: string
  display_name?: string
}

// API响应通用格式
export interface ApiResponse<T = any> {
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
  [key: string]
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
export interface ModalState {
  visible: boolean
  loading: boolean
  data?: any
}

// 表格列配置
export interface TableColumn {
  key: string
  title: string
  dataIndex?: string
  width?: number | string
  align?: 'left' | 'center' | 'right'
  fixed?: 'left' | 'right'
  sorter?: boolean | ((a: any,  b: any) => number)
  filters?: Array<{ text: string; value: any }>
  render?: (value: any, record: any, index: number) => any
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
  recordMetadata?: Record<string, any>
  /** 扩展配置，用于控制分析行为 */
  options?: Record<string, any>
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
  options?: Record<string, any>
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
  icon?: any // Vue组件引用
  color?: string
  loading?: boolean
}

// 路由元信息
export interface RouteMeta {
  title?: string
  icon?: string
  permission?: string[]
  hidden?: boolean
  keepAlive?: boolean
  breadcrumb?: BreadcrumbItem[]
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
export interface WebSocketMessage {
  type: string
  payload: any
  timestamp: string
}

// 错误类型
export interface AppError {
  code: string
  message: string
  details?: any
  timestamp: string
}

// 操作日志
export interface OperationLog {
  id: string
  userId: string
  userName: string
  action: string
  resource: string
  details: Record<string, any>
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
