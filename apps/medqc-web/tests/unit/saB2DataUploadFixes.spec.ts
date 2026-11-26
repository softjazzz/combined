import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const hoisted = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(() => vi.fn()),
  },
  echartsSetOptionCalls: [] as Array<{ option: any; notMerge?: boolean }>,
  echartsInitCount: 0,
}))

vi.mock('ant-design-vue', () => ({
  message: hoisted.message,
  Modal: { confirm: vi.fn() },
}))

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: () => 'test-token',
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => {
    hoisted.echartsInitCount += 1
    return {
      setOption: vi.fn((option: any, notMerge?: boolean) => {
        hoisted.echartsSetOptionCalls.push({ option, notMerge })
      }),
      on: vi.fn(),
      dispose: vi.fn(),
      getDom: vi.fn(() => document.createElement('div')),
    }
  }),
}))

const mockAuthState = reactive({
  isAuthenticated: true,
  user: { id: 'actor-1', is_demo_account: false },
  userRoles: ['super_admin'] as string[],
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthState,
}))

vi.mock('@/api/clinicalSources', () => ({
  clinicalSourcesApi: {
    options: vi.fn().mockResolvedValue({
      default_source: 'legacy_pg',
      sources: [{ id: 'legacy_pg', enabled: true, name: '传统库' }],
    }),
  },
}))

import FieldMappingStep from '@/views/workstation-v4/frontpage/components/FieldMappingStep.vue'
import PostEventAnalysisView from '@/views/workstation-v4/frontpage/components/PostEventAnalysisView.vue'
import WorkstationV2View from '@/views/workstation-v4/WorkstationV2View.vue'
import ExcelUploadView from '@/views/workstation-v4/frontpage/components/ExcelUploadView.vue'
import CDMDataView from '@/views/workstation-v4/CDMDataView.vue'

const Slot = defineComponent({
  setup: (_, { slots }) => () => h('div', slots.default?.()),
})

const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  setup: (props, { slots, attrs }) => () =>
    h('button', { type: 'button', ...attrs, disabled: props.disabled }, slots.default?.()),
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(fetch).mockReset()
  hoisted.echartsSetOptionCalls.length = 0
  hoisted.echartsInitCount = 0
  window.sessionStorage.clear()
})

afterEach(() => {
  window.sessionStorage.clear()
})

