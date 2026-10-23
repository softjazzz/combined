/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, inject, provide } from 'vue'
import CustomerSampleTaskHistoryView from '@/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue'

let latestResultDrawerProps: Record<string, unknown> | null = null

const {
  message,
  routerPush,
  listSichuanWorkspaceBatchJobs,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  reviewSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  normalizeBatchExportBlob,
  downloadBlob,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  routerPush: vi.fn(),
  listSichuanWorkspaceBatchJobs: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  normalizeBatchExportBlob: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({ message }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  listSichuanWorkspaceBatchJobs,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  reviewSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
}))

vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  normalizeBatchExportBlob,
  downloadBlob,
}))

const AButtonStub = defineComponent({
  name: 'AButtonStub',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.())
  },
})

// 菜单桩：a-menu 通过 provide 把点击回调交给菜单项，菜单项按 data-menu-key 触发对应 key。
const AMenuStub = defineComponent({
  name: 'AMenuStub',
  emits: ['click'],
  setup(_, { emit, slots }) {
    provide('menuStubClick', (key: string) => emit('click', { key }))
    return () => h('div', { class: 'a-menu-stub' }, slots.default?.())
  },
})

const AMenuItemStub = defineComponent({
  name: 'AMenuItemStub',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const click = inject<(key: string) => void>('menuStubClick', () => undefined)
    return () =>
      h(
        'button',
        { class: 'a-menu-item-stub', onClick: () => click(String(attrs['data-menu-key'] || '')) },
        slots.default?.(),
      )
  },
})

const ADropdownStub = defineComponent({
  name: 'ADropdownStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-dropdown-stub' }, [slots.default?.(), slots.overlay?.()])
  },
})

const APaginationStub = defineComponent({
  name: 'APaginationStub',
  props: { current: Number, total: Number, pageSize: Number },
  emits: ['change'],
  setup(props) {
    return () => h('div', { class: 'a-pagination-stub' }, `${props.current}/${props.total}`)
  },
})

const ASpinStub = defineComponent({
  name: 'ASpinStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-spin-stub' }, slots.default?.())
  },
})

const SemanticRulesBatchResultDrawerStub = defineComponent({
  name: 'SemanticRulesBatchResultDrawerStub',
  props: {
    open: Boolean,
    batchJobDetail: {
      type: Object,
      default: null,
    },
    batchJobDebugSnapshot: {
      type: Object,
      default: null,
    },
    batchJobDebugLoading: Boolean,
    fetchBatchJobDebugSnapshot: {
      type: Function,
      default: undefined,
    },
  },
  setup(props) {
    latestResultDrawerProps = props as unknown as Record<string, unknown>
    return () =>
      h('div', {
        class: 'batch-result-drawer-stub',
        'data-open': props.open ? 'true' : 'false',
      })
  },
})

function buildCompletedJob() {
  return {
    id: 'job-history-1',
    rule_code: 'LX0609',
    rule_name: '泸县0609质控点验证',
    status: 'completed',
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_name: '泸县0609质控点验证 v1',
    customer_rule_count: 2,
    execution_rule_count: 2,
    record_ids: ['208790', '359787'],
    created_at: '2026-07-31T08:30:00Z',
    filters: {
      selected_rule_ids: ['LX0609-01-02-01', 'LX0609-12-01-01'],
    },
    summary: {
      total_records: 2,
      display_status_counts: {
        non_compliant: 1,
        compliant: 1,
      },
      history_issue_summaries: [
        {
          rule_id: 'LX0609-01-02-01',
          text: '首次病程记录未在入院后8小时内完成',
        },
      ],
    },
  }
}

