import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskTodoStats: vi.fn(),
  routerPush: vi.fn(),
  message: { info: vi.fn(), warning: vi.fn() },
}))

vi.mock('@/api/tasks', () => ({ getTaskTodoStats: mocks.getTaskTodoStats }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.routerPush }) }))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))

import HomeTaskTodos from '@/views/workstation/HomeTaskTodos.vue'

const asOf = '2026-09-22T07:30:00+00:00'

function success(overrides: Record<string, unknown> = {}) {
  return {
    success: true,
    data: { as_of: asOf, assigned: 2, in_progress: 1, due_soon: 3, ...overrides },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

describe('HomeTaskTodos', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getTaskTodoStats.mockResolvedValue(success())
  })

  it('独立展示全部场景的三类个人任务待办', async () => {
    const wrapper = mount(HomeTaskTodos)
    await flushPromises()

    expect(wrapper.get('h2').text()).toBe('我的任务待办')
    expect(wrapper.text()).toContain('全部场景')
    expect(wrapper.get('[data-testid="todo-due_soon-count"]').text()).toBe('3')
    expect(wrapper.get('[data-testid="todo-in_progress-count"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="todo-assigned-count"]').text()).toBe('2')
    expect(mocks.getTaskTodoStats).toHaveBeenCalledWith(undefined)
  })

  it('切换场景后禁用旧数，并将场景带入统计与下钻链接', async () => {
    const running = deferred<ReturnType<typeof success>>()
    mocks.getTaskTodoStats.mockResolvedValueOnce(success()).mockReturnValueOnce(running.promise)
    const wrapper = mount(HomeTaskTodos)
    await flushPromises()

    await wrapper.get('[data-testid="home-task-scene"]').setValue('running')
    expect(wrapper.get('[data-testid="todo-assigned-count"]').text()).toBe('加载中')
    expect(mocks.getTaskTodoStats).toHaveBeenLastCalledWith({ scene: 'running' })

    running.resolve(success({ assigned: 4 }))
    await flushPromises()
    await wrapper.get('[data-testid="todo-assigned"]').trigger('click')
    expect(mocks.routerPush).toHaveBeenLastCalledWith({
      path: '/dashboard/tasks/my',
      query: { todo: 'assigned', as_of: asOf, scene: 'running' },
    })
  })

  it('场景快速切换时晚到旧响应不覆盖新场景', async () => {
    const running = deferred<ReturnType<typeof success>>()
    const final = deferred<ReturnType<typeof success>>()
    mocks.getTaskTodoStats
      .mockResolvedValueOnce(success())
      .mockReturnValueOnce(running.promise)
      .mockReturnValueOnce(final.promise)
    const wrapper = mount(HomeTaskTodos)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      activeSceneValue: string
      fetchTodos: () => Promise<void>
    }
    vm.activeSceneValue = 'running'
    void vm.fetchTodos()
    vm.activeSceneValue = 'final'
    void vm.fetchTodos()
    final.resolve(success({ assigned: 7 }))
    await flushPromises()
    running.resolve(success({ assigned: 9 }))
    await flushPromises()

    expect(wrapper.get('[data-testid="todo-assigned-count"]').text()).toBe('7')
    expect(wrapper.text()).toContain('终末')
  })

  it.each(['due_soon', 'in_progress', 'assigned'] as const)(
    '%s 非零时携带服务端 as_of 下钻已有个人列表',
    async (todo) => {
      const wrapper = mount(HomeTaskTodos)
      await flushPromises()

      await wrapper.get(`[data-testid="todo-${todo}"]`).trigger('click')

      expect(mocks.routerPush).toHaveBeenLastCalledWith({
        path: '/dashboard/tasks/my',
        query: { todo, as_of: asOf },
      })
    },
  )

  it('真实零值只提示没有待处理事项', async () => {
    mocks.getTaskTodoStats.mockResolvedValue(success({ assigned: 0 }))
    const wrapper = mount(HomeTaskTodos)
    await flushPromises()

    await wrapper.get('[data-testid="todo-assigned"]').trigger('click')

    expect(mocks.message.info).toHaveBeenCalledWith('没有待处理的事项')
    expect(mocks.routerPush).not.toHaveBeenCalled()
  })

  it('失败显示不可用且重试可恢复，不伪装成零值', async () => {
    mocks.getTaskTodoStats.mockResolvedValueOnce({ success: false, message: '服务暂不可用' })
    const wrapper = mount(HomeTaskTodos)
    await flushPromises()

    expect(wrapper.get('[data-testid="home-task-todos-error"]').text()).toContain('服务暂不可用')
    expect(wrapper.get('[data-testid="todo-assigned-count"]').text()).toBe('不可用')

    mocks.getTaskTodoStats.mockResolvedValueOnce(success({ assigned: 4 }))
    await wrapper.get('[data-testid="retry-home-task-todos"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="todo-assigned-count"]').text()).toBe('4')
  })

  it('晚到旧失败不覆盖较新的成功统计', async () => {
    const first = deferred<{ success: false; message: string }>()
    const second = deferred<ReturnType<typeof success>>()
    mocks.getTaskTodoStats.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = mount(HomeTaskTodos)

    const vm = wrapper.vm as unknown as { fetchTodos: () => Promise<void> }
    void vm.fetchTodos()
    second.resolve(success({ due_soon: 5 }))
    await flushPromises()
    expect(wrapper.get('[data-testid="todo-due_soon-count"]').text()).toBe('5')

    first.resolve({ success: false, message: '旧请求失败' })
    await flushPromises()
    expect(wrapper.get('[data-testid="todo-due_soon-count"]').text()).toBe('5')
    expect(wrapper.find('[data-testid="home-task-todos-error"]').exists()).toBe(false)
  })
})
