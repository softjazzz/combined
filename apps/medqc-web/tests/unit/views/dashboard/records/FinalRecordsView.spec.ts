import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createBatch: vi.fn(),
  retryBatch: vi.fn(),
  exportDefects: vi.fn(),
  getFinalRecordList: vi.fn(),
  getAdminOverview: vi.fn(),
  getDepartmentList: vi.fn(),
  routerPush: vi.fn(),
  fetchBatchJobDetail: vi.fn(),
  jobs: [] as Array<{ id: string; items?: Array<{ record_id: string }> }>,
  message: { warning: vi.fn(), error: vi.fn(), success: vi.fn(), loading: vi.fn() },
}))

vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: mocks.routerPush }),
}))
vi.mock('@/api/qcAdmin', () => ({
  getFinalRecordList: mocks.getFinalRecordList,
  getAdminOverview: mocks.getAdminOverview,
  getDepartmentList: mocks.getDepartmentList,
  exportDefects: mocks.exportDefects,
}))
vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  createSichuanWorkspaceBatchJob: mocks.createBatch,
}))
vi.mock('@/views/workstation-v4/semantic-rules/composables/useSichuanBatchJobs', async () => {
  const { ref, reactive } = await import('vue')
  return {
    useSichuanBatchJobs: () => ({
      batchJobLoading: ref(false),
      batchJobDetailLoading: ref(false),
      batchJobDebugLoading: ref(false),
      cancellingBatchJobId: ref(''),
      retryingBatchJobId: ref(''),
      batchJobs: ref(mocks.jobs),
      batchJobDetail: ref(null),
      batchJobDebugSnapshot: ref(null),
      batchJobPagination: reactive({ current: 1, pageSize: 20, total: 0 }),
      batchJobQuery: reactive({ scope: 'final', keyword: '', status: undefined }),
      batchJobStatusOptions: [],
      loadBatchJobs: vi.fn(),
      handleBatchJobTableChange: vi.fn(),
      searchBatchJobs: vi.fn(),
      stopBatchJobPolling: vi.fn(),
      startBatchJobPolling: vi.fn(),
      fetchBatchJobDetail: mocks.fetchBatchJobDetail,
      fetchBatchJobDebugSnapshot: vi.fn(),
      executeCancelBatchJob: vi.fn(),
      executeRetryBatchJob: mocks.retryBatch,
      exportBatchJobReport: vi.fn(),
      prependBatchJob: vi.fn(),
    }),
  }
})

import FinalRecordsView from '@/views/dashboard/records/FinalRecordsView.vue'

type FinalVm = {
  openBatchLaunchModal: () => Promise<void>
  confirmBatchLaunch: () => Promise<void>
  retryFinalBatchJob: (jobId: string) => void
  handleExport: () => Promise<void>
  openCustomQCExperience: (record?: { record_id: string }) => void
  handleQCReport: (record: { record_id: string }) => void
}

describe('旧已出院病历页终末范围守卫', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getFinalRecordList.mockResolvedValue({ success: true, data: { items: [], total: 0 } })
    mocks.getAdminOverview.mockResolvedValue({ success: true, data: {} })
    mocks.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    mocks.jobs = []
  })

  it('禁用创建与全场景导出入口，直接调用也不会写入或导出', async () => {
    const wrapper = shallowMount(FinalRecordsView, {
      global: {
        stubs: {
          'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
          ProQueryBar: { template: '<div><slot name="filters" /><slot name="actions" /></div>' },
          ProTableToolbar: { template: '<div><slot /></div>' },
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('已出院病历（归档未核验）')
    expect(wrapper.text()).toContain('归档字段暂无权威口径')
    expect(wrapper.text()).toContain('待处理范围未定义')
    expect(wrapper.text()).not.toContain('已完成质控闭环')
    const batchPanel = wrapper.findComponent({ name: 'SemanticRulesBatchPanel' })
    expect(batchPanel.props('allowLaunch')).toBe(false)
    expect(batchPanel.props('allowRetry')).toBe(false)
    const buttons = wrapper.findAll('button')
    expect(buttons.filter((button) => button.text().includes('发起批量质控'))).toHaveLength(2)
    expect(buttons.filter((button) => button.text().includes('发起批量质控')).every((button) => button.attributes('disabled') !== undefined)).toBe(true)
    const exportButton = buttons.find((button) => button.text().includes('导出'))
    expect(exportButton?.attributes('disabled')).toBeDefined()

    const vm = wrapper.vm as unknown as FinalVm
    await vm.openBatchLaunchModal()
    await vm.confirmBatchLaunch()
    vm.retryFinalBatchJob('historical-job')
    await vm.handleExport()
    expect(mocks.createBatch).not.toHaveBeenCalled()
    expect(mocks.retryBatch).not.toHaveBeenCalled()
    expect(mocks.exportDefects).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledTimes(4)
  })

  it('自定义质控不可跳转；逐病例报告无权威明细时不打开任何批次', async () => {
    mocks.jobs = [{ id: 'other-job', items: [{ record_id: 'other-record' }] }]
    const wrapper = shallowMount(FinalRecordsView, {
      global: {
        stubs: {
          'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
          ProQueryBar: { template: '<div><slot name="filters" /><slot name="actions" /></div>' },
          ProTableToolbar: { template: '<div><slot /></div>' },
        },
      },
    })
    await flushPromises()
    const customButton = wrapper.findAll('button').find((button) => button.text() === '自定义质控点')
    expect(customButton?.attributes('disabled')).toBeDefined()

    const vm = wrapper.vm as unknown as FinalVm
    vm.openCustomQCExperience({ record_id: 'current-record' })
    vm.handleQCReport({ record_id: 'current-record' })
    expect(mocks.routerPush).not.toHaveBeenCalled()
    expect(mocks.fetchBatchJobDetail).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith(
      '当前无法按病例匹配报告，请在下方历史任务列表查看',
    )

    vm.handleQCReport({ record_id: 'other-record' })
    await flushPromises()
    expect(mocks.fetchBatchJobDetail).not.toHaveBeenCalled()
  })
})
