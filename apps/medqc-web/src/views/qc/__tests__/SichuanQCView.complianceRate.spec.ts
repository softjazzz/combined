import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

import SichuanQCView from '../SichuanQCView.vue'

const StatisticStub = {
  name: 'AStatistic',
  props: ['title', 'value', 'prefix', 'suffix', 'precision', 'valueStyle'],
  template: `
    <div
      class="stat-stub"
      :data-title="title"
      :data-value="String(value ?? '')"
      :data-suffix="suffix ?? ''"
      :data-precision="precision ?? ''"
      :data-color="valueStyle?.color ?? ''"
    >
      {{ title }}: {{ value }}{{ suffix || '' }}
    </div>
  `,
}

const PassthroughStub = {
  template: '<div><slot /></div>',
}

const ButtonStub = {
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
}

function mockFetch(evalPayload: Record<string, unknown>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/api/v1/qc/sichuan/evaluate')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: evalPayload }),
        text: async () => '',
      } as Response
    }
    if (url.includes('/api/v1/qc/sichuan/rules')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: { rules: [], total_rules: 0 } }),
      } as Response
    }
    if (url.includes('/api/v1/qc/settings')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ settings: {} }),
      } as Response
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ providers: [], models: [] }),
    } as Response
  })
}

function mountView() {
  return mount(SichuanQCView, {
    global: {
      stubs: {
        'a-row': PassthroughStub,
        'a-col': PassthroughStub,
        'a-card': PassthroughStub,
        'a-statistic': StatisticStub,
        'a-input': PassthroughStub,
        'a-select': PassthroughStub,
        'a-select-option': PassthroughStub,
        'a-select-opt-group': PassthroughStub,
        'a-button': ButtonStub,
        'a-collapse': PassthroughStub,
        'a-collapse-panel': PassthroughStub,
        'a-input-number': PassthroughStub,
        'a-slider': PassthroughStub,
        'a-tabs': PassthroughStub,
        'a-tab-pane': PassthroughStub,
        'a-upload-dragger': PassthroughStub,
        'a-form': PassthroughStub,
        'a-form-item': PassthroughStub,
        'a-divider': PassthroughStub,
        'a-table': PassthroughStub,
        'a-tag': PassthroughStub,
        'a-progress': PassthroughStub,
        'a-tooltip': PassthroughStub,
        'a-alert': PassthroughStub,
        'a-descriptions': PassthroughStub,
        'a-descriptions-item': PassthroughStub,
        MedicineBoxOutlined: true,
        'play-circle-outlined': true,
        'inbox-outlined': true,
        'reload-outlined': true,
        'bar-chart-outlined': true,
      },
    },
  })
}

function buildEvalPayload(summary: Record<string, unknown>) {
  return {
    evaluation_summary: {
      overall_grade: '暂无',
      ...summary,
    },
    performance_metrics: {
      token_usage: 120,
      estimated_cost: 0.01,
      processing_time: 1.2,
    },
    optimization_metrics: {
      token_savings_rate: 0.8,
      cost_savings: 0.04,
    },
    evaluation_results: [],
  }
}

describe('SichuanQCView P1-G2 合规率空值保护', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  async function runWithSummary(summary: Record<string, unknown>) {
    globalThis.fetch = mockFetch(buildEvalPayload(summary)) as unknown as typeof fetch
    const wrapper = mountView()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      linkedRecordId: string
      startEvaluationWithLinkedRecord: () => Promise<void>
    }
    vm.linkedRecordId = 'REC-001'
    await vm.startEvaluationWithLinkedRecord()
    await flushPromises()
    return wrapper
  }

  it('compliance_rate 为 null 且存在规则时展示“无适用项”、不带%且使用中性色（不落入红色告警）', async () => {
    const wrapper = await runWithSummary({ compliance_rate: null, total_rules: 5 })
    const stat = wrapper.get('[data-title="合规率"]')
    expect(stat.attributes('data-value')).toBe('无适用项')
    expect(stat.attributes('data-suffix')).toBe('')
    expect(stat.attributes('data-precision')).toBe('')
    expect(stat.attributes('data-color')).toBe('#8c8c8c')
    expect(stat.text()).not.toContain('NaN')
    expect(stat.text()).not.toContain('0%')
    wrapper.unmount()
  })

  it('compliance_rate 为 null 且 total_rules 为 0 时展示“--”并使用中性色', async () => {
    const wrapper = await runWithSummary({ compliance_rate: null, total_rules: 0 })
    const stat = wrapper.get('[data-title="合规率"]')
    expect(stat.attributes('data-value')).toBe('--')
    expect(stat.attributes('data-suffix')).toBe('')
    expect(stat.attributes('data-color')).toBe('#8c8c8c')
    wrapper.unmount()
  })

  it('compliance_rate 为 undefined 或 NaN 时展示“--”并使用中性色', async () => {
    const wrapper = await runWithSummary({ compliance_rate: undefined, total_rules: 3 })
    const stat = wrapper.get('[data-title="合规率"]')
    expect(stat.attributes('data-value')).toBe('--')
    expect(stat.attributes('data-suffix')).toBe('')
    expect(stat.attributes('data-color')).toBe('#8c8c8c')
    wrapper.unmount()
  })

  it('有效数值合规率（含 0 与正常分档）正常展示百分比与分档颜色', async () => {
    const high = await runWithSummary({ compliance_rate: 96.5, total_rules: 10 })
    expect(high.get('[data-title="合规率"]').attributes('data-value')).toBe('96.5')
    expect(high.get('[data-title="合规率"]').attributes('data-suffix')).toBe('%')
    expect(high.get('[data-title="合规率"]').attributes('data-precision')).toBe('1')
    expect(high.get('[data-title="合规率"]').attributes('data-color')).toBe('#52c41a')
    high.unmount()

    const zero = await runWithSummary({ compliance_rate: 0, total_rules: 10 })
    expect(zero.get('[data-title="合规率"]').attributes('data-value')).toBe('0')
    expect(zero.get('[data-title="合规率"]').attributes('data-suffix')).toBe('%')
    expect(zero.get('[data-title="合规率"]').attributes('data-color')).toBe('#ff4d4f')
    zero.unmount()
  })
})
