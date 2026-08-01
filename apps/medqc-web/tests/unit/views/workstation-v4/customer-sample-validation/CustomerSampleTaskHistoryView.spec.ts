/* eslint-disable vue/one-component-per-file */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import CustomerSampleTaskHistoryView from '@/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue'

let latestResultDrawerProps: Record<string, unknown> | null = null

const {
  message,
  routerPush,
  listSichuanWorkspaceBatchJobs,
  getSichuanWorkspaceBatchJob,
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
      selected_rule_ids: ['LX0609-002', 'LX0609-016'],
    },
    summary: {
      total_records: 2,
      display_status_counts: {
        non_compliant: 1,
        compliant: 1,
      },
      history_issue_summaries: [
        {
          rule_id: 'LX0609-002',
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
    expect(wrapper.text()).toContain('共 1 条任务')
    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('2 份病历')
    expect(wrapper.text()).toContain('发现需关注结果：不合规 1')
    expect(wrapper.text()).toContain('LX0609-002 首次病程记录未在入院后8小时内完成')
    expect(wrapper.text()).toContain('合规 1')
  })

  it('从历史任务打开单一结果抽屉', async () => {
    const wrapper = await mountView()
    const viewButton = wrapper
      .findAll('.customer-task-history-actions button')
      .find((button) => button.text().includes('查看结果'))

    expect(viewButton).toBeTruthy()
    await viewButton!.trigger('click')
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-history-1')
    expect(latestResultDrawerProps?.open).toBe(true)
    expect((latestResultDrawerProps?.batchJobDetail as { id?: string } | null)?.id).toBe(
      'job-history-1',
    )
  })

  it('已完成任务提供复核与HTML导出入口', async () => {
    const wrapper = await mountView()
    const actionButtons = wrapper.findAll('.customer-task-history-actions button')
    const reviewButton = actionButtons.find((button) => button.text().includes('复核'))
    const exportButton = actionButtons.find((button) => button.text().includes('导出HTML'))

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
