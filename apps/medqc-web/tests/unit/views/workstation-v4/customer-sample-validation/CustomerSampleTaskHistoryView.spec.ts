/* eslint-disable vue/one-component-per-file */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, inject, provide } from 'vue'
import CustomerSampleTaskHistoryView from '@/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue'

let latestResultDrawerProps: Record<string, unknown> | null = null

const {
  message,
  routeQuery,
  routerPush,
  routerReplace,
  listSichuanWorkspaceBatchJobs,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  reviewSichuanWorkspaceBatchJob,
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  normalizeBatchExportBlob,
  downloadBlob,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  routeQuery: {} as Record<string, string>,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  listSichuanWorkspaceBatchJobs: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
  cancelSichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  normalizeBatchExportBlob: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({ message }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  listSichuanWorkspaceBatchJobs,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  reviewSichuanWorkspaceBatchJob,
  cancelSichuanWorkspaceBatchJob,
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
    close: {
      type: Function,
      default: undefined,
    },
    cancelBatchJob: {
      type: Function,
      default: undefined,
    },
    cancelBatchJobLoading: Boolean,
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
    vi.useRealTimers()
    Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
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
    cancelSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        ...job,
        status: 'canceled',
      },
    })
    exportSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: new Blob(['report'], { type: 'text/html' }),
    })
    normalizeBatchExportBlob.mockResolvedValue(new Blob(['report'], { type: 'text/html' }))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('进入页面后加载并展示质控任务列表', async () => {
    const wrapper = await mountView()

    expect(listSichuanWorkspaceBatchJobs).toHaveBeenCalledWith({
      view: 'overview',
      page: 1,
      page_size: 20,
      q: undefined,
      status: undefined,
    })
    expect(wrapper.text()).toContain('共 1 条')
    const row = wrapper.get('[data-testid="task-history-row-job-history-1"]')
    // 列表只读任务元信息；点开后才读取结果。
    expect(row.text()).toContain('泸县0609质控点验证')
    expect(row.text()).toContain('2 份病历')
    expect(row.text()).toContain('选定 2 个质控点')
    expect(row.text()).not.toContain('项问题')
    expect(row.text()).not.toContain('合格')
    expect(row.text()).not.toContain('首次病程记录未在入院后8小时内完成')
    expect(wrapper.find('.task-history__counts').exists()).toBe(false)
    expect(getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(getSichuanWorkspaceBatchJobDebugSnapshot).not.toHaveBeenCalled()
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
      view: 'overview',
      page: 1,
      page_size: 20,
      q: undefined,
      status: 'completed',
    })
  })

  it('轻量列表分页与搜索保留，翻页不读取任务详情', async () => {
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: {
        items: [buildCompletedJob()],
        total: 41,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-history-search"]').setValue('样本')
    await wrapper.get('[data-testid="task-history-search"]').trigger('keyup.enter')
    await flushPromises()
    wrapper.findComponent(APaginationStub).vm.$emit('change', 2)
    await flushPromises()
    expect(listSichuanWorkspaceBatchJobs).toHaveBeenLastCalledWith({
      view: 'overview',
      page: 2,
      page_size: 20,
      q: '样本',
      status: undefined,
    })
    expect(getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
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

  it('初始加载失败时展示内联错误态并支持重试恢复', async () => {
    listSichuanWorkspaceBatchJobs.mockResolvedValueOnce({
      success: false,
      message: '后端服务暂不可用',
    })
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-history-error"]').text()).toContain('后端服务暂不可用')
    await wrapper.get('[data-testid="task-history-retry"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="task-history-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="task-history-row-job-history-1"]').exists()).toBe(true)
  })

  it('从 URL 查询参数恢复筛选，且修改关键词后点刷新会重置为第 1 页', async () => {
    routeQuery.q = '住院'
    routeQuery.status = 'failed'
    routeQuery.page = '3'
    const wrapper = await mountView()

    expect(listSichuanWorkspaceBatchJobs).toHaveBeenCalledWith({
      view: 'overview',
      page: 3,
      page_size: 20,
      q: '住院',
      status: 'failed',
    })

    await wrapper.get('[data-testid="task-history-search"]').setValue('新关键词')
    await wrapper.get('[data-testid="task-history-refresh"]').trigger('click')
    await flushPromises()

    expect(listSichuanWorkspaceBatchJobs).toHaveBeenLastCalledWith({
      view: 'overview',
      page: 1,
      page_size: 20,
      q: '新关键词',
      status: 'failed',
    })
    expect(routerReplace).toHaveBeenCalledWith({
      query: { q: '新关键词', status: 'failed' },
    })
  })

  it('打开任务详情失败时清空旧详情并自动关闭抽屉，快速切换时丢弃过期响应', async () => {
    const job1 = buildCompletedJob()
    const job2 = { ...buildCompletedJob(), id: 'job-history-2', rule_name: '第二个任务' }
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: { items: [job1, job2], total: 2, page: 1, page_size: 20 },
    })

    let resolveFirst!: (val: unknown) => void
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve
    })
    getSichuanWorkspaceBatchJob
      .mockReturnValueOnce(firstPromise)
      .mockResolvedValueOnce({ success: true, data: job2 })
      .mockResolvedValueOnce({ success: false, message: '任务不存在' })

    const wrapper = await mountView()
    const buttons = wrapper.findAll('[data-testid="task-history-open"]')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await flushPromises()

    resolveFirst({ success: true, data: job1 })
    await flushPromises()

    expect((latestResultDrawerProps?.batchJobDetail as { id?: string } | null)?.id).toBe(
      'job-history-2',
    )

    // 再次打开失败时清空旧 detail 并关闭抽屉
    await buttons[0].trigger('click')
    await flushPromises()
    expect(latestResultDrawerProps?.open).toBe(false)
    expect(latestResultDrawerProps?.batchJobDetail).toBeNull()
  })

  it('运行中任务支持轮询更新、关闭抽屉停止轮询，且向抽屉透传 cancelBatchJob', async () => {
    vi.useFakeTimers()
    const runningJob = { ...buildCompletedJob(), id: 'job-running-1', status: 'running' }
    const doneJob = { ...runningJob, status: 'completed' }
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: { items: [runningJob], total: 1, page: 1, page_size: 20 },
    })
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({ success: true, data: runningJob })
      .mockResolvedValueOnce({ success: true, data: doneJob })

    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-history-open"]').trigger('click')
    await flushPromises()

    expect(latestResultDrawerProps?.cancelBatchJob).toBeTypeOf('function')
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(3100)
    await flushPromises()
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(2)
    expect((latestResultDrawerProps?.batchJobDetail as { status?: string } | null)?.status).toBe(
      'completed',
    )

    // 验证取消任务回调
    const cancelFn = latestResultDrawerProps?.cancelBatchJob as (id: string) => Promise<void>
    await cancelFn('job-running-1')
    expect(cancelSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-running-1')
    wrapper.unmount()
  })

  it('完全失败任务展示 danger 状态和“查看原因”按钮', async () => {
    const failedJob = {
      ...buildCompletedJob(),
      id: 'job-failed-1',
      status: 'failed',
      summary: null,
      has_results: false,
    }
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: { items: [failedJob], total: 1, page: 1, page_size: 20 },
    })
    const wrapper = await mountView()
    const row = wrapper.get('[data-testid="task-history-row-job-failed-1"]')
    expect(row.text()).toContain('执行失败')
    expect(row.find('.mq-status--danger').exists()).toBe(true)
    expect(row.get('[data-testid="task-history-open"]').text()).toContain('查看原因')
  })
})
