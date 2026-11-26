import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AnalyticsDrilldownBar from '../../components/workbench/AnalyticsDrilldownBar.vue'
import {
  analyticsDrilldownSignature,
  analyticsResultStatusLabel,
  analyticsStatsQuery,
  parseAnalyticsResultStatuses,
  readAnalyticsDrilldown,
  withoutAnalyticsDrilldown,
} from '../analyticsDrilldown'

const DRILLDOWN_QUERY = {
  source: 'analytics',
  analytics_scope: 'final',
  analytics_rule_id: 'LX0609-06-01-05',
  analytics_rule_name: '日常病程：上级医师查房分析内容',
  analytics_completed_from: '2026-10-01T00:00:00',
  analytics_completed_to: '2026-10-08T23:59:59',
  department: 'ICU',
  keyword: 'C01',
}

describe('analyticsDrilldown', () => {
  it('从 URL 还原规则、范围、时间与科室（刷新后可恢复）', () => {
    expect(readAnalyticsDrilldown(DRILLDOWN_QUERY)).toEqual({
      ruleId: 'LX0609-06-01-05',
      ruleName: '日常病程：上级医师查房分析内容',
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

  it('清除下钻移除 source、department 与全部统计参数，保留其它筛选', () => {
    expect(withoutAnalyticsDrilldown(DRILLDOWN_QUERY)).toEqual({ keyword: 'C01' })
  })

  it('签名只随统计参数与科室变化，用于返回/前进时重新查询', () => {
    const base = analyticsDrilldownSignature(DRILLDOWN_QUERY)
    expect(analyticsDrilldownSignature({ ...DRILLDOWN_QUERY, keyword: 'C02' })).toBe(base)
    expect(
      analyticsDrilldownSignature({ ...DRILLDOWN_QUERY, analytics_rule_id: 'LX0609-03-01-04' }),
    ).not.toBe(base)
    expect(
      analyticsDrilldownSignature({ ...DRILLDOWN_QUERY, department: '心内科' }),
    ).not.toBe(base)
  })

  it('返回统计时换回统计页自己的参数名并保留科室视图上下文', () => {
    const drilldown = readAnalyticsDrilldown({ ...DRILLDOWN_QUERY, analytics_job_id: 'job-1' })!
    expect(analyticsStatsQuery(drilldown)).toEqual({
      view: 'department',
      department: 'ICU',
      completed_from: '2026-10-01T00:00:00',
      completed_to: '2026-10-08T23:59:59',
      job_id: 'job-1',
    })

    const hospitalDrilldown = readAnalyticsDrilldown({
      source: 'analytics',
      analytics_scope: 'final',
      analytics_completed_from: '2026-10-01T00:00:00',
    })!
    expect(analyticsStatsQuery(hospitalDrilldown)).toEqual({
      completed_from: '2026-10-01T00:00:00',
      completed_to: undefined,
      job_id: undefined,
    })
  })
  it('支持逗号分隔多状态解析、归一化与友好中文标签', () => {
    expect(parseAnalyticsResultStatuses('non_compliant, data_gap, uncertain, non_compliant')).toEqual([
      'non_compliant',
      'data_gap',
      'uncertain',
    ])
    expect(analyticsResultStatusLabel('non_compliant')).toBe('确定问题')
    expect(analyticsResultStatusLabel('non_compliant,data_gap,uncertain')).toBe('存在问题')
    expect(analyticsResultStatusLabel('uncertain, non_compliant, data_gap')).toBe('存在问题')
    expect(analyticsResultStatusLabel('non_compliant,data_gap')).toBe('确定问题 / 资料待核实')

    const parsed = readAnalyticsDrilldown({
      ...DRILLDOWN_QUERY,
      analytics_result_status: 'non_compliant, data_gap, uncertain',
    })!
    expect(parsed.resultStatus).toBe('non_compliant,data_gap,uncertain')
    expect(
      analyticsDrilldownSignature({
        ...DRILLDOWN_QUERY,
        analytics_result_status: 'non_compliant,data_gap,uncertain',
      }),
    ).toBe(
      analyticsDrilldownSignature({
        ...DRILLDOWN_QUERY,
        analytics_result_status: 'non_compliant, data_gap, uncertain',
      }),
    )
  })
})

describe('AnalyticsDrilldownBar', () => {
  it('说明来源与命中数量，并提供返回统计与查看全部病历', async () => {
    const wrapper = mount(AnalyticsDrilldownBar, {
      props: { drilldown: readAnalyticsDrilldown(DRILLDOWN_QUERY)!, total: 29 },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })

    expect(wrapper.text()).toContain('来自统计分析')
    expect(wrapper.get('[data-testid="analytics-drilldown-rule"]').text()).toBe('LX0609-06-01-05')
    expect(wrapper.text()).toContain('日常病程：上级医师查房分析内容')
    expect(wrapper.get('[data-testid="analytics-drilldown-desc"]').text()).toContain('共 29 份')
    expect(wrapper.text()).toContain('终末质控')
    expect(wrapper.find('[data-testid="analytics-drilldown-result-status"]').exists()).toBe(false)

    const [back, clear] = wrapper.findAll('button')
    expect(back.text()).toContain('返回统计分析')
    expect(clear.text()).toContain('查看全部病历')
    await back.trigger('click')
    await clear.trigger('click')
    expect(wrapper.emitted('back')).toHaveLength(1)
    expect(wrapper.emitted('clear')).toHaveLength(1)
  })

  it('存在 analytics_result_status 时展示结论状态筛选胶囊', () => {
    const wrapper = mount(AnalyticsDrilldownBar, {
      props: {
        drilldown: readAnalyticsDrilldown({
          ...DRILLDOWN_QUERY,
          analytics_result_status: 'non_compliant',
        })!,
        total: 12,
      },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })

    expect(wrapper.get('[data-testid="analytics-drilldown-result-status"]').text()).toBe(
      '结论状态 确定问题',
    )
  })

  it('逗号分隔三类问题状态在胶囊中展示为“结论状态 存在问题”', () => {
    const wrapper = mount(AnalyticsDrilldownBar, {
      props: {
        drilldown: readAnalyticsDrilldown({
          ...DRILLDOWN_QUERY,
          analytics_result_status: 'non_compliant,data_gap,uncertain',
        })!,
        total: 18,
      },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })

    const chip = wrapper.get('[data-testid="analytics-drilldown-result-status"]')
    expect(chip.text()).toBe('结论状态 存在问题')
    expect(chip.attributes('title')).toBe('确定问题、资料待核实、待判断')
  })

  it('列表加载中不显示命中数量', () => {
    const wrapper = mount(AnalyticsDrilldownBar, {
      props: { drilldown: readAnalyticsDrilldown(DRILLDOWN_QUERY)!, total: null },
      global: { stubs: { 'a-button': { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.get('[data-testid="analytics-drilldown-desc"]').text()).not.toContain('共')
  })
})
