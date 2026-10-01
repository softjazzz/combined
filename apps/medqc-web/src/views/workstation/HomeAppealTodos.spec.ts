import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import HomeAppealTodos from './HomeAppealTodos.vue'

const mocks = vi.hoisted(() => ({
  getAppeals: vi.fn(),
  push: vi.fn(),
  info: vi.fn(),
  authStore: null as {
    user: { id: string } | null
    userRoles: string[]
  } | null,
}))

vi.mock('@/api/appeal', () => ({ getAppeals: mocks.getAppeals }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('ant-design-vue', () => ({ message: { info: mocks.info } }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await vi.importActual<typeof import('vue')>('vue')
  mocks.authStore = reactive({ user: { id: 'reviewer-1' }, userRoles: ['qc_manager'] })
  return { useAuthStore: () => mocks.authStore }
})

function page(total: number) {
  return { items: [], total, page: 1, pageSize: 1, totalPages: total > 0 ? total : 0 }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

describe('V5 首页临床申诉待办', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.authStore!.user = { id: 'reviewer-1' }
    mocks.authStore!.userRoles = ['qc_manager']
    mocks.getAppeals.mockResolvedValue(page(3))
  })

  it('复用 reviewable 列表总数并按审核待办下钻', async () => {
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    expect(mocks.getAppeals).toHaveBeenCalledTimes(3)
    expect(mocks.getAppeals).toHaveBeenCalledWith({
      status: 'reviewable',
      scene: 'running',
      page: 1,
      pageSize: 1,
    })
    expect(mocks.getAppeals).toHaveBeenCalledWith({
      status: 'reviewable',
      scene: 'final',
      page: 1,
      pageSize: 1,
    })
    expect(mocks.getAppeals).toHaveBeenCalledWith({
      status: 'reviewable',
      scene: 'outpatient_emergency',
      page: 1,
      pageSize: 1,
    })
    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('3')

    await wrapper.get('[data-testid="appeal-review-todo-running"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/dashboard/qc/appeals',
      query: { todo: 'review', scene: 'running' },
    })
    wrapper.unmount()
  })

  it('两个可审核账号切换时清空旧计数并丢弃前账号迟到响应', async () => {
    const first = [
      deferred<ReturnType<typeof page>>(),
      deferred<ReturnType<typeof page>>(),
      deferred<ReturnType<typeof page>>(),
    ]
    mocks.getAppeals
      .mockReset()
      .mockReturnValueOnce(first[0].promise)
      .mockReturnValueOnce(first[1].promise)
      .mockReturnValueOnce(first[2].promise)
      .mockResolvedValue(page(7))
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    mocks.authStore!.user = { id: 'reviewer-2' }
    await flushPromises()
    expect(mocks.getAppeals).toHaveBeenCalledTimes(6)
    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('7')

    first.forEach(({ resolve }) => resolve(page(99)))
    await flushPromises()
    expect(wrapper.get('[data-testid="appeal-review-count-running"]').text()).toBe('7')
    wrapper.unmount()
  })

  it('权限或登录身份消失时立即失效在途请求并隐藏待办', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    mocks.getAppeals.mockReset().mockReturnValueOnce(pending.promise)
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    mocks.authStore!.userRoles = ['doctor']
    await flushPromises()
    expect(wrapper.find('[data-testid="appeal-review-todo-running"]').exists()).toBe(false)

    pending.resolve(page(99))
    await flushPromises()
    expect(wrapper.find('[data-testid="appeal-review-todo-running"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('卸载后使在途请求失效', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    mocks.getAppeals.mockReset().mockReturnValueOnce(pending.promise)
    const wrapper = mount(HomeAppealTodos)
    await flushPromises()

    wrapper.unmount()
    pending.resolve(page(99))
    await flushPromises()
    expect(mocks.push).not.toHaveBeenCalled()
  })
})
