import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import View from '@/views/auth/RegisterView.vue'
import type { RegistrationResult } from '@/api/accountRegistration'

const api = vi.hoisted(() => ({ submit: vi.fn(), status: vi.fn(), own: vi.fn() }))
const actor = reactive({ user: { id: '' }, isAuthenticated: false })
const route = reactive<{ query: { mode?: string } }>({ query: {} })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => actor }))
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/api/accountRegistration', () => ({
  submitRegistration: api.submit,
  queryRegistrationStatus: api.status,
  getOwnRegistration: api.own,
}))
const result: RegistrationResult = {
  user_id: 'request-id',
  status: 'pending',
  version: 1,
  requested_institute_id: 'A',
  requested_department: '内科',
  submitted_at: '2026-10-25T01:00:00Z',
  updated_at: '2026-10-25T01:00:00Z',
  reviewed_at: null,
  review_comment: null,
}
function make() {
  return mount(View, { global: { stubs: { RouterLink: { template: '<a><slot/></a>' } } } })
}
async function fill(wrapper: ReturnType<typeof make>) {
  for (const [label, value] of Object.entries({
    注册用户名: 'doctor1',
    工作邮箱: 'synthetic@example.com',
    申请姓名: '申请医生',
    申请机构: 'A',
    申请科室: '内科',
    注册口令: 'synthetic-only-secret!',
    确认口令: 'synthetic-only-secret!',
  }))
    await wrapper.get(`input[aria-label="${label}"]`).setValue(value)
}
beforeEach(() => {
  vi.clearAllMocks()
  actor.user.id = ''
  actor.isAuthenticated = false
  route.query = {}
  api.submit.mockResolvedValue(structuredClone(result))
  api.status.mockResolvedValue(structuredClone(result))
  api.own.mockResolvedValue({ ...result, status: 'approved', is_active: true })
})
describe('注册申请与登录外结果查询', () => {
  it('提交真实接口，不模拟成功、自动登录或承诺邮件', async () => {
    const wrapper = make()
    await fill(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.submit).toHaveBeenCalledWith({
      username: 'doctor1',
      email: 'synthetic@example.com',
      display_name: '申请医生',
      institute_id: 'A',
      department: '内科',
      password: 'synthetic-only-secret!',
    })
    expect(wrapper.text()).toContain('待审批 · 尚未开通')
    expect(wrapper.text()).not.toContain('邮件')
    expect(actor.isAuthenticated).toBe(false)
    expect((wrapper.get('input[aria-label="注册口令"]').element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })
  it('口令不一致不请求，服务失败不能显示成功', async () => {
    const wrapper = make()
    await fill(wrapper)
    await wrapper.get('input[aria-label="确认口令"]').setValue('different-secret!')
    await wrapper.get('form').trigger('submit')
    expect(api.submit).not.toHaveBeenCalled()
    await wrapper.get('input[aria-label="确认口令"]').setValue('synthetic-only-secret!')
    api.submit.mockRejectedValueOnce(new Error('未配置审批管理员'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('未配置审批管理员')
    expect(wrapper.find('[aria-label="申请结果"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('未登录只查自己的结果，不保存口令或生成业务身份', async () => {
    route.query = { mode: 'status' }
    api.status.mockResolvedValueOnce({
      ...result,
      status: 'rejected',
      review_comment: '请核实机构',
      reviewed_at: result.updated_at,
    })
    const wrapper = make()
    await wrapper.get('[aria-label="查询账号"]').setValue('doctor1')
    await wrapper.get('[aria-label="查询口令"]').setValue('synthetic-only-secret!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.status).toHaveBeenCalledWith('doctor1', 'synthetic-only-secret!')
    expect(wrapper.text()).toContain('已驳回 · 尚未开通')
    expect(wrapper.text()).toContain('请核实机构')
    expect((wrapper.get('[aria-label="查询口令"]').element as HTMLInputElement).value).toBe('')
    expect(actor.isAuthenticated).toBe(false)
    wrapper.unmount()
  })
  it('消息回执入口读本人结果，旧账号响应失效', async () => {
    route.query = { mode: 'status' }
    actor.user.id = 'doctor'
    actor.isAuthenticated = true
    let resolve!: (value: RegistrationResult) => void
    api.own.mockReturnValueOnce(
      new Promise<RegistrationResult>((r) => {
        resolve = r
      }),
    )
    const wrapper = make()
    await flushPromises()
    expect(api.own).toHaveBeenCalledTimes(1)
    actor.user.id = 'other'
    actor.isAuthenticated = false
    await flushPromises()
    resolve({ ...result, status: 'approved' })
    await flushPromises()
    expect(wrapper.find('[aria-label="申请结果"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
