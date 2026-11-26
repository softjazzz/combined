/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  apiGet: vi.fn(),
  getRecordQualityReport: vi.fn(),
  getRecordQualityRecords: vi.fn(),
  exportRecordQualityReport: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  route: {
    path: '/workstation-v5/stats',
    query: {} as Record<string, string | string[] | undefined>,
  },
  authUser: {
    id: 'user-1',
    institute_id: 'H1',
    department: '内科',
    roles: ['admin'] as string[],
    is_demo_account: false,
  },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: state.apiGet,
  },
}))

vi.mock('@/api/qualityReports', () => ({
  getRecordQualityReport: state.getRecordQualityReport,
  getRecordQualityRecords: state.getRecordQualityRecords,
  exportRecordQualityReport: state.exportRecordQualityReport,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return state.authUser
    },
    get userRoles() {
      return state.authUser.roles
    },
  }),
}))

vi.mock('vue-router', async () => {
  const { reactive: vueReactive } = await import('vue')
  state.route = vueReactive({
    path: '/workstation-v5/stats',
    query: {} as Record<string, string | string[] | undefined>,
  })
  return {
    useRoute: () => ({
      get path() {
        return state.route.path
      },
      get query() {
        return state.route.query
      },
      get fullPath() {
        return `${state.route.path}?${JSON.stringify(state.route.query)}`
      },
    }),
    useRouter: () => ({
      push: state.routerPush,
      replace: state.routerReplace,
    }),
  }
})

vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

import LuxianQcAnalyticsView from '@/views/workstation-v4/LuxianQcAnalyticsView.vue'
import RecordQualityReportView from '@/views/qc/reports/RecordQualityReportView.vue'

const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          ...attrs,
          onClick: () => emit('click'),
        },
        slots.default?.(),
      )
  },
})

const RangePickerStub = defineComponent({
  name: 'ARangePickerStub',
  props: ['value', 'showTime', 'format', 'valueFormat', 'placeholder'],
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('div', {
        ...attrs,
        'data-testid': 'range-picker-stub',
        'data-show-time': String(props.showTime ?? false),
        'data-format': props.format ?? '',
        'data-value-format': props.valueFormat ?? '',
        'data-value': JSON.stringify(props.value ?? null),
        onClick: () => emit('update:value', ['2026-08-01', '2026-08-08']),
      })
  },
})

const SelectStub = defineComponent({
  name: 'ASelectStub',
  props: ['value', 'options'],
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value ?? '',
          onChange: (event: Event) => {
            const val = (event.target as HTMLSelectElement).value
            emit('update:value', val || undefined)
          },
        },
        [
          h('option', { value: '' }, '全部科室'),
          ...((props.options as Array<{ label: string; value: string }>) || []).map((opt) =>
            h('option', { value: opt.value }, opt.label),
          ),
        ],
      )
  },
})

const InputStub = defineComponent({
  name: 'AInputStub',
  props: ['value'],
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h('input', {
        ...attrs,
        value: props.value ?? '',
        onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
      })
  },
})

const DrawerStub = defineComponent({
  name: 'ADrawerStub',
  props: ['open', 'title', 'width', 'rootStyle', 'keyboard'],
  emits: ['update:open', 'close'],
  setup(props, { slots }) {
    return () =>
      props.open
        ? h(
            'aside',
            {
              'data-testid': 'drilldown-drawer',
              'data-keyboard': String(props.keyboard ?? ''),
            },
            slots.default?.(),
          )
        : null
  },
})

