import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LlmPerformanceObservabilityPanel from '@/views/workstation-v4/components/system-config/LlmPerformanceObservabilityPanel.vue'
import { getLlmObservabilityOverview, getLlmRecordCallAttempts } from '@/services/llmObservability'
import type { LlmObservabilityOverview, LlmRecordCallAttempts } from '@/types/llmObservability'

vi.mock('@/services/llmObservability', () => ({
  getLlmObservabilityOverview: vi.fn(),
  getLlmRecordCallAttempts: vi.fn(),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="v-chart-stub">{{ JSON.stringify(option.xAxis?.data) }}</div>',
  },
}))

const overview: LlmObservabilityOverview = {
  range: {
    start_at: '2026-08-03T00:00:00Z',
    end_at: '2026-08-10T00:00:00Z',
    timezone: 'Asia/Shanghai',
  },
  kpis: {
    logical_calls: 8,
    http_attempts: 9,
    record_count: 2,
    input_tokens: 1200,
    output_tokens: 300,
    total_tokens: 1500,
    avg_latency_ms: 1200,
    p95_latency_ms: 1800,
    peak_concurrency: 3,
    retry_attempts: 1,
    successful_attempts: 8,
    failed_attempts: 1,
    unknown_usage_attempts: 0,
  },
  trends: [
    {
      bucket: '2026-08-10',
      logical_calls: 8,
      http_attempts: 9,
      input_tokens: 1200,
      output_tokens: 300,
      total_tokens: 1500,
      p95_latency_ms: 1800,
      peak_concurrency: 3,
      unknown_usage_attempts: 0,
    },
  ],
  models: [
    {
      provider_code: 'openai-compatible',
      model: 'medical-model',
      model_role: 'qc_fact_extractor',
      logical_calls: 8,
      http_attempts: 9,
      total_tokens: 1500,
      avg_latency_ms: 1200,
      unknown_usage_attempts: 0,
    },
  ],
  safe_errors: [{ safe_error_kind: 'timeout', count: 1 }],
  records: {
    items: [
      {
        record_key_hash: 'abcdef1234567890abcdef1234567890',
        logical_calls: 8,
        http_attempts: 9,
        input_tokens: 1200,
        output_tokens: 300,
        total_tokens: 1500,
        p95_latency_ms: 1800,
        unknown_usage_attempts: 0,
        last_called_at: '2026-08-10T10:00:00Z',
        status: 'partial_failure',
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  },
}

const calls: LlmRecordCallAttempts = {
  record_key_hash: 'abcdef1234567890abcdef1234567890',
  items: [
    {
      logical_call_id: 'logical-1',
      attempt_no: 1,
      business_scene: 'luxian_0609_qc',
      root_job_id: 'job-1',
      executor_key: 'LX0609-025',
      provider_code: 'openai-compatible',
      model: 'medical-model',
      model_role: 'quality_control',
      status: 'success',
      safe_error_kind: null,
      usage_state: 'known',
      input_tokens: 1200,
      output_tokens: 300,
      total_tokens: 1500,
      latency_ms: 1200,
      started_at: '2026-08-10T10:00:00Z',
      finished_at: '2026-08-10T10:00:01Z',
    },
    {
      logical_call_id: 'logical-2',
      attempt_no: 1,
      business_scene: 'luxian_0609_qc',
      root_job_id: 'job-1',
      executor_key: 'LX0609-044',
      provider_code: 'openai-compatible',
      model: 'medical-model',
      model_role: 'quality_control',
      status: 'timeout',
      safe_error_kind: 'timeout',
      usage_state: 'unknown',
      input_tokens: null,
      output_tokens: null,
      total_tokens: null,
      latency_ms: 30000,
      started_at: '2026-08-10T10:01:00Z',
      finished_at: '2026-08-10T10:01:30Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
}

function mountPanel() {
  return mount(LlmPerformanceObservabilityPanel, {
    global: {
      stubs: {
        'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'a-select': {
          props: ['value', 'options'],
          emits: ['update:value', 'change'],
          template:
            '<button class="select-stub" @click="$emit(\'update:value\', options[1]?.value); $emit(\'change\', options[1]?.value)">{{ JSON.stringify(options) }}</button>',
        },
        'a-drawer': {
          props: ['open'],
          template: '<aside v-if="open" data-testid="attempt-drawer"><slot /></aside>',
        },
        'a-pagination': { template: '<div class="pagination-stub" />' },
        'a-spin': { template: '<div class="spin-stub"><slot /></div>' },
      },
    },
  })
}

describe('LlmPerformanceObservabilityPanel', () => {
  beforeEach(() => {
    vi.mocked(getLlmObservabilityOverview).mockReset()
    vi.mocked(getLlmRecordCallAttempts).mockReset()
    vi.mocked(getLlmObservabilityOverview).mockResolvedValue(overview)
    vi.mocked(getLlmRecordCallAttempts).mockResolvedValue(calls)
  })

  it('展示真实 KPI、两张趋势图和脱敏病历列表', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('逻辑调用')
    expect(wrapper.text()).toContain('HTTP 尝试')
    expect(wrapper.text()).toContain('总 Token')
    expect(wrapper.text()).toContain('1,500')
    expect(wrapper.text()).toContain('P95 响应')
    expect(wrapper.text()).toContain('峰值并发')
    expect(wrapper.text()).toContain('不含独立部署的 SQLBot')
    expect(wrapper.findAll('.v-chart-stub')).toHaveLength(2)
    expect(wrapper.findAll('.v-chart-stub')[0].text()).toBe('["08-10"]')
    expect(wrapper.text()).toContain('质控事实抽取模型')
    expect(wrapper.text()).toContain('病历 #abcdef12')
    expect(wrapper.text()).not.toContain('abcdef1234567890abcdef1234567890')
    expect(wrapper.text()).not.toContain('patient_id')
    expect(wrapper.text()).not.toContain('visit_id')
  })

  it('使用后端真实业务场景枚举发起筛选请求', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    vi.mocked(getLlmObservabilityOverview).mockClear()

    await wrapper.get('[data-testid="business-scene-filter"]').trigger('click')
    await flushPromises()

    expect(getLlmObservabilityOverview).toHaveBeenCalledWith(
      expect.objectContaining({ business_scene: 'luxian_0609_qc' }),
    )
    const options = wrapper.get('[data-testid="business-scene-filter"]').text()
    for (const scene of [
      'coding_qc',
      'frontpage_extraction',
      'frontpage_report_generation',
      'custom_qc_prompt_generation',
      'legacy_llm_proxy',
      'llm_config_probe',
      'luxian_0609_preproduction',
      'smart_upload_field_mapping',
      'icd_coding',
      'diagnosis_surgery_profiling',
      'qc_agent_intent',
      'demo_custom_rule_generation',
      'icd_semantic_embedding',
    ]) {
      expect(options).toContain(scene)
    }
    expect(options).not.toContain('"value":"custom_qc"')
    expect(options).not.toContain('"value":"llm_proxy"')
  })

  it('缓存历次模型选项，服务商筛选后仍可切回其他已知服务商', async () => {
    vi.mocked(getLlmObservabilityOverview)
      .mockResolvedValueOnce({
        ...overview,
        models: [
          ...overview.models,
          {
            ...overview.models[0],
            provider_code: 'deepseek',
            model: 'deepseek-chat',
          },
        ],
      })
      .mockResolvedValueOnce({ ...overview, models: [] })

    const wrapper = mountPanel()
    await flushPromises()

    const providerFilter = wrapper.get('[data-testid="provider-filter"]')
    expect(providerFilter.text()).toContain('deepseek')
    expect(providerFilter.text()).toContain('openai-compatible')

    await providerFilter.trigger('click')
    await flushPromises()

    expect(providerFilter.text()).toContain('deepseek')
    expect(providerFilter.text()).toContain('openai-compatible')
  })

  it('快速连续筛选时只接受最后一次请求结果', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    let resolveSlow!: (value: LlmObservabilityOverview) => void
    let resolveFast!: (value: LlmObservabilityOverview) => void
    const slow = new Promise<LlmObservabilityOverview>((resolve) => {
      resolveSlow = resolve
    })
    const fast = new Promise<LlmObservabilityOverview>((resolve) => {
      resolveFast = resolve
    })
    vi.mocked(getLlmObservabilityOverview)
      .mockImplementationOnce(() => slow)
      .mockImplementationOnce(() => fast)

    await wrapper.get('[data-testid="provider-filter"]').trigger('click')
    await wrapper.get('[data-testid="business-scene-filter"]').trigger('click')
    resolveFast({
      ...overview,
      kpis: { ...overview.kpis, logical_calls: 22 },
    })
    await flushPromises()
    resolveSlow({
      ...overview,
      kpis: { ...overview.kpis, logical_calls: 11 },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('逻辑调用22')
    expect(wrapper.text()).not.toContain('逻辑调用11')
  })

  it('快速切换病历时只接受最后一次明细请求结果', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('[data-testid="view-record-calls"]').trigger('click')
    await flushPromises()
    vi.mocked(getLlmRecordCallAttempts).mockClear()

    let resolveSlow!: (value: LlmRecordCallAttempts) => void
    let resolveFast!: (value: LlmRecordCallAttempts) => void
    const slow = new Promise<LlmRecordCallAttempts>((resolve) => {
      resolveSlow = resolve
    })
    const fast = new Promise<LlmRecordCallAttempts>((resolve) => {
      resolveFast = resolve
    })
    vi.mocked(getLlmRecordCallAttempts)
      .mockImplementationOnce(() => slow)
      .mockImplementationOnce(() => fast)

    const vm = wrapper.vm as unknown as {
      openRecordCalls: (hash: string) => Promise<void>
    }
    const first = vm.openRecordCalls('record-a-hash')
    const second = vm.openRecordCalls('record-b-hash')
    resolveFast({
      ...calls,
      record_key_hash: 'record-b-hash',
      items: [{ ...calls.items[0], executor_key: 'LATEST-RESULT' }],
    })
    await second
    resolveSlow({
      ...calls,
      record_key_hash: 'record-a-hash',
      items: [{ ...calls.items[0], executor_key: 'STALE-RESULT' }],
    })
    await first
    await flushPromises()

    expect(wrapper.text()).toContain('LATEST-RESULT')
    expect(wrapper.text()).not.toContain('STALE-RESULT')
  })

  it('首次进入页面时展示明确加载状态，避免空白闪屏', async () => {
    vi.mocked(getLlmObservabilityOverview).mockReturnValue(new Promise(() => undefined))

    const wrapper = mountPanel()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('正在读取真实模型调用数据')
    expect(wrapper.text()).not.toContain('当前范围暂无真实模型调用记录')
  })

  it('点击脱敏病历后按 HTTP 尝试展示明细，未知 Token 不显示为 0', async () => {
    vi.mocked(getLlmRecordCallAttempts).mockResolvedValue({ ...calls, total: 25 })
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('[data-testid="view-record-calls"]').trigger('click')
    await flushPromises()

    expect(getLlmRecordCallAttempts).toHaveBeenCalledWith(
      'abcdef1234567890abcdef1234567890',
      expect.objectContaining({
        start_at: expect.any(String),
        end_at: expect.any(String),
        provider_code: undefined,
        model: undefined,
        business_scene: undefined,
        page: 1,
      }),
    )
    expect(wrapper.find('[data-testid="attempt-drawer"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('LX0609-025')
    expect(wrapper.text()).toContain('第 1 次尝试')
    expect(wrapper.text()).toContain('用量已上报')
    expect(wrapper.text()).toContain('用量未上报')
    expect(wrapper.text()).toContain('未知')
    expect(wrapper.text()).not.toContain('job-1')
    expect(wrapper.find('.pagination-stub').exists()).toBe(true)
  })

  it('无真实调用时不显示空图表并给出诚实空状态', async () => {
    vi.mocked(getLlmObservabilityOverview).mockResolvedValue({
      ...overview,
      kpis: {
        ...overview.kpis,
        logical_calls: 0,
        http_attempts: 0,
        record_count: 0,
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
      },
      trends: [],
      models: [],
      safe_errors: [],
      records: { items: [], total: 0, page: 1, page_size: 20 },
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.findAll('.v-chart-stub')).toHaveLength(0)
    expect(wrapper.text()).toContain('当前范围暂无真实模型调用记录')
  })

  it('模型未上报用量时明确显示未知，不把 Token 和响应时间伪装为 0', async () => {
    vi.mocked(getLlmObservabilityOverview).mockResolvedValue({
      ...overview,
      kpis: {
        ...overview.kpis,
        input_tokens: null,
        output_tokens: null,
        total_tokens: null,
        avg_latency_ms: null,
        p95_latency_ms: null,
        unknown_usage_attempts: 9,
      },
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Token未知')
    expect(wrapper.text()).not.toContain('总 Token未知')
    expect(wrapper.text()).toContain('输入 未知 · 输出 未知')
    expect(wrapper.text()).toContain('P95 响应未知')
    expect(wrapper.text()).toContain('Token 未上报 9')
  })

  it('存在部分未上报用量时将全部聚合 Token 明确标为已上报值', async () => {
    vi.mocked(getLlmObservabilityOverview).mockResolvedValue({
      ...overview,
      kpis: { ...overview.kpis, unknown_usage_attempts: 2 },
      trends: overview.trends.map((item) => ({ ...item, unknown_usage_attempts: 2 })),
      models: overview.models.map((item) => ({ ...item, unknown_usage_attempts: 2 })),
      records: {
        ...overview.records,
        items: overview.records.items.map((item) => ({ ...item, unknown_usage_attempts: 2 })),
      },
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('已上报 Token')
    expect(wrapper.text()).toContain('2 次未上报')
    const chart = wrapper.findAllComponents({ name: 'VChart' })[0]
    expect(chart.props('option').series[2].name).toBe('已上报 Token')
  })

  it('将观测事实中的安全错误类别翻译为客户可读文案', async () => {
    vi.mocked(getLlmObservabilityOverview).mockResolvedValue({
      ...overview,
      safe_errors: [
        { safe_error_kind: 'http_transport', count: 1 },
        { safe_error_kind: 'configuration', count: 1 },
        { safe_error_kind: 'upstream_4xx', count: 1 },
        { safe_error_kind: 'stale_running', count: 1 },
      ],
    })

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('网络连接失败')
    expect(wrapper.text()).toContain('配置不可用')
    expect(wrapper.text()).toContain('上游请求被拒绝')
    expect(wrapper.text()).toContain('调用未正常结束')
  })

  it('接口失败时展示可重试状态且不伪造 KPI', async () => {
    vi.mocked(getLlmObservabilityOverview).mockRejectedValue(new Error('secret SQL error'))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('模型性能数据暂不可用')
    expect(wrapper.text()).not.toContain('secret SQL error')
    expect(wrapper.text()).not.toContain('逻辑调用')
  })
})
