import { describe, expect, it } from 'vitest'

import {
  buildDepartmentSelectOptions,
  buildQuickDepartments,
  buildWorkstationFilterSummary,
  filterDepartmentOption,
} from '@/views/workstation-v4/utils/workstationFilterPresentation'
import type { DeptInfo } from '@/views/workstation-v4/types'

const departments: DeptInfo[] = [
  { name: '全部科室', total: 100, warningCount: 0 },
  { name: '普通外科', total: 38, warningCount: 2 },
  { name: '心血管内科', total: 26, warningCount: 1 },
  { name: '中医科', total: 19, warningCount: 0 },
  { name: '骨科', total: 13, warningCount: 0 },
  { name: '呼吸内科', total: 9, warningCount: 0 },
  { name: '神经内科', total: 8, warningCount: 0 },
]

describe('workstationFilterPresentation', () => {
  it('department select options include all departments and sort by count', () => {
    const options = buildDepartmentSelectOptions(departments)

    expect(options[0].name).toBe('全部科室')
    expect(options.map((item) => item.name)).toContain('中医科')
    expect(options.find((item) => item.name === '中医科')?.total).toBe(19)
  })

  it('department filter option matches Chinese department names', () => {
    expect(filterDepartmentOption('中医', { value: '中医科' })).toBe(true)
    expect(filterDepartmentOption('中医', { value: '普通外科' })).toBe(false)
  })

  it('quick departments keep all, active department and top departments', () => {
    const quick = buildQuickDepartments(departments, '神经内科')

    expect(quick[0].name).toBe('全部科室')
    expect(quick.map((item) => item.name)).toContain('神经内科')
    expect(quick.length).toBeLessThanOrEqual(7)
  })

  it('filter summary shows department, date field, date range and total', () => {
    const summary = buildWorkstationFilterSummary({
      activeDept: '中医科',
      dateField: 'visit',
      dateRange: ['2026-05-25', '2026-05-27'],
      total: 19,
      stageTitle: '病历池',
      isStageQueueMode: false,
    })

    expect(summary).toBe('当前筛选：中医科 / 入出院日期 2026-05-25 至 2026-05-27 / 共 19 份')
  })

  it('stage queue summary does not include date text', () => {
    const summary = buildWorkstationFilterSummary({
      activeDept: '全部科室',
      dateField: 'discharge',
      dateRange: ['2026-05-25', '2026-05-27'],
      total: 8,
      stageTitle: '参考首页生成队列',
      isStageQueueMode: true,
    })

    expect(summary).toBe('当前筛选：全部科室 / 参考首页生成队列 / 共 8 份')
  })
})