function makeAnalyticsPayload(overrides: Record<string, unknown> = {}) {
  return {
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
      distinct_record_total: 44,
      completed_event_total: 103,
      records_with_non_compliant: 29,
      records_with_data_gap: 12,
      canonical_invalid_or_missing_total: 0,
    },
    status_distribution: [
      { status: 'non_compliant', count: 54 },
      { status: 'data_gap', count: 4 },
      { status: 'compliant', count: 200 },
    ],
    department_options: ['外一科', '重症医学科（ICU）'],
    department_distribution: [
      {
        department: '外一科',
        distinct_record_total: 12,
        non_compliant_record_total: 8,
        data_gap_record_total: 2,
        uncertain_record_total: 0,
        problem_record_total: 10,
        primary_non_compliant_record_total: 8,
        primary_data_gap_record_total: 2,
        primary_uncertain_record_total: 0,
      },
    ],
    physician_distribution: [
      {
        physician: '张医生',
        distinct_record_total: 12,
        non_compliant_record_total: 8,
        data_gap_record_total: 2,
        uncertain_record_total: 0,
        problem_record_total: 10,
        primary_non_compliant_record_total: 8,
        primary_data_gap_record_total: 2,
        primary_uncertain_record_total: 0,
      },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-06-01-05',
        rule_name: '检查记录完整性',
        distinct_record_count: 22,
        non_compliant_record_count: 20,
        data_gap_record_count: 2,
        uncertain_record_count: 0,
        non_compliant_count: 54,
        data_gap_count: 4,
        uncertain_count: 0,
        evaluated_count: 103,
      },
      {
        rule_id: 'LX0609-06-01-04',
        rule_name: '主诉与现病史一致',
        distinct_record_count: 17,
        non_compliant_record_count: 15,
        data_gap_record_count: 2,
        uncertain_record_count: 0,
        non_compliant_count: 41,
        data_gap_count: 8,
        uncertain_count: 0,
        evaluated_count: 103,
      },
      {
        rule_id: 'LX0609-06-01-99',
        rule_name: '仅资料待核实项',
        distinct_record_count: 5,
        non_compliant_record_count: 0,
        data_gap_record_count: 5,
        uncertain_record_count: 0,
        non_compliant_count: 0,
        data_gap_count: 9,
        uncertain_count: 0,
        evaluated_count: 103,
      },
    ],
    completion_time_series: null,
    data_health: { canonical_invalid_or_missing_total: 0 },
    ...overrides,
  }
}

function makeRecordQualityReport(scene: 'running' | 'final' = 'final') {
  return {
    scope: {
      scene,
      archive_status: scene === 'final' ? 'unverified' : null,
    },
    score_standard: {
      status: 'no_standard',
      standard_id: null,
      standard_name: null,
      standard_updated_at: null,
    },
    source_status: { review: 'available', manual_defect: 'available' },
    kpis: {
      record_total: 10,
      qc_ready_total: 8,
      qc_unavailable_total: 0,
      scored_total: 0,
      average_score: null,
      top_grade_rate: null,
      review_approved_total: 4,
      auto_defect_total: 12,
      manual_defect_total: 1,
      manual_defect_rejected_total: 0,
      veto_defect_total: 0,
      veto_record_total: 0,
    },
    grade_distribution: [],
    score_distribution: [],
    defect_level_distribution: [],
    defect_type_distribution: [],
    document_distribution: [],
    top_rules: [],
    top_categories: [],
    top_types: [],
    top_veto_rules: [],
    top_documents: [],
    classification_unknown: null,
    department_rows: [
      {
        name: '重症医学科（ICU）',
        record_total: 8,
        qc_ready_total: 8,
        average_score: null,
        top_grade_rate: null,
        review_approved_total: 3,
        reviewed_total: 4,
        top_grade_total: 0,
        defect_total: 12,
        average_defect_total: 1.5,
        auto_defect_total: 12,
        manual_defect_total: 0,
        veto_defect_total: 0,
        veto_record_total: 0,
        records_with_defect: 6,
      },
    ],
    doctor_rows: [],
    unavailable_dimensions: [],
  }
}

function mountAnalytics() {
  return shallowMount(LuxianQcAnalyticsView, {
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-range-picker': RangePickerStub,
        'a-select': SelectStub,
        'a-input': InputStub,
        'a-spin': { template: '<div />' },
        'a-empty': { template: '<div />' },
      },
    },
  })
}

