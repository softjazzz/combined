import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import HomeReviewTodos from './HomeReviewTodos.vue'

const mocks = vi.hoisted(() => ({
  getReviewTodoCounts: vi.fn(),
  push: vi.fn(),
  info: vi.fn(),
  authStore: null as { user: { id: string } | null } | null,
}))

vi.mock('@/api/dashboard', () => ({ getReviewTodoCounts: mocks.getReviewTodoCounts }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('ant-design-vue', () => ({ message: { info: mocks.info } }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await vi.importActual<typeof import('vue')>('vue')
  mocks.authStore = reactive({ user: { id: 'user-1' } })
  return { useAuthStore: () => mocks.authStore }
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => { resolve = next })
  return { promise, resolve }
}

describe('V5 首页审核待办', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.authStore!.user = { id: 'user-1' }
    mocks.getReviewTodoCounts.mockResolvedValue({
      success: true,
      data: {
        pending_record_review: 3,
        pending_record_recheck: 2,
        pending_manual_defect_review: 4,
        scene: 'all',
      },
    })
  })

  it('显示三类真实计数并按同一谓词下钻', async () => {
    const wrapper = mount(HomeReviewTodos)
    await flushPromises()

    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('3')
    expect(wrapper.get('[data-testid="review-todo-record-recheck-count"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="review-todo-manual-defect-count"]').text()).toBe('4')

    await wrapper.get('[data-testid="review-todo-record-review"]').trigger('click')
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/dashboard/qc/record-reviews',
      query: { stage: 'initial', scene: 'all' },
    })
    await wrapper.get('[data-testid="review-todo-record-recheck"]').trigger('click')
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/dashboard/qc/record-reviews',
      query: { stage: 'recheck', scene: 'all' },
    })
    await wrapper.get('[data-testid="review-todo-manual-defect"]').trigger('click')
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/dashboard/qc/manual-defects',
      query: { review_status: 'pending', scene: 'all' },
    })
  })

  it('无人工缺陷审核权限时显示不可用且不下钻', async () => {
    mocks.getReviewTodoCounts.mockResolvedValueOnce({
      success: true,
      data: {
        pending_record_review: 1,
        pending_record_recheck: 0,
        pending_manual_defect_review: null,
        scene: 'all',
      },
    })
    const wrapper = mount(HomeReviewTodos)
    await flushPromises()

    const manual = wrapper.get('[data-testid="review-todo-manual-defect"]')
    expect(manual.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="review-todo-manual-defect-count"]').text()).toBe('不可用')
    expect(wrapper.get('[data-testid="manual-defect-scope-note"]').text()).toContain('无人工缺陷审核权限')
    await manual.trigger('click')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('真实 0 显示为 0，不进入空列表', async () => {
    mocks.getReviewTodoCounts.mockResolvedValueOnce({
      success: true,
      data: {
        pending_record_review: 0,
        pending_record_recheck: 0,
        pending_manual_defect_review: 0,
        scene: 'all',
      },
    })
    const wrapper = mount(HomeReviewTodos)
    await flushPromises()

    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('0')
    await wrapper.get('[data-testid="review-todo-record-review"]').trigger('click')
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.info).toHaveBeenCalledWith('没有待初审病历')
  })

  it('未接通病历审核来源显示不可用且不下钻、不提示零待办', async () => {
    mocks.getReviewTodoCounts.mockResolvedValueOnce({ success: true, data: {
      pending_record_review: null, pending_record_recheck: null, pending_manual_defect_review: 2,
      record_unavailable_reason: 'review_source_unavailable', scene: 'outpatient_emergency',
    } })
    const wrapper = mount(HomeReviewTodos, { props: { scene: 'outpatient_emergency' } })
    await flushPromises()
    for (const key of ['record-review', 'record-recheck']) {
      expect(wrapper.get(`[data-testid="review-todo-${key}-count"]`).text()).toBe('不可用')
      expect(wrapper.get(`[data-testid="review-todo-${key}"]`).attributes('disabled')).toBeDefined()
      await wrapper.get(`[data-testid="review-todo-${key}"]`).trigger('click')
    }
    expect(wrapper.get('[data-testid="record-review-scope-note"]').text()).toContain('审核来源尚未接通')
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.info).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="review-todo-manual-defect-count"]').text()).toBe('2')
  })

  it('失败后清空计数，重试恢复最新数据', async () => {
    mocks.getReviewTodoCounts
      .mockResolvedValueOnce({ success: false, message: '服务不可用' })
      .mockResolvedValueOnce({
        success: true,
        data: {
          pending_record_review: 5,
          pending_record_recheck: 1,
          pending_manual_defect_review: 2,
          scene: 'all',
        },
      })
    const wrapper = mount(HomeReviewTodos)
    await flushPromises()

    expect(wrapper.get('[data-testid="home-review-todos-error"]').text()).toContain('服务不可用')
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('不可用')

    await wrapper.get('[data-testid="retry-home-review-todos"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="home-review-todos-error"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('5')
  })

  it('账号切换时清空旧计数并丢弃前账号迟到响应', async () => {
    const first = deferred<{
      success: true
      data: {
        pending_record_review: number
        pending_record_recheck: number
        pending_manual_defect_review: number
        scene: 'all'
      }
    }>()
    mocks.getReviewTodoCounts
      .mockReset()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValue({
        success: true,
        data: {
          pending_record_review: 7,
          pending_record_recheck: 1,
          pending_manual_defect_review: 2,
          scene: 'all',
        },
      })
    const wrapper = mount(HomeReviewTodos)
    await flushPromises()

    mocks.authStore!.user = { id: 'user-2' }
    await flushPromises()
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('7')

    first.resolve({
      success: true,
      data: {
        pending_record_review: 99,
        pending_record_recheck: 99,
        pending_manual_defect_review: 99,
        scene: 'all',
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('7')

    mocks.authStore!.user = null
    await flushPromises()
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('不可用')
  })

  it('场景切换时清空旧计数、丢弃迟到响应并保持计数与下钻同场景', async () => {
    const first = deferred<{
      success: true
      data: {
        pending_record_review: number
        pending_record_recheck: number
        pending_manual_defect_review: number
        scene: 'running'
      }
    }>()
    const second = deferred<{
      success: true
      data: {
        pending_record_review: number
        pending_record_recheck: number
        pending_manual_defect_review: number
        scene: 'final'
      }
    }>()
    mocks.getReviewTodoCounts
      .mockReset()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const wrapper = mount(HomeReviewTodos, { props: { scene: 'running' } })
    await flushPromises()
    expect(mocks.getReviewTodoCounts).toHaveBeenLastCalledWith('running')

    await wrapper.setProps({ scene: 'final' })
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('加载中')
    second.resolve({
      success: true,
      data: {
        pending_record_review: 6,
        pending_record_recheck: 2,
        pending_manual_defect_review: 3,
        scene: 'final',
      },
    })
    await flushPromises()
    expect(mocks.getReviewTodoCounts).toHaveBeenLastCalledWith('final')
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('6')

    first.resolve({
      success: true,
      data: {
        pending_record_review: 99,
        pending_record_recheck: 99,
        pending_manual_defect_review: 99,
        scene: 'running',
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="review-todo-record-review-count"]').text()).toBe('6')

    await wrapper.get('[data-testid="review-todo-manual-defect"]').trigger('click')
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/dashboard/qc/manual-defects',
      query: { review_status: 'pending', scene: 'final' },
    })
  })
})
