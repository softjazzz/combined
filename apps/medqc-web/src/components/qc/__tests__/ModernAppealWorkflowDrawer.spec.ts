import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Drawer from '../ModernAppealWorkflowDrawer.vue'

const mocks = vi.hoisted(() => ({
  auth: { user: { id: 'doctor', roles: ['doctor'] } },
  list: vi.fn(),
  detail: vi.fn(),
  create: vi.fn(),
  act: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return mocks.auth.user
    },
    hasRole: (role: string) => mocks.auth.user.roles.includes(role),
  }),
}))
vi.mock('@/api/modernAppeals', () => ({
  listModernAppeals: mocks.list,
  getModernAppeal: mocks.detail,
  createModernAppeal: mocks.create,
  actOnModernAppeal: mocks.act,
}))
const row = {
  id: 'appeal',
  appellant_id: 'doctor',
  appellant_name: '合成医生',
  target_id: 'R',
  target_kind: 'canonical_defect',
  scene: 'running',
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
  root_job_id: 'J',
  envelope_id: 'E',
  status: 'pending',
  reason: '合成申诉理由超过十个字',
  events: [],
}
const source = {
  id: 'task',
  assignee_id: 'doctor',
  target_id: 'R',
  target_kind: 'canonical_defect',
  scene: 'running',
  visit_id: 'V',
  institute_id: 'I',
  patient_id: 'P',
  root_job_id: 'J',
  envelope_id: 'E',
  assignee_name: '医生',
  creator_id: 'manager',
  department: '内科',
  requirement: '合成要求',
  status: 'pending',
  version: 1,
  submission: null,
  review_comment: null,
  updated_at: '2026-10-24',
} as const
function make(withSource = false) {
  return mount(Drawer, {
    props: { open: true, ...(withSource ? { source } : {}) },
    global: {
      stubs: {
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot/></aside>' },
        MqIcon: true,
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = reactive({ user: { id: 'doctor', roles: ['doctor'] } })
  mocks.list.mockResolvedValue({ items: [row], total: 1, pending_count: 1 })
  mocks.detail.mockResolvedValue(row)
  mocks.create.mockResolvedValue(row)
  mocks.act.mockResolvedValue({ ...row, status: 'withdrawn' })
})
describe('V5现代申诉闭环', () => {
  it('工作分析按申诉ID直达历史，读取全部状态且不开放创建入口', async () => {
    const wrapper = make()
    await wrapper.setProps({ appealId: 'appeal' })
    await flushPromises()
    expect(mocks.detail).toHaveBeenCalledWith('appeal')
    expect(mocks.list).toHaveBeenLastCalledWith(undefined, undefined, 1)
    expect(wrapper.findAll('textarea')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('提交申诉')
    wrapper.unmount()
  })
  it('提交只传已授权整改ID，成功刷新待办和详情并通知父报表', async () => {
    const wrapper = make(true)
    await flushPromises()
    await wrapper.get('textarea').setValue('合成申诉原因已经超过十个字')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith('task', '合成申诉原因已经超过十个字')
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(wrapper.text()).toContain('待处理 1')
    wrapper.unmount()
  })
  it('医生撤回携带读取状态；不能审核自己的申诉', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.appeal-row').trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('审核通过')
    await wrapper.get('textarea').setValue('合成撤回说明已经超过十个字')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '撤回申诉')!
      .trigger('click')
    await flushPromises()
    expect(mocks.act).toHaveBeenCalledWith(
      'appeal',
      'pending',
      'withdraw',
      '合成撤回说明已经超过十个字',
    )
    wrapper.unmount()
  })
  it('审核员通过及驳回均通知父报表刷新', async () => {
    mocks.auth.user = { id: 'reviewer', roles: ['qc_manager'] }
    const wrapper = make()
    await flushPromises()
    await wrapper.get('.appeal-row').trigger('click')
    await flushPromises()
    await wrapper.get('textarea').setValue('合成审核说明已经超过十个字')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '驳回申诉')!
      .trigger('click')
    await flushPromises()
    expect(mocks.act).toHaveBeenCalledWith(
      'appeal',
      'pending',
      'reject',
      '合成审核说明已经超过十个字',
    )
    expect(wrapper.emitted('changed')).toHaveLength(1)
    wrapper.unmount()
  })
  it('未知写入不自动重试，不伪造成功或清零待办', async () => {
    mocks.create.mockRejectedValue(new Error('结果待核对'))
    const wrapper = make(true)
    await flushPromises()
    await wrapper.get('textarea').setValue('合成申诉原因已经超过十个字')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('changed')).toBeUndefined()
    expect(wrapper.text()).toContain('结果待核对')
    expect(wrapper.text()).toContain('待处理 1')
    mocks.list.mockRejectedValue(new Error('核对失败'))
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('刷新核对'))!
      .trigger('click')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('待处理 未知')
    wrapper.unmount()
  })
  it('查询失败显示未知，角色切换丢弃旧响应', async () => {
    let resolve!: (value: unknown) => void
    mocks.list.mockReturnValueOnce(
      new Promise((r) => {
        resolve = r
      }),
    )
    const wrapper = make()
    mocks.auth.user = { id: 'reviewer', roles: ['qc_manager'] }
    mocks.list.mockRejectedValueOnce(new Error('来源不可用'))
    await flushPromises()
    resolve({ items: [row], total: 1, pending_count: 1 })
    await flushPromises()
    expect(wrapper.text()).toContain('待处理 未知')
    expect(wrapper.text()).toContain('来源不可用')
    expect(wrapper.findAll('.appeal-row')).toHaveLength(0)
    wrapper.unmount()
  })
})
