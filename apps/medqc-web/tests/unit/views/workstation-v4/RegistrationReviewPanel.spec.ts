import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Panel from '@/views/workstation-v4/components/system-config/RegistrationReviewPanel.vue'
import type { RegistrationDetail, RegistrationPage } from '@/api/accountRegistration'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  review: vi.fn(),
  success: vi.fn(),
}))
const actor = reactive({ user: { id: 'admin' }, userRoles: ['admin'] })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => actor }))
vi.mock('@/api/accountRegistration', () => ({
  listRegistrations: api.list,
  getRegistrationDetail: api.detail,
  reviewRegistration: api.review,
}))
vi.mock('ant-design-vue', () => ({ message: { success: api.success } }))
const detail: RegistrationDetail = {
  user_id: 'request-id',
  username: 'doctor1',
  email: 'synthetic@example.com',
  display_name: '申请医生',
  status: 'pending',
  version: 1,
  requested_institute_id: 'A',
  requested_department: '内科',
  submitted_at: '2026-10-25T01:00:00Z',
  reviewed_at: null,
  updated_at: '2026-10-25T01:00:00Z',
  review_comment: null,
  history: [
    {
      id: 'event',
      actor_id: 'request-id',
      action: 'submit',
      version: 1,
      comment: '提交注册申请',
      institute_id: 'A',
      department: '内科',
      roles_json: '[]',
      created_at: '2026-10-25T01:00:00Z',
    },
  ],
}
const page: RegistrationPage = { items: [detail], total: 1, page: 1, page_size: 20 }
function make(registrationId?: string) {
  return mount(Panel, {
    props: { registrationId },
    global: {
      stubs: { AModal: { props: ['open'], template: '<aside v-if="open"><slot/></aside>' } },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  actor.user.id = 'admin'
  actor.userRoles = ['admin']
  api.list.mockResolvedValue(structuredClone(page))
  api.detail.mockResolvedValue(structuredClone(detail))
  api.review.mockResolvedValue({ ...detail, status: 'approved', version: 2 })
})
describe('V5注册审批', () => {
  it('真实队列、空态和错误，不显示模拟申请', async () => {
    const wrapper = make()
    expect(wrapper.text()).toContain('正在读取注册申请')
    await flushPromises()
    expect(wrapper.text()).toContain('申请医生')
    await wrapper.get('select[aria-label="申请状态"]').setValue('approved')
    api.list.mockResolvedValueOnce({ ...page, items: [], total: 0 })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({ status: 'approved', page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('暂无匹配申请')
    api.list.mockRejectedValueOnce(new Error('注册服务暂不可用'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('申请未能加载')
    expect(wrapper.text()).not.toContain('申请医生')
    wrapper.unmount()
  })
  it('通过要求核定范围和角色，带申请版本，无口令或启用标志', async () => {
    const wrapper = make('request-id')
    await flushPromises()
    expect(api.detail).toHaveBeenCalledWith('request-id')
    expect(wrapper.get('aside').text()).toContain('提交申请')
    await wrapper.get('input[aria-label="核定科室"]').setValue('外科')
    await wrapper.get('textarea').setValue('已核验人员和机构资料')
    api.detail.mockResolvedValueOnce({ ...detail, status: 'approved' })
    await wrapper.get('.registration-review').trigger('submit')
    await flushPromises()
    expect(api.review).toHaveBeenCalledWith('request-id', {
      expected_version: 1,
      decision: 'approve',
      comment: '已核验人员和机构资料',
      institute_id: 'A',
      department: '外科',
      roles: ['doctor'],
    })
    expect(wrapper.find('.registration-review').exists()).toBe(false)
    expect(api.success).toHaveBeenCalledWith('账号已开通，结果通知已发送')
    wrapper.unmount()
  })
  it('驳回只提交原因，不夹带权限；冲突后不伪造成功并可重新核对', async () => {
    const wrapper = make('request-id')
    await flushPromises()
    await wrapper.get('select[aria-label="审批决定"]').setValue('reject')
    expect(wrapper.find('input[aria-label="核定机构"]').exists()).toBe(false)
    await wrapper.get('textarea').setValue('资料不完整，请补齐')
    api.review.mockRejectedValueOnce(new Error('申请已处理，请刷新'))
    await wrapper.get('.registration-review').trigger('submit')
    await flushPromises()
    expect(api.review).toHaveBeenCalledWith('request-id', {
      expected_version: 1,
      decision: 'reject',
      comment: '资料不完整，请补齐',
    })
    expect(api.success).not.toHaveBeenCalled()
    expect(wrapper.get('aside').text()).toContain('申请已处理，请刷新')
    expect(
      wrapper.get('.registration-review button[type="submit"]').attributes('disabled'),
    ).toBeDefined()
    await wrapper.get('aside button.mq-btn').trigger('click')
    await flushPromises()
    expect(api.detail).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
  it('账号切换使旧响应失效，不泄露旧申请', async () => {
    let resolve!: (value: RegistrationDetail) => void
    api.detail.mockReturnValueOnce(
      new Promise<RegistrationDetail>((r) => {
        resolve = r
      }),
    )
    const wrapper = make('request-id')
    await flushPromises()
    actor.user.id = 'doctor'
    actor.userRoles = ['doctor']
    await flushPromises()
    resolve(detail)
    await flushPromises()
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('申请医生')
    expect(wrapper.text()).toContain('仅持久系统管理员可审批')
    wrapper.unmount()
  })
})