function mountRecordQuality() {
  return mount(RecordQualityReportView, {
    global: {
      stubs: {
        'a-drawer': DrawerStub,
        CoreSystemReportPanel: true,
        RecordRemediationAnalysisPanel: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  state.route.path = '/workstation-v5/stats'
  state.route.query = {}
  state.authUser = reactive({
    id: 'user-1',
    institute_id: 'H1',
    department: '内科',
    roles: ['admin'],
    is_demo_account: false,
  })
  state.routerReplace.mockImplementation(
    async (loc: { path?: string; query?: Record<string, string | undefined> }) => {
      if (loc.path) state.route.path = loc.path
      state.route.query = { ...(loc.query || {}) }
    },
  )
  state.apiGet.mockResolvedValue({ success: true, data: makeAnalyticsPayload() })
  state.getRecordQualityReport.mockImplementation(async (filters: { scene: 'running' | 'final' }) => ({
    success: true,
    data: makeRecordQualityReport(filters.scene),
  }))
  state.getRecordQualityRecords.mockResolvedValue({
    success: true,
    data: { total: 1, page: 1, page_size: 20, items: [] },
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('P1 #9 & #8b: LuxianQcAnalyticsView 统计分析修复', () => {
  it('移除 RangePicker show-time 改为纯日期选择，同时向后端/URL/下钻兼容补全起止时分秒', async () => {
    const wrapper = mountAnalytics()
    await flushPromises()

    const picker = wrapper.get('[data-testid="range-picker-stub"]')
    expect(picker.attributes('data-show-time')).toBe('false')
    expect(picker.attributes('data-format')).toBe('YYYY-MM-DD')
    expect(picker.attributes('data-value-format')).toBe('YYYY-MM-DD')

    // 点选纯日期范围 ['2026-08-01', '2026-08-08'] 后点击查询
    await picker.trigger('click')
    state.apiGet.mockClear()
    const queryBtn = wrapper.findAll('button').find((b) => b.text().trim() === '查询')!
    await queryBtn.trigger('click')
    await flushPromises()

    // 查询严格只发 1 次，并补全 00:00:00 / 23:59:59 兼容后端 datetime 校验
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(state.apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/analytics/luxian-0609',
      {
        completed_from: '2026-08-01T00:00:00',
        completed_to: '2026-08-08T23:59:59',
        department: undefined,
        job_id: undefined,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(state.route.query).toEqual({
      completed_from: '2026-08-01T00:00:00',
      completed_to: '2026-08-08T23:59:59',
    })

    // 点击 Top 5 下钻携带完整起止时间戳
    await wrapper.get('[data-testid="analytics-rule-chart"] .rule-list button').trigger('click')
    expect(state.routerPush).toHaveBeenCalledWith({
      path: '/workstation-v5/worklist',
      query: expect.objectContaining({
        analytics_completed_from: '2026-08-01T00:00:00',
        analytics_completed_to: '2026-08-08T23:59:59',
      }),
    })
    wrapper.unmount()

    // URL 带 ISO 时间戳回填时，RangePicker 以纯日期 YYYY-MM-DD 展示
    state.route.query = {
      completed_from: '2026-08-01T00:00:00',
      completed_to: '2026-08-08T23:59:59',
    }
    const hydrated = mountAnalytics()
    await flushPromises()
    expect(hydrated.get('[data-testid="range-picker-stub"]').attributes('data-value')).toBe(
      JSON.stringify(['2026-08-01', '2026-08-08']),
    )
    hydrated.unmount()
  })

  it('消除嵌套 <main> 地标：根节点使用 <section class="analytics-canvas">', async () => {
    const wrapper = mountAnalytics()
    await flushPromises()

    expect(wrapper.find('main').exists()).toBe(false)
    const canvas = wrapper.get('section.analytics-canvas')
    expect(canvas.attributes('aria-label')).toBe('质控统计分析')
    wrapper.unmount()
  })

  it('首屏仅发 1 次请求且不被取消重发；无关 query 变化与离页导航均不重复发请求', async () => {
    const signals: AbortSignal[] = []
    state.apiGet.mockImplementation(async (_url, _params, config) => {
      signals.push(config.signal)
      return { success: true, data: makeAnalyticsPayload() }
    })

    const wrapper = mountAnalytics()
    await flushPromises()

    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(signals).toHaveLength(1)
    expect(signals[0]?.aborted).toBe(false)

    // 无关 query 参数变化（如 source_id）不触发取消重发
    state.route.query = { source_id: 'legacy_pg' }
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)
    expect(signals[0]?.aborted).toBe(false)

    // 离开 /stats 页面到 /worklist（带 department）时不触发多余统计请求
    state.route.path = '/workstation-v5/worklist'
    state.route.query = { source: 'analytics', department: '外一科' }
    await flushPromises()
    expect(state.apiGet).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('Top 5 卡片按去重命中病历数展示并附注事件次数，演示态与下钻一致', async () => {
    const wrapper = mountAnalytics()
    await flushPromises()

    const ruleButtons = wrapper.findAll('[data-testid="analytics-rule-chart"] .rule-list button')
    expect(ruleButtons).toHaveLength(3)
    expect(ruleButtons[0]!.get('.rule-count strong').text()).toBe('22')
    expect(ruleButtons[0]!.get('.rule-count').text()).toContain('命中病历')
    expect(ruleButtons[0]!.get('[data-testid="rule-event-count"]').text()).toBe('58 次事件')
    expect(ruleButtons[1]!.get('.rule-count strong').text()).toBe('17')
    expect(ruleButtons[1]!.get('[data-testid="rule-event-count"]').text()).toBe('49 次事件')
    wrapper.unmount()

    // 演示态优先读取 non_compliant_record_count / 后端裁剪后的 distinct_record_count，过滤纯待核实规则
    state.authUser.is_demo_account = true
    const demoWrapper = mountAnalytics()
    await flushPromises()

    const demoButtons = demoWrapper.findAll('[data-testid="analytics-rule-chart"] .rule-list button')
    expect(demoButtons).toHaveLength(2)
    expect(demoButtons[0]!.get('.rule-count strong').text()).toBe('20')
    expect(demoButtons[0]!.get('.rule-count').text()).toContain('命中病历')
    expect(demoButtons[0]!.get('[data-testid="rule-event-count"]').text()).toBe('54 次事件')
    expect(demoWrapper.text()).not.toContain('仅资料待核实项')
    demoWrapper.unmount()
  })

  it('统计分析筛选区收紧 1440/1280 折行并清除「已完成任务 ID」输入框内层胶囊视觉嵌套', () => {
    const source = readFileSync(
      resolve(__dirname, '../../src/views/workstation-v4/LuxianQcAnalyticsView.vue'),
      'utf8',
    )
    expect(source).not.toContain('show-time')
    expect(source).toMatch(
      /\.analytics-toolbar\s*:deep\(\.ant-input-affix-wrapper\s+\.ant-input\)[\s\S]*?border:\s*0\s*!important;[\s\S]*?background:\s*transparent\s*!important;[\s\S]*?box-shadow:\s*none\s*!important;/,
    )
    expect(source).toMatch(
      /@media\s*\(max-width:\s*1440px\)\s*\{[\s\S]*?\.analytics-heading\s*\{[\s\S]*?flex-direction:\s*column;/,
    )
  })
})

describe('P1 #11: RecordQualityReportView 病历质量分析修复', () => {
  it('无 URL ?scene= 时默认进入 scene=final（终末病历），显式传 ?scene=running 时严格尊重 URL', async () => {
    state.route.path = '/workstation-v5/reports/record-quality'
    state.route.query = {}

    const defaultWrapper = mountRecordQuality()
    await flushPromises()

    expect(state.getRecordQualityReport).toHaveBeenCalledWith(
      expect.objectContaining({ scene: 'final', defect_source: 'all' }),
      expect.any(AbortSignal),
    )
    const sceneButtons = defaultWrapper.findAll('[aria-labelledby="report-scene-label"] button')
    expect(sceneButtons[0]!.attributes('aria-pressed')).toBe('false')
    expect(sceneButtons[1]!.attributes('aria-pressed')).toBe('true')
    expect(defaultWrapper.text()).toContain('已出院且有已完成质控结果的病历')
    defaultWrapper.unmount()

    // 显式传 ?scene=running 严格尊重 URL
    state.getRecordQualityReport.mockClear()
    state.route.query = { scene: 'running' }
    const runningWrapper = mountRecordQuality()
    await flushPromises()

    expect(state.getRecordQualityReport).toHaveBeenCalledWith(
      expect.objectContaining({ scene: 'running', defect_source: 'all' }),
      expect.any(AbortSignal),
    )
    const runningSceneButtons = runningWrapper.findAll(
      '[aria-labelledby="report-scene-label"] button',
    )
    expect(runningSceneButtons[0]!.attributes('aria-pressed')).toBe('true')
    expect(runningSceneButtons[1]!.attributes('aria-pressed')).toBe('false')
    runningWrapper.unmount()
  })

  it('限制 1366/1440 下「质控类型」下拉框及筛选项最大宽度，防止孤立下拉框铺满整行', async () => {
    state.route.path = '/workstation-v5/reports/record-quality'
    const wrapper = mountRecordQuality()
    await flushPromises()

    const sourceField = wrapper.get('#report-source').element.closest('.field')
    expect(sourceField?.classList.contains('field--select')).toBe(true)
    wrapper.unmount()

    const css = readFileSync(
      resolve(__dirname, '../../src/views/qc/reports/reportPage.css'),
      'utf8',
    )
    expect(css).toMatch(/\.field\s*\{[^}]*max-width:\s*240px;/)
    expect(css).toMatch(/\.field--select\s*\{[^}]*max-width:\s*220px;[^}]*flex:\s*0\s+1\s+180px;/)
    expect(css).toMatch(/\.field--datetime\s*\{[^}]*max-width:\s*240px;/)
    expect(css).toMatch(/@media\s*\(max-width:\s*480px\)\s*\{[\s\S]*?\.field--select[\s\S]*?max-width:\s*none;/)
  })

  it('科室下钻抽屉支持按 Escape 键关闭并中止在途请求，组件卸载后清理监听', async () => {
    state.route.path = '/workstation-v5/reports/record-quality'
    let capturedSignal: AbortSignal | undefined
    state.getRecordQualityRecords.mockImplementationOnce((_filters, signal: AbortSignal) => {
      capturedSignal = signal
      return new Promise(() => {
        /* 保持在途状态以验证按 Escape 后中止 */
      })
    })

    const removeListenerSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mountRecordQuality()
    await flushPromises()

    // 点击科室明细打开下钻抽屉
    const deptButton = wrapper
      .findAll('button.link')
      .find((btn) => btn.text().trim() === '重症医学科（ICU）')
    expect(deptButton).toBeTruthy()
    await deptButton!.trigger('click')
    await nextTick()

    const drawer = wrapper.find('[data-testid="drilldown-drawer"]')
    expect(drawer.exists()).toBe(true)
    expect(drawer.attributes('data-keyboard')).toBe('true')
    expect(capturedSignal?.aborted).toBe(false)

    // 按 Escape 关闭抽屉并中止在途请求
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
    await nextTick()
    expect(wrapper.find('[data-testid="drilldown-drawer"]').exists()).toBe(false)
    expect(capturedSignal?.aborted).toBe(true)

    wrapper.unmount()
    expect(removeListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function))
  })
})
