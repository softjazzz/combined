import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'
import { caseScopeLabel, dischargedDateRangeError, sceneCaseScope } from '@/utils/taskCaseScope'

const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
const day = (offset: number) => today.add(offset, 'day').format('YYYY-MM-DD')

describe('taskCaseScope', () => {
  it('maps each scene to its required case scope', () => {
    expect(sceneCaseScope('running')).toBe('active')
    expect(sceneCaseScope('final')).toBe('discharged')
    expect(sceneCaseScope('outpatient')).toBeUndefined()
    expect(sceneCaseScope(null)).toBeUndefined()
    expect(caseScopeLabel('discharged')).toBe('已出院（未核验归档）')
    expect(caseScopeLabel('active')).toBe('当前在院')
    expect(caseScopeLabel('other')).toBe('')
  })

  it('validates the discharge window like the backend contract', () => {
    expect(dischargedDateRangeError(day(-10), day(-1))).toBe('')
    expect(dischargedDateRangeError(day(-30), day(0))).toBe('')
    expect(dischargedDateRangeError(undefined, day(-1))).toBe(
      '终末任务必须选择出院开始日期和结束日期',
    )
    expect(dischargedDateRangeError('2026-02-30', day(-1))).toBe(
      '出院日期范围格式无效，请选择有效日期',
    )
    expect(dischargedDateRangeError(day(-1), day(-2))).toBe('出院开始日期不能晚于结束日期')
    expect(dischargedDateRangeError(day(-1), day(1))).toBe('出院结束日期不能晚于今天')
    expect(dischargedDateRangeError(day(-31), day(0))).toBe('出院日期范围最多 31 天')
  })
})
