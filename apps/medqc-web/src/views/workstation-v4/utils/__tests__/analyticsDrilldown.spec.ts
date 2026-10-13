import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AnalyticsDrilldownBar from '../../components/workbench/AnalyticsDrilldownBar.vue'
import {
  analyticsDrilldownSignature,
  analyticsStatsQuery,
  readAnalyticsDrilldown,
  withoutAnalyticsDrilldown,
} from '../analyticsDrilldown'

const DRILLDOWN_QUERY = {
  source: 'analytics',
  analytics_scope: 'final',
  analytics_rule_id: 'LX0609-06-01-05',
  analytics_completed_from: '2026-10-01T00:00:00',
  analytics_completed_to: '2026-10-08T23:59:59',
  department: 'ICU',
  keyword: 'C01',
}

describe('analyticsDrilldown', () => {
  it('从 URL 还原规则、范围、时间与科室（刷新后可恢复）', () => {
    expect(readAnalyticsDrilldown(DRILLDOWN_QUERY)).toEqual({
      ruleId: 'LX0609-06-01-05',
      scope: 'final',
      completedFrom: '2026-10-01T00:00:00',
      completedTo: '2026-10-08T23:59:59',
      jobId: '',
      resultStatus: '',
      department: 'ICU',
    })
  })

  it('非统计来源或没有统计参数时不视为下钻', () => {
    expect(readAnalyticsDrilldown({ analytics_rule_id: 'LX0609-06-01-05' })).toBeNull()
    expect(readAnalyticsDrilldown({ source: 'analytics' })).toBeNull()
    expect(readAnalyticsDrilldown({ source: 'dashboard', record_id: 'C01' })).toBeNull()
  })

  it('清除下钻只移除统计参数，保留其它筛选', () => {
    expect(withoutAnalyticsDrilldown(DRILLDOWN_QUERY)).toEqual({ department: 'ICU', keyword: 'C01' })
  })

  it('签名只随统计参数变化，用于返回/前进时重新查询', () => {
    const base = analyticsDrilldownSignature(DRILLDOWN_QUERY)
    expect(analyticsDrilldownSignature({ ...DRILLDOWN_QUERY, keyword: 'C02' })).toBe(base)
    expect(
      analyticsDrilldownSignature({ ...DRILLDOWN_QUERY, analytics_rule_id: 'LX0609-03-01-04' }),
    ).not.toBe(base)
  })

  it('返回统计时换回统计页自己的参数名', () => {
    const drilldown = readAnalyticsDrilldown({ ...DRILLDOWN_QUERY, analytics_job_id: 'job-1' })!
    expect(analyticsStatsQuery(drilldown)).toEqual({
      completed_from: '2026-10-01T00:00:00',
      completed_to: '2026-10-08T23:59:59',
      job_id: 'job-1',
    })
  })
})

describe('AnalyticsDrilldownBar', () => {
  it('明确展示规则筛选状态并提供返回与清除操作', async () => {
    const wrapper = mount(AnalyticsDrilldownBar, {
      props: { drilldown: readAnalyticsDrilldown(DRILLDOWN_QUERY)! },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })

    expect(wrapper.get('[data-testid="analytics-drilldown-rule"]').text()).toBe(
      '规则 LX0609-06-01-05',
    )
    expect(wrapper.text()).toContain('终末质控')
    expect(wrapper.text()).toContain('ICU')

    const [back, clear] = wrapper.findAll('button')
    await back.trigger('click')
    await clear.trigger('click')
    expect(wrapper.emitted('back')).toHaveLength(1)
    expect(wrapper.emitted('clear')).toHaveLength(1)
  })
})
