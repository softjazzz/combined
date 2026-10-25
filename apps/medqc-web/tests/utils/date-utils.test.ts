import { afterAll, beforeAll, describe, it, expect, vi } from 'vitest'
import {
  formatRelativeTime,
  formatDate,
  getDaysDifference,
  isExpired,
  getDateRangeDescription,
  getCurrentTimestamp,
  addDays,
  getThisWeekRange,
  getThisMonthRange,
  isWorkingHours,
  formatDuration,
  getFriendlyDate
} from '@/utils/date-utils'

// 本文件的日期断言以北京时间为基准，不能依赖开发机或CI宿主时区。
const originalTimezone = process.env.TZ
beforeAll(() => { process.env.TZ = 'Asia/Shanghai' })
afterAll(() => {
  if (originalTimezone === undefined) delete process.env.TZ
  else process.env.TZ = originalTimezone
})

describe('formatRelativeTime', () => {
  it('returns friendly labels based on time difference', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-01-02T00:00:00Z'))

    expect(formatRelativeTime('2024-01-02T00:00:30Z')).toBe('刚刚')
    expect(formatRelativeTime('2024-01-01T23:59:00Z')).toBe('1分钟前')
    expect(formatRelativeTime('2024-01-01T21:00:00Z')).toBe('3小时前')
    expect(formatRelativeTime('2024-01-01T00:00:00Z')).toBe('1天前')

    vi.useRealTimers()
  })
})

describe('formatDate', () => {
  it('formats date into different presentation styles', () => {
    expect(formatDate('2024-01-02T10:20:30Z')).toBe('2024-01-02')
    expect(formatDate('2024-01-02T10:20:30Z', 'datetime')).toContain('2024-01-02')
    expect(formatDate('2024-01-02T10:20:30Z', 'time')).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    expect(formatDate('invalid-date')).toBe('无效日期')
  })
})

describe('date calculations', () => {
  it('computes day differences and expiration', () => {
    expect(getDaysDifference('2024-01-01', '2024-01-02')).toBe(1)
    expect(getDaysDifference('invalid', '2024-01-02')).toBe(0)

    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-01-10T00:00:00Z'))
    expect(isExpired('2024-01-09')).toBe(true)
    expect(isExpired('2024-01-11')).toBe(false)
    vi.useRealTimers()
  })

  it('describes date ranges and timestamps', () => {
    const description = getDateRangeDescription('2024-01-01', '2024-01-10')
    expect(description).toBe('2024-01-01 至 2024-01-10 (9天)')

    vi.useFakeTimers()
    const fixed = new Date('2024-01-05T12:34:56Z')
    vi.setSystemTime(fixed)
    expect(getCurrentTimestamp()).toBe(fixed.toISOString())
    expect(addDays('2024-01-01T00:00:00Z', 5)).toBe(new Date('2024-01-06T00:00:00Z').toISOString())
    vi.useRealTimers()
  })
})

describe('range helpers', () => {
  it('computes current week range', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-01-18T12:00:00Z'))

    const { start, end } = getThisWeekRange()
    const startDate = new Date(start)
    const endDate = new Date(end)
    const now = new Date()

    expect(startDate.getDay()).toBe(0) // Sunday
    expect(endDate.getDay()).toBe(6) // Saturday
    expect(startDate.getTime()).toBeLessThanOrEqual(now.getTime())
    expect(endDate.getTime()).toBeGreaterThanOrEqual(now.getTime())

    vi.useRealTimers()
  })

  it('computes current month range', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-03-15T10:00:00Z'))

    const { start, end } = getThisMonthRange()
    const startDate = new Date(start)
    const endDate = new Date(end)

    expect(startDate.getDate()).toBe(1)
    expect(new Date(endDate.getFullYear(), endDate.getMonth() + 1, 0).getDate()).toBe(endDate.getDate())

    vi.useRealTimers()
  })
})

describe('time helpers', () => {
  it('verifies working hours boundaries', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

    const withinHours = new Date()
    withinHours.setHours(10, 30, 0, 0)

    const outsideHours = new Date()
    outsideHours.setHours(20, 0, 0, 0)

    const customRange = new Date()
    customRange.setHours(7, 30, 0, 0)

    expect(isWorkingHours(withinHours.toISOString())).toBe(true)
    expect(isWorkingHours(outsideHours.toISOString())).toBe(false)
    expect(isWorkingHours(customRange.toISOString(), { start: '07:00', end: '08:00' })).toBe(true)

    vi.useRealTimers()
  })

  it('formats durations', () => {
    expect(formatDuration(45)).toBe('45分钟')
    expect(formatDuration(90)).toBe('1小时30分钟')
    expect(formatDuration(1500)).toBe('1天1小时')
    expect(formatDuration(1561)).toBe('1天2小时1分钟')
  })
})

describe('getFriendlyDate', () => {
  it('returns relative labels for nearby dates', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2024-05-10T08:00:00Z'))

    expect(getFriendlyDate('2024-05-10')).toBe('今天')
    expect(getFriendlyDate('2024-05-09')).toBe('昨天')
    expect(getFriendlyDate('2024-05-11')).toBe('明天')
    expect(getFriendlyDate('2024-05-01')).toBe('2024-05-01')

    vi.useRealTimers()
  })
})
