import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listTaskScheduleRuns: vi.fn(),
  runTaskScheduleNow: vi.fn(),
  retryTaskScheduleRun: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
}))
const authState = vi.hoisted(() => ({ user: { id: 'u-1' } as { id: string } | null }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/api/taskSchedules', () => ({
  listTaskScheduleRuns: mocks.listTaskScheduleRuns,
  runTaskScheduleNow: mocks.runTaskScheduleNow,
  retryTaskScheduleRun: mocks.retryTaskScheduleRun,
}))
vi.mock('ant-design-vue', () => ({
  Modal: { confirm: mocks.confirm },
  message: mocks.message,
}))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return { PlayCircleOutlined: icon, ReloadOutlined: icon }
})

import TaskScheduleRunsDrawer from '@/components/qc/TaskScheduleRunsDrawer.vue'
import type { TaskScheduleRunResponse } from '@/api/taskSchedules'

const run: TaskScheduleRunResponse = {
  id: 'run-1', schedule_id: 'schedule-1', trigger_type: 'scheduled',
  scheduled_fire_at: '2026-10-01T09:00:00+08:00', idempotency_key: 'schedule-1:fire-1',
  status: 'succeeded', generated_task_id: 'child-1', async_job_id: null, attempt_count: 1,
  heartbeat_at: null, started_at: '2026-10-01T09:00:01+08:00',
  finished_at: '2026-10-01T09:00:02+08:00', error_code: null, error_message: null,
  created_at: '2026-10-01T09:00:00+08:00', updated_at: '2026-10-01T09:00:02+08:00',
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return shallowMount(TaskScheduleRunsDrawer, {
    props: { open: true, scheduleId: 'schedule-1', scheduleName: '每日运行质控', ...props },
    global: {
      stubs: {
        'a-alert': { props: ['message'], template: '<div>{{ message }}</div>' },
        'a-button': { template: '<button><slot /></button>' },
        'a-drawer': { template: '<div><slot /></div>' },
        'a-empty': true,
        'a-pagination': true,
        'a-select': true,
        'a-spin': { template: '<div><slot /></div>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-tooltip': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('TaskScheduleRunsDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    authState.user = { id: 'u-1' }
    mocks.listTaskScheduleRuns.mockResolvedValue({
      success: true, data: { items: [run], total: 1, page: 1, page_size: 20 },
    })
    mocks.runTaskScheduleNow.mockResolvedValue({
      success: true, data: { ...run, trigger_type: 'manual', status: 'queued' },
    })
    mocks.retryTaskScheduleRun.mockResolvedValue({
      success: true, data: { ...run, status: 'queued', attempt_count: 2 },
    })
    mocks.confirm.mockImplementation((options: { onOk?: () => unknown }) => options.onOk?.())
  })

  afterEach(() => vi.unstubAllGlobals())

  it('读取具体计划的真实运行历史并显示生成任务', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    expect(mocks.listTaskScheduleRuns).toHaveBeenCalledWith('schedule-1', { page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('抽样完成')
    expect(wrapper.text()).toContain('child-1')
    expect(wrapper.find('[data-testid="run-now"]').exists()).toBe(true)
    const taskLink = wrapper.findAll('button').find((button) => button.text().includes('child-1'))
    await taskLink?.trigger('click')
    expect(wrapper.emitted('view-task')?.[0]).toEqual(['child-1'])
  })

  it('切换计划后丢弃旧计划迟到响应', async () => {
    const pending = deferred<{
      success: boolean
      data: { items: TaskScheduleRunResponse[]; total: number; page: number; page_size: number }
    }>()
    mocks.listTaskScheduleRuns.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    mocks.listTaskScheduleRuns.mockResolvedValueOnce({
      success: true,
      data: { items: [{ ...run, id: 'run-2', schedule_id: 'schedule-2' }], total: 1, page: 1, page_size: 20 },
    })
    await wrapper.setProps({ scheduleId: 'schedule-2' })
    pending.resolve({ success: true, data: { items: [run], total: 1, page: 1, page_size: 20 } })
    await flushPromises()
    const vm = wrapper.vm as unknown as { runs: TaskScheduleRunResponse[] }
    expect(vm.runs.map((item) => item.schedule_id)).toEqual(['schedule-2'])
  })

  it('读取失败保持空列表，不伪造成功运行', async () => {
    mocks.listTaskScheduleRuns.mockResolvedValue({ success: false, message: '运行历史不可用' })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { runs: TaskScheduleRunResponse[]; loadError: string }
    expect(vm.runs).toEqual([])
    expect(vm.loadError).toBe('运行历史不可用')
    expect(wrapper.text()).not.toContain('抽样完成')
  })

  it('立即运行使用稳定幂等键，未知结果只用原编号安全重试', async () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'request-123' })
    mocks.runTaskScheduleNow.mockResolvedValue({ success: false, uncertain: true, message: '结果未知' })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { confirmRunNow: () => void }
    vm.confirmRunNow()
    await flushPromises()
    wrapper.unmount()
    const restored = mountDrawer()
    await flushPromises()
    ;(restored.vm as unknown as { confirmRunNow: () => void }).confirmRunNow()
    await flushPromises()
    expect(mocks.runTaskScheduleNow.mock.calls).toEqual([
      ['schedule-1', 'request-123'],
      ['schedule-1', 'request-123'],
    ])
  })

  it('失败运行即使已有子任务仍显示错误，并用原运行 ID 重试', async () => {
    const failed = {
      ...run, status: 'failed' as const, generated_task_id: 'child-failed', error_message: '抽样写入失败',
    }
    mocks.listTaskScheduleRuns.mockResolvedValue({
      success: true, data: { items: [failed], total: 1, page: 1, page_size: 20 },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.text()).toContain('抽样写入失败')
    expect(wrapper.text()).toContain('child-failed')
    const vm = wrapper.vm as unknown as { confirmRetry: (item: TaskScheduleRunResponse) => void }
    vm.confirmRetry(failed)
    await flushPromises()
    expect(mocks.retryTaskScheduleRun).toHaveBeenCalledWith('run-1')
  })
})