describe('SA-B2 Smart Upload & Data Management Fixes', () => {
  it('FieldMappingStep 展示 mappedCount / props.columns.length 已映射而非 localMappings 键数', async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/mapping-status/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            ready: true,
            mappings: { 科室: 'department_name', 总费用: 'actual_cost' },
            confidence: 0.92,
          }),
        } as Response
      }
      if (url.includes('/mapping/fields')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            fields: {
              department_name: { name: '科室名称', description: '', required: true, category: 'base', aliases: [] },
              actual_cost: { name: '总费用', description: '', required: true, category: 'cost', aliases: [] },
            },
          }),
        } as Response
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(FieldMappingStep, {
      props: {
        fileId: 'f1234567',
        fileName: 'his.csv',
        rowCount: 25,
        columns: ['科室', '总费用', '住院号', '医生', '备注'],
        sampleData: [{ 科室: '内科', 总费用: '1000', 住院号: 'H001', 医生: '张医生', 备注: '' }],
      },
      global: {
        stubs: {
          'a-progress': true,
          'a-tag': Slot,
          'a-spin': true,
          'a-select': Slot,
          'a-select-option': true,
          'a-alert': true,
          'a-button': ButtonStub,
        },
      },
    })

    await flushPromises()
    expect(wrapper.get('[data-testid="mapped-count"]').text()).toBe('2 / 5 已映射')
    wrapper.unmount()
  })

  it('WorkstationV2View 将 uploadedAnalysis 作为 prop 透传给 PostEventAnalysisView', async () => {
    const PostStub = defineComponent({
      props: { uploadedAnalysis: { type: Object, default: null } },
      template:
        '<div data-testid="post-prop-probe">{{ uploadedAnalysis?.aiInsights?.join(",") || "none" }}|{{ Object.keys(uploadedAnalysis?.charts || {}).join(",") }}</div>',
    })

    const wrapper = mount(WorkstationV2View, {
      props: { embedded: true, initialView: 'upload' },
      global: {
        stubs: {
          ExcelUploadView: {
            emits: ['analysis-ready'],
            template:
              '<button data-testid="trigger-ready" @click="$emit(\'analysis-ready\', { charts: { profit_waterfall: { title: { text: \'瀑布\' } } }, aiInsights: [\'智能上传结论A\'], analysisResults: { overview: { total_cases: 18 } } })">ok</button>',
          },
          PostEventAnalysisView: PostStub,
          CodingOptimizationDrawer: true,
          QCAlertPanel: true,
          'a-button': ButtonStub,
        },
      },
    })

    await wrapper.get('[data-testid="trigger-ready"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="post-prop-probe"]').text()).toBe(
      '智能上传结论A|profit_waterfall',
    )
    wrapper.unmount()
  })

  it('PostEventAnalysisView 渲染 uploadedAnalysis prop 的真实图表与摘要，并支持 sessionStorage 回退读取', async () => {
    const uploadedPayload = {
      charts: {
        profit_waterfall: {
          title: { text: '上传批次收支瀑布' },
          xAxis: { type: 'category', data: ['DIP支付', '总成本', '盈亏'] },
          yAxis: { type: 'value' },
          series: [{ type: 'bar', data: [12, -10, 2] }],
        },
        dept_cost_ranking: {
          title: { text: '科室费用排名' },
          xAxis: { type: 'category', data: ['心内科'] },
          yAxis: { type: 'value' },
          series: [{ type: 'bar', data: [8500] }],
        },
      },
      aiInsights: ['本批次共 28 例病例，总体盈亏率 14.5%'],
      analysisResults: {
        overview: {
          total_cases: 28,
          disease_count: 6,
          total_cost: 280000,
          total_payment: 320000,
          total_profit_loss: 40000,
          cmi: 1.42,
          avg_los: 5.5,
          avg_cost_per_case: 10000,
        },
        department: [
          { department: '心内科', 病例数: 28, 总费用: 280000, 总支付标准: 320000, 盈亏: 40000 },
        ],
      },
    }

    const commonStubs = {
      MqIcon: true,
      DatasetUploadPanel: true,
      OverCostAnalysisCard: true,
      DrillDownModal: true,
      'a-dropdown': Slot,
      'a-menu': Slot,
      'a-menu-item': Slot,
      'a-button': ButtonStub,
      'a-radio-group': Slot,
      'a-radio-button': Slot,
      'a-range-picker': true,
      'a-select': Slot,
      'a-select-option': true,
      'a-tag': Slot,
    }

    // 1. Direct prop rendering
    const propWrapper = mount(PostEventAnalysisView, {
      props: { uploadedAnalysis: uploadedPayload },
      global: { stubs: commonStubs },
    })
    await flushPromises()

    expect(propWrapper.get('[data-testid="post-analysis-mode-chip"]').text()).toContain(
      '当前使用智能上传分析结果（28 例 · 2 个图表）',
    )
    expect(propWrapper.text()).toContain('本批次共 28 例病例，总体盈亏率 14.5%')
    expect(propWrapper.text()).toContain('上传批次收支瀑布')
    expect(propWrapper.text()).toContain('科室费用排名')
    expect(propWrapper.text()).not.toContain('32,021')
    expect(propWrapper.findAll('[data-testid="uploaded-chart-card"]')).toHaveLength(2)
    expect(
      hoisted.echartsSetOptionCalls.some(
        (call) => call.option?.title?.text === '上传批次收支瀑布',
      ),
    ).toBe(true)
    propWrapper.unmount()

    // 2. Fallback read from sessionStorage['medqc:smart-upload-analysis-ready']
    hoisted.echartsSetOptionCalls.length = 0
    window.sessionStorage.setItem(
      'medqc:smart-upload-analysis-ready',
      JSON.stringify(uploadedPayload),
    )
    const storageWrapper = mount(PostEventAnalysisView, {
      global: { stubs: commonStubs },
    })
    await flushPromises()

    expect(storageWrapper.get('[data-testid="post-analysis-mode-chip"]').text()).toContain(
      '当前使用智能上传分析结果（28 例 · 2 个图表）',
    )
    expect(storageWrapper.text()).toContain('本批次共 28 例病例，总体盈亏率 14.5%')
    expect(storageWrapper.findAll('[data-testid="uploaded-chart-card"]')).toHaveLength(2)
    storageWrapper.unmount()
  })

  it('ExcelUploadView 历史批次刷新拉取 batch-tasks 回填 currentSessionId 并支持点击进入分析', async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/batch-tasks')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            success: true,
            data: [
              {
                task_id: 't-1',
                filename: 'april_drg.xlsx',
                status: 'succeeded',
                session_id: 'sess-888',
                batch_id: 'batch_20260401_001',
                total_records: 36,
                created_at: '2026-04-01T08:00:00Z',
                result_summary: { total_cost: 128000 },
              },
            ],
          }),
        } as Response
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(ExcelUploadView, {
      global: { stubs: { MqIcon: true, FieldMappingStep: true } },
    })

    await wrapper.get('[data-testid="refresh-batches-btn"]').trigger('click')
    await flushPromises()

    const items = wrapper.findAll('[data-testid="upload-history-item"]')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toContain('april_drg.xlsx')
    expect(items[0].text()).toContain('36 条')
    expect(window.sessionStorage.getItem('medqc:drg-upload-session-id')).toBe('sess-888')

    await items[0].trigger('click')
    expect(wrapper.emitted('go-analysis')).toEqual([['sess-888', 'batch_20260401_001']])
    wrapper.unmount()
  })

  it('CDMDataView openRecordModal 兼容服务端三坐标过滤与数字/字符串类型差异', async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/stats')) return { ok: true, status: 200, json: async () => ({ total_records: 1 }) } as Response
      if (url.endsWith('/list')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ institute_id: 'H1', patient_id: 1001, visit_id: 2001, name: '王测试', mr_no: 'MR99' }],
          }),
        } as Response
      }
      if (url.endsWith('/departments')) return { ok: true, status: 200, json: async () => ['内科'] } as Response
      if (url.endsWith('/schema')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            total_tables: 1,
            tables: [{ name: 'mr', label: '病案首页', column_count: 1, columns: [{ name: 'mr_no', type: 'text' }] }],
          }),
        } as Response
      }
      if (url.includes('/frontpage/')) {
        return { ok: true, status: 200, json: async () => ({ name: '王测试', diagnoses: [] }) } as Response
      }
      if (url.includes('/table-data/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            columns: ['institute_id', 'patient_id', 'visit_id', 'mr_no'],
            items: [{ institute_id: 'H1', patient_id: '1001', visit_id: '2001', mr_no: 'MR99' }],
            total: 1,
            page: 1,
            page_size: 100,
          }),
        } as Response
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(CDMDataView, {
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-alert': true,
          'a-tag': Slot,
          'a-modal': { props: ['open'], template: '<div v-if="open" data-testid="record-modal"><slot /></div>' },
          'a-spin': true,
          'a-badge': true,
          'a-tabs': Slot,
          'a-tab-pane': { props: ['tab'], template: '<div data-testid="modal-tab">{{ tab }}<slot /></div>' },
        },
      },
    })

    await flushPromises()
    await wrapper.get('[data-testid="pt-table-data-btn"]').trigger('click')
    await flushPromises()

    const modalText = wrapper.get('[data-testid="record-modal"]').text()
    expect(modalText).toContain('病案首页 (1)')
    expect(modalText).toContain('MR99')
    wrapper.unmount()
  })
})
