import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routerPush = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string | undefined> }))

vi.mock('@/services/apiService', () => ({ ApiService: { get: apiGet } }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { is_demo_account: false, roles: ['admin'] },
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeState.query,
    get fullPath() {
      return JSON.stringify(routeState.query)
    },
  }),
  useRouter: () => ({ push: routerPush }),
}))

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
      rule_id: 'LX0609-06-01-02',
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

const Stub = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h('button', attrs, slots.default?.())
  },
})
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
    routeState.query = {}
  })

  it('展示紧凑的真实统计概览与主分析模块，不展示旧 mock 指标', async () => {
    const wrapper = mountView()
    await flush()
    expect(wrapper.text()).toContain('质控统计分析')
    expect(wrapper.text()).toContain('按质控完成时间')
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).toContain('纳入病历')
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).not.toContain('按三坐标去重')
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).not.toContain('已完成根任务')
    expect(wrapper.findAll('[data-testid="analytics-kpi"]')).toHaveLength(4)
    expect(wrapper.get('[data-testid="analytics-kpis"]').text()).toContain('需优先处理')
    expect(wrapper.get('[data-testid="analytics-conclusion-structure"]').text()).toContain(
      '确定问题',
    )
    expect(wrapper.get('[data-testid="analytics-data-health"]').text()).toContain('数据状态')
    expect(wrapper.get('[data-testid="analytics-department-chart"]').text()).toContain('ICU')
    expect(wrapper.get('[data-testid="analytics-rule-chart"]').text()).toContain('LX0609-06-01-02')
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

  it('点击科室进入保留统计范围的科室报告，而不是返回质控首页', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.get('.department-row').trigger('click')

    expect(routerPush).toHaveBeenCalledWith({
      path: '/workstation-v5/stats',
      query: {
        view: 'department',
        department: 'ICU',
        completed_from: undefined,
        completed_to: undefined,
        job_id: undefined,
      },
    })
  })

  it('点击 Top 5 质控点下钻到病历池列表，而不是工作台首页', async () => {
    const wrapper = mountView()
    await flush()

    await wrapper.get('[data-testid="analytics-rule-chart"] .rule-list button').trigger('click')

    expect(routerPush).toHaveBeenCalledWith({
      path: '/workstation-v5/worklist',
      query: expect.objectContaining({
        source: 'analytics',
        analytics_scope: 'final',
        analytics_rule_id: 'LX0609-06-01-02',
        analytics_rule_name: '检查记录：CT/MRI',
      }),
    })
  })

  it('科室报告以科室条件请求同一Canonical统计，并显示返回全院入口', async () => {
    routeState.query = {
      view: 'department',
      department: 'ICU',
      completed_from: '2026-08-01T00:00:00',
      completed_to: '2026-08-08T23:59:59',
      job_id: 'job-1',
    }

    const wrapper = mountView()
    await flush()

    expect(wrapper.text()).toContain('ICU质控分析')
    expect(wrapper.text()).toContain('终末质控')
    expect(wrapper.text()).not.toContain('科室专项范围')
    expect(wrapper.text()).not.toContain('聚焦本科室已完成任务中可交付的 Canonical 结果')
    expect(wrapper.find('[data-testid="analytics-scope"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="analytics-return-hospital"]').exists()).toBe(true)
    expect(apiGet).toHaveBeenCalledWith('/api/v1/workstation/analytics/luxian-0609', {
      completed_from: '2026-08-01T00:00:00',
      completed_to: '2026-08-08T23:59:59',
      department: 'ICU',
      job_id: 'job-1',
    })
    expect(wrapper.find('[data-testid="analytics-department-chart"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="analytics-physician-chart"]').text()).toContain('张医生')
  })

  it('点击“查询”和错误态“重新加载”按钮均能触发统计请求', async () => {
    const wrapper = mountView()
    await flush()
    expect(apiGet).toHaveBeenCalledTimes(1)

    const queryButton = wrapper.findAll('button').find((btn) => btn.text().trim() === '查询')
    expect(queryButton).toBeTruthy()
    await queryButton!.trigger('click')
    await flush()
    expect(apiGet).toHaveBeenCalledTimes(2)

    apiGet.mockRejectedValueOnce(new Error('network_timeout'))
    await queryButton!.trigger('click')
    await flush()
    expect(wrapper.find('[data-testid="analytics-error"]').exists()).toBe(true)

    const reloadButton = wrapper.findAll('button').find((btn) => btn.text().trim() === '重新加载')
    expect(reloadButton).toBeTruthy()
    await reloadButton!.trigger('click')
    await flush()
    expect(apiGet).toHaveBeenCalledTimes(4)
    expect(wrapper.find('[data-testid="analytics-error"]').exists()).toBe(false)
  })
})