async function mountView() {
  const wrapper = mount(CustomerSampleTaskHistoryView, {
    global: {
      stubs: {
        AButton: AButtonStub,
        ASpin: ASpinStub,
        SemanticRulesBatchResultDrawer: SemanticRulesBatchResultDrawerStub,
        'a-button': AButtonStub,
        'a-spin': ASpinStub,
        'a-dropdown': ADropdownStub,
        'a-menu': AMenuStub,
        'a-menu-item': AMenuItemStub,
        'a-pagination': APaginationStub,
        'semantic-rules-batch-result-drawer': SemanticRulesBatchResultDrawerStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('CustomerSampleTaskHistoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    latestResultDrawerProps = null
    const job = buildCompletedJob()
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: {
        items: [job],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    getSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: job })
    getSichuanWorkspaceBatchJobDebugSnapshot.mockResolvedValue({
      success: true,
      data: {
        job_id: 'job-history-1',
        status: 'completed',
        scope: 'running',
        execution_mode: 'native',
        rules: [],
        recent_items: [],
        recent_failed_records: [],
      },
    })
    reviewSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        job: {
          ...job,
          summary: {
            ...job.summary,
            review_report: { summary: { total_findings: 1 } },
          },
        },
        review_report: { summary: { total_findings: 1 } },
      },
    })
    exportSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: new Blob(['report'], { type: 'text/html' }),
    })
    normalizeBatchExportBlob.mockResolvedValue(new Blob(['report'], { type: 'text/html' }))
  })

  it('进入页面后加载并展示质控任务列表', async () => {
    const wrapper = await mountView()

    expect(listSichuanWorkspaceBatchJobs).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      q: undefined,
      status: undefined,
    })
    expect(wrapper.text()).toContain('共 1 条')
    const row = wrapper.get('[data-testid="task-history-row-job-history-1"]')
    // 2026-10-23 客户视图：任务名为主标题，范围一句话，结果按问题/需补资料/合格计数。
    expect(row.text()).toContain('泸县0609质控点验证')
    expect(row.text()).toContain('2 份病历')
    expect(row.text()).toContain('选定 2 个质控点')
    expect(row.text()).toContain('1 项问题')
    expect(row.text()).toContain('1 合格')
    expect(row.text()).not.toContain('LX0609-01-02-01')
    expect(row.text()).not.toContain('不合规')
    // 只有 1 页时不显示分页。
    expect(wrapper.find('.a-pagination-stub').exists()).toBe(false)
  })

  it('状态切换即按状态重新查询，从第 1 页开始', async () => {
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-history-status-completed"]').trigger('click')
    await flushPromises()
    expect(listSichuanWorkspaceBatchJobs).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      q: undefined,
      status: 'completed',
    })
  })

  it('从历史任务打开单一结果抽屉', async () => {
    const wrapper = await mountView()
    const viewButton = wrapper.get('[data-testid="task-history-open"]')
    expect(viewButton.text()).toContain('查看结果')
    await viewButton.trigger('click')
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-history-1')
    expect(getSichuanWorkspaceBatchJobDebugSnapshot).toHaveBeenCalledWith('job-history-1', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(latestResultDrawerProps?.open).toBe(true)
    expect((latestResultDrawerProps?.batchJobDetail as { id?: string } | null)?.id).toBe(
      'job-history-1',
    )
    expect(latestResultDrawerProps?.batchJobDebugSnapshot).toMatchObject({
      job_id: 'job-history-1',
      execution_mode: 'native',
    })
    expect(latestResultDrawerProps?.fetchBatchJobDebugSnapshot).toBeTypeOf('function')
  })

  it('已完成任务在“更多”中提供复核与导出质控报告', async () => {
    const wrapper = await mountView()
    const menuItems = wrapper.findAll('.a-menu-item-stub')
    const reviewButton = menuItems.find((button) => button.text().includes('复核本次结果'))
    const exportButton = menuItems.find((button) => button.text().includes('导出质控报告'))

    expect(reviewButton).toBeTruthy()
    expect(exportButton).toBeTruthy()

    await reviewButton!.trigger('click')
    await flushPromises()
    expect(reviewSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-history-1')
    expect(message.success).toHaveBeenCalledWith('复核完成，发现 1 条复核建议')

    await exportButton!.trigger('click')
    await flushPromises()
    expect(exportSichuanWorkspaceBatchJob).toHaveBeenCalledWith({
      job_id: 'job-history-1',
      format: 'html',
    })
    expect(normalizeBatchExportBlob).toHaveBeenCalledWith(expect.any(Blob), 'html')
    expect(downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob),
      'manual-sample-validation-job-history-1.html',
    )
    expect(message.success).toHaveBeenCalledWith('HTML 质控明细已开始下载')
  })
})
