import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  todos: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  route: null as null | { query: Record<string, string> },
}))

vi.mock('@/api/recordReviews', () => ({ getRecordReviewTodos: mocks.todos }))
vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}))

import RecordReviewTodoView from '@/views/qc/RecordReviewTodoView.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const slot = { template: '<div><slot /></div>' }

function todo(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 'task-1', task_name: '九月运行抽查', task_scene: 'running', task_record_id: 'assoc-1',
    record_status: 'in_progress', institute_id: 'H1', patient_id: 'P1', visit_id: 'V1',
    rule_set_key: 'lx0609', rule_set_version: 'v1', run_number: 3, job_id: 'job-3',
    envelope_id: 'env-3', stage: 'recheck', state: 'pending_recheck', ...overrides,
  }
}

function mountView() {
  return mount(RecordReviewTodoView, {
    global: { stubs: {
      'a-page-header': true, 'a-card': slot, 'a-radio-group': slot, 'a-radio-button': slot,
      'a-select': true, 'a-pagination': true,
      'a-alert': { template: '<div data-testid="record-review-todo-error">{{ $attrs.message }}</div>' },
      'a-empty': { template: '<div data-testid="empty">{{ $attrs.description }}</div>' },
      'a-tag': { template: '<span><slot /></span>' },
      'a-button': ButtonStub,
    } },
  })
}

describe('RecordReviewTodoView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route = reactive({ query: {} })
    mocks.todos.mockResolvedValue({ success: true, status: 200, data: { items: [todo()], total: 1, page: 1, page_size: 20, stage: null, scene: 'all' } })
  })

  it('按 query 的 stage 与 scene 请求，无效值回落默认', async () => {
    mocks.route = reactive({ query: { stage: 'recheck', scene: 'running' } })
    mountView()
    await flushPromises()
    expect(mocks.todos).toHaveBeenCalledWith({ stage: 'recheck', scene: 'running', page: 1, page_size: 20 })

    mocks.route = reactive({ query: { stage: 'bogus', scene: 'bogus' } })
    mountView()
    await flushPromises()
    expect(mocks.todos).toHaveBeenLastCalledWith({ stage: undefined, scene: 'all', page: 1, page_size: 20 })
  })

  it('展示病例、任务、运行与阶段，去审核带任务/病历/运行定位跳转', async () => {
    const wrapper = mountView()
    await flushPromises()
    const text = wrapper.get('[data-testid="record-review-todo-item"]').text()
    expect(text).toContain('机构 H1 / 患者 P1 / 就诊 V1')
    expect(text).toContain('九月运行抽查')
    expect(text).toContain('第 3 次运行')
    expect(text).toContain('待复审')
    await wrapper.get('[data-testid="record-review-go-assoc-1"]').trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/dashboard/tasks/my',
      query: { task_id: 'task-1', task_record_id: 'assoc-1', run_number: '3' },
    })
  })

  it('失败显示错误而不是空列表，空结果显示空态', async () => {
    mocks.todos.mockResolvedValueOnce({ success: false, status: 503, message: '病历审核服务暂不可用，请稍后重试' })
    const failed = mountView()
    await flushPromises()
    expect(failed.get('[data-testid="record-review-todo-error"]').text()).toContain('暂不可用')
    expect(failed.find('[data-testid="empty"]').exists()).toBe(false)
    failed.unmount()

    mocks.todos.mockResolvedValueOnce({ success: true, status: 200, data: { items: [], total: 0, page: 1, page_size: 20, stage: 'initial', scene: 'all' } })
    const empty = mountView()
    await flushPromises()
    expect(empty.get('[data-testid="empty"]').text()).toContain('当前没有待审核的病历')
  })

  it('筛选变化后晚到的旧响应不覆盖新范围', async () => {
    let resolveOld!: (value: unknown) => void
    mocks.todos.mockReturnValueOnce(new Promise((done) => { resolveOld = done }))
    const wrapper = mountView()
    mocks.route!.query = { stage: 'initial' }
    mocks.todos.mockResolvedValueOnce({ success: true, status: 200, data: { items: [todo({ stage: 'initial', task_record_id: 'assoc-new' })], total: 1, page: 1, page_size: 20, stage: 'initial', scene: 'all' } })
    await flushPromises()
    resolveOld({ success: true, status: 200, data: { items: [todo({ task_record_id: 'assoc-old' })], total: 1, page: 1, page_size: 20, stage: null, scene: 'all' } })
    await flushPromises()
    expect(wrapper.find('[data-testid="record-review-go-assoc-new"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="record-review-go-assoc-old"]').exists()).toBe(false)
  })
})
