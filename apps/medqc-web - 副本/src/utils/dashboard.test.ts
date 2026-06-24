import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  formatNumber,
  formatPercentage,
  calculateTrend,
  getGreetingByTime,
  validateDashboardData,
  generateMockData,
  formatTimeAgo
} from './dashboard'
import type { DashboardStats, TrendChange } from '@/types/dashboard'

describe('Dashboard Utils', () => {
  describe('formatNumber', () => {
    it('应该正确格式化数字', () => {
      expect(formatNumber(1234)).toBe('1,234')
      expect(formatNumber(1234567)).toBe('1,234,567')
      expect(formatNumber(0)).toBe('0')
      expect(formatNumber(123)).toBe('123')
    })

    it('应该处理小数', () => {
      expect(formatNumber(1234.56)).toBe('1,234.56')
      expect(formatNumber(1234.5)).toBe('1,234.5')
    })

    it('应该处理负数', () => {
      expect(formatNumber(-1234)).toBe('-1,234')
      expect(formatNumber(-1234.56)).toBe('-1,234.56')
    })
  })

  describe('formatPercentage', () => {
    it('应该正确格式化百分比', () => {
      expect(formatPercentage(0.1234)).toBe('12.34%')
      expect(formatPercentage(0.1)).toBe('10.00%')
      expect(formatPercentage(1)).toBe('100.00%')
      expect(formatPercentage(0)).toBe('0.00%')
    })

    it('应该支持自定义小数位数', () => {
      expect(formatPercentage(0.1234, 1)).toBe('12.3%')
      expect(formatPercentage(0.1234, 0)).toBe('12%')
      expect(formatPercentage(0.1234, 3)).toBe('12.340%')
    })

    it('应该处理边界值', () => {
      expect(formatPercentage(1.5)).toBe('150.00%')
      expect(formatPercentage(-0.1)).toBe('-10.00%')
    })
  })

  describe('calculateTrend', () => {
    it('应该正确计算增长趋势', () => {
      const result = calculateTrend(120, 100)
      expect(result.type).toBe('increase')
      expect(result.value).toBe(20)
    })

    it('应该正确计算下降趋势', () => {
      const result = calculateTrend(80, 100)
      expect(result.type).toBe('decrease')
      expect(result.value).toBe(20)
    })

    it('应该处理零值', () => {
      const result = calculateTrend(100, 0)
      expect(result.type).toBe('increase')
      expect(result.value).toBe(100)
    })

    it('应该处理相等值', () => {
      const result = calculateTrend(100, 100)
      expect(result.type).toBe('increase')
      expect(result.value).toBe(0)
    })

    it('应该处理小数', () => {
      const result = calculateTrend(105.5, 100)
      expect(result.type).toBe('increase')
      expect(result.value).toBe(5.5)
    })
  })

  describe('getGreetingByTime', () => {
    it('应该根据小时返回正确问候语', () => {
      expect(getGreetingByTime(5)).toBe('凌晨好')
      expect(getGreetingByTime(8)).toBe('早上好')
      expect(getGreetingByTime(11)).toBe('上午好')
      expect(getGreetingByTime(13)).toBe('中午好')
      expect(getGreetingByTime(16)).toBe('下午好')
      expect(getGreetingByTime(18)).toBe('傍晚好')
      expect(getGreetingByTime(21)).toBe('晚上好')
      expect(getGreetingByTime(23)).toBe('深夜好')
    })

    it('应该处理边界值', () => {
      expect(getGreetingByTime(0)).toBe('深夜好')
      expect(getGreetingByTime(6)).toBe('早上好')
      expect(getGreetingByTime(12)).toBe('中午好')
      expect(getGreetingByTime(17)).toBe('傍晚好')
      expect(getGreetingByTime(19)).toBe('晚上好')
      expect(getGreetingByTime(22)).toBe('深夜好')
    })

    it('应该处理无效输入', () => {
      expect(getGreetingByTime(-1)).toBe('深夜好')
      expect(getGreetingByTime(25)).toBe('深夜好')
      expect(getGreetingByTime(NaN)).toBe('深夜好')
    })
  })

  describe('validateDashboardData', () => {
    const validData: DashboardStats = {
      totalRecords: 1000,
      pendingRecords: 50,
      analyzingRecords: 10,
      completedRecords: 940,
      averageScore: 85.5,
      passRate: 94.2,
      todayUploads: 15,
      weeklyTrend: '+12.5%'
    }

    it('应该验证有效数据', () => {
      const result = validateDashboardData(validData)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('应该检测缺失字段', () => {
      const invalidData = { ...validData }
      delete (invalidData as any).totalRecords
      
      const result = validateDashboardData(invalidData as any)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContain('totalRecords is required')
    })

    it('应该检测无效数值', () => {
      const invalidData = {
        ...validData,
        totalRecords: -1,
        averageScore: 150,
        passRate: -10
      }
      
      const result = validateDashboardData(invalidData)
      expect(result.isValid).toBe(false)
      expect(result.errors.length).toBeGreaterThan(0)
    })

    it('应该检测数据一致性', () => {
      const invalidData = {
        ...validData,
        totalRecords: 100,
        completedRecords: 150 // 完成数量不能大于总数量
      }
      
      const result = validateDashboardData(invalidData)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContain('completedRecords cannot exceed totalRecords')
    })
  })

  describe('generateMockData', () => {
    it('应该生成指定数量的模拟数据', () => {
      const data = generateMockData(10)
      expect(data).toHaveLength(10)
      
      data.forEach(item => {
        expect(item).toHaveProperty('date')
        expect(item).toHaveProperty('count')
        expect(item).toHaveProperty('score')
        expect(item).toHaveProperty('passRate')
        expect(typeof item.count).toBe('number')
        expect(typeof item.score).toBe('number')
        expect(typeof item.passRate).toBe('number')
      })
    })

    it('应该生成合理范围内的数据', () => {
      const data = generateMockData(100)
      
      data.forEach(item => {
        expect(item.count).toBeGreaterThanOrEqual(0)
        expect(item.count).toBeLessThanOrEqual(1000)
        expect(item.score).toBeGreaterThanOrEqual(0)
        expect(item.score).toBeLessThanOrEqual(100)
        expect(item.passRate).toBeGreaterThanOrEqual(0)
        expect(item.passRate).toBeLessThanOrEqual(100)
      })
    })

    it('应该生成唯一的日期', () => {
      const data = generateMockData(30)
      const dates = data.map(item => item.date)
      const uniqueDates = [...new Set(dates)]
      expect(uniqueDates).toHaveLength(dates.length)
    })
  })

  describe('formatTimeAgo', () => {
    const now = new Date('2024-01-01T12:00:00Z')
    
    beforeEach(() => {
      vi.setSystemTime(now)
    })

    it('应该正确格式化时间差', () => {
      const oneMinuteAgo = new Date(now.getTime() - 60 * 1000)
      expect(formatTimeAgo(oneMinuteAgo)).toBe('1分钟前')
      
      const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000)
      expect(formatTimeAgo(oneHourAgo)).toBe('1小时前')
      
      const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      expect(formatTimeAgo(oneDayAgo)).toBe('1天前')
    })

    it('应该处理复数形式', () => {
      const twoMinutesAgo = new Date(now.getTime() - 2 * 60 * 1000)
      expect(formatTimeAgo(twoMinutesAgo)).toBe('2分钟前')
      
      const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000)
      expect(formatTimeAgo(twoHoursAgo)).toBe('2小时前')
    })

    it('应该处理刚刚发生的时间', () => {
      const justNow = new Date(now.getTime() - 30 * 1000)
      expect(formatTimeAgo(justNow)).toBe('刚刚')
    })

    it('应该处理未来时间', () => {
      const future = new Date(now.getTime() + 60 * 1000)
      expect(formatTimeAgo(future)).toBe('刚刚')
    })
  })
})
