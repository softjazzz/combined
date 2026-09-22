import { describe, expect, it } from 'vitest'

import {
  ANALYTICS_DRILLDOWN_RESET_PATH,
  describeAnalyticsDrilldown,
  hasAnalyticsDrilldownQuery,
  parseAnalyticsDrilldown,
  parseAnalyticsDrilldownFromQuery,
  resolveAnalyticsDrilldownResetLocation,
  stripAnalyticsDrilldown,
  stripAnalyticsDrilldownQuery,
} from '@/views/workstation-v4/analyticsDrilldown'

describe('analyticsDrilldown', () => {
  it('parses the drill-down scope written by the analytics page', () => {
    const drilldown = parseAnalyticsDrilldown(
      '?source=analytics&department=ICU&analytics_scope=final&analytics_result_status=non_compliant&analytics_rule_id=LX0609-010&analytics_completed_from=2026-01-01&analytics_completed_to=2026-02-01',
    )

    expect(drilldown).toEqual({
      scope: 'final',
      resultStatus: 'non_compliant',
      ruleId: 'LX0609-010',
      jobId: '',
      completedFrom: '2026-01-01',
      completedTo: '2026-02-01',
    })
    expect(describeAnalyticsDrilldown(drilldown!)).toEqual([
      '结果范围：最终结果',
      '结果状态：确定问题',
      '质控点：LX0609-010',
      '质控完成：2026-01-01 至 2026-02-01',
    ])
  })

  it('treats a plain bookmark query as no drill-down', () => {
    expect(parseAnalyticsDrilldown('?department=ICU&source=bookmark')).toBeNull()
    expect(hasAnalyticsDrilldownQuery({ department: 'ICU', source: 'bookmark' })).toBe(false)
  })

  it('reads drill-down state from a route query object', () => {
    const drilldown = parseAnalyticsDrilldownFromQuery({
      analytics_scope: 'final',
      analytics_result_status: ['data_gap'],
    })

    expect(drilldown?.scope).toBe('final')
    expect(drilldown?.resultStatus).toBe('data_gap')
    expect(hasAnalyticsDrilldownQuery({ analytics_job_id: 'job-1' })).toBe(true)
  })

  it('strips only the drill-down keys and keeps the remaining filters', () => {
    const search =
      'department=ICU&keyword=%E5%BC%A0%E4%B8%89&analytics_scope=final&analytics_result_status=non_compliant&source=analytics'

    const stripped = new URLSearchParams(stripAnalyticsDrilldown(search))

    expect(stripped.get('department')).toBe('ICU')
    expect(stripped.get('keyword')).toBe('张三')
    expect(stripped.get('analytics_scope')).toBeNull()
    expect(stripped.get('analytics_result_status')).toBeNull()
    expect(stripped.get('source')).toBeNull()
    expect(stripAnalyticsDrilldown('')).toBe('')
  })

  it('builds a router query without the drill-down keys', () => {
    expect(
      stripAnalyticsDrilldownQuery({
        department: 'ICU',
        source: 'analytics',
        analytics_scope: 'final',
        analytics_result_status: 'non_compliant',
        keyword: '',
      }),
    ).toEqual({ department: 'ICU' })
  })

  it('exits the drill-down inside the record pool instead of the home entry', () => {
    expect(
      resolveAnalyticsDrilldownResetLocation({
        source: 'analytics',
        department: 'ICU',
        analytics_scope: 'final',
        analytics_result_status: 'non_compliant',
      }),
    ).toEqual({
      path: ANALYTICS_DRILLDOWN_RESET_PATH,
      query: { department: 'ICU' },
    })
  })

  it('falls back to the raw status code when the label is unknown', () => {
    const drilldown = parseAnalyticsDrilldown('?analytics_result_status=brand_new_status')

    expect(describeAnalyticsDrilldown(drilldown!)).toEqual(['结果状态：brand_new_status'])
  })
})
