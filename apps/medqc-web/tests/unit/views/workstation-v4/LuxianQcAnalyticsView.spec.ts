import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('@/services/apiService', () => ({ ApiService: { get: apiGet } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))

import LuxianQcAnalyticsView from '@/views/workstation-v4/LuxianQcAnalyticsView.vue'

const payload = {
  scope: {
    time_basis: 'qc_completed_at',
    completed_from: null,
    completed_to: null,
    department: null,
    job_id: null,
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_version: '2026-06-09',
    generated_at: '2026-08-08T12:00:00+08:00',
  },
  kpis: {
    distinct_record_total: 8,
    completed_event_total: 12,
    records_with_non_compliant: 3,
    records_with_data_gap: 4,
    canonical_invalid_or_missing_total: 2,
  },
  status_distribution: [
    { status: 'non_compliant', count: 3 },
    { status: 'data_gap', count: 4 },
    { status: 'uncertain', count: 1 },
    { status: 'compliant', count: 20 },
    { status: 'not_applicable', count: 5 },
    { status: 'not_executed', count: 0 },
  ],
  department_distribution: [
    {
      department: 'ICU',
      distinct_record_total: 8,
      non_compliant_record_total: 3,
      data_gap_record_total: 4,
      uncertain_record_total: 1,
    },
  ],
  physician_distribution: [
    {
      physician: '张医生',
      distinct_record_total: 4,
      non_compliant_record_total: 2,
      data_gap_record_total: 1,
      uncertain_record_total: 0,
    },
  ],
  rule_distribution: [
    {
      rule_id: 'LX0609-010',
      rule_name: '检查记录：CT/MRI',
      non_compliant_count: 3,
      data_gap_count: 1,
      uncertain_count: 0,
      evaluated_count: 12,
    },
  ],
  completion_time_series: null,
  data_health: { canonical_invalid_or_missing_total: 2 },
}

const Stub = defineComponent({ setup: () => () => h('div') })
async function flush() {
  await Promise.resolve()
  await nextTick()
}
function mountView() {
  return shallowMount(LuxianQcAnalyticsView, {
    global: {
      stubs: {
        'a-button': Stub,
        'a-range-picker': Stub,
        'a-select': Stub,
        'a-input': Stub,
        'a-spin': Stub,
        'a-empty': Stub,
      },
    },
  })
}

describe('LuxianQcAnalyticsView', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiGet.mockResolvedValue({ success: true, data: payload })
    routerPush.mockReset()
  })

  it('展示紧凑的真实统计概览与主分析模块，不展示旧 mock 指标', async () => {
    const wrapper = mountView()
    await flush()
    expect(wrapper.text()).toContain('质控统计分析')
    expect(wrapper.text()).toContain('按质控完成时间')
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).toContain('纳入病历')
    expect(wrapper.findAll('[data-testid="analytics-kpi"]')).toHaveLength(4)
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).toContain('需优先处理')
    expect(wrapper.get('[data-testid="analytics-conclusion-structure"]').text()).toContain(
      '确定问题',
    )
    expect(wrapper.get('[data-testid="analytics-data-health"]').text()).toContain('数据状态')
    expect(wrapper.get('[data-testid="analytics-department-chart"]').text()).toContain('ICU')
    expect(wrapper.get('[data-testid="analytics-rule-chart"]').text()).toContain('LX0609-010')
    expect(wrapper.get('[data-testid="analytics-physician-chart"]').text()).toContain('张医生')
    expect(wrapper.get('[data-testid="analytics-rule-chart"]').text()).toContain('质控点问题 Top 5')
    expect(wrapper.text()).not.toContain('平均评分')
    expect(wrapper.text()).not.toContain('AI 准确率')
  })

  it('没有至少两个真实时间桶时完全隐藏趋势图', async () => {
    const wrapper = mountView()
    await flush()
    expect(wrapper.find('[data-testid="analytics-trend"]').exists()).toBe(false)
  })

  it('只使用服务端统计接口，不在前端补全统计数据', async () => {
    const wrapper = mountView()
    await flush()
    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/analytics/luxian-0609',
      expect.any(Object),
    )
    expect(wrapper.get('[data-testid="analytics-data-health"]').text()).toContain('数据状态')
  })
})
