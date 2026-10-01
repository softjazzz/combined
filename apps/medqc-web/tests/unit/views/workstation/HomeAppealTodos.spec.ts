import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getAppeals: vi.fn(),
  routerPush: vi.fn(),
  messageInfo: vi.fn(),
  auth: {
    user: { id: 'qc-manager-1' } as { id: string } | null,
    userRoles: ['qc_manager'] as string[],
  },
}))

vi.mock('@/api/appeal', () => ({ getAppeals: mocks.getAppeals }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.routerPush }) }))
vi.mock('ant-design-vue', () => ({ message: { info: mocks.messageInfo } }))

import HomeAppealTodos from '@/views/workstation/HomeAppealTodos.vue'

describe('HomeAppealTodos', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.auth.user = { id: 'qc-manager-1' }
    mocks.auth.userRoles = ['qc_manager']
    mocks.getAppeals.mockImplementation(({ scene }: { scene: string }) =>
      Promise.resolve({ items: [], total: scene === 'running' ? 2 : 0 }),
    )
  })

  it('审核者读取真实待办数并下钻审核队列', async () => {
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    expect(mocks.getAppeals).toHaveBeenCalledTimes(3)
    expect(mocks.getAppeals).toHaveBeenCalledWith({
      status: 'reviewable',
      scene: 'running',
      page: 1,
      pageSize: 1,
    })
    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('2')
    await wrapper.get('[data-testid="appeal-review-todo-running"]').trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith({
      path: '/dashboard/qc/appeals',
      query: { todo: 'review', scene: 'running' },
    })
  })

  it('非审核角色不显示入口且不请求共享池', async () => {
    mocks.auth.userRoles = ['doctor']
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    expect(wrapper.find('[data-testid="appeal-review-todo-running"]').exists()).toBe(false)
    expect(mocks.getAppeals).not.toHaveBeenCalled()
  })

  it('真实零值给空反馈，不进入列表', async () => {
    mocks.getAppeals.mockResolvedValue({ items: [], total: 0 })
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()
    await wrapper.get('[data-testid="appeal-review-todo-running"]').trigger('click')

    expect(mocks.messageInfo).toHaveBeenCalledWith('没有待审核的临床申诉')
    expect(mocks.routerPush).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="appeal-todos-empty"]').text()).toBe('没有待处理事项')
    await wrapper.get('[data-testid="all-appeals"]').trigger('click')
    expect(mocks.routerPush).toHaveBeenCalledWith('/dashboard/qc/appeals')
  })

  it('请求失败显示不可用，重试后恢复', async () => {
    mocks.getAppeals.mockRejectedValueOnce(new Error('private database details'))
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('不可用')
    expect(wrapper.get('[data-testid="appeal-todos-error"]').text()).not.toContain('private')
    expect(wrapper.find('[data-testid="appeal-todos-empty"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="appeal-review-todo-running"]').element).toHaveProperty(
      'disabled',
      true,
    )

    await wrapper.get('[aria-label="刷新临床申诉待办"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('2')
  })
})
