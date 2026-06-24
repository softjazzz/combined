import type { DashboardStats, TrendChange, ChartDataPoint } from '@/types/dashboard'

interface DashboardDataShape {
  totalRecords: number
  pendingRecords: number
  analyzingRecords: number
  completedRecords: number
  averageScore: number
  passRate: number
  todayUploads: number
  weeklyTrend: unknown
}

/**
 * 格式化数字，添加千分位分隔符
 */
export function formatNumber(num: number): string {
  if (isNaN(num)) return '0'
  return num.toLocaleString()
}

/**
 * 格式化百分比
 */
export function formatPercentage(value: number, decimals: number = 2): string {
  if (isNaN(value)) return '0.00%'
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * 计算趋势变化
 */
export function calculateTrend(current: number, previous: number): TrendChange {
  if (previous === 0) {
    return {
      value: current,
      type: 'increase',
    }
  }

  const change = ((current - previous) / previous) * 100
  return {
    value: Math.abs(change),
    type: change >= 0 ? 'increase' : 'decrease',
  }
}

/**
 * 根据时间获取问候语
 */
export function getGreetingByTime(hour: number): string {
  if (hour < 0 || hour > 23 || isNaN(hour)) return '深夜好'

  if (hour === 0 || hour >= 22) return '深夜好'
  if (hour < 6) return '凌晨好'
  if (hour === 6 || hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour === 12 || hour < 14) return '中午好'
  if (hour < 17) return '下午好'
  if (hour === 17 || hour < 19) return '傍晚好'
  return '晚上好'
}

/**
 * 验证仪表盘数据
 */
export function validateDashboardData(data: unknown): { isValid: boolean; errors: string[] } {
  const errors: string[] = []
  if (typeof data !== 'object' || data === null) {
    return { isValid: false, errors: ['data must be an object'] }
  }
  const dashboardData = data as Partial<DashboardDataShape>

  // 检查必需字段
  const requiredFields = [
    'totalRecords',
    'pendingRecords',
    'analyzingRecords',
    'completedRecords',
    'averageScore',
    'passRate',
    'todayUploads',
    'weeklyTrend',
  ]

  requiredFields.forEach((field) => {
    if (!(field in dashboardData)) {
      errors.push(`${field} is required`)
    }
  })

  if (errors.length > 0) {
    return { isValid: false, errors }
  }

  // 检查数值范围
  if ((dashboardData.totalRecords || 0) < 0) errors.push('totalRecords must be non-negative')
  if ((dashboardData.pendingRecords || 0) < 0) errors.push('pendingRecords must be non-negative')
  if ((dashboardData.analyzingRecords || 0) < 0)
    errors.push('analyzingRecords must be non-negative')
  if ((dashboardData.completedRecords || 0) < 0)
    errors.push('completedRecords must be non-negative')
  if ((dashboardData.averageScore || 0) < 0 || (dashboardData.averageScore || 0) > 100)
    errors.push('averageScore must be between 0 and 100')
  if ((dashboardData.passRate || 0) < 0 || (dashboardData.passRate || 0) > 100)
    errors.push('passRate must be between 0 and 100')
  if ((dashboardData.todayUploads || 0) < 0) errors.push('todayUploads must be non-negative')

  // 检查数据一致性
  if ((dashboardData.completedRecords || 0) > (dashboardData.totalRecords || 0)) {
    errors.push('completedRecords cannot exceed totalRecords')
  }

  if (
    (dashboardData.pendingRecords || 0) +
      (dashboardData.analyzingRecords || 0) +
      (dashboardData.completedRecords || 0) >
    (dashboardData.totalRecords || 0)
  ) {
    errors.push('sum of pending, analyzing, and completed records cannot exceed total records')
  }

  return { isValid: errors.length === 0, errors }
}

/**
 * 生成模拟数据
 */
export function generateMockData(count: number): ChartDataPoint[] {
  const data: ChartDataPoint[] = []
  const now = new Date()

  for (let i = 0; i < count; i++) {
    const date = new Date(now.getTime() - (count - i - 1) * 24 * 60 * 60 * 1000)
    data.push({
      date: date.toISOString().split('T')[0],
      count: Math.floor(Math.random() * 1000),
      score: Math.floor(Math.random() * 100),
      passRate: Math.floor(Math.random() * 100),
    })
  }

  return data
}

/**
 * 格式化相对时间
 */
export function formatTimeAgo(date: Date): string {
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (diffInSeconds < 60) return '刚刚'

  const diffInMinutes = Math.floor(diffInSeconds / 60)
  if (diffInMinutes < 60) return `${diffInMinutes}分钟前`

  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) return `${diffInHours}小时前`

  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays < 30) return `${diffInDays}天前`

  const diffInMonths = Math.floor(diffInDays / 30)
  if (diffInMonths < 12) return `${diffInMonths}个月前`

  const diffInYears = Math.floor(diffInMonths / 12)
  return `${diffInYears}年前`
}

/**
 * 防抖函数
 */
export function debounce<T extends (...args: unknown[]) => any>(
  func: T,
  wait: number,
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

/**
 * 节流函数
 */
export function throttle<T extends (...args: unknown[]) => any>(
  func: T,
  limit: number,
): (...args: Parameters<T>) => void {
  let inThrottle: boolean = false

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

/**
 * 深拷贝对象
 */
export function deepClone<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') return obj
  if (obj instanceof Date) return new Date(obj.getTime()) as unknown as T
  if (obj instanceof Array) return obj.map((item) => deepClone(item)) as unknown as T
  if (typeof obj === 'object') {
    const clonedObj = {} as T
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        clonedObj[key] = deepClone(obj[key])
      }
    }
    return clonedObj
  }
  return obj
}

/**
 * 生成唯一ID
 */
export function generateId(): string {
  return Math.random().toString(36).substr(2, 9)
}

/**
 * 安全的JSON解析
 */
export function safeJsonParse<T>(str: string, defaultValue: T): T {
  try {
    return JSON.parse(str)
  } catch {
    return defaultValue
  }
}

/**
 * 检查是否为移动设备
 */
export function isMobile(): boolean {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
}

/**
 * 获取颜色透明度版本
 */
export function getColorWithOpacity(color: string, opacity: number): string {
  if (color.startsWith('#')) {
    const hex = color.slice(1)
    const r = parseInt(hex.substr(0, 2), 16)
    const g = parseInt(hex.substr(2, 2), 16)
    const b = parseInt(hex.substr(4, 2), 16)
    return `rgba(${r}, ${g}, ${b}, ${opacity})`
  }
  return color
}
