// 日期工具函数
// 用于审核模块的日期格式化和计算

/**
 * 格式化相对时间
 * @param dateString 日期字符串
 * @returns 相对时间描述
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (diffInSeconds < 60) {
    return '刚刚'
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60)
  if (diffInMinutes < 60) {
    return `${diffInMinutes}分钟前`
  }

  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) {
    return `${diffInHours}小时前`
  }

  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays < 7) {
    return `${diffInDays}天前`
  }

  const diffInWeeks = Math.floor(diffInDays / 7)
  if (diffInWeeks < 4) {
    return `${diffInWeeks}周前`
  }

  const diffInMonths = Math.floor(diffInDays / 30)
  if (diffInMonths < 12) {
    return `${diffInMonths}个月前`
  }

  const diffInYears = Math.floor(diffInDays / 365)
  return `${diffInYears}年前`
}

/**
 * 格式化日期为标准格式
 * @param dateString 日期字符串
 * @param format 格式类型
 * @returns 格式化后的日期字符串
 */
export function formatDate(dateString: string, format: 'date' | 'datetime' | 'time' = 'date'): string {
  const date = new Date(dateString)
  
  if (isNaN(date.getTime())) {
    return '无效日期'
  }

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  switch (format) {
    case 'date':
      return `${year}-${month}-${day}`
    case 'datetime':
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    case 'time':
      return `${hours}:${minutes}:${seconds}`
    default:
      return `${year}-${month}-${day}`
  }
}

/**
 * 计算两个日期之间的天数差
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 天数差
 */
export function getDaysDifference(startDate: string, endDate: string): number {
  const start = new Date(startDate)
  const end = new Date(endDate)
  
  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return 0
  }

  const diffInTime = end.getTime() - start.getTime()
  return Math.ceil(diffInTime / (1000 * 60 * 60 * 24))
}

/**
 * 检查日期是否过期
 * @param dateString 日期字符串
 * @returns 是否过期
 */
export function isExpired(dateString: string): boolean {
  const date = new Date(dateString)
  const now = new Date()
  
  if (isNaN(date.getTime())) {
    return false
  }

  return date.getTime() < now.getTime()
}

/**
 * 获取日期范围描述
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 日期范围描述
 */
export function getDateRangeDescription(startDate: string, endDate: string): string {
  const start = formatDate(startDate)
  const end = formatDate(endDate)
  const days = getDaysDifference(startDate, endDate)
  
  return `${start} 至 ${end} (${days}天)`
}

/**
 * 获取当前时间戳
 * @returns ISO格式的时间戳
 */
export function getCurrentTimestamp(): string {
  return new Date().toISOString()
}

/**
 * 添加天数到日期
 * @param dateString 原始日期
 * @param days 要添加的天数
 * @returns 新的日期字符串
 */
export function addDays(dateString: string, days: number): string {
  const date = new Date(dateString)
  date.setDate(date.getDate() + days)
  return date.toISOString()
}

/**
 * 获取本周的开始和结束日期
 * @returns 本周的日期范围
 */
export function getThisWeekRange(): { start: string; end: string } {
  const now = new Date()
  const dayOfWeek = now.getDay()
  const startOfWeek = new Date(now)
  startOfWeek.setDate(now.getDate() - dayOfWeek)
  startOfWeek.setHours(0, 0, 0, 0)
  
  const endOfWeek = new Date(startOfWeek)
  endOfWeek.setDate(startOfWeek.getDate() + 6)
  endOfWeek.setHours(23, 59, 59, 999)
  
  return {
    start: startOfWeek.toISOString(),
    end: endOfWeek.toISOString()
  }
}

/**
 * 获取本月的开始和结束日期
 * @returns 本月的日期范围
 */
export function getThisMonthRange(): { start: string; end: string } {
  const now = new Date()
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
  const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999)
  
  return {
    start: startOfMonth.toISOString(),
    end: endOfMonth.toISOString()
  }
}

/**
 * 检查时间是否在工作时间内
 * @param dateString 日期字符串
 * @param workHours 工作时间配置
 * @returns 是否在工作时间内
 */
export function isWorkingHours(
  dateString: string,
  workHours: { start: string; end: string } = { start: '09:00', end: '17:00' }
): boolean {
  const date = new Date(dateString)
  const hours = date.getHours()
  const minutes = date.getMinutes()
  const currentTime = hours * 60 + minutes
  
  const [startHour, startMinute] = workHours.start.split(':').map(Number)
  const [endHour, endMinute] = workHours.end.split(':').map(Number)
  const startTime = startHour * 60 + startMinute
  const endTime = endHour * 60 + endMinute
  
  return currentTime >= startTime && currentTime <= endTime
}

/**
 * 格式化持续时间
 * @param minutes 分钟数
 * @returns 格式化的持续时间
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}分钟`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  
  if (hours < 24) {
    return remainingMinutes > 0 ? `${hours}小时${remainingMinutes}分钟` : `${hours}小时`
  }
  
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  
  let result = `${days}天`
  if (remainingHours > 0) {
    result += `${remainingHours}小时`
  }
  if (remainingMinutes > 0) {
    result += `${remainingMinutes}分钟`
  }
  
  return result
}

/**
 * 获取友好的日期描述
 * @param dateString 日期字符串
 * @returns 友好的日期描述
 */
export function getFriendlyDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  
  const inputDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  
  if (inputDate.getTime() === today.getTime()) {
    return '今天'
  } else if (inputDate.getTime() === yesterday.getTime()) {
    return '昨天'
  } else if (inputDate.getTime() === tomorrow.getTime()) {
    return '明天'
  } else {
    return formatDate(dateString)
  }
}
