import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  fetchTaskProgress: vi.fn(),
  getAdminOverview: vi.fn(),
  getAdminRecordList: vi.fn(),
  getDefectList: vi.fn(),
  reAnalyzeQCTask: vi.fn(),
  message: {
    error: vi.fn(),
    loading: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/qcAdmin', () => ({
  approveDefect: vi.fn(),
  batchCreateQCTask: vi.fn(),
  batchCreateRemediation: vi.fn(),
  batchDefectAction: vi.fn(),
  exportDefectsDownload: vi.fn(),
  fetchTaskProgress: mocks.fetchTaskProgress,
  getAdminOverview: mocks.getAdminOverview,
  getAdminRecordList: mocks.getAdminRecordList,
  getDefectList: mocks.getDefectList,
  reAnalyzeQCTask: mocks.reAnalyzeQCTask,
  urgeDefect: vi.fn(),
}))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    AlertOutlined: icon,
    CheckCircleOutlined: icon,
    CheckOutlined: icon,
    ClockCircleOutlined: icon,
    CloseOutlined: icon,
    DeleteOutlined: icon,
    ExclamationCircleOutlined: icon,
    EyeOutlined: icon,
    FilePdfOutlined: icon,
    FileTextOutlined: icon,
    FilterOutlined: icon,
    MoreOutlined: icon,
    PlusOutlined: icon,
    ReloadOutlined: icon,
    SearchOutlined: icon,
    SendOutlined: icon,
    ThunderboltOutlined: icon,
  }
})

import RunningRecordsViewNew from '@/views/dashboard/records/RunningRecordsViewNew.vue'

type RunningVm = {
  handleTaskCreated: (data: {
    task_id: string
    task_number: string
    sampled: boolean
    sampled_count: number
  }) => void
  stopProgressPolling: () => void
  handleMenuAction: (key: string, record: { task_id: string }) => Promise<void>
}

describe('RunningRecordsViewNew 任务创建阶段', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getAdminOverview.mockResolvedValue({ success: true, data: {} })
    mocks.getAdminRecordList.mockResolvedValue({
      success: true,
      data: { items: [], total: 0 },
    })
    mocks.getDefectList.mockResolvedValue({ success: true, data: { items: [], total: 0 } })
    mocks.fetchTaskProgress.mockResolvedValue({ success: false })
  })

  it('运行病历入口固定 scene=running，只有抽样完成才轮询', async () => {
    const wrapper = shallowMount(RunningRecordsViewNew, {
      global: {
        stubs: {
          'a-button': true,
          'a-dropdown': true,
          'a-input': true,
          'a-menu': true,
          'a-menu-item': true,
          'a-progress': true,
          'a-select': true,
          'a-select-option': true,
          'a-tag': true,
          'a-tooltip': true,
        },
      },
    })
    await flushPromises()
    const modal = wrapper.findComponent({ name: 'CreateTaskModal' })
    expect(modal.props('scene')).toBe('running')

    const vm = wrapper.vm as unknown as RunningVm
    vm.handleTaskCreated({
      task_id: 'draft-task',
      task_number: 'QC-DRAFT',
      sampled: false,
      sampled_count: 0,
    })
    expect(mocks.fetchTaskProgress).not.toHaveBeenCalled()

    vm.handleTaskCreated({
      task_id: 'sampled-task',
      task_number: 'QC-SAMPLED',
      sampled: true,
      sampled_count: 3,
    })
    await flushPromises()
    expect(mocks.fetchTaskProgress).toHaveBeenCalledWith('sampled-task')
    vm.stopProgressPolling()
  })

  it('旧任务重新质控部分成功时展示后端的真实结果说明', async () => {
    mocks.reAnalyzeQCTask.mockResolvedValue({
      success: true,
      message: '重新质控部分完成：本次尝试 2 条，成功 1 条，失败 1 条，未尝试 0 条',
    })
    const wrapper = shallowMount(RunningRecordsViewNew, {
      global: {
        stubs: {
          'a-button': true,
          'a-dropdown': true,
          'a-input': true,
          'a-menu': true,
          'a-menu-item': true,
          'a-progress': true,
          'a-select': true,
          'a-select-option': true,
          'a-tag': true,
          'a-tooltip': true,
        },
      },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as RunningVm
    await vm.handleMenuAction('reanalyze', { task_id: 'legacy-task' })

    expect(mocks.reAnalyzeQCTask).toHaveBeenCalledWith('legacy-task')
    expect(mocks.message.success).toHaveBeenCalledWith(
      '重新质控部分完成：本次尝试 2 条，成功 1 条，失败 1 条，未尝试 0 条',
    )
  })
})
