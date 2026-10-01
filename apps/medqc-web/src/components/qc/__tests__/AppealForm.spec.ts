import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppealForm from '@/components/qc/AppealForm.vue'

const state = vi.hoisted(() => ({
  authState: {
    user: { id: 'doctor-1', institute_id: 'H0', department: '心内科' },
    userRoles: ['doctor'] as string[],
  },
  auth: null as unknown as {
    user: { id: string; institute_id?: string; department?: string }
    userRoles: string[]
  },
  getCandidates: vi.fn(),
  createAppeal: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  state.auth = reactive(state.authState)
  return { useAuthStore: () => state.auth }
})
vi.mock('@/api/appeal', () => ({
  getAppealCandidates: state.getCandidates,
  createAppeal: state.createAppeal,
}))
vi.mock('ant-design-vue', () => ({ message: { success: state.success, error: state.error } }))

const candidates = {
  instituteId: 'H1',
  patientId: 'P1',
  visitId: 'V1',
  caseDepartment: '心内科',
  canonical: {
    state: 'ready',
    scene: 'running',
    jobId: 'job-1',
    envelopeId: 'env-1',
    items: [{ ruleId: 'LX0609-001', ruleName: '入院记录', conclusion: '超时' }],
  },
  manualDefects: [
    {
      defectId: 'manual-1',
      ruleCode: 'MANUAL',
      ruleName: '人工问题',
      description: '问题说明',
      scene: 'final',
    },
  ],
} as const
const slot = { template: '<div><slot /></div>' }
const stubs = {
  'a-modal': slot,
  'a-alert': slot,
  'a-form': slot,
  'a-form-item': slot,
  'a-input': true,
  'a-button': slot,
  'a-select': slot,
  'a-select-opt-group': slot,
  'a-select-option': slot,
  'a-textarea': true,
}
type Vm = {
  formState: {
    instituteId: string
    patientId: string
    visitId: string
    targetKey: string
    appealReason: string
  }
  candidates: typeof candidates | null
  candidatesError: string
  loadCandidates: () => Promise<void>
  handleSubmit: () => Promise<void>
}

describe('AppealForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.auth.user = { id: 'doctor-1', institute_id: 'H0', department: '心内科' }
    state.auth.userRoles = ['doctor']
    state.getCandidates.mockResolvedValue(candidates)
    state.createAppeal.mockResolvedValue({ id: 'appeal-1' })
  })

  it('从三坐标真实候选创建 Canonical 申诉，不传旧 recordId', async () => {
    const wrapper = mount(AppealForm, {
      props: { visible: true, instituteId: 'H1', patientId: 'P1', visitId: 'V1' },
      global: { stubs },
    })
    await flushPromises()
    const vm = wrapper.vm as unknown as Vm
    vm.formState.targetKey = 'canonical:LX0609-001'
    vm.formState.appealReason = '原判定与病历原文不一致，请复核。'
    await vm.handleSubmit()
    expect(state.createAppeal).toHaveBeenCalledWith(
      expect.objectContaining({
        targetKind: 'canonical_defect',
        instituteId: 'H1',
        patientId: 'P1',
        visitId: 'V1',
        scene: 'running',
        expectedJobId: 'job-1',
        expectedEnvelopeId: 'env-1',
        ruleId: 'LX0609-001',
      }),
    )
    expect(state.createAppeal.mock.calls[0]?.[0]).not.toHaveProperty('recordId')
  })

  it('坐标变更后丢弃迟到候选，不保留旧目标', async () => {
    let resolve!: (value: typeof candidates) => void
    state.getCandidates.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = mount(AppealForm, { props: { visible: true }, global: { stubs } })
    const vm = wrapper.vm as unknown as Vm
    vm.formState.instituteId = 'H1'
    vm.formState.patientId = 'P1'
    vm.formState.visitId = 'V1'
    const loading = vm.loadCandidates()
    vm.formState.visitId = 'V2'
    await nextTick()
    resolve(candidates)
    await loading
    expect(vm.candidates).toBeNull()
    expect(vm.formState.targetKey).toBe('')
  })

  it('使用当前账号医院作为默认值，归属变更时清空旧候选', async () => {
    const wrapper = mount(AppealForm, { props: { visible: true }, global: { stubs } })
    const vm = wrapper.vm as unknown as Vm
    expect(vm.formState.instituteId).toBe('H0')
    vm.formState.patientId = 'P1'
    vm.formState.visitId = 'V1'
    await nextTick()
    state.getCandidates.mockResolvedValueOnce({ ...candidates, instituteId: 'H0' })
    await vm.loadCandidates()
    expect(vm.candidates?.instituteId).toBe('H0')

    state.auth.user = { id: 'doctor-1', institute_id: 'H2', department: '骨科' }
    await nextTick()

    expect(vm.formState.instituteId).toBe('H2')
    expect(vm.candidates).toBeNull()
    expect(vm.formState.targetKey).toBe('')
  })

  it('关闭表单后丢弃迟到的提交成功回执', async () => {
    let resolve!: (value: { id: string }) => void
    state.createAppeal.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = mount(AppealForm, {
      props: { visible: true, instituteId: 'H1', patientId: 'P1', visitId: 'V1' },
      global: { stubs },
    })
    await flushPromises()
    const vm = wrapper.vm as unknown as Vm
    vm.formState.targetKey = 'canonical:LX0609-001'
    vm.formState.appealReason = '原判定与病历原文不一致，请复核。'
    const submit = vm.handleSubmit()

    await wrapper.setProps({ visible: false })
    resolve({ id: 'appeal-late' })
    await submit

    expect(state.success).not.toHaveBeenCalled()
    expect(state.error).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeUndefined()
  })
})
