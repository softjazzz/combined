import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskAnalysis: vi.fn(),
  authState: { user: { id: 'user-1' } as { id: string } | null },
  authStore: null as unknown as { user: { id: string } | null },
}))

vi.mock('@/api/taskAnalysis', () => ({ getTaskAnalysis: mocks.getTaskAnalysis }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  mocks.authStore = reactive(mocks.authState)
  return { useAuthStore: () => mocks.authStore }
})

import TaskAnalysisDrawer from '@/components/qc/TaskAnalysisDrawer.vue'

const DrawerStub = defineComponent({
  props: { open: Boolean, title: String },
  emits: ['close'],
  setup(props, { emit, slots }) {
    return () => props.open
      ? h('section', { 'data-testid': 'drawer' }, [
          h('h2', props.title),
          h('button', { 'data-testid': 'close', onClick: () => emit('close') }, '关闭'),
          slots.default?.(),
        ])
      : null
  },
})

const ButtonStub = defineComponent({
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

function analysis(taskId = 'task-1', taskName = '任务一') {
  return {
    contract_version: 'task-analysis-v1',
    task: {
      id: taskId, task_number: `NO-${taskId}`, task_name: taskName, scene: 'running',
      status: 'in_progress', creator_id: 'creator', creator_name: '创建人',
    },
    summary: {
      total_records: 3, completed_records: 1, completion_rate: 33.33,
      average_score: null, score_known_count: 1, score_unknown_count: 2,
      total_defect_count: null, defect_known_count: 1, defect_unknown_count: 2,
    },
    status_counts: { pending: 1, in_progress: 1, completed: 1, skipped: 0, unknown: 0 },
    assignees: [
      { assignee_id: 'staff-1', assignee_name: '质控员甲', total_records: 2, completed_records: 1, completion_rate: 50 },
      { assignee_id: null, assignee_name: null, total_records: 1, completed_records: 0, completion_rate: 0 },
    ],
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

const mountedWrappers: Array<ReturnType<typeof mount>> = []

function mountDrawer(taskId = 'task-1') {
  const wrapper = mount(TaskAnalysisDrawer, {
    props: { open: true, taskId },
    global: {
      stubs: {
        'a-button': ButtonStub,
        'a-drawer': DrawerStub,
        'a-empty': { template: '<div data-testid="empty">{{ $attrs.description }}</div>' },
        'a-skeleton': true,
        Eye: true,
        RotateCw: true,
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('TaskAnalysisDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.authStore.user = { id: 'user-1' }
    mocks.getTaskAnalysis.mockResolvedValue({ success: true, data: analysis() })
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows unknown metrics without converting them to zero and emits same-task detail', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.text()).toContain('任务一')
    expect(wrapper.text()).toContain('未知 2 份')
    expect(wrapper.text()).toContain('未分配')
    expect(wrapper.text()).not.toContain('已知评分均值0')

    await wrapper.get('[data-testid="open-task-detail"]').trigger('click')
    expect(wrapper.emitted('view-detail')).toEqual([['task-1']])
  })

  it('discards a late response after switching tasks', async () => {
    const first = deferred<{ success: true; data: ReturnType<typeof analysis> }>()
    mocks.getTaskAnalysis
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ success: true, data: analysis('task-2', '任务二') })
    const wrapper = mountDrawer('task-1')
    await wrapper.setProps({ taskId: 'task-2' })
    await flushPromises()
    expect(wrapper.text()).toContain('任务二')

    first.resolve({ success: true, data: analysis('task-1', '迟到任务一') })
    await flushPromises()
    expect(wrapper.text()).toContain('任务二')
    expect(wrapper.text()).not.toContain('迟到任务一')
  })

  it('reloads on account change and ignores the old account response', async () => {
    const first = deferred<{ success: true; data: ReturnType<typeof analysis> }>()
    mocks.getTaskAnalysis
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ success: true, data: analysis('task-1', '新账号结果') })
    const wrapper = mountDrawer()
    mocks.authStore.user = { id: 'user-2' }
    await flushPromises()
    expect(mocks.getTaskAnalysis).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('新账号结果')

    first.resolve({ success: true, data: analysis('task-1', '旧账号迟到结果') })
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧账号迟到结果')
  })

  it('keeps failures explicit and retries', async () => {
    mocks.getTaskAnalysis
      .mockResolvedValueOnce({ success: false, message: '任务分析读取失败' })
      .mockResolvedValueOnce({ success: true, data: analysis() })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('任务分析读取失败')
    await wrapper.get('[data-testid="retry-task-analysis"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('任务一')
  })

  it('invalidates requests when closed', async () => {
    const pending = deferred<{ success: true; data: ReturnType<typeof analysis> }>()
    mocks.getTaskAnalysis.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    await wrapper.get('[data-testid="close"]').trigger('click')
    expect(wrapper.emitted('update:open')).toEqual([[false]])
    pending.resolve({ success: true, data: analysis('task-1', '关闭后迟到') })
    await flushPromises()
    expect(wrapper.text()).not.toContain('关闭后迟到')
  })
})
