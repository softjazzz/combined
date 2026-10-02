import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getOutpatientEmergencyRecordList: vi.fn(),
  getAdminOverview: vi.fn(),
  getDepartmentList: vi.fn(),
  getRecordDetail: vi.fn(),
  getDefectList: vi.fn(),
  batchDefectAction: vi.fn(),
  exportDefects: vi.fn(),
  urgeDefect: vi.fn(),
  approveDefect: vi.fn(),
  rejectDefect: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/qcAdmin', () => ({
  approveDefect: mocks.approveDefect,
  batchDefectAction: mocks.batchDefectAction,
  exportDefects: mocks.exportDefects,
  getDefectList: mocks.getDefectList,
  getAdminOverview: mocks.getAdminOverview,
  getDepartmentList: mocks.getDepartmentList,
  getRecordDetail: mocks.getRecordDetail,
  getOutpatientEmergencyRecordList: (params: { source?: string }) => params.source === 'cdm_outpat_record'
    ? Promise.resolve(emptySuccess) : mocks.getOutpatientEmergencyRecordList(params),
  getOutpatientCdmDetail: vi.fn(),
  rejectDefect: mocks.rejectDefect,
  urgeDefect: mocks.urgeDefect,
}))

// 视图按当前登录用户隔离列表与导出；本组用例固定为已登录管理员
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 'admin-1', roles: ['admin'] }, userRoles: ['admin'] }),
}))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => ({
  ReloadOutlined: { template: '<span />' },
  SearchOutlined: { template: '<span />' },
}))

import OutpatientEmergencyRecordsView from '@/views/dashboard/records/OutpatientEmergencyRecordsView.vue'
import OutpatientFilterTemplateBar from '@/views/dashboard/records/OutpatientFilterTemplateBar.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => {
        if (!attrs.disabled) emit('click')
      },
    }, slots.default?.())
  },
})

