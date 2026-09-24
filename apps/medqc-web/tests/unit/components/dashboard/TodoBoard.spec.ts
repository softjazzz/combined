import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TodoBoard from '@/components/dashboard/TodoBoard.vue'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('ant-design-vue', () => ({ message: { info: mocks.info, warning: mocks.warning } }))

const zeroData = {
  task_stats: { in_progress: 0, not_started: 0, countdown: 0, as_of: '2026-09-24T10:00:00Z' },
  defect_stats: { clinical_appeals: 0, pending_review: null, urged: null },
  record_stats: { pending_review: null, pending_recheck: null, total: 0 },
}

describe('TodoBoard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('真实零值展示空反馈，点击不进入空白筛选页', async () => {
    const wrapper = shallowMount(TodoBoard, { props: { todoData: zeroData } })

    expect(wrapper.get('[data-testid="todo-board-empty"]').text()).toBe('已接入待办：没有待处理事项')
    expect(wrapper.find('[data-testid="todo-board-unavailable"]').exists()).toBe(false)
    await wrapper.findAll('.stat-item')[0].trigger('click')
    expect(mocks.info).toHaveBeenCalledWith('没有待处理事项')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('数据缺失时不伪装成零，无法下钻', async () => {
    const wrapper = shallowMount(TodoBoard, { props: { todoData: {} } })

    expect(wrapper.get('[data-testid="todo-board-unavailable"]').text()).toBe('待办数据暂不可用')
    expect(wrapper.findAll('.stat-number')[0].text()).toBe('不可用')
    await wrapper.findAll('.stat-item')[0].trigger('click')
    expect(mocks.warning).toHaveBeenCalled()
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('任务计数按真实 todo 和快照下钻', async () => {
    const wrapper = shallowMount(TodoBoard, {
      props: {
        todoData: {
          ...zeroData,
          task_stats: { ...zeroData.task_stats, in_progress: 2, not_started: 3, countdown: 4 },
        },
      },
    })

    const items = wrapper.findAll('.stat-item')
    for (const [index, todo] of [[0, 'in_progress'], [1, 'assigned'], [2, 'due_soon']] as const) {
      await items[index].trigger('click')
      expect(mocks.push).toHaveBeenLastCalledWith({
        path: '/dashboard/tasks/my',
        query: { todo, as_of: zeroData.task_stats.as_of },
      })
    }
  })

  it('临床申诉走审核列表，未知审核类别不能下钻', async () => {
    const wrapper = shallowMount(TodoBoard, {
      props: {
        todoData: {
          ...zeroData,
          defect_stats: { ...zeroData.defect_stats, clinical_appeals: 2 },
        },
      },
    })

    const items = wrapper.findAll('.stat-item')
    await items[3].trigger('click')
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/dashboard/qc/appeals',
      query: { todo: 'review' },
    })
    mocks.push.mockClear()
    await items[4].trigger('click')
    await items[5].trigger('click')
    await items[6].trigger('click')
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.warning).toHaveBeenCalled()
  })
})
