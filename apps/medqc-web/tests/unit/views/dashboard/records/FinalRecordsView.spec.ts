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
import type { AdminRecordItem } from '@/api/qcAdmin'

type FinalVm = {
  openBatchLaunchModal: () => Promise<void>
  confirmBatchLaunch: () => Promise<void>
  retryFinalBatchJob: (jobId: string) => void
  handleExport: () => Promise<void>
  openCustomQCExperience: (record?: { record_id: string }) => void
  handleQCReport: (record: { record_id: string }) => void
  jumpToWorkstation: (record: AdminRecordItem, action: string) => void
  handleView: (record: AdminRecordItem) => void
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

  it('两院同就诊号不能从旧终末页单键进入工作台或详情', async () => {
    const sameVisitRows = ['hospital-a', 'hospital-b'].map((hospitalId, index) => ({
      id: `${hospitalId}-row`,
      task_id: '',
      record_id: 'same-visit-id',
      visit_id: 'same-visit-id',
      hospital_id: hospitalId,
      patient_name: `患者${index + 1}`,
      status: 'pending',
      defect_count: 0,
      created_at: '2026-09-25T00:00:00Z',
    }))
    mocks.getFinalRecordList.mockResolvedValue({
      success: true,
      data: { items: sameVisitRows, total: sameVisitRows.length },
    })
    const wrapper = shallowMount(FinalRecordsView, {
      global: {
        stubs: {
          'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
          'a-tooltip': { props: ['title'], template: '<div :data-tooltip="title"><slot /></div>' },
          ProQueryBar: { template: '<div><slot name="filters" /><slot name="actions" /></div>' },
          ProTableToolbar: { template: '<div><slot /></div>' },
          ProStandardTable: {
            props: ['dataSource'],
            template: '<div><div v-for="row in dataSource" :key="row.id"><div data-cell="record-number"><slot name="bodyCell" :column="{ key: \'recordNumber\' }" :record="row" /></div><slot name="bodyCell" :column="{ key: \'stageActions\' }" :record="row" /><slot name="bodyCell" :column="{ key: \'action\' }" :record="row" /></div></div>',
          },
        },
      },
    })
    await flushPromises()

    const stageLabels = ['进入工作台', '生成首页', '编码质控', '首页质控', '结算质控']
    for (const label of stageLabels) {
      const buttons = wrapper.findAll('button').filter((button) => button.text() === label)
      expect(buttons).toHaveLength(2)
      expect(buttons.every((button) => button.attributes('disabled') !== undefined)).toBe(true)
    }

    const vm = wrapper.vm as unknown as FinalVm
    for (const row of sameVisitRows) {
      for (const action of ['open_record', 'generate_frontpage', 'qc_coding', 'qc_frontpage', 'qc_settlement']) {
        vm.jumpToWorkstation(row, action)
      }
    }
    expect(mocks.routerPush).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalled()

    const detailButtons = wrapper.findAll('[data-tooltip*="病历详情"] button')
    expect(detailButtons).toHaveLength(2)
    expect(detailButtons.every((button) => button.attributes('disabled') !== undefined)).toBe(true)
    const recordNumberCells = wrapper.findAll('[data-cell="record-number"]')
    expect(recordNumberCells).toHaveLength(2)
    for (const cell of recordNumberCells) {
      await cell.find('*').trigger('click')
    }
    expect(wrapper.findComponent({ name: 'QCReviewDrawer' }).exists()).toBe(false)
    vm.handleView(sameVisitRows[0])
    await flushPromises()
    expect(wrapper.findComponent({ name: 'QCReviewDrawer' }).exists()).toBe(false)
    expect(mocks.routerPush).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalled()
  })

  it('三坐标行键隔离选择，未核实结果不伪装成零缺陷或已有评分', async () => {
    const rows = ['hospital-a', 'hospital-b'].map((hospitalId) => ({
      id: `${hospitalId}:final:same-visit-id`,
      hospital_id: hospitalId,
      visit_type: 'final',
      visit_id: 'same-visit-id',
      record_id: 'same-visit-id',
      patient_name: hospitalId,
      identity_status: 'unverified',
      status: 'unverified',
      defect_count: null,
      score: null,
      created_at: '2026-09-25T00:00:00Z',
    }))
    mocks.getFinalRecordList.mockResolvedValue({
      success: true,
      data: { items: rows, total: rows.length },
    })
    const wrapper = shallowMount(FinalRecordsView, {
      global: {
        stubs: {
          ProQueryBar: { template: '<div><slot name="filters" /><slot name="actions" /></div>' },
          ProTableToolbar: { template: '<div><slot /></div>' },
          ProStandardTable: {
            name: 'ProStandardTable',
            props: ['dataSource', 'rowKey', 'rowSelection'],
            template: '<div><div v-for="row in dataSource" :key="row.id" :data-row-key="row.id"><div data-cell="status"><slot name="bodyCell" :column="{ key: \'qcStatus\' }" :record="row" /></div><div data-cell="defects"><slot name="bodyCell" :column="{ key: \'defectCount\' }" :record="row" /></div><div data-cell="score"><slot name="bodyCell" :column="{ key: \'qcScore\' }" :record="row" /></div></div></div>',
          },
        },
      },
    })
    await flushPromises()

    const table = wrapper.findComponent({ name: 'ProStandardTable' })
    expect(table.props('rowKey')).toBe('id')
    expect(wrapper.findAll('[data-row-key]').map((row) => row.attributes('data-row-key'))).toEqual(
      rows.map((row) => row.id),
    )
    const selection = table.props('rowSelection') as {
      onChange: (keys: string[]) => void
      selectedRowKeys: string[]
    }
    selection.onChange([rows[0].id])
    await flushPromises()
    expect((table.props('rowSelection') as typeof selection).selectedRowKeys).toEqual([rows[0].id])
    expect(wrapper.findAll('[data-cell="status"]').map((cell) => cell.text())).toEqual([
      '质控归属待核实',
      '质控归属待核实',
    ])
    expect(wrapper.findAll('[data-cell="defects"]').map((cell) => cell.text())).toEqual([
      '—',
      '—',
    ])
    expect(wrapper.findAll('[data-cell="score"]').map((cell) => cell.text())).toEqual([
      '—',
      '—',
    ])
    expect(wrapper.findAll('[data-cell="status"]').map((cell) => cell.text().includes('通过') || cell.text().includes('失败'))).toEqual([false, false])
    const statusOptions = wrapper.findAll('a-select-option')
      .map((option) => option.attributes('value'))
    expect(statusOptions).toContain('unverified')
    expect(statusOptions).not.toContain('passed')
    expect(statusOptions).not.toContain('failed')
    expect(statusOptions).not.toContain('pending')
  })
})
