import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getOutpatientEmergencyRecordList: vi.fn(),
  getAdminOverview: vi.fn(),
  getDepartmentList: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/qcAdmin', () => ({
  approveDefect: vi.fn(),
  batchDefectAction: vi.fn(),
  exportDefects: vi.fn(),
  getDefectList: vi.fn(),
  getAdminOverview: mocks.getAdminOverview,
  getDepartmentList: mocks.getDepartmentList,
  getRecordDetail: vi.fn(),
  getOutpatientEmergencyRecordList: mocks.getOutpatientEmergencyRecordList,
  rejectDefect: vi.fn(),
  urgeDefect: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => ({
  ReloadOutlined: { template: '<span />' },
  SearchOutlined: { template: '<span />' },
}))

import OutpatientEmergencyRecordsView from '@/views/dashboard/records/OutpatientEmergencyRecordsView.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const TableStub = defineComponent({
  name: 'ATable',
  props: {
    dataSource: { type: Array, default: () => [] },
    loading: Boolean,
  },
  setup(props) {
    return () =>
      h('div', {
        'data-testid': 'outpatient-table',
        'data-record-ids': JSON.stringify(
          (props.dataSource as Array<{ id?: string }>).map((row) => row.id),
        ),
        'data-loading': String(props.loading),
      })
  },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

const emptySuccess = {
  success: true,
  data: { items: [], total: 0, page: 1, page_size: 20 },
}

function successWith(id: string) {
  return {
    success: true,
    data: {
      items: [{ id, record_id: id, patient_name: '测试患者' }],
      total: 1,
      page: 1,
      page_size: 20,
    },
  }
}

function mountView() {
  return shallowMount(OutpatientEmergencyRecordsView, {
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-table': TableStub,
        'a-input': true,
        'a-select': true,
        'a-select-option': true,
        'a-range-picker': true,
        'a-tooltip': { template: '<div><slot /></div>' },
        'a-tag': true,
        OutpatientEmergencyDetailDrawer: true,
      },
    },
  })
}

describe('OutpatientEmergencyRecordsView 列表故障语义', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    mocks.getOutpatientEmergencyRecordList.mockResolvedValue(emptySuccess)
  })

  it('正常空结果保留空表，不显示数据源故障', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="outpatient-list-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-record-ids')).toBe('[]')
    expect(wrapper.get('[data-testid="outpatient-current-total"]').text()).toBe('0')
    expect(mocks.getAdminOverview).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('94.2')
    expect(wrapper.text().match(/暂不可用/g)).toHaveLength(3)
  })

  it('首指标使用当前筛选列表总数，加载与失败不显示假零', async () => {
    const pendingRequest = deferred<{
      success: boolean
      data?: { items: never[]; total: number; page: number; page_size: number }
      message?: string
    }>()
    mocks.getOutpatientEmergencyRecordList.mockReturnValueOnce(pendingRequest.promise)
    const wrapper = mountView()
    await nextTick()

    expect(wrapper.get('[data-testid="outpatient-current-total"]').text()).toBe('加载中')
    pendingRequest.resolve({
      success: true,
      data: { items: [], total: 37, page: 1, page_size: 20 },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="outpatient-current-total"]').text()).toBe('37')

    const vm = wrapper.vm as unknown as { fetchRecords: () => Promise<void> }
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce({
      success: false,
      message: '数据源暂不可用',
    })
    await vm.fetchRecords()
    await flushPromises()

    expect(wrapper.get('[data-testid="outpatient-current-total"]').text()).toBe('不可用')
    expect(wrapper.text()).not.toContain('94.2')
    expect(mocks.getAdminOverview).not.toHaveBeenCalled()
  })

  it.each([
    ['非成功响应', () => Promise.resolve({ success: false, message: '数据源暂不可用' })],
    ['请求抛错', () => Promise.reject(new Error('network down'))],
  ])('%s 时清空旧列表与选择，显示持久错误并可重试', async (_case, failedRequest) => {
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce(successWith('old-record'))
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      selectedRowKeys: string[]
      fetchRecords: () => Promise<void>
    }
    vm.selectedRowKeys = ['old-record']
    mocks.getOutpatientEmergencyRecordList.mockImplementationOnce(failedRequest)

    await vm.fetchRecords()
    await flushPromises()

    expect(vm.selectedRowKeys).toEqual([])
    expect(wrapper.find('[data-testid="outpatient-table"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="outpatient-list-error"]').text()).toContain(
      _case === '非成功响应' ? '数据源暂不可用' : '获取门急诊病历失败',
    )

    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce(successWith('recovered-record'))
    await wrapper.get('[data-testid="retry-outpatient-list"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="outpatient-list-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-record-ids')).toBe(
      '["recovered-record"]',
    )
  })

  it('晚到的旧失败不覆盖较新成功，旧请求也不提前结束加载态', async () => {
    const oldRequest = deferred<{ success: false; message: string }>()
    const newRequest = deferred<ReturnType<typeof successWith>>()
    mocks.getOutpatientEmergencyRecordList
      .mockReturnValueOnce(oldRequest.promise)
      .mockReturnValueOnce(newRequest.promise)
    const wrapper = mountView()
    const vm = wrapper.vm as unknown as { fetchRecords: () => Promise<void> }

    void vm.fetchRecords()
    oldRequest.resolve({ success: false, message: '旧请求失败' })
    await flushPromises()

    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-loading')).toBe('true')
    expect(wrapper.find('[data-testid="outpatient-list-error"]').exists()).toBe(false)

    newRequest.resolve(successWith('new-record'))
    await flushPromises()

    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-loading')).toBe('false')
    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-record-ids')).toBe(
      '["new-record"]',
    )
  })
})
