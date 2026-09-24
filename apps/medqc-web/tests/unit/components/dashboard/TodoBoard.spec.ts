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
  task_stats: { in_progress: 0, not_started: 0, countdown: 0 },
  defect_stats: { clinical_appeals: 0, pending_review: 0, urged: 0 },
  record_stats: { pending_review: 0, pending_recheck: 0, total: 0 },
}
const mountOptions = { global: { stubs: { 'a-segmented': true } } }

describe('TodoBoard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('真实零值展示空反馈，点击不进入空白筛选页', async () => {
    const wrapper = shallowMount(TodoBoard, { props: { todoData: zeroData }, ...mountOptions })

    expect(wrapper.get('[data-testid="todo-board-empty"]').text()).toBe('没有待处理事项')
    expect(wrapper.find('[data-testid="todo-board-unavailable"]').exists()).toBe(false)
    await wrapper.findAll('.stat-item')[0].trigger('click')
    expect(mocks.info).toHaveBeenCalledWith('没有待处理事项')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('数据缺失时不伪装成零，无法下钻', async () => {
    const wrapper = shallowMount(TodoBoard, { props: { todoData: {} }, ...mountOptions })

    expect(wrapper.get('[data-testid="todo-board-unavailable"]').text()).toBe('待办数据暂不可用')
    expect(wrapper.findAll('.stat-number')[0].text()).toBe('不可用')
    await wrapper.findAll('.stat-item')[0].trigger('click')
    expect(mocks.warning).toHaveBeenCalled()
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('非零值保留原有下钻行为', async () => {
    const wrapper = shallowMount(TodoBoard, {
      props: { todoData: { ...zeroData, task_stats: { ...zeroData.task_stats, in_progress: 2 } } },
      ...mountOptions,
    })

    await wrapper.findAll('.stat-item')[0].trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/dashboard/tasks/my',
      query: { status: 'in_progress' },
    })
  })
})
