import { nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  getList: vi.fn(),
  getDepartments: vi.fn(),
  getDetail: vi.fn(),
  exportRecords: vi.fn(),
  downloadBlob: vi.fn(),
  error: vi.fn(),
}))
const authControl = vi.hoisted(() => ({
  set: null as null | ((user: { id: string; roles: string[] } | null) => void),
}))

vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  const auth = reactive({
    user: null as { id: string; roles: string[] } | null,
    userRoles: [] as string[],
  })
  authControl.set = (user) => {
    auth.user = user
    auth.userRoles = user ? [...user.roles] : []
  }
  return { useAuthStore: () => auth }
})

vi.mock('ant-design-vue', () => ({ message: { error: state.error, warning: vi.fn() } }))
vi.mock('@/api/qcAdmin', () => ({
  getOutpatientEmergencyRecordList: state.getList,
  getDepartmentList: state.getDepartments,
  getRecordDetail: state.getDetail,
  exportOutpatientEmergencyRecords: state.exportRecords,
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({
  downloadBlob: state.downloadBlob,
}))

import OutpatientEmergencyRecordsView from './OutpatientEmergencyRecordsView.vue'
import type { OutpatientEmergencyRecordFilters } from '@/api/qcAdmin'

const ButtonStub = {
  props: ['disabled', 'loading'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot name="icon"/><slot/></button>',
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function render() {
  authControl.set?.({ id: 'admin-1', roles: ['admin'] })
  return shallowMount(OutpatientEmergencyRecordsView, {
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-input': true,
        'a-select': true,
        'a-select-option': true,
        'a-range-picker': true,
        'a-tooltip': true,
        'a-table': true,
        OutpatientFilterTemplateBar: true,
        OutpatientEmergencyDetailDrawer: true,
        Download: true,
        ReloadOutlined: true,
        SearchOutlined: true,
      },
    },
  })
}

type ViewState = {
  searchKeyword: string
  selectedDepartment?: string
  scoringStandard: string
  appliedExportFilters: OutpatientEmergencyRecordFilters | null
  exportLoading: boolean
  listError: string
  records: Array<{ id: string }>
  handleSearch: () => void
  handleExportRecords: () => Promise<void>
  resetFilters: () => void
}

describe('门急诊病历列表导出', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authControl.set?.({ id: 'admin-1', roles: ['admin'] })
    state.getDepartments.mockResolvedValue({ success: true, data: [] })
    state.getList.mockResolvedValue({
      success: true,
      data: { items: [], total: 0, page: 1, page_size: 20 },
    })
    state.exportRecords.mockResolvedValue({
      success: true,
      blob: new Blob(['csv'], { type: 'text/csv' }),
      filename: 'outpatient-emergency-records.csv',
    })
  })

  it('导出最近一次成功列表的全量筛选，不读取尚未查询的关键词或分页', async () => {
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState
    view.searchKeyword = '尚未查询的关键词'
    await flush()

    await wrapper.get('[data-testid="export-outpatient-records"]').trigger('click')
    await flush()

    expect(state.exportRecords).toHaveBeenLastCalledWith({
      keyword: undefined,
      department: undefined,
      scoring_standard: undefined,
      start_date: undefined,
      end_date: undefined,
      sort_field: 'visit_date',
      sort_order: 'desc',
    })
    expect(state.downloadBlob).toHaveBeenCalledOnce()

    view.handleSearch()
    await flush()
    await view.handleExportRecords()
    expect(state.exportRecords).toHaveBeenLastCalledWith(expect.objectContaining({
      keyword: '尚未查询的关键词',
    }))
    wrapper.unmount()
  })

  it('评分标准精确条件进入查询和导出，未查询修改不污染快照，重置清空条件', async () => {
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState
    expect(wrapper.find('[data-testid="outpatient-scoring-standard-filter"]').exists()).toBe(true)
    view.scoringStandard = ' 门急诊历史标准 '
    view.handleSearch()
    await flush()
    expect(state.getList).toHaveBeenLastCalledWith(expect.objectContaining({
      scoring_standard: '门急诊历史标准',
      page: 1,
    }))
    view.scoringStandard = '未查询标准'
    await flush()
    await view.handleExportRecords()
    expect(state.exportRecords).toHaveBeenLastCalledWith(expect.objectContaining({
      scoring_standard: '门急诊历史标准',
    }))
    view.resetFilters()
    await flush()
    expect(view.scoringStandard).toBe('')
    expect(state.getList).toHaveBeenLastCalledWith(expect.objectContaining({
      scoring_standard: undefined,
    }))
    wrapper.unmount()
  })

  it('筛选变化后丢弃迟到导出，不下载旧筛选文件', async () => {
    const pending = deferred<{
      success: true
      blob: Blob
      filename: string
    }>()
    state.exportRecords.mockReturnValueOnce(pending.promise)
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState

    const exporting = view.handleExportRecords()
    expect(view.exportLoading).toBe(true)
    view.selectedDepartment = '急诊科'
    await flush()
    pending.resolve({
      success: true,
      blob: new Blob(['csv'], { type: 'text/csv' }),
      filename: 'outpatient-emergency-records.csv',
    })
    await exporting
    await flush()

    expect(state.downloadBlob).not.toHaveBeenCalled()
    expect(view.exportLoading).toBe(false)
    wrapper.unmount()
  })

  it('账号变化或页面卸载后均不处理旧账号的迟到导出', async () => {
    const accountPending = deferred<{ success: true; blob: Blob; filename: string }>()
    state.exportRecords.mockReturnValueOnce(accountPending.promise)
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState
    const exporting = view.handleExportRecords()
    authControl.set?.({ id: 'admin-2', roles: ['admin'] })
    await flush()
    accountPending.resolve({
      success: true,
      blob: new Blob(['old-account']),
      filename: 'old.csv',
    })
    await exporting
    expect(state.downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()

    const unmountPending = deferred<{ success: true; blob: Blob; filename: string }>()
    state.exportRecords.mockReturnValueOnce(unmountPending.promise)
    const second = render()
    await flush()
    const secondView = second.vm as unknown as ViewState
    const unmountedExport = secondView.handleExportRecords()
    second.unmount()
    unmountPending.resolve({ success: true, blob: new Blob(['late']), filename: 'late.csv' })
    await unmountedExport
    expect(state.downloadBlob).not.toHaveBeenCalled()
  })

  it('导出失败显示真实错误且不创建下载', async () => {
    state.exportRecords.mockResolvedValueOnce({ success: false, message: '筛选结果超过10000条' })
    const wrapper = render()
    await flush()

    await (wrapper.vm as unknown as ViewState).handleExportRecords()

    expect(state.error).toHaveBeenCalledWith('筛选结果超过10000条')
    expect(state.downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([
    ['缺失总数', { items: [] }],
    ['总数错型', { items: [], total: '0' }],
    ['明细错型', { items: null, total: 0 }],
  ])('成功回执%s时不伪装为0条，也不开放导出', async (_label, data) => {
    state.getList.mockResolvedValueOnce({ success: true, data })
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState

    expect(view.listError).toContain('返回格式异常')
    expect(view.appliedExportFilters).toBeNull()
    expect(wrapper.get('[data-testid="export-outpatient-records"]').attributes('disabled')).toBeDefined()
    expect(state.exportRecords).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('切换账号使旧账号迟到列表失效，不能开放新账号导出', async () => {
    const oldList = deferred<{
      success: true
      data: { items: Array<{ id: string }>; total: number }
    }>()
    state.getList
      .mockReturnValueOnce(oldList.promise)
      .mockResolvedValueOnce({ success: false, message: '新账号无权读取' })
    const wrapper = render()
    await flush()
    const view = wrapper.vm as unknown as ViewState

    authControl.set?.({ id: 'admin-2', roles: ['admin'] })
    await flush()
    oldList.resolve({ success: true, data: { items: [{ id: 'old-account-record' }], total: 1 } })
    await flush()

    expect(view.records).toEqual([])
    expect(view.listError).toBe('新账号无权读取')
    expect(view.appliedExportFilters).toBeNull()
    expect(state.exportRecords).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
