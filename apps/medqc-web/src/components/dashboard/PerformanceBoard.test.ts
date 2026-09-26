import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PerformanceBoard from './PerformanceBoard.vue'
import type { PerformanceData } from '@/api/dashboard'

const baseData: PerformanceData = {
  period: 'this_week',
  period_label: '本周',
  range: { start: '2026-09-21T00:00:00+08:00', end: '2026-09-27T15:30:00+08:00' },
  scene: 'all',
  defect_ranking: [
    { user_id: 'u1', name: '李质控', count: 6, approved_count: 4, rejected_count: 1, rank: 1 },
    { user_id: 'u2', name: null, count: 6, approved_count: 2, rejected_count: 0, rank: 1 },
    { user_id: 'u3', name: '王质控', count: 2, approved_count: 0, rejected_count: 2, rank: 3 },
  ],
  record_ranking: [
    { user_id: 'r1', name: '赵审核', count: 9, initial_count: 7, recheck_count: 2, rank: 1 },
  ],
  unavailable_reason: null,
}

function mountBoard(props: Partial<InstanceType<typeof PerformanceBoard>['$props']> = {}) {
  return mount(PerformanceBoard, {
    props: { period: 'this_week', status: 'ready', data: baseData, ...props },
  })
}

describe('PerformanceBoard', () => {
  it('展示姓名或回退 user_id、计数、竞争名次及分项计数', () => {
    const wrapper = mountBoard()
    const defect = wrapper.get('[data-testid="perf-section-defect"]')
    const items = defect.findAll('[data-testid="perf-item"]')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('李质控')
    expect(items[0].text()).toContain('通过 4 / 驳回 1')
    expect(items[1].text()).toContain('u2')
    expect(items[1].find('.rank-badge').text()).toBe('1')
    expect(items[2].find('.rank-badge').text()).toBe('3')

    const record = wrapper.get('[data-testid="perf-section-record"]')
    expect(record.text()).toContain('赵审核')
    expect(record.text()).toContain('9')
    expect(record.text()).toContain('初审 7 / 复审 2')
    expect(wrapper.get('[data-testid="perf-range"]').text()).toContain('2026-09-21 00:00 ~ 2026-09-27 15:30')
  })

  it('空数组显示“本期暂无”', () => {
    const wrapper = mountBoard({ data: { ...baseData, defect_ranking: [], record_ranking: [] } })
    expect(wrapper.findAll('[data-testid="perf-empty"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('本期暂无')
    expect(wrapper.find('[data-testid="perf-item"]').exists()).toBe(false)
  })

  it('场景不可归属时显示“该场景暂不支持”', () => {
    const wrapper = mountBoard({ data: {
      ...baseData,
      scene: 'running',
      defect_ranking: null,
      record_ranking: null,
      unavailable_reason: 'scene_not_attributable',
    } })
    const unavailable = wrapper.findAll('[data-testid="perf-unavailable"]')
    expect(unavailable).toHaveLength(2)
    expect(unavailable[0].text()).toBe('该场景暂不支持')
    expect(wrapper.text()).not.toContain('本期暂无')
  })

  it('失败时显示可重试，不渲染排名或 0', async () => {
    const wrapper = mountBoard({ status: 'error', data: null, errorMessage: '服务暂不可用' })
    expect(wrapper.get('[data-testid="perf-error"]').text()).toContain('服务暂不可用')
    expect(wrapper.find('[data-testid="perf-item"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="perf-range"]').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/\d/)
    await wrapper.get('[data-testid="perf-retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('加载中不显示排名或空态', () => {
    const wrapper = mountBoard({ status: 'loading', data: null })
    expect(wrapper.find('[data-testid="perf-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="perf-empty"]').exists()).toBe(false)
  })

  it('周期切换发出对应 period，点击当前周期不重复请求', async () => {
    const wrapper = mountBoard()
    expect(wrapper.get('[data-testid="perf-period-this_week"]').attributes('aria-pressed')).toBe('true')
    await wrapper.get('[data-testid="perf-period-last_week"]').trigger('click')
    await wrapper.get('[data-testid="perf-period-this_month"]').trigger('click')
    await wrapper.get('[data-testid="perf-period-this_week"]').trigger('click')
    expect(wrapper.emitted('period-change')).toEqual([['last_week'], ['this_month']])
  })
})
