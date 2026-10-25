import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createJob: vi.fn(),
  getJob: vi.fn(),
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  createSichuanWorkspaceBatchJob: mocks.createJob,
  getSichuanWorkspaceBatchJob: mocks.getJob,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 'selected-qc-user' } }),
}))

import QcRunSelectedControl from '@/views/workstation-v4/components/qc/QcRunSelectedControl.vue'

const recordRefs = [
  { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' },
  { institute_id: 'H2', patient_id: 'P2', visit_id: 'V2' },
]

enableAutoUnmount(afterEach)

describe('QcRunSelectedControl', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
  })

  afterEach(() => vi.useRealTimers())

  it('没有勾选病历时禁用质控入口', () => {
    const wrapper = mount(QcRunSelectedControl, {
      props: { carePhase: 'inpatient', recordRefs: [] },
    })

    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
    expect(wrapper.text()).toContain('质控所选')
  })

  it('只用勾选病历三坐标创建本地质控任务，不触发资料同步', async () => {
    mocks.createJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'queued' },
    })
    mocks.getJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'completed' },
    })
    const wrapper = mount(QcRunSelectedControl, {
      props: { carePhase: 'discharged', recordRefs },
    })

    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mocks.createJob).toHaveBeenCalledWith({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'final',
      date_field: 'discharge',
      record_refs: recordRefs,
    })
    expect(mocks.getJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.emitted('completed')).toHaveLength(1)
    expect(wrapper.emitted('results-updated')).toHaveLength(1)
  })

  it.each(['inpatient', 'discharged'] as const)(
    '%s 部分失败后刷新已保存结果，不冒充全部成功',
    async (carePhase) => {
      mocks.createJob.mockResolvedValue({
        success: true,
        data: { id: 'partial', status: 'queued' },
      })
      mocks.getJob.mockResolvedValue({
        success: true,
        data: {
          id: 'partial',
          status: 'failed',
          summary: {
            execution_status: 'partial_failed',
            completed_rule_count: 2050,
            failed_rule_count: 2,
            automatic_failed_rule_retry: { status: 'not_retryable', should_retry: false },
          },
        },
      })
      const wrapper = mount(QcRunSelectedControl, { props: { carePhase, recordRefs } })
      await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('results-updated')).toHaveLength(1)
      expect(wrapper.emitted('completed')).toBeUndefined()
      expect(wrapper.text()).toContain('不适合自动补跑')
      expect(mocks.createJob).toHaveBeenCalledTimes(1)
    },
  )

  it.each(['queued', 'running'])(
    '失败首轮的自动补跑 %s 时继续轮询，最终只刷新一次',
    async (retryStatus) => {
      vi.useFakeTimers()
      mocks.createJob.mockResolvedValue({ success: true, data: { id: 'retry', status: 'queued' } })
      mocks.getJob
        .mockResolvedValueOnce({
          success: true,
          data: {
            id: 'retry',
            status: 'failed',
            summary: { automatic_failed_rule_retry: { status: retryStatus, should_retry: true } },
          },
        })
        .mockResolvedValueOnce({ success: true, data: { id: 'retry', status: 'completed' } })
      const wrapper = mount(QcRunSelectedControl, { props: { carePhase: 'inpatient', recordRefs } })
      await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('results-updated')).toBeUndefined()
      expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
      await vi.advanceTimersByTimeAsync(3000)
      await flushPromises()
      expect(mocks.getJob).toHaveBeenCalledTimes(2)
      expect(wrapper.emitted('results-updated')).toHaveLength(1)
      expect(wrapper.emitted('completed')).toHaveLength(1)
      await vi.advanceTimersByTimeAsync(6000)
      expect(mocks.getJob).toHaveBeenCalledTimes(2)
    },
  )

  it('取消后的终态也刷新现有结果', async () => {
    mocks.createJob.mockResolvedValue({ success: true, data: { id: 'canceled', status: 'queued' } })
    mocks.getJob.mockResolvedValue({ success: true, data: { id: 'canceled', status: 'canceled' } })
    const wrapper = mount(QcRunSelectedControl, { props: { carePhase: 'discharged', recordRefs } })
    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('results-updated')).toHaveLength(1)
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('连续读取失败不当作后台结果已结束，也不刷新临床结果', async () => {
    vi.useFakeTimers()
    mocks.createJob.mockResolvedValue({ success: true, data: { id: 'network', status: 'queued' } })
    mocks.getJob.mockResolvedValue({ success: false, message: '网络不可用' })
    const wrapper = mount(QcRunSelectedControl, { props: { carePhase: 'inpatient', recordRefs } })
    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(6000)
    await flushPromises()
    expect(mocks.getJob).toHaveBeenCalledTimes(3)
    expect(wrapper.emitted('results-updated')).toBeUndefined()
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('本地病历未命中时明确提示先同步，不自动扩大质控范围', async () => {
    mocks.createJob.mockResolvedValue({
      success: false,
      message: '当前筛选条件下没有可执行病历',
    })
    const wrapper = mount(QcRunSelectedControl, {
      props: { carePhase: 'inpatient', recordRefs: [recordRefs[0]!] },
    })

    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mocks.createJob).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('当前筛选条件下没有可执行病历')
    expect(wrapper.text()).toContain('系统设置')
    expect(mocks.getJob).not.toHaveBeenCalled()
  })
})
