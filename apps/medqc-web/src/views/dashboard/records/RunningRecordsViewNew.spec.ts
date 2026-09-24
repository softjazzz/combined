import { nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RunningRecordsViewNew from './RunningRecordsViewNew.vue'

const state = vi.hoisted(() => ({
  getAdminRecordList: vi.fn(),
  getAdminOverview: vi.fn(),
  error: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('ant-design-vue', () => ({ message: { error: state.error } }))

vi.mock('@/api/qcAdmin', () => ({
  getAdminRecordList: state.getAdminRecordList,
  getAdminOverview: state.getAdminOverview,
  getDefectList: vi.fn(),
  batchDefectAction: vi.fn(),
  urgeDefect: vi.fn(),
  approveDefect: vi.fn(),
  batchCreateQCTask: vi.fn(),
  fetchTaskProgress: vi.fn(),
  batchCreateRemediation: vi.fn(),
  exportDefectsDownload: vi.fn(),
  reAnalyzeQCTask: vi.fn(),
}))

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

function render() {
  return shallowMount(RunningRecordsViewNew, {
    global: {
      stubs: {
        'a-progress': true,
        'a-button': true,
        'a-input': true,
        'a-select': true,
        'a-select-option': true,
        'a-tag': true,
        'a-tooltip': true,
        'a-dropdown': true,
        'a-menu': true,
        'a-menu-item': true,
      },
    },
  })
}

function recordState(wrapper: ReturnType<typeof render>) {
  return wrapper.vm as unknown as {
    records: unknown[]
    pagination: { current: number; total: number }
    selectedRowKeys: string[]
    fetchRecords: () => Promise<void>
  }
}

describe('旧运行病历页失败保护', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.getAdminOverview.mockResolvedValue({ success: true, data: null })
    state.getAdminRecordList.mockResolvedValue({
      success: true,
      data: { items: [{ id: 'record-1', patient_name: '已返回患者' }], total: 1 },
    })
  })

  it.each([
    ['业务失败', () => state.getAdminRecordList.mockResolvedValueOnce({ success: false, data: null })],
    ['请求异常', () => state.getAdminRecordList.mockRejectedValueOnce(new Error('network error'))],
  ])('%s时清空旧病历与分页，不显示虚构患者', async (_reason, failNext) => {
    const wrapper = render()
    await flush()
    const view = recordState(wrapper)
    expect(view.records).toHaveLength(1)

    view.pagination.current = 2
    view.selectedRowKeys = ['record-1']
    failNext()
    await view.fetchRecords()

    expect(view.records).toEqual([])
    expect(view.pagination.current).toBe(1)
    expect(view.pagination.total).toBe(0)
    expect(view.selectedRowKeys).toEqual([])
    expect(state.error).toHaveBeenCalled()
    wrapper.unmount()
  })
})