const TableStub = defineComponent({
  name: 'ATable',
  props: {
    dataSource: { type: Array, default: () => [] },
    loading: Boolean,
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        {
          'data-testid': 'outpatient-table',
          'data-record-ids': JSON.stringify(
            (props.dataSource as Array<{ id?: string }>).map((row) => row.id),
          ),
          'data-loading': String(props.loading),
        },
        (props.dataSource as Array<{ id?: string }>).map((record) =>
          h('div', { 'data-testid': `record-actions-${record.id}` }, [
            slots.bodyCell?.({ column: { key: 'status' }, record }),
            slots.bodyCell?.({ column: { key: 'score' }, record }),
            slots.bodyCell?.({ column: { key: 'defect_count' }, record }),
            slots.bodyCell?.({ column: { key: 'actions' }, record }),
          ]),
        ),
      )
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
  const wrapper = shallowMount(OutpatientEmergencyRecordsView, {
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
  ;(wrapper.vm as unknown as { recordSource: string }).recordSource = 'legacy_medical_records'
  return wrapper
}

describe('OutpatientEmergencyRecordsView 列表故障语义', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    mocks.getOutpatientEmergencyRecordList.mockResolvedValue(emptySuccess)
    mocks.getRecordDetail.mockResolvedValue({ success: true, data: {} })
  })

  it('正常空结果保留空表，不显示数据源故障', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('[data-testid="outpatient-list-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="outpatient-table"]').attributes('data-record-ids')).toBe('[]')
    expect(wrapper.get('[data-testid="outpatient-current-total"]').text()).toBe('0')
    expect(mocks.getAdminOverview).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('94.2')
    expect(wrapper.text().match(/暂不可用/g)).toHaveLength(4)
  })

  it('把当前真实查询条件交给门急诊模板，并用一次查询应用模板', async () => {
    const wrapper = mountView()
    await flushPromises()
    const templateBar = wrapper.getComponent(OutpatientFilterTemplateBar)
    expect(templateBar.props('currentFilters')).toEqual({
      scoring_standard: undefined,
      keyword: undefined,
      department: undefined,
      start_date: undefined,
      end_date: undefined,
    })

    mocks.getOutpatientEmergencyRecordList.mockClear()
    templateBar.vm.$emit('apply', {
      keyword: '张三',
      department: '急诊科',
      start_date: '2026-09-01',
      end_date: '2026-09-02',
    })
    await flushPromises()

    expect(mocks.getOutpatientEmergencyRecordList).toHaveBeenCalledTimes(1)
    expect(mocks.getOutpatientEmergencyRecordList).toHaveBeenCalledWith(expect.objectContaining({
      keyword: '张三',
      department: '急诊科',
      start_date: '2026-09-01',
      end_date: '2026-09-02',
      page: 1,
    }))
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

  it('默认模板触发的新查询不会被初始未筛选请求的迟到失败覆盖', async () => {
    const oldRequest = deferred<{ success: false; message: string }>()
    const newRequest = deferred<ReturnType<typeof successWith>>()
    mocks.getOutpatientEmergencyRecordList
      .mockReturnValueOnce(oldRequest.promise)
      .mockReturnValueOnce(newRequest.promise)
    const wrapper = mountView()

    await nextTick()
    wrapper.getComponent(OutpatientFilterTemplateBar).vm.$emit('apply', { keyword: '默认模板' })
    await nextTick()
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

  it('从列表打开详情失败后保留病历上下文，可重试并区分真实成功空集', async () => {
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce(successWith('record-A'))
    mocks.getRecordDetail
      .mockResolvedValueOnce({ success: false, message: '详情服务暂不可用' })
      .mockResolvedValueOnce({ success: true, data: { defects: [], documents: {} } })
    const wrapper = mountView()
    await flushPromises()

    const action = wrapper.get('[data-testid="record-actions-record-A"]')
      .findAll('button').find((button) => button.text() === '查看病历文书')!
    await action.trigger('click')
    await flushPromises()

    const drawer = wrapper.getComponent({ name: 'OutpatientEmergencyDetailDrawer' })
    expect(drawer.props()).toMatchObject({
      visible: true,
      loading: false,
      record: expect.objectContaining({ id: 'record-A' }),
      detailData: null,
      error: '详情服务暂不可用',
    })

    drawer.vm.$emit('retry')
    await flushPromises()
    expect(mocks.getRecordDetail).toHaveBeenCalledTimes(2)
    expect(drawer.props('error')).toBe('')
    expect(drawer.props('detailData')).toEqual({ defects: [], documents: {} })
  })

  it('切换病历时旧响应不能覆盖当前详情，前后导航使用同一隔离语义', async () => {
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce({
      success: true,
      data: {
        items: [
          { id: 'record-A', record_id: 'A', patient_name: '患者甲' },
          { id: 'record-B', record_id: 'B', patient_name: '患者乙' },
        ],
        total: 2,
      },
    })
    const oldRequest = deferred<{ success: boolean; data: Record<string, unknown> }>()
    mocks.getRecordDetail
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce({ success: true, data: { defects: [{ id: 'B-defect' }] } })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-testid="record-actions-record-A"]').findAll('button')
      .find((button) => button.text() === '查看病历文书')!.trigger('click')
    const drawer = wrapper.getComponent({ name: 'OutpatientEmergencyDetailDrawer' })
    drawer.vm.$emit('navigate-next')
    await flushPromises()
    expect(drawer.props('record')).toMatchObject({ id: 'record-B' })
    expect(drawer.props('detailData')).toEqual({ defects: [{ id: 'B-defect' }] })

    oldRequest.resolve({ success: true, data: { defects: [{ id: 'A-defect' }] } })
    await flushPromises()
    expect(drawer.props('detailData')).toEqual({ defects: [{ id: 'B-defect' }] })
    expect(drawer.props('loading')).toBe(false)
  })

  it('关联待核实时只读详情可用，单条及批量质控操作不会查询或写入缺陷', async () => {
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce({
      success: true,
      data: {
        items: [{
          id: 'primary-id', record_id: 'business-id', patient_name: '测试患者',
          status: 'approved', score: 98, defect_count: 2,
        }],
        total: 1,
      },
    })
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as unknown as { selectedRowKeys: string[] }
    vm.selectedRowKeys = ['primary-id']
    await nextTick()

    expect(wrapper.text()).toContain('质控关联待核实')
    expect(wrapper.text()).not.toContain('已通过')
    expect(wrapper.get('[data-testid="record-actions-primary-id"]').text()).toContain('质控关联待核实')
    expect(wrapper.get('[data-testid="record-actions-primary-id"]').text()).toContain('暂不可用')
    expect(wrapper.findAll('button').filter((button) =>
      ['批量催办', '批量通过', '导出缺陷', '催办', '通过'].includes(button.text()),
    ).every((button) => button.attributes('disabled') !== undefined)).toBe(true)

    for (const button of wrapper.findAll('button').filter((item) =>
      ['批量催办', '批量通过', '导出缺陷', '催办', '通过'].includes(item.text()),
    )) {
      await button.trigger('click')
    }
    const drawer = wrapper.getComponent({ name: 'OutpatientEmergencyDetailDrawer' })
    drawer.vm.$emit('urge-defect', 'untrusted-defect')
    drawer.vm.$emit('approve-defect', 'untrusted-defect')
    drawer.vm.$emit('reject-defect', 'untrusted-defect')
    await flushPromises()
    for (const operation of [
      mocks.getDefectList, mocks.batchDefectAction, mocks.exportDefects,
      mocks.urgeDefect, mocks.approveDefect, mocks.rejectDefect,
    ]) expect(operation).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="record-actions-primary-id"]').findAll('button')
      .find((button) => button.text() === '查看病历文书')!.trigger('click')
    await flushPromises()
    expect(mocks.getRecordDetail).toHaveBeenCalledWith('primary-id', 'legacy_medical_records')
    expect(drawer.props('visible')).toBe(true)
  })

  it('缺少旧病历表主键时不回退使用就诊号打开详情', async () => {
    mocks.getOutpatientEmergencyRecordList.mockResolvedValueOnce({
      success: true,
      data: {
        items: [{ record_id: 'shared-visit', patient_name: '测试患者' }],
        total: 1,
      },
    })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('[data-testid="record-actions-undefined"]').findAll('button')
      .find((button) => button.text() === '查看病历文书')!.trigger('click')
    await flushPromises()

    expect(mocks.getRecordDetail).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalled()
    expect(wrapper.getComponent({ name: 'OutpatientEmergencyDetailDrawer' }).props('visible')).toBe(false)
  })
})
