import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

describe('QcRunSelectedControl', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
  })

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
