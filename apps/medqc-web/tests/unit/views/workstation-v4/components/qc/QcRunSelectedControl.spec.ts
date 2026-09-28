import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createJob: vi.fn(),
  getJob: vi.fn(),
  authStore: null as null | { user: { id: string } | null; userRoles: string[] },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  createSichuanWorkspaceBatchJob: mocks.createJob,
  getSichuanWorkspaceBatchJob: mocks.getJob,
}))

vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  return {
    useAuthStore: () => {
      if (!mocks.authStore) mocks.authStore = reactive({ user: { id: 'selected-qc-user' }, userRoles: ['qc_manager'] })
      return mocks.authStore
    },
  }
})

import QcRunSelectedControl from '@/views/workstation-v4/components/qc/QcRunSelectedControl.vue'

const recordRefs = [
  { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' },
  { institute_id: 'H2', patient_id: 'P2', visit_id: 'V2' },
]

const ModalStub = defineComponent({
  props: { open: Boolean }, emits: ['ok', 'cancel'],
  template: '<section v-if="open" data-testid="selected-qc-confirm"><slot/><button data-testid="selected-qc-confirm-ok" @click="$emit(\'ok\')">确认</button><button data-testid="selected-qc-confirm-cancel" @click="$emit(\'cancel\')">取消</button></section>',
})

function mountControl(props: { carePhase: 'inpatient' | 'discharged'; recordRefs: typeof recordRefs; selectedCount?: number }) {
  return mount(QcRunSelectedControl, { props, global: { stubs: { 'a-modal': ModalStub } } })
}

async function confirmRun(wrapper: ReturnType<typeof mountControl>) {
  await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
  await wrapper.get('[data-testid="selected-qc-confirm-ok"]').trigger('click')
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('QcRunSelectedControl', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    mocks.authStore = null
  })

  it('没有勾选病历时禁用质控入口', () => {
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs: [] })

    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
    expect(wrapper.text()).toContain('质控所选')
  })

  it('已出院列表即使有完整三坐标也不能创建未核验归档的终末任务', async () => {
    const wrapper = mountControl({ carePhase: 'discharged', recordRefs })

    const trigger = wrapper.get('[data-testid="run-selected-qc-trigger"]')
    expect(trigger.attributes('disabled')).toBe('')
    expect(wrapper.text()).toContain('此列表未核验归档状态，暂不可发起终末质控')
    await trigger.trigger('click')
    await flushPromises()

    expect(mocks.createJob).not.toHaveBeenCalled()
    expect(mocks.getJob).not.toHaveBeenCalled()
  })

  it('只用在院勾选病历三坐标创建本地质控任务，不触发资料同步', async () => {
    mocks.createJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'queued' },
    })
    mocks.getJob.mockResolvedValue({
      success: true,
      data: { id: 'job-1', status: 'completed' },
    })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })

    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    expect(mocks.createJob).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="selected-qc-confirm"]').text()).toContain('luxian_0609_qc_v1')
    await wrapper.get('[data-testid="selected-qc-confirm-ok"]').trigger('click')
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mocks.createJob).toHaveBeenCalledWith({
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'running',
      date_field: 'admission',
      record_refs: recordRefs,
    })
    expect(mocks.getJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.emitted('completed')).toHaveLength(1)
  })

  it('创建请求回执失败时保留原信息并锁定重复提交', async () => {
    mocks.createJob.mockResolvedValue({
      success: false,
      message: '当前筛选条件下没有可执行病历',
    })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs: [recordRefs[0]!] })

    await confirmRun(wrapper)
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mocks.createJob).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('当前筛选条件下没有可执行病历')
    expect(wrapper.text()).toContain('创建结果未确认')
    expect(wrapper.text()).toContain('勿直接重复提交')
    expect(wrapper.text()).not.toContain('系统设置')
    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
    expect(mocks.getJob).not.toHaveBeenCalled()
  })

  it('取消二次确认不创建任务，确认后仍使用打开时冻结的精确三坐标', async () => {
    mocks.createJob.mockResolvedValue({ success: true, data: { id: 'job-frozen', status: 'queued' } })
    mocks.getJob.mockResolvedValue({ success: true, data: { id: 'job-frozen', status: 'completed' } })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await wrapper.get('[data-testid="selected-qc-confirm-cancel"]').trigger('click')
    expect(mocks.createJob).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="run-selected-qc-trigger"]').trigger('click')
    await wrapper.setProps({ recordRefs: [{ institute_id: 'H3', patient_id: 'P3', visit_id: 'V3' }] })
    await wrapper.get('[data-testid="selected-qc-confirm-ok"]').trigger('click')
    await flushPromises()
    expect(mocks.createJob).toHaveBeenCalledWith(expect.objectContaining({ record_refs: recordRefs }))
  })

  it.each([
    { refs: [{ institute_id: 'H1', patient_id: '', visit_id: 'V1' }], count: 1, text: '不完整身份' },
    { refs: [recordRefs[0]!, recordRefs[0]!], count: 2, text: '重复身份' },
    { refs: [recordRefs[0]!], count: 2, text: '数量与身份清单不一致' },
  ])('身份清单异常时整批拒绝：$text', async ({ refs, count, text }) => {
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs: refs, selectedCount: count })
    expect(wrapper.text()).toContain(text)
    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
    expect(mocks.createJob).not.toHaveBeenCalled()
  })

  it('切换账号时丢弃迟到创建回执，不轮询也不刷新', async () => {
    const pending = deferred<{ success: true; data: { id: string; status: string } }>()
    mocks.createJob.mockReturnValueOnce(pending.promise)
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    if (!mocks.authStore) throw new Error('auth missing')
    mocks.authStore.user = { id: 'other-user' }
    await nextTick()
    pending.resolve({ success: true, data: { id: 'old-job', status: 'queued' } })
    await flushPromises()
    expect(mocks.getJob).not.toHaveBeenCalled()
    expect(wrapper.emitted('completed')).toBeUndefined()
    expect(wrapper.text()).not.toContain('old-job')
  })

  it('同账号角色变化时丢弃迟到创建回执', async () => {
    const pending = deferred<{ success: true; data: { id: string; status: string } }>()
    mocks.createJob.mockReturnValueOnce(pending.promise)
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    if (!mocks.authStore) throw new Error('auth missing')
    mocks.authStore.userRoles = ['admin']
    await nextTick()
    pending.resolve({ success: true, data: { id: 'old-role-job', status: 'queued' } })
    await flushPromises()
    expect(mocks.getJob).not.toHaveBeenCalled()
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('轮询回执 job id 不匹配时失败关闭且不刷新', async () => {
    mocks.createJob.mockResolvedValue({ success: true, data: { id: 'expected-job', status: 'queued' } })
    mocks.getJob.mockResolvedValue({ success: true, data: { id: 'other-job', status: 'completed' } })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    await flushPromises()
    expect(wrapper.text()).toContain('任务身份与请求不一致')
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('创建回执缺失或异常时锁定重复提交并提示先核对', async () => {
    mocks.createJob.mockResolvedValueOnce({ success: true, data: { id: '   ', status: 'queued' } })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    await flushPromises()
    expect(wrapper.text()).toContain('创建结果未确认')
    expect(wrapper.text()).toContain('勿直接重复提交')
    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
  })

  it('无法区分拒绝与断网的失败回执保留原错误并锁定重复提交', async () => {
    mocks.createJob.mockResolvedValue({ success: false, message: '无权发起全院质控' })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    await flushPromises()
    expect(wrapper.text()).toContain('无权发起全院质控')
    expect(wrapper.text()).toContain('创建结果未确认')
    expect(wrapper.text()).not.toContain('系统设置同步')
    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
  })

  it('未知任务状态失败关闭且不刷新', async () => {
    mocks.createJob.mockResolvedValue({ success: true, data: { id: 'unknown-job', status: 'queued' } })
    mocks.getJob.mockResolvedValue({ success: true, data: { id: 'unknown-job', status: 'mystery' } })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    await flushPromises()
    expect(wrapper.text()).toContain('未知状态')
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('卸载后丢弃迟到创建回执', async () => {
    const pending = deferred<{ success: true; data: { id: string; status: string } }>()
    mocks.createJob.mockReturnValueOnce(pending.promise)
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await confirmRun(wrapper)
    wrapper.unmount()
    pending.resolve({ success: true, data: { id: 'unmounted-job', status: 'queued' } })
    await flushPromises()
    expect(mocks.getJob).not.toHaveBeenCalled()
    expect(wrapper.emitted('completed')).toBeUndefined()
  })

  it('同账号角色变化不恢复旧角色任务，且 qc_staff 无全院入口权限', async () => {
    if (!mocks.authStore) {
      mountControl({ carePhase: 'inpatient', recordRefs }).unmount()
    }
    if (!mocks.authStore) throw new Error('auth missing')
    const oldActor = 'selected-qc-user|admin'
    window.sessionStorage.setItem(
      `medqc:selected-qc:running:${encodeURIComponent(oldActor)}`,
      JSON.stringify({ jobId: 'admin-job', actor: oldActor }),
    )
    mocks.authStore.userRoles = ['qc_manager']
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await flushPromises()
    expect(mocks.getJob).not.toHaveBeenCalled()
    mocks.authStore.userRoles = ['qc_staff']
    await nextTick()
    expect(wrapper.get('[data-testid="run-selected-qc-trigger"]').attributes('disabled')).toBe('')
  })

  it('仅恢复当前账号与角色的任务，完成刷新只发出一次', async () => {
    const actor = 'selected-qc-user|qc_manager'
    window.sessionStorage.setItem(
      `medqc:selected-qc:running:${encodeURIComponent(actor)}`,
      JSON.stringify({ jobId: 'recover-job', actor }),
    )
    mocks.getJob.mockResolvedValue({ success: true, data: { id: 'recover-job', status: 'completed' } })
    const wrapper = mountControl({ carePhase: 'inpatient', recordRefs })
    await flushPromises()
    expect(mocks.getJob).toHaveBeenCalledWith('recover-job')
    expect(wrapper.emitted('completed')).toHaveLength(1)
  })
})
