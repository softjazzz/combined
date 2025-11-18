/**
 * DRG/DIP 模块工具函数
 */

import type {
  CodingStatus,
  ReviewStatus,
  Severity,
  AlertLevel,
  AlertType,
  SuggestionType,
  RiskLevel
} from '@/types/drg'

/**
 * 格式化金额（千分位、保留2位小数）
 * @param amount 金额
 * @returns 格式化后的金额字符串，例如：¥42,000.00
 */
export function formatCurrency(amount: number | undefined | null): string {
  if (amount === undefined || amount === null) {
    return '¥0.00'
  }
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`
}

/**
 * 格式化 DRG 权重（保留4位小数）
 * @param weight 权重
 * @returns 格式化后的权重字符串
 */
export function formatWeight(weight: number | undefined | null): string {
  if (weight === undefined || weight === null) {
    return '0.0000'
  }
  return weight.toFixed(4)
}

/**
 * 计算盈亏金额
 * @param baseline 基准支付金额
 * @param actual 实际费用
 * @returns 盈亏金额（正数为盈余，负数为亏损）
 */
export function calculateProfitMargin(
  baseline: number | undefined | null,
  actual: number | undefined | null
): number {
  if (baseline === undefined || baseline === null || actual === undefined || actual === null) {
    return 0
  }
  return baseline - actual
}

/**
 * 计算费用消耗率（实际费用/基准支付金额）
 * @param baseline 基准支付金额
 * @param actual 实际费用
 * @returns 费用消耗率（百分比）
 */
export function calculateCostRate(
  baseline: number | undefined | null,
  actual: number | undefined | null
): number {
  if (!baseline || baseline === 0 || !actual) {
    return 0
  }
  return (actual / baseline) * 100
}

/**
 * 格式化置信度（显示为百分比）
 * @param confidence 置信度 0-1
 * @returns 格式化后的置信度字符串，例如：92%
 */
export function formatConfidence(confidence: number | undefined | null): string {
  if (confidence === undefined || confidence === null) {
    return '0%'
  }
  return `${Math.round(confidence * 100)}%`
}

/**
 * 格式化百分比
 * @param value 数值
 * @param decimals 小数位数
 * @returns 格式化后的百分比字符串
 */
export function formatPercentage(value: number | undefined | null, decimals: number = 1): string {
  if (value === undefined || value === null) {
    return '0%'
  }
  return `${value.toFixed(decimals)}%`
}

/**
 * 编码状态中英文映射
 */
export const codingStatusMap: Record<CodingStatus, string> = {
  draft: '草稿',
  completed: '已完成',
  reviewed: '已审核'
}

/**
 * 审核状态中英文映射
 */
export const reviewStatusMap: Record<ReviewStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝'
}

/**
 * 严重程度中英文映射
 */
export const severityMap: Record<Severity, string> = {
  info: '信息',
  warning: '警告',
  error: '错误'
}

/**
 * 建议类型中英文映射
 */
export const suggestionTypeMap: Record<SuggestionType, string> = {
  missing_diagnosis: '遗漏诊断',
  procedure_missing: '遗漏手术操作',
  complication_marking: '并发症标记建议',
  logic_conflict: '逻辑冲突'
}

/**
 * 预警类型中英文映射
 */
export const alertTypeMap: Record<AlertType, string> = {
  cost_overrun: '费用超标',
  los_long: '住院日过长',
  coding_abnormal: '编码异常',
  profit_loss: '预计亏损'
}

/**
 * 风险等级中英文映射
 */
export const riskLevelMap: Record<RiskLevel, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险'
}

/**
 * 编码状态颜色映射（Ant Design Vue tag 颜色）
 */
export const codingStatusColor: Record<CodingStatus, string> = {
  draft: 'default',
  completed: 'processing',
  reviewed: 'success'
}

/**
 * 审核状态颜色映射
 */
export const reviewStatusColor: Record<ReviewStatus, string> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error'
}

/**
 * 严重程度颜色映射
 */
export const severityColor: Record<Severity, string> = {
  info: 'blue',
  warning: 'orange',
  error: 'red'
}

/**
 * 预警级别颜色映射
 */
export const alertLevelColor: Record<AlertLevel, string> = {
  info: 'blue',
  warning: 'orange',
  critical: 'red'
}

/**
 * 风险等级颜色映射
 */
export const riskLevelColor: Record<RiskLevel, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red'
}

/**
 * 预警类型图标映射（Ant Design Icons）
 */
export const alertTypeIcon: Record<AlertType, string> = {
  cost_overrun: 'dollar-circle',
  los_long: 'clock-circle',
  coding_abnormal: 'warning',
  profit_loss: 'fall'
}

/**
 * 格式化日期时间
 * @param dateString 日期字符串
 * @param format 格式类型
 * @returns 格式化后的日期字符串
 */
export function formatDateTime(
  dateString: string | undefined | null,
  format: 'date' | 'datetime' | 'time' = 'datetime'
): string {
  if (!dateString) {
    return '-'
  }

  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) {
      return '-'
    }

    switch (format) {
      case 'date':
        return date.toLocaleDateString('zh-CN')
      case 'time':
        return date.toLocaleTimeString('zh-CN')
      case 'datetime':
      default:
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        })
    }
  } catch (error) {
    return '-'
  }
}

/**
 * 获取盈亏状态描述
 * @param profitMargin 盈亏金额
 * @returns 盈亏状态描述
 */
export function getProfitStatus(profitMargin: number | undefined | null): {
  text: string
  color: string
  icon: string
} {
  if (profitMargin === undefined || profitMargin === null) {
    return { text: '未知', color: 'default', icon: 'question-circle' }
  }

  if (profitMargin > 0) {
    return { text: '盈余', color: 'success', icon: 'rise' }
  } else if (profitMargin < 0) {
    return { text: '亏损', color: 'error', icon: 'fall' }
  } else {
    return { text: '持平', color: 'warning', icon: 'minus-circle' }
  }
}

/**
 * 判断费用消耗率等级
 * @param costRate 费用消耗率
 * @returns 费用等级信息
 */
export function getCostRateLevel(costRate: number): {
  level: 'normal' | 'warning' | 'critical'
  color: string
  text: string
} {
  if (costRate <= 100) {
    return { level: 'normal', color: 'success', text: '正常' }
  } else if (costRate <= 120) {
    return { level: 'warning', color: 'warning', text: '超标' }
  } else {
    return { level: 'critical', color: 'error', text: '严重超标' }
  }
}

/**
 * 截断长文本
 * @param text 原文本
 * @param maxLength 最大长度
 * @returns 截断后的文本
 */
export function truncateText(text: string | undefined | null, maxLength: number = 50): string {
  if (!text) {
    return ''
  }
  if (text.length <= maxLength) {
    return text
  }
  return text.substring(0, maxLength) + '...'
}

/**
 * 获取性别文本
 * @param gender 性别代码
 * @returns 性别文本
 */
export function getGenderText(gender: 'M' | 'F' | undefined | null): string {
  if (!gender) {
    return '未知'
  }
  return gender === 'M' ? '男' : '女'
}

/**
 * 生成随机颜色（用于图表）
 * @param index 索引
 * @returns 颜色值
 */
export function getChartColor(index: number): string {
  const colors = [
    '#5470c6',
    '#91cc75',
    '#fac858',
    '#ee6666',
    '#73c0de',
    '#3ba272',
    '#fc8452',
    '#9a60b4',
    '#ea7ccc'
  ]
  return colors[index % colors.length]
}
